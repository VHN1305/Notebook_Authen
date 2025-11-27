#!/bin/bash
# Script to create and configure the default MLflow kernel

set -e

echo "🔧 Setting up default MLflow kernel..."

# Kernel name
KERNEL_NAME="mlflow_kernel"
KERNEL_DISPLAY_NAME="Python 3 (MLflow 2.8.0)"
KERNEL_DIR="/usr/local/share/jupyter/kernels/${KERNEL_NAME}"

# Create virtual environment for the kernel
VENV_PATH="/opt/mlflow_env"

# Path to requirements file
REQUIREMENTS_FILE="/srv/jupyterhub/kernel_requirements.txt"

echo "📦 Creating Python virtual environment at ${VENV_PATH}..."
python3 -m venv ${VENV_PATH}

# Activate virtual environment
source ${VENV_PATH}/bin/activate

echo "📥 Installing packages from kernel_requirements.txt..."
# Install essential packages first
pip install --no-cache-dir --upgrade pip setuptools wheel

# Install all packages from requirements file
if [ -f "${REQUIREMENTS_FILE}" ]; then
    echo "📋 Using requirements file: ${REQUIREMENTS_FILE}"
    pip install --no-cache-dir -r "${REQUIREMENTS_FILE}"
else
    echo "⚠️  Requirements file not found: ${REQUIREMENTS_FILE}"
    echo "📥 Installing minimal packages..."
    # Fallback to minimal installation
    pip install --no-cache-dir \
        mlflow==2.8.0 \
        ipykernel \
        ipywidgets \
        numpy \
        pandas \
        matplotlib \
        seaborn \
        scikit-learn \
        scipy \
        requests \
        sqlalchemy \
        psycopg2-binary
fi

# Install the kernel
echo "🔌 Registering IPython kernel..."
python -m ipykernel install \
    --name="${KERNEL_NAME}" \
    --display-name="${KERNEL_DISPLAY_NAME}" \
    --prefix=/usr/local

deactivate

echo "✅ MLflow kernel installed successfully!"

# Verify kernel installation
echo "📋 Installed kernel:"
jupyter kernelspec list | grep ${KERNEL_NAME} || echo "⚠️  Kernel not found in list"

# Create a marker file to indicate kernel is set up
touch /opt/.mlflow_kernel_ready

echo "🎉 Kernel setup complete!"
