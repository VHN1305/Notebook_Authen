FROM apache/superset:3.0.0

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python dependencies
RUN pip install \
    psycopg2-binary \
    authlib \
    flask-oidc \
    pyjwt \
    cryptography

# Copy configuration
COPY superset_config.py /app/pythonpath/
COPY superset_init.sh /app/

RUN chmod +x /app/superset_init.sh

USER superset

# Set environment variable to use our config
ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py

ENTRYPOINT ["/app/superset_init.sh"]
