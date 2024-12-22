import stripe
from typing import Optional, Dict
import os
from uuid import UUID
import logging
from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager

logger = logging.getLogger(__name__)

# Initialize Stripe with secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "mock_key_for_development")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "mock_key_for_development")

class StripeService:
    def __init__(self, state_manager: StateManager):
        self.is_mock = "mock" in stripe.api_key
        self.state_manager = state_manager
        self.supabase = get_supabase_client()
        
    async def create_checkout_session(
        self,
        user_id: str,  # Can be UUID or auth_id
        plan_name: str,
        price_id: str,
        mode: str = "subscription"
    ) -> Optional[Dict]:
        """Create Stripe checkout session for subscription"""
        try:
            logger.info(f"Creating checkout session - user_id: {user_id}, plan: {plan_name}, mode: {mode}")
            
            # Get user state
            state = await self.state_manager.get_current_state(user_id)
            logger.info(f"Current state: {state}")
            
            if not state:
                logger.error(f"User state not found: {user_id}")
                return None
                
            # Get user email from state metadata or user data
            user_email = state.get('state_metadata', {}).get('email') or state.get('state_metadata', {}).get('user', {}).get('email')
            logger.info(f"Found user email: {user_email}")
            
            if not user_email:
                logger.error(f"User email not found in state: {user_id}")
                return None
            
            # For trial or mock mode, create a mock session
            if mode == "trial" or self.is_mock:
                logger.debug(f"Starting mock/trial session creation - mode: {mode}, is_mock: {self.is_mock}")
                session_id = f"mock_session_{user_id}" if self.is_mock else f"trial_session_{user_id}"
                mock_session = {
                    "id": session_id,
                    "url": "/api/state/payment/success"  # Return success URL for mock sessions
                }
                logger.debug(f"Created mock session: {mock_session}")
                
                # Update state with payment session - include required fields
                state_data = {
                    'state_metadata': {
                        'plan_id': 'trial',
                        'session_id': session_id,
                        'status': 'completed',
                        'payment_complete': True,
                        'user': {
                            'email': user_email
                        },
                        'allowed_transitions': ['DRIVE']
                    }
                }
                logger.debug(f"Preparing state data for mock session: {state_data}")
                
                success, result = await self.state_manager.transition_user_state(
                    user_id,
                    'PAYMENT',
                    state_data,
                    f"Started {mode} payment session"
                )
                logger.debug(f"State transition completed - success: {success}, result: {result}")
                
                if not success:
                    logger.error(f"Failed to update state with payment session: {result}")
                    return None
                    
                logger.info(f"Successfully created mock session: {session_id}")
                return mock_session
            
            # Create real Stripe checkout session
            session = stripe.checkout.Session.create(
                customer_email=user_email,
                success_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/state/payment/success?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name.lower().replace(' ', '_')}",
                cancel_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/",
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                metadata={
                    "user_id": str(user_id),
                    "plan_name": plan_name,
                    "user_email": user_email
                }
            )
            
            # Update state with payment session
            success, _ = await self.state_manager.transition_user_state(
                user_id,
                'PAYMENT',
                {
                    'state_metadata': {
                        'session_id': session["id"],
                        'plan_name': plan_name,
                        'mode': 'subscription',
                        'status': 'pending',
                        'stripe_session': {
                            'id': session["id"],
                            'url': session["url"]
                        }
                    }
                },
                "Started Stripe checkout session"
            )
            
            if not success:
                logger.error("Failed to update state with payment session")
                return None
                
            return session
            
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            return None

    def _create_mock_session(self, user_id: str, user_email: str, plan_name: str) -> Dict:
        """Create mock session for development/trial"""
        session_id = f"trial_session_{user_id}"
        return {
            "id": session_id,
            "url": "/api/state/payment/success",
            "metadata": {
                "user_id": user_id,
                "plan_name": plan_name,
                "user_email": user_email
            }
        }

    async def update_user_subscription(
        self,
        user_id: UUID,
        subscription_id: str,
        subscription_tier: str,
        storage_limit_gb: int
    ) -> bool:
        """Update user's subscription through state transition"""
        try:
            success, _ = await self.state_manager.transition_user_state(
                str(user_id),
                'PAYMENT',
                {
                    'subscription_id': subscription_id,
                    'subscription_tier': subscription_tier,
                    'storage_limit_gb': storage_limit_gb,
                    'status': 'completed',
                    'payment_complete': True
                },
                f"Completed subscription to {subscription_tier} plan"
            )
            
            if not success:
                logger.error(f"Failed to update subscription state: {user_id}")
                return False
                
            logger.info(f"Successfully updated subscription state for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating subscription state: {e}")
            return False

    async def update_payment_session_status(
        self,
        session_id: str,
        status: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Update payment session status through state"""
        try:
            # First get the user_id from current state
            current_states = await self.state_manager.get_states_by_metadata({'session_id': session_id})
            if not current_states:
                logger.error(f"No state found for session: {session_id}")
                return False
                
            user_id = current_states[0].get('user_id')
            if not user_id:
                logger.error(f"No user_id found in state for session: {session_id}")
                return False
                
            # Update the state with new status
            state_metadata = {'status': status}
            if metadata:
                state_metadata.update(metadata)
                
            success, _ = await self.state_manager.transition_user_state(
                user_id,
                'PAYMENT',
                state_metadata,
                f"Updated payment session status to {status}"
            )
            
            if not success:
                logger.error(f"Failed to update payment session state: {session_id}")
                return False
                
            logger.info(f"Successfully updated payment session state: {session_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating payment session state: {e}")
            return False 

    async def retrieve_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve Stripe checkout session"""
        try:
            if self.is_mock:
                # Return mock session for development
                return {
                    'id': session_id,
                    'payment_status': 'paid',
                    'metadata': {
                        'payment_session_id': session_id,
                        'payment_type': 'additional_folder'
                    }
                }
            
            # Get real session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            return session
            
        except Exception as e:
            logger.error(f"Failed to retrieve session: {str(e)}")
            return None 