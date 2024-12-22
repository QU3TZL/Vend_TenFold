import logging
from typing import Dict, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

logger = logging.getLogger(__name__)

class MockDB:
    def __init__(self):
        self._users = {}
        self._folders = {}
        
    async def create_or_update_user(self, email: str, auth_id: UUID) -> Optional[Dict]:
        """Create or update user in mock database"""
        try:
            # Check if user exists by auth_id
            existing_user = next(
                (user for user in self._users.values() if str(user['auth_id']) == str(auth_id)),
                None
            )
            
            if existing_user:
                # Update existing user
                existing_user.update({
                    'email': email,
                    'updated_at': datetime.utcnow().isoformat()
                })
                logger.info(f"Updated mock user: {existing_user['id']}")
                return existing_user
                
            # Create new user
            user_id = str(uuid4())
            new_user = {
                'id': user_id,
                'email': email,
                'auth_id': str(auth_id),
                'drive_auth_status': 'pending',
                'account_status': 'active',
                'subscription_tier': 'free',
                'storage_limit_gb': 5,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            self._users[user_id] = new_user
            logger.info(f"Created mock user: {user_id}")
            return new_user
            
        except Exception as e:
            logger.error(f"Mock user creation failed: {e}")
            return None
            
    async def get_user(self, user_id: UUID) -> Optional[Dict]:
        """Get user by ID from mock database"""
        return self._users.get(str(user_id))
        
    async def get_user_by_auth_id(self, auth_id: UUID) -> Optional[Dict]:
        """Get user by auth_id from mock database"""
        return next(
            (user for user in self._users.values() if str(user['auth_id']) == str(auth_id)),
            None
        )
        
    async def update_user_subscription(
        self,
        user_id: UUID,
        subscription_id: str,
        subscription_tier: str
    ) -> Optional[Dict]:
        """Update user subscription in mock database"""
        user = self._users.get(str(user_id))
        if user:
            user.update({
                'subscription_id': subscription_id,
                'subscription_tier': subscription_tier,
                'subscription_status': 'active',
                'updated_at': datetime.utcnow().isoformat()
            })
            return user
        return None
        
    async def create_folder(self, folder_data: Dict) -> Optional[Dict]:
        """Create folder in mock database"""
        try:
            folder_id = str(uuid4())
            folder = {
                'id': folder_id,
                **folder_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            self._folders[folder_id] = folder
            return folder
        except Exception as e:
            logger.error(f"Mock folder creation failed: {e}")
            return None
            
    async def get_folder(self, folder_id: UUID) -> Optional[Dict]:
        """Get folder by ID from mock database"""
        return self._folders.get(str(folder_id))
        
    async def get_user_folders(self, user_id: UUID) -> List[Dict]:
        """Get all folders for a user from mock database"""
        return [
            folder for folder in self._folders.values()
            if str(folder['user_id']) == str(user_id)
        ]
        
    async def update_folder(self, folder_id: UUID, folder_data: Dict) -> Optional[Dict]:
        """Update folder in mock database"""
        folder = self._folders.get(str(folder_id))
        if folder:
            folder.update({
                **folder_data,
                'updated_at': datetime.utcnow().isoformat()
            })
            return folder
        return None

mock_db = MockDB() 