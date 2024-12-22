from fastapi import APIRouter, Request, Response, HTTPException
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, Dict, Optional, Any
from pydantic import BaseModel
import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

class StateUpdate(BaseModel):
    current_state: str
    state_metadata: Dict = {}

router = APIRouter()

@router.get("/api/state")
async def get_state(request: Request):
    """Get current state"""
    try:
        # Get token from cookies
        token = request.cookies.get('access_token')
        if not token:
            return {"success": False, "error": "No token found"}

        # Verify token and get user data
        state_manager = request.app.state.state_manager
        user_data = await state_manager.verify_session_token(token)
        
        if not user_data:
            return {"success": False, "error": "Invalid token"}

        # Get current state for user
        current_state = await state_manager.get_current_state(user_data['auth_id'])
        
        if current_state:
            return {"success": True, "data": current_state}
        return {"success": False, "error": "No state found"}
    except Exception as e:
        logger.error(f"State fetch failed: {str(e)}")
        return {"success": False, "error": str(e)}

async def state_event_generator(request: Request) -> AsyncGenerator[str, None]:
    """Generate state events for SSE"""
    while True:
        # Check if client closed connection
        if await request.is_disconnected():
            break

        # Get current state from database
        state_manager = request.app.state.state_manager
        current_state = await state_manager.get_current_state()

        # Send state update
        if current_state:
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "state_update",
                    "state": current_state
                })
            }

        # Wait before next update (5 seconds)
        await asyncio.sleep(5)

@router.get("/api/state/events")
async def state_events(request: Request):
    """SSE endpoint for state updates"""
    return EventSourceResponse(state_event_generator(request))

@router.post("/update")
async def update_state(request: Request, state_update: StateUpdate):
    try:
        # Update state in database
        response = supabase.table('users').update({
            'current_state': state_update.current_state,
            'state_metadata': state_update.state_metadata
        }).eq('auth_id', request.state.user.auth_id).execute()
        
        if response.data:
            return {"success": True, "data": response.data[0]}
        return {"success": False, "error": "Failed to update state"}
    except Exception as e:
        logger.error(f"State update failed: {str(e)}")
        return {"success": False, "error": str(e)}

@router.post("/api/state/debug/simulate")
async def simulate_state(request: Request, data: Dict[str, Any]):
    """Debug endpoint for simulating state changes"""
    # Only allow in development
    if os.getenv('ENV') != 'development':
        raise HTTPException(status_code=403, detail="Debug endpoints only available in development")
        
    try:
        state_manager = request.app.state.state_manager
        token = request.cookies.get('access_token')
        
        if not token:
            raise HTTPException(status_code=401, detail="No session token")
            
        # Verify user
        user_data = await state_manager.verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid session")
            
        # Simulate state change
        success, result = await state_manager.transition_user_state(
            user_id=user_data['auth_id'],
            target_state=data['state'],
            state_data={'state_metadata': data.get('metadata', {})},
            reason='Debug: Manual state simulation'
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=result.get('error', 'State transition failed'))
            
        return {
            "success": True,
            "state": data['state'],
            "metadata": data.get('metadata', {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Additional routes can be added below