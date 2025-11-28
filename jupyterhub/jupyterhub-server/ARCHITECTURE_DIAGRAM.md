# System Architecture Diagram

## Complete AutoML Workflow with MinIO Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENT APPLICATION                         │
│                    (AutoML Configuration Interface)                  │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ HTTP REST API
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI SERVER                                │
│                    (Port 8002, set_params.py)                       │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ MINIO TEMPLATE MANAGEMENT                                   │   │
│  │  POST   /minio/upload-template      → Upload notebook       │   │
│  │  GET    /minio/list-templates       → List all templates    │   │
│  │  GET    /minio/get-template/{name}  → Get template info     │   │
│  │  DELETE /minio/delete-template      → Delete template       │   │
│  │  GET    /minio/download-url         → Presigned URL         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ NOTEBOOK CREATION FROM TEMPLATE                             │   │
│  │  POST /create-from-template → Download from MinIO           │   │
│  │                               + Inject parameters           │   │
│  │                               + Save to user directory      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ NOTEBOOK EXECUTION (Async with MLflow Kernel)               │   │
│  │  POST /execute-notebook     → Execute in background         │   │
│  │                               + Return after first cell     │   │
│  │  POST /execute              → In-place execution            │   │
│  │  GET  /execution-status/{id}→ Check status                  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ LEGACY ENDPOINTS (Maintained for compatibility)             │   │
│  │  POST /submit-notebook      → Database-based submission     │   │
│  │  GET  /notebooks            → List notebooks                │   │
│  │  GET  /notebook/{id}        → Get notebook by ID            │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────┬──────────────────┬──────────────────┬───────────────────┘
           │                  │                  │
           │                  │                  │
           ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────┐  ┌────────────────────┐
│  MinIO Client    │  │  Papermill   │  │  Database Client   │
│ (minio_client.py)│  │  + nbformat  │  │  (database.py)     │
└─────────┬────────┘  └──────┬───────┘  └─────────┬──────────┘
          │                  │                     │
          │                  │                     │
          ▼                  ▼                     ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  MinIO Server   │  │  Jupyter     │  │  PostgreSQL          │
│  Port: 9000     │  │  Kernel      │  │  Port: 5432          │
│  User: minioadmin│  │  (mlflow_env)│  │  DB: notebook_manager│
│                 │  │              │  │                      │
│  Bucket:        │  │  MLflow 2.8.0│  │  Tables:             │
│  notebook-      │  │  + 40 libs   │  │  - notebooks         │
│  templates/     │  │              │  │  - notebook_params   │
│  ├── ml/        │  │              │  │  - notebook_execs    │
│  ├── etl/       │  │              │  │                      │
│  └── analysis/  │  │              │  │                      │
└─────────────────┘  └──────────────┘  └──────────────────────┘
```

## Request Flow: Complete Workflow

### 1️⃣ Upload Template (Admin/Template Creator)
```
User → POST /minio/upload-template
      ├─ Upload: automl_template.ipynb
      ├─ Category: "ml"
      └─ Description: "AutoML classification template"
      
FastAPI → minio_client.upload_notebook()
         └─ MinIO: Save to notebook-templates/ml/automl_template.ipynb
         
FastAPI → database.py (optional)
         └─ PostgreSQL: INSERT INTO notebooks (template metadata)
         
Response ← {status: "success", template_name: "ml/automl_template.ipynb"}
```

### 2️⃣ List Available Templates (Client Discovery)
```
User → GET /minio/list-templates?category=ml

FastAPI → minio_client.list_notebooks(prefix="ml/")
         └─ MinIO: List objects in notebook-templates/ml/
         
Response ← {templates: [{name: "ml/automl_template.ipynb", size: 12345, ...}]}
```

### 3️⃣ Create Notebook from Template (Client Execution)
```
User → POST /create-from-template
      ├─ template_name: "ml/automl_template.ipynb"
      ├─ target_directory: "/home/user1/notebooks"
      ├─ parameters: {dataset_path: "/data/train.csv", model: "xgboost"}
      └─ new_name: "my_automl_run.ipynb"
      
FastAPI → minio_client.get_notebook_content("ml/automl_template.ipynb")
         └─ MinIO: Download template to memory
         
FastAPI → papermill.inject_parameters()
         └─ Inject parameters into notebook cells
         
FastAPI → Save to /home/user1/notebooks/my_automl_run.ipynb

FastAPI → database.py (optional)
         └─ PostgreSQL: INSERT INTO notebooks
         
Response ← {
  status: "success",
  new_notebook_path: "/home/user1/notebooks/my_automl_run.ipynb",
  parameters_applied: {...}
}
```

### 4️⃣ Execute Notebook (Async Execution)
```
User → POST /execute-notebook
      ├─ notebook_path: "/home/user1/notebooks/my_automl_run.ipynb"
      └─ username: "user1"
      
FastAPI → database.py
         └─ PostgreSQL: INSERT INTO notebook_executions
            (status="pending", start_time=now())
            
FastAPI → Start background thread (execute_notebook_background)
         └─ Thread: papermill.execute_notebook(kernel_name="mlflow_kernel")
         
FastAPI → Monitor first cell (30s timeout)
         └─ Thread: check_first_cell_execution()
         
Response ← {
  status: "running",
  execution_id: 1,
  notebook_url: "http://localhost:8888/user/user1/notebooks/my_automl_run.ipynb",
  status_url: "/execution-status/1"
}
[API returns in ~1.5 seconds, notebook continues running]

Background Thread continues:
├─ Execute all cells with MLflow 2.8.0 kernel
├─ Track experiment with MLflow
├─ Generate outputs
└─ Update database: status="success", end_time=now()
```

### 5️⃣ Check Execution Status (Progress Monitoring)
```
User → GET /execution-status/1

FastAPI → database.py
         └─ PostgreSQL: SELECT * FROM notebook_executions WHERE id=1
         
Response ← {
  execution_id: 1,
  status: "success",
  notebook_path: "/home/user1/notebooks/my_automl_run.ipynb",
  start_time: "2024-01-15T10:00:00",
  end_time: "2024-01-15T10:05:30",
  duration: "5m 30s"
}
```

## Data Flow Diagram

```
┌──────────────────┐
│  Template Store  │
│     (MinIO)      │
│                  │
│  ml/             │
│  ├─ automl.ipynb │
│  ├─ clf.ipynb    │
│  └─ reg.ipynb    │
└────────┬─────────┘
         │
         │ 1. Download Template
         ▼
┌──────────────────┐
│   FastAPI        │
│  (set_params.py) │
│                  │
│  Template Dict   │
│  + Parameters    │
└────────┬─────────┘
         │
         │ 2. Inject Parameters
         │    (papermill)
         ▼
┌──────────────────┐
│  User Directory  │
│  /home/user1/    │
│  notebooks/      │
│                  │
│  my_run.ipynb    │ ← Parametrized notebook
└────────┬─────────┘
         │
         │ 3. Execute with MLflow Kernel
         ▼
┌──────────────────┐
│  Jupyter Kernel  │
│  (mlflow_env)    │
│                  │
│  MLflow 2.8.0    │
│  + Libraries     │
└────────┬─────────┘
         │
         │ 4. Track & Log
         ▼
┌──────────────────┐
│  MLflow Server   │
│  (Experiments)   │
│                  │
│  Run 1: XGBoost  │
│  Accuracy: 0.95  │
└──────────────────┘
```

## Component Interactions

```
┌─────────────────────────────────────────────────────────┐
│                    JUPYTERHUB CONTAINER                  │
│                                                          │
│  ┌────────────────────────────────────────────────┐   │
│  │  FastAPI Server (Port 8002)                     │   │
│  │  - REST API Endpoints                           │   │
│  │  - Request routing                              │   │
│  │  - Background task management                   │   │
│  └────────────┬──────────────────────────┬─────────┘   │
│               │                          │              │
│               ▼                          ▼              │
│  ┌────────────────────┐    ┌─────────────────────┐    │
│  │  minio_client.py   │    │  database.py        │    │
│  │  - MinIO ops       │    │  - SQLAlchemy ORM   │    │
│  │  - S3 protocol     │    │  - Models & queries │    │
│  └────────┬───────────┘    └──────────┬──────────┘    │
│           │                           │                 │
│  ┌────────┴───────────────────────────┴──────────┐    │
│  │  JupyterHub Server (Port 8000)                 │    │
│  │  - User authentication                         │    │
│  │  - Notebook server spawning                    │    │
│  │  - Kernel management                           │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  MLflow Kernel (/opt/mlflow_env)               │    │
│  │  - Python 3.x + MLflow 2.8.0                   │    │
│  │  - 40+ scientific libraries                     │    │
│  │  - Registered as "mlflow_kernel"                │    │
│  └────────────────────────────────────────────────┘    │
└──────────────────┬───────────────────────┬─────────────┘
                   │                       │
                   │                       │
    ┌──────────────▼─────────┐   ┌────────▼──────────┐
    │  MinIO Container       │   │  PostgreSQL       │
    │  Port: 9000-9001       │   │  Port: 5432       │
    │  Bucket: templates     │   │  DB: notebook_mgr │
    └────────────────────────┘   └───────────────────┘
```

## Technology Stack

### Backend Services
- **FastAPI 2.0.0**: REST API framework (async support)
- **Uvicorn**: ASGI server
- **SQLAlchemy 2.0+**: ORM for database operations
- **Papermill**: Notebook parameterization & execution
- **nbformat**: Notebook file manipulation

### Storage Layer
- **MinIO**: S3-compatible object storage for templates
- **PostgreSQL**: Relational database for metadata
- **Filesystem**: User notebook storage

### Execution Environment
- **JupyterHub 4.0.2**: Multi-user notebook server
- **JupyterLab**: Web-based IDE
- **Custom Kernel**: mlflow_kernel with MLflow 2.8.0
- **Python Libraries**: 40+ data science packages

### Integration
- **Docker Compose**: Container orchestration
- **OAuth**: Keycloak integration (optional)
- **Superset**: Analytics dashboard (optional)

## Security Architecture

```
┌────────────────────────────────────────────────────┐
│                  API Gateway Layer                  │
│  (Future: Authentication, Rate Limiting, WAF)       │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│               FastAPI Application                   │
│  - Endpoint validation                             │
│  - Request sanitization                            │
│  - File type checking (.ipynb only)                │
│  - JSON structure validation                       │
└─────────┬──────────────────────┬───────────────────┘
          │                      │
          ▼                      ▼
┌──────────────────┐    ┌────────────────────┐
│  MinIO Access    │    │  Database Access   │
│  - Credentials   │    │  - Connection pool │
│  - Bucket policy │    │  - Prepared stmts  │
│  - Presigned URL │    │  - SQL injection   │
│    (time-limited)│    │    prevention      │
└──────────────────┘    └────────────────────┘

Production Recommendations:
├─ Change default credentials
├─ Enable TLS/SSL
├─ Implement IAM policies
├─ Add JWT authentication
├─ Configure CORS properly
├─ Enable audit logging
└─ Set up network isolation
```

## Scalability Considerations

### Horizontal Scaling
- **FastAPI**: Multiple uvicorn workers
- **MinIO**: Distributed mode (4+ nodes)
- **PostgreSQL**: Read replicas
- **JupyterHub**: Kubernetes spawner

### Performance Optimization
- **Caching**: Template metadata caching
- **Connection Pooling**: Database & MinIO
- **Async I/O**: Non-blocking operations
- **Background Tasks**: Notebook execution

### Resource Management
- **Memory**: Limit notebook execution memory
- **CPU**: Kernel CPU quotas
- **Storage**: MinIO quotas per user
- **Concurrent Executions**: Queue management

## Monitoring & Observability

```
┌─────────────────────────────────────────────┐
│           Application Metrics                │
│  - API request rate                         │
│  - Response times                           │
│  - Error rates                              │
│  - Active executions                        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          Infrastructure Metrics              │
│  - MinIO: Storage used, throughput          │
│  - PostgreSQL: Connection count, queries/s  │
│  - Kernel: Memory usage, CPU utilization    │
│  - Container: Resource consumption          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│            Logging & Alerts                  │
│  - Centralized logging (ELK/Loki)           │
│  - Error tracking (Sentry)                  │
│  - Uptime monitoring                        │
│  - Performance alerts                       │
└─────────────────────────────────────────────┘
```

## File Structure

```
Notebook_Authen/
├── docker-compose.yml                    # Container orchestration
├── README.md                             # Project overview
├── ARCHITECTURE.md                       # System architecture
│
├── jupyterhub/
│   └── jupyterhub-server/
│       ├── set_params.py                 # Main FastAPI server (2100+ lines)
│       ├── minio_client.py               # MinIO operations (350 lines)
│       ├── database.py                   # SQLAlchemy models
│       ├── requirements.txt              # Python dependencies
│       ├── kernel_requirements.txt       # Kernel packages (MLflow 2.8.0)
│       │
│       ├── setup_kernel.sh               # Kernel installation script
│       ├── start.sh                      # Container startup script
│       ├── Dockerfile                    # Container build config
│       │
│       ├── MINIO_INTEGRATION.md          # Complete integration guide
│       ├── QUICKSTART_MINIO.md           # Quick start guide
│       └── IMPLEMENTATION_SUMMARY.md     # This document
│
├── keycloak/                             # OAuth/SSO integration
│   └── config/
│       └── jhub-realm.json
│
└── superset/                             # Analytics dashboard
    ├── Dockerfile
    ├── superset_config.py
    └── superset_init.sh
```

## API Endpoint Summary

### MinIO Operations (New)
| Method | Endpoint                           | Purpose                    |
|--------|------------------------------------|----------------------------|
| POST   | `/minio/upload-template`           | Upload template to MinIO   |
| GET    | `/minio/list-templates`            | List all templates         |
| GET    | `/minio/get-template/{name}`       | Get template metadata      |
| DELETE | `/minio/delete-template/{name}`    | Delete template            |
| GET    | `/minio/download-url/{name}`       | Generate download URL      |

### Template Usage (Modified)
| Method | Endpoint                 | Purpose                              |
|--------|--------------------------|--------------------------------------|
| POST   | `/create-from-template`  | Create notebook from MinIO template  |

### Execution (Existing)
| Method | Endpoint                      | Purpose                         |
|--------|-------------------------------|---------------------------------|
| POST   | `/execute-notebook`           | Execute notebook (async)        |
| POST   | `/execute`                    | In-place execution              |
| GET    | `/execution-status/{id}`      | Check execution status          |

### Database Operations (Existing)
| Method | Endpoint                 | Purpose                          |
|--------|--------------------------|----------------------------------|
| POST   | `/submit-notebook`       | Submit notebook metadata to DB   |
| GET    | `/notebooks`             | List all notebooks               |
| GET    | `/notebook/{id}`         | Get notebook by ID               |
| PUT    | `/notebook/{id}`         | Update notebook                  |
| DELETE | `/notebook/{id}`         | Delete notebook                  |

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Status**: ✅ Complete and Ready for Deployment
