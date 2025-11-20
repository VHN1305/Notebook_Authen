# JupyterHub + Keycloak (Docker Compose)

This repository contains a minimal Docker Compose setup to run Keycloak (for OpenID Connect) and a JupyterHub instance configured to use Keycloak for authentication.

Files added
- `docker-compose.yml` — starts Keycloak and the `jhub` service (builds from `jupyterhub/jupyterhub-server`).
- `jupyterhub/jupyterhub-server/Dockerfile` — image for JupyterHub.
- `jupyterhub/jupyterhub-server/requirements.txt` — Python dependencies (jupyterhub, oauthenticator).
- `jupyterhub/jupyterhub-server/jupyterhub_config.py` — JupyterHub config using Keycloak OAuthenticator.
- `keycloak/config/jhub-realm.json` — sample realm import for Keycloak.

Quick setup

1. Edit the Keycloak client secret in `keycloak/config/jhub-realm.json` or configure a client in the Keycloak admin UI after startup. Replace the placeholder `REPLACE_WITH_CLIENT_SECRET`.

2. Update `docker-compose.yml` with the same secret for `OAUTH_CLIENT_SECRET` in the `jhub` service.

3. (Optional) Set `JUPYTERHUB_CRYPT_KEY` to a random value (32+ bytes base64 or hex) for cookie/encryption security.

Build and run

Run these commands from the repository root:

```bash
docker-compose build
docker-compose up -d
```

Open Keycloak admin at http://localhost:8080 (user: `admin`, password: `secret`). The realm `jhub` and client should be imported automatically from `keycloak/config/` on startup. 

Access JupyterHub at http://localhost:8000 and click "Sign in with Keycloak" to authenticate.

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
