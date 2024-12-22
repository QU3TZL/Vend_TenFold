from supabase import create_client, Client
import os
from functools import lru_cache

@lru_cache()
def get_supabase_client() -> Client:
    """Get or create Supabase client instance"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("Missing Supabase configuration")
        
    return create_client(url, key)