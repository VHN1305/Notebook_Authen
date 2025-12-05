import os
from oauthenticator.generic import GenericOAuthenticator

c = get_config()  # JupyterHub expects get_config() available in this context

# Basic hub settings
c.JupyterHub.bind_url = 'http://:8000'

# Authenticator - use GenericOAuthenticator for Keycloak
c.JupyterHub.authenticator_class = GenericOAuthenticator

# Read URLs and client info from environment (set in docker-compose.yml)
authorize_url = os.environ.get('OAUTH2_AUTHORIZE_URL')
token_url = os.environ.get('OAUTH2_TOKEN_URL')
userdata_url = os.environ.get('OAUTH2_USERDATA_URL')
client_id = os.environ.get('OAUTH_CLIENT_ID')
client_secret = os.environ.get('OAUTH_CLIENT_SECRET')
callback_url = os.environ.get('OAUTH_CALLBACK_URL')

if not (authorize_url and token_url and userdata_url and client_id and client_secret):
    raise RuntimeError('Missing required OIDC environment variables for Keycloak')


# Bắt buộc dùng thằng này
# c.GenericOAuthenticator.auto_login = True

# (tuỳ chọn) đặt tên service cho rõ, dù auto_login bật thì cũng ít khi thấy
# c.GenericOAuthenticator.login_service = "Keycloak"

# # Có thể giữ lại dòng này, không sao:
# c.Authenticator.auto_login = True
c.GenericOAuthenticator.authorize_url = authorize_url
c.GenericOAuthenticator.token_url = token_url
# Don't set userdata_url when using userdata_from_id_token
# c.GenericOAuthenticator.userdata_url = userdata_url
c.GenericOAuthenticator.client_id = client_id
c.GenericOAuthenticator.client_secret = client_secret
c.GenericOAuthenticator.oauth_callback_url = callback_url

# Request the 'openid' scope (required for OIDC)
# Note: oauthenticator expects a list
c.GenericOAuthenticator.scope = ['openid', 'profile', 'email']

# Use the token response to get user info instead of calling userdata_url
# This avoids the 401 error on the userinfo endpoint
c.GenericOAuthenticator.userdata_from_id_token = True

# Keycloak returns username in 'preferred_username' field
c.GenericOAuthenticator.username_claim = 'preferred_username'

# Allow any authenticated user
c.GenericOAuthenticator.allow_all = True

# Enable verbose logging for OAuth
c.GenericOAuthenticator.enable_auth_state = True

# Cookie configuration to fix OAuth state issues
# Set SameSite to Lax to allow OAuth callbacks from Keycloak
c.JupyterHub.cookie_options = {
    'samesite': 'Lax',
    'secure': False,  # Set to True if using HTTPS
}

# Allow OAuth state cookies to work across different hosts
c.GenericOAuthenticator.cookie_options = {
    'samesite': 'Lax',
    'secure': False,
}

# Optional: skip TLS verification for development (controlled by env var OAUTH_TLS_VERIFY)
tls_verify = os.environ.get('OAUTH_TLS_VERIFY', '1')
if tls_verify in ('0', 'false', 'False'):
    c.GenericOAuthenticator.tls_verify = False

# Optional: read admin list from env var and set c.Authenticator.admin_users
admins = os.environ.get('JUPYTERHUB_ADMIN_USERS')
if admins:
    c.Authenticator.admin_users = set([u.strip() for u in admins.split(',') if u.strip()])

# Spawner configuration
c.Spawner.default_url = '/lab'  # Use JupyterLab by default

# Create user directories automatically
c.Spawner.notebook_dir = '~/notebooks'

# Set environment variables for spawned servers
# These will be available in notebooks but hidden from users
MLFLOW_IP = os.environ.get('MLFLOW_IP', 'localhost')
MLFLOW_PORT = os.environ.get('MLFLOW_PORT', '5000')
MINIO_PORT = os.environ.get('MINIO_PORT', '9000')
MINIO_USER = os.environ.get('MINIO_USER', 'minioadmin')
MINIO_PASSWORD = os.environ.get('MINIO_PASSWORD', 'minioadmin')
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'mlflow')

c.Spawner.environment = {
    'JUPYTERHUB_SINGLEUSER_APP': 'jupyter_server.serverapp.ServerApp',
    # MLflow configuration
    'MLFLOW_IP': MLFLOW_IP,
    'MLFLOW_PORT': MLFLOW_PORT,
    # MinIO configuration
    'MINIO_PORT': MINIO_PORT,
    'MINIO_USER': MINIO_USER,
    'MINIO_PASSWORD': MINIO_PASSWORD,
    'MINIO_BUCKET': MINIO_BUCKET,
}

# Pre-spawn hook to create user if not exists
import pwd
import subprocess
import os

async def create_user_and_setup_spawner(spawner):
    """Create system user if it doesn't exist and configure spawner"""
    username = spawner.user.name
    
    # Check if user exists, if not create it
    try:
        user_info = pwd.getpwnam(username)
    except KeyError:
        # User doesn't exist, create it
        subprocess.run([
            'sudo', 'useradd', '-m', '-s', '/bin/bash', username
        ], check=True)
        subprocess.run([
            'sudo', 'mkdir', '-p', f'/home/{username}/notebooks'
        ], check=True)
        subprocess.run([
            'sudo', 'chown', '-R', f'{username}:{username}', f'/home/{username}'
        ], check=True)
        
        # Grant passwordless sudo access for this user
        sudoers_file = f'/etc/sudoers.d/jupyterhub-{username}'
        sudoers_content = f'{username} ALL=(ALL) NOPASSWD:ALL\n'
        subprocess.run([
            'sudo', 'bash', '-c', f'echo "{sudoers_content}" > {sudoers_file}'
        ], check=True)
        subprocess.run([
            'sudo', 'chmod', '0440', sudoers_file
        ], check=True)
        
        user_info = pwd.getpwnam(username)
    
    # Set the user for the spawned process
    # LocalProcessSpawner will use these to setuid/setgid
    import grp
    spawner.user_options = {}
    spawner.pre_spawn_start = lambda: None
    
    # Get user info
    uid = user_info.pw_uid
    gid = user_info.pw_gid
    
    # Store original make_preexec_fn
    original_make_preexec_fn = spawner.make_preexec_fn
    
    def custom_make_preexec_fn(name):
        """Custom preexec function to set user context"""
        def preexec():
            # Demote to user
            os.setgid(gid)
            os.setuid(uid)
            # Set home directory
            os.environ['HOME'] = f'/home/{username}'
            os.environ['USER'] = username
            os.environ['LOGNAME'] = username
            os.chdir(f'/home/{username}')
        return preexec
    
    spawner.make_preexec_fn = custom_make_preexec_fn

c.Spawner.pre_spawn_hook = create_user_and_setup_spawner

# Allow named servers (optional, for multiple notebooks per user)
c.JupyterHub.allow_named_servers = True

# Increase timeout for spawner start
c.Spawner.start_timeout = 60
c.Spawner.http_timeout = 60

# Enable debug logging
c.JupyterHub.log_level = 'DEBUG'
c.Spawner.debug = True
