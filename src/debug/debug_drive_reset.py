import os
import sys
import asyncio
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
from datetime import datetime

async def reset_drive_state():
    supabase = get_supabase_client()
    
    # Get current user
    user_response = supabase.table('users').select('*').eq('email', 'matt@rhombus.ventures').single().execute()
    if not user_response.data:
        print("User not found!")
        return
        
    user = user_response.data
    print("\nWorkspace Status:")
    print(f"Email: {user['email']}")
    print(f"Current State: {user['current_state']}")
    
    print("Moving user back to DRIVE state...")
    
    # First reset drive auth status to pending
    update_response = supabase.table('users').update({
        'current_state': 'DRIVE',
        'drive_auth_status': 'pending',
        'state_metadata': {
            'drive': {
                'status': 'pending'
            }
        }
    }).eq('id', user['id']).execute()
    
    if update_response.data:
        print("Successfully moved to DRIVE state and reset auth status")
        
        # Create a new pending folder
        folder_number = 7  # You can modify this as needed
        folder_name = f"[FolderName{folder_number:02d}]_TenFold"
        
        print(f"\nCreating workspace folder {folder_name}...")
        
        folder_data = {
            'user_id': user['id'],
            'name': folder_name,
            'current_state': 'PENDING',
            'storage_limit_gb': 10,
            'current_size_bytes': 0,
            'file_count': 0,
            'state_metadata': {
                'workspace_status': {
                    'owner': user['email'],
                    'status': 'pending',
                    'created_at': datetime.utcnow().isoformat(),
                    'folder_number': folder_number,
                    'recent_activity': [{
                        'action': 'workspace_created',
                        'details': 'Initial workspace creation',
                        'timestamp': datetime.utcnow().isoformat()
                    }],
                    'storage_metrics': {
                        'folder_count': 1,
                        'storage_used': 0,
                        'storage_limit': 10 * 1024 * 1024 * 1024  # 10GB in bytes
                    }
                }
            }
        }
        
        folder_response = supabase.table('folders').insert(folder_data).execute()
        
        if folder_response.data:
            print("Workspace folder created successfully:")
            print(json.dumps(folder_response.data[0], indent=2))
            
            # Now update drive auth status to connected to trigger deployment
            print("\nUpdating drive auth status to trigger deployment...")
            final_update = supabase.table('users').update({
                'drive_auth_status': 'connected',
                'drive_access_token': 'test_token',
                'drive_refresh_token': 'test_refresh_token',
                'state_metadata': {
                    'drive': {
                        'status': 'connected',
                        'tokens': {
                            'access_token': 'test_token',
                            'refresh_token': 'test_refresh_token'
                        }
                    }
                }
            }).eq('id', user['id']).execute()
            
            if final_update.data:
                print("Drive auth status updated to trigger deployment")
        else:
            print("Failed to create workspace folder!")
    else:
        print("Failed to update user state!")

if __name__ == "__main__":
    asyncio.run(reset_drive_state()) 