import os
import sys
import asyncio
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
from src.api.state.active.active_service import ActiveService
from src.services.state.state_manager import StateManager

async def test_deployment():
    supabase = get_supabase_client()
    state_manager = StateManager()
    active_service = ActiveService(state_manager, supabase)
    
    # Get user and folder in PROCESSING state
    user_response = supabase.table('users').select('*').eq('email', 'matt@rhombus.ventures').single().execute()
    if not user_response.data:
        print("User not found!")
        return
        
    user = user_response.data
    print("\nUser Status:")
    print(f"Email: {user['email']}")
    print(f"Current State: {user['current_state']}")
    print(f"Drive Auth Status: {user['drive_auth_status']}")
    print(f"State Metadata: {json.dumps(user['state_metadata'], indent=2)}")
    
    # Get processing folder
    folder_response = supabase.table('folders').select('*').eq('user_id', user['id']).eq('current_state', 'PROCESSING').single().execute()
    if not folder_response.data:
        print("\nNo folder in PROCESSING state found!")
        return
        
    folder = folder_response.data
    print("\nFolder Status:")
    print(f"Name: {folder['name']}")
    print(f"Current State: {folder['current_state']}")
    print(f"State Metadata: {json.dumps(folder['state_metadata'], indent=2)}")
    
    print("\nStarting folder deployment...")
    try:
        # Create deployment payload
        payload = {
            'new': folder,
            'old': {**folder, 'current_state': 'PENDING'}
        }
        
        # Handle deployment
        await active_service.handle_folder_deployment(payload)
        print("\nDeployment completed successfully!")
        
        # Check final states
        final_user = supabase.table('users').select('*').eq('id', user['id']).single().execute().data
        final_folder = supabase.table('folders').select('*').eq('id', folder['id']).single().execute().data
        
        print("\nFinal User State:")
        print(f"Current State: {final_user['current_state']}")
        print(f"State Metadata: {json.dumps(final_user['state_metadata'], indent=2)}")
        
        print("\nFinal Folder State:")
        print(f"Current State: {final_folder['current_state']}")
        print(f"Drive Folder ID: {final_folder['drive_folder_id']}")
        print(f"State Metadata: {json.dumps(final_folder['state_metadata'], indent=2)}")
        
    except Exception as e:
        print(f"\nError during deployment: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_deployment()) 