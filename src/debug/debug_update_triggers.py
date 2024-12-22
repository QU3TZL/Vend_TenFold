import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase import get_supabase_client
import re

async def update_triggers():
    supabase = get_supabase_client()
    
    # Read the SQL file
    with open('src/database/create_functions.sql', 'r') as f:
        sql = f.read()
    
    print("\nUpdating database triggers...")
    
    # Split SQL into statements, preserving dollar-quoted strings
    def split_sql(sql):
        statements = []
        current = []
        in_dollar_quote = False
        quote_tag = ''
        
        for line in sql.split('\n'):
            # Check for start of dollar quote
            if not in_dollar_quote and '$$' in line:
                in_dollar_quote = True
                quote_tag = '$$'
                current.append(line)
            # Check for end of dollar quote
            elif in_dollar_quote and quote_tag in line:
                in_dollar_quote = False
                current.append(line)
                if not any(c.strip() for c in current):
                    continue
                statements.append('\n'.join(current))
                current = []
            # Inside dollar quote or regular statement
            elif in_dollar_quote:
                current.append(line)
            else:
                if ';' in line:
                    current.append(line)
                    if not any(c.strip() for c in current):
                        continue
                    statements.append('\n'.join(current))
                    current = []
                else:
                    current.append(line)
        
        if current:
            statements.append('\n'.join(current))
        
        return [s.strip() for s in statements if s.strip()]
    
    statements = split_sql(sql)
    
    # Execute each statement
    for statement in statements:
        if statement.strip():
            try:
                response = supabase.rpc('exec_sql', {'sql': statement}).execute()
                print(f"Success: {response.data}")
            except Exception as e:
                print(f"Error: {e}")
    
    print("\nTrigger update complete!")

if __name__ == "__main__":
    asyncio.run(update_triggers()) 