from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
import logging
import jwt
import os
from src.database.supabase import get_supabase_client
import traceback
import json

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self):
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', 'dev_secret_key')
        self.supabase = get_supabase_client()
        
        # Define the linear state progression
        self.STATE_FLOW = {
            'VISITOR': {
                'next': 'AUTH',
                'required': [],
                'description': 'Unknown user'
            },
            'AUTH': {
                'next': 'PAYMENT',
                'required': ['email', 'auth_id'],
                'description': 'Google sign-in successful'
            },
            'PAYMENT': {
                'next': 'DRIVE',
                'required': ['plan_id', 'session_id', 'status'],
                'description': 'Payment or trial activated'
            },
            'DRIVE': {
                'next': 'ACTIVE',
                'required': ['drive_access_token', 'drive_refresh_token', 'drive_auth_status'],
                'description': 'Drive connected'
            },
            'ACTIVE': {
                'next': None,
                'required': ['folder_id'],
                'description': 'Folders deployed and shared'
            }
        }

    async def verify_session_token(self, token: str) -> Optional[Dict]:
        """Verify session token"""
        try:
            if not token:
                return None
                
            # Decode the JWT token
            decoded = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=['HS256'],
                leeway=60
            )
            
            # Verify user exists in Supabase
            response = self.supabase.table('users').select('*').eq('auth_id', decoded['auth_id']).single().execute()
            if not response.data:
                return None
                
            return decoded
            
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    async def get_current_state(self, user_id: str = None) -> Dict[str, Any]:
        """Get current state from database"""
        try:
            # Return VISITOR state if no user_id provided
            if not user_id:
                return {
                    "current_state": "VISITOR",
                    "state_metadata": {
                        "allowed_transitions": ["AUTH"]
                    }
                }
                
            try:
                # First check users table for current state
                user_response = self.supabase.table('users').select('*').eq('auth_id', user_id).single().execute()
                
                if user_response.data:
                    return {
                        "current_state": user_response.data['current_state'],
                        "state_metadata": user_response.data['state_metadata']
                    }
                    
                # Fallback to state history if user not found
                history_response = self.supabase.table('user_state_history') \
                    .select('*') \
                    .eq('auth_id', user_id) \
                    .order('created_at', desc=True) \
                    .limit(1) \
                    .execute()
                
                if history_response.data and len(history_response.data) > 0:
                    state_data = history_response.data[0]
                    return {
                        "current_state": state_data['to_state'],
                        "state_metadata": state_data['metadata']
                    }
                    
            except Exception as db_error:
                logger.warning(f"Database query failed or user not found: {db_error}")
                
            # Return VISITOR state if user not found or query fails
            return {
                "current_state": "VISITOR",
                "state_metadata": {
                    "allowed_transitions": ["AUTH"]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get user state: {e}")
            return {
                "current_state": "VISITOR",
                "state_metadata": {
                    "error": str(e),
                    "allowed_transitions": ["AUTH"]
                }
            }

    async def validate_state_transition(self, current_state: str, target_state: str) -> Tuple[bool, str]:
        """Validate if transition follows linear progression"""
        try:
            if current_state not in self.STATE_FLOW:
                return False, f"Invalid current state: {current_state}"
                
            # Allow transition to next state or fallback to previous states
            valid_transitions = []
            temp_state = current_state
            
            # Build list of valid previous states
            while temp_state != 'VISITOR':
                for state, config in self.STATE_FLOW.items():
                    if config['next'] == temp_state:
                        temp_state = state
                        valid_transitions.append(state)
                        break
            
            # Add next state if exists
            if self.STATE_FLOW[current_state]['next']:
                valid_transitions.append(self.STATE_FLOW[current_state]['next'])
                
            if target_state not in valid_transitions:
                return False, f"Invalid transition from {current_state} to {target_state}"
                
            return True, ""
            
        except Exception as e:
            logger.error(f"State validation error: {e}")
            return False, str(e)

    async def transition_user_state(
        self,
        user_id: str,
        target_state: str,
        state_data: Dict,
        reason: str
    ) -> Tuple[bool, Dict]:
        """Transition user state and sync with database"""
        try:
            # Get current state
            current = await self.get_current_state(user_id)
            current_state = current.get('current_state', 'VISITOR')
            
            logger.info("[StateManager] Current state before transition", extra={
                "user_id": user_id,
                "current_state": current_state,
                "target_state": target_state
            })
            
            # Validate transition
            valid, error = await self.validate_state_transition(current_state, target_state)
            if not valid:
                logger.error("[StateManager] Invalid state transition", extra={
                    "user_id": user_id,
                    "from_state": current_state,
                    "to_state": target_state,
                    "error": error
                })
                return False, {"error": error}
            
            # Validate required fields
            required_fields = self.STATE_FLOW[target_state]['required']
            missing = []
            for field in required_fields:
                if '.' in field:
                    # Handle nested fields in state_metadata
                    parts = field.split('.')
                    value = state_data.get('state_metadata', {})
                    for part in parts:
                        if not isinstance(value, dict) or part not in value:
                            missing.append(field)
                            break
                        value = value[part]
                else:
                    # Check both state_metadata and top-level fields
                    if field not in state_data.get('state_metadata', {}) and field not in state_data:
                        missing.append(field)
            
            if missing:
                logger.error("[StateManager] Missing required fields", extra={
                    "user_id": user_id,
                    "missing_fields": missing,
                    "provided_data": state_data
                })
                return False, {"error": f"Missing required fields: {missing}"}
            
            # First get the internal user ID
            user_response = self.supabase.table('users').select('id').eq('auth_id', user_id).single().execute()
            if not user_response.data:
                logger.error("[StateManager] Failed to get internal user ID", extra={
                    "auth_id": user_id
                })
                return False, {"error": "User not found"}
                
            internal_user_id = user_response.data['id']
            
            try:
                # Record state transition in history
                history_data = {
                    'auth_id': user_id,
                    'internal_user_id': internal_user_id,
                    'to_state': target_state,
                    'metadata': state_data.get('state_metadata', {}),
                    'from_state': current_state,
                    'transition_reason': reason,
                    'drive_auth_status': state_data.get('drive_auth_status'),
                    'drive_access_token': state_data.get('drive_access_token'),
                    'drive_refresh_token': state_data.get('drive_refresh_token')
                }
                
                # Insert new state record
                response = self.supabase.table('user_state_history').insert(history_data).execute()

                if not response.data:
                    logger.error("[StateManager] Failed to record state history", extra={
                        "auth_id": user_id,
                        "target_state": target_state
                    })
                    return False, {"error": "Failed to record state history"}

                # Update user's current state
                user_update = {
                    'current_state': target_state,
                    'state_metadata': state_data.get('state_metadata', {})
                }
                user_response = self.supabase.table('users').update(user_update).eq('auth_id', user_id).execute()

                if not user_response.data:
                    logger.error("[StateManager] Failed to update user state", extra={
                        "auth_id": user_id,
                        "target_state": target_state
                    })
                    return False, {"error": "Failed to update user state"}
                    
                return True, {"message": "State updated successfully"}
                
            except Exception as e:
                logger.error(f"[StateManager] State transition failed: {str(e)}\n{traceback.format_exc()}")
                return False, {"error": str(e)}
            
        except Exception as e:
            logger.error(f"[StateManager] State transition failed: {str(e)}\n{traceback.format_exc()}")
            return False, {"error": str(e)}

    async def notify_state_change(self, user_id: str, state_update: Dict) -> bool:
        """Notify state changes and sync with database"""
        try:
            logger.info("[StateManager] Processing state change notification", extra={
                "user_id": user_id,
                "update": state_update
            })
            
            # Try auth_id first, then internal_id
            user_response = self.supabase.table('users').select('id').eq('auth_id', user_id).single().execute()
            if not user_response.data:
                # Try internal_id
                user_response = self.supabase.table('users').select('id').eq('id', user_id).single().execute()
                if not user_response.data:
                    logger.error("[StateManager] User not found for notification", extra={
                        "user_id": user_id
                    })
                    return False
                
            internal_user_id = user_response.data['id']
            
            # Get auth_id for history
            auth_response = self.supabase.table('users').select('auth_id').eq('id', internal_user_id).single().execute()
            auth_id = auth_response.data['auth_id'] if auth_response.data else user_id
            
            # Record state change in history if state is changing
            current = await self.get_current_state(auth_id)
            current_state = current.get('current_state')
            new_state = state_update.get('current_state')
            
            if new_state and new_state != current_state:
                history_data = {
                    'auth_id': auth_id,
                    'internal_user_id': internal_user_id,
                    'from_state': current_state,
                    'to_state': new_state,
                    'metadata': state_update.get('state_metadata', {}),
                    'transition_reason': 'State change notification',
                    'created_at': datetime.utcnow().isoformat()
                }
                
                history_response = self.supabase.table('user_state_history').insert(history_data).execute()
                if not history_response.data:
                    logger.error("[StateManager] Failed to record state history for notification", extra={
                        "auth_id": auth_id,
                        "new_state": new_state
                    })
                    return False
            
            # Update user's current state and metadata
            update_data = {}
            if new_state:
                update_data['current_state'] = new_state
            if 'state_metadata' in state_update:
                update_data['state_metadata'] = state_update['state_metadata']
                
            if update_data:
                user_update = self.supabase.table('users').update(update_data).eq('id', internal_user_id).execute()
                if not user_update.data:
                    logger.error("[StateManager] Failed to update user state", extra={
                        "auth_id": auth_id,
                        "update": update_data
                    })
                    return False
                    
            logger.info("[StateManager] State change notification processed", extra={
                "user_id": user_id,
                "success": True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"[StateManager] Failed to process state change notification: {str(e)}", extra={
                "user_id": user_id,
                "error": str(e),
                "stack": traceback.format_exc()
            })
            return False