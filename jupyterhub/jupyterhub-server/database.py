"""
Database models and connection management for JupyterHub Notebook Manager
"""
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mlflow:mlflow@localhost:5432/mlflow_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Notebook(Base):
    """
    Notebook model - stores information about notebooks
    """
    __tablename__ = "notebooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False, unique=True)
    username = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    tags = Column(JSON, default=list)  # List of tags for categorization
    notebook_metadata = Column(JSON, default=dict)  # Additional metadata (renamed to avoid SQLAlchemy reserved word)
    
    # Relationship with parameters
    parameters = relationship("NotebookParameter", back_populates="notebook", cascade="all, delete-orphan")
    
    # Add unique constraint for name + username combination
    __table_args__ = (
        UniqueConstraint('name', 'username', name='uq_notebook_name_username'),
    )

    def __repr__(self):
        return f"<Notebook(id={self.id}, name='{self.name}', path='{self.file_path}')>"


class NotebookParameter(Base):
    """
    NotebookParameter model - stores configurable parameters for notebooks
    """
    __tablename__ = "notebook_parameters"

    id = Column(Integer, primary_key=True, index=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True)
    param_name = Column(String(100), nullable=False, index=True)
    param_type = Column(String(50), nullable=False)  # e.g., 'string', 'integer', 'float', 'boolean', 'json'
    default_value = Column(JSON, nullable=True)  # Default value (stored as JSON)
    description = Column(Text, nullable=True)
    required = Column(Integer, default=0)  # 0 = False, 1 = True (SQLite compatible)
    validation_rules = Column(JSON, nullable=True)  # JSON with min, max, regex, options, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship back to notebook
    notebook = relationship("Notebook", back_populates="parameters")
    
    # Add unique constraint for param_name per notebook
    __table_args__ = (
        UniqueConstraint('notebook_id', 'param_name', name='uq_param_name_per_notebook'),
    )

    def __repr__(self):
        return f"<NotebookParameter(id={self.id}, notebook_id={self.notebook_id}, name='{self.param_name}', type='{self.param_type}')>"


class NotebookExecution(Base):
    """
    NotebookExecution model - stores execution history
    """
    __tablename__ = "notebook_executions"

    id = Column(Integer, primary_key=True, index=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(100), nullable=False, index=True)
    input_path = Column(String(512), nullable=False)
    output_path = Column(String(512), nullable=True)
    parameters_used = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False)  # 'success', 'failed', 'running'
    error_message = Column(Text, nullable=True)
    execution_time_seconds = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<NotebookExecution(id={self.id}, notebook_id={self.notebook_id}, status='{self.status}')>"


def get_db():
    """
    Database session dependency for FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def drop_db():
    """
    Drop all tables (use with caution!)
    """
    Base.metadata.drop_all(bind=engine)
    print("⚠️ All database tables dropped!")


if __name__ == "__main__":
    print("Initializing database...")
    print(f"Database URL: {DATABASE_URL}")
    init_db()
