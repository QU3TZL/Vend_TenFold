from fastapi import APIRouter, HTTPException, Request, Response, Depends
from typing import Dict, Optional
import logging
from .auth_service import AuthService
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import traceback

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Set up templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "shared" / "templates"))

def get_state_manager(request: Request) -> StateManager:
    return request.app.state.state_manager

def get_auth_service() -> AuthService:
    return AuthService()

class GoogleSignInRequest(BaseModel):
    token: str

@router.post("/google/signin")
async def google_signin(request: Request, signin_data: GoogleSignInRequest):
    """Handle Google Sign-In token verification"""
    try:
        logger.info("[GoogleSignIn] Starting sign-in process with token length: %d", len(signin_data.token))
        
        if not signin_data.token:
            logger.error("[GoogleSignIn] No token provided in request")
            raise HTTPException(status_code=400, detail="No token provided")

        # Get services
        auth_service = get_auth_service()
        state_manager = get_state_manager(request)
        
        logger.info("[GoogleSignIn] Services initialized", extra={
            "has_auth_service": bool(auth_service),
            "has_state_manager": bool(state_manager),
            "jwt_secret_length": len(auth_service.jwt_secret) if auth_service.jwt_secret else 0,
            "client_id": auth_service.client_id[:10] + "..." if auth_service.client_id else None
        })
        
        # Verify token and get user info
        auth_result = await auth_service.verify_google_token(signin_data.token)
        
        logger.info("[GoogleSignIn] Token verification result", extra={
            "success": auth_result.success,
            "has_user_info": bool(auth_result.user_info),
            "has_session_token": bool(auth_result.session_token),
            "error_message": auth_result.error_message,
            "user_email": auth_result.user_info.get('email') if auth_result.user_info else None,
            "auth_id": auth_result.user_info.get('auth_id') if auth_result.user_info else None
        })
        
        if not auth_result.success:
            logger.error(f"[GoogleSignIn] Token verification failed: {auth_result.error_message}")
            raise HTTPException(status_code=400, detail=auth_result.error_message)
            
        # Create response with session token
        response = JSONResponse({
            "success": True,
            "message": "Successfully authenticated",
            "user": auth_result.user_info
        })
        
        # Set session cookie with strict security settings
        logger.info(f"[GoogleSignIn] Setting session cookie", extra={
            "token_length": len(auth_result.session_token) if auth_result.session_token else 0,
            "user_email": auth_result.user_info.get('email'),
            "auth_id": auth_result.user_info.get('auth_id'),
            "cookie_settings": {
                "httponly": True,
                "secure": False,  # Set to True in production
                "samesite": "lax",
                "max_age": 7 * 24 * 60 * 60
            }
        })
        
        response.set_cookie(
            key="access_token",
            value=auth_result.session_token,
            httponly=True,
            secure=False,  # Set to True in production
            samesite="lax",
            max_age=7 * 24 * 60 * 60  # 7 days
        )

        logger.info(f"[GoogleSignIn] Authentication successful", extra={
            "user_email": auth_result.user_info.get('email'),
            "auth_id": auth_result.user_info.get('auth_id'),
            "response_headers": dict(response.headers),
            "cookie_set": "access_token" in response.headers.get("set-cookie", "")
        })
        
        return response
        
    except Exception as e:
        logger.error(f"[GoogleSignIn] Error in google_signin: {str(e)}", extra={
            "error_type": type(e).__name__,
            "stack": traceback.format_exc()
        })
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/login")
async def login_page(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    """Show login page with Google Sign-In button"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "google_client_id": auth_service.client_id
    })

@router.get("/verify")
async def verify_session(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    """Verify current session"""
    try:
        token = request.cookies.get('access_token')
        logger.info("[SessionVerify] Checking session", extra={
            "has_token": bool(token),
            "cookie_names": list(request.cookies.keys())
        })
        
        if not token:
            logger.info("[SessionVerify] No session token found")
            return {"authenticated": False}
            
        user_data = await auth_service.verify_session_token(token)
        logger.info("[SessionVerify] Verification result", extra={
            "success": bool(user_data),
            "user_email": user_data.get('email') if user_data else None,
            "auth_id": user_data.get('auth_id') if user_data else None
        })
        
        return {
            "authenticated": bool(user_data),
            "user": user_data
        }
    except Exception as e:
        logger.error("[SessionVerify] Verification failed", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "stack": traceback.format_exc()
        })
        return {"authenticated": False}

@router.get("/requirements")
async def get_state_requirements(auth_service: AuthService = Depends(get_auth_service)):
    """Get requirements for the AUTH state"""
    try:
        requirements = await auth_service.get_state_requirements()
        return {
            "success": True,
            "data": requirements
        }
    except Exception as e:
        logger.error(f"Failed to get state requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_auth_status(request: Request):
    """Get auth status component"""
    return templates.TemplateResponse("auth_status.html", {"request": request})

