# TenFold Authentication State Documentation

## Overview
The AUTH state implements Google authentication flow, transitioning users from VISITOR to AUTH state. It uses:
- Supabase for user management and persistence
- JWT tokens for session management
- Alpine.js for state management and UI updates

## Core Components

### AuthService
```python
class AuthService:
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        self.supabase = get_supabase_client()
        
    async def verify_google_token(self, token: str) -> AuthResult:
        """Verify Google token and create/update user"""
        
    async def verify_session_token(self, token: str) -> Optional[Dict]:
        """Verify session token with timing validation"""
        
    def create_session_token(self, user_info: Dict) -> str:
        """Create JWT session token with proper timestamps"""
```

## Token Management

### Session Tokens
- Uses JWT tokens with proper timestamp handling
- Token fields:
  ```python
  {
    'auth_id': 'google_user_id',
    'email': 'user@email.com',
    'exp': current_time + (7 * 24 * 60 * 60),  # 7 days
    'iat': current_time,  # Issue time
    'nbf': current_time   # Not before time
  }
  ```
- Stored in HTTP-only cookies
- 7-day expiration
- Timing validation with 5-minute leeway

### Error Handling
```python
try:
    decoded = jwt.decode(
        token,
        self.jwt_secret,
        algorithms=['HS256'],
        leeway=300  # 5 minutes leeway
    )
except jwt.ExpiredSignatureError:
    logger.error("Token has expired")
    return None
except jwt.InvalidTokenError as e:
    logger.error(f"Invalid token: {str(e)}")
    return None
```

## User Management

### Supabase Integration
```python
# User data structure
user_data = {
    'auth_id': 'google_user_id',
    'email': 'user@email.com',
    'name': 'User Name',
    'current_state': 'AUTH',
    'state_metadata': {
        'user': {
            'auth_id': 'google_user_id',
            'email': 'user@email.com',
            'picture': 'profile_url'
        },
        'last_login': 'iso_timestamp',
        'allowed_transitions': ['PAYMENT']
    },
    'updated_at': 'iso_timestamp'
}

# Upsert with conflict handling
response = supabase.table('users').upsert(
    user_data,
    on_conflict='email'
).execute()
```

## API Endpoints

### auth_routes.py
```python
@router.post("/google/signin")
async def google_signin(request: Request, signin_data: GoogleSignInRequest):
    """Handle Google Sign-In token verification"""

@router.get("/verify")
async def verify_session(request: Request):
    """Verify current session token"""

@router.get("/requirements")
async def get_state_requirements():
    """Get AUTH state requirements"""
```

## State Transitions

### VISITOR to AUTH
1. User clicks Google Sign-In button
2. Frontend receives Google token
3. Token sent to backend for verification
4. Backend verifies with Google
5. User created/updated in Supabase
6. JWT session token created
7. Token stored in HTTP-only cookie
8. State transition triggered

## Security Considerations

### Token Security
- HTTP-only cookies prevent XSS
- Proper timestamp validation
- 5-minute leeway for clock skew
- 7-day expiration
- Secure and SameSite cookie attributes

### User Data
- Email verification through Google
- Unique auth_id from Google
- Conflict resolution on email
- State transition validation

## Error Handling

### Common Scenarios
1. Invalid/expired Google token
2. Invalid/expired session token
3. User not found in database
4. Token timing issues
5. Database conflicts

### Implementation
```python
class AuthResult(BaseModel):
    success: bool
    user_info: Optional[Dict] = None
    session_token: Optional[str] = None
    error_message: Optional[str] = None
```

## Monitoring

### Logging
```python
logger.info("Token timing details:",
    f"Current time (UTC): {current_time}\n"
    f"Token iat: {decoded.get('iat')} (diff: {current_time - decoded.get('iat', 0)} seconds)\n"
    f"Token nbf: {decoded.get('nbf')} (diff: {current_time - decoded.get('nbf', 0)} seconds)\n"
    f"Token exp: {decoded.get('exp')} (diff: {decoded.get('exp', 0) - current_time} seconds remaining)"
)
```

### Key Metrics
- Token validation success/failure rates
- Timing validation issues
- Database operation success rates
- State transition success rates

## State Management

### Store Integration
```javascript
// AUTH state in Alpine.js store
Alpine.store('state', {
    current_state: 'AUTH',
    state_metadata: {
        user: {
            email: 'user@email.com',
            auth_id: 'google_user_id',
            name: 'User Name',
            picture: 'profile_url'
        },
        auth: {
            provider: 'google',
            last_login: new Date().toISOString(),
            session_token: 'jwt_token'
        }
    }
});

// Handle auth completion
async function handleAuthSuccess(googleUser) {
    await Alpine.store('state').transitionState('AUTH', {
        user: {
            email: googleUser.email,
            auth_id: googleUser.id,
            name: googleUser.name,
            picture: googleUser.picture
        },
        auth: {
            provider: 'google',
            last_login: new Date().toISOString()
        }
    });
}
```

### State Events
```javascript
// Listen for auth state changes
window.addEventListener('state-change', (event) => {
    const { current_state, state_metadata } = event.detail;
    if (current_state === 'AUTH') {
        updateAuthUI(state_metadata);
    }
});

// Listen for auth transitions
window.addEventListener('state-transition', (event) => {
    const { from, to, metadata } = event.detail;
    if (to === 'AUTH') {
        handleAuthTransition(from, metadata);
    }
});
```

## Frontend Implementation

### Google Sign-In Handler
```javascript
// Critical: Request body must use 'token' field, not 'credential'
function handleCredentialResponse(response) {
    if (response.credential) {
        fetch('/api/state/auth/google/signin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token: response.credential  // MUST be 'token', not 'credential'
            })
        })
        .then(async response => {
            const data = await response.json();
            if (data.success) {
                // Critical: Must sync after auth to get updated state
                await Alpine.store('state').sync();
                
                // Dispatch state transition event
                window.dispatchEvent(new CustomEvent('state-transition', {
                    detail: {
                        from: 'VISITOR',
                        to: 'AUTH'
                    }
                }));
            }
        });
    }
}
```

### UI State Binding
```html
<!-- State-Aware User Component -->
<div class="flex items-center gap-3" 
     x-data 
     x-init="$watch('$store.state.current_state', value => console.log('State changed:', value))">
    
    <!-- Google Sign-In Button -->
    <div x-show="$store.state.current_state === 'VISITOR'" 
         x-transition
         x-cloak>
        <!-- Google Sign-In Container -->
        <div id="g_id_onload" 
             data-client_id="{{ google_client_id }}"
             data-callback="handleCredentialResponse">
        </div>
    </div>

    <!-- User Avatar -->
    <div x-show="$store.state.current_state !== 'VISITOR'" 
         x-transition
         x-cloak
         class="flex items-center gap-2">
        <span x-text="$store.state.state_metadata.user?.email"></span>
        <!-- Avatar circle with initial -->
        <div class="h-9 w-9 rounded-full bg-primary flex items-center justify-center">
            <span x-text="$store.state.state_metadata.user?.email?.[0].toUpperCase()">
            </span>
        </div>
    </div>
</div>
```

### Common Issues and Solutions

1. **422 Unprocessable Entity Error**
   - Cause: Wrong field name in request body
   - Solution: Use `token` instead of `credential` in request body

2. **UI Not Updating After Auth**
   - Cause: Missing state sync after auth
   - Solution: Call `Alpine.store('state').sync()` after successful auth

3. **State Persistence**
   - Flow: Auth → DB Update → SSE Update → UI Refresh
   - Critical: Wait for sync completion before UI updates

4. **Debug Checklist**
   ```javascript
   // Add these logs for troubleshooting
   console.log('Pre-sync state:', Alpine.store('state').current_state);
   await Alpine.store('state').sync();
   console.log('Post-sync state:', Alpine.store('state').current_state);
   ```

### Required Response Format
```javascript
// Server response structure
{
    success: true,
    message: "Successfully authenticated"
}

// State update via SSE
{
    type: "state_update",
    state: {
        current_state: "AUTH",
        state_metadata: {
            user: {
                email: "user@email.com",
                auth_id: "google_user_id",
                name: "User Name",
                picture: "profile_url"
            },
            allowed_transitions: ["PAYMENT"]
        }
    }
}
```