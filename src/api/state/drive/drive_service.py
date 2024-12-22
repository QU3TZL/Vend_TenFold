"""
# Google Drive Service Implementation
# ================================
#
# This service handles all Drive operations using a service account.
# For OAuth scopes and permission model, see google.py.
#
# Service Account Operations
# ------------------------
# 1. Folder Management
#    - Create folders for users
#    - Set initial permissions
#    - Manage file operations
#
# 2. File Operations
#    - Upload/download files
#    - Update permissions
#    - Track file changes
#
# 3. Permission Management
#    - Grant user access
#    - Update sharing settings
#    - Monitor access changes
"""

import logging
import os
from typing import Dict, Optional, Tuple
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from supabase import Client
import base64
import json
import asyncio
from .google import OAUTH_SCOPES  # Import central scopes

logger = logging.getLogger(__name__)

class DriveService:
    """Service to handle drive state logic"""
    
    def __init__(self, state_manager, supabase_client: Client):
        self.state_manager = state_manager
        self.supabase = supabase_client
        self.allowed_transitions = ["ACTIVE"]
        self.required_fields = ["drive_tokens", "drive_permissions"]
        
        # Simple mock mode check
        self.is_mock = os.getenv("USE_MOCK", "false").lower() == "true"
        logger.info(f"DriveService running in {'mock' if self.is_mock else 'real'} mode")
        
        if not self.is_mock:
            try:
                # Set up service account for Drive operations
                creds_b64 = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_BASE64')
                if not creds_b64:
                    raise ValueError("Missing Google service account credentials")
                    
                creds_json = base64.b64decode(creds_b64).decode('utf-8')
                creds_data = json.loads(creds_json)
                self.service_creds = service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=OAUTH_SCOPES  # Use central scopes
                )
                
                # Build the service once during initialization
                self.service = build('drive', 'v3', credentials=self.service_creds)
                logger.info("Successfully initialized Drive service with service account")
            except Exception as e:
                logger.error(f"Failed to initialize Drive service: {e}")
                raise

    async def get_next_folder_name(self) -> str:
        """Get the next folder name in the sequence [FolderName##]_TenFold"""
        try:
            # Get all folders from supabase
            folders_response = self.supabase.table('folders').select('name').execute()
            folder_num = 1
            
            if folders_response.data:
                numbers = []
                for folder in folders_response.data:
                    if folder['name'] and '[FolderName' in folder['name']:
                        try:
                            num = int(folder['name'].split('[FolderName')[1][:2])
                            numbers.append(num)
                        except (ValueError, IndexError):
                            continue
                folder_num = max(numbers + [0]) + 1
            
            return f"[FolderName{folder_num:02d}]_TenFold"
            
        except Exception as e:
            logger.error(f"Failed to generate folder name: {str(e)}")
            return f"[FolderName01]_TenFold"  # Fallback name

    async def create_folder(self, owner_email: str) -> Optional[Dict]:
        """Create a folder in Google Drive"""
        try:
            # Generate the next folder name
            folder_name = await self.get_next_folder_name()
            
            if self.is_mock:
                return {
                    'id': 'mock_folder_id',
                    'name': folder_name,
                    'webViewLink': f'https://drive.google.com/mock/{folder_name}'
                }
                
            # Create the folder with service account ownership
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'supportsAllDrives': True
            }
            
            # Create the folder
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            # Share with user as editor with full content access
            permission = {
                'type': 'user',
                'role': 'writer',  # Editor role
                'emailAddress': owner_email,
                'sendNotificationEmail': False,
                'supportsAllDrives': True
            }
            
            # Create the permission
            self.service.permissions().create(
                fileId=folder['id'],
                body=permission,
                supportsAllDrives=True,
                transferOwnership=False  # Ensure service account retains ownership
            ).execute()
            
            # Wait a moment for permission to propagate
            await asyncio.sleep(2)
            
            return folder
            
        except Exception as e:
            logger.error(f"Failed to create folder: {str(e)}")
            return None

    async def upload_file(self, file_path: str, file_name: str, mime_type: str, parent_folder_id: str) -> Optional[Dict]:
        """Upload a file to Google Drive"""
        try:
            if self.is_mock:
                return {
                    'id': 'mock_file_id',
                    'name': file_name,
                    'webViewLink': f'https://drive.google.com/mock/{file_name}'
                }
                
            file_metadata = {
                'name': file_name,
                'parents': [parent_folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload the file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            return file
            
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            return None

    async def get_drive_info(self, user_id: str) -> Dict:
        """Get current drive state information"""
        try:
            # Get user state from state manager
            state = await self.state_manager.get_current_state(user_id)
            
            if not state:
                return {
                    "current_state": "DRIVE",
                    "state_metadata": {
                        "error": "User not found",
                        "last_updated": datetime.utcnow().isoformat()
                    }
                }
                
            return {
                "current_state": "DRIVE",
                "state_metadata": {
                    **state.get('state_metadata', {}),
                    "last_updated": datetime.utcnow().isoformat(),
                    "allowed_transitions": self.allowed_transitions
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get drive info: {str(e)}")
            raise

    async def validate_transition(self, target_state: str, state_data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate state transition from DRIVE"""
        try:
            # Check if transition is allowed
            if target_state not in self.allowed_transitions:
                return False, f"Invalid transition from DRIVE to {target_state}"
                
            # Validate required fields
            missing_fields = [field for field in self.required_fields if field not in state_data]
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"
                
            # Validate drive connection
            if not state_data.get('drive_connected'):
                return False, "Drive must be connected before transitioning"
                
            return True, None
            
        except Exception as e:
            logger.error(f"Transition validation failed: {str(e)}")
            return False, str(e)

    async def transition_state(self, user_id: str, target_state: str, state_data: Dict) -> Tuple[bool, Dict]:
        """Handle the transition from DRIVE to another state"""
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
                f"Transition from DRIVE to {target_state}"
            )
            
            if not success:
                return False, {"error": result}
                
            return True, result
            
        except Exception as e:
            logger.error(f"State transition failed: {str(e)}")
            return False, {"error": str(e)}

    async def get_state_requirements(self) -> Dict:
        """Get requirements for the DRIVE state"""
        return {
            "required_fields": self.required_fields,
            "allowed_transitions": self.allowed_transitions,
            "description": "Google Drive connection required"
        }

    async def verify_drive_tokens(self, tokens: Dict) -> bool:
        """Verify drive tokens are valid"""
        try:
            if self.is_mock:
                return True
                
            credentials = Credentials(
                token=tokens.get('access_token'),
                refresh_token=tokens.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET')
            )
            
            service = build('drive', 'v3', credentials=credentials)
            about = service.about().get(fields='user').execute()
            
            return bool(about.get('user', {}).get('emailAddress'))
            
        except Exception as e:
            logger.error(f"Failed to verify drive tokens: {str(e)}")
            return False
