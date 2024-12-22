# TenFold Payment State Documentation

## Overview
The PAYMENT state manages subscription and billing processes, handling the transition from authenticated user to paying customer. It integrates with Stripe for payment processing and supports both trial and paid subscriptions.

## Directory Structure
```
src/api/state/payment/
├── __init__.py
├── payment_routes.py      # API routes and handlers
├── payment_service.py     # Business logic
├── stripe_service.py      # Stripe integration
└── templates/
    ├── payment_success_box.html      # Success state UI
    └── components/
        └── plan_selector.html        # Plan selection UI
```

## State Management

### Payment State Pattern
```python
# Default payment state
default_payment_state = {
    "current_state": "PAYMENT",
    "state_metadata": {
        "allowed_transitions": ["DRIVE", "AUTH"],
        "payment": {
            "status": "pending",
            "plan": None,
            "subscription_id": None
        }
    }
}

# Active payment state
active_payment_state = {
    "current_state": "PAYMENT",
    "state_metadata": {
        "allowed_transitions": ["DRIVE"],
        "payment": {
            "status": "completed",
            "plan_name": "trial|standard|pro",
            "session_id": "session_id",
            "payment_complete": True,
            "user": {
                "email": "user@email.com"
            }
        }
    }
}
```

## Payment Flow Implementation

### 1. Checkout Process
```python
@router.post("/checkout")
async def create_checkout_session(
    request: Request,
    plan_name: str = Form(...),
    price_id: str = Form(...),
    mode: str = Form(...)
):
    """Create Stripe checkout session"""
    # Verify authentication
    token = request.cookies.get('access_token')
    user_data = await state_manager.verify_session_token(token)
    
    # Create checkout session
    session = await payment_service.create_checkout_session(
        user_id=user_data['auth_id'],
        plan_name=plan_name,
        price_id=price_id,
        mode=mode
    )
    
    # Handle trial/mock sessions
    if mode == "trial" or session.get("id", "").startswith("mock_session_"):
        return {
            "success": True,
            "data": {
                "id": session["id"],
                "url": "/api/state/payment/success"
            }
        }
```

### 2. Success Handling
```python
@router.get("/success")
async def payment_success(request: Request):
    """Redirect to home with payment success state"""
    return RedirectResponse(
        url=f"/?payment_success=true&session_id={session_id}",
        status_code=303
    )
```

### 3. Frontend Integration
```html
<!-- Payment Success Box -->
<div x-show="$store.state.current_state === 'PAYMENT'"
     x-transition:enter="transition ease-out duration-300"
     x-transition:enter-start="opacity-0 transform scale-95"
     x-transition:enter-end="opacity-100 transform scale-100">
    {% include "payment_success_box.html" %}
</div>

<!-- Payment Form -->
<form hx-post="/api/state/payment/checkout" 
      hx-trigger="submit"
      hx-ext="json-enc"
      class="mt-6">
    <input type="hidden" name="plan_name" value="standard">
    <input type="hidden" name="price_id" value="price_standard">
    <input type="hidden" name="mode" value="subscription">
    <button type="submit">Get Standard Folder</button>
</form>
```

### 4. HTMX Response Handling
```javascript
// Handle payment response and redirect
htmx.on('htmx:afterRequest', function (evt) {
    if (evt.detail.pathInfo.requestPath === '/api/state/payment/checkout') {
        const response = JSON.parse(evt.detail.xhr.response);
        if (response.success && response.data.url) {
            window.location.href = response.data.url;
        }
    }
});
```

## Plan Configuration
```python
PAYMENT_CONFIG = {
    "plans": {
        "trial": {
            "id": "trial_plan",
            "name": "Trial Folder",
            "storage_gb": 5,
            "price": "Free",
            "interval": "7 days",
            "features": [
                "Basic AI Features",
                "1 Active Folder",
                "5GB Storage",
                "7-Day Trial"
            ]
        },
        "standard": {
            "id": "price_standard",
            "name": "Standard Folder",
            "storage_gb": 25,
            "price": "$3",
            "interval": "month",
            "features": [
                "Advanced AI Features",
                "1 Active Folder",
                "25GB Storage",
                "Priority Support"
            ]
        },
        "pro": {
            "id": "price_pro",
            "name": "Pro Folder",
            "storage_gb": 100,
            "price": "$5",
            "interval": "month",
            "features": [
                "Premium AI Features",
                "1 Active Folder",
                "100GB Storage",
                "24/7 Priority Support"
            ]
        }
    }
}
```

## State Transitions

### AUTH → PAYMENT
- Triggered by plan selection
- Creates checkout session
- Updates state metadata with plan details

### PAYMENT → DRIVE
- Triggered after successful payment
- Validates payment status
- Initiates Google Drive setup

## Error Handling

### Common Scenarios
1. Authentication failures
2. Invalid plan selection
3. Session creation errors
4. State transition failures

### Implementation
```python
try:
    # Create checkout session
    session = await payment_service.create_checkout_session(...)
    if not session:
        raise HTTPException(
            status_code=500,
            detail="Failed to create checkout session"
        )
except Exception as e:
    logger.error(f"Failed to create checkout session: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))
```

## Logging

### Configuration
```python
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Set specific loggers
logger = logging.getLogger(__name__)
stripe_logger = logging.getLogger('src.api.state.payment.stripe_service')
logger.setLevel(logging.DEBUG)
stripe_logger.setLevel(logging.DEBUG)
```

### Key Events
- Checkout session creation
- Payment success/failure
- State transitions
- Error scenarios

## Security Considerations

### Authentication
- Verify access token for all requests
- Validate user session state
- Check transition permissions

### Data Protection
- Secure handling of payment data
- State validation before transitions
- Proper error message sanitization

## Development Guidelines

### Adding New Plans
1. Update plan configuration
2. Add UI components
3. Update state handling
4. Test state transitions

### Testing Checklist
- Authentication flow
- Plan selection
- Payment processing
- Success page rendering
- State transitions
- Error handling

## Stripe Integration

### Service Configuration
```python
class StripeService:
    def __init__(self, state_manager: StateManager, supabase_client: Client):
        self.stripe = stripe
        self.stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "mock_key_for_development")
        self.is_mock = self.stripe.api_key == "mock_key_for_development"
        self.state_manager = state_manager
        self.supabase = supabase_client

    async def create_checkout_session(
        self,
        user_id: str,
        plan_name: str,
        price_id: str,
        mode: str = "subscription"
    ) -> Optional[Dict]:
        """Create Stripe checkout session for subscription"""
        try:
            # Get user state and email
            state = await self.state_manager.get_current_state(user_id)
            user_email = state.get('state_metadata', {}).get('email') or \
                        state.get('state_metadata', {}).get('user', {}).get('email')

            # For trial or mock mode, create a mock session
            if mode == "trial" or self.is_mock:
                return self._create_mock_session(user_id, user_email, plan_name)

            # Create real Stripe checkout session
            session = stripe.checkout.Session.create(
                customer_email=user_email,
                success_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/state/payment/success?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name.lower().replace(' ', '_')}",
                cancel_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/",
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                metadata={
                    "user_id": str(user_id),
                    "plan_name": plan_name,
                    "user_email": user_email
                }
            )
            
            # Update state with session info
            await self._update_payment_state(user_id, session, plan_name)
            return session

        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            return None

    def _create_mock_session(self, user_id: str, user_email: str, plan_name: str) -> Dict:
        """Create mock session for development/trial"""
        session_id = f"mock_session_{user_id}"
        return {
            "id": session_id,
            "url": "/api/state/payment/success",
            "metadata": {
                "user_id": user_id,
                "plan_name": plan_name,
                "user_email": user_email
            }
        }

    async def _update_payment_state(self, user_id: str, session: Dict, plan_name: str) -> None:
        """Update state with payment session info"""
        state_data = {
            'session_id': session["id"],
            'plan_name': plan_name,
            'mode': 'subscription',
            'status': 'pending',
            'stripe_session': {
                'id': session["id"],
                'url': session["url"]
            }
        }
        await self.state_manager.transition_user_state(
            user_id,
            'PAYMENT',
            state_data,
            "Started Stripe checkout session"
        )
```

### Environment Configuration
```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...        # Test key for development
STRIPE_PUBLIC_KEY=pk_test_...        # Public key for client-side
STRIPE_WEBHOOK_SECRET=whsec_...      # Webhook signing secret

# App Configuration
APP_URL=http://localhost:8000        # Base URL for redirects
```

### Webhook Handling
```python
@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        # Get webhook signature
        signature = request.headers.get('stripe-signature')
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        # Verify webhook
        payload = await request.body()
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
        
        # Handle specific events
        if event.type == 'checkout.session.completed':
            session = event.data.object
            await handle_successful_payment(session)
        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            await handle_subscription_update(subscription)
            
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

async def handle_successful_payment(session: Dict):
    """Handle successful payment completion"""
    try:
        user_id = session.metadata.get('user_id')
        plan_name = session.metadata.get('plan_name')
        
        # Update user state
        await state_manager.transition_user_state(
            user_id,
            'PAYMENT',
            {
                'status': 'completed',
                'payment_complete': True,
                'plan_name': plan_name,
                'session_id': session.id,
                'subscription_id': session.subscription
            },
            "Payment completed successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to handle payment success: {e}")
```

### Client-Side Integration
```javascript
// Initialize Stripe
const stripe = Stripe('pk_test_...');  // Your publishable key

// Handle real payment (non-trial/mock)
async function handlePayment(priceId, planName) {
    try {
        const response = await fetch('/api/state/payment/checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                price_id: priceId,
                plan_name: planName,
                mode: 'subscription'
            })
        });
        
        const session = await response.json();
        if (session.success) {
            if (session.data.url.startsWith('/')) {
                // Mock/trial session - direct redirect
                window.location.href = session.data.url;
            } else {
                // Real Stripe session - redirect to Stripe
                await stripe.redirectToCheckout({
                    sessionId: session.data.id
                });
            }
        }
    } catch (error) {
        console.error('Payment failed:', error);
    }
}
```

## Critical Implementation Details

### Payment Success Flow
```python
# IMPORTANT: Payment success MUST redirect to home page, not render a standalone page
@router.get("/success")
async def payment_success(request: Request):
    """Redirect to home with payment success state"""
    return RedirectResponse(
        url=f"/?payment_success=true&session_id={session_id}",
        status_code=303
    )
```

### Frontend Integration Points
1. Payment forms in `home.html`:
```html
<form hx-post="/api/state/payment/checkout" 
      hx-headers='{"Authorization": "Bearer ${localStorage.getItem("access_token")}"}'
      hx-include="[name='csrf_token']"
      hx-trigger="submit"
      hx-swap="none">
    <!-- Plan-specific inputs -->
</form>
```

2. Success box inclusion in `home.html`:
```html
<div x-show="$store.state.current_state === 'PAYMENT'">
    {% include "payment_success_box.html" %}
</div>
```

### Key Requirements
1. Authentication headers MUST be included in payment forms
2. Success page MUST redirect to home, not standalone
3. Payment success box shows in main layout
4. State transitions happen before redirect

### Common Gotchas
- Missing auth headers in HTMX requests
- Trying to render success as standalone page
- Not including CSRF tokens
- Double session_id in URLs

### Testing Flow
1. Start payment -> Check auth headers
2. Complete payment -> Verify redirect to home
3. Verify success box appears in main layout
4. Check state transition completed