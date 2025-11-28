import subprocess
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field
from fastapi.concurrency import run_in_threadpool
from typing import Optional, Dict, Any, List
import papermill as pm
import os
import json
import shutil
from datetime import datetime
from sqlalchemy.orm import Session
import nbformat
import threading

# Import database models and session
from database import get_db, Notebook, NotebookParameter, NotebookExecution
# Import MinIO client
from minio_client import get_minio_client, MinIOClient

app = FastAPI(
    title="JupyterHub Papermill API with Database Management",
    description="API for executing notebooks with parameters and managing notebook metadata",
    version="2.0.0"
)

# ==================== Pydantic Models ====================

class NotebookRequest(BaseModel):
    params: Dict[str, Any]
    input_path: str
    output_path: str

class NotebookExecuteRequest(BaseModel):
    """Execute notebook by input path with optional username"""
    username: Optional[str] = None
    input_path: str
    parameters: Optional[Dict[str, Any]] = {}

# Database Models
class NotebookCreate(BaseModel):
    """Create new notebook entry"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    file_path: str = Field(..., min_length=1, max_length=512)
    username: str = Field(..., min_length=1, max_length=100)
    tags: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}
    
    class Config:
        # Allow population by field name for database compatibility
        populate_by_name = True

class NotebookUpdate(BaseModel):
    """Update notebook entry"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    file_path: Optional[str] = Field(None, min_length=1, max_length=512)
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True

class NotebookResponse(BaseModel):
    """Notebook response model"""
    id: int
    name: str
    description: Optional[str]
    file_path: str
    username: str
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    metadata: Dict[str, Any] = Field(alias='notebook_metadata')
    
    class Config:
        from_attributes = True
        populate_by_name = True

class ParameterCreate(BaseModel):
    """Create notebook parameter"""
    notebook_id: int
    param_name: str = Field(..., min_length=1, max_length=100)
    param_type: str = Field(..., pattern="^(string|integer|float|boolean|json|list)$")
    default_value: Optional[Any] = None
    description: Optional[str] = None
    required: bool = False
    validation_rules: Optional[Dict[str, Any]] = None

class ParameterUpdate(BaseModel):
    """Update notebook parameter"""
    param_name: Optional[str] = Field(None, min_length=1, max_length=100)
    param_type: Optional[str] = Field(None, pattern="^(string|integer|float|boolean|json|list)$")
    default_value: Optional[Any] = None
    description: Optional[str] = None
    required: Optional[bool] = None
    validation_rules: Optional[Dict[str, Any]] = None

class ParameterResponse(BaseModel):
    """Parameter response model"""
    id: int
    notebook_id: int
    param_name: str
    param_type: str
    default_value: Optional[Any]
    description: Optional[str]
    required: bool
    validation_rules: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class NotebookWithParameters(NotebookResponse):
    """Notebook with its parameters"""
    parameters: List[ParameterResponse] = []
    
    class Config:
        from_attributes = True

class ExecutionHistoryResponse(BaseModel):
    """Execution history response"""
    id: int
    notebook_id: Optional[int]
    username: str
    input_path: str
    output_path: Optional[str]
    parameters_used: Optional[Dict[str, Any]]
    status: str
    error_message: Optional[str]
    execution_time_seconds: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ==================== Helper Functions ====================

def set_params(params: dict, input_path: str, output_path: str, kernel_name: str = "mlflow_kernel"):
    """Execute notebook with papermill using specified kernel"""
    pm.execute_notebook(
        input_path,
        output_path,
        parameters=params,
        kernel_name=kernel_name
    )

def execute_notebook_background(execution_id: int, params: dict, input_path: str, output_path: str, database_url: str):
    """Execute notebook in background and update execution status in database"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Create new database session for this thread
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    started_at = datetime.utcnow()
    
    try:
        # Update status to running
        execution = db.query(NotebookExecution).filter(NotebookExecution.id == execution_id).first()
        if execution:
            execution.status = "running"
            execution.started_at = started_at
            db.commit()
        
        # Execute the notebook with MLflow kernel
        pm.execute_notebook(
            input_path,
            output_path,
            parameters=params,
            kernel_name="mlflow_kernel"
        )
        
        # Update status to success
        completed_at = datetime.utcnow()
        execution_time = int((completed_at - started_at).total_seconds())
        
        if execution:
            execution.status = "success"
            execution.completed_at = completed_at
            execution.execution_time_seconds = execution_time
            db.commit()
            
    except Exception as e:
        # Update status to failed
        completed_at = datetime.utcnow()
        execution_time = int((completed_at - started_at).total_seconds())
        
        execution = db.query(NotebookExecution).filter(NotebookExecution.id == execution_id).first()
        if execution:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = completed_at
            execution.execution_time_seconds = execution_time
            db.commit()
    
    finally:
        db.close()

def check_first_cell_execution(output_path: str, timeout: int = 30) -> bool:
    """Check if the first cell has been executed by monitoring the output notebook"""
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r') as f:
                    nb = nbformat.read(f, as_version=4)
                    # Check if any cell has been executed (has execution_count or outputs)
                    for cell in nb.cells:
                        if cell.cell_type == 'code':
                            if cell.get('execution_count') is not None or len(cell.get('outputs', [])) > 0:
                                return True
            except (json.JSONDecodeError, Exception):
                # File might be partially written, continue waiting
                pass
        time.sleep(0.5)
    
    return False

def check_last_cell_execution(output_path: str, timeout: int = 30) -> bool:
    """
    Check if the last code cell of the notebook has been executed.
    Returns True when the last code cell has execution_count or outputs.
    """
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r') as f:
                    nb = nbformat.read(f, as_version=4)

                # Lấy danh sách cell
                code_cells = [c for c in nb.cells if c.cell_type == "code"]

                if not code_cells:
                    return False  # Notebook không có code cell

                last_cell = code_cells[-1]

                # Kiểm tra cell cuối đã chạy chưa
                if (last_cell.get("execution_count") is not None and
                    last_cell["execution_count"] != 0):
                    return True

                if len(last_cell.get("outputs", [])) > 0:
                    return True

            except (json.JSONDecodeError, Exception):
                # File có thể đang được Papermill ghi dở → chờ
                pass

        time.sleep(0.5)

    return False


@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "JupyterHub Papermill API with Database Management",
        "version": "2.1.0",
        "kernel": {
            "default": "mlflow_kernel",
            "display_name": "Python 3 (MLflow 2.8.0)",
            "mlflow_version": "2.8.0"
        },
        "endpoints": {
            "execution": {
                "/health": "Health check (includes kernel status)",
                "/run-notebook": "Execute notebook (simple)",
                "/execute-notebook": "Execute notebook (async with MLflow kernel)",
                "/execute": "Execute notebook (async, in-place, with MLflow kernel)",
                "/execute2": "Execute notebook (synchronous, in-place, waits for completion)",
                "/list-notebooks/{username}": "List user notebooks"
            },
            "notebook_submission": {
                "/submit-notebook": "Create/submit notebook to user directory",
                "/copy-notebook": "Copy notebook from DB to user directory",
                "/upload-notebook": "Upload notebook file to user directory",
                "/create-from-template": "Create notebook from MinIO template with parameters"
            },
            "minio_templates": {
                "/minio/upload-template": "Upload notebook to MinIO as template",
                "/minio/list-templates": "List all template notebooks in MinIO",
                "/minio/get-template": "Get template notebook info from MinIO",
                "/minio/delete-template": "Delete template notebook from MinIO",
                "/minio/download-url": "Get presigned download URL for template"
            },
            "database": {
                "/db/notebooks": "List all notebooks in DB",
                "/db/notebooks/{notebook_id}": "Get/Update/Delete specific notebook",
                "/db/notebooks/user/{username}": "Get notebooks by username",
                "/db/parameters/notebook/{notebook_id}": "Get parameters for notebook",
                "/db/parameters/{param_id}": "Get/Update/Delete specific parameter",
                "/db/executions": "Get execution history",
                "/db/executions/notebook/{notebook_id}": "Get executions for notebook"
            },
            "docs": {
                "/docs": "Interactive API documentation",
                "/redoc": "ReDoc API documentation"
            }
        }
    }

@app.get("/health")
def health_check():
    """
    Check if the API service and Papermill are available
    
    Returns:
    - status: "healthy", "degraded", or "unhealthy"
    - papermill_available: Boolean indicating if papermill is installed
    - papermill_path: Path to papermill executable
    - mlflow_kernel: Information about MLflow kernel
    - timestamp: Current server time
    
    Example response:
    {
        "status": "healthy",
        "papermill_available": true,
        "papermill_path": "/usr/local/bin/papermill",
        "mlflow_kernel": {
            "installed": true,
            "name": "mlflow_kernel",
            "display_name": "Python 3 (MLflow 2.8.0)"
        },
        "timestamp": "2025-11-21T10:30:00"
    }
    """
    try:
        # Check if papermill is accessible
        result = subprocess.run(
            ["which", "papermill"],
            capture_output=True,
            text=True
        )
        
        papermill_available = result.returncode == 0
        
        # Check if MLflow kernel is installed
        kernel_check = subprocess.run(
            ["jupyter", "kernelspec", "list"],
            capture_output=True,
            text=True
        )
        
        mlflow_kernel_installed = "mlflow_kernel" in kernel_check.stdout
        
        # Get MLflow version if available
        mlflow_version = None
        if mlflow_kernel_installed:
            try:
                version_check = subprocess.run(
                    ["/opt/mlflow_env/bin/python", "-c", "import mlflow; print(mlflow.__version__)"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_check.returncode == 0:
                    mlflow_version = version_check.stdout.strip()
            except Exception:
                pass
        
        mlflow_kernel_info = {
            "installed": mlflow_kernel_installed,
            "name": "mlflow_kernel" if mlflow_kernel_installed else None,
            "display_name": "Python 3 (MLflow 2.8.0)" if mlflow_kernel_installed else None,
            "mlflow_version": mlflow_version
        }
        
        overall_status = "healthy"
        if not papermill_available or not mlflow_kernel_installed:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "papermill_available": papermill_available,
            "papermill_path": result.stdout.strip() if papermill_available else None,
            "mlflow_kernel": mlflow_kernel_info,
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/run-notebook")
async def run_notebook(req: NotebookRequest):
    """
    Execute a notebook with parameters using Papermill (simple version)
    
    Parameters:
    - params: Dictionary of parameter key-value pairs to inject into notebook
    - input_path: Absolute path to the input notebook file
    - output_path: Absolute path where the executed notebook will be saved
    
    Example request body:
    {
        "params": {"name": "John", "age": 25, "debug": true},
        "input_path": "/home/user/notebooks/template.ipynb",
        "output_path": "/home/user/results/output.ipynb"
    }
    
    Returns:
    - status: "success" or error
    - output: Path to the executed notebook
    - timestamp: Execution completion time
    """
    # Validate input path exists
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=404, detail=f"Input notebook not found: {req.input_path}")

    # Ensure output folder exists
    out_dir = os.path.dirname(req.output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        # Run papermill in thread (Papermill is blocking)
        await run_in_threadpool(set_params, req.params, req.input_path, req.output_path, "mlflow_kernel")

        return {
            "status": "success",
            "output": req.output_path,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/execute-notebook")
async def execute_notebook(req: NotebookRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Execute a notebook with parameters using Papermill (async version)
    
    Parameters:
    - params: Dictionary of parameter key-value pairs to inject into notebook
    - input_path: Absolute path to the input notebook file
    - output_path: Absolute path where the executed notebook will be saved
    
    Behavior:
    - Validates input notebook exists
    - Creates output directory if needed
    - Starts notebook execution in background
    - Returns immediately after first cell executes with link to monitor progress
    
    Example request body:
    {
        "params": {"dataset": "sales_2025.csv", "threshold": 0.95},
        "input_path": "/home/user/analysis.ipynb",
        "output_path": "/home/user/results/analysis_output.ipynb"
    }
    
    Returns:
    - status: "started"
    - execution_id: ID to track execution status
    - output_notebook: Path to executed notebook
    - notebook_url: URL to access notebook in JupyterLab
    - status_url: URL to check execution status
    - message: Info about background execution
    - timestamp: Start time
    """
    try:
        # Validate input path exists
        if not os.path.exists(req.input_path):
            raise HTTPException(status_code=404, detail=f"Input notebook not found: {req.input_path}")

        # Ensure output folder exists
        out_dir = os.path.dirname(req.output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Create execution record in database
        execution = NotebookExecution(
            notebook_id=None,  # Can be linked if you track notebook_id
            username="api_user",  # Update if you have username in request
            input_path=req.input_path,
            output_path=req.output_path,
            parameters_used=req.params,
            status="pending",
            started_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL', 'postgresql://mlflow:mlflow@host.docker.internal:5432/notebook_manager')
        
        # Start background execution in a separate thread
        thread = threading.Thread(
            target=execute_notebook_background,
            args=(execution.id, req.params, req.input_path, req.output_path, database_url)
        )
        thread.daemon = True
        thread.start()
        
        # Wait for first cell to execute (with timeout)
        first_cell_executed = await run_in_threadpool(check_first_cell_execution, req.output_path, 30)
        
        if not first_cell_executed:
            # Even if first cell didn't execute yet, still return - execution is running
            message = "Notebook execution started but first cell not yet completed. Check status URL for progress."
        else:
            message = "Notebook execution started successfully. First cell executed. Check status URL for progress."
        
        # Generate notebook URL (assumes JupyterHub is running)
        # Extract username from path if possible
        username = "unknown"
        if "/home/" in req.output_path:
            parts = req.output_path.split("/home/")[1].split("/")
            if parts:
                username = parts[0]
        
        # Generate relative path from user home
        relative_path = req.output_path.replace(f"/home/{username}/", "")
        notebook_url = f"http://localhost:8000/user/{username}/lab/tree/{relative_path}"
        status_url = f"http://localhost:8002/db/executions/{execution.id}"

        return {
            "status": "started",
            "execution_id": execution.id,
            "output_notebook": req.output_path,
            "notebook_url": notebook_url,
            "status_url": status_url,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute")
async def execute_user_notebook(req: NotebookExecuteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Execute a notebook in-place with parameters (async version)
    
    Parameters:
    - username: JupyterLab username (optional, for path validation)
    - input_path: Absolute path to the notebook to execute
    - parameters: Dictionary of parameters to inject (optional, default: {})
    
    Behavior:
    - Validates input_path exists and is a file
    - If username provided, ensures notebook is in user's home directory
    - Starts notebook execution in background
    - Returns immediately after first cell executes with link to monitor progress
    
    Example request body:
    {
        "username": "student1",
        "input_path": "/home/student1/assignments/hw1.ipynb",
        "parameters": {"student_name": "Alice", "problem_set": 1}
    }
    
    Returns:
    - status: "started"
    - execution_id: ID to track execution status
    - input_notebook: Path to the notebook
    - notebook_url: URL to access notebook in JupyterLab
    - status_url: URL to check execution status
    - parameters: Parameters that were injected
    - message: Info about background execution
    - timestamp: Start time
    
    Note: This endpoint modifies the original notebook file in-place!
    """
    import tempfile
    try:
        input_path = req.input_path

        # Validate input path exists
        if not os.path.exists(input_path) or not os.path.isfile(input_path):
            raise HTTPException(status_code=404, detail=f"Input notebook not found: {input_path}")

        # If username provided, ensure input_path is within the user's home directory
        username = req.username or "unknown"
        if req.username:
            user_home = os.path.realpath(f"/home/{req.username}")
            real_input = os.path.realpath(input_path)
            if not real_input.startswith(user_home + os.sep) and real_input != user_home:
                raise HTTPException(status_code=403, detail="Input path is not inside the user's home directory")
        else:
            # Try to extract username from path
            if "/home/" in input_path:
                parts = input_path.split("/home/")[1].split("/")
                if parts:
                    username = parts[0]

        # Prepare temporary output path in same directory
        input_dir = os.path.dirname(input_path)
        fd, tmp_path = tempfile.mkstemp(suffix=".ipynb", dir=input_dir)
        os.close(fd)

        # Get original file's ownership and permissions
        stat_info = os.stat(input_path)
        original_uid = stat_info.st_uid
        original_gid = stat_info.st_gid
        original_mode = stat_info.st_mode

        # Create execution record in database
        execution = NotebookExecution(
            notebook_id=None,
            username=username,
            input_path=input_path,
            output_path=tmp_path,
            parameters_used=req.parameters or {},
            status="pending",
            started_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL', 'postgresql://mlflow:mlflow@host.docker.internal:5432/notebook_manager')
        
        # Define a wrapper function for in-place execution
        def execute_inplace_background(execution_id: int, params: dict, input_path: str, tmp_path: str, 
                                      original_uid: int, original_gid: int, original_mode: int, database_url: str):
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            engine = create_engine(database_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db_local = SessionLocal()
            
            started_at = datetime.utcnow()
            
            try:
                # Update status to running
                exec_record = db_local.query(NotebookExecution).filter(NotebookExecution.id == execution_id).first()
                if exec_record:
                    exec_record.status = "running"
                    exec_record.started_at = started_at
                    db_local.commit()
                
                # Execute notebook to temp file with MLflow kernel
                pm.execute_notebook(input_path, tmp_path, parameters=params, kernel_name="mlflow_kernel")
                
                # Set ownership and permissions
                os.chown(tmp_path, original_uid, original_gid)
                os.chmod(tmp_path, original_mode)
                
                # Replace original file atomically
                os.replace(tmp_path, input_path)
                
                # Update status to success
                completed_at = datetime.utcnow()
                execution_time = int((completed_at - started_at).total_seconds())
                
                if exec_record:
                    exec_record.status = "success"
                    exec_record.output_path = input_path  # Update to final path
                    exec_record.completed_at = completed_at
                    exec_record.execution_time_seconds = execution_time
                    db_local.commit()
                    
            except Exception as e:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                
                # Update status to failed
                completed_at = datetime.utcnow()
                execution_time = int((completed_at - started_at).total_seconds())
                
                exec_record = db_local.query(NotebookExecution).filter(NotebookExecution.id == execution_id).first()
                if exec_record:
                    exec_record.status = "failed"
                    exec_record.error_message = str(e)
                    exec_record.completed_at = completed_at
                    exec_record.execution_time_seconds = execution_time
                    db_local.commit()
            
            finally:
                db_local.close()
        
        # Start background execution
        thread = threading.Thread(
            target=execute_inplace_background,
            args=(execution.id, req.parameters or {}, input_path, tmp_path, 
                  original_uid, original_gid, original_mode, database_url)
        )
        thread.daemon = True
        thread.start()
        
        # Wait for first cell to execute
        first_cell_executed = await run_in_threadpool(check_first_cell_execution, tmp_path, 30)
        
        if not first_cell_executed:
            message = "Notebook execution started but first cell not yet completed. Check status URL for progress."
        else:
            message = "Notebook execution started successfully. First cell executed. Check status URL for progress."
        
        # Generate URLs
        relative_path = input_path.replace(f"/home/{username}/", "")
        notebook_url = f"http://localhost:8000/user/{username}/lab/tree/{relative_path}"
        status_url = f"http://localhost:8002/db/executions/{execution.id}"

        return {
            "status": "started",
            "execution_id": execution.id,
            "input_notebook": input_path,
            "notebook_url": notebook_url,
            "status_url": status_url,
            "parameters": req.parameters,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@app.post("/execute2")
async def execute_notebook_sync(req: NotebookExecuteRequest, db: Session = Depends(get_db)):
    """
    Execute a notebook in-place with parameters (synchronous version)
    
    This endpoint waits for the entire notebook to complete before returning.
    Use this when you want to wait for full execution results.
    
    Parameters:
    - username: JupyterLab username (optional, for path validation)
    - input_path: Absolute path to the notebook to execute
    - parameters: Dictionary of parameters to inject (optional, default: {})
    
    Behavior:
    - Validates input_path exists and is a file
    - If username provided, ensures notebook is in user's home directory
    - Executes notebook synchronously (waits for completion)
    - Returns after notebook execution finishes with complete results
    
    Example request body:
    {
        "username": "student1",
        "input_path": "/home/student1/assignments/hw1.ipynb",
        "parameters": {"student_name": "Alice", "problem_set": 1}
    }
    
    Returns:
    - status: "success" or "failed"
    - execution_id: Database execution record ID
    - input_notebook: Path to the notebook
    - notebook_url: URL to access notebook in JupyterLab
    - execution_time_seconds: Total execution time
    - error_message: Error details if failed (null if success)
    - started_at: Execution start timestamp
    - completed_at: Execution completion timestamp
    - parameters: Parameters that were injected
    
    Note: This endpoint modifies the original notebook file in-place!
    This endpoint blocks until execution completes - may take minutes for long notebooks.
    """
    import tempfile
    try:
        input_path = req.input_path

        # Validate input path exists
        if not os.path.exists(input_path) or not os.path.isfile(input_path):
            raise HTTPException(status_code=404, detail=f"Input notebook not found: {input_path}")

        # If username provided, ensure input_path is within the user's home directory
        username = req.username or "unknown"
        if req.username:
            user_home = os.path.realpath(f"/home/{req.username}")
            real_input = os.path.realpath(input_path)
            if not real_input.startswith(user_home + os.sep) and real_input != user_home:
                raise HTTPException(status_code=403, detail="Input path is not inside the user's home directory")
        else:
            # Try to extract username from path
            if "/home/" in input_path:
                parts = input_path.split("/home/")[1].split("/")
                if parts:
                    username = parts[0]

        # Prepare temporary output path in same directory
        input_dir = os.path.dirname(input_path)
        fd, tmp_path = tempfile.mkstemp(suffix=".ipynb", dir=input_dir)
        os.close(fd)

        # Get original file's ownership and permissions
        stat_info = os.stat(input_path)
        original_uid = stat_info.st_uid
        original_gid = stat_info.st_gid
        original_mode = stat_info.st_mode

        # Create execution record in database
        started_at = datetime.utcnow()
        execution = NotebookExecution(
            notebook_id=None,
            username=username,
            input_path=input_path,
            output_path=tmp_path,
            parameters_used=req.parameters or {},
            status="running",
            started_at=started_at
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        try:
            # Execute notebook synchronously with MLflow kernel
            await run_in_threadpool(
                pm.execute_notebook,
                input_path,
                tmp_path,
                parameters=req.parameters or {},
                kernel_name="mlflow_kernel"
            )
            
            # Set ownership and permissions
            os.chown(tmp_path, original_uid, original_gid)
            os.chmod(tmp_path, original_mode)
            
            # Replace original file atomically
            os.replace(tmp_path, input_path)
            
            # Update status to success
            completed_at = datetime.utcnow()
            execution_time = int((completed_at - started_at).total_seconds())
            
            execution.status = "success"
            execution.output_path = input_path  # Update to final path
            execution.completed_at = completed_at
            execution.execution_time_seconds = execution_time
            db.commit()
            
            # Generate URLs
            relative_path = input_path.replace(f"/home/{username}/", "")
            notebook_url = f"http://localhost:8000/user/{username}/lab/tree/{relative_path}"

            return {
                "status": "success",
                "execution_id": execution.id,
                "input_notebook": input_path,
                "notebook_url": notebook_url,
                "execution_time_seconds": execution_time,
                "error_message": None,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "parameters": req.parameters,
                "message": f"Notebook executed successfully in {execution_time} seconds"
            }
                
        except Exception as e:
            # Important: Keep the partially executed notebook with error outputs
            # Check if temp file was created and has content
            notebook_has_outputs = False
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                try:
                    # Verify it's valid JSON and has some execution outputs
                    with open(tmp_path, 'r') as f:
                        nb_data = json.load(f)
                        # Check if any cells were executed
                        for cell in nb_data.get('cells', []):
                            if cell.get('cell_type') == 'code':
                                if cell.get('execution_count') is not None or len(cell.get('outputs', [])) > 0:
                                    notebook_has_outputs = True
                                    break
                    
                    if notebook_has_outputs:
                        # Replace original with partially executed notebook (contains error outputs)
                        os.chown(tmp_path, original_uid, original_gid)
                        os.chmod(tmp_path, original_mode)
                        os.replace(tmp_path, input_path)
                    else:
                        # No outputs captured, remove temp file
                        os.remove(tmp_path)
                        
                except Exception as cleanup_error:
                    # If we can't process temp file, try to remove it
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
            
            # Update status to failed
            completed_at = datetime.utcnow()
            execution_time = int((completed_at - started_at).total_seconds())
            
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = completed_at
            execution.execution_time_seconds = execution_time
            db.commit()
            
            # Generate URLs
            relative_path = input_path.replace(f"/home/{username}/", "")
            notebook_url = f"http://localhost:8000/user/{username}/lab/tree/{relative_path}"
            
            return {
                "status": "failed",
                "execution_id": execution.id,
                "input_notebook": input_path,
                "notebook_url": notebook_url,
                "execution_time_seconds": execution_time,
                "error_message": str(e),
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "parameters": req.parameters,
                "notebook_updated": notebook_has_outputs,
                "message": f"Notebook execution failed after {execution_time} seconds. " + 
                          (f"Partial outputs saved to notebook." if notebook_has_outputs else "No outputs captured.")
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@app.get("/list-notebooks/{username}")
def list_user_notebooks(username: str):
    """
    List all Jupyter notebooks in a user's home directory
    
    Parameters:
    - username: JupyterLab username (path parameter)
    
    Behavior:
    - Recursively searches user's home directory for .ipynb files
    - Excludes .ipynb_checkpoints directories
    - Returns file metadata (name, path, size, modified time)
    
    Example request:
    GET /list-notebooks/student1
    
    Returns:
    - username: The username queried
    - user_home: Path to user's home directory
    - notebook_count: Total number of notebooks found
    - notebooks: Array of notebook objects with:
        * name: Filename
        * path: Absolute path
        * relative_path: Path relative to user home
        * size: File size in bytes
        * modified: Last modified timestamp
    """
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


# ==================== Database CRUD Endpoints ====================

# ===== Notebook Management =====

@app.post("/db/notebooks", response_model=NotebookResponse, status_code=201)
def create_notebook(notebook: NotebookCreate, db: Session = Depends(get_db)):
    """
    Register a new notebook in the database
    
    Parameters:
    - name: Notebook display name (required, max 255 chars)
    - description: Optional description
    - file_path: Absolute path to notebook file (required, max 512 chars)
    - username: Owner username (required, max 100 chars)
    - tags: Array of string tags (optional, default: [])
    - metadata: Additional metadata as JSON object (optional, default: {})
    
    Example request body:
    {
        "name": "Sales Analysis Q4",
        "description": "Quarterly sales analysis notebook",
        "file_path": "/home/analyst/notebooks/sales_q4.ipynb",
        "username": "analyst",
        "tags": ["sales", "quarterly", "2025"],
        "metadata": {"department": "finance", "priority": "high"}
    }
    
    Returns:
    - Notebook object with generated ID and timestamps
    
    Errors:
    - 400: Notebook with same name and username already exists
    - 404: File path does not exist
    """
    # Check if notebook with same name and username exists
    existing = db.query(Notebook).filter(
        Notebook.name == notebook.name,
        Notebook.username == notebook.username
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Notebook '{notebook.name}' already exists for user '{notebook.username}'"
        )
    
    # Check if file exists
    if not os.path.exists(notebook.file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Notebook file not found: {notebook.file_path}"
        )
    
    # Map metadata to notebook_metadata for database
    notebook_data = notebook.model_dump()
    notebook_data['notebook_metadata'] = notebook_data.pop('metadata', {})
    
    db_notebook = Notebook(**notebook_data)
    db.add(db_notebook)
    db.commit()
    db.refresh(db_notebook)
    
    return db_notebook


@app.get("/db/notebooks", response_model=List[NotebookResponse])
def list_notebooks(
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all registered notebooks with optional filtering
    
    Query Parameters:
    - skip: Number of records to skip for pagination (default: 0)
    - limit: Maximum number of records to return (default: 100)
    - username: Filter by username (optional)
    - tag: Filter by tag (optional, matches if tag is in notebook's tags array)
    
    Example requests:
    GET /db/notebooks
    GET /db/notebooks?username=student1
    GET /db/notebooks?tag=assignment&limit=50
    GET /db/notebooks?skip=20&limit=10
    
    Returns:
    - Array of notebook objects with all fields
    """
    query = db.query(Notebook)
    
    if username:
        query = query.filter(Notebook.username == username)
    
    if tag:
        # Filter notebooks that contain the specified tag
        query = query.filter(Notebook.tags.contains([tag]))
    
    notebooks = query.offset(skip).limit(limit).all()
    return notebooks


@app.get("/db/notebooks/{notebook_id}", response_model=NotebookWithParameters)
def get_notebook(notebook_id: int, db: Session = Depends(get_db)):
    """
    Get a specific notebook with all its parameters
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    
    Example request:
    GET /db/notebooks/5
    
    Returns:
    - Notebook object with embedded parameters array
    - Each parameter includes: id, name, type, default_value, description, required, validation_rules
    
    Errors:
    - 404: Notebook not found
    """
    notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    return notebook


@app.get("/db/notebooks/user/{username}", response_model=List[NotebookResponse])
def get_notebooks_by_user(username: str, db: Session = Depends(get_db)):
    """
    Get all notebooks registered for a specific user
    
    Parameters:
    - username: JupyterLab username (path parameter)
    
    Example request:
    GET /db/notebooks/user/student1
    
    Returns:
    - Array of all notebooks owned by the specified user
    """
    notebooks = db.query(Notebook).filter(Notebook.username == username).all()
    return notebooks


@app.put("/db/notebooks/{notebook_id}", response_model=NotebookResponse)
def update_notebook(notebook_id: int, notebook_update: NotebookUpdate, db: Session = Depends(get_db)):
    """
    Update an existing notebook's information
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    - name: New display name (optional, max 255 chars)
    - description: New description (optional)
    - file_path: New file path (optional, max 512 chars)
    - tags: New tags array (optional)
    - metadata: New metadata object (optional)
    
    Example request:
    PUT /db/notebooks/5
    {
        "name": "Updated Sales Analysis",
        "tags": ["sales", "2025", "updated"],
        "description": "Updated quarterly analysis"
    }
    
    Note: Only provided fields will be updated. Omitted fields remain unchanged.
    
    Returns:
    - Updated notebook object with new updated_at timestamp
    
    Errors:
    - 404: Notebook not found or file_path does not exist
    """
    db_notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    
    if not db_notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    # Update only provided fields
    update_data = notebook_update.model_dump(exclude_unset=True)
    
    # Map metadata to notebook_metadata if present
    if 'metadata' in update_data:
        update_data['notebook_metadata'] = update_data.pop('metadata')
    
    # Check if file path exists if being updated
    if "file_path" in update_data:
        if not os.path.exists(update_data["file_path"]):
            raise HTTPException(
                status_code=404,
                detail=f"Notebook file not found: {update_data['file_path']}"
            )
    
    for key, value in update_data.items():
        setattr(db_notebook, key, value)
    
    db_notebook.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_notebook)
    
    return db_notebook


@app.delete("/db/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: int, db: Session = Depends(get_db)):
    """
    Delete a notebook from the database
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    
    Example request:
    DELETE /db/notebooks/5
    
    Behavior:
    - Deletes the notebook record from database
    - Automatically deletes all associated parameters (cascade delete)
    - Does NOT delete the actual notebook file from filesystem
    
    Returns:
    - 204 No Content on success
    
    Errors:
    - 404: Notebook not found
    """
    db_notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    
    if not db_notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    db.delete(db_notebook)
    db.commit()
    
    return None


# ===== Parameter Management =====

@app.post("/db/parameters", response_model=ParameterResponse, status_code=201)
def create_parameter(parameter: ParameterCreate, db: Session = Depends(get_db)):
    """
    Create a new parameter definition for a notebook
    
    Parameters:
    - notebook_id: ID of the notebook this parameter belongs to (required)
    - param_name: Parameter name (required, max 100 chars)
    - param_type: Data type - one of: "string", "integer", "float", "boolean", "json", "list" (required)
    - default_value: Default value for this parameter (optional)
    - description: Parameter description (optional)
    - required: Whether this parameter is required (default: false)
    - validation_rules: JSON object with validation rules (optional)
    
    Example request body:
    {
        "notebook_id": 5,
        "param_name": "threshold",
        "param_type": "float",
        "default_value": 0.95,
        "description": "Confidence threshold for predictions",
        "required": true,
        "validation_rules": {"min": 0.0, "max": 1.0}
    }
    
    Returns:
    - Parameter object with generated ID and timestamps
    
    Errors:
    - 404: Notebook not found
    - 400: Parameter with same name already exists for this notebook
    """
    # Check if notebook exists
    notebook = db.query(Notebook).filter(Notebook.id == parameter.notebook_id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    # Check if parameter with same name exists for this notebook
    existing = db.query(NotebookParameter).filter(
        NotebookParameter.notebook_id == parameter.notebook_id,
        NotebookParameter.param_name == parameter.param_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Parameter '{parameter.param_name}' already exists for this notebook"
        )
    
    db_param = NotebookParameter(
        notebook_id=parameter.notebook_id,
        param_name=parameter.param_name,
        param_type=parameter.param_type,
        default_value=parameter.default_value,
        description=parameter.description,
        required=1 if parameter.required else 0,
        validation_rules=parameter.validation_rules
    )
    
    db.add(db_param)
    db.commit()
    db.refresh(db_param)
    
    # Convert required back to boolean for response
    response_param = ParameterResponse.model_validate(db_param)
    response_param.required = bool(db_param.required)
    
    return response_param


@app.get("/db/parameters/notebook/{notebook_id}", response_model=List[ParameterResponse])
def get_notebook_parameters(notebook_id: int, db: Session = Depends(get_db)):
    """
    Get all parameter definitions for a specific notebook
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    
    Example request:
    GET /db/parameters/notebook/5
    
    Returns:
    - Array of parameter objects for the notebook
    - Each parameter includes type, default value, validation rules, etc.
    
    Errors:
    - 404: Notebook not found
    """
    # Check if notebook exists
    notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    parameters = db.query(NotebookParameter).filter(
        NotebookParameter.notebook_id == notebook_id
    ).all()
    
    # Convert required field to boolean
    result = []
    for param in parameters:
        param_dict = ParameterResponse.model_validate(param)
        param_dict.required = bool(param.required)
        result.append(param_dict)
    
    return result


@app.get("/db/parameters/{param_id}", response_model=ParameterResponse)
def get_parameter(param_id: int, db: Session = Depends(get_db)):
    """
    Get a specific parameter definition by ID
    
    Parameters:
    - param_id: Parameter ID (path parameter)
    
    Example request:
    GET /db/parameters/15
    
    Returns:
    - Parameter object with all fields
    
    Errors:
    - 404: Parameter not found
    """
    parameter = db.query(NotebookParameter).filter(NotebookParameter.id == param_id).first()
    
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    
    response_param = ParameterResponse.model_validate(parameter)
    response_param.required = bool(parameter.required)
    
    return response_param


@app.put("/db/parameters/{param_id}", response_model=ParameterResponse)
def update_parameter(param_id: int, parameter_update: ParameterUpdate, db: Session = Depends(get_db)):
    """
    Update an existing parameter definition
    
    Parameters:
    - param_id: Parameter ID (path parameter)
    - param_name: New parameter name (optional, max 100 chars)
    - param_type: New data type (optional, must be valid type)
    - default_value: New default value (optional)
    - description: New description (optional)
    - required: New required flag (optional)
    - validation_rules: New validation rules (optional)
    
    Example request:
    PUT /db/parameters/15
    {
        "default_value": 0.90,
        "description": "Updated: Lower threshold for recall",
        "validation_rules": {"min": 0.5, "max": 1.0}
    }
    
    Note: Only provided fields will be updated.
    
    Returns:
    - Updated parameter object with new updated_at timestamp
    
    Errors:
    - 404: Parameter not found
    """
    db_param = db.query(NotebookParameter).filter(NotebookParameter.id == param_id).first()
    
    if not db_param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    
    # Update only provided fields
    update_data = parameter_update.model_dump(exclude_unset=True)
    
    # Convert required boolean to integer if present
    if "required" in update_data:
        update_data["required"] = 1 if update_data["required"] else 0
    
    for key, value in update_data.items():
        setattr(db_param, key, value)
    
    db_param.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_param)
    
    response_param = ParameterResponse.model_validate(db_param)
    response_param.required = bool(db_param.required)
    
    return response_param


@app.delete("/db/parameters/{param_id}", status_code=204)
def delete_parameter(param_id: int, db: Session = Depends(get_db)):
    """
    Delete a parameter definition
    
    Parameters:
    - param_id: Parameter ID (path parameter)
    
    Example request:
    DELETE /db/parameters/15
    
    Returns:
    - 204 No Content on success
    
    Errors:
    - 404: Parameter not found
    """
    db_param = db.query(NotebookParameter).filter(NotebookParameter.id == param_id).first()
    
    if not db_param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    
    db.delete(db_param)
    db.commit()
    
    return None


@app.post("/db/parameters/bulk/{notebook_id}", response_model=List[ParameterResponse], status_code=201)
def create_bulk_parameters(
    notebook_id: int,
    parameters: List[ParameterCreate],
    db: Session = Depends(get_db)
):
    """
    Create multiple parameter definitions for a notebook in a single request
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    - parameters: Array of parameter objects (request body)
    
    Example request:
    POST /db/parameters/bulk/5
    [
        {
            "notebook_id": 5,
            "param_name": "threshold",
            "param_type": "float",
            "default_value": 0.95,
            "required": true
        },
        {
            "notebook_id": 5,
            "param_name": "max_iterations",
            "param_type": "integer",
            "default_value": 1000,
            "required": false
        }
    ]
    
    Note: All parameters must have notebook_id matching the path parameter.
    
    Returns:
    - Array of created parameter objects
    
    Errors:
    - 404: Notebook not found
    - 400: notebook_id mismatch or duplicate parameter names
    """
    # Check if notebook exists
    notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    created_params = []
    
    for param in parameters:
        # Ensure notebook_id matches
        if param.notebook_id != notebook_id:
            raise HTTPException(
                status_code=400,
                detail=f"Parameter notebook_id must match the URL notebook_id"
            )
        
        # Check for duplicates
        existing = db.query(NotebookParameter).filter(
            NotebookParameter.notebook_id == notebook_id,
            NotebookParameter.param_name == param.param_name
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Parameter '{param.param_name}' already exists for this notebook"
            )
        
        db_param = NotebookParameter(
            notebook_id=param.notebook_id,
            param_name=param.param_name,
            param_type=param.param_type,
            default_value=param.default_value,
            description=param.description,
            required=1 if param.required else 0,
            validation_rules=param.validation_rules
        )
        
        db.add(db_param)
        created_params.append(db_param)
    
    db.commit()
    
    # Refresh and convert to response
    result = []
    for param in created_params:
        db.refresh(param)
        param_response = ParameterResponse.model_validate(param)
        param_response.required = bool(param.required)
        result.append(param_response)
    
    return result


# ===== Execution History =====

@app.get("/db/executions", response_model=List[ExecutionHistoryResponse])
def get_execution_history(
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get notebook execution history with optional filtering
    
    Query Parameters:
    - skip: Number of records to skip for pagination (default: 0)
    - limit: Maximum number of records to return (default: 100)
    - username: Filter by username (optional)
    - status: Filter by status - "success", "failed", "running" (optional)
    
    Example requests:
    GET /db/executions
    GET /db/executions?username=student1&status=success
    GET /db/executions?limit=50&skip=100
    
    Returns:
    - Array of execution records ordered by started_at (newest first)
    - Each record includes: notebook_id, username, paths, parameters, status, timing
    """
    query = db.query(NotebookExecution)
    
    if username:
        query = query.filter(NotebookExecution.username == username)
    
    if status:
        query = query.filter(NotebookExecution.status == status)
    
    executions = query.order_by(NotebookExecution.started_at.desc()).offset(skip).limit(limit).all()
    return executions


@app.get("/db/executions/notebook/{notebook_id}", response_model=List[ExecutionHistoryResponse])
def get_notebook_executions(notebook_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    Get execution history for a specific notebook
    
    Parameters:
    - notebook_id: Notebook ID (path parameter)
    - skip: Number of records to skip (query parameter, default: 0)
    - limit: Maximum records to return (query parameter, default: 50)
    
    Example request:
    GET /db/executions/notebook/5?limit=20
    
    Returns:
    - Array of execution records for this notebook, ordered by started_at (newest first)
    """
    executions = db.query(NotebookExecution).filter(
        NotebookExecution.notebook_id == notebook_id
    ).order_by(NotebookExecution.started_at.desc()).offset(skip).limit(limit).all()
    
    return executions


@app.get("/db/executions/{execution_id}", response_model=ExecutionHistoryResponse)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """
    Get details of a specific notebook execution
    
    Parameters:
    - execution_id: Execution ID (path parameter)
    
    Example request:
    GET /db/executions/123
    
    Returns:
    - Execution record with all details:
        * notebook_id, username
        * input_path, output_path
        * parameters_used (JSON)
        * status, error_message
        * execution_time_seconds
        * started_at, completed_at timestamps
    
    Errors:
    - 404: Execution not found
    """
    execution = db.query(NotebookExecution).filter(NotebookExecution.id == execution_id).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


# ==================== Notebook Submission/Creation Endpoints ====================

class NotebookSubmitRequest(BaseModel):
    """Submit/create a notebook for a user"""
    username: str = Field(..., min_length=1, max_length=100)
    notebook_name: str = Field(..., min_length=1, description="Notebook filename (e.g., 'my_notebook.ipynb')")
    notebook_content: Optional[Dict[str, Any]] = None  # Full notebook JSON structure
    directory: Optional[str] = "notebooks"  # Subdirectory within user's home
    overwrite: bool = False  # Whether to overwrite if file exists

class NotebookCopyRequest(BaseModel):
    """Copy a notebook from source to user's directory"""
    username: str = Field(..., min_length=1, max_length=100)
    source_notebook_id: int  # Notebook ID from database
    new_name: Optional[str] = None  # New name, or use original
    directory: Optional[str] = "notebooks"
    overwrite: bool = False


@app.post("/submit-notebook")
async def submit_notebook(
    username: str,
    file: UploadFile = File(...),
    directory: str = "notebooks",
    overwrite: bool = False,
    save_to_db: bool = True,
    tags: str = "",
    description: str = "",
    db: Session = Depends(get_db)
):
    """
    Upload a notebook file from local machine and save it to:
    1. User's JupyterLab directory
    2. Database registry (optional)
    
    Parameters:
    - username: Target JupyterLab username
    - file: The .ipynb file to upload (multipart form data)
    - directory: Subdirectory in user's home (default: "notebooks")
    - overwrite: Whether to overwrite existing file (default: false)
    - save_to_db: Register notebook in database (default: true)
    - tags: Comma-separated tags for database entry (optional)
    - description: Description for database entry (optional)
    """
    try:
        # Validate user exists
        user_home = f"/home/{username}"
        if not os.path.exists(user_home):
            raise HTTPException(status_code=404, detail=f"User '{username}' does not exist")
        
        # Validate file is a notebook
        if not file.filename.endswith('.ipynb'):
            raise HTTPException(status_code=400, detail="File must be a .ipynb notebook file")
        
        # Create target directory
        target_dir = os.path.join(user_home, directory) if directory else user_home
        os.makedirs(target_dir, exist_ok=True)
        
        # Full path to notebook
        notebook_path = os.path.join(target_dir, file.filename)
        
        # Check if file exists
        if os.path.exists(notebook_path) and not overwrite:
            raise HTTPException(
                status_code=400, 
                detail=f"Notebook '{file.filename}' already exists. Set overwrite=true to replace it."
            )
        
        # Read and validate notebook content
        content = await file.read()
        try:
            notebook_data = json.loads(content)
            # Validate notebook structure
            if "cells" not in notebook_data or "metadata" not in notebook_data:
                raise ValueError("Invalid notebook structure - missing 'cells' or 'metadata'")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in notebook file")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Write notebook file
        with open(notebook_path, 'w') as f:
            json.dump(notebook_data, f, indent=2)
        
        # Set proper ownership
        stat_info = os.stat(user_home)
        os.chown(notebook_path, stat_info.st_uid, stat_info.st_gid)
        os.chown(target_dir, stat_info.st_uid, stat_info.st_gid)
        os.chmod(notebook_path, 0o644)
        
        # Save to database if requested
        db_entry = None
        if save_to_db:
            try:
                # Parse tags
                tag_list = [t.strip() for t in tags.split(",")] if tags else []
                
                # Create database entry
                db_entry = Notebook(
                    name=file.filename,
                    file_path=notebook_path,
                    username=username,
                    description=description or f"Uploaded via API: {file.filename}",
                    tags=tag_list,
                    notebook_metadata=notebook_data.get("metadata", {})
                )
                db.add(db_entry)
                db.commit()
                db.refresh(db_entry)
            except Exception as e:
                # Don't fail the whole request if DB save fails
                print(f"Warning: Failed to save to database: {e}")
        
        return {
            "status": "success",
            "message": "Notebook uploaded and saved successfully",
            "username": username,
            "notebook_path": notebook_path,
            "notebook_name": file.filename,
            "directory": directory,
            "overwrite": overwrite,
            "file_size_bytes": len(content),
            "saved_to_db": save_to_db and db_entry is not None,
            "db_entry_id": db_entry.id if db_entry else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload notebook: {str(e)}")


@app.post("/copy-notebook")
async def copy_notebook_to_user(request: NotebookCopyRequest, db: Session = Depends(get_db)):
    """
    Copy a notebook from database registry to a user's JupyterLab directory
    
    Parameters:
    - username: Target JupyterLab username (required)
    - source_notebook_id: ID of notebook in database to copy (required)
    - new_name: New filename for copied notebook (optional, uses original if not provided)
    - directory: Subdirectory in user's home (default: "notebooks")
    - overwrite: Whether to overwrite if file exists (default: false)
    
    Example request body:
    {
        "username": "student1",
        "source_notebook_id": 5,
        "new_name": "assignment1.ipynb",
        "directory": "assignments",
        "overwrite": false
    }
    
    Use cases:
    - Distribute assignment templates to students
    - Share analysis templates across team
    - Deploy standard notebooks to multiple users
    
    Returns:
    - status: "success"
    - source_notebook_id, source_notebook_name, source_path
    - target_username, target_path, target_name
    - timestamp
    
    Errors:
    - 404: Source notebook or user not found
    - 400: Target file exists and overwrite=false
    """
    try:
        # Get source notebook from database
        source_notebook = db.query(Notebook).filter(Notebook.id == request.source_notebook_id).first()
        if not source_notebook:
            raise HTTPException(status_code=404, detail="Source notebook not found in database")
        
        # Check if source file exists
        if not os.path.exists(source_notebook.file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Source notebook file not found: {source_notebook.file_path}"
            )
        
        # Validate target user
        user_home = f"/home/{request.username}"
        if not os.path.exists(user_home):
            raise HTTPException(
                status_code=404,
                detail=f"User '{request.username}' does not exist"
            )
        
        # Determine target filename
        if request.new_name:
            target_name = request.new_name
            if not target_name.endswith('.ipynb'):
                target_name += '.ipynb'
        else:
            target_name = os.path.basename(source_notebook.file_path)
        
        # Create target directory
        target_dir = os.path.join(user_home, request.directory)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            stat_info = os.stat(user_home)
            os.chown(target_dir, stat_info.st_uid, stat_info.st_gid)
        
        target_path = os.path.join(target_dir, target_name)
        
        # Check if file exists
        if os.path.exists(target_path) and not request.overwrite:
            raise HTTPException(
                status_code=400,
                detail=f"Notebook '{target_name}' already exists. Set overwrite=true to replace it."
            )
        
        # Copy the file
        shutil.copy2(source_notebook.file_path, target_path)
        
        # Set proper ownership
        stat_info = os.stat(user_home)
        os.chown(target_path, stat_info.st_uid, stat_info.st_gid)
        os.chmod(target_path, 0o644)
        
        return {
            "status": "success",
            "message": "Notebook copied successfully",
            "source_notebook_id": request.source_notebook_id,
            "source_notebook_name": source_notebook.name,
            "source_path": source_notebook.file_path,
            "target_username": request.username,
            "target_path": target_path,
            "target_name": target_name,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy notebook: {str(e)}")


@app.post("/upload-notebook")
async def upload_notebook(
    username: str,
    file: UploadFile = File(...),
    directory: str = "notebooks",
    overwrite: bool = False
):
    """
    Upload a notebook file to user's JupyterLab directory (simple upload, no DB registration)
    
    Parameters:
    - username: Target JupyterLab username (query parameter or form field)
    - file: The .ipynb file to upload (multipart form data, required)
    - directory: Subdirectory in user's home (default: "notebooks")
    - overwrite: Whether to overwrite existing file (default: false)
    
    Example cURL request:
    curl -X POST "http://localhost:8002/upload-notebook?username=student1&directory=work" \
      -F "file=@/local/path/notebook.ipynb"
    
    Note: This endpoint does NOT register the notebook in the database.
          Use /submit-notebook if you want DB registration.
    
    Returns:
    - status: "success"
    - username, filename, path
    - size: File size in bytes
    - timestamp
    
    Errors:
    - 404: User not found
    - 400: Invalid file type, file exists, or invalid JSON
    """
    try:
        # Validate username
        user_home = f"/home/{username}"
        if not os.path.exists(user_home):
            raise HTTPException(
                status_code=404,
                detail=f"User '{username}' does not exist"
            )
        
        # Validate file extension
        filename = file.filename
        if not filename or not filename.endswith('.ipynb'):
            raise HTTPException(
                status_code=400,
                detail="File must be a Jupyter notebook (.ipynb)"
            )
        
        # Create target directory
        target_dir = os.path.join(user_home, directory)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            stat_info = os.stat(user_home)
            os.chown(target_dir, stat_info.st_uid, stat_info.st_gid)
        
        target_path = os.path.join(target_dir, filename)
        
        # Check if file exists
        if os.path.exists(target_path) and not overwrite:
            raise HTTPException(
                status_code=400,
                detail=f"Notebook '{filename}' already exists. Set overwrite=true to replace it."
            )
        
        # Save uploaded file
        with open(target_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Validate it's valid JSON
        try:
            with open(target_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            os.remove(target_path)
            raise HTTPException(
                status_code=400,
                detail="Invalid notebook file - not valid JSON"
            )
        
        # Set proper ownership
        stat_info = os.stat(user_home)
        os.chown(target_path, stat_info.st_uid, stat_info.st_gid)
        os.chmod(target_path, 0o644)
        
        return {
            "status": "success",
            "message": "Notebook uploaded successfully",
            "username": username,
            "filename": filename,
            "path": target_path,
            "size": len(content),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload notebook: {str(e)}")


@app.post("/create-from-template")
async def create_notebook_from_template(
    username: str,
    template_name: str,
    new_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    directory: str = "notebooks",
    save_to_db: bool = True,
    db: Session = Depends(get_db)
):
    """
    Create a personalized notebook from a MinIO template with pre-filled parameters
    
    Parameters:
    - username: Target JupyterLab username (query parameter, required)
    - template_name: Name of template notebook in MinIO (query parameter, required)
    - new_name: Filename for new notebook (query parameter, required)
    - directory: Subdirectory in user's home (query parameter, default: "notebooks")
    - parameters: Dictionary of parameter values to inject (request body, optional)
    - save_to_db: Register notebook in database (query parameter, default: true)
    
    Example request:
    POST /create-from-template?username=student1&template_name=ml_template.ipynb&new_name=student1_hw.ipynb&directory=assignments
    Content-Type: application/json
    
    {
        "student_name": "Alice Johnson",
        "student_id": "12345",
        "assignment_number": 1,
        "due_date": "2025-12-01"
    }
    
    Behavior:
    - Downloads template notebook from MinIO
    - If parameters provided, injects them as a code cell at the beginning
    - Parameter cell is tagged with "parameters" for Papermill compatibility
    - Saves to user's JupyterLab directory
    - Optionally registers in database
    - Sets proper file ownership and permissions
    
    Use cases:
    - Create personalized assignments with student info
    - Generate analysis notebooks with custom data paths
    - Deploy parameterized workflows to users
    
    Returns:
    - status: "success"
    - template_name: Name of template used
    - username, new_notebook_path, new_notebook_name
    - parameters_applied: Dictionary of injected parameters
    - saved_to_db: Whether notebook was registered in database
    - db_entry_id: Database ID if saved
    - timestamp
    
    Errors:
    - 404: Template not found in MinIO or user does not exist
    - 400: Notebook with new_name already exists
    """
    try:
        # Get MinIO client
        minio_client = get_minio_client()
        
        # Validate user
        user_home = f"/home/{username}"
        if not os.path.exists(user_home):
            raise HTTPException(status_code=404, detail=f"User '{username}' does not exist")
        
        # Ensure name ends with .ipynb
        if not new_name.endswith('.ipynb'):
            new_name += '.ipynb'
        
        # Create target directory
        target_dir = os.path.join(user_home, directory)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            stat_info = os.stat(user_home)
            os.chown(target_dir, stat_info.st_uid, stat_info.st_gid)
        
        target_path = os.path.join(target_dir, new_name)
        
        if os.path.exists(target_path):
            raise HTTPException(
                status_code=400,
                detail=f"Notebook '{new_name}' already exists"
            )
        
        # Download template from MinIO
        try:
            notebook_data = minio_client.get_notebook_content(template_name)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Template notebook '{template_name}' not found in MinIO"
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # If parameters provided, add them as a code cell at the beginning
        if parameters:
            # Create parameters cell
            param_cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"tags": ["parameters"]},
                "outputs": [],
                "source": []
            }
            
            # Add parameters as Python code
            for key, value in parameters.items():
                if isinstance(value, str):
                    param_cell["source"].append(f'{key} = "{value}"\n')
                else:
                    param_cell["source"].append(f'{key} = {value}\n')
            
            # Insert as first cell
            notebook_data["cells"].insert(0, param_cell)
        
        # Write notebook to user directory
        with open(target_path, 'w') as f:
            json.dump(notebook_data, f, indent=2)
        
        # Set ownership
        stat_info = os.stat(user_home)
        os.chown(target_path, stat_info.st_uid, stat_info.st_gid)
        os.chmod(target_path, 0o644)
        
        # Save to database if requested
        db_entry = None
        if save_to_db:
            try:
                db_entry = Notebook(
                    name=new_name,
                    file_path=target_path,
                    username=username,
                    description=f"Created from template: {template_name}",
                    tags=["from-template", template_name.replace('.ipynb', '')],
                    notebook_metadata=notebook_data.get("metadata", {})
                )
                db.add(db_entry)
                db.commit()
                db.refresh(db_entry)
            except Exception as e:
                print(f"Warning: Failed to save to database: {e}")
        
        return {
            "status": "success",
            "message": "Notebook created from MinIO template",
            "template_name": template_name,
            "username": username,
            "new_notebook_path": target_path,
            "new_notebook_name": new_name,
            "parameters_applied": parameters or {},
            "saved_to_db": save_to_db and db_entry is not None,
            "db_entry_id": db_entry.id if db_entry else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create notebook from template: {str(e)}")

