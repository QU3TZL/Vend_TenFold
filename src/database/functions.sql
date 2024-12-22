-- Function to update user state while avoiding trigger issues
CREATE OR REPLACE FUNCTION update_user_state(
    p_user_id UUID,
    p_state TEXT,
    p_metadata JSONB,
    p_drive_status TEXT DEFAULT NULL,
    p_drive_access TEXT DEFAULT NULL,
    p_drive_refresh TEXT DEFAULT NULL
) RETURNS JSONB AS $$
BEGIN
    UPDATE users
    SET 
        current_state = p_state,
        state_metadata = p_metadata,
        updated_at = NOW(),
        drive_auth_status = COALESCE(p_drive_status, drive_auth_status),
        drive_access_token = COALESCE(p_drive_access, drive_access_token),
        drive_refresh_token = COALESCE(p_drive_refresh, drive_refresh_token)
    WHERE id = p_user_id;
    
    RETURN jsonb_build_object(
        'success', true,
        'user_id', p_user_id,
        'state', p_state
    );
END;
$$ LANGUAGE plpgsql; 