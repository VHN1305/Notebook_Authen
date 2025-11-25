# JupyterHub + Keycloak + Superset + Notebook Management (Docker Compose)

This repository contains a Docker Compose setup to run:
- **Keycloak** for OpenID Connect authentication (SSO)
- **JupyterHub** with Keycloak integration for notebook environment
- **Apache Superset** with Keycloak OAuth for data visualization and dashboards
- **Papermill API** for notebook execution with parameters
- **PostgreSQL Database** for notebook and parameter management

## 🌟 Key Features

### Authentication & Security
- ✅ **Single Sign-On (SSO)** - One login for all services via Keycloak
- ✅ **OAuth 2.0 / OpenID Connect** - Industry-standard authentication
- ✅ **Multi-URL Access** - Works with both localhost and IP address access
- ✅ **Custom OAuth State Handling** - Bypasses session cookie limitations for flexible deployment

### Data Visualization with Superset
- ✅ **Apache Superset 3.0** - Modern data visualization and business intelligence platform
- ✅ **Keycloak Integration** - Automatic login with SSO
- ✅ **Admin Role Assignment** - OAuth users get Admin privileges automatically
- ✅ **Database Connectivity** - Connect to PostgreSQL and other data sources

### Notebook Management
- ✅ **Register notebooks** in database with metadata (tags, descriptions)
- ✅ **Define parameters** for each notebook with validation rules
- ✅ **Track execution history** with parameters used
- ✅ **Query notebooks** by user, tags, or other criteria
- ✅ **Execute notebooks** with custom parameters via REST API

**Quick Start for Database Features:**
```bash
# One-command setup
./setup_database.sh
```

**🔗 Service Access URLs:**
- **JupyterHub**: http://localhost:8000 or http://YOUR_IP:8000
- **Superset**: http://localhost:8088 or http://YOUR_IP:8088
- **Papermill API**: http://localhost:8002
- **API Documentation**: http://localhost:8002/docs
- **Keycloak Admin**: http://localhost:8080 (admin/secret)

**📚 Documentation:**
- **[QUICK_START_DB.md](QUICK_START_DB.md)** - Quick reference for database features
- **[SUPERSET_SETUP_GUIDE.md](SUPERSET_SETUP_GUIDE.md)** - Superset configuration and OAuth setup
- **[API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md)** - Original Papermill API reference

## Files Structure
- `docker-compose.yml` — starts Keycloak, JupyterHub, and Superset services
- `jupyterhub/jupyterhub-server/` — JupyterHub Docker image and configuration
  - `Dockerfile` — JupyterHub container image
  - `requirements.txt` — Python dependencies (jupyterhub, oauthenticator)
  - `jupyterhub_config.py` — JupyterHub config using Keycloak OAuthenticator
- `superset/` — Apache Superset configuration
  - `Dockerfile` — Superset container with custom OAuth patches
  - `superset_config.py` — Custom OAuth handling for multi-URL access
  - `superset_init.sh` — Initialization script for database and admin user
- `keycloak/config/jhub-realm.json` — Keycloak realm configuration with OAuth clients

## Quick Setup

**Option 1: One-command complete setup (easiest)**

```bash
./complete-setup.sh
```

This automated script will:
- Detect and configure your server IP
- Stop any existing containers
- Start all services (Keycloak, JupyterHub, Superset)
- Wait for Keycloak to be ready
- Update Keycloak redirect URIs automatically
- Display all access information

**What you get:**
- JupyterHub at http://YOUR_IP:8000
- Superset at http://YOUR_IP:8088
- Keycloak at http://YOUR_IP:8080
- All services use SSO authentication

**Option 2: Step-by-step automated setup**

Run the setup script to automatically detect and configure your server IP:
```bash
./setup-host-ip.sh
```

This script will:
- Detect available IP addresses on your server
- Let you choose which one to use
- Create the `.env` file with the correct configuration

After running the setup script, start the services and update Keycloak:
```bash
docker compose down
HOST_IP=YOUR_IP docker compose up -d
# Wait for Keycloak to start (about 15 seconds)
sleep 15
./update-keycloak-redirect.sh
```

**Or use this one-liner:**
```bash
docker compose down && HOST_IP=YOUR_IP docker compose up -d && sleep 15 && ./update-keycloak-redirect.sh
```

**Note:** Replace `YOUR_IP` with your actual IP address (e.g., 192.168.180.241)

**Option 3: Manual setup**

1. **Configure the host IP address**: Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set `HOST_IP` to your server's IP address or hostname:
   ```bash
   # For local access only
   HOST_IP=localhost
   
   # For access from other computers on your network
   HOST_IP=192.168.1.100  # Replace with your actual IP
   
   # Or use a hostname/domain
   HOST_IP=myserver.example.com
   ```
   
   **Important**: You can find your server's IP address using:
   ```bash
   # On Linux
   hostname -I | awk '{print $1}'
   # or
   ip addr show | grep "inet " | grep -v 127.0.0.1
   ```

2. Edit the Keycloak client secret in `keycloak/config/jhub-realm.json` or configure a client in the Keycloak admin UI after startup. Replace the placeholder `REPLACE_WITH_CLIENT_SECRET`.

3. Update `docker-compose.yml` with the same secret for `OAUTH_CLIENT_SECRET` in the `jhub` service.

4. (Optional) Set `JUPYTERHUB_CRYPT_KEY` to a random value (32+ bytes base64 or hex) for cookie/encryption security.

Build and run

Run these commands from the repository root:

```bash
# Make sure you have created and configured the .env file first!
docker compose down  # Stop existing containers if running
docker compose build
HOST_IP=YOUR_IP docker compose up -d
```

**Important:** Set `HOST_IP` environment variable to enable access from other computers:
```bash
# For localhost only
docker compose up -d

# For network access (replace with your actual IP)
HOST_IP=192.168.180.241 docker compose up -d
```

**Accessing the services:**
- **JupyterHub**: http://YOUR_IP:8000 - Launch Jupyter notebooks
- **Superset**: http://YOUR_IP:8088 - Create dashboards and visualizations  
- **Keycloak Admin**: http://YOUR_IP:8080 - Manage users and authentication (admin/secret)
- Ensure firewall allows connections on ports 8000, 8080, and 8088

## Using Superset for Data Visualization

1. **Login to Superset** at http://YOUR_IP:8088
   - Click "Sign in with Keycloak"
   - Use your Keycloak credentials (e.g., testuser/password)
   - You'll be automatically logged in with Admin privileges

2. **Connect to Database**
   - Go to Settings → Database Connections
   - Add a new database (PostgreSQL, MySQL, etc.)
   - Create datasets from your tables

3. **Create Charts and Dashboards**
   - Navigate to Charts → Create new chart
   - Select your dataset and visualization type
   - Build interactive dashboards

**Note:** OAuth users are automatically assigned Admin role for full access to all features.

## Notes & Troubleshooting

### General Configuration

- **Modern Keycloak**: This setup uses `quay.io/keycloak/keycloak:23.0`. The realm JSON is imported automatically from `/opt/keycloak/data/import` on startup (using `--import-realm` flag).

- **HTTP for local dev**: The configuration uses HTTP (not HTTPS) for local development. For production, you **must**:
  - Enable HTTPS with valid certificates
  - Update all URLs to use `https://`
  - Run behind a reverse proxy (nginx, Traefik, etc.)

- **TLS verification**: `OAUTH_TLS_VERIFY=0` is set for development. Remove or set to `1` in production with proper certificates.

### OAuth State Validation

This setup includes **custom OAuth state handling** to support multi-URL access (localhost + IP address):

- **Problem**: Flask-AppBuilder's default OAuth stores state in session cookies that are domain-specific, causing "mismatching_state" errors when accessing via different URLs
- **Solution**: Custom `AuthOAuthView` that bypasses state validation and manually completes OAuth flow
- **Result**: SSO works seamlessly whether you access via localhost or IP address

**Technical Details:**
- `superset/superset_config.py` contains:
  - `patch_authlib_state_validation()` - Patches Authlib to bypass state checks
  - `CustomAuthOAuthView` - Custom OAuth callback handler
  - `CustomSecurityManager` - Registers custom view and handles user info

### Superset-Specific Issues

**"Forbidden" errors after login:**
- Ensure OAuth users are assigned Admin role (handled automatically in this setup)
- Check logs: `docker logs notebook_authen-superset-1 | grep CUSTOM`

**OAuth callback not working:**
- Verify `HOST_IP` environment variable is set correctly
- Check Keycloak redirect URIs include your access URL
- Monitor logs for 🔵 🟢 🔴 emoji markers showing OAuth flow steps

**Database connection issues:**
- Superset needs to initialize its metadata database on first run
- Wait 20-30 seconds after starting for initialization to complete
- Check logs: `docker logs notebook_authen-superset-1`

### DNS and URL Configuration

The `docker-compose.yml` uses different URLs for different purposes:
- **Browser URLs**: Use `http://localhost:8080` or `http://YOUR_IP:8080` (browser-accessible)
- **Internal URLs**: Use `http://keycloak:8080` (Docker network communication)

This is required because browsers can't resolve the `keycloak` hostname (it only exists inside Docker's network), but services can communicate using Docker service names.

### Security Considerations

- Replace development defaults (admin password, secrets) before deploying to production
- Keycloak clients should have proper `client_secret` matching environment variables
- Enable HTTPS for production deployments
- Use strong passwords and enable 2FA in Keycloak for production users

## Architecture Overview

```
┌─────────────┐         ┌──────────────┐         ┌────────────────┐
│   Browser   │────────▶│   Keycloak   │◀────────│  JupyterHub    │
│  (User)     │         │   (SSO/Auth) │         │  (Notebooks)   │
└─────────────┘         └──────────────┘         └────────────────┘
                               │                          
                               │                  ┌────────────────┐
                               └─────────────────▶│   Superset     │
                                                  │ (Dashboards)   │
                                                  └────────────────┘
                                                          │
                                                          ▼
                                                  ┌────────────────┐
                                                  │   PostgreSQL   │
                                                  │   (Database)   │
                                                  └────────────────┘
```

**OAuth Flow:**
1. User clicks "Sign in with Keycloak" on JupyterHub or Superset
2. Redirected to Keycloak for authentication
3. After login, Keycloak redirects back with authorization code
4. Application exchanges code for access token (custom handler bypasses state validation)
5. User info retrieved from Keycloak
6. User automatically created/updated with appropriate roles
7. User logged in and redirected to application home page

## Next Steps

- **View Superset documentation**: See [SUPERSET_SETUP_GUIDE.md](SUPERSET_SETUP_GUIDE.md) for detailed configuration
- **Configure database connections**: Connect Superset to your data sources
- **Create Keycloak users**: Add users and groups in Keycloak admin console
- **Set up HTTPS**: Configure reverse proxy with SSL certificates for production
- **Customize roles**: Map Keycloak groups to application roles

## Contributing

Feel free to submit issues and pull requests to improve this setup!
