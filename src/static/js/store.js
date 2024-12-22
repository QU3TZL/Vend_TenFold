/*
STATE MANAGEMENT AND INITIALIZATION
=================================

Key Concepts:
------------
1. Single Source of Truth
   - Alpine.js store is the ONLY source of truth for frontend state
   - Server state is only used for initial hydration
   - Never mix server-side state checks with store state in templates

2. State Initialization Flow
   - Server provides initial state via window.INITIAL_STATE
   - Store initializes with window.INITIAL_STATE or defaults to VISITOR
   - Store.init() fetches latest state from /api/state endpoint
   - All state updates must go through updateState() method

3. State Updates
   - Always use updateState() to modify state
   - Updates are atomic (state + metadata updated together)
   - State changes trigger custom 'state-transition' event
   - Metadata preserves existing fields not included in update

Common Issues:
-------------
1. Component Not Showing
   - Check store initialization in console
   - Verify x-show conditions only use store state
   - Never mix server-side state checks with store state

2. State Not Updating
   - All updates must use updateState()
   - Check network requests for /api/state
   - Verify event listeners for state-transition

3. Lost Metadata
   - Always spread existing metadata in updates
   - Check allowed_transitions preservation
   - Log state updates to verify metadata

4. Initialization Race Conditions
   - Store init happens after Alpine init
   - Components should handle loading state
   - Use x-cloak to prevent flash of content
*/

// TenFold State Management
document.addEventListener('alpine:init', () => {
    // Get initial state from server
    const initialState = window.INITIAL_STATE || {
        current_state: 'VISITOR',
        state_metadata: {
            allowed_transitions: ['AUTH']
        },
        loading: false,
        error: null
    };

    console.log('Creating store with initial state:', initialState);

    Alpine.store('state', {
        current_state: initialState.current_state,
        state_metadata: initialState.state_metadata,
        loading: initialState.loading,
        error: initialState.error,

        async init() {
            console.log('Store init with state:', this.current_state);
            const response = await fetch('/api/state', {
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                console.log('State API response:', data);
                if (data.success) {
                    this.updateState(data.data.current_state, data.data.state_metadata);
                }
            }
        },

        // Single source of truth for state updates
        updateState(state, metadata = {}) {
            console.log('Updating state:', { state, metadata });
            const oldState = this.current_state;

            // Update state and metadata atomically
            this.current_state = state;
            this.state_metadata = {
                ...this.state_metadata,
                ...metadata,
                allowed_transitions: metadata.allowed_transitions || this.state_metadata.allowed_transitions
            };

            // Dispatch state change event
            window.dispatchEvent(new CustomEvent('state-transition', {
                detail: {
                    from: oldState,
                    to: state,
                    metadata: this.state_metadata
                }
            }));

            // Log state change
            console.log('State updated:', {
                from: oldState,
                to: state,
                metadata: this.state_metadata
            });
        },

        // Keep existing methods but use updateState internally
        async refreshState() {
            await this.init();
        },

        updateFromDB(data) {
            if (data.current_state || data.state_metadata) {
                this.updateState(
                    data.current_state || this.current_state,
                    data.state_metadata || this.state_metadata
                );
            }
        }
    });

    // Initialize state after store creation
    Alpine.store('state').init();
});

// Handle payment request
htmx.on('htmx:configRequest', function (evt) {
    if (evt.detail.path === '/api/state/payment/checkout') {
        console.log('=== PAYMENT REQUEST CONFIG ===');
        // Use credentials instead of localStorage token
        evt.detail.headers['X-HTMX-Request'] = 'true';
        // Include credentials in the request
        evt.detail.xhr.withCredentials = true;
        console.log('1. Request Headers:', evt.detail.headers);
    }
});

// Handle payment response and redirect
htmx.on('htmx:afterRequest', function (evt) {
    if (evt.detail.pathInfo.requestPath === '/api/state/payment/checkout') {
        console.log('=== PAYMENT RESPONSE DEBUG ===');
        console.log('2. Response Status:', evt.detail.xhr.status);

        if (evt.detail.xhr.status === 401) {
            console.error('Authentication failed');
            return;
        }

        try {
            const response = JSON.parse(evt.detail.xhr.response);
            console.log('3. Parsed Response:', response);

            if (response.success && response.data.url) {
                console.log('4. Current Window Location:', {
                    href: window.location.href,
                    pathname: window.location.pathname,
                    origin: window.location.origin
                });

                if (response.data.url.startsWith('/api')) {
                    const fullUrl = response.data.url +
                        (response.data.url.includes('?') ? '&' : '?') +
                        'session_id=' + response.data.id;

                    console.log('5. Redirect Attempt:', {
                        originalUrl: response.data.url,
                        fullUrl: fullUrl,
                        sessionId: response.data.id
                    });

                    try {
                        console.log('6. Starting Redirect...');
                        window.location.replace(fullUrl);
                        console.log('7. Redirect Initiated');
                    } catch (redirectError) {
                        console.error('8. Redirect Failed:', redirectError);
                    }
                } else {
                    console.log('5. Stripe Redirect:', response.data.url);
                    window.location.href = response.data.url;
                }
            } else {
                console.error('4. Invalid Response Structure:', response);
            }
        } catch (parseError) {
            console.error('3. Parse Failed:', parseError);
        }
    }
});

// Update the Google Sign-In configuration
function handleCredentialResponse(response) {
    console.log("Google Sign-In callback received", {
        hasCredential: !!response.credential,
        responseData: response
    });

    if (response.credential) {
        const requestData = {
            token: response.credential
        };

        console.log("Sending auth request with data:", JSON.stringify(requestData, null, 2));

        fetch('/api/state/auth/google/signin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
            .then(async response => {
                const text = await response.text();
                console.log('Raw response text:', text);

                const data = text ? JSON.parse(text) : {};
                console.log('Auth response:', {
                    status: response.status,
                    ok: response.ok,
                    data: data
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}, details: ${text}`);
                }
                return data;
            })
            .then(async data => {
                console.log('Auth successful:', data);

                if (data.success) {
                    // Fetch latest state from server
                    await Alpine.store('state').init();

                    // Update local state
                    Alpine.store('state').updateState('AUTH', {
                        ...Alpine.store('state').state_metadata,
                        user: data.user,
                        allowed_transitions: ['PAYMENT']
                    });
                } else {
                    throw new Error(data.message || 'Authentication failed');
                }
            })
            .catch(error => {
                console.error('Sign-in error:', {
                    message: error.message,
                    stack: error.stack,
                    type: error.constructor.name
                });
                Alpine.store('state').error = 'Sign-in failed. Please try again.';
            });
    }
}