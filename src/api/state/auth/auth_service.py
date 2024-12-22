import logging
import jwt
import os
from typing import Dict, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from src.database.supabase import get_supabase_client
import time
import traceback

logger = logging.getLogger(__name__)

class AuthResult(BaseModel):
    success: bool
    user_info: Optional[Dict] = None
    session_token: Optional[str] = None
    error_message: Optional[str] = None

class AuthService:
    """Service to handle Google Sign-In authentication"""
    
    def __init__(self):
        """Initialize AuthService"""
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', '')
        self.supabase = get_supabase_client()

    async def verify_google_token(self, token: str) -> AuthResult:
        """Verify Google Sign-In token"""
        try:
            logger.info("[GoogleVerify] Starting token verification", extra={
                "token_length": len(token),
                "has_client_id": bool(self.client_id),
                "has_jwt_secret": bool(self.jwt_secret)
            })
            
            if not self.client_id:
                logger.error("[GoogleVerify] Google Client ID not configured")
                return AuthResult(
                    success=False,
                    error_message="Google authentication not configured"
                )

            # Log verification attempt
            logger.info("[GoogleVerify] Verifying token with Google", extra={
                "client_id": self.client_id[:10] + "...",  # Log partial client ID for security
                "token_length": len(token),
                "has_jwt_secret": bool(self.jwt_secret)
            })

            try:
                # Verify the token with Google
                idinfo = id_token.verify_oauth2_token(
                    token, 
                    requests.Request(), 
                    self.client_id
                )
                
                logger.info("[GoogleVerify] Raw token verification result", extra={
                    "has_sub": bool(idinfo.get('sub')),
                    "has_email": bool(idinfo.get('email')),
                    "has_name": bool(idinfo.get('name')),
                    "has_picture": bool(idinfo.get('picture')),
                    "email": idinfo.get('email'),
                    "sub": idinfo.get('sub')
                })
            except Exception as e:
                logger.error("[GoogleVerify] Token verification failed", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack": traceback.format_exc()
                })
                raise

            # Extract user info from verified token
            user_info = {
                'auth_id': idinfo['sub'],  # Google's unique ID
                'email': idinfo['email'],
                'name': idinfo.get('name'),
                'picture': idinfo.get('picture'),
                'email_verified': idinfo.get('email_verified', False)
            }
            
            logger.info("[GoogleVerify] User info extracted", extra={
                "email": user_info['email'],
                "auth_id": user_info['auth_id'],
                "has_name": bool(user_info['name']),
                "has_picture": bool(user_info['picture'])
            })
            
            # Update or create user in Supabase
            user_data = {
                'auth_id': user_info['auth_id'],
                'email': user_info['email'],
                'name': user_info['name'],
                'current_state': 'AUTH',
                'state_metadata': {
                    'user': {
                        'auth_id': user_info['auth_id'],
                        'email': user_info['email'],
                        'picture': user_info['picture']
                    },
                    'last_login': datetime.utcnow().isoformat(),
                    'allowed_transitions': ['PAYMENT']
                },
                'updated_at': datetime.utcnow().isoformat()
            }

            logger.info("[GoogleVerify] Attempting Supabase upsert", extra={
                "auth_id": user_info['auth_id'],
                "email": user_info['email'],
                "current_state": user_data['current_state'],
                "metadata_keys": list(user_data['state_metadata'].keys())
            })
            
            try:
                # Upsert user data with conflict handling
                response = self.supabase.table('users').upsert(
                    user_data,
                    on_conflict='auth_id'  # Use auth_id for conflict resolution
                ).execute()
                
                logger.info("[GoogleVerify] Supabase upsert response", extra={
                    "has_data": bool(response.data),
                    "response_data": response.data,
                    "status": response.status_code if hasattr(response, 'status_code') else None
                })
                
                if not response.data:
                    raise Exception("Failed to update user data in Supabase")
            except Exception as e:
                logger.error("[GoogleVerify] Supabase upsert failed", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack": traceback.format_exc(),
                    "user_data": user_data
                })
                raise
            
            try:
                # Get the user's ID for state history
                user_response = self.supabase.table('users').select('id').eq('auth_id', user_info['auth_id']).single().execute()
                
                logger.info("[GoogleVerify] Supabase user lookup response", extra={
                    "has_data": bool(user_response.data),
                    "response_data": user_response.data,
                    "auth_id": user_info['auth_id']
                })
                
                if not user_response.data:
                    raise Exception("Failed to get user ID after upsert")
            except Exception as e:
                logger.error("[GoogleVerify] Supabase user lookup failed", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack": traceback.format_exc(),
                    "auth_id": user_info['auth_id']
                })
                raise
            
            # Record initial state transition
            history_data = {
                'internal_user_id': user_response.data['id'],
                'from_state': 'VISITOR',
                'to_state': 'AUTH',
                'transition_reason': 'Google Sign-In',
                'metadata': user_data['state_metadata'],
                'created_at': datetime.utcnow().isoformat()
            }
            
            try:
                history_response = self.supabase.table('user_state_history').insert(history_data).execute()
                logger.info("[GoogleVerify] State history recorded", extra={
                    "has_data": bool(history_response.data),
                    "response_data": history_response.data,
                    "internal_user_id": user_response.data['id']
                })
            except Exception as e:
                logger.error("[GoogleVerify] Failed to record state history", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack": traceback.format_exc(),
                    "history_data": history_data
                })
                # Don't fail the whole process if history recording fails
            
            # Create session token
            try:
                session_token = self.create_session_token(user_info)
                logger.info("[GoogleVerify] Session token created", extra={
                    "token_length": len(session_token) if session_token else 0,
                    "user_email": user_info['email'],
                    "auth_id": user_info['auth_id']
                })
            except Exception as e:
                logger.error("[GoogleVerify] Failed to create session token", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack": traceback.format_exc(),
                    "user_info": user_info
                })
                raise
            
            logger.info("[GoogleVerify] Token verification successful", extra={
                "user_email": user_info.get("email"),
                "auth_id": user_info.get("auth_id"),
                "current_state": user_data['current_state']
            })
            
            return AuthResult(
                success=True,
                user_info=user_info,
                session_token=session_token
            )
            
        except ValueError as e:
            # Invalid token
            logger.error("[GoogleVerify] Invalid Google token", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "stack": traceback.format_exc()
            })
            return AuthResult(
                success=False,
                error_message="Invalid Google token"
            )
        except Exception as e:
            logger.error("[GoogleVerify] Google Sign-In failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "stack": traceback.format_exc()
            })
            return AuthResult(
                success=False,
                error_message=str(e)
            )

    async def verify_session_token(self, token: str) -> Optional[Dict]:
        """Verify session token"""
        try:
            if not token:
                logger.info("No token provided for verification")
                return None
                
            # Log token details before verification
            logger.info("Verifying session token")
            current_time = int(datetime.now(timezone.utc).timestamp())
            logger.info(f"Current time (UTC): {current_time}")
            
            try:
                # First decode without verification to log token contents
                unverified = jwt.decode(token, options={"verify_signature": False})
                logger.info(f"Raw token data: {unverified}")
                
                # Now decode with verification and generous leeway
                decoded = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=['HS256'],
                    leeway=300  # Allow 5 minutes of leeway for timing issues
                )
                logger.info(f"Token decoded successfully, auth_id: {decoded.get('auth_id')}")
                
                # Log timing details
                logger.info(
                    f"Token timing details:\n"
                    f"Current time (UTC): {current_time}\n"
                    f"Token iat: {decoded.get('iat')} (diff: {current_time - decoded.get('iat', 0)} seconds)\n"
                    f"Token nbf: {decoded.get('nbf')} (diff: {current_time - decoded.get('nbf', 0)} seconds)\n"
                    f"Token exp: {decoded.get('exp')} (diff: {decoded.get('exp', 0) - current_time} seconds remaining)"
                )
                
                # Verify user exists in Supabase
                response = self.supabase.table('users').select('*').eq('auth_id', decoded['auth_id']).single().execute()
                logger.info(f"Supabase user lookup result: {bool(response.data)}")
                
                if not response.data:
                    logger.warning(f"User not found in database for auth_id: {decoded.get('auth_id')}")
                    return None
                
                return decoded
                
            except jwt.ExpiredSignatureError:
                logger.error("Token has expired")
                return None
            except jwt.InvalidTokenError as e:
                logger.error(f"Invalid token: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def create_session_token(self, user_info: Dict) -> str:
        """Create a session token for the user"""
        # Get current Unix timestamp
        current_time = int(time.time())
        
        token_data = {
            'auth_id': user_info['auth_id'],
            'email': user_info['email'],
            'exp': current_time + (7 * 24 * 60 * 60),  # 7 days from now
            'iat': current_time,
            'nbf': current_time
        }
        
        logger.info(f"Creating token with current_time={current_time}")
        
        return jwt.encode(
            token_data,
            self.jwt_secret,
            algorithm='HS256'
        )

    async def get_state_requirements(self) -> Dict:
        """Get requirements for the AUTH state"""
        return {
            "required_fields": ["auth_id", "email"],
            "allowed_transitions": ["PAYMENT"],
            "description": "Authentication state using Google Sign-In"
        }
