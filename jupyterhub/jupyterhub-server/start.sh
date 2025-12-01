#!/bin/bash
set -e

echo "🚀 Starting JupyterHub services..."

# Verify MLflow kernel is available
echo "🔍 Checking MLflow kernel..."
if [ -f /opt/.mlflow_kernel_ready ]; then
    echo "✅ MLflow kernel is ready"
    jupyter kernelspec list | grep mlflow_kernel || echo "⚠️  Warning: mlflow_kernel not found"
else
    echo "⚠️  MLflow kernel not set up, running setup..."
    /srv/jupyterhub/setup_kernel.sh
fi

# Start the FastAPI service in the background on port 8002
echo "📡 Starting Papermill API service on port 8002..."
uvicorn set_params:app --host 0.0.0.0 --port 8002 --log-level info --workers 4 &
API_PID=$!

# Give the API a moment to start
sleep 2

# Check if API started successfully
if kill -0 $API_PID 2>/dev/null; then
    echo "✅ Papermill API started successfully (PID: $API_PID)"
else
    echo "❌ Failed to start Papermill API"
    exit 1
fi

# Start JupyterHub (this will run in foreground)
echo "🎯 Starting JupyterHub on port 8000..."
jupyterhub -f /srv/jupyterhub/jupyterhub_config.py
