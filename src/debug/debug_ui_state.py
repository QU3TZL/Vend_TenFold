import os
import sys
import asyncio
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager

class UIStateDebugger:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.state_manager = StateManager()
        
        # Define expected UI states and their components
        self.UI_STATES = {
            'VISITOR': {
                'visible_components': ['login-button', 'hero-section'],
                'hidden_components': ['workspace', 'payment-form', 'drive-connect', 'folder-view'],
                'expected_content': {
                    'header': 'Welcome to TenFold',
                    'cta': 'Sign in to get started'
                }
            },
            'AUTH': {
                'visible_components': ['payment-form', 'user-profile'],
                'hidden_components': ['login-button', 'drive-connect', 'folder-view'],
                'expected_content': {
                    'header': 'Choose Your Plan',
                    'user_email': True  # Should show user email
                }
            },
            'PAYMENT': {
                'visible_components': ['drive-connect', 'subscription-details'],
                'hidden_components': ['payment-form', 'folder-view'],
                'expected_content': {
                    'header': 'Connect Your Drive',
                    'plan_details': True
                }
            },
            'DRIVE': {
                'visible_components': ['folder-setup', 'drive-status'],
                'hidden_components': ['drive-connect', 'folder-view'],
                'expected_content': {
                    'header': 'Setting Up Your Workspace',
                    'drive_status': True
                }
            },
            'ACTIVE': {
                'visible_components': ['folder-view', 'workspace-controls'],
                'hidden_components': ['folder-setup'],
                'expected_content': {
                    'header': 'Your Workspace',
                    'folder_details': True
                }
            }
        }

    async def verify_ui_state(self, user_id: str):
        """Verify current state matches expected UI configuration"""
        current = await self.state_manager.get_current_state(user_id)
        current_state = current.get('current_state', 'VISITOR')
        
        expected_ui = self.UI_STATES[current_state]
        
        print(f"\nVerifying UI State for: {current_state}")
        print("Expected Visible Components:", expected_ui['visible_components'])
        print("Expected Hidden Components:", expected_ui['hidden_components'])
        print("Expected Content:", expected_ui['expected_content'])
        
        return {
            'state': current_state,
            'ui_config': expected_ui,
            'state_metadata': current.get('state_metadata', {})
        }

    async def simulate_state_change(self, user_id: str, target_state: str, state_data: dict):
        """Simulate state change and verify UI updates"""
        print(f"\nSimulating transition to {target_state}")
        
        # Perform state transition
        success, result = await self.state_manager.transition_user_state(
            user_id=user_id,
            target_state=target_state,
            state_data=state_data,
            reason=f'UI Debug: Testing {target_state} state'
        )
        
        if success:
            # Verify UI state after transition
            ui_state = await self.verify_ui_state(user_id)
            print("\nState Transition Success!")
            print(f"New State: {ui_state['state']}")
            print("UI Should Update To Show:")
            print(json.dumps(ui_state['ui_config'], indent=2))
        else:
            print(f"State Transition Failed: {result}")

async def test_ui_states():
    debugger = UIStateDebugger()
    supabase = get_supabase_client()
    
    # Get test user
    response = supabase.table('users').select('*').limit(1).execute()
    if not response.data:
        print("No users found for testing!")
        return
        
    user = response.data[0]
    user_id = user['auth_id']
    
    print(f"Testing UI states for user: {user['email']}")
    
    # Test initial state
    await debugger.verify_ui_state(user_id)
    
    # Test each state transition
    test_states = [
        ('AUTH', {
            'state_metadata': {
                'email': user['email'],
                'auth_id': user['auth_id']
            }
        }),
        ('PAYMENT', {
            'state_metadata': {
                'plan_id': 'trial',
                'session_id': f'trial_session_{user_id}',
                'status': 'completed'
            }
        }),
        ('DRIVE', {
            'state_metadata': {
                'drive_access_token': 'test_token',
                'drive_refresh_token': 'test_refresh',
                'drive_auth_status': 'connected'
            }
        }),
        ('ACTIVE', {
            'state_metadata': {
                'folder_id': 'test_folder_id',
                'workspace_status': {
                    'deployment_status': 'completed'
                }
            }
        })
    ]
    
    for state, data in test_states:
        await debugger.simulate_state_change(user_id, state, data)
        await asyncio.sleep(1)  # Pause between transitions

if __name__ == "__main__":
    asyncio.run(test_ui_states()) 