import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool
from typing import Optional, Dict, Any
import papermill as pm
import os
from datetime import datetime

app = FastAPI(
    title="JupyterHub Papermill API",
    description="API for executing notebooks with parameters inside JupyterHub",
    version="1.0.0"
)

class NotebookRequest(BaseModel):
    params: Dict[str, Any]
    input_path: str
    output_path: str

class NotebookExecuteRequest(BaseModel):
    """Execute notebook by input path with optional username"""
    username: Optional[str] = None
    input_path: str
    parameters: Optional[Dict[str, Any]] = {}

def set_params(params: dict, input_path: str, output_path: str):
    """Execute notebook with papermill"""
    pm.execute_notebook(
        input_path,
        output_path,
        parameters=params
    )

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "JupyterHub Papermill API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/run-notebook": "Execute notebook (simple)",
            "/execute-notebook": "Execute notebook (full)",
            "/execute": "Execute notebook (user-based)",
            "/list-notebooks/{username}": "List user notebooks",
            "/docs": "Interactive API documentation"
        }
    }

@app.get("/health")
def health_check():
    """Check if the service is running"""
    try:
        # Simple check to see if papermill is accessible
        result = subprocess.run(
            ["which", "papermill"],
            capture_output=True,
            text=True
        )
        
        papermill_available = result.returncode == 0
        
        return {
            "status": "healthy" if papermill_available else "degraded",
            "papermill_available": papermill_available,
            "papermill_path": result.stdout.strip() if papermill_available else None,
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/run-notebook")
async def run_notebook(req: NotebookRequest):
    """Execute notebook with given parameters (simple version)"""
    # Validate input path exists
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=404, detail=f"Input notebook not found: {req.input_path}")

    # Ensure output folder exists
    out_dir = os.path.dirname(req.output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        # Run papermill in thread (Papermill is blocking)
        await run_in_threadpool(set_params, req.params, req.input_path, req.output_path)

        return {
            "status": "success",
            "output": req.output_path,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/execute-notebook")
async def execute_notebook(req: NotebookRequest):
    """Execute a notebook with given parameters using papermill"""
    try:
        # Validate input path exists
        if not os.path.exists(req.input_path):
            raise HTTPException(status_code=404, detail=f"Input notebook not found: {req.input_path}")

        # Ensure output folder exists
        out_dir = os.path.dirname(req.output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Run papermill in thread (Papermill is blocking)
        await run_in_threadpool(set_params, req.params, req.input_path, req.output_path)

        return {
            "status": "success",
            "output_notebook": req.output_path,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute")
async def execute_user_notebook(req: NotebookExecuteRequest):
    """Execute a notebook given an input path and parameters.

    Behavior:
    - Validate `input_path` exists and is a file.
    - Optionally verify that `input_path` is under `/home/{username}` when `username` is provided.
    - Execute the notebook by running papermill to a temporary file in the same directory,
      then atomically replace the original notebook with the executed result. This avoids
      leaving a separate output notebook file.
    """
    import tempfile
    try:
        input_path = req.input_path

        # Validate input path exists
        if not os.path.exists(input_path) or not os.path.isfile(input_path):
            raise HTTPException(status_code=404, detail=f"Input notebook not found: {input_path}")

        # If username provided, ensure input_path is within the user's home directory
        if req.username:
            user_home = os.path.realpath(f"/home/{req.username}")
            real_input = os.path.realpath(input_path)
            if not real_input.startswith(user_home + os.sep) and real_input != user_home:
                raise HTTPException(status_code=403, detail="Input path is not inside the user's home directory")

        # Prepare temporary output path in same directory
        input_dir = os.path.dirname(input_path)
        fd, tmp_path = tempfile.mkstemp(suffix=".ipynb", dir=input_dir)
        os.close(fd)

        # Get original file's ownership and permissions
        stat_info = os.stat(input_path)
        original_uid = stat_info.st_uid
        original_gid = stat_info.st_gid
        original_mode = stat_info.st_mode

        try:
            # Execute into temporary file (blocking call in thread)
            await run_in_threadpool(set_params, req.parameters or {}, input_path, tmp_path)

            # Set ownership and permissions on temp file to match original
            os.chown(tmp_path, original_uid, original_gid)
            os.chmod(tmp_path, original_mode)

            # Replace the original file atomically
            os.replace(tmp_path, input_path)

            return {
                "status": "success",
                "input_notebook": input_path,
                "parameters": req.parameters,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            # Cleanup temp file if it still exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.get("/list-notebooks/{username}")
def list_user_notebooks(username: str):
    """List all notebooks for a specific user"""
    try:
        user_home = f"/home/{username}"
        
        if not os.path.exists(user_home):
            raise HTTPException(
                status_code=404,
                detail=f"User directory not found: {user_home}"
            )
        
        notebooks = []
        
        # Search for .ipynb files
        for root, dirs, files in os.walk(user_home):
            # Skip checkpoint directories
            if '.ipynb_checkpoints' in root:
                continue
                
            for file in files:
                if file.endswith('.ipynb'):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, user_home)
                    notebooks.append({
                        "name": file,
                        "path": full_path,
                        "relative_path": relative_path,
                        "size": os.path.getsize(full_path),
                        "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                    })
        
        return {
            "username": username,
            "user_home": user_home,
            "notebook_count": len(notebooks),
            "notebooks": notebooks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
