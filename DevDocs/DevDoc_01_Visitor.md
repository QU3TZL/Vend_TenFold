# TenFold Visitor State Documentation

## Overview
The VISITOR state represents the initial entry point for all users. It handles the landing page experience, feature showcase, and transition to authentication.

## Directory Structure
```
src/api/state/01_visitor/
├── __init__.py
├── visitor_routes.py
├── visitor_service.py
├── visitor_models.py
└── templates/
    ├── landing.html
    ├── components/
    │   ├── feature_showcase.html
    │   ├── pricing_cards.html
    │   └── cta_section.html
    └── partials/
        ├── header.html
        └── footer.html
```

## Core Components

### VisitorService
```python
class VisitorService:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.allowed_transitions = ["AUTH"]
        
    async def track_visitor(self, visitor_data: Dict):
        """Track visitor analytics"""
        
    async def get_feature_list(self) -> List[Feature]:
        """Return feature showcase data"""
        
    async def get_pricing_plans(self) -> List[PricingPlan]:
        """Return pricing plans"""
```

### Data Models
```python
class VisitorAnalytics(BaseModel):
    visitor_id: str
    entry_timestamp: datetime
    referrer: Optional[str]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]

class Feature(BaseModel):
    title: str
    description: str
    icon: str
    benefits: List[str]

class PricingPlan(BaseModel):
    name: str
    price: float
    interval: str
    features: List[str]
```

## API Endpoints

### visitor_routes.py
```python
router = APIRouter(prefix="/api/state/visitor")

@router.get("")
async def get_landing_page():
    """Serve landing page"""

@router.post("/track")
async def track_visitor(data: VisitorAnalytics):
    """Track visitor data"""

@router.get("/features")
async def get_features():
    """Get feature list"""

@router.get("/pricing")
async def get_pricing():
    """Get pricing plans"""

@router.post("/transition/auth")
async def transition_to_auth():
    """Handle AUTH state transition"""
```

## UI Components

### Landing Page Structure
```html
<!-- landing.html -->
{% extends "base.html" %}

{% block content %}
<div class="landing-container">
    {% include "components/hero_section.html" %}
    {% include "components/feature_showcase.html" %}
    {% include "components/pricing_cards.html" %}
    {% include "components/cta_section.html" %}
</div>
{% endblock %}
```

### Interactive Elements
```html
<!-- components/cta_section.html -->
<div x-data="{ showAuthModal: false }"
     class="cta-container">
    <button hx-post="/api/state/visitor/transition/auth"
            hx-trigger="click"
            class="cta-button">
        Get Started
    </button>
</div>
```

## State Transitions

### To AUTH State
1. User triggers auth transition
2. Validate visitor session
3. Store analytics data
4. Redirect to auth flow

```python
async def prepare_auth_transition(visitor_id: str) -> bool:
    """
    Prepare visitor for AUTH state transition
    - Store visitor analytics
    - Initialize auth session
    - Set transition flags
    """
```

## Analytics Integration

### Tracking Points
- Page load
- Feature views
- Pricing plan views
- CTA interactions
- Exit events

### Implementation
```python
class VisitorAnalytics:
    async def track_event(
        self,
        visitor_id: str,
        event_type: str,
        metadata: Dict
    ):
        """Track visitor events"""
```

## Security Considerations

### CSRF Protection
```python
@router.post("/transition/auth")
async def transition_to_auth(
    request: Request,
    csrf_token: str = Form(...)
):
    """Protected auth transition"""
```

### Rate Limiting
```python
@router.get("")
@limits(calls=100, period=60)
async def get_landing_page():
    """Rate-limited landing page"""
```

## Testing Strategy

### Unit Tests
```python
async def test_visitor_tracking():
    """Test visitor analytics tracking"""

async def test_feature_list():
    """Test feature showcase data"""

async def test_pricing_plans():
    """Test pricing plan data"""
```

### Integration Tests
```python
async def test_auth_transition():
    """Test AUTH state transition"""

async def test_analytics_flow():
    """Test analytics tracking flow"""
```

## Development Guidelines

### Adding New Features
1. Create feature component
2. Add to feature list
3. Implement tracking
4. Update tests

### UI Components
1. Follow TailwindCSS patterns
2. Implement HTMX triggers
3. Add Alpine.js state
4. Ensure mobile responsiveness

## Configuration

### Environment Variables
```
ANALYTICS_KEY=...
RATE_LIMIT_ENABLED=true
FEATURE_FLAGS=...
```

### Feature Flags
```python
VISITOR_FEATURES = {
    "show_pricing": True,
    "enable_chat": False,
    "beta_features": False
}
```

## Monitoring

### Key Metrics
- Page load time
- Bounce rate
- CTA click rate
- State transition success rate

### Logging
```python
logger.info("Visitor event", extra={
    "visitor_id": visitor_id,
    "event_type": event_type,
    "timestamp": datetime.now()
})
```

## Error Handling

### Visitor State Fallback
```python
# Always provide a safe VISITOR state
default_visitor_state = {
    "current_state": "VISITOR",
    "state_metadata": {
        "allowed_transitions": ["AUTH"]
    }
}
```

### Common Scenarios
1. New visitor (no token)
2. Invalid/expired token
3. Database query failures
4. User not found
5. State transition errors

### Implementation Pattern
```python
async def handle_visitor_state():
    try:
        # Check for token
        if not token:
            return default_visitor_state
            
        # Verify token if present
        try:
            user_data = await verify_token(token)
            if user_data:
                return await get_user_state(user_data)
        except TokenError:
            logger.warning("Token verification failed")
            
        # Fallback to VISITOR state
        return default_visitor_state
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return default_visitor_state
```

### SSE Error Handling
```python
async def state_events():
    try:
        token = get_token()
        current_state = None
        
        if token:
            try:
                user_data = await verify_token(token)
                if user_data:
                    current_state = await get_state(user_data)
            except Exception:
                logger.warning("Token verification failed")
                
        # Always fallback to VISITOR state
        if not current_state:
            current_state = default_visitor_state
            
        yield state_update(current_state)
        
    except Exception as e:
        logger.error(f"SSE error: {e}")
        yield error_response(str(e))
```

## State Management

### Store Integration
```javascript
// Initial VISITOR state
Alpine.store('state', {
    current_state: 'VISITOR',
    state_metadata: {
        user: {
            email: null,
            auth_id: null,
            name: null,
            picture: null
        },
        visitor: {
            entry_timestamp: new Date().toISOString(),
            last_action: null
        }
    }
});

// Transition to AUTH
await Alpine.store('state').transitionState('AUTH', {
    transition_reason: 'user_initiated',
    from_page: currentPage
});
```

### State Events
```javascript
// Listen for state changes
window.addEventListener('state-change', (event) => {
    const { current_state, state_metadata } = event.detail;
    updateVisitorUI(current_state, state_metadata);
});

// Listen for transitions
window.addEventListener('state-transition', (event) => {
    const { from, to, metadata } = event.detail;
    handleVisitorTransition(from, to, metadata);
});
```
