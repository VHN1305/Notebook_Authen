# JupyterHub Papermill API - Setup Guide 🚀

## Overview

Your FastAPI service is now **integrated into the JupyterHub Docker container**! This means:

- ✅ **JupyterHub** runs on port 8000
- ✅ **Papermill API** runs on port 8002 (inside the same container)
- ✅ Both services start automatically when the container starts
- ✅ The API can access all user notebooks directly

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker Container: mlops-jhub-1                         │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  JupyterHub Service                            │    │
│  │  Port: 8000 (exposed)                          │    │
│  │  - User authentication                         │    │
│  │  - Notebook interface                          │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  Papermill API Service (FastAPI)               │    │
│  │  Port: 8002 (exposed)                          │    │
│  │  - Execute notebooks with parameters           │    │
│  │  - List user notebooks                         │    │
│  │  - Health checks                               │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  User Notebooks: /home/{username}/*.ipynb               │
└─────────────────────────────────────────────────────────┘
```

## What Was Changed

### 1. Files Modified

✅ **`requirements.txt`** - Added FastAPI and Uvicorn
✅ **`set_params.py`** - Enhanced with better endpoints
✅ **`Dockerfile`** - Updated to include API service
✅ **`docker-compose.yml`** - Exposed port 8002

### 2. Files Created

✅ **`start.sh`** - Startup script for both services
✅ **`test_jupyterhub_api.py`** - Test script

## 🚀 Rebuild & Start

### Step 1: Rebuild the Docker Image

```bash
cd /home/vhn1305/Documents/Github/MLops

# Stop current containers
docker compose down

# Rebuild the jhub image
docker compose build --no-cache jhub

# Start services
docker compose up -d
```

### Step 2: Verify Services are Running

```bash
# Check container status
docker compose ps

# Check logs
docker compose logs jhub -f
```

You should see:
```
✅ Papermill API started successfully
✅ Starting JupyterHub...
```

### Step 3: Test the API

```bash
# Run the test script
python test_jupyterhub_api.py

# Or manually test
curl http://localhost:8002/health
```

## 📡 API Endpoints

Once running, the API is available at `http://localhost:8002`

### 1. Root / API Info
```bash
curl http://localhost:8002/
```

### 2. Health Check
```bash
curl http://localhost:8002/health
```

Response:
```json
{
  "status": "healthy",
  "papermill_available": true,
  "papermill_path": "/usr/local/bin/papermill",
  "timestamp": "2024-11-19T12:00:00"
}
```

### 3. List User Notebooks
```bash
curl http://localhost:8002/list-notebooks/testuser
```

Response:
```json
{
  "username": "testuser",
  "user_home": "/home/testuser",
  "notebook_count": 2,
  "notebooks": [
    {
      "name": "Test_notebook.ipynb",
      "path": "/home/testuser/notebooks/Test_notebook.ipynb",
      "relative_path": "notebooks/Test_notebook.ipynb",
      "size": 4096,
      "modified": "2024-11-19T10:30:00"
    }
  ]
}
```

### 4. Execute Notebook (User-based) ⭐ **Recommended**
```bash
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "notebook_name": "Test_notebook.ipynb",
    "parameters": {
      "param1": "value1",
      "threshold": 0.8
    }
  }'
```

Response:
```json
{
  "status": "success",
  "username": "testuser",
  "input_notebook": "/home/testuser/notebooks/Test_notebook.ipynb",
  "output_notebook": "/home/testuser/Test_notebook_output_20241119_120000.ipynb",
  "parameters": {"param1": "value1", "threshold": 0.8},
  "timestamp": "2024-11-19T12:00:00"
}
```

### 5. Execute Notebook (Full Path)
```bash
curl -X POST http://localhost:8002/run-notebook \
  -H "Content-Type: application/json" \
  -d '{
    "params": {"param1": "value1"},
    "input_path": "/home/testuser/notebooks/Test_notebook.ipynb",
    "output_path": "/home/testuser/output.ipynb"
  }'
```

## 🎨 Interactive API Documentation

Visit: **http://localhost:8002/docs**

You'll get a beautiful Swagger UI where you can:
- See all endpoints
- Try them out interactively
- See request/response schemas
- Download API specs

## 📝 Python Client Example

```python
import requests

# Execute a notebook
response = requests.post(
    'http://localhost:8002/execute',
    json={
        'username': 'testuser',
        'notebook_name': 'Test_notebook.ipynb',
        'parameters': {
            'learning_rate': 0.01,
            'epochs': 100,
            'batch_size': 32
        }
    },
    timeout=300  # 5 minute timeout
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Success!")
    print(f"Output: {result['output_notebook']}")
else:
    print(f"❌ Failed: {response.json()}")
```

## 🔧 Advanced Usage

### MLOps Pipeline Integration

```python
import requests
from typing import Dict, Any

class JupyterHubPapermillClient:
    def __init__(self, base_url="http://localhost:8002"):
        self.base_url = base_url
    
    def execute_notebook(
        self,
        username: str,
        notebook_name: str,
        parameters: Dict[str, Any],
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Execute a notebook with parameters"""
        response = requests.post(
            f"{self.base_url}/execute",
            json={
                "username": username,
                "notebook_name": notebook_name,
                "parameters": parameters
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    
    def list_notebooks(self, username: str) -> list:
        """List all notebooks for a user"""
        response = requests.get(
            f"{self.base_url}/list-notebooks/{username}"
        )
        response.raise_for_status()
        return response.json()["notebooks"]

# Usage
client = JupyterHubPapermillClient()

# Run experiment
result = client.execute_notebook(
    username="testuser",
    notebook_name="train_model.ipynb",
    parameters={
        "dataset": "iris.csv",
        "model_type": "random_forest",
        "n_estimators": 100
    }
)

print(f"Notebook executed: {result['output_notebook']}")
```

### Scheduled Execution

```python
import schedule
import requests
import time
from datetime import datetime

def run_daily_report():
    """Run daily report notebook"""
    print(f"Running daily report at {datetime.now()}")
    
    response = requests.post(
        'http://localhost:8002/execute',
        json={
            'username': 'testuser',
            'notebook_name': 'daily_report.ipynb',
            'parameters': {
                'date': datetime.now().strftime('%Y-%m-%d')
            }
        }
    )
    
    if response.status_code == 200:
        print(f"✅ Report generated: {response.json()['output_notebook']}")
    else:
        print(f"❌ Failed: {response.json()}")

# Schedule daily at 2 AM
schedule.every().day.at("02:00").do(run_daily_report)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 🐛 Troubleshooting

### API not accessible?

```bash
# Check if container is running
docker compose ps

# Check logs
docker compose logs jhub

# Verify port is exposed
docker compose port jhub 8002
```

### Can't find notebook?

```bash
# List notebooks via API
curl http://localhost:8002/list-notebooks/testuser

# Or check directly in container
docker exec -u testuser mlops-jhub-1 ls -la /home/testuser/
```

### Service won't start?

```bash
# Check detailed logs
docker compose logs jhub -f

# Rebuild without cache
docker compose build --no-cache jhub
docker compose up -d
```

### Papermill execution fails?

The notebook must have a cell tagged with `parameters`. See `PAPERMILL_GUIDE.md` for details.

## 🔐 Security Considerations

### Current Setup (Development)
- ⚠️ No authentication on API endpoints
- ⚠️ No rate limiting
- ⚠️ Direct file system access

### Production Recommendations

1. **Add API Authentication**
```python
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.post("/execute")
async def execute_user_notebook(
    req: NotebookExecuteRequest,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    # Validate token
    if not validate_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid token")
    # ... rest of code
```

2. **Add Rate Limiting**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/execute")
@limiter.limit("5/minute")
async def execute_user_notebook(...):
    # ... code
```

3. **Input Validation**
- Validate notebook names (prevent path traversal)
- Sanitize parameters
- Set execution timeouts

## 📊 Monitoring

### Check API Health
```bash
# Simple health check
watch -n 5 'curl -s http://localhost:8002/health | jq'
```

### Monitor Logs
```bash
# Follow API logs
docker compose logs jhub -f | grep "uvicorn"
```

## 🎉 Summary

You now have:

✅ FastAPI service **inside** JupyterHub container
✅ Papermill API on port 8002
✅ Execute notebooks via REST API
✅ List user notebooks
✅ Health checks
✅ Interactive API docs at http://localhost:8002/docs

## 🚀 Next Steps

1. **Rebuild and start:**
   ```bash
   docker compose down
   docker compose build --no-cache jhub
   docker compose up -d
   ```

2. **Test the API:**
   ```bash
   python test_jupyterhub_api.py
   ```

3. **Visit interactive docs:**
   http://localhost:8002/docs

4. **Integrate with your application:**
   Use the Python client example above

Happy automating! 🎊
