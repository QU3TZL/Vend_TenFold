import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from supabase import Client
from .stripe_service import StripeService
import os
from src.api.state.drive.drive_service import DriveService

logger = logging.getLogger(__name__)

class PaymentService:
    """Service to handle payment state logic"""
    
    def __init__(self, state_manager, supabase_client: Client):
        self.state_manager = state_manager
        self.supabase = supabase_client
        self.allowed_transitions = ["DRIVE"]
        self.required_fields = ["plan_id", "session_id", "status"]
        self.stripe_service = StripeService(state_manager)
        
    async def get_payment_info(self, user_id: str) -> Dict:
        """Get current payment state information"""
        try:
            # Get user state from state manager
            state = await self.state_manager.get_current_state(user_id)
            
            if not state:
                return {
                    "current_state": "PAYMENT",
                    "state_metadata": {
                        "error": "User not found",
                        "last_updated": datetime.utcnow().isoformat()
                    }
                }
                
            return {
                "current_state": "PAYMENT",
                "state_metadata": {
                    **state.get('state_metadata', {}),
                    "last_updated": datetime.utcnow().isoformat(),
                    "allowed_transitions": self.allowed_transitions
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get payment info: {str(e)}")
            raise

    async def create_checkout_session(
        self,
        user_id: str,
        plan_name: str,
        price_id: str,
        mode: str = "subscription"
    ) -> Optional[Dict]:
        """Create Stripe checkout session"""
        return await self.stripe_service.create_checkout_session(
            user_id=user_id,
            plan_name=plan_name,
            price_id=price_id,
            mode=mode
        )

    async def validate_transition(self, target_state: str, state_data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate state transition from PAYMENT"""
        try:
            # Check if transition is allowed
            if target_state not in self.allowed_transitions:
                return False, f"Invalid transition from PAYMENT to {target_state}"
                
            # Validate required fields
            missing_fields = [field for field in self.required_fields if field not in state_data]
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"
                
            # Validate payment status
            if state_data.get('status') != 'completed':
                return False, "Payment must be completed before transitioning"
                
            return True, None
            
        except Exception as e:
            logger.error(f"Transition validation failed: {str(e)}")
            return False, str(e)

    async def transition_state(self, user_id: str, target_state: str, state_data: Dict) -> Tuple[bool, Dict]:
        """Handle the transition from PAYMENT to another state"""
        try:
            # Validate the transition
            valid, error = await self.validate_transition(target_state, state_data)
            if not valid:
                return False, {"error": error}
            
            # Use central StateManager for the actual transition
            success, result = await self.state_manager.transition_user_state(
                user_id,
                target_state,
                state_data,
                f"Transition from PAYMENT to {target_state}"
            )
            
            if not success:
                return False, {"error": result}
                
            return True, result
            
        except Exception as e:
            logger.error(f"State transition failed: {str(e)}")
            return False, {"error": str(e)}

    async def get_state_requirements(self) -> Dict:
        """Get requirements for the PAYMENT state"""
        return {
            "required_fields": self.required_fields,
            "allowed_transitions": self.allowed_transitions,
            "description": "Payment or trial activation required"
        }

    async def update_payment_session_status(
        self,
        session_id: str,
        status: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Update payment session status through Stripe service"""
        return await self.stripe_service.update_payment_session_status(
            session_id=session_id,
            status=status,
            metadata=metadata
        )

    async def create_folder_checkout_session(self, user_id: str) -> Optional[Dict]:
        """Create checkout session for additional folder"""
        try:
            # Get user details
            user_response = self.supabase.table('users').select('*').eq('auth_id', user_id).single().execute()
            if not user_response.data:
                logger.error(f"User not found: {user_id}")
                return None
                
            user = user_response.data
            
            # Create payment session record
            session_data = {
                'user_id': user['id'],
                'type': 'additional_folder',
                'status': 'pending',
                'metadata': {
                    'user_email': user['email'],
                    'payment_type': 'additional_folder'
                }
            }
            
            session_response = self.supabase.table('payment_sessions').insert(session_data).execute()
            if not session_response.data:
                logger.error("Failed to create payment session record")
                return None
                
            session_record = session_response.data[0]
            
            # Create Stripe checkout session
            return await self.stripe_service.create_checkout_session(
                user_id=user_id,
                plan_name='additional_folder',
                price_id=os.getenv('STRIPE_ADDITIONAL_FOLDER_PRICE_ID'),
                mode='payment',
                metadata={
                    'payment_session_id': session_record['id'],
                    'payment_type': 'additional_folder'
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create folder checkout session: {str(e)}")
            return None

    async def verify_folder_payment_session(self, session_id: str) -> Optional[Dict]:
        """Verify folder payment session"""
        try:
            # Get session from Stripe
            session = await self.stripe_service.retrieve_session(session_id)
            if not session:
                return None
                
            # Verify payment status
            if session['payment_status'] != 'paid':
                logger.error(f"Payment not completed for session {session_id}")
                return None
                
            # Get payment session record
            session_response = self.supabase.table('payment_sessions').select('*').eq('id', session['metadata']['payment_session_id']).single().execute()
            if not session_response.data:
                logger.error(f"Payment session record not found: {session['metadata']['payment_session_id']}")
                return None
                
            return session_response.data
            
        except Exception as e:
            logger.error(f"Failed to verify folder payment session: {str(e)}")
            return None

    async def create_folder_after_payment(self, user_id: str, session_id: str) -> Optional[Dict]:
        """Create new folder after successful payment"""
        try:
            # Get user details
            user_response = self.supabase.table('users').select('*').eq('auth_id', user_id).single().execute()
            if not user_response.data:
                logger.error(f"User not found: {user_id}")
                return None
                
            user = user_response.data
            
            # Get folder name from drive service
            drive_service = DriveService(self.state_manager, self.supabase)
            folder_name = await drive_service.get_next_folder_name()
            
            # Create folder record
            folder_data = {
                'user_id': user['id'],
                'name': folder_name,
                'current_state': 'PENDING',
                'payment_id': session_id,
                'state_metadata': {
                    'workspace_status': {
                        'owner': user['email'],
                        'status': 'pending',
                        'created_at': datetime.utcnow().isoformat(),
                        'storage_metrics': {
                            'storage_used': 0,
                            'storage_limit': 10 * 1024 * 1024 * 1024,  # 10GB in bytes
                            'folder_count': 1
                        },
                        'recent_activity': [{
                            'action': 'workspace_created',
                            'timestamp': datetime.utcnow().isoformat(),
                            'details': 'Initial workspace creation'
                        }]
                    }
                },
                'storage_limit_gb': 10,
                'current_size_bytes': 0,
                'file_count': 0
            }
            
            folder_response = self.supabase.table('folders').insert(folder_data).execute()
            if not folder_response.data:
                logger.error("Failed to create folder record")
                return None
                
            return folder_response.data[0]
            
        except Exception as e:
            logger.error(f"Failed to create folder after payment: {str(e)}")
            return None
