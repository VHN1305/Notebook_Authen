# System Architecture - Integrated Data Science Platform

## 🏗️ High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        User / Client                                 │
│         (Browser, Python scripts, cURL, HTTP clients)                │
└────────────┬────────────────────────────────┬─────────────────────────┘
             │                                │
             │                                │
    ┌────────▼────────┐              ┌────────▼─────────┐
    │   JupyterHub    │              │    Superset      │
    │   Port: 8000    │              │   Port: 8088     │
    │                 │              │                  │
    │  - Notebooks    │              │  - Dashboards    │
    │  - Code Editor  │              │  - Charts        │
    │  - Terminals    │              │  - SQL Lab       │
    └────────┬────────┘              └────────┬─────────┘
             │                                │
             │         OAuth 2.0 / OIDC       │
             │         (Single Sign-On)       │
             └───────────────┬────────────────┘
                             │
                   ┌─────────▼──────────┐
                   │     Keycloak       │
                   │    Port: 8080      │
                   │                    │
                   │  - Authentication  │
                   │  - User Management │
                   │  - SSO Provider    │
                   └────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│                   Docker Container: jhub                             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  JupyterHub Service                    Port: 8000            │   │
│  │  - User authentication via Keycloak OAuth                    │   │
│  │  - Jupyter notebook interface                                │   │
│  │  - Terminal access                                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Papermill API (FastAPI)               Port: 8002           │    │
│  │                                                             │    │
│  │  📡 Execution Endpoints:                                    │    │
│  │    • /execute - Execute notebooks with parameters           │    │
│  │    • /run-notebook - Run with full paths                    │    │
│  │    • /list-notebooks/{user} - List user notebooks           │    │
│  │                                                             │    │
│  │  🗄️  Database Endpoints:                                    │    │
│  │    • /db/notebooks - CRUD for notebooks                     │    │
│  │    • /db/parameters - CRUD for parameters                   │    │
│  │    • /db/executions - Query execution history               │    │
│  │                                                             │    │
│  │  📚 Documentation:                                          │    │
│  │    • /docs - Swagger UI                                     │    │
│  │    • /redoc - ReDoc                                         │    │
│  └────────────────────┬────────────────────────────────────────┘    │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
                        │ PostgreSQL Connection
                        │
┌───────────────────────▼──────────────────────────────────────────────┐
│                   Docker Container: superset                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Apache Superset                       Port: 8088            │   │
│  │                                                              │   │
│  │  🔐 Custom OAuth Integration:                                │   │
│  │    • CustomAuthOAuthView - Handles OAuth callbacks          │   │
│  │    • Authlib state validation bypass for multi-URL access   │   │
│  │    • Automatic Admin role assignment                        │   │
│  │                                                              │   │
│  │  📊 Features:                                                │   │
│  │    • Interactive dashboards                                 │   │
│  │    • Chart builder                                          │   │
│  │    • SQL Lab for queries                                    │   │
│  │    • Database connections                                   │   │
│  │    • Keycloak SSO integration                               │   │
│  └────────────────────┬─────────────────────────────────────────┘   │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
                        │ PostgreSQL Connection
                        │ (Superset Metadata + User Data)
                        │
┌───────────────────────▼──────────────────────────────────────────────┐
│                PostgreSQL Database (Host or Container)               │
│                                                                      │
│  Database: notebook_manager                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Table: notebooks                                            │    │
│  │  - id, name, description, file_path, username                │    │
│  │  - tags (JSON), metadata (JSON)                              │    │
│  │  - created_at, updated_at                                    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Table: notebook_parameters                                  │    │
│  │  - id, notebook_id (FK), param_name, param_type              │    │
│  │  - default_value (JSON), description, required               │    │
│  │  - validation_rules (JSON), created_at, updated_at           │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Table: notebook_executions                                  │    │
│  │  - id, notebook_id (FK), username                            │    │
│  │  - input_path, output_path, parameters_used (JSON)           │    │
│  │  - status, error_message, execution_time_seconds             │    │
│  │  - started_at, completed_at                                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Database: superset (Superset metadata)                              │
│  - User accounts, roles, permissions                                 │
│  - Dashboard definitions, chart configs                              │
│  - Database connection strings                                       │
│  - SQL Lab query history                                             │
└──────────────────────────────────────────────────────────────────────┘
```

## 🔄 Request Flow Examples

### 1. OAuth Authentication Flow (JupyterHub/Superset → Keycloak)

```
Browser                JupyterHub/Superset      Keycloak
  │                           │                    │
  │──── Access Service ──────>│                    │
  │                           │                    │
  │                           │─── Redirect to ───>│
  │                           │    /auth endpoint  │
  │                           │                    │
  │<──────── Redirect to Keycloak login ───────────│
  │                                                 │
  │──── Enter credentials ─────────────────────────>│
  │                                                 │
  │<──── Authorization code ────────────────────────│
  │                           │                    │
  │── Redirect with code ────>│                    │
  │                           │                    │
  │                           │─── Exchange code ─>│
  │                           │    for token       │
  │                           │                    │
  │                           │<── Access token ───│
  │                           │                    │
  │                           │─── Get user info ─>│
  │                           │                    │
  │                           │<── User details ───│
  │                           │                    │
  │<─── Logged in, redirect ──│                    │
  │     to dashboard/home                          │
```

**Key Features:**
- Custom OAuth view bypasses state validation for multi-URL access
- Automatic user creation with Admin role (Superset)
- Session cookies set for authenticated access
- Works with both localhost and IP address URLs

### 2. Register Notebook

```
Client                  API                    Database
  │                      │                        │
  │─── POST /db/notebooks ──>                     │
  │    {name, path, user}                         │
  │                      │                        │
  │                      │─── INSERT INTO ──────>│
  │                      │    notebooks          │
  │                      │                        │
  │                      │<── Return notebook_id ─│
  │                      │                        │
  │<── 201 Created ──────│                        │
  │    {id, name, ...}                            │
```

### 3. Add Parameters

```
Client                  API                    Database
  │                      │                        │
  │─ POST /db/parameters ─>                       │
  │  {notebook_id, name,                          │
  │   type, default}                              │
  │                      │                        │
  │                      │─── INSERT INTO ──────>│
  │                      │    notebook_parameters│
  │                      │                        │
  │                      │<── Return param_id ───│
  │                      │                        │
  │<── 201 Created ──────│                        │
  │    {id, param_name...}                        │
```

### 4. Execute Notebook with Parameters

```
Client                  API                    Papermill
  │                      │                        │
  │──── POST /execute ───>                        │
  │  {user, path, params}                         │
  │                      │                        │
  │                      │─── (Optional) ─────────>
  │                      │    Query DB for        │
  │                      │    default params      │
  │                      │                        │
  │                      │─── Execute ──────────>│
  │                      │    pm.execute_notebook │
  │                      │                        │
  │                      │<── Execution result ───│
  │                      │                        │
  │                      │─── INSERT INTO ──────>│
  │                      │    notebook_executions │
  │                      │    (log execution)     │
  │                      │                        │
  │<─── 200 OK ──────────│                        │
  │  {status, timestamp}                          │
```

### 5. Query Notebooks

```
Client                  API                    Database
  │                      │                        │
  │─ GET /db/notebooks/user/testuser ───>        │
  │                      │                        │
  │                      │─── SELECT * FROM ────>│
  │                      │    notebooks          │
  │                      │    WHERE username=... │
  │                      │                        │
  │                      │<── Return rows ───────│
  │                      │                        │
  │<── 200 OK ───────────│                        │
  │  [{id, name, ...}]                            │
```

### 6. Superset Dashboard Access with OAuth

```
Browser                 Superset               Keycloak         Database
  │                        │                      │                │
  │── Access Dashboard ───>│                      │                │
  │                        │                      │                │
  │                        │─── OAuth redirect ──>│                │
  │<──── Login page ───────┼──────────────────────│                │
  │                                               │                │
  │── Enter credentials ──────────────────────────>│                │
  │                                               │                │
  │<── Authorization code ─────────────────────────│                │
  │                        │                      │                │
  │── Code + callback ────>│                      │                │
  │                        │                      │                │
  │                        │─── Exchange token ───>│                │
  │                        │                      │                │
  │                        │<── Access token ─────│                │
  │                        │                      │                │
  │                        │─── Get user info ────>│                │
  │                        │                      │                │
  │                        │<── User details ─────│                │
  │                        │                                       │
  │                        │─── Create/Update user ───────────────>│
  │                        │    (with Admin role)                  │
  │                        │                                       │
  │                        │<── User saved ───────────────────────│
  │                        │                                       │
  │<── Dashboard page ─────│                                       │
  │    (authenticated)                                             │
```

## 📦 Component Details

### Superset OAuth Configuration

```
┌─────────────────────────────────────────────────┐
│        Superset Custom OAuth Setup              │
├─────────────────────────────────────────────────┤
│                                                 │
│  CustomAuthOAuthView:                           │
│  ├─ oauth_authorized() override                 │
│  │  └─ Handles OAuth callback                   │
│  │     • Receives authorization code             │
│  │     • Exchanges code for token               │
│  │     • Fetches user info from Keycloak        │
│  │     • Creates/updates user with Admin role   │
│  │     • Logs user in via Flask-Login           │
│  │     • Redirects to dashboard                 │
│  │                                              │
│  Authlib Patch:                                 │
│  ├─ patch_authlib_state_validation()            │
│  │  └─ Bypasses OAuth state validation          │
│  │     • Manually exchanges authorization code  │
│  │     • Skips session cookie state check       │
│  │     • Enables multi-URL access               │
│  │                                              │
│  CustomSecurityManager:                         │
│  ├─ authoauthview = CustomAuthOAuthView         │
│  ├─ oauth_user_info() - Enhanced user mapping   │
│  └─ Registers custom OAuth view                 │
│                                                 │
│  Configuration (superset_config.py):            │
│  ├─ AUTH_TYPE = AUTH_OAUTH                      │
│  ├─ OAUTH_PROVIDERS with Keycloak config        │
│  └─ CUSTOM_SECURITY_MANAGER                     │
└─────────────────────────────────────────────────┘
```

### FastAPI Application (`set_params.py`)

```
┌──────────────────────────────────────────┐
│         FastAPI Application               │
├──────────────────────────────────────────┤
│                                           │
│  Pydantic Models:                         │
│  ├─ NotebookCreate/Update/Response        │
│  ├─ ParameterCreate/Update/Response       │
│  ├─ NotebookWithParameters                │
│  └─ ExecutionHistoryResponse              │
│                                           │
│  Endpoints:                               │
│  ├─ Notebook Management (8 endpoints)     │
│  ├─ Parameter Management (7 endpoints)    │
│  ├─ Execution History (3 endpoints)       │
│  └─ Legacy Execution (4 endpoints)        │
│                                           │
│  Dependencies:                            │
│  └─ get_db() - Database session           │
└──────────────────────────────────────────┘
```

### Database Layer (`database.py`)

```
┌──────────────────────────────────────────┐
│      SQLAlchemy ORM Layer                 │
├──────────────────────────────────────────┤
│                                           │
│  Models:                                  │
│  ├─ Notebook                              │
│  │  └─ One-to-Many → NotebookParameter    │
│  ├─ NotebookParameter                     │
│  │  └─ Many-to-One → Notebook             │
│  └─ NotebookExecution                     │
│     └─ Many-to-One → Notebook (optional)  │
│                                           │
│  Connection:                              │
│  ├─ Engine (PostgreSQL connection pool)   │
│  ├─ SessionLocal (session factory)        │
│  └─ get_db() (dependency injection)       │
│                                           │
│  Functions:                               │
│  ├─ init_db() - Create tables             │
│  └─ drop_db() - Drop tables               │
└──────────────────────────────────────────┘
```

## 🔐 Database Schema

### notebooks Table
```sql
┌─────────────┬──────────────┬──────────┬─────────┐
│   Column    │     Type     │ Nullable │  Key    │
├─────────────┼──────────────┼──────────┼─────────┤
│ id          │ INTEGER      │ NOT NULL │ PRIMARY │
│ name        │ VARCHAR(255) │ NOT NULL │ INDEX   │
│ description │ TEXT         │ NULL     │         │
│ file_path   │ VARCHAR(512) │ NOT NULL │ UNIQUE  │
│ username    │ VARCHAR(100) │ NOT NULL │ INDEX   │
│ created_at  │ TIMESTAMP    │ NOT NULL │         │
│ updated_at  │ TIMESTAMP    │ NOT NULL │         │
│ tags        │ JSON         │ NULL     │         │
│ metadata    │ JSON         │ NULL     │         │
└─────────────┴──────────────┴──────────┴─────────┘
Constraints:
  - UNIQUE(name, username)
```

### notebook_parameters Table
```sql
┌──────────────────┬──────────────┬──────────┬─────────┐
│     Column       │     Type     │ Nullable │  Key    │
├──────────────────┼──────────────┼──────────┼─────────┤
│ id               │ INTEGER      │ NOT NULL │ PRIMARY │
│ notebook_id      │ INTEGER      │ NOT NULL │ FOREIGN │
│ param_name       │ VARCHAR(100) │ NOT NULL │ INDEX   │
│ param_type       │ VARCHAR(50)  │ NOT NULL │         │
│ default_value    │ JSON         │ NULL     │         │
│ description      │ TEXT         │ NULL     │         │
│ required         │ INTEGER      │ NOT NULL │         │
│ validation_rules │ JSON         │ NULL     │         │
│ created_at       │ TIMESTAMP    │ NOT NULL │         │
│ updated_at       │ TIMESTAMP    │ NOT NULL │         │
└──────────────────┴──────────────┴──────────┴─────────┘
Constraints:
  - FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
  - UNIQUE(notebook_id, param_name)
```

### notebook_executions Table
```sql
┌──────────────────────────┬──────────────┬──────────┬─────────┐
│        Column            │     Type     │ Nullable │  Key    │
├──────────────────────────┼──────────────┼──────────┼─────────┤
│ id                       │ INTEGER      │ NOT NULL │ PRIMARY │
│ notebook_id              │ INTEGER      │ NULL     │ FOREIGN │
│ username                 │ VARCHAR(100) │ NOT NULL │ INDEX   │
│ input_path               │ VARCHAR(512) │ NOT NULL │         │
│ output_path              │ VARCHAR(512) │ NULL     │         │
│ parameters_used          │ JSON         │ NULL     │         │
│ status                   │ VARCHAR(50)  │ NOT NULL │         │
│ error_message            │ TEXT         │ NULL     │         │
│ execution_time_seconds   │ INTEGER      │ NULL     │         │
│ started_at               │ TIMESTAMP    │ NOT NULL │         │
│ completed_at             │ TIMESTAMP    │ NULL     │         │
└──────────────────────────┴──────────────┴──────────┴─────────┘
Constraints:
  - FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
```

## 🔌 API Endpoint Map

```
/
├── / (GET) - API info
├── /health (GET) - Health check
├── /docs (GET) - Swagger UI
├── /redoc (GET) - ReDoc
│
├── /execute (POST) - Execute notebook (user-based)
├── /run-notebook (POST) - Execute notebook (simple)
├── /execute-notebook (POST) - Execute notebook (full)
├── /list-notebooks/{username} (GET) - List user notebooks
│
├── /db/
│   ├── /notebooks
│   │   ├── (GET) - List notebooks
│   │   ├── (POST) - Create notebook
│   │   ├── /{id} (GET) - Get notebook with params
│   │   ├── /{id} (PUT) - Update notebook
│   │   ├── /{id} (DELETE) - Delete notebook
│   │   └── /user/{username} (GET) - Get user notebooks
│   │
│   ├── /parameters
│   │   ├── (POST) - Create parameter
│   │   ├── /bulk/{notebook_id} (POST) - Create multiple
│   │   ├── /notebook/{id} (GET) - Get notebook params
│   │   ├── /{id} (GET) - Get parameter
│   │   ├── /{id} (PUT) - Update parameter
│   │   └── /{id} (DELETE) - Delete parameter
│   │
│   └── /executions
│       ├── (GET) - List executions
│       ├── /notebook/{id} (GET) - Get notebook executions
│       └── /{id} (GET) - Get execution
```

## 📊 Data Flow

```
1. Register Notebook → Store in DB
                     ↓
2. Define Parameters → Link to Notebook
                     ↓
3. Execute Notebook  → Use Parameters
                     ↓
4. Log Execution     → Store Results
                     ↓
5. Query History     → Analyze Results
```

## 🎯 Use Case Scenarios

### Scenario 1: End-to-End Data Analysis Workflow
```
1. Data scientist logs in via Keycloak SSO
   ├─ Access to JupyterHub (port 8000)
   └─ Access to Superset (port 8088)

2. Develop analysis in JupyterHub
   ├─ Write Python/R code in notebooks
   ├─ Query database for data
   └─ Register notebook with parameters

3. Execute parameterized notebook
   ├─ Define parameters (date range, filters)
   ├─ Run via Papermill API
   └─ Track execution history

4. Visualize results in Superset
   ├─ Connect to same database
   ├─ Create charts from notebook outputs
   ├─ Build interactive dashboard
   └─ Share with stakeholders
```

### Scenario 2: Template-Based Reports with Visualization
```
1. Register template notebook for monthly reports
2. Define standard parameters (month, region, product)
3. Execute monthly with different parameters
4. Output results to database tables
5. Create Superset dashboard connected to output tables
6. Schedule automatic report generation
7. Monitor execution history and dashboard usage
```

### Scenario 3: ML Experiment Tracking & Monitoring
```
1. Register training notebooks with hyperparameters
2. Run experiments with different configurations via API
3. Store results in database (metrics, model paths)
4. Query execution history to compare runs
5. Visualize experiment results in Superset
   ├─ Compare accuracy across runs
   ├─ Track training time trends
   └─ Monitor resource usage
6. Share best model dashboards with team
```

### Scenario 4: Collaborative Data Science Platform
```
1. Multiple users authenticated via Keycloak
2. Each user has isolated JupyterHub environment
3. Shared database for collaborative queries
4. Common Superset instance for dashboards
5. Role-based access control via Keycloak
6. Audit trail in execution history
```

## 📁 File Structure

```
Notebook_Authen/
├── docker-compose.yml (All services: Keycloak, JupyterHub, Superset)
├── setup_database.sh (Automated database setup)
├── example_notebook_manager.py (Python client)
├── test_database_api.py (Test suite)
│
├── Documentation/
│   ├── README.md (Main documentation)
│   ├── ARCHITECTURE.md (This file - System architecture)
│   ├── SUPERSET_SETUP_GUIDE.md (Superset configuration)
│   ├── QUICK_START_DB.md (Quick database reference)
│   ├── API_QUICK_REFERENCE.md (API documentation)
│   └── IMPLEMENTATION_SUMMARY.md (Implementation overview)
│
├── jupyterhub/jupyterhub-server/
│   ├── Dockerfile (JupyterHub container)
│   ├── requirements.txt (Python dependencies)
│   ├── jupyterhub_config.py (JupyterHub + Keycloak config)
│   ├── database.py (SQLAlchemy models)
│   ├── init_db.py (Database initialization)
│   └── set_params.py (FastAPI application)
│
├── superset/
│   ├── Dockerfile (Superset with custom patches)
│   ├── superset_config.py (Custom OAuth + Keycloak integration)
│   ├── superset_init.sh (Initialization script)
│   └── init_superset_db.sql (Database schema)
│
└── keycloak/config/
    └── jhub-realm.json (Realm with OAuth clients for all services)
```

## 🔧 Technologies Used

### Core Infrastructure
- **Docker & Docker Compose** - Containerization and orchestration
- **Keycloak 23.0** - Identity and access management (IAM)
- **PostgreSQL** - Relational database for data and metadata

### Application Services
- **JupyterHub** - Multi-user notebook server
- **Apache Superset 3.0** - Data visualization and business intelligence
- **FastAPI** - Modern web framework for REST APIs
- **Papermill** - Parameterized notebook execution

### Backend Libraries
- **SQLAlchemy** - Python SQL toolkit and ORM
- **Pydantic** - Data validation using type annotations
- **Authlib** - OAuth and OpenID Connect library
- **Flask-AppBuilder** - Application framework (used by Superset)
- **Flask-Login** - User session management

### OAuth & Security
- **OpenID Connect (OIDC)** - Authentication protocol
- **OAuth 2.0** - Authorization framework
- **Custom OAuth patches** - Multi-URL access support

### Frontend & API
- **Uvicorn** - ASGI server for FastAPI
- **Swagger UI / ReDoc** - API documentation
- **React** - Frontend framework (Superset UI)

## 🔐 Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Keycloak (IAM)                        │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Realm: jhub                                     │   │
│  │                                                  │   │
│  │  OAuth Clients:                                  │   │
│  │  ├─ jupyterhub-client (JupyterHub)              │   │
│  │  │  └─ Redirect: http://HOST:8000/oauth_callback│   │
│  │  │                                               │   │
│  │  └─ superset-client (Superset)                   │   │
│  │     └─ Redirect: http://HOST:8088/oauth-authorized/│
│  │                  keycloak                        │   │
│  │                                                  │   │
│  │  Users & Roles:                                  │   │
│  │  ├─ User accounts with credentials               │   │
│  │  ├─ Groups for role management                   │   │
│  │  └─ Role mappings (optional)                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           │ OAuth 2.0 / OIDC
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ▼                                     ▼
┌──────────────────┐              ┌──────────────────┐
│   JupyterHub     │              │    Superset      │
│                  │              │                  │
│  Authentication: │              │  Authentication: │
│  ├─ OAuth via    │              │  ├─ Custom OAuth │
│  │  GenericOAuth│              │  │  View          │
│  │  Authenticator│              │  ├─ Authlib patch│
│  │              │              │  ├─ Auto Admin    │
│  └─ User session │              │  │  role assign  │
│     management   │              │  └─ Flask-Login  │
└──────────────────┘              └──────────────────┘
```

**Security Features:**
- Single Sign-On (SSO) across all services
- Centralized user management in Keycloak
- OAuth 2.0 authorization code flow with PKCE
- Session-based authentication after OAuth
- Automatic role assignment based on OAuth
- State validation bypass for flexible deployment (dev only)
- HTTPS recommended for production

## 🌐 Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                       │
│                (notebook_authen_default)                │
│                                                         │
│  ┌─────────────────┐    ┌─────────────────┐           │
│  │   Keycloak      │    │   JupyterHub    │           │
│  │   Container     │◄───┤   Container     │           │
│  │   Port: 8080    │    │   Port: 8000    │           │
│  │                 │    │   Port: 8002    │           │
│  │   hostname:     │    │                 │           │
│  │   keycloak      │    │   hostname:     │           │
│  └────────┬────────┘    │   jhub          │           │
│           │             └────────┬────────┘           │
│           │                      │                    │
│           │             ┌────────▼────────┐           │
│           └────────────►│   Superset      │           │
│                         │   Container     │           │
│                         │   Port: 8088    │           │
│                         │                 │           │
│                         │   hostname:     │           │
│                         │   superset      │           │
│                         └────────┬────────┘           │
│                                  │                    │
└──────────────────────────────────┼─────────────────────┘
                                   │
                                   │ Database Connection
                                   │
                         ┌─────────▼──────────┐
                         │   PostgreSQL       │
                         │   (Host/Container) │
                         │   Port: 5432       │
                         └────────────────────┘
```

**Network Configuration:**
- All services in same Docker network for internal communication
- Services use Docker hostnames (keycloak, jhub, superset) for inter-service calls
- External access via HOST_IP environment variable
- Ports 8000, 8080, 8088 exposed to host
- PostgreSQL accessible via host.docker.internal or container network

## 🚀 Deployment Considerations

### Development Setup
- HTTP protocol (no SSL/TLS)
- localhost or IP address access
- Embedded databases acceptable
- OAuth state validation bypassed
- Default credentials (change in production!)

### Production Setup
- ✅ HTTPS with valid SSL certificates
- ✅ Reverse proxy (nginx, Traefik, Caddy)
- ✅ Single public domain/hostname
- ✅ External PostgreSQL cluster
- ✅ Enable OAuth state validation
- ✅ Strong passwords and secrets
- ✅ Firewall rules and network security
- ✅ Regular backups
- ✅ Monitoring and logging
- ✅ Container orchestration (Kubernetes, Docker Swarm)

### Scaling Considerations
- JupyterHub can spawn multiple single-user servers
- Superset supports horizontal scaling with load balancer
- PostgreSQL can be clustered for high availability
- Keycloak supports clustering for HA
- Consider object storage for notebook outputs
