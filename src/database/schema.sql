-- Add name column to users table
ALTER TABLE users ADD COLUMN name text;

-- Migrate existing names from state_metadata
UPDATE users 
SET name = state_metadata->'user'->>'name'
WHERE state_metadata->'user'->>'name' IS NOT NULL;

// ... existing code ... 