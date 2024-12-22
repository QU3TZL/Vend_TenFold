"""
# Google OAuth and Permissions Configuration
# =======================================
#
# Overview
# --------
# This file centralizes all Google OAuth configuration and permissions management.
# It defines the scopes needed for both user authentication and Drive access.
#
# Authentication Types
# ------------------
# 1. User Authentication (OpenID Connect)
#    - openid: Core authentication protocol
#    - userinfo.email: User's email for identification
#    - userinfo.profile: Basic profile info (name)
#    Purpose: Verify user identity and link Google account
#
# 2. Drive API Access
#    - drive.file: Restricted to app-created/opened files only
#    Purpose: Create and manage folders/files owned by service account
#
# Permission Model
# --------------
# 1. Service Account
#    - Creates and owns all folders
#    - Has full CRUD access to owned content
#    - Never transfers ownership
#    - Uses drive.file scope for minimal access
#
# 2. User Access
#    - Gets Editor role on folders
#    - Can add/edit files in folders
#    - Cannot change ownership
#    - Inherits permissions from folder
#
# 3. File Inheritance
#    - New files inherit folder permissions
#    - Moving files into folder grants access
#    - No need for file-by-file permissions
#
# Security Notes
# ------------
# - Using most restrictive scopes possible
# - Service account owns all content
# - Users get Editor access only
# - No access to broader Drive content
# - Permissions inherit automatically
# - Tokens stored securely in database
#
# Implementation Details
# -------------------
# - OAuth flow handles user consent
# - Refresh tokens managed automatically
# - State parameter used for security
# - Credentials encrypted in database
# - Service account credentials in env vars
"""

import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import Optional, Dict, List
import logging
import json
import traceback
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Google OAuth Scopes Configuration
# -------------------------------
# We require two types of authentication:
#
# 1. Basic Authentication (OpenID Connect)
#    - openid: Core authentication
#    - userinfo.email: User's email address
#    - userinfo.profile: Basic profile info (name)
#    Required for: User identity verification, account linking
#
# 2. Drive-specific Permissions
#    - drive.file: Most restrictive Drive scope
#    - Only allows access to files/folders created/opened by our app
#    - Cannot see or access any other Drive content
#    Required for: Creating folders, managing files
#
# Permission Model:
# - Service account creates and owns folders
# - Users get Editor access to their folders
# - Files inherit folder permissions automatically
# - No need for broader Drive access

OAUTH_SCOPES = [
    # Basic Authentication
    'openid',                    # Core authentication
    'https://www.googleapis.com/auth/userinfo.email',    # User email
    'https://www.googleapis.com/auth/userinfo.profile',  # Basic profile info
    
    # Drive-specific Permissions
    'https://www.googleapis.com/auth/drive.file'         # Restricted Drive access
]

class GoogleOAuthHandler:
    def __init__(self):
        # Get required environment variables
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        if not self.client_id:
            raise ValueError("GOOGLE_CLIENT_ID environment variable is required")
            
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        if not self.client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET environment variable is required")
            
        self.redirect_uri = os.getenv('GOOGLE_DRIVE_REDIRECT_URI')
        if not self.redirect_uri:
            raise ValueError("GOOGLE_DRIVE_REDIRECT_URI environment variable is required")
        
        # Validate redirect URI matches expected pattern
        expected_path = "/api/state/drive/callback"
        if not self.redirect_uri.endswith(expected_path):
            raise ValueError(
                f"Invalid GOOGLE_DRIVE_REDIRECT_URI. "
                f"Expected to end with {expected_path}, got {self.redirect_uri}"
            )
        
        # Log full configuration
        logger.info("[GoogleOAuth] Full configuration", extra={
            "client_id": f"{self.client_id[:10]}...",
            "redirect_uri": self.redirect_uri,
            "env_vars": {
                "GOOGLE_DRIVE_REDIRECT_URI": os.getenv('GOOGLE_DRIVE_REDIRECT_URI'),
                "has_client_secret": bool(self.client_secret)
            }
        })
        
        # Use the centrally defined scopes
        self.default_scopes = OAUTH_SCOPES
        
        # Debug all possible sources of the redirect URI
        logger.info("[GoogleOAuth] Environment sources", extra={
            "env_file": os.getenv('GOOGLE_DRIVE_REDIRECT_URI'),
            "environ": os.environ.get('GOOGLE_DRIVE_REDIRECT_URI'),
            "all_google_vars": {k: v for k, v in os.environ.items() if 'GOOGLE' in k}
        })
        
    async def get_auth_url(self, scopes: List[str] = None, state: str = None) -> str:
        """Get Google OAuth URL"""
        try:
            logger.info("[GoogleOAuth] Generating auth URL", extra={
                "configured_redirect": self.redirect_uri,
                "scopes": scopes or self.default_scopes,
                "client_id": self.client_id[:10] + "...",  # Log partial client ID
                "has_state": bool(state)
            })
            
            # Create flow instance with explicit scopes
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=scopes or self.default_scopes
            )
            
            # Set the redirect URI explicitly
            flow.redirect_uri = self.redirect_uri
            
            # Log configuration without accessing internal attributes
            logger.info("[GoogleOAuth] Flow configured", extra={
                "flow_redirect": flow.redirect_uri,
                "requested_scopes": scopes or self.default_scopes
            })
            
            # Generate authorization URL with explicit scopes and state
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=state  # Add the state parameter here
            )
            
            logger.info("[GoogleOAuth] Generated URL", extra={
                "url_preview": auth_url[:100] + "..."
            })
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to generate auth URL: {str(e)}")
            raise

    async def process_callback(self, code: str, state: str = None) -> Dict:
        """Process OAuth callback code and return user info"""
        try:
            logger.info("[GoogleOAuth] Processing callback", extra={
                "has_code": bool(code),
                "has_state": bool(state)
            })
            
            # Create flow instance
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                # Include openid in the scopes
                scopes=[*self.default_scopes, 'openid'],
                state=state  # Pass the state parameter
            )
            flow.redirect_uri = self.redirect_uri

            # Exchange authorization code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Build the service
            service = build('oauth2', 'v2', credentials=credentials)
            
            # Get user info
            user_info = service.userinfo().get().execute()
            
            logger.info("[GoogleOAuth] Successfully retrieved user info", extra={
                "email": user_info.get('email'),
                "has_refresh_token": bool(credentials.refresh_token)
            })
            
            # Structure the response with proper state metadata format
            credentials_dict = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None
            }

            return {
                'state_metadata': {
                    'user': {
                        'email': user_info.get('email'),
                        'name': user_info.get('name'),
                        'picture': user_info.get('picture'),
                        'auth_id': user_info.get('id')
                    },
                    'allowed_transitions': ['ACTIVE'],
                    'drive': {
                        'status': 'completed',
                        'auth_status': 'connected',
                        'setup_complete': True,
                        'folders': {
                            'root': {
                                'id': None,  # Will be set after folder creation
                                'name': f"{user_info.get('name', 'User')}'s Workspace",
                                'url': None  # Will be set after folder creation
                            }
                        },
                        'permissions': {
                            'owner': user_info.get('email'),
                            'configured': True
                        },
                        'tokens': credentials_dict
                    }
                },
                'credentials': credentials_dict,
                'user_info': user_info
            }
            
        except Exception as e:
            logger.error(f"Failed to process Google callback: {str(e)}", extra={
                "error": str(e),
                "stack": traceback.format_exc()
            })
            raise