"""
MinIO Helper Module
Handles all MinIO operations for template notebook storage
"""
import os
import io
import json
from datetime import timedelta
from typing import Optional, List, Dict, Any
from minio import Minio
from minio.error import S3Error

class MinIOClient:
    """MinIO client for template notebook storage"""
    
    def __init__(
        self,
        endpoint: str = "host.docker.internal:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        secure: bool = False
    ):
        """
        Initialize MinIO client
        
        Args:
            endpoint: MinIO server endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
            secure: Use HTTPS if True
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = "notebook-templates"
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(bucket_name=self.bucket_name):
                self.client.make_bucket(bucket_name=self.bucket_name)
                print(f"✅ Created MinIO bucket: {self.bucket_name}")
            else:
                print(f"✅ MinIO bucket exists: {self.bucket_name}")
        except S3Error as e:
            print(f"⚠️  Error checking/creating bucket: {e}")
    
    def upload_notebook(
        self,
        notebook_path: str,
        object_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a notebook to MinIO
        
        Args:
            notebook_path: Local path to notebook file
            object_name: Name to store in MinIO (default: filename)
            metadata: Additional metadata to store
        
        Returns:
            Dictionary with upload info
        """
        if not os.path.exists(notebook_path):
            raise FileNotFoundError(f"Notebook not found: {notebook_path}")
        
        if not object_name:
            object_name = os.path.basename(notebook_path)
        
        # Ensure .ipynb extension
        if not object_name.endswith('.ipynb'):
            object_name += '.ipynb'
        
        # Read notebook content
        with open(notebook_path, 'rb') as file_data:
            file_stat = os.stat(notebook_path)
            
            # Upload to MinIO (metadata not supported in v7+, use tags instead if needed)
            result = self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_stat.st_size,
                content_type='application/x-ipynb+json'
            )
        
        return {
            "bucket": self.bucket_name,
            "object_name": object_name,
            "etag": result.etag,
            "size": file_stat.st_size,
            "version_id": result.version_id
        }
    
    def download_notebook(
        self,
        object_name: str,
        destination_path: Optional[str] = None
    ) -> str:
        """
        Download a notebook from MinIO
        
        Args:
            object_name: Name of object in MinIO
            destination_path: Local path to save (default: temp file)
        
        Returns:
            Path to downloaded file
        """
        try:
            # Get object
            response = self.client.get_object(bucket_name=self.bucket_name, object_name=object_name)
            
            # Read content
            content = response.read()
            
            # Validate JSON
            try:
                notebook_data = json.loads(content)
                if "cells" not in notebook_data or "metadata" not in notebook_data:
                    raise ValueError("Invalid notebook structure")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in notebook file")
            
            # Save to destination
            if not destination_path:
                import tempfile
                fd, destination_path = tempfile.mkstemp(suffix='.ipynb')
                os.close(fd)
            
            with open(destination_path, 'wb') as f:
                f.write(content)
            
            return destination_path
            
        except S3Error as e:
            raise FileNotFoundError(f"Notebook not found in MinIO: {object_name}")
        finally:
            response.close()
            response.release_conn()
    
    def get_notebook_content(self, object_name: str) -> Dict[str, Any]:
        """
        Get notebook content as dictionary without saving to file
        
        Args:
            object_name: Name of object in MinIO
        
        Returns:
            Notebook content as dictionary
        """
        try:
            response = self.client.get_object(bucket_name=self.bucket_name, object_name=object_name)
            content = response.read()
            
            notebook_data = json.loads(content)
            
            if "cells" not in notebook_data or "metadata" not in notebook_data:
                raise ValueError("Invalid notebook structure")
            
            return notebook_data
            
        except S3Error as e:
            raise FileNotFoundError(f"Notebook not found in MinIO: {object_name}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in notebook file")
        finally:
            response.close()
            response.release_conn()
    
    def list_notebooks(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List all notebooks in MinIO bucket
        
        Args:
            prefix: Filter by prefix (folder path)
        
        Returns:
            List of notebook objects
        """
        notebooks = []
        
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            for obj in objects:
                if obj.object_name.endswith('.ipynb'):
                    notebooks.append({
                        "name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "etag": obj.etag
                    })
        
        except S3Error as e:
            print(f"Error listing notebooks: {e}")
        
        return notebooks
    
    def delete_notebook(self, object_name: str) -> bool:
        """
        Delete a notebook from MinIO
        
        Args:
            object_name: Name of object to delete
        
        Returns:
            True if successful
        """
        try:
            self.client.remove_object(bucket_name=self.bucket_name, object_name=object_name)
            return True
        except S3Error as e:
            print(f"Error deleting notebook: {e}")
            return False
    
    def get_notebook_url(self, object_name: str, expires: int = 3600) -> str:
        """
        Generate presigned URL for notebook download
        
        Args:
            object_name: Name of object in MinIO
            expires: URL expiration time in seconds (default: 1 hour)
        
        Returns:
            Presigned download URL
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise Exception(f"Error generating URL: {e}")
    
    def notebook_exists(self, object_name: str) -> bool:
        """
        Check if notebook exists in MinIO
        
        Args:
            object_name: Name of object to check
        
        Returns:
            True if exists
        """
        try:
            self.client.stat_object(bucket_name=self.bucket_name, object_name=object_name)
            return True
        except S3Error:
            return False
    
    def get_notebook_metadata(self, object_name: str) -> Dict[str, Any]:
        """
        Get notebook metadata from MinIO
        
        Args:
            object_name: Name of object
        
        Returns:
            Metadata dictionary
        """
        try:
            stat = self.client.stat_object(bucket_name=self.bucket_name, object_name=object_name)
            return {
                "name": object_name,
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "content_type": stat.content_type,
                "metadata": stat.metadata
            }
        except S3Error as e:
            raise FileNotFoundError(f"Notebook not found: {object_name}")


# Singleton instance
_minio_client: Optional[MinIOClient] = None

def get_minio_client() -> MinIOClient:
    """Get or create MinIO client singleton"""
    global _minio_client
    
    if _minio_client is None:
        # Get configuration from environment variables
        endpoint = os.environ.get('MINIO_ENDPOINT', 'host.docker.internal:9000')
        access_key = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
        secret_key = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
        secure = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'
        
        _minio_client = MinIOClient(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
    
    return _minio_client
