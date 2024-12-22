from fastapi import APIRouter, HTTPException, Response, Request, Depends
from typing import Dict, Optional
import logging
from .visitor_service import VisitorService
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from src.api.state.auth.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["visitor"])
visitor_service = VisitorService()

# Set up templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

def get_auth_service() -> AuthService:
    return AuthService()

@router.get("")
async def get_visitor_info():
    """Get information for the visitor state"""
    try:
        visitor_info = await visitor_service.get_visitor_info()
        return {
            "success": True,
            "data": visitor_info
        }
    except Exception as e:
        logger.error(f"Failed to get visitor info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transition")
async def transition_visitor_state(target_state: str, state_data: Optional[Dict] = None):
    """Transition from VISITOR to another state"""
    try:
        success, result = await visitor_service.transition_state(
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
        logger.error(f"Failed to transition state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requirements")
async def get_state_requirements():
    """Get requirements for the VISITOR state"""
    try:
        requirements = await visitor_service.get_state_requirements()
        return {
            "success": True,
            "data": requirements
        }
    except Exception as e:
        logger.error(f"Failed to get state requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_visitor_status(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    """Get visitor status component"""
    google_client_id = auth_service.client_id
    if not google_client_id:
        logger.warning("GOOGLE_CLIENT_ID environment variable is not set")
        
    # Get environment variables for debugging
    debug_env = {k: v for k, v in os.environ.items() if 'google' in k.lower()}
    
    return templates.TemplateResponse("visitor_status.html", {
        "request": request,
        "google_client_id": google_client_id,
        "debug_env": debug_env
    })
