from fastapi import APIRouter, HTTPException, Response, Request, Depends
from typing import Dict, Optional
import logging
from .active_service import ActiveService
from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["active"])

def get_state_manager(request: Request) -> StateManager:
    return request.app.state.state_manager

def get_active_service(request: Request) -> ActiveService:
    state_manager = get_state_manager(request)
    return ActiveService(state_manager=state_manager, supabase_client=get_supabase_client())

@router.get("")
async def get_active_info(request: Request, active_service: ActiveService = Depends(get_active_service)):
    """Get information for the active state"""
    try:
        # Get user ID from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        active_info = await active_service.get_active_info(user_data['auth_id'])
        return {
            "success": True,
            "data": active_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_folder_stats(request: Request):
    """Get statistics for user's active folders"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Get folder stats
        stats = await get_active_service(request).get_folder_stats(user_data['auth_id'])
        
        if not stats:
            return {
                "success": True,
                "data": {
                    "folder_count": 0,
                    "total_size_bytes": 0,
                    "total_files": 0,
                    "folders": []
                }
            }
            
        return {
            "success": True,
            "data": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get folder stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folder/{folder_id}/stats")
async def update_folder_stats(
    request: Request,
    folder_id: str,
    size_bytes: int,
    file_count: int
):
    """Update statistics for a specific folder"""
    try:
        # Verify user is authenticated
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Update folder stats
        success = await get_active_service(request).update_folder_stats(
            folder_id,
            size_bytes,
            file_count
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update folder stats")
            
        return {
            "success": True,
            "data": {
                "folder_id": folder_id,
                "size_bytes": size_bytes,
                "file_count": file_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update folder stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requirements")
async def get_state_requirements(active_service: ActiveService = Depends(get_active_service)):
    """Get requirements for the ACTIVE state"""
    try:
        requirements = await active_service.get_state_requirements()
        return {
            "success": True,
            "data": requirements
        }
    except Exception as e:
        logger.error(f"Failed to get state requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initialize")
async def initialize_active_state(
    request: Request,
    active_service: ActiveService = Depends(get_active_service)
):
    """Initialize ACTIVE state after drive authorization"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Initialize active state
        success, result = await active_service.initialize_active_state(
            user_data['auth_id'],
            user_data
        )

        if not success:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to initialize ACTIVE state"))

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize active state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
