FROM python:3.11-slim

# Install Node.js and npm for configurable-http-proxy, plus system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        sudo \
        locales && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    npm install -g configurable-http-proxy && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

WORKDIR /srv/jupyterhub

# Copy requirement file and install Python packages
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy config and API files
COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
COPY set_params.py /srv/jupyterhub/set_params.py
COPY start.sh /srv/jupyterhub/start.sh
RUN chmod +x /srv/jupyterhub/start.sh

# Create directory for user notebooks
RUN mkdir -p /home && chmod 755 /home

# Allow JupyterHub to create users and run sudo commands
RUN echo "jupyterhub ALL=(ALL) NOPASSWD: /usr/sbin/useradd,/usr/sbin/usermod,/bin/mkdir,/bin/chown" >> /etc/sudoers.d/jupyterhub && \
    chmod 0440 /etc/sudoers.d/jupyterhub

EXPOSE 8000 8002

CMD ["/srv/jupyterhub/start.sh"]
