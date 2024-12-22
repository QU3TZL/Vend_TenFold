// TenFold Debug Tools
window.__TENFOLD_DEBUG__ = {
    stateHistory: [],
    initialized: false,

    // Initialize debug tools
    init() {
        if (this.initialized) return;
        this.initialized = true;

        console.log('🔧 TenFold Debug Tools Initialized');
        this.attachStateWatcher();
        this.showDebugCommands();
    },

    // Watch for state changes
    attachStateWatcher() {
        if (window.Alpine) {
            Alpine.effect(() => {
                const state = Alpine.store('state');
                if (state && state.current_state) {
                    this.logStateChange(state.current_state);
                }
            });
        }
    },

    // Log state changes with metadata
    logStateChange(newState) {
        const timestamp = new Date();
        const state = Alpine.store('state');
        const metadata = state ? (state.state_metadata || {}) : {};

        // Don't log duplicate states
        const lastEntry = this.stateHistory[this.stateHistory.length - 1];
        if (lastEntry &&
            lastEntry.state === newState &&
            JSON.stringify(lastEntry.metadata) === JSON.stringify(metadata)) {
            return;
        }

        const stateChange = {
            timestamp,
            state: newState,
            metadata
        };

        this.stateHistory.push(stateChange);
        console.log(`🔄 State Change [${newState}]`, metadata);
    },

    showDebugCommands() {
        console.log(`
🔧 TenFold Debug Commands:
- __TENFOLD_DEBUG__.api.getCurrentState()
- __TENFOLD_DEBUG__.api.getStateHistory()
- __TENFOLD_DEBUG__.api.getMetadata()
- __TENFOLD_DEBUG__.api.simulateState(state, metadata)
- __TENFOLD_DEBUG__.api.verifyUI()
        `);
    },

    // Debug API
    api: {
        getCurrentState() {
            return Alpine.store('state').current_state;
        },

        getStateHistory() {
            return window.__TENFOLD_DEBUG__.stateHistory;
        },

        getMetadata() {
            return Alpine.store('state').state_metadata;
        },

        async simulateState(state, metadata = {}) {
            try {
                const response = await fetch('/api/state/debug/simulate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ state, metadata })
                });

                if (!response.ok) throw new Error('State simulation failed');

                const result = await response.json();
                console.log('🔧 State Simulation Result:', result);
                return result;
            } catch (error) {
                console.error('🔧 State Simulation Error:', error);
                throw error;
            }
        },

        verifyUI() {
            const state = this.getCurrentState();
            const expectedUI = window.__TENFOLD_DEBUG__.UI_STATES[state];

            if (!expectedUI) {
                console.error(`🔧 No UI configuration found for state: ${state}`);
                return;
            }

            const results = {
                visible: [],
                hidden: [],
                content: []
            };

            // Check visible components
            expectedUI.visible_components.forEach(id => {
                const element = document.getElementById(id);
                results.visible.push({
                    id,
                    expected: true,
                    actual: !!(element && element.style.display !== 'none')
                });
            });

            // Check hidden components
            expectedUI.hidden_components.forEach(id => {
                const element = document.getElementById(id);
                results.hidden.push({
                    id,
                    expected: false,
                    actual: !element || element.style.display === 'none'
                });
            });

            console.table(results.visible, ['id', 'expected', 'actual']);
            console.table(results.hidden, ['id', 'expected', 'actual']);

            return results;
        }
    },

    state: {
        async syncWithDB() {
            try {
                const response = await fetch('/api/state', {
                    headers: {
                        'Authorization': 'Bearer ' + localStorage.getItem('access_token')
                    }
                });
                const data = await response.json();

                // Use consistent updateState pattern
                Alpine.store('state').updateState(
                    data.current_state,
                    data.state_metadata
                );

                console.log('State synced:', {
                    current_state: data.current_state,
                    state_metadata: data.state_metadata
                });

                return data;
            } catch (error) {
                console.error('State sync failed:', error);
                return null;
            }
        },

        async verifyStateSync() {
            const dbState = await this.syncWithDB();
            const uiState = Alpine.store('state').current_state;

            console.log('State Verification:', {
                database: dbState?.current_state,
                ui: uiState,
                inSync: dbState?.current_state === uiState
            });
        }
    }
};

// Initialize on load
document.addEventListener('alpine:init', () => {
    window.__TENFOLD_DEBUG__.init();
}); 