import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from supabase import Client
from src.api.state.drive.drive_service import DriveService
from src.services.logging.state_logger import StateLogger, StateTransition
import json
import tempfile
import os

logger = logging.getLogger(__name__)

class ActiveService:
    """Service to handle active state logic"""
    
    def __init__(self, state_manager, supabase_client: Client):
        self.state_manager = state_manager
        self.supabase = supabase_client
        self.drive_service = DriveService(state_manager, supabase_client)
        self.logger = StateLogger()
        self.allowed_transitions = []  # No transitions from ACTIVE state
        self.required_fields = ["folder_id", "folder_name", "folder_url"]
        
    async def init_deployment_listener(self):
        """Initialize listener for folder deployment notifications"""
        try:
            # For now, we'll rely on the database trigger auto_deploy_folder()
            # to handle the folder creation when drive_auth_status changes
            logger.info("Active service initialized - using database triggers for folder deployment")
            
        except Exception as e:
            logger.error(f"Failed to initialize deployment listener: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Clean up any resources if needed
            logger.info("Successfully cleaned up active service")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise

    async def handle_folder_deployment(self, payload: Dict):
        """Handle folder deployment notification"""
        try:
            logger.info(f"Received deployment notification: {payload}")
            
            # Extract data from payload
            folder_id = payload['new']['id']
            user_id = payload['new']['user_id']
            
            # Get user details
            user_response = self.supabase.table('users').select('*').eq('id', user_id).single().execute()
            if not user_response.data:
                raise Exception("User not found")
            
            user = user_response.data
            user_email = user['email']
            
            # Notify started
            await self.state_manager.notify_state_change(user_id, {
                'current_state': 'DRIVE',
                'state_metadata': {
                    'folder_deployment': {
                        'type': 'folder_deployment',
                        'status': 'started'
                    }
                }
            })
            
            # Get folder name from drive service
            folder_name = await self.drive_service.get_next_folder_name()
            
            # Create drive folder
            drive_folder = await self.drive_service.create_folder(
                owner_email=user_email
            )
            
            if not drive_folder:
                raise Exception("Failed to create drive folder")

            # Notify folder created
            await self.state_manager.notify_state_change(user_id, {
                'current_state': 'DRIVE',
                'state_metadata': {
                    'folder_deployment': {
                        'type': 'folder_deployment',
                        'status': 'folder_created',
                        'folder_id': drive_folder['id'],
                        'folder_name': drive_folder['name']
                    }
                }
            })

            # Create and upload README
            readme_content = self.create_readme_content(
                folder_name=drive_folder['name'],
                owner_email=user_email,
                created_at=datetime.utcnow().isoformat(),
                folder_number=payload['new']['state_metadata']['workspace_status']['folder_number']
            )
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
                temp_file.write(readme_content)
                temp_path = temp_file.name
            
            try:
                readme_file = await self.drive_service.upload_file(
                    file_path=temp_path,
                    file_name='README.md',
                    mime_type='text/markdown',
                    parent_folder_id=drive_folder['id']
                )

                # Notify README uploaded
                await self.state_manager.notify_state_change(user_id, {
                    'current_state': 'DRIVE',
                    'state_metadata': {
                        'folder_deployment': {
                            'type': 'folder_deployment',
                            'status': 'readme_uploaded'
                        }
                    }
                })

            finally:
                os.unlink(temp_path)

            # Update folder status
            folder_update = {
                'drive_folder_id': drive_folder['id'],
                'current_state': 'ACTIVE',
                'status': 'active',
                'state_metadata': {
                    'workspace_status': {
                        'drive_url': drive_folder['webViewLink'],
                        'deployment_status': 'completed',
                        'storage_metrics': {
                            'storage_used': 0,
                            'storage_limit': 10 * 1024 * 1024 * 1024,
                            'folder_count': 1
                        }
                    }
                }
            }
            
            self.supabase.table('folders').update(folder_update).eq('id', folder_id).execute()
            
            # Notify frontend of completion
            await self.state_manager.notify_state_change(user_id, {
                'current_state': 'ACTIVE',
                'state_metadata': {
                    'folder_deployment': {
                        'type': 'folder_deployment',
                        'status': 'completed'
                    },
                    'folder_id': drive_folder['id'],
                    'folder_name': drive_folder['name'],
                    'folder_url': drive_folder['webViewLink'],
                    'deployment_status': 'completed',
                    'workspace_status': folder_update['state_metadata']['workspace_status']
                }
            })
            
        except Exception as e:
            logger.error(f"Error during folder deployment: {e}")
            raise

    def create_readme_content(self, folder_name, owner_email, created_at, folder_number):
        return f"""# {folder_name}

## Folder Details
- Owner: {owner_email}
- Created: {created_at}
- Folder Number: {folder_number:02d}

## Purpose
This folder is managed by TenFold for secure document storage and processing.

## Features
- Automatic document processing
- Secure storage
- Version control
- Access management

## Notes
- Do not modify folder structure directly
- All changes are tracked and versioned
- Contact support for assistance
"""

    async def get_active_info(self, user_id: str) -> Dict:
        """Get current active state information"""
        try:
            # Get user state from state manager
            state = await self.state_manager.get_current_state(user_id)
            
            if not state:
                return {
                    "current_state": "ACTIVE",
                    "state_metadata": {
                        "error": "User not found",
                        "last_updated": datetime.utcnow().isoformat()
                    }
                }
            
            # Get folder information
            folder_id = state.get('state_metadata', {}).get('active_folder_id')
            folder_info = None
            
            if folder_id:
                response = self.supabase.table('folders').select('*').eq('id', folder_id).single().execute()
                folder_info = response.data if response.data else None
                
            return {
                "current_state": "ACTIVE",
                "state_metadata": {
                    **state.get('state_metadata', {}),
                    "folder": folder_info,
                    "last_updated": datetime.utcnow().isoformat(),
                    "allowed_transitions": self.allowed_transitions
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get active info: {str(e)}")
            raise

    async def validate_transition(self, target_state: str, state_data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate state transition from ACTIVE"""
        try:
            # ACTIVE is the final state - no transitions allowed
            return False, "Cannot transition from ACTIVE state"
            
        except Exception as e:
            logger.error(f"Transition validation failed: {str(e)}")
            return False, str(e)

    async def transition_state(self, user_id: str, target_state: str, state_data: Dict) -> Tuple[bool, Dict]:
        """Handle the transition from ACTIVE to another state"""
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
                f"Transition from ACTIVE to {target_state}"
            )
            
            if not success:
                return False, {"error": result}
                
            return True, result
            
        except Exception as e:
            logger.error(f"State transition failed: {str(e)}")
            return False, {"error": str(e)}

    async def get_state_requirements(self) -> Dict:
        """Get requirements for the ACTIVE state"""
        return {
            "required_fields": self.required_fields,
            "allowed_transitions": self.allowed_transitions,
            "description": "Folders deployed and active"
        }

    async def get_folder_stats(self, user_id: str) -> Optional[Dict]:
        """Get statistics for user's active folders"""
        try:
            response = self.supabase.table('folders')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('current_state', 'ACTIVE')\
                .execute()
                
            if not response.data:
                return None
                
            folders = response.data
            total_size = sum(folder.get('current_size_bytes', 0) for folder in folders)
            total_files = sum(folder.get('file_count', 0) for folder in folders)
            
            return {
                "folder_count": len(folders),
                "total_size_bytes": total_size,
                "total_files": total_files,
                "folders": folders
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder stats: {str(e)}")
            return None

    async def update_folder_stats(self, folder_id: str, size_bytes: int, file_count: int) -> bool:
        """Update statistics for a specific folder"""
        try:
            response = self.supabase.table('folders').update({
                'current_size_bytes': size_bytes,
                'file_count': file_count,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', folder_id).execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Failed to update folder stats: {str(e)}")
            return False

    async def initialize_active_state(self, user_id: str, state_data: Dict) -> Tuple[bool, Dict]:
        """Initialize the ACTIVE state after drive auth"""
        try:
            self.logger.state_change(
                StateTransition.DRIVE_TO_ACTIVE,
                user_id,
                success=True,
                details={"action": "start_initialization"}
            )
            
            # Get pending folder
            folder = await self.drive_service.get_pending_folder(user_id)
            if not folder:
                self.logger.error("active", "No pending folder found", {"user_id": user_id})
                return False, {"error": "No pending folder found"}

            # Create drive folder
            self.logger.drive_event("create_folder", {
                "user_id": user_id,
                "folder_name": folder['name']
            })
            
            drive_folder = await self.drive_service.create_folder(
                folder['name'], 
                state_data.get('email', 'user@example.com')
            )
            
            if not drive_folder:
                self.logger.error("drive", "Failed to create folder", {
                    "user_id": user_id,
                    "folder_name": folder['name']
                })
                return False, {"error": "Failed to create drive folder"}

            # Update folder status
            self.logger.db_event("update_folder", {
                "folder_id": folder['id'],
                "drive_folder_id": drive_folder['id'],
                "status": "active"
            })

            folder_update = {
                'drive_folder_id': drive_folder['id'],
                'current_state': 'ACTIVE',
                'status': 'active',
                'state_metadata': {
                    'workspace_status': {
                        'drive_url': drive_folder['webViewLink'],
                        'deployment_status': 'completed',
                        'storage_metrics': {
                            'storage_used': 0,
                            'storage_limit': 10 * 1024 * 1024 * 1024,
                            'folder_count': 1
                        }
                    }
                }
            }

            folder_response = self.supabase.table('folders').update(folder_update).eq('id', folder['id']).execute()
            
            if not folder_response.data:
                self.logger.error("database", "Failed to update folder status", {
                    "folder_id": folder['id']
                })
                return False, {"error": "Failed to update folder status"}

            self.logger.state_change(
                StateTransition.DRIVE_TO_ACTIVE,
                user_id,
                success=True,
                details={
                    "folder_id": drive_folder['id'],
                    "folder_name": drive_folder['name']
                }
            )

            return True, {
                "state_metadata": {
                    'folder_id': drive_folder['id'],
                    'folder_name': drive_folder['name'],
                    'folder_url': drive_folder['webViewLink'],
                    'deployment_status': 'completed',
                    'workspace_status': folder_update['state_metadata']['workspace_status']
                },
                "folder": drive_folder
            }

        except Exception as e:
            self.logger.error("active", str(e), {
                "user_id": user_id,
                "action": "initialize_active_state"
            })
            return False, {"error": str(e)}
