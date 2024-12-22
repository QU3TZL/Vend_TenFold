# TenFold Active State Documentation

## Overview
The ACTIVE state represents the main operational state where users interact with their configured workspace. This state manages ongoing folder operations, user settings, and subscription maintenance.

## Directory Structure
```
src/api/state/05_active/
├── __init__.py
├── active_routes.py
├── active_service.py
├── active_models.py
├── workspace_service.py
└── templates/
    ├── dashboard.html
    ├── components/
    │   ├── folder_browser.html
    │   ├── user_settings.html
    │   ├── usage_stats.html
    │   └── subscription_info.html
    └── partials/
        ├── workspace_header.html
        └── workspace_footer.html
```

## Core Components

### ActiveService
```python
class ActiveService:
    def __init__(self, state_manager, workspace_service):
        self.state_manager = state_manager
        self.workspace = workspace_service
        self.allowed_transitions = ["PAYMENT"]  # Can return to payment for plan changes
        
    async def get_workspace_status(self, user_id: str) -> WorkspaceStatus:
        """Get current workspace status"""
        
    async def update_folder_access(self, folder_id: str, updates: AccessUpdates) -> AccessResult:
        """Update folder permissions"""
        
    async def monitor_usage(self, user_id: str) -> UsageMetrics:
        """Track workspace usage"""
```

### Data Models
```python
class WorkspaceStatus(BaseModel):
    user_id: str
    subscription_status: str
    storage_usage: StorageMetrics
    recent_activity: List[ActivityLog]
    folder_count: int

class AccessUpdates(BaseModel):
    folder_id: str
    user_updates: List[UserAccess]
    notification_settings: NotificationPrefs
    
class UsageMetrics(BaseModel):
    storage_used: int
    storage_limit: int
    active_users: int
    folder_count: int
    last_activity: datetime
```

## API Endpoints

### active_routes.py
```python
router = APIRouter(prefix="/api/state/active")

@router.get("/workspace")
async def get_workspace():
    """Get workspace dashboard data"""

@router.post("/folders/{folder_id}/access")
async def update_access(folder_id: str, updates: AccessUpdates):
    """Update folder access"""

@router.get("/usage")
async def get_usage_metrics():
    """Get usage statistics"""

@router.post("/settings")
async def update_settings(settings: UserSettings):
    """Update user settings"""

@router.post("/transition/payment")
async def transition_to_payment():
    """Handle payment state transition (for plan changes)"""
```

## UI Components

### Dashboard Structure
```html
<!-- dashboard.html -->
{% extends "base.html" %}

{% block content %}
<div class="dashboard-container"
     x-data="{ activeTab: 'folders' }">
    {% include "components/workspace_nav.html" %}
    {% include "components/folder_browser.html" %}
    {% include "components/usage_stats.html" %}
    
    <div class="workspace-actions">
        <button @click="showSettings()"
                class="settings-button">
            Workspace Settings
        </button>
    </div>
</div>
{% endblock %}
```

### Folder Management
```html
<!-- components/folder_browser.html -->
<div class="folder-browser"
     x-data="{ folders: [] }"
     hx-get="/api/state/active/folders"
     hx-trigger="load">
    <template x-for="folder in folders">
        <div class="folder-item">
            <span x-text="folder.name"></span>
            <div class="folder-actions">
                <button @click="manageFolderAccess(folder.id)">
                    Manage Access
                </button>
            </div>
        </div>
    </template>
</div>
```

## Workspace Management

### Usage Monitoring
```python
class WorkspaceMonitor:
    async def track_storage_usage(self, user_id: str) -> StorageMetrics:
        """Monitor storage usage"""
        
    async def track_user_activity(self, user_id: str) -> ActivityMetrics:
        """Track user activity"""
        
    async def check_quota_limits(self, user_id: str) -> QuotaStatus:
        """Check usage against quota limits"""
```

### Access Management
```python
class AccessManager:
    async def update_user_access(self, folder_id: str, updates: List[UserAccess]) -> bool:
        """Update user access rights"""
        
    async def audit_access_changes(self, folder_id: str, changes: List[AccessChange]) -> None:
        """Log access changes"""
```

## Security Considerations

### Workspace Security
```python
class WorkspaceSecurity:
    def validate_access_request(self, user_id: str, folder_id: str) -> bool:
        """Validate access request"""
    
    def enforce_quota_limits(self, user_id: str) -> bool:
        """Enforce usage quotas"""
```

### Activity Monitoring
```python
class ActivityMonitor:
    async def log_activity(self, user_id: str, activity: ActivityData) -> None:
        """Log user activity"""
    
    async def detect_suspicious_activity(self, activity: ActivityData) -> bool:
        """Detect unusual patterns"""
```

## Testing Strategy

### Unit Tests
```python
async def test_folder_operations():
    """Test folder management"""

async def test_access_control():
    """Test access management"""

async def test_usage_monitoring():
    """Test usage tracking"""
```

### Integration Tests
```python
async def test_workspace_flow():
    """Test workspace operations"""

async def test_quota_enforcement():
    """Test quota management"""
```

## Development Guidelines

### Adding Features
1. Define feature requirements
2. Implement access controls
3. Add usage tracking
4. Update UI components

### Performance Optimization
1. Implement caching
2. Optimize queries
3. Batch operations
4. Monitor metrics

## Configuration

### Environment Variables
```
WORKSPACE_QUOTA_LIMIT=...
ACTIVITY_LOG_RETENTION=...
MONITORING_INTERVAL=...
ALERT_THRESHOLD=...
```

### Workspace Configuration
```python
WORKSPACE_CONFIG = {
    "quotas": {
        "basic": {
            "storage": "10GB",
            "users": 5,
            "folders": 100
        },
        "pro": {
            "storage": "100GB",
            "users": 25,
            "folders": 500
        }
    },
    "monitoring": {
        "check_interval": 300,  # 5 minutes
        "alert_threshold": 0.9  # 90% of quota
    }
}
```

## Monitoring

### Key Metrics
- Active users
- Storage utilization
- Access patterns
- Error rates

### Logging
```python
logger.info("Workspace event", extra={
    "user_id": user_id,
    "event_type": "folder_access",
    "resource_id": folder_id,
    "timestamp": datetime.now()
})
```

## Error Handling

### Common Scenarios
1. Quota exceeded
2. Access denied
3. Resource conflicts
4. API rate limits

### Implementation
```python
async def handle_workspace_error(
    error_type: str,
    error_data: Dict
) -> Response:
    """Handle workspace operation errors"""
``` 