#!/bin/bash
# Database Initialization Script for Notebook_Authen Project
# Initializes both JupyterHub notebook tables and Superset data tables

set -e  # Exit on error

echo "============================================================"
echo "🚀 Notebook Authentication System - Database Setup"
echo "============================================================"
echo ""

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_USER="${POSTGRES_USER:-mlflow}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-mlflow}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-mlflow_db}"

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "Configuration:"
echo "  Host: $POSTGRES_HOST"
echo "  Port: $POSTGRES_PORT"
echo "  User: $POSTGRES_USER"
echo "  Database: $POSTGRES_DB"
echo ""

# Check if PostgreSQL is accessible
echo "🔌 Checking PostgreSQL connection..."
if ! psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d postgres -c '\q' 2>/dev/null; then
    echo "❌ Error: Cannot connect to PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT"
    echo "   Please ensure PostgreSQL is running and accessible."
    exit 1
fi
echo "✅ PostgreSQL connection successful!"
echo ""

# Check if database exists, create if not
echo "📦 Checking database '$POSTGRES_DB'..."
DB_EXISTS=$(psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'")

if [ "$DB_EXISTS" != "1" ]; then
    echo "   Creating database '$POSTGRES_DB'..."
    psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d postgres -c "CREATE DATABASE $POSTGRES_DB;"
    echo "   ✅ Database created!"
else
    echo "   ℹ️  Database already exists."
fi
echo ""

# Initialize JupyterHub notebook tables
echo "📓 Initializing JupyterHub notebook tables..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/jupyterhub/jupyterhub-server"
POSTGRES_DB="$POSTGRES_DB" python init_db.py
if [ $? -eq 0 ]; then
    echo "✅ JupyterHub tables initialized!"
else
    echo "❌ Error initializing JupyterHub tables"
    exit 1
fi
echo ""

# Initialize Superset data tables
echo "📊 Initializing Superset data tables..."
cd "$SCRIPT_DIR"
psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -f ./superset/init_superset_db.sql > /dev/null
echo "✅ Superset data tables initialized!"
echo ""

# Verify setup
echo "🔍 Verifying database setup..."
echo ""

# Check schemas
echo "Schemas:"
psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -c "\dn" | grep -E "Name|public|---"
echo ""

# Check notebook tables
echo "JupyterHub notebook tables:"
NOTEBOOK_TABLES=$(psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'notebook%';")
if [ "$NOTEBOOK_TABLES" -ge 3 ]; then
    echo "  ✅ Found $NOTEBOOK_TABLES notebook-related tables"
    psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -c "SELECT '  ✓ ' || tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'notebook%';" -t
else
    echo "  ⚠️  Warning: Only found $NOTEBOOK_TABLES notebook tables (expected 3+)"
fi
echo ""

# Check Superset data tables
echo "Superset data tables:"
SUPERSET_TABLES=$(psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('superset_datasets', 'superset_metrics', 'user_activity');")
if [ "$SUPERSET_TABLES" -ge 3 ]; then
    echo "  ✅ Found $SUPERSET_TABLES Superset data tables"
    psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -c "SELECT '  ✓ ' || tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('superset_datasets', 'superset_metrics', 'user_activity');" -t
else
    echo "  ⚠️  Warning: Only found $SUPERSET_TABLES Superset data tables (expected 3+)"
fi
echo ""

# Total table count
TOTAL_TABLES=$(psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "Total tables in public schema: $TOTAL_TABLES"
echo ""

echo "============================================================"
echo "✅ Database initialization completed successfully!"
echo "============================================================"
echo ""
echo "📝 Next steps:"
echo "   1. Start the services: docker compose up -d"
echo "   2. Access JupyterHub: http://localhost:8000"
echo "   3. Access Superset: http://localhost:8088 (admin/admin)"
echo "   4. Access Keycloak: http://localhost:8080 (admin/secret)"
echo ""
echo "💡 Tip: Superset will create its metadata tables automatically on first start."
echo ""
