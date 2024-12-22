-- Function to auto-deploy folder and transition to ACTIVE state
CREATE OR REPLACE FUNCTION auto_deploy_folder()
RETURNS TRIGGER AS $$
DECLARE
    v_folder_id UUID;
    v_folder_data JSONB;
BEGIN
    -- Only proceed if in DRIVE state and OAuth just completed
    IF NEW.current_state = 'DRIVE' AND 
       NEW.drive_auth_status = 'connected' AND 
       OLD.drive_auth_status != 'connected' AND
       (NEW.state_metadata->>'drive_access_token') IS NOT NULL THEN
        
        -- Get the pending folder for this user
        SELECT id, state_metadata INTO v_folder_id, v_folder_data
        FROM folders 
        WHERE user_id = NEW.id 
        AND current_state = 'PENDING'
        AND name LIKE '[FolderName%'
        LIMIT 1;

        IF v_folder_id IS NOT NULL THEN
            -- First transition user to ACTIVE state
            UPDATE users 
            SET current_state = 'ACTIVE',
                state_metadata = jsonb_set(
                    state_metadata,
                    '{folder_deployment_status}',
                    '"in_progress"'
                )
            WHERE id = NEW.id;

            -- Then update folder status to trigger deployment
            UPDATE folders 
            SET current_state = 'DEPLOYING',
                state_metadata = jsonb_set(
                    state_metadata,
                    '{workspace_status,deployment_status}',
                    '"in_progress"'
                ),
                updated_at = NOW()
            WHERE id = v_folder_id;

            -- Notify deployment service
            PERFORM pg_notify(
                'folder_deployment',
                json_build_object(
                    'folder_id', v_folder_id,
                    'user_id', NEW.id,
                    'user_email', NEW.email,
                    'auth_id', NEW.auth_id,
                    'drive_access_token', NEW.state_metadata->>'drive_access_token',
                    'drive_refresh_token', NEW.state_metadata->>'drive_refresh_token'
                )::text
            );
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update trigger to watch for drive_auth_status changes
DROP TRIGGER IF EXISTS auto_deploy_folder_trigger ON users;
CREATE TRIGGER auto_deploy_folder_trigger
    AFTER UPDATE OF drive_auth_status
    ON users
    FOR EACH ROW
    WHEN (NEW.drive_auth_status = 'connected' AND OLD.drive_auth_status != 'connected')
    EXECUTE FUNCTION auto_deploy_folder();

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION auto_deploy_folder() TO authenticated;
GRANT EXECUTE ON FUNCTION auto_deploy_folder() TO service_role; 