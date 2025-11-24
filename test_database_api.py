#!/usr/bin/env python3
"""
Test script to verify the database management API is working correctly
"""

import requests
import sys
import time

BASE_URL = "http://localhost:8002"

def color_print(message, color="green"):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{message}{colors['reset']}")

def test_health():
    """Test API health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') in ['healthy', 'degraded']:
                color_print("✅ Health check passed", "green")
                return True
        color_print("❌ Health check failed", "red")
        return False
    except requests.exceptions.ConnectionError:
        color_print("❌ Cannot connect to API. Is it running?", "red")
        return False
    except Exception as e:
        color_print(f"❌ Health check error: {e}", "red")
        return False

def test_database_connection():
    """Test database connectivity by listing notebooks"""
    try:
        response = requests.get(f"{BASE_URL}/db/notebooks", timeout=5)
        if response.status_code == 200:
            color_print("✅ Database connection successful", "green")
            return True
        else:
            color_print(f"❌ Database query failed: {response.status_code}", "red")
            color_print(f"   Response: {response.text}", "yellow")
            return False
    except Exception as e:
        color_print(f"❌ Database connection error: {e}", "red")
        return False

def test_create_notebook():
    """Test creating a notebook entry"""
    try:
        # Use a unique name with timestamp
        timestamp = int(time.time())
        test_data = {
            "name": f"Test Notebook {timestamp}",
            "description": "Test notebook for verification",
            "file_path": f"/tmp/test_{timestamp}.ipynb",
            "username": "testuser",
            "tags": ["test"],
            "metadata": {"test": True}
        }
        
        response = requests.post(
            f"{BASE_URL}/db/notebooks",
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 201:
            notebook = response.json()
            color_print("✅ Notebook creation successful", "green")
            color_print(f"   Created notebook ID: {notebook['id']}", "blue")
            return True, notebook['id']
        else:
            color_print(f"❌ Notebook creation failed: {response.status_code}", "red")
            color_print(f"   Response: {response.text}", "yellow")
            return False, None
    except Exception as e:
        color_print(f"❌ Notebook creation error: {e}", "red")
        return False, None

def test_create_parameter(notebook_id):
    """Test creating a parameter"""
    try:
        test_param = {
            "notebook_id": notebook_id,
            "param_name": "test_param",
            "param_type": "string",
            "default_value": "test_value",
            "description": "Test parameter",
            "required": False
        }
        
        response = requests.post(
            f"{BASE_URL}/db/parameters",
            json=test_param,
            timeout=10
        )
        
        if response.status_code == 201:
            param = response.json()
            color_print("✅ Parameter creation successful", "green")
            color_print(f"   Created parameter ID: {param['id']}", "blue")
            return True, param['id']
        else:
            color_print(f"❌ Parameter creation failed: {response.status_code}", "red")
            color_print(f"   Response: {response.text}", "yellow")
            return False, None
    except Exception as e:
        color_print(f"❌ Parameter creation error: {e}", "red")
        return False, None

def test_get_notebook(notebook_id):
    """Test retrieving a notebook"""
    try:
        response = requests.get(f"{BASE_URL}/db/notebooks/{notebook_id}", timeout=5)
        
        if response.status_code == 200:
            notebook = response.json()
            param_count = len(notebook.get('parameters', []))
            color_print("✅ Notebook retrieval successful", "green")
            color_print(f"   Notebook has {param_count} parameter(s)", "blue")
            return True
        else:
            color_print(f"❌ Notebook retrieval failed: {response.status_code}", "red")
            return False
    except Exception as e:
        color_print(f"❌ Notebook retrieval error: {e}", "red")
        return False

def test_list_notebooks():
    """Test listing notebooks"""
    try:
        response = requests.get(f"{BASE_URL}/db/notebooks?limit=10", timeout=5)
        
        if response.status_code == 200:
            notebooks = response.json()
            color_print(f"✅ Notebook listing successful ({len(notebooks)} notebooks)", "green")
            return True
        else:
            color_print(f"❌ Notebook listing failed: {response.status_code}", "red")
            return False
    except Exception as e:
        color_print(f"❌ Notebook listing error: {e}", "red")
        return False

def test_delete_notebook(notebook_id):
    """Test deleting a notebook"""
    try:
        response = requests.delete(f"{BASE_URL}/db/notebooks/{notebook_id}", timeout=5)
        
        if response.status_code == 204:
            color_print("✅ Notebook deletion successful", "green")
            return True
        else:
            color_print(f"❌ Notebook deletion failed: {response.status_code}", "red")
            return False
    except Exception as e:
        color_print(f"❌ Notebook deletion error: {e}", "red")
        return False

def main():
    print("=" * 60)
    color_print("🧪 Database Management API Test Suite", "blue")
    print("=" * 60)
    print()
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Health check
    print("Test 1: API Health Check")
    tests_total += 1
    if test_health():
        tests_passed += 1
    print()
    
    # Test 2: Database connection
    print("Test 2: Database Connection")
    tests_total += 1
    if test_database_connection():
        tests_passed += 1
    else:
        color_print("\n⚠️  Database connection failed. Stopping tests.", "yellow")
        print_summary(tests_passed, tests_total)
        sys.exit(1)
    print()
    
    # Test 3: Create notebook
    print("Test 3: Create Notebook")
    tests_total += 1
    success, notebook_id = test_create_notebook()
    if success:
        tests_passed += 1
    else:
        color_print("\n⚠️  Cannot proceed without creating a notebook.", "yellow")
        print_summary(tests_passed, tests_total)
        sys.exit(1)
    print()
    
    # Test 4: Create parameter
    print("Test 4: Create Parameter")
    tests_total += 1
    success, param_id = test_create_parameter(notebook_id)
    if success:
        tests_passed += 1
    print()
    
    # Test 5: Get notebook with parameters
    print("Test 5: Retrieve Notebook with Parameters")
    tests_total += 1
    if test_get_notebook(notebook_id):
        tests_passed += 1
    print()
    
    # Test 6: List notebooks
    print("Test 6: List Notebooks")
    tests_total += 1
    if test_list_notebooks():
        tests_passed += 1
    print()
    
    # Test 7: Delete notebook (cleanup)
    print("Test 7: Delete Notebook (Cleanup)")
    tests_total += 1
    if test_delete_notebook(notebook_id):
        tests_passed += 1
    print()
    
    print_summary(tests_passed, tests_total)
    
    if tests_passed == tests_total:
        color_print("\n🎉 All tests passed! Your database management system is working correctly.", "green")
        sys.exit(0)
    else:
        color_print(f"\n⚠️  Some tests failed. Please check the output above.", "yellow")
        sys.exit(1)

def print_summary(passed, total):
    print("=" * 60)
    color_print("Test Summary", "blue")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    percentage = (passed / total * 100) if total > 0 else 0
    print(f"Success rate: {percentage:.1f}%")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        color_print(f"\n❌ Unexpected error: {e}", "red")
        sys.exit(1)
