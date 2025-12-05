import os
from flask_appbuilder.security.manager import AUTH_OAUTH

# Disable OAuth state validation for development (allows multi-URL access)
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Patch Authlib to skip state validation at the lowest level
def patch_authlib_state_validation():
    """Completely disable OAuth state validation in Authlib"""
    try:
        from authlib.integrations.flask_client import OAuth
        from authlib.integrations.base_client import BaseOAuth
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Patch at the BaseOAuth level - the parent class of all OAuth clients
        original_parse_response = BaseOAuth._parse_response if hasattr(BaseOAuth, '_parse_response') else None
        
        # More importantly, patch the Flask integration's authorize_access_token
        from authlib.integrations.flask_client import FlaskOAuth2App
        original_authorize = FlaskOAuth2App.authorize_access_token
        
        def patched_authorize_access_token(self, **kwargs):
            """Patched version that doesn't validate state"""
            from flask import request
            import logging
            
            logger = logging.getLogger(__name__)
            
            try:
                # Try to manually handle the OAuth callback without state validation
                code = request.args.get('code')
                if code:
                    redirect_uri = request.base_url
                    logger.info(f"[Authlib Patch] Intercepting OAuth callback, redirect_uri={redirect_uri}")
                    
                    # Manually exchange code for token
                    token = self.fetch_access_token(
                        code=code,
                        redirect_uri=redirect_uri
                    )
                    
                    if token and 'access_token' in token:
                        logger.info(f"[Authlib Patch] Successfully exchanged code for token")
                        return token
                    else:
                        logger.warning(f"[Authlib Patch] Token exchange returned: {token}")
                        
            except Exception as e:
                logger.warning(f"[Authlib Patch] Manual token exchange failed: {e}")
            
            # Fall back to original method
            try:
                return original_authorize(self, **kwargs)
            except Exception as e:
                # If original fails with state error, try one more time without validation
                error_msg = str(e)
                if 'state' in error_msg.lower():
                    logger.error(f"[Authlib Patch] State validation failed, attempting recovery: {e}")
                    code = request.args.get('code')
                    if code:
                        try:
                            token = self.fetch_access_token(
                                code=code,
                                redirect_uri=request.base_url
                            )
                            if token:
                                logger.info(f"[Authlib Patch] Recovered from state error")
                                return token
                        except Exception as recovery_error:
                            logger.error(f"[Authlib Patch] Recovery failed: {recovery_error}")
                raise
        
        FlaskOAuth2App.authorize_access_token = patched_authorize_access_token
        print("✓ Authlib OAuth state validation disabled")
        
    except Exception as e:
        print(f"⚠ Failed to patch Authlib: {e}")
        import traceback
        traceback.print_exc()

patch_authlib_state_validation()

# Monkey-patch Flask-AppBuilder's OAuth to bypass state validation
# This allows access via multiple URLs (localhost + IP) without state mismatch errors
def patch_flask_appbuilder_oauth():
    """Patch Flask-AppBuilder to skip OAuth state validation"""
    try:
        from flask_appbuilder.security.views import AuthOAuthView
        from functools import wraps
        
        # Save the original oauth_authorized method
        _original_oauth_authorized = AuthOAuthView.oauth_authorized
        
        @wraps(_original_oauth_authorized)
        def patched_oauth_authorized(self, provider):
            """Patched version that catches and recovers from state mismatch errors"""
            import logging
            from flask import request, redirect
            from flask_login import login_user
            
            logger = logging.getLogger(__name__)
            
            try:
                # Try the original method first
                return _original_oauth_authorized(self, provider)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"OAuth error: {error_msg}")
                
                # Check if it's a state mismatch error
                if 'mismatching_state' in error_msg or 'state' in error_msg.lower():
                    logger.info("State mismatch detected - attempting recovery")
                    
                    code = request.args.get('code')
                    if not code:
                        logger.error("No authorization code found")
                        raise
                    
                    try:
                        # Manually exchange the code for a token
                        remote = self.appbuilder.sm.oauth_remotes[provider]
                        redirect_uri = request.base_url
                        
                        logger.info(f"Manual token exchange: redirect_uri={redirect_uri}")
                        token = remote.fetch_access_token(code=code, redirect_uri=redirect_uri)
                        
                        if not token or 'access_token' not in token:
                            logger.error(f"Failed to get access token: {token}")
                            raise
                        
                        # Get user info using the token
                        user_info = self.appbuilder.sm.oauth_user_info(provider, response=token)
                        
                        if not user_info or not user_info.get('username'):
                            logger.error(f"Failed to get user info: {user_info}")
                            raise
                        
                        logger.info(f"Successfully recovered - user: {user_info['username']}")
                        
                        # Find or create the user
                        user = self.appbuilder.sm.find_user(username=user_info['username'])
                        
                        if not user:
                            user = self.appbuilder.sm.add_user(
                                username=user_info['username'],
                                first_name=user_info.get('first_name', ''),
                                last_name=user_info.get('last_name', ''),
                                email=user_info.get('email', ''),
                                role=self.appbuilder.sm.find_role(self.appbuilder.sm.auth_role_public)
                            )
                        
                        if user and user.is_active:
                            login_user(user)
                            next_url = request.args.get('state', '/superset/welcome/')
                            try:
                                # Try to decode JWT state token
                                import jwt
                                import json
                                state_data = jwt.decode(next_url, options={"verify_signature": False})
                                next_url = state_data.get('next', ['/superset/welcome/'])[0] or '/superset/welcome/'
                            except:
                                next_url = '/superset/welcome/'
                            
                            logger.info(f"User logged in successfully, redirecting to: {next_url}")
                            return redirect(next_url)
                        else:
                            logger.error(f"User not active or not found: {user}")
                            raise
                    
                    except Exception as recovery_error:
                        logger.error(f"Failed to recover from state mismatch: {recovery_error}", exc_info=True)
                        raise
                
                # If it's not a state error, re-raise
                raise
        
        # Apply the patch
        AuthOAuthView.oauth_authorized = patched_oauth_authorized
        print("✓ Flask-AppBuilder OAuth patched for multi-URL support")
        
    except Exception as e:
        print(f"⚠ Failed to patch Flask-AppBuilder OAuth: {e}")

# Apply the patch when config is loaded
patch_flask_appbuilder_oauth()

# Superset specific config
ROW_LIMIT = 5000
SUPERSET_WEBSERVER_PORT = 8088

# Flask App Builder configuration
# Your App secret key
SECRET_KEY = os.getenv('SUPERSET_SECRET_KEY', 'thisISaSECRET_1234')

# The SQLAlchemy connection string to your database backend
# This connection defines the path to the database that stores your
# superset metadata (slices, connections, tables, dashboards, ...).
# Using superset schema in mlflow_db to consolidate databases
SQLALCHEMY_DATABASE_URI = os.getenv(
    'SQLALCHEMY_DATABASE_URI',
    'postgresql://mlflow:mlflow@host.docker.internal:5432/mlflow_db?options=-csearch_path%3Dsuperset'
)

# Flask-WTF flag for CSRF
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ['/oauth-authorized/keycloak']  # Exempt OAuth callback from CSRF
# A CSRF token that expires in 1 year
WTF_CSRF_TIME_LIMIT = 60 * 60 * 24 * 365

# Session and cookie configuration for OAuth
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False  # Set to True when using HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_DOMAIN = None  # Don't restrict to specific domain
SESSION_COOKIE_PATH = '/'

# Set this API key to enable Mapbox visualizations
MAPBOX_API_KEY = ''

# Authentication configuration
AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"

# Keycloak OAuth configuration
# Internal URL for server-to-server communication
KEYCLOAK_BASE_URL = os.getenv('KEYCLOAK_BASE_URL', 'http://keycloak:8080')
# Public URL for browser redirects
KEYCLOAK_PUBLIC_URL = os.getenv('KEYCLOAK_PUBLIC_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'jhub')
KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'superset-client')
KEYCLOAK_CLIENT_SECRET = os.getenv('KEYCLOAK_CLIENT_SECRET', 'superset-secret-key-change-me')

# OAuth configuration
OAUTH_PROVIDERS = [
    {
        'name': 'keycloak',
        'icon': 'fa-key',
        'token_key': 'access_token',
        'remote_app': {
            'client_id': KEYCLOAK_CLIENT_ID,
            'client_secret': KEYCLOAK_CLIENT_SECRET,
            'api_base_url': f'{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect',
            'access_token_url': f'{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token',
            'authorize_url': f'{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth',
            'userinfo_url': f'{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo',
            'server_metadata_url': f'{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration',
            'client_kwargs': {
                'scope': 'openid email profile',
            },
        }
    }
]

# Map Keycloak user info to Superset user info
AUTH_ROLE_ADMIN = 'Admin'
AUTH_ROLE_PUBLIC = 'Public'

# Custom Security Manager to disable state validation
from superset.security import SupersetSecurityManager
from flask import redirect, request, session
from flask_login import login_user
import logging

logger = logging.getLogger(__name__)

# Custom OAuth View to handle callbacks without state validation
from flask_appbuilder.security.views import AuthOAuthView
from flask_appbuilder import expose
from flask import redirect, request
from flask_login import login_user

class CustomAuthOAuthView(AuthOAuthView):
    """Custom OAuth view that handles state validation issues"""
    
    @expose('/oauth-authorized/<provider>')
    def oauth_authorized(self, provider):
        """Override OAuth callback to handle state mismatch"""
        logger.info(f"🔵 [CUSTOM VIEW] OAuth authorized callback START for provider: {provider}")
        logger.info(f"🔵 [CUSTOM VIEW] Request URL: {request.url}")
        logger.info(f"🔵 [CUSTOM VIEW] Request args: {request.args}")
        
        # Get the code from the callback
        code = request.args.get('code')
        if not code:
            logger.error("🔴 [CUSTOM VIEW] No authorization code in callback!")
            return redirect(self.appbuilder.get_url_for_login)
        
        logger.info(f"🔵 [CUSTOM VIEW] Authorization code received: {code[:20]}...")
        
        # DON'T call parent - it will fail on state validation
        # Instead, manually complete the OAuth flow using our patched Authlib
        try:
            logger.info(f"🔵 [CUSTOM VIEW] Getting OAuth remote for provider: {provider}")
            remote = self.appbuilder.sm.oauth_remotes[provider]
            redirect_uri = request.base_url
            
            logger.info(f"🔵 [CUSTOM VIEW] Exchanging code for token with redirect_uri: {redirect_uri}")
            # This will use our patched authorize_access_token that bypasses state validation
            token = remote.authorize_access_token()
            
            if not token or 'access_token' not in token:
                logger.error(f"🔴 [CUSTOM VIEW] Failed to get access token: {token}")
                return redirect(self.appbuilder.get_url_for_login)
            
            logger.info(f"🟢 [CUSTOM VIEW] Token received successfully")
            
            # Get user info
            logger.info(f"🔵 [CUSTOM VIEW] Getting user info...")
            user_info = self.appbuilder.sm.oauth_user_info(provider, response=token)
            
            if not user_info or not user_info.get('username'):
                logger.error(f"🔴 [CUSTOM VIEW] Failed to get user info: {user_info}")
                return redirect(self.appbuilder.get_url_for_login)
            
            username = user_info['username']
            logger.info(f"🟢 [CUSTOM VIEW] User info retrieved for: {username}")
            
            # Find or create user
            user = self.appbuilder.sm.find_user(username=username)
            
            if not user:
                logger.info(f"🔵 [CUSTOM VIEW] Creating new user: {username}")
                # Assign Admin role to new OAuth users
                admin_role = self.appbuilder.sm.find_role('Admin')
                user = self.appbuilder.sm.add_user(
                    username=username,
                    first_name=user_info.get('first_name', ''),
                    last_name=user_info.get('last_name', ''),
                    email=user_info.get('email', f'{username}@example.com'),
                    role=admin_role
                )
                logger.info(f"🟢 [CUSTOM VIEW] User created successfully with Admin role")
            else:
                logger.info(f"🟢 [CUSTOM VIEW] User found: {username}")
                # Ensure existing user has Admin role
                admin_role = self.appbuilder.sm.find_role('Admin')
                if admin_role not in user.roles:
                    logger.info(f"🔵 [CUSTOM VIEW] Adding Admin role to existing user")
                    user.roles.append(admin_role)
                    self.appbuilder.sm.update_user(user)
                    logger.info(f"🟢 [CUSTOM VIEW] Admin role added")
            
            # Log the user in
            logger.info(f"🔵 [CUSTOM VIEW] Logging in user: {username}")
            login_user(user, remember=True)
            logger.info(f"🟢 [CUSTOM VIEW] User logged in successfully!")
            
            # Redirect to index
            logger.info(f"🔵 [CUSTOM VIEW] Redirecting to index page")
            return redirect(self.appbuilder.get_url_for_index)
            
        except Exception as e:
            logger.error(f"🔴 [CUSTOM VIEW] Exception during manual OAuth: {str(e)}", exc_info=True)
            return redirect(self.appbuilder.get_url_for_login)

class CustomSecurityManager(SupersetSecurityManager):
    """Custom security manager that uses our custom OAuth view"""
    authoauthview = CustomAuthOAuthView
    
    def oauth_user_info(self, provider, response=None):
        """Get user info from OAuth provider without strict state validation"""
        if provider == 'keycloak':
            try:
                # Get the OAuth remote app
                remote = self.oauth_remotes[provider]
                
                # If response is None, we're being called from the callback
                # Try to get the token directly without state validation
                if response is None:
                    code = request.args.get('code')
                    if code:
                        try:
                            # Construct redirect_uri from current request
                            # This ensures it matches regardless of localhost vs IP
                            redirect_uri = request.base_url
                            logger.info(f"OAuth callback: Using redirect_uri={redirect_uri}")
                            
                            # Manually exchange code for token, bypassing state check
                            token = remote.fetch_access_token(
                                code=code,
                                redirect_uri=redirect_uri
                            )
                            response = token
                            logger.info(f"Successfully exchanged code for token")
                        except Exception as e:
                            logger.error(f"Manual token exchange failed: {e}, trying standard flow")
                            try:
                                response = remote.authorize_access_token()
                            except Exception as e2:
                                logger.error(f"Standard authorize_access_token also failed: {e2}")
                                return None
                    else:
                        try:
                            response = remote.authorize_access_token()
                        except Exception as e:
                            logger.error(f"authorize_access_token failed (no code): {e}")
                            return None
                
                # Parse user info from token
                if response and 'access_token' in response:
                    # Use the correct userinfo endpoint
                    userinfo_url = f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
                    logger.info(f"Fetching user info from: {userinfo_url}")
                    
                    me = remote.get(userinfo_url, token=response)
                    data = me.json() if hasattr(me, 'json') else me
                    
                    username = data.get('preferred_username', data.get('username', ''))
                    logger.info(f"Retrieved user info for: {username}")
                    
                    if not username:
                        logger.error(f"No username found in user info: {data}")
                        return None
                    
                    return {
                        'username': username,
                        'email': data.get('email', ''),
                        'first_name': data.get('given_name', ''),
                        'last_name': data.get('family_name', ''),
                        'role_keys': ['Public']  # Default role
                    }
                else:
                    logger.error(f"No valid response with access_token: {response}")
            except Exception as e:
                logger.error(f"Error getting OAuth user info: {e}", exc_info=True)
                # Return None to trigger standard flow
                return None
        
        # Fall back to parent implementation
        return super().oauth_user_info(provider, response)

CUSTOM_SECURITY_MANAGER = CustomSecurityManager

# Additional configuration
ENABLE_PROXY_FIX = True
FEATURE_FLAGS = {
    "ALERT_REPORTS": True,
}

# Cache configuration
CACHE_CONFIG = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
}

# Async queries configuration
RESULTS_BACKEND = None

# CORS configuration
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*']
}

# NOTE: OAuth state validation with multi-URL access (localhost + IP)
# ====================================================================
# The issue with IP address access is that Flask-AppBuilder's OAuth implementation
# stores the OAuth state in session cookies that are domain-specific. When you:
# 
# 1. Start OAuth flow at http://192.168.180.241:8088/login/keycloak
#    - Creates session with state='xyz'
#    - Redirects to Keycloak
# 
# 2. Keycloak redirects back to http://192.168.180.241:8088/oauth-authorized/keycloak?state=xyz&code=abc
#    - Flask-AppBuilder tries to verify state
#    - Session cookie may not match because browser treats localhost != IP address
#    - Result: "mismatching_state" error -> redirects to /login/
# 
# PRODUCTION SOLUTION:
# Use a single public-facing domain with HTTPS and proper DNS (e.g., superset.yourdomain.com)
# Configure nginx reverse proxy to handle all requests through one domain
# 
# DEVELOPMENT WORKAROUND:
# Always access Superset through http://localhost:8088 (which works correctly)
# Avoid using http://192.168.180.241:8088 for OAuth flows
# 
# For production deployment, see ARCHITECTURE.md for proper nginx configuration
