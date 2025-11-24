#!/usr/bin/env python3
"""
Example script demonstrating the Notebook Management API

This script shows how to:
1. Register a notebook in the database
2. Add parameters to it
3. Query notebook configurations
4. Execute notebooks with parameters
"""

import requests
import json
from typing import Dict, List, Any

BASE_URL = "http://localhost:8002"


class NotebookManager:
    """Client for the Notebook Management API"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
    
    def health_check(self) -> Dict:
        """Check if API is healthy"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    # Notebook operations
    def register_notebook(
        self,
        name: str,
        file_path: str,
        username: str,
        description: str = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict:
        """Register a notebook in the database"""
        response = requests.post(
            f"{self.base_url}/db/notebooks",
            json={
                "name": name,
                "description": description,
                "file_path": file_path,
                "username": username,
                "tags": tags or [],
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()
    
    def list_notebooks(
        self,
        username: str = None,
        tag: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """List notebooks with optional filters"""
        params = {"skip": skip, "limit": limit}
        if username:
            params["username"] = username
        if tag:
            params["tag"] = tag
        
        response = requests.get(f"{self.base_url}/db/notebooks", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_notebook(self, notebook_id: int) -> Dict:
        """Get a specific notebook with its parameters"""
        response = requests.get(f"{self.base_url}/db/notebooks/{notebook_id}")
        response.raise_for_status()
        return response.json()
    
    def get_user_notebooks(self, username: str) -> List[Dict]:
        """Get all notebooks for a specific user"""
        response = requests.get(f"{self.base_url}/db/notebooks/user/{username}")
        response.raise_for_status()
        return response.json()
    
    def update_notebook(self, notebook_id: int, **updates) -> Dict:
        """Update notebook fields"""
        response = requests.put(
            f"{self.base_url}/db/notebooks/{notebook_id}",
            json=updates
        )
        response.raise_for_status()
        return response.json()
    
    def delete_notebook(self, notebook_id: int) -> None:
        """Delete a notebook"""
        response = requests.delete(f"{self.base_url}/db/notebooks/{notebook_id}")
        response.raise_for_status()
    
    # Parameter operations
    def add_parameter(
        self,
        notebook_id: int,
        param_name: str,
        param_type: str,
        default_value: Any = None,
        description: str = None,
        required: bool = False,
        validation_rules: Dict[str, Any] = None
    ) -> Dict:
        """Add a parameter to a notebook"""
        response = requests.post(
            f"{self.base_url}/db/parameters",
            json={
                "notebook_id": notebook_id,
                "param_name": param_name,
                "param_type": param_type,
                "default_value": default_value,
                "description": description,
                "required": required,
                "validation_rules": validation_rules
            }
        )
        response.raise_for_status()
        return response.json()
    
    def add_parameters_bulk(self, notebook_id: int, parameters: List[Dict]) -> List[Dict]:
        """Add multiple parameters at once"""
        # Ensure all parameters have the correct notebook_id
        for param in parameters:
            param["notebook_id"] = notebook_id
        
        response = requests.post(
            f"{self.base_url}/db/parameters/bulk/{notebook_id}",
            json=parameters
        )
        response.raise_for_status()
        return response.json()
    
    def get_notebook_parameters(self, notebook_id: int) -> List[Dict]:
        """Get all parameters for a notebook"""
        response = requests.get(f"{self.base_url}/db/parameters/notebook/{notebook_id}")
        response.raise_for_status()
        return response.json()
    
    def update_parameter(self, param_id: int, **updates) -> Dict:
        """Update parameter fields"""
        response = requests.put(
            f"{self.base_url}/db/parameters/{param_id}",
            json=updates
        )
        response.raise_for_status()
        return response.json()
    
    def delete_parameter(self, param_id: int) -> None:
        """Delete a parameter"""
        response = requests.delete(f"{self.base_url}/db/parameters/{param_id}")
        response.raise_for_status()
    
    # Execution operations
    def execute_notebook(
        self,
        username: str,
        input_path: str,
        parameters: Dict[str, Any] = None
    ) -> Dict:
        """Execute a notebook with parameters"""
        response = requests.post(
            f"{self.base_url}/execute",
            json={
                "username": username,
                "input_path": input_path,
                "parameters": parameters or {}
            },
            timeout=300
        )
        response.raise_for_status()
        return response.json()
    
    def get_execution_history(
        self,
        username: str = None,
        status: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """Get execution history"""
        params = {"skip": skip, "limit": limit}
        if username:
            params["username"] = username
        if status:
            params["status"] = status
        
        response = requests.get(f"{self.base_url}/db/executions", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_notebook_executions(
        self,
        notebook_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict]:
        """Get execution history for a specific notebook"""
        params = {"skip": skip, "limit": limit}
        response = requests.get(
            f"{self.base_url}/db/executions/notebook/{notebook_id}",
            params=params
        )
        response.raise_for_status()
        return response.json()


def example_workflow():
    """Demonstrate a complete workflow"""
    
    print("=" * 60)
    print("📓 Notebook Management API - Example Workflow")
    print("=" * 60)
    print()
    
    manager = NotebookManager()
    
    # 1. Health check
    print("1️⃣  Checking API health...")
    health = manager.health_check()
    print(f"   Status: {health['status']}")
    print()
    
    # 2. Register a notebook
    print("2️⃣  Registering notebook...")
    notebook = manager.register_notebook(
        name="Data Processing Pipeline",
        file_path="/home/testuser/notebooks/process_data.ipynb",
        username="testuser",
        description="Automated data processing and cleaning",
        tags=["data", "etl", "automation"]
    )
    print(f"   ✅ Registered notebook ID: {notebook['id']}")
    print(f"   Name: {notebook['name']}")
    print(f"   Path: {notebook['file_path']}")
    print()
    
    # 3. Add parameters
    print("3️⃣  Adding parameters...")
    parameters = [
        {
            "notebook_id": notebook['id'],
            "param_name": "input_file",
            "param_type": "string",
            "default_value": "data/input.csv",
            "description": "Path to input data file",
            "required": True
        },
        {
            "notebook_id": notebook['id'],
            "param_name": "output_dir",
            "param_type": "string",
            "default_value": "data/output",
            "description": "Output directory for processed data",
            "required": True
        },
        {
            "notebook_id": notebook['id'],
            "param_name": "batch_size",
            "param_type": "integer",
            "default_value": 1000,
            "description": "Batch size for processing",
            "required": False,
            "validation_rules": {"min": 100, "max": 10000}
        }
    ]
    
    created_params = manager.add_parameters_bulk(notebook['id'], parameters)
    print(f"   ✅ Added {len(created_params)} parameters:")
    for param in created_params:
        req = "REQUIRED" if param['required'] else "optional"
        print(f"      - {param['param_name']} ({param['param_type']}): {param['default_value']} [{req}]")
    print()
    
    # 4. Retrieve notebook with parameters
    print("4️⃣  Retrieving notebook configuration...")
    full_notebook = manager.get_notebook(notebook['id'])
    print(f"   Notebook: {full_notebook['name']}")
    print(f"   Parameters: {len(full_notebook['parameters'])}")
    print()
    
    # 5. List user notebooks
    print("5️⃣  Listing user notebooks...")
    user_notebooks = manager.get_user_notebooks("testuser")
    print(f"   Found {len(user_notebooks)} notebooks for testuser:")
    for nb in user_notebooks:
        print(f"      - {nb['name']} (ID: {nb['id']})")
    print()
    
    # 6. Update notebook
    print("6️⃣  Updating notebook...")
    updated = manager.update_notebook(
        notebook['id'],
        description="Enhanced data processing pipeline with validation",
        tags=["data", "etl", "automation", "production"]
    )
    print(f"   ✅ Updated description and tags")
    print(f"   Tags: {', '.join(updated['tags'])}")
    print()
    
    print("=" * 60)
    print("✅ Workflow completed successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  • Execute the notebook with: manager.execute_notebook(...)")
    print("  • View execution history with: manager.get_execution_history(...)")
    print("  • Explore API docs at: http://localhost:8002/docs")
    print()


def example_query_operations():
    """Demonstrate query and filter operations"""
    
    print("=" * 60)
    print("🔍 Query Examples")
    print("=" * 60)
    print()
    
    manager = NotebookManager()
    
    # Filter by tag
    print("📌 Notebooks tagged with 'production':")
    prod_notebooks = manager.list_notebooks(tag="production")
    for nb in prod_notebooks:
        print(f"   - {nb['name']}")
    print()
    
    # Filter by username
    print("👤 Notebooks for user 'analyst':")
    analyst_notebooks = manager.list_notebooks(username="analyst")
    for nb in analyst_notebooks:
        print(f"   - {nb['name']}")
    print()
    
    # Get execution history
    print("📊 Recent executions:")
    recent_executions = manager.get_execution_history(limit=5)
    for ex in recent_executions:
        print(f"   - {ex['input_path']}: {ex['status']} ({ex['started_at']})")
    print()


if __name__ == "__main__":
    try:
        # Run the example workflow
        example_workflow()
        
        # Optionally uncomment to run query examples
        # example_query_operations()
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API at", BASE_URL)
        print("   Make sure the services are running:")
        print("   docker compose up -d")
    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
