import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
import json

def check_folders():
    supabase = get_supabase_client()
    response = supabase.table('folders').select('*').execute()
    print('\nAll folders:')
    print(json.dumps(response.data, indent=2))

if __name__ == "__main__":
    check_folders() 