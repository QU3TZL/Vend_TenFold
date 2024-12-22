from fastapi import APIRouter, HTTPException, Response, Request, Depends, Body, Form
from fastapi.templating import Jinja2Templates
from typing import Dict, Optional
import logging
from .payment_service import PaymentService
from src.services.state.state_manager import StateManager
from src.database.supabase import get_supabase_client
from pydantic import BaseModel
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payment"])

# Initialize templates with correct path
templates = Jinja2Templates(directory="src/api/state/payment/templates")

def get_state_manager(request: Request) -> StateManager:
    return request.app.state.state_manager

def get_payment_service(request: Request) -> PaymentService:
    state_manager = get_state_manager(request)
    return PaymentService(state_manager=state_manager, supabase_client=get_supabase_client())

class CheckoutData(BaseModel):
    plan_name: str
    price_id: str
    mode: str = "subscription"

@router.get("")
async def get_payment_info(request: Request, payment_service: PaymentService = Depends(get_payment_service)):
    """Get information for the payment state"""
    try:
        # Get user ID from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        payment_info = await payment_service.get_payment_info(user_data['auth_id'])
        return {
            "success": True,
            "data": payment_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/checkout")
async def create_checkout_session(
    request: Request,
    plan_name: str = Form(...),
    price_id: str = Form(...),
    mode: str = Form(...)
):
    """Create Stripe checkout session"""
    try:
        # Log incoming request data
        logger.info(f"Checkout request received - Form data: plan_name={plan_name}, price_id={price_id}, mode={mode}")
        
        # Get user from token
        token = request.cookies.get('access_token')
        logger.info(f"Token from cookies: {token}")
        
        if not token:
            logger.warning("No access token found in cookies")
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        logger.info(f"User data from token: {user_data}")
        
        if not user_data:
            logger.warning("Invalid token - no user data found")
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Create checkout session
        logger.info(f"Creating checkout session for user {user_data['auth_id']}")
        session = await get_payment_service(request).create_checkout_session(
            user_id=user_data['auth_id'],
            plan_name=plan_name,
            price_id=price_id,
            mode=mode
        )
        
        if not session:
            logger.error("Failed to create checkout session - no session returned")
            raise HTTPException(status_code=500, detail="Failed to create checkout session")
            
        logger.info(f"Checkout session created successfully: {session}")
        
        # Handle trial/mock sessions
        if mode == "trial" or session.get("id", "").startswith("mock_session_"):
            success_url = f"/api/state/payment/success?session_id={session['id']}"
            logger.info(f"Trial/mock session - redirecting to: {success_url}")
            return {
                "success": True,
                "data": {
                    "id": session["id"],
                    "url": success_url
                }
            }
            
        # For real payments, return Stripe session
        return {
            "success": True,
            "data": session
        }
        
    except HTTPException as he:
        logger.error(f"HTTP Exception in checkout: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Failed to create checkout session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transition")
async def transition_payment_state(request: Request, target_state: str, state_data: Optional[Dict] = None, payment_service: PaymentService = Depends(get_payment_service)):
    """Transition from PAYMENT to another state"""
    try:
        # Verify user is authenticated
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Attempt state transition
        success, result = await payment_service.transition_state(
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
        logger.error(f"Failed to transition state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requirements")
async def get_state_requirements(payment_service: PaymentService = Depends(get_payment_service)):
    """Get requirements for the PAYMENT state"""
    try:
        requirements = await payment_service.get_state_requirements()
        return {
            "success": True,
            "data": requirements
        }
    except Exception as e:
        logger.error(f"Failed to get state requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/success")
async def payment_success(request: Request):
    """Handle successful payment and redirect to home"""
    try:
        session_id = request.query_params.get('session_id')
        logger.info(f"Payment success redirect with session: {session_id}")
        
        # Get user from token
        token = request.cookies.get('access_token')
        logger.info(f"Access token from cookies: {token[:10]}..." if token else "No token found")
        
        if not token:
            logger.warning("No access token found in cookies")
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        logger.info(f"User data from token: {user_data}")
        
        # Get current state
        state_manager = get_state_manager(request)
        current_state = await state_manager.get_current_state(user_data['auth_id'])
        logger.info(f"Current state: {current_state}")
        
        # Verify payment status
        if not current_state.get('state_metadata', {}).get('payment_complete'):
            logger.error("Payment not marked as complete in state")
            raise HTTPException(status_code=400, detail="Payment not complete")
        
        # Instead of rendering template, redirect to home with success param
        return RedirectResponse(
            url=f"/?payment_success=true&session_id={session_id}",
            status_code=303  # Use 303 for POST-to-GET redirect
        )
        
    except Exception as e:
        logger.error(f"Payment success redirect failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-folder-session")
async def create_folder_session(request: Request, payment_service: PaymentService = Depends(get_payment_service)):
    """Create a payment session for an additional folder"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Create checkout session for additional folder
        session = await payment_service.create_folder_checkout_session(
            user_id=user_data['auth_id']
        )
        
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create checkout session")
            
        # For trial/mock sessions
        if session.get("id", "").startswith("mock_session_"):
            success_url = f"/api/state/payment/folder-success?session_id={session['id']}"
            return {
                "success": True,
                "data": {
                    "sessionUrl": success_url
                }
            }
            
        # For real payments, return Stripe session URL
        return {
            "success": True,
            "data": {
                "sessionUrl": session.get("url")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create folder payment session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/folder-success")
async def folder_payment_success(
    request: Request,
    session_id: str,
    payment_service: PaymentService = Depends(get_payment_service)
):
    """Handle successful folder payment"""
    try:
        # Get user from token
        token = request.cookies.get('access_token')
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
            
        user_data = await get_state_manager(request).verify_session_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Verify payment session
        session = await payment_service.verify_folder_payment_session(session_id)
        if not session:
            raise HTTPException(status_code=400, detail="Invalid payment session")
            
        # Create new folder directly (user is already onboarded)
        folder = await payment_service.create_folder_after_payment(
            user_id=user_data['auth_id'],
            session_id=session_id
        )
        
        if not folder:
            raise HTTPException(status_code=500, detail="Failed to create folder")
            
        # Redirect back to drive page
        return RedirectResponse(
            url=f"/drive?folder_created=true&folder_id={folder['id']}",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Folder payment success failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
