import os
import sys
from supabase import create_client, Client

def get_supabase_client() -> Client:
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(supabase_url, supabase_key)

def deploy_functions():
    supabase = get_supabase_client()
    
    # Read the SQL file
    with open(os.path.join(os.path.dirname(__file__), 'functions.sql'), 'r') as f:
        sql = f.read()
    
    print("Deploying database functions...")
    print("SQL to execute:", sql)
    
    # Execute the SQL
    try:
        response = supabase.rpc('exec_sql', {'sql': sql}).execute()
        print("Functions deployed successfully!")
        print(response.data)
    except Exception as e:
        print(f"Error deploying functions: {e}")

if __name__ == "__main__":
    deploy_functions() 