FROM docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

# Install Python. mcp-knowledge-base is fetched as a release tarball over
# plain HTTPS (see requirements.txt), so no git client is required.
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/mcp-dos-re-knowledge

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Application code
COPY mcp-service.py .
COPY ingest/ ingest/

# Knowledge volume mount point
RUN mkdir -p /opt/knowledge

EXPOSE 5176

CMD ["python3", "mcp-service.py"]
