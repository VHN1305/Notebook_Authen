#!/bin/bash
set -e

echo "Starting Superset initialization..."

# Wait for database to be ready with timeout
echo "Waiting for database..."
TIMEOUT=60
ELAPSED=0
DB_HOST="${POSTGRES_HOST_IP:-host.docker.internal}"
DB_PORT="${POSTGRES_PORT:-5432}"
echo "Connecting to database at $DB_HOST:$DB_PORT"
until nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null || [ $ELAPSED -eq $TIMEOUT ]; do
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  echo "Waiting for database... ($ELAPSED/$TIMEOUT seconds)"
done

if [ $ELAPSED -eq $TIMEOUT ]; then
  echo "Warning: Database connection timeout. Proceeding anyway..."
else
  echo "Database is ready!"
fi

# Initialize Superset database
echo "Initializing Superset database..."
# Use stamp instead of upgrade if there are migration issues
superset db upgrade || {
    echo "Migration error detected. Attempting to reset..."
    export SUPERSET_LOAD_EXAMPLES=no
    superset db init || superset db upgrade
}

# Create default admin user if it doesn't exist
echo "Creating admin user..."
superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@superset.com \
    --password admin || echo "Admin user already exists"

# Initialize roles and permissions
echo "Initializing roles and permissions..."
superset init

echo "Superset initialization complete!"

# Start Superset
echo "Starting Superset web server..."
/usr/bin/run-server.sh
