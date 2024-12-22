# TenFold Drive State Documentation

## Overview
The DRIVE state manages Google Drive integration, folder setup, and permission management after successful payment completion. It implements folder creation, permission setup, and validates the transition to ACTIVE state.

## Directory Structure
```
src/api/state/04_drive/
├── __init__.py
├── drive_routes.py
├── drive_service.py
├── drive_models.py
├── google_service.py
└── templates/
    ├── drive_setup.html
    ├── components/
    │   ├── folder_structure.html
    │   ├── permission_manager.html
    │   ├── setup_progress.html
    │   └── drive_status.html
    └── partials/
        ├── drive_header.html
        └── drive_footer.html
```

## Core Components

### DriveService
```python
class DriveService:
    def __init__(self, state_manager, google_service):
        self.state_manager = state_manager
        self.google = google_service
        self.allowed_transitions = ["ACTIVE", "PAYMENT"]
        
    async def setup_folder_structure(self, user_id: str) -> FolderSetupResult:
        """Create initial folder structure"""
        
    async def configure_permissions(self, folder_id: str, permissions: List[Permission]) -> PermissionResult:
        """Set folder permissions"""
        
    async def validate_setup(self, user_id: str) -> ValidationResult:
        """Validate drive setup completion"""
```

### Data Models
```python
class FolderStructure(BaseModel):
    root_folder_id: str
    subfolders: Dict[str, str]  # name: folder_id
    owner_email: str
    created_at: datetime

class Permission(BaseModel):
    email: str
    role: str  # viewer, editor, owner
    folder_id: str
    notify: bool = True

class SetupStatus(BaseModel):
    completed_steps: List[str]
    current_step: str
    errors: List[str]
    is_complete: bool
```

## API Endpoints

### drive_routes.py
```python
router = APIRouter(prefix="/api/state/drive")

@router.post("/setup")
async def initialize_drive(user_data: UserDriveData):
    """Initialize drive setup"""

@router.post("/folders")
async def create_folders(folder_structure: FolderStructure):
    """Create folder structure"""

@router.post("/permissions")
async def set_permissions(permissions: List[Permission]):
    """Configure folder permissions"""

@router.get("/status")
async def get_setup_status():
    """Get drive setup status"""

@router.post("/transition/active")
async def transition_to_active():
    """Handle ACTIVE state transition"""
```

## UI Components

### Drive Setup Page
```html
<!-- drive_setup.html -->
{% extends "base.html" %}

{% block content %}
<div class="drive-setup-container"
     x-data="{ setupStep: 'init' }">
    {% include "components/setup_progress.html" %}
    {% include "components/folder_structure.html" %}
    
    <div class="setup-actions">
        <button hx-post="/api/state/drive/transition/active"
                hx-trigger="click"
                x-show="setupComplete">
            Complete Setup
        </button>
    </div>
</div>
{% endblock %}
```

### Google Drive Integration
```html
<!-- components/folder_structure.html -->
<div class="folder-structure"
     x-data="{ folders: [] }">
    <template x-for="folder in folders">
        <div class="folder-item">
            <span x-text="folder.name"></span>
            <button @click="configureFolderPermissions(folder.id)">
                Configure Access
            </button>
        </div>
    </template>
</div>
```

## State Transitions

### To ACTIVE State
1. Verify folder structure
2. Validate permissions
3. Test drive access
4. Initialize active state

```python
async def prepare_active_transition(user_id: str) -> bool:
    """
    Prepare drive setup for ACTIVE state
    - Validate folder structure
    - Verify permissions
    - Test access tokens
    - Set transition flags
    """
```

## Google Drive Integration

### Services
```python
class GoogleDriveService:
    def __init__(self, credentials: GoogleCredentials):
        self.drive = build('drive', 'v3', credentials=credentials)
        
    async def create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Create Google Drive folder"""
        
    async def set_folder_permission(self, folder_id: str, permission: Permission) -> bool:
        """Set folder permissions"""
        
    async def validate_access(self, folder_id: str) -> bool:
        """Validate folder access"""
```

## Security Considerations

### Access Control
```python
class DriveAccessControl:
    def validate_permissions(self, permissions: List[Permission]) -> bool:
        """Validate permission settings"""
    
    def verify_user_access(self, user_id: str, folder_id: str) -> bool:
        """Verify user access rights"""
```

### Token Management
```python
class DriveTokenManager:
    def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh Google Drive access token"""
    
    def validate_token(self, access_token: str) -> bool:
        """Validate token validity"""
```

## Testing Strategy

### Unit Tests
```python
async def test_folder_creation():
    """Test folder structure creation"""

async def test_permission_setup():
    """Test permission configuration"""

async def test_drive_validation():
    """Test drive setup validation"""
```

### Integration Tests
```python
async def test_google_drive_integration():
    """Test Google Drive API integration"""

async def test_setup_flow():
    """Test end-to-end setup flow"""
```

## Development Guidelines

### Adding Folder Templates
1. Define folder structure
2. Configure default permissions
3. Add validation rules
4. Update setup flow

### Permission Management
1. Define permission levels
2. Implement access controls
3. Add notification system
4. Handle permission updates

## Configuration

### Environment Variables
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_API_KEY=...
DRIVE_FOLDER_PREFIX=...
```

### Drive Configuration
```python
DRIVE_CONFIG = {
    "folder_structure": {
        "root": {
            "name": "{company_name} Workspace",
            "subfolders": ["Documents", "Shared", "Archive"]
        }
    },
    "default_permissions": {
        "owner": ["FULL_ACCESS"],
        "editor": ["ORGANIZE", "EDIT_CONTENT"],
        "viewer": ["VIEW_ONLY"]
    }
}
```

## Monitoring

### Key Metrics
- Setup completion rate
- Permission configuration success
- Access validation rate
- Setup duration

### Logging
```python
logger.info("Drive event", extra={
    "user_id": user_id,
    "event_type": "folder_created",
    "folder_id": folder_id,
    "timestamp": datetime.now()
})
```

## Error Handling

### Common Scenarios
1. Drive API errors
2. Permission conflicts
3. Token expiration
4. Quota limitations

### Implementation
```python
async def handle_drive_error(
    error_type: str,
    error_data: Dict
) -> Response:
    """Handle drive setup errors"""
```

## State Management

### Drive State Pattern
```python
# Default drive state
default_drive_state = {
    "current_state": "DRIVE",
    "state_metadata": {
        "allowed_transitions": ["ACTIVE", "PAYMENT"],
        "drive": {
            "status": "pending",
            "folder_id": None,
            "setup_complete": False
        }
    }
}

# Active drive state
active_drive_state = {
    "current_state": "DRIVE",
    "state_metadata": {
        "allowed_transitions": ["ACTIVE"],
        "drive": {
            "status": "completed",
            "folder_id": "google_folder_id",
            "setup_complete": True,
            "folders": {
                "root": {
                    "id": "root_folder_id",
                    "name": "Company Workspace",
                    "url": "folder_url"
                },
                "subfolders": {
                    "documents": "doc_folder_id",
                    "shared": "shared_folder_id",
                    "archive": "archive_folder_id"
                }
            },
            "permissions": {
                "owner": "user@email.com",
                "configured": True
            }
        }
    }
}
```

### State Transitions

#### PAYMENT → DRIVE
```python
@router.post("/initialize")
async def initialize_drive_state(request: Request):
    """Initialize drive state after payment"""
    try:
        # Verify payment completion
        token = request.cookies.get('access_token')
        user_data = await state_manager.verify_session_token(token)
        
        # Validate payment state
        current_state = await state_manager.get_current_state(user_data['auth_id'])
        if current_state['current_state'] != 'PAYMENT' or \
           not current_state['state_metadata']['payment']['payment_complete']:
            raise HTTPException(status_code=400, detail="Invalid state transition")
        
        # Initialize drive setup
        drive_state = await drive_service.initialize_drive_setup(user_data)
        
        return {
            "success": True,
            "data": drive_state
        }
        
    except Exception as e:
        logger.error(f"Drive initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### DRIVE → ACTIVE
```python
@router.post("/complete")
async def complete_drive_setup(request: Request):
    """Complete drive setup and transition to ACTIVE"""
    try:
        # Verify setup completion
        token = request.cookies.get('access_token')
        user_data = await state_manager.verify_session_token(token)
        
        # Validate drive state
        validation = await drive_service.validate_setup(user_data['auth_id'])
        if not validation.is_complete:
            return {
                "success": False,
                "errors": validation.errors
            }
        
        # Transition to ACTIVE
        active_state = await state_manager.transition_user_state(
            user_data['auth_id'],
            'ACTIVE',
            validation.state_data
        )
        
        return {
            "success": True,
            "data": active_state
        }
        
    except Exception as e:
        logger.error(f"Drive completion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Frontend Integration

### Alpine.js Store Integration
```javascript
// Drive state store module
Alpine.store('driveState', {
    setup: {
        currentStep: 'init',
        progress: 0,
        errors: [],
        completed: false
    },
    folders: {
        root: null,
        subfolders: {}
    },
    
    // Actions
    async initializeDrive() {
        try {
            const response = await fetch('/api/state/drive/initialize', {
                method: 'POST',
                credentials: 'include'
            });
            const data = await response.json();
            
            if (data.success) {
                this.setup.currentStep = 'creating_folders';
                this.startProgressMonitoring();
            }
        } catch (error) {
            this.handleError('initialization', error);
        }
    },
    
    // Progress monitoring
    startProgressMonitoring() {
        const events = new EventSource('/api/state/drive/progress');
        
        events.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateProgress(data);
        };
        
        events.onerror = () => {
            events.close();
            this.handleError('sse', new Error('Progress monitoring failed'));
        };
    },
    
    // Update handlers
    updateProgress(data) {
        this.setup.progress = data.progress;
        this.setup.currentStep = data.current_step;
        
        if (data.folders) {
            this.folders = data.folders;
        }
        
        if (data.completed) {
            this.setup.completed = true;
            this.transitionToActive();
        }
    }
});
```

### UI Components Integration
```html
<!-- components/setup_progress.html -->
<div x-data 
     x-bind:class="{ 'completed': $store.driveState.setup.completed }">
    
    <!-- Progress indicator -->
    <div class="progress-bar"
         x-bind:style="{ width: $store.driveState.setup.progress + '%' }">
    </div>
    
    <!-- Step indicator -->
    <div class="setup-step"
         x-text="$store.driveState.setup.currentStep">
    </div>
    
    <!-- Error display -->
    <div class="error-container" 
         x-show="$store.driveState.setup.errors.length > 0">
        <template x-for="error in $store.driveState.setup.errors">
            <div class="error-message" x-text="error"></div>
        </template>
    </div>
</div>
```

## Server-Sent Events (SSE)

### Progress Monitoring
```python
@router.get("/progress")
async def monitor_progress(request: Request):
    """Stream drive setup progress"""
    try:
        # Verify user session
        token = request.cookies.get('access_token')
        user_data = await state_manager.verify_session_token(token)
        
        async def event_generator():
            """Generate SSE events for setup progress"""
            setup_id = f"drive_setup_{user_data['auth_id']}"
            
            while True:
                # Get current progress
                progress = await drive_service.get_setup_progress(setup_id)
                
                # Format SSE data
                data = {
                    "progress": progress.percentage,
                    "current_step": progress.step,
                    "folders": progress.folders,
                    "completed": progress.is_complete
                }
                
                # Send event
                yield f"data: {json.dumps(data)}\n\n"
                
                # Check for completion
                if progress.is_complete:
                    break
                    
                await asyncio.sleep(1)
        
        return EventSourceResponse(event_generator())
        
    except Exception as e:
        logger.error(f"Progress monitoring failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Error Handling Patterns

### Error Types
```python
class DriveError(Exception):
    """Base class for drive errors"""
    def __init__(self, message: str, error_code: str, details: Dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class FolderCreationError(DriveError):
    """Error during folder creation"""
    pass

class PermissionError(DriveError):
    """Error during permission setup"""
    pass

class QuotaExceededError(DriveError):
    """Google Drive quota exceeded"""
    pass
```

### Error Handling Implementation
```python
class DriveErrorHandler:
    """Handle drive-related errors"""
    
    @staticmethod
    async def handle_error(error: Exception) -> Dict:
        """Process and format error response"""
        if isinstance(error, DriveError):
            return {
                "success": False,
                "error": {
                    "code": error.error_code,
                    "message": error.message,
                    "details": error.details
                }
            }
        
        # Handle unexpected errors
        logger.error(f"Unexpected drive error: {str(error)}")
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    
    @staticmethod
    async def handle_quota_error(error: QuotaExceededError) -> Dict:
        """Handle quota exceeded errors"""
        await state_manager.record_quota_incident(error.details)
        return {
            "success": False,
            "error": {
                "code": "QUOTA_EXCEEDED",
                "message": "Drive quota exceeded",
                "retry_after": 3600  # Suggest retry after 1 hour
            }
        }
```

### Frontend Error Handling
```javascript
// Error handling in Alpine.js store
Alpine.store('driveState', {
    // ... other store properties ...
    
    async handleError(context, error) {
        const errorData = {
            context,
            timestamp: new Date().toISOString(),
            message: error.message
        };
        
        // Add error to state
        this.setup.errors.push(errorData);
        
        // Log error
        console.error('Drive setup error:', errorData);
        
        // Handle specific error types
        if (error.code === 'QUOTA_EXCEEDED') {
            await this.handleQuotaError(error);
        }
        
        // Emit error event
        window.dispatchEvent(new CustomEvent('drive-error', {
            detail: errorData
        }));
    },
    
    async handleQuotaError(error) {
        // Show quota error UI
        this.setup.currentStep = 'quota_exceeded';
        
        // Schedule retry
        if (error.retry_after) {
            setTimeout(() => {
                this.retrySetup();
            }, error.retry_after * 1000);
        }
    }
});
```