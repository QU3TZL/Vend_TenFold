-- Function to execute arbitrary SQL (for admin use only)
CREATE OR REPLACE FUNCTION exec_sql(sql text) RETURNS text AS $$
BEGIN
    EXECUTE sql;
    RETURN 'SQL executed successfully';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to service role
GRANT EXECUTE ON FUNCTION exec_sql(text) TO service_role;

-- Drop existing functions and triggers
DROP TRIGGER IF EXISTS drive_state_change_trigger ON users;
DROP TRIGGER IF EXISTS on_drive_state_change ON users;
DROP TRIGGER IF EXISTS user_state_change_trigger ON users;
DROP FUNCTION IF EXISTS handle_drive_state_change CASCADE;
DROP FUNCTION IF EXISTS log_state_change CASCADE;
DROP FUNCTION IF EXISTS update_user_state CASCADE;

-- Function to handle drive state changes
CREATE OR REPLACE FUNCTION handle_drive_state_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only proceed if transitioning to DRIVE state
    IF NEW.current_state = 'DRIVE' THEN
        -- Create a pending folder for the user
        INSERT INTO folders (
            user_id,
            name,
            current_state,
            state_metadata,
            storage_limit_gb,
            current_size_bytes,
            file_count
        ) VALUES (
            NEW.id,  -- internal user ID
            'Pending TenFold Folder',  -- temporary name, will be updated by drive service
            'PENDING',  -- initial state
            jsonb_build_object(
                'owner', NEW.email,
                'status', 'pending',
                'created_at', NOW()
            ),
            10,  -- default 10GB limit
            0,   -- initial size
            0    -- initial file count
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to log state changes
CREATE OR REPLACE FUNCTION log_state_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log if state actually changed
    IF OLD.current_state IS DISTINCT FROM NEW.current_state THEN
        INSERT INTO user_state_history (
            internal_user_id,
            from_state,
            to_state,
            transition_reason,
            metadata,
            created_at
        ) VALUES (
            NEW.id,  -- This is the internal user_id
            OLD.current_state,
            NEW.current_state,
            COALESCE(TG_ARGV[0], 'State change via trigger'),
            NEW.state_metadata,
            NOW()
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update user state
CREATE OR REPLACE FUNCTION update_user_state(
    p_auth_id TEXT,
    p_state TEXT,
    p_metadata JSONB,
    p_drive_status TEXT DEFAULT NULL,
    p_drive_access TEXT DEFAULT NULL,
    p_drive_refresh TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_user_id UUID;
    v_old_state TEXT;
BEGIN
    -- Get the internal user ID first
    SELECT u.id, u.current_state INTO v_user_id, v_old_state
    FROM users u
    WHERE u.auth_id = p_auth_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'User not found'
        );
    END IF;

    -- Update the user state
    UPDATE users u
    SET 
        current_state = p_state,
        state_metadata = p_metadata,
        updated_at = NOW(),
        drive_auth_status = COALESCE(p_drive_status, u.drive_auth_status),
        drive_access_token = COALESCE(p_drive_access, u.drive_access_token),
        drive_refresh_token = COALESCE(p_drive_refresh, u.drive_refresh_token)
    WHERE u.id = v_user_id;
    
    RETURN jsonb_build_object(
        'success', true,
        'user_id', v_user_id,
        'auth_id', p_auth_id,
        'state', p_state
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION update_user_state TO authenticated;
GRANT EXECUTE ON FUNCTION update_user_state TO service_role;

-- Create single trigger for state history
CREATE TRIGGER user_state_change_trigger
    AFTER UPDATE OF current_state ON users
    FOR EACH ROW
    WHEN (OLD.current_state IS DISTINCT FROM NEW.current_state)
    EXECUTE FUNCTION log_state_change();

-- Create single trigger for drive state
CREATE TRIGGER drive_state_change_trigger
    AFTER UPDATE OF current_state ON users
    FOR EACH ROW
    WHEN (NEW.current_state = 'DRIVE')
    EXECUTE FUNCTION handle_drive_state_change();

-- Function to auto-deploy folder and transition to ACTIVE state
CREATE OR REPLACE FUNCTION auto_deploy_folder()
RETURNS TRIGGER AS $$
DECLARE
    v_folder_id UUID;
    v_folder_data JSONB;
BEGIN
    -- Log trigger execution
    RAISE NOTICE 'Auto deploy trigger fired for user %', NEW.id;
    RAISE NOTICE 'Current state: %, Drive auth status: %, State metadata: %', 
        NEW.current_state, NEW.drive_auth_status, NEW.state_metadata;

    -- Only proceed if in DRIVE state and OAuth just completed
    IF NEW.current_state = 'DRIVE' AND 
       NEW.drive_auth_status = 'connected' AND 
       OLD.drive_auth_status != 'connected' AND
       (NEW.state_metadata->'drive'->'tokens'->>'access_token') IS NOT NULL THEN
        
        RAISE NOTICE 'Conditions met, proceeding with deployment';
        
        -- Get the pending folder for this user
        SELECT id, state_metadata INTO v_folder_id, v_folder_data
        FROM folders 
        WHERE user_id = NEW.id 
        AND current_state = 'PENDING'
        AND name LIKE '[FolderName%'
        LIMIT 1;

        IF v_folder_id IS NOT NULL THEN
            RAISE NOTICE 'Found pending folder: %', v_folder_id;
            
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
            SET current_state = 'PROCESSING',
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
                    'drive_access_token', NEW.state_metadata->'drive'->'tokens'->>'access_token',
                    'drive_refresh_token', NEW.state_metadata->'drive'->'tokens'->>'refresh_token'
                )::text
            );
            
            RAISE NOTICE 'Deployment notification sent';
        ELSE
            RAISE NOTICE 'No pending folder found for user %', NEW.id;
        END IF;
    ELSE
        RAISE NOTICE 'Conditions not met: current_state=%, drive_auth_status=%, old_status=%, has_token=%',
            NEW.current_state, NEW.drive_auth_status, OLD.drive_auth_status,
            (NEW.state_metadata->'drive'->'tokens'->>'access_token') IS NOT NULL;
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