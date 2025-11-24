# System Architecture - Notebook Database Management

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User / Client                            │
│  (Browser, Python scripts, cURL, or other HTTP clients)         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTP/REST API
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                   Docker Container: jhub                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  JupyterHub Service                    Port: 8000        │   │
│  │  - User authentication via Keycloak                      │   │
│  │  - Notebook interface                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Papermill API (FastAPI)               Port: 8002       │    │
│  │                                                         │    │
│  │  📡 Execution Endpoints:                                │    │
│  │    • /execute - Execute notebooks with parameters       │    │
│  │    • /run-notebook - Run with full paths                │    │
│  │    • /list-notebooks/{user} - List user notebooks       │    │
│  │                                                         │    │
│  │  🗄️  Database Endpoints:                                │    │
│  │    • /db/notebooks - CRUD for notebooks                 │    │
│  │    • /db/parameters - CRUD for parameters               │    │
│  │    • /db/executions - Query execution history           │    │
│  │                                                         │    │
│  │  📚 Documentation:                                      │    │
│  │    • /docs - Swagger UI                                 │    │
│  │    • /redoc - ReDoc                                     │    │
│  └────────────────────┬────────────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ PostgreSQL Connection
                          │ (host.docker.internal:5432)
                          │
┌─────────────────────────▼────────────────────────────────────────┐
│                PostgreSQL Database (Host)                        │
│                                                                  │
│  Database: notebook_manager                                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Table: notebooks                                        │    │
│  │  - id, name, description, file_path, username            │    │
│  │  - tags (JSON), metadata (JSON)                          │    │
│  │  - created_at, updated_at                                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Table: notebook_parameters                              │    │
│  │  - id, notebook_id (FK), param_name, param_type          │    │
│  │  - default_value (JSON), description                     │    │
│  │  - required, validation_rules (JSON)                     │    │
│  │  - created_at, updated_at                                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Table: notebook_executions                              │    │
│  │  - id, notebook_id (FK), username                        │    │
│  │  - input_path, output_path, parameters_used (JSON)       │    │
│  │  - status, error_message, execution_time_seconds         │    │
│  │  - started_at, completed_at                              │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## 🔄 Request Flow Examples

### 1. Register Notebook

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

### 2. Add Parameters

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

### 3. Execute Notebook with Parameters

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

### 4. Query Notebooks

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

## 📦 Component Details

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

### Scenario 1: Template-Based Reports
```
1. Register template notebook
2. Define standard parameters (month, region, etc.)
3. Execute monthly with different parameters
4. Track all report generations
```

### Scenario 2: ML Experiment Tracking
```
1. Register training notebook
2. Define hyperparameters as parameters
3. Run experiments with different configs
4. Query execution history to compare results
```

### Scenario 3: Automated Pipelines
```
1. Register data processing notebooks
2. Define data source parameters
3. Schedule executions via API
4. Monitor execution status
```

## 📁 File Structure

```
Notebook_Authen/
├── docker-compose.yml (Updated with DB env vars)
├── setup_database.sh (Automated setup)
├── example_notebook_manager.py (Python client)
├── test_database_api.py (Test suite)
│
├── Documentation/
│   ├── DATABASE_MANAGEMENT_GUIDE.md (Complete guide)
│   ├── QUICK_START_DB.md (Quick reference)
│   ├── IMPLEMENTATION_SUMMARY.md (Overview)
│   ├── SETUP_CHECKLIST.md (Setup steps)
│   └── ARCHITECTURE.md (This file)
│
└── jupyterhub/jupyterhub-server/
    ├── database.py (SQLAlchemy models)
    ├── init_db.py (Database initialization)
    ├── set_params.py (FastAPI application)
    ├── requirements.txt (Updated with DB deps)
    └── Dockerfile (Unchanged)
```

## 🔧 Technologies Used

- **FastAPI** - Modern web framework for building APIs
- **SQLAlchemy** - Python SQL toolkit and ORM
- **PostgreSQL** - Relational database
- **Pydantic** - Data validation using Python type annotations
- **Papermill** - Parameterized notebook execution
- **Docker** - Containerization
- **Uvicorn** - ASGI server
