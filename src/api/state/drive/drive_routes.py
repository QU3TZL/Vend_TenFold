"""
# Drive Routes and OAuth Flow
# =========================
#
# This module handles the OAuth flow and Drive-related routes.
# For OAuth scopes and permission model, see google.py.
#
# Route Handlers
# -------------
# 1. OAuth Flow
#    - Generate auth URL
#    - Handle callbacks
#    - Process tokens
#
# 2. Drive Operations
#    - Create folders
#    - Set permissions
#    - Manage access
#
# 3. State Management
#    - Track auth status
#    - Handle transitions
#    - Monitor changes
"""

from fastapi import APIRouter, HTTPException, Response, Request, Depends
from typing import Dict, Optional
from .drive_service import DriveService
from .google import GoogleOAuthHandler
from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager
from datetime import datetime
from fastapi.responses import RedirectResponse
import json
from sse_starlette.sse import EventSourceResponse
import traceback
import os
from fastapi.responses import JSONResponse
import base64
from src.services.logging.state_logger import StateLogger

# Initialize state logger
state_logger = StateLogger()

router = APIRouter(tags=["drive"])

def get_state_manager(request: Request) -> StateManager:
    return request.app.state.state_manager

def get_drive_service(request: Request) -> DriveService:
    state_manager = get_state_manager(request)
    return DriveService(state_manager=state_manager, supabase_client=get_supabase_client())

def get_oauth_handler(request: Request) -> GoogleOAuthHandler:
    """Get or create OAuth handler with consistent configuration"""
    if not hasattr(request.app.state, 'oauth_handler'):
        state_logger.drive_event("oauth_handler_create", {"status": "creating_new"})
        request.app.state.oauth_handler = GoogleOAuthHandler()
    else:
        state_logger.drive_event("oauth_handler_get", {"status": "using_existing"})
    
    handler = request.app.state.oauth_handler
    state_logger.drive_event("oauth_handler_config", {
        "redirect_uri": handler.redirect_uri,
        "has_client_id": bool(handler.client_id),
        "has_client_secret": bool(handler.client_secret)
    })
    
    return handler

@router.get("")
async def get_drive_info(request: Request, drive_service: DriveService = Depends(get_drive_service)):
    """Get information for the drive state"""
    try:
        # Get user ID from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        drive_info = await drive_service.get_drive_info(user_data['auth_id'])
        return {
            "success": True,
            "data": drive_info
        }
    except HTTPException:
        raise
    except Exception as e:
        state_logger.error("drive", "Failed to get drive info", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify")
async def verify_drive_tokens(request: Request, tokens: Dict, drive_service: DriveService = Depends(get_drive_service)):
    """Verify drive tokens are valid"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Verify tokens
        is_valid = await drive_service.verify_drive_tokens(tokens)
        
        return {
            "success": True,
            "data": {"valid": is_valid}
        }
        
    except Exception as e:
        state_logger.error("drive", "Failed to verify drive tokens", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folder")
async def create_folder(request: Request, drive_service: DriveService = Depends(get_drive_service)):
    """Create a new folder in Drive"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Get user email from state
        state = await get_state_manager(request).get_current_state(user_data['auth_id'])
        user_email = state.get('state_metadata', {}).get('user', {}).get('email')
        
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
            
        # Create folder
        folder = await drive_service.create_folder(user_email)
        
        if not folder:
            raise HTTPException(status_code=500, detail="Failed to create folder")
            
        return {
            "success": True,
            "data": folder
        }
        
    except HTTPException:
        raise
    except Exception as e:
        state_logger.error("drive", "Failed to create folder", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transition")
async def transition_drive_state(request: Request, target_state: str, state_data: Optional[Dict] = None):
    """Transition from DRIVE to another state"""
    try:
        # Verify user is authenticated
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Attempt state transition
        success, result = await drive_service.transition_state(
            user_data['auth_id'],
            target_state,
            state_data or {}
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        state_logger.error("drive", "Failed to transition state", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requirements")
async def get_state_requirements():
    """Get requirements for the DRIVE state"""
    try:
        requirements = await drive_service.get_state_requirements()
        return {
            "success": True,
            "data": requirements
        }
    except Exception as e:
        state_logger.error("drive", "Failed to get state requirements", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

async def verify_user_auth(request: Request, state_manager: StateManager) -> Dict:
    """Helper function to verify user authentication"""
    token = request.cookies.get('access_token')
    if not token:
        state_logger.error("auth", "No access token cookie found", {
            "cookies": list(request.cookies.keys())
        })
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please sign in."
        )
        
    user_data = await state_manager.verify_session_token(token)
    if not user_data:
        state_logger.error("auth", "Invalid or expired token", None)
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please sign in again."
        )
    
    state_logger.auth_event("user_verified", {
        "user_id": user_data['auth_id'],
        "email": user_data.get('email')
    })
    
    return user_data

@router.get("/oauth/url")
async def get_oauth_url(request: Request):
    """Get Google OAuth URL for drive authorization"""
    try:
        state_logger.drive_event("oauth_url_start", {"status": "generating"})
        
        # Verify user auth using helper
        state_manager = request.app.state.state_manager
        user_data = await verify_user_auth(request, state_manager)

        # Initialize OAuth handler
        oauth_handler = get_oauth_handler(request)
        
        # Get current session token and encode it in state
        session_token = request.cookies.get('access_token')
        state_data = {
            'session_token': session_token,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_data['auth_id']
        }
        encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
        
        # Get auth URL - scopes are managed by the OAuth handler
        auth_url = await oauth_handler.get_auth_url(state=encoded_state)
        
        state_logger.drive_event("oauth_url_generated", {
            "user_id": user_data['auth_id']
        })
        
        return {
            "success": True,
            "url": auth_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        state_logger.error("drive", "Failed to generate OAuth URL", {
            "error": str(e),
            "stack": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback")
async def oauth_callback(request: Request, code: str, state: Optional[str] = None):
    """Handle Google Drive OAuth callback"""
    try:
        state_logger.drive_event("oauth_callback_received", {
            "has_code": bool(code),
            "code_length": len(code) if code else 0,
            "has_state": bool(state)
        })

        # Decode state parameter to get original session token
        session_token = None
        if state:
            try:
                state_json = base64.urlsafe_b64decode(state.encode()).decode()
                state_data = json.loads(state_json)
                session_token = state_data.get('session_token')
                state_logger.drive_event("state_decoded", {"success": True})
            except Exception as e:
                state_logger.error("drive", "Failed to decode state", {"error": str(e)})

        if not session_token:
            state_logger.error("drive", "No session token in state", None)
            return RedirectResponse(url="/?drive_auth=error&reason=no_session")

        # Verify user auth using the decoded session token
        state_manager = request.app.state.state_manager
        user_data = await state_manager.verify_session_token(session_token)
        
        if not user_data:
            state_logger.error("drive", "Invalid session token", None)
            return RedirectResponse(url="/?drive_auth=error&reason=invalid_session")

        # Get OAuth handler and process callback
        oauth_handler = get_oauth_handler(request)
        result = await oauth_handler.process_callback(code)

        # Get current state and ensure we maintain the access token
        current_state = await state_manager.get_current_state(user_data['auth_id'])
        
        # Merge state data while preserving existing auth data
        credentials = result['credentials']
        state_data = {
            'drive_access_token': credentials.get('token'),
            'drive_refresh_token': credentials.get('refresh_token'),
            'drive_auth_status': 'completed',
            'state_metadata': {
                'drive': {
                    'tokens': {
                        'token_uri': credentials.get('token_uri'),
                        'client_id': credentials.get('client_id'),
                        'client_secret': credentials.get('client_secret'),
                        'scopes': credentials.get('scopes', []),
                        'expiry': credentials.get('expiry')
                    },
                    'permissions': result['state_metadata']['drive']['permissions'],
                    'status': 'completed'
                },
                'user': current_state.get('state_metadata', {}).get('user', {}),
                'allowed_transitions': ['ACTIVE']
            }
        }

        # Transition state through state manager
        success, transition_result = await state_manager.transition_user_state(
            user_id=user_data['auth_id'],
            target_state='DRIVE',
            state_data=state_data,
            reason='Drive authorization completed'
        )

        if not success:
            state_logger.error("drive", "State transition failed", {
                "user_id": user_data['auth_id'],
                "error": transition_result.get('error')
            })
            return RedirectResponse(url="/?drive_auth=error&reason=transition_failed")
        
        # Create response with success redirect
        response = RedirectResponse(url="/?drive_auth=success")
        
        # Set the session token cookie
        if session_token:
            response.set_cookie(
                key='access_token',
                value=session_token,
                httponly=True,
                secure=True,
                samesite='lax',
                max_age=7 * 24 * 60 * 60  # 7 days
            )
            
        state_logger.drive_event("oauth_success", {
            "user_id": user_data['auth_id'],
            "status": "completed"
        })
        
        return response
        
    except Exception as e:
        state_logger.error("drive", "Callback failed", {
            "error": str(e),
            "stack": traceback.format_exc()
        })
        return RedirectResponse(url="/?drive_auth=error&reason=callback_failed")

@router.get("/events")
async def drive_events(request: Request):
    """Stream drive state events"""
    try:
        token = request.cookies.get('access_token')
        user_data = await state_manager.verify_session_token(token)
        
        async def event_generator():
            async for event in state_manager.subscribe_to_events(
                user_id=user_data['auth_id'],
                event_types=['drive_auth_status']
            ):
                yield f"data: {json.dumps(event)}\n\n"
                
        return EventSourceResponse(event_generator())
        
    except Exception as e:
        state_logger.error("drive", "Drive events stream failed", {
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-redirect")
async def test_redirect_uri():
    """Test endpoint to verify redirect URI configuration"""
    oauth_handler = GoogleOAuthHandler()
    return {
        "configured_uri": oauth_handler.redirect_uri,
        "router_prefix": router.prefix,
        "full_expected_path": f"http://localhost:8000{router.prefix}/callback"
    }

@router.get("/oauth/config")
async def get_oauth_config():
    """Get OAuth configuration for debugging"""
    oauth_handler = GoogleOAuthHandler()
    return {
        "redirect_uri": oauth_handler.redirect_uri,
        "router_prefix": router.prefix,
        "expected_callback_path": f"{router.prefix}/callback",
        "full_expected_uri": f"http://localhost:8000{router.prefix}/callback",
        "env_redirect_uri": os.getenv('GOOGLE_DRIVE_REDIRECT_URI')
    }

@router.post("/transition/active")
async def transition_to_active(request: Request):
    """Transition from DRIVE to ACTIVE state"""
    try:
        # Verify user is authenticated
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Verify drive is connected
        drive_service = get_drive_service(request)
        drive_info = await drive_service.get_drive_info(user_data['auth_id'])
        
        if drive_info.get('drive_auth_status') != 'connected':
            raise HTTPException(status_code=400, detail="Drive not connected")
            
        # Initialize workspace
        state_manager = get_state_manager(request)
        await state_manager.transition_state(
            user_data['auth_id'],
            'ACTIVE',
            {
                'workspace_initialized': True,
                'storage_quota': drive_info.get('storage_quota', {}),
                'last_transition': {
                    'from': 'DRIVE',
                    'to': 'ACTIVE',
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        
        return {
            "success": True,
            "redirect": "/workspace/dashboard"
        }
        
    except Exception as e:
        state_logger.error("drive", "Failed to transition to ACTIVE", {
            "error": str(e),
            "error_type": type(e).__name__,
            "stack": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/folders")
async def get_folders(request: Request):
    """Get user's folders"""
    try:
        # Get state manager and verify user
        state_manager = request.app.state.state_manager
        user_data = await verify_user_auth(request, state_manager)
        
        # Get current state
        current_state = await state_manager.get_current_state(user_data['auth_id'])
        
        # Extract folder data from state metadata
        state_metadata = current_state.get('state_metadata', {})
        drive_metadata = state_metadata.get('drive', {})
        
        # Format folder data
        folders = []
        if drive_metadata:
            folder_data = {
                'id': drive_metadata.get('folder_id'),
                'name': drive_metadata.get('folder_name', 'My TenFold Folder'),
                'drive_url': drive_metadata.get('folder_url', '#'),
                'created_at': current_state.get('created_at', datetime.now().isoformat()),
                'status': drive_metadata.get('status', 'active')
            }
            folders.append(folder_data)
        
        state_logger.drive_event("folders_returned", {
            "user_id": user_data['auth_id'],
            "folder_count": len(folders)
        })
        
        return JSONResponse({
            "success": True,
            "folders": folders
        })
        
    except Exception as e:
        state_logger.error("drive", "Failed to get folders", {
            "error": str(e),
            "stack": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail="Failed to fetch folders")
