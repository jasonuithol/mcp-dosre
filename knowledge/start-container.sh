#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="mcp-dos-re-knowledge"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_DIR="$SCRIPT_DIR/knowledge"
MODEL_DIR="$SCRIPT_DIR/models/all-MiniLM-L6-v2"

mkdir -p "$KNOWLEDGE_DIR"

if [ ! -f "$MODEL_DIR/onnx/model.onnx" ]; then
    echo "ERROR: Embedding model not found at $MODEL_DIR"
    echo "Run build-container.sh first to download (or link) it."
    exit 1
fi

# Resolve the model dir so podman/docker mounts work whether MODEL_DIR is a
# symlink or a real directory.
MODEL_DIR_REAL="$(readlink -f "$MODEL_DIR")"

# Revive a leftover container from a prior run if one exists; otherwise
# create a fresh one. ChromaDB state lives in the $KNOWLEDGE_DIR volume
# either way, so reviving preserves the seeded index without re-embedding.
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    docker start "$CONTAINER_NAME" >/dev/null
else
    docker run -d \
        --name "$CONTAINER_NAME" \
        --network host \
        --device nvidia.com/gpu=all \
        -e ONNX_PROVIDERS=CUDAExecutionProvider \
        -e PORT=5176 \
        -e COLLECTION_NAME=dosre_knowledge \
        -v "$KNOWLEDGE_DIR:/opt/knowledge" \
        -v "$MODEL_DIR_REAL:/root/.cache/chroma/onnx_models/all-MiniLM-L6-v2:ro" \
        -v "$HOME/Projects:/opt/projects:ro" \
        mcp-dos-re-knowledge
fi
