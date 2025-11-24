# JupyterHub + Keycloak (Docker Compose)

This repository contains a minimal Docker Compose setup to run Keycloak (for OpenID Connect) and a JupyterHub instance configured to use Keycloak for authentication.

Files added
- `docker-compose.yml` — starts Keycloak and the `jhub` service (builds from `jupyterhub/jupyterhub-server`).
- `jupyterhub/jupyterhub-server/Dockerfile` — image for JupyterHub.
- `jupyterhub/jupyterhub-server/requirements.txt` — Python dependencies (jupyterhub, oauthenticator).
- `jupyterhub/jupyterhub-server/jupyterhub_config.py` — JupyterHub config using Keycloak OAuthenticator.
- `keycloak/config/jhub-realm.json` — sample realm import for Keycloak.

Quick setup

**Option 1: One-command complete setup (easiest)**

```bash
./complete-setup.sh
```

This automated script will:
- Detect and configure your server IP
- Stop any existing containers
- Start all services
- Wait for Keycloak to be ready
- Update Keycloak redirect URIs automatically
- Display all access information

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
sudo docker compose down
sudo docker compose up -d
# Wait for Keycloak to start (about 15 seconds)
sleep 15
./update-keycloak-redirect.sh
```

**Or use this one-liner:**
```bash
sudo docker compose down && sudo docker compose up -d && sleep 15 && ./update-keycloak-redirect.sh
```

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
docker-compose down  # Stop existing containers if running
docker-compose build
docker-compose up -d
```

**Accessing from other computers:**
- Make sure the `.env` file has the correct `HOST_IP` set to your server's IP or hostname
- Access JupyterHub at `http://YOUR_SERVER_IP:8000` (e.g., `http://192.168.1.100:8000`)
- Access Keycloak admin at `http://YOUR_SERVER_IP:8080` (user: `admin`, password: `secret`)
- Ensure firewall allows connections on ports 8000 and 8080

Notes & troubleshooting

- **Modern Keycloak**: This setup uses the newer `quay.io/keycloak/keycloak:23.0` image. The realm JSON is imported automatically from the `/opt/keycloak/data/import` directory on startup (using `--import-realm` flag).

- **HTTP for local dev**: The configuration uses HTTP (not HTTPS) for local development. You'll see warnings like "JupyterHub seems to be served over an unsecured HTTP connection". This is expected for local testing. For production, you **must**:
  - Enable HTTPS with valid certificates
  - Update all URLs to use `https://`
  - Run behind a reverse proxy (nginx, Traefik, etc.)

- **DNS and URL configuration**: The `docker-compose.yml` uses different URLs for different purposes:
  - `OAUTH2_AUTHORIZE_URL`: Uses `http://localhost:8080` (browser-accessible)
  - `OAUTH2_TOKEN_URL` and `OAUTH2_USERDATA_URL`: Use `http://keycloak:8080` (internal Docker network)
  
  This is required because your browser can't resolve the `keycloak` hostname (it only exists inside Docker's network), but JupyterHub server can communicate with Keycloak using the service name.

- **TLS verification**: `OAUTH_TLS_VERIFY=0` is set for development. Remove or set to `1` in production with proper certificates.

- Make sure the Keycloak client `jhub-1` has `Direct Access Grants`/`Authorization` enabled if needed and a proper `client secret` matching `OAUTH_CLIENT_SECRET`.

- Replace the development defaults (admin password, secrets) before deploying to production.

Next steps

- If you want, I can:
  1. Run `docker-compose up --build` here to start the services (I will only do that if you want me to), or
  2. Tweak `jupyterhub_config.py` to automatically map Keycloak groups/roles to JupyterHub admin users, or
  3. Add support for a proper HTTPS reverse proxy (Traefik / nginx) and generate self-signed certs for local test.
