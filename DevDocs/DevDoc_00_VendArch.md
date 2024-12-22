# TenFold Vending Machine Architecture

## Overview
TenFold's core application is designed as a state-based vending machine that processes users through distinct states, each representing a phase in the folder acquisition journey. This document outlines the technical architecture and implementation approach.

## State Machine Design

### State Flow
```
VISITOR → AUTH → PAYMENT → DRIVE → ACTIVE
```

Each state:
- Is self-contained with its own logic
- Has clear entry/exit conditions
- Maintains its own UI components
- Validates transitions
- Syncs with Alpine.js store
- Persists in Supabase

### State Management

#### Core State Flow
```javascript
// Alpine.js store core state
{
    current_state: 'VISITOR',  // Current state
    state_metadata: {          // State-specific data
        user: {
            email: null,
            auth_id: null,
            name: null,
            picture: null
        }
    }
}
```

#### State Synchronization Flow
1. Client-side Alpine.js store maintains UI state
2. Server-Sent Events (SSE) provide real-time updates
3. State changes flow through StateManager
4. Supabase maintains persistent state
5. State history tracked in separate table

#### Error Handling Pattern
```python
try:
    # Primary operation
    result = await primary_operation()
    if result.success:
        return success_response(result)
        
except SpecificError as e:
    # Handle specific error case
    logger.warning(f"Specific error: {e}")
    return fallback_state()
    
except Exception as e:
    # Handle unexpected errors
    logger.error(f"Unexpected error: {e}")
    return safe_default_state()
```

#### State Transition Safety
1. Validate current state
2. Check required fields
3. Record transition history
4. Handle database errors gracefully
5. Maintain fallback states

#### State History Recording
```python
history_data = {
    'internal_user_id': user_id,
    'from_state': current_state,
    'to_state': target_state,
    'transition_reason': reason,
    'metadata': state_data,
    'created_at': timestamp
}
```

### Directory Structure
```
src/
├── api/
│   ├── state/                      # State management core
│   │   ├── shared/                 # Shared components
│   │   │   └── templates/
│   │   │       └── base.html       # Base template
│   │   ├── visitor/               # Landing state
│   │   ├── auth/                  # Authentication
│   │   ├── payment/               # Subscription
│   │   ├── drive/                 # Setup
│   │   └── active/                # Active usage
│   └── __init__.py                # FastAPI setup
├── database/                       # Data layer
└── services/                      # Shared services
```

Note: We use non-numbered directory names to avoid potential import path resolution issues and maintain cleaner imports. The state flow order is managed through the application logic rather than directory naming conventions.

## State Implementation

### State Module Pattern
Each state follows a consistent structure:
```
XX_statename/
├── __init__.py          # State initialization
├── state_routes.py      # FastAPI endpoints
├── state_service.py     # Business logic
└── templates/           # UI components
```

### Common Files
1. `state_routes.py`
   ```python
   router = APIRouter(prefix="/api/state/{state_name}")
   
   @router.get("")
   async def get_state_info():
       """Get current state information"""
   
   @router.post("/transition")
   async def transition_state():
       """Handle state transition"""
   ```

2. `state_service.py`
   ```python
   class StateService:
       def __init__(self, state_manager):
           self.state_manager = state_manager
           self.allowed_transitions = []
           self.required_fields = []
           
       async def validate_transition(self):
           """Validate state requirements"""
           
       async def transition_state(self):
           """Handle state transition"""
   ```

## Core Services

### StateManager
Central service managing state transitions:
```python
class StateManager:
    async def transition_user_state(
        self,
        user_id: str,
        target_state: str,
        metadata: Dict
    ) -> Tuple[bool, Dict]:
        """Handle state transition with validation"""
```

### External Service Integration
Clean wrappers for external services:
```python
class ExternalService:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        
    async def service_operation(self):
        """Handle external service interaction"""
```

## Frontend Architecture

### Template Hierarchy
```
base.html                # Core layout
├── state.html          # State template
└── components/         # State components
```

### Technologies
- HTMX: Dynamic updates
- Alpine.js: UI state
- TailwindCSS: Styling

### Component Pattern
```html
<!-- State-specific component -->
<div x-data="{ state: {} }" 
     hx-get="/api/state/{state_name}"
     hx-trigger="load">
  <!-- Component content -->
</div>
```

### State Store Pattern
```javascript
Alpine.store('state', {
    // Core state management
    async updateState(newState) {
        // Update state in database
        // Sync local store
        // Trigger events
    },

    async transitionState(newState, metadata) {
        // Handle state transition
        // Update metadata
        // Trigger transition events
    }
});
```

### Event System
```javascript
// State change events
window.dispatchEvent(new CustomEvent('state-change', {
    detail: { 
        current_state: newState,
        state_metadata: metadata
    }
}));

// State transition events
window.dispatchEvent(new CustomEvent('state-transition', {
    detail: { 
        from: oldState,
        to: newState,
        metadata: transitionMetadata
    }
}));
```

## API Structure

### Endpoint Pattern
```
/api/state/{state_name}/{action}
```

### Common Endpoints
- GET `/api/state/{state_name}` - State info
- POST `/api/state/{state_name}/transition` - State transition
- GET `/api/state/{state_name}/requirements` - State requirements

## State-Specific Implementations

### 1. VISITOR
- Landing page
- Feature showcase
- Transition to auth

### 2. AUTH
- Google OAuth
- Session management
- User profiles

### 3. PAYMENT
- Stripe integration
- Plan selection
- Trial management

### 4. DRIVE
- Google Drive setup
- Folder creation
- Permission management

### 5. ACTIVE
- Dashboard
- Folder management
- Settings

## Development Guidelines

### Adding New States
1. Create state directory structure
2. Implement required interfaces
3. Define transitions
4. Add templates
5. Register routes

### Service Integration
1. Create service wrapper
2. Define state interactions
3. Implement error handling
4. Add logging

### Template Development
1. Extend base template
2. Create state components
3. Add HTMX triggers
4. Implement Alpine.js state

## Testing Strategy

### Unit Tests
- Service methods
- State transitions
- Validation logic

### Integration Tests
- API endpoints
- State flow
- External services

### UI Tests
- Component rendering
- State transitions
- User interactions

## Deployment

### Requirements
- Python 3.9+
- FastAPI
- PostgreSQL
- Redis (optional)

### Environment Variables
```
STRIPE_SECRET_KEY=sk_...
GOOGLE_CLIENT_ID=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

### State Configuration
```python
STATE_CONFIG = {
    "VISITOR": {"next": ["AUTH"]},
    "AUTH": {"next": ["PAYMENT"]},
    "PAYMENT": {"next": ["DRIVE"]},
    "DRIVE": {"next": ["ACTIVE"]},
    "ACTIVE": {"next": []}
}
```

## Security Considerations

### State Validation
- Required fields
- Allowed transitions
- User permissions

### Authentication
- OAuth2 flow
- Session management
- Token validation

### Data Protection
- State encryption
- Secure transitions
- Audit logging 