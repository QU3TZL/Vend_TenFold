"""
FASTAPI APPLICATION CONFIGURATION
==============================

This is the main entry point for the TenFold application. It handles:
1. Route Configuration
2. Template Setup
3. Static File Serving
4. State Management

Key Components:
-------------
1. Route Configuration
   - All route prefixes are defined here
   - Individual route files should NOT include prefixes
   - Route structure:
     * /api/state/visitor/* -> visitor_routes.py
     * /api/state/auth/* -> auth_routes.py
     * /api/state/payment/* -> payment_routes.py
     * /api/state/drive/* -> drive_routes.py
     * /api/state/active/* -> active_routes.py

2. Template Configuration
   - Multiple template directories supported
   - Search order:
     1. State-specific templates
     2. Shared templates
   - Template directories:
     * src/api/state/shared/templates/
     * src/api/state/visitor/templates/
     * src/api/state/auth/templates/
     * src/api/state/payment/templates/
     * src/api/state/drive/templates/
     * src/api/state/active/templates/

3. Static File Serving
   - Base directory: src/static/
   - URL prefix: /static/
   - Directories:
     * /static/css/ - Stylesheets
     * /static/js/ - JavaScript files
     * /static/img/ - Images

4. State Management
   - StateManager initialized at startup
   - Handles user state transitions
   - Manages state persistence
   - Controls state-based UI rendering

Common Issues:
------------
1. Route Conflicts
   - Check prefix definitions in this file
   - Verify route files don't include prefixes
   - Debug URL patterns with router.url_path_for()

2. Template Not Found
   - Verify template directories are correctly listed
   - Check template exists in correct location
   - Enable debug logging for template loading

3. Static Files 404
   - Check static_dir path is correct
   - Verify file exists in static directory
   - Debug static file mounting
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
import logging
import os
from pathlib import Path
from src.services.logging.state_logger import StateLogger
import traceback
from src.services.state.state_manager import StateManager

# Import routers
from src.api import (
    visitor_router,
    auth_router,
    payment_router,
    drive_router,
    active_router
)

# Initialize state logger first
state_logger = StateLogger()

# Set log levels for key components
logging.getLogger('uvicorn').setLevel(logging.DEBUG)
logging.getLogger('fastapi').setLevel(logging.DEBUG)
logging.getLogger('src.api.state.payment.stripe_service').setLevel(logging.DEBUG)

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(visitor_router, prefix="/api/state/visitor")
app.include_router(auth_router, prefix="/api/state/auth")
app.include_router(payment_router, prefix="/api/state/payment")
app.include_router(drive_router, prefix="/api/state/drive")
app.include_router(active_router, prefix="/api/state/active")

# Configure static files and templates
static_dir = Path(__file__).parent / "src" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Set up templates with multiple directories
template_dirs = [
    Path(__file__).parent / "src/api/state/shared/templates",
    Path(__file__).parent / "src/api/state/visitor/templates",
    Path(__file__).parent / "src/api/state/auth/templates",
    Path(__file__).parent / "src/api/state/payment/templates",
    Path(__file__).parent / "src/api/state/drive/templates",
    Path(__file__).parent / "src/api/state/active/templates"
]

# Verify template directories exist and log their contents
for dir_path in template_dirs:
    state_logger.db_event("template_check", {
        "directory": str(dir_path),
        "exists": dir_path.exists(),
        "files": [f.name for f in dir_path.glob("*.html")] if dir_path.exists() else []
    })

# Configure templates with FileSystemLoader for multiple directories
loader = FileSystemLoader([str(d) for d in template_dirs])
templates = Jinja2Templates(
    directory=str(template_dirs[0]),  # Use first directory as primary
    loader=loader  # Use our loader instance
)

# Test template loading
try:
    state_logger.db_event("template_test", {
        "action": "loading_visitor_box",
        "template_dirs": [str(d) for d in template_dirs],
        "exists": [d.exists() for d in template_dirs],
        "files": {str(d): [f.name for f in d.glob("*.html")] if d.exists() else [] for d in template_dirs}
    })
    
    # Try to load visitor_box.html directly
    template = loader.get_source(templates.env, "visitor_box.html")
    state_logger.db_event("template_test", {
        "action": "visitor_box_found",
        "template": "visitor_box.html",
        "source_length": len(template[0]) if template else 0
    })
except Exception as e:
    state_logger.error("template_test", "Failed to load visitor_box.html", {
        "error": str(e),
        "type": type(e).__name__,
        "stack": traceback.format_exc()
    })

# Create state manager instance
state_manager = StateManager()
app.state.state_manager = state_manager

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize active service with state manager
        from src.api.state.active.active_service import ActiveService
        from src.database.supabase import get_supabase_client
        
        app.state.active_service = ActiveService(state_manager, get_supabase_client())
        await app.state.active_service.init_deployment_listener()
        
        state_logger.db_event("startup", {
            "status": "completed",
            "services": ["active_service", "deployment_listener"]
        })
    except Exception as e:
        state_logger.error("startup", "Failed to initialize services", {
            "error": str(e)
        })
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    try:
        if hasattr(app.state, 'active_service'):
            # Clean up active service
            await app.state.active_service.cleanup()
        
        state_logger.db_event("shutdown", {
            "status": "completed",
            "services": ["active_service"]
        })
    except Exception as e:
        state_logger.error("shutdown", "Failed to clean up services", {
            "error": str(e)
        })

# Root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    try:
        # Get current state from token if available
        token = request.cookies.get('access_token')
        current_state = None
        user_id = "anonymous"
        user_data = None
        
        if token:
            try:
                user_data = await state_manager.verify_session_token(token)
                if user_data:
                    user_id = user_data['auth_id']
                    current_state = await state_manager.get_current_state(user_id)
                    state_logger.db_event("state_check", {
                        "user_id": user_id,
                        "current_state": current_state.get('current_state'),
                        "has_metadata": bool(current_state.get('state_metadata'))
                    })
            except Exception as e:
                state_logger.error("auth", "Token verification failed", {
                    "user_id": user_id,
                    "error_type": type(e).__name__
                })
        
        # Get current state data
        state_data = current_state if current_state else await state_manager.get_current_state()
        
        state_logger.db_event("state_data", {
            "action": "preparing_context",
            "state_data": state_data,
            "current_state": current_state
        })
        
        # Prepare template context with state data and environment
        context = {
            "request": request,
            "current_state": state_data["current_state"],
            "state_metadata": state_data["state_metadata"],
            "user": user_data if user_data else None,
            "google_client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "env": os.getenv('ENV', 'development')  # Add environment to context
        }
        
        state_logger.db_event("state_data", {
            "action": "final_context",
            "current_state": context["current_state"],
            "state_metadata": context["state_metadata"],
            "has_user": bool(context["user"])
        })
        
        state_logger.db_event("template_render", {
            "template": "home.html",
            "user_id": user_id,
            "current_state": context["current_state"],
            "has_metadata": bool(context["state_metadata"])
        })
        
        try:
            # Try to get the template first
            template = templates.env.get_template("home.html")
            state_logger.db_event("template_render", {
                "action": "template_found",
                "template": "home.html",
                "loader_paths": templates.env.loader.searchpath
            })
            
            # Try rendering
            rendered = template.render(context)
            state_logger.db_event("template_render", {
                "action": "render_success",
                "template": "home.html",
                "context_keys": list(context.keys())
            })
            
            return HTMLResponse(rendered)
            
        except Exception as e:
            state_logger.error("template_render", "Template rendering failed", {
                "error": str(e),
                "type": type(e).__name__,
                "stack": traceback.format_exc(),
                "template_dirs": [str(d) for d in template_dirs],
                "template_files": {str(d): [f.name for f in d.glob("*.html")] if d.exists() else [] for d in template_dirs}
            })
            raise HTTPException(status_code=500, detail="Template rendering failed")
    except Exception as e:
        state_logger.error("template", "Failed to render home template", {
            "error": str(e),
            "stack": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail="Internal server error")

# Add state endpoint
@app.get("/api/state")
async def get_current_state(request: Request):
    """Get the current state and metadata"""
    try:
        # Get user ID from token if available
        token = request.cookies.get('access_token')
        if token:
            user_data = await state_manager.verify_session_token(token)
            if user_data:
                current_state = await state_manager.get_current_state(user_data['auth_id'])
                return {
                    "success": True,
                    "data": current_state
                }

        # Return visitor state if no token or invalid token
        return {
            "success": True,
            "data": {
                "current_state": "VISITOR",
                "state_metadata": {
                    "allowed_transitions": ["AUTH"]
                }
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
