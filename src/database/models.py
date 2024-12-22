from pydantic import BaseModel, EmailStr, UUID4, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class StateMetadata(BaseModel):
    """Model for state metadata"""
    user: Optional[Dict[str, Any]] = {}
    status: Optional[str] = None
    plan_id: Optional[str] = None
    plan_name: Optional[str] = None
    session_id: Optional[str] = None
    payment_complete: Optional[bool] = False
    stripe_session_id: Optional[str] = None
    trial: Optional[bool] = False
    trial_end_date: Optional[datetime] = None
    drive_tokens: Optional[Dict[str, Any]] = None
    drive_permissions: Optional[Dict[str, Any]] = None
    drive_connected: Optional[bool] = False
    oauth_in_progress: Optional[bool] = False
    active_folder_id: Optional[str] = None
    activation_date: Optional[datetime] = None

class UserBase(BaseModel):
    """Base User model with common attributes"""
    email: EmailStr
    auth_id: str
    current_state: str = 'VISITOR'
    state_metadata: StateMetadata = Field(default_factory=StateMetadata)
    drive_auth_status: str = 'pending'
    account_status: str = 'pending'
    subscription_tier: str = 'free'
    storage_limit_gb: int = 5

class UserCreate(UserBase):
    """Model for creating a new user"""
    pass

class UserUpdate(BaseModel):
    """Model for updating user data"""
    email: Optional[EmailStr] = None
    current_state: Optional[str] = None
    state_metadata: Optional[StateMetadata] = None
    drive_auth_status: Optional[str] = None
    account_status: Optional[str] = None
    subscription_tier: Optional[str] = None
    storage_limit_gb: Optional[int] = None
    stripe_customer_id: Optional[str] = None
    drive_access_token: Optional[str] = None
    drive_refresh_token: Optional[str] = None
    drive_expiry_date: Optional[datetime] = None

class User(UserBase):
    """Complete User model with all attributes"""
    id: UUID
    stripe_customer_id: Optional[str] = None
    drive_access_token: Optional[str] = None
    drive_refresh_token: Optional[str] = None
    drive_expiry_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FolderState(BaseModel):
    """Model for folder state"""
    current_state: str = 'PENDING'
    state_metadata: Dict[str, Any] = Field(default_factory=dict)

class FolderBase(BaseModel):
    """Base Folder model with common attributes"""
    user_id: UUID
    name: str
    current_state: str = 'PENDING'
    state_metadata: Dict[str, Any] = Field(default_factory=dict)
    storage_limit_gb: int = 5
    current_size_bytes: int = 0
    file_count: int = 0
    payment_id: Optional[str] = None

class FolderCreate(FolderBase):
    """Model for creating a new folder"""
    pass

class FolderUpdate(BaseModel):
    """Model for updating folder data"""
    name: Optional[str] = None
    current_state: Optional[str] = None
    state_metadata: Optional[Dict[str, Any]] = None
    storage_limit_gb: Optional[int] = None
    current_size_bytes: Optional[int] = None
    file_count: Optional[int] = None
    payment_id: Optional[str] = None

class Folder(FolderBase):
    """Complete Folder model with all attributes"""
    id: UUID
    drive_folder_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True

class StateTransition(BaseModel):
    """Model for state transitions"""
    from_state: str
    to_state: str
    transition_reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True 