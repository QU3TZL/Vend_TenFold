-- Add auth_id column to user_state_history table
BEGIN;

-- Add new column
ALTER TABLE user_state_history 
ADD COLUMN auth_id VARCHAR(255);

-- Add index for performance
CREATE INDEX idx_user_state_history_auth_id 
ON user_state_history(auth_id);

COMMIT; 