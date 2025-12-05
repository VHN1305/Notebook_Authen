#!/usr/bin/env python3
"""
Database initialization script for JupyterHub Notebook Manager
Creates the PostgreSQL database and all required tables
"""
import sys
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Database configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST_IP", "34.59.142.41")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mlflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mlflow")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mlflow_db")


def create_database():
    """
    Create the database if it doesn't exist
    """
    try:
        # Connect to PostgreSQL server (default 'postgres' database)
        print(f"🔌 Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}...")
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=POSTGRES_PORT,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{POSTGRES_DB}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"📦 Creating database '{POSTGRES_DB}'...")
            cursor.execute(f'CREATE DATABASE {POSTGRES_DB}')
            print(f"✅ Database '{POSTGRES_DB}' created successfully!")
        else:
            print(f"ℹ️  Database '{POSTGRES_DB}' already exists.")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error creating database: {e}")
        return False


def initialize_tables():
    """
    Initialize all database tables using SQLAlchemy models
    """
    try:
        # Set the database URL environment variable
        database_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        os.environ['DATABASE_URL'] = database_url
        
        print(f"🏗️  Initializing tables in database '{POSTGRES_DB}'...")
        
        # Import and initialize database
        from database import init_db
        init_db()
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing tables: {e}")
        return False


def verify_connection():
    """
    Verify database connection and list tables
    """
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=POSTGRES_PORT,
            database=POSTGRES_DB
        )
        cursor = conn.cursor()
        
        # List all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        
        print("\n📊 Database tables:")
        if tables:
            for table in tables:
                print(f"  ✓ {table[0]}")
        else:
            print("  ⚠️  No tables found")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verifying connection: {e}")
        return False


def main():
    """
    Main initialization flow
    """
    print("=" * 60)
    print("🚀 JupyterHub Notebook Manager - Database Initialization")
    print("=" * 60)
    print()
    
    print("Configuration:")
    print(f"  Host: {POSTGRES_HOST}")
    print(f"  Port: {POSTGRES_PORT}")
    print(f"  User: {POSTGRES_USER}")
    print(f"  Database: {POSTGRES_DB}")
    print()
    
    # Step 1: Create database
    if not create_database():
        print("\n❌ Failed to create database. Exiting.")
        sys.exit(1)
    
    # Step 2: Initialize tables
    if not initialize_tables():
        print("\n❌ Failed to initialize tables. Exiting.")
        sys.exit(1)
    
    # Step 3: Verify connection
    if not verify_connection():
        print("\n❌ Failed to verify connection. Exiting.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Database initialization completed successfully!")
    print("=" * 60)
    print()
    print("You can now use the API to manage notebooks and parameters.")
    print()


if __name__ == "__main__":
    main()
