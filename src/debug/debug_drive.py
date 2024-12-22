import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
from src.services.state.state_manager import StateManager
import json
from datetime import datetime
import time

async def get_user_and_folder_details():
    supabase = get_supabase_client()
    
    # Get user in DRIVE state
    user_response = supabase.table('users').select('*').eq('current_state', 'DRIVE').execute()
    if not user_response.data:
        return None, None
        
    user = user_response.data[0]
    
    # Get the pending folder for this user that starts with '[FolderName'
    folder_response = supabase.table('folders').select('*').eq('user_id', user['id']).eq('current_state', 'PENDING').like('name', '[FolderName%').execute()
    
    print("\nWorkspace Status:")
    print(f"Email: {user['email']}")
    print(f"Auth ID: {user['auth_id']}")
    print(f"Current State: {user['current_state']}")
    print("\nWorkspace Details:")
    if folder_response.data:
        folder = folder_response.data[0]
        print(f"Workspace Name: {folder['name']}")
        print(f"Workspace ID: {folder['id']}")
        print(f"Current State: {folder['current_state']}")
        print(f"Metadata: {json.dumps(folder['state_metadata'], indent=2)}")
    else:
        print("No pending workspace found!")
        folder = None
        
    return user, folder

async def test_drive_deployment():
    # Get user and workspace details
    user, folder = await get_user_and_folder_details()
    if not user or not folder:
        print("Could not find user in DRIVE state or their pending workspace!")
        return
        
    supabase = get_supabase_client()
    state_manager = StateManager()
    
    print(f"\nDeploying workspace for user: {user['email']}")
    
    try:
        # Update user's drive_auth_status to trigger auto-deploy
        print("\nUpdating drive_auth_status to trigger deployment...")
        user_update = {
            'drive_auth_status': 'connected',
            'state_metadata': {
                'drive': {
                    'tokens': {
                        'access_token': 'test_token',
                        'refresh_token': 'test_refresh_token'
                    },
                    'status': 'connected'
                }
            }
        }
        
        user_response = supabase.table('users').update(user_update).eq('id', user['id']).execute()
        if not user_response.data:
            print("Failed to update user status!")
            return
            
        print("\nAuto-deployment triggered. Checking user state...")
        
        # Check user state after update
        user_check = supabase.table('users').select('*').eq('id', user['id']).single().execute()
        if user_check.data:
            print("\nUser state after update:")
            print(f"Current State: {user_check.data['current_state']}")
            print(f"Drive Auth Status: {user_check.data['drive_auth_status']}")
            print(f"State Metadata: {json.dumps(user_check.data['state_metadata'], indent=2)}")
            
        # Check deployment logs
        print("\nChecking deployment logs...")
        logs = supabase.table('deployment_logs').select('*').order('created_at', desc=True).limit(5).execute()
        if logs.data:
            print("\nRecent deployment logs:")
            for log in logs.data:
                print(f"\nLog ID: {log['id']}")
                print(f"Created At: {log['created_at']}")
                print(f"Notification: {json.dumps(log['notification'], indent=2)}")
        else:
            print("\nNo deployment logs found!")
            
        print("\nMonitoring folder status...")
        
        # Monitor folder status
        max_attempts = 30  # 30 seconds timeout
        attempt = 0
        while attempt < max_attempts:
            folder_response = supabase.table('folders').select('*').eq('id', folder['id']).single().execute()
            if not folder_response.data:
                print("Failed to get folder status!")
                return
                
            current_folder = folder_response.data
            status = current_folder['current_state']
            
            print(f"\nCurrent folder state: {status}")
            if status == 'ACTIVE':
                print("\nFolder deployment completed successfully!")
                print("\nFinal folder details:")
                print(json.dumps(current_folder, indent=2))
                break
            elif status == 'ERROR':
                print("\nFolder deployment failed!")
                print(json.dumps(current_folder.get('state_metadata', {}).get('error', {}), indent=2))
                break
                
            print("Waiting for deployment to complete...")
            await asyncio.sleep(1)
            attempt += 1
            
        if attempt >= max_attempts:
            print("\nDeployment timed out!")
            return
            
        # Verify final states
        user_response = supabase.table('users').select('*').eq('auth_id', user['auth_id']).single().execute()
        if user_response.data:
            print(f"\nFinal User State: {user_response.data['current_state']}")
            print(f"Final User Metadata: {json.dumps(user_response.data['state_metadata'], indent=2)}")
            
    except Exception as e:
        print(f"Error during workspace deployment: {e}")

if __name__ == "__main__":
    asyncio.run(test_drive_deployment()) 