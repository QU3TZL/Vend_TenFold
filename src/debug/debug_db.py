import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager
import json

async def inspect_schema():
    supabase = get_supabase_client()
    
    print("\nInspecting database schema...")
    
    # Get user table info
    response = supabase.table('users').select('*').limit(1).execute()
    print("\nUser table example:")
    print(json.dumps(response.data, indent=2))
    
    # Get state history info
    response = supabase.table('user_state_history').select('*').limit(1).execute()
    print("\nState history example:")
    print(json.dumps(response.data, indent=2))

async def test_state_transitions():
    supabase = get_supabase_client()
    state_manager = StateManager()
    
    # Get current user for testing
    response = supabase.table('users').select('*').limit(1).execute()
    if not response.data:
        print("No users found in database!")
        return
        
    user = response.data[0]
    user_id = user['auth_id']
    
    print(f"\nTesting state transitions for user: {user['email']}")
    print(f"Current state: {user['current_state']}")
    print(f"Current metadata: {json.dumps(user['state_metadata'], indent=2)}")
    
    # Test each state transition
    states = ['AUTH', 'PAYMENT', 'DRIVE', 'ACTIVE']
    for state in states:
        print(f"\nTesting transition to {state}...")
        
        # Prepare test data based on state requirements
        state_data = {'state_metadata': {}}
        if state == 'AUTH':
            state_data['state_metadata'].update({
                'email': user['email'],
                'auth_id': user['auth_id']
            })
        elif state == 'PAYMENT':
            state_data['state_metadata'].update({
                'plan_id': 'trial',
                'session_id': f'trial_session_{user_id}',
                'status': 'completed'
            })
        elif state == 'DRIVE':
            state_data = {
                'state_metadata': {
                    'drive_access_token': 'test_access_token',
                    'drive_refresh_token': 'test_refresh_token',
                    'drive_auth_status': 'connected'
                },
                'drive_access_token': 'test_access_token',
                'drive_refresh_token': 'test_refresh_token',
                'drive_auth_status': 'connected'
            }
        elif state == 'ACTIVE':
            state_data['state_metadata'].update({
                'folder_id': 'test_folder_id'
            })
            
        # Attempt state transition
        print(f"\nState data for {state}:")
        print(json.dumps(state_data, indent=2))
        
        success, result = await state_manager.transition_user_state(
            user_id=user_id,
            target_state=state,
            state_data=state_data,
            reason='Testing state transition'
        )
        
        print(f"Success: {success}")
        print(f"Result: {json.dumps(result, indent=2)}")
        
        if success:
            # Verify the state was updated
            response = supabase.table('users').select('*').eq('auth_id', user_id).single().execute()
            if response.data:
                print(f"Database state after update: {response.data['current_state']}")
                print(f"Database metadata after update: {json.dumps(response.data['state_metadata'], indent=2)}")
            else:
                print("Failed to fetch updated user data!")
        
        # Small delay between transitions
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_state_transitions())