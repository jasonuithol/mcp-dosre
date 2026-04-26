#!/usr/bin/env bash
# build-container.sh — build mcp-dos-re-knowledge; reuse an existing embedding
# model from claude-pygame or claude-sandbox if present (saves ~90MB).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/models/all-MiniLM-L6-v2"

# Siblings that might already have the model on disk.
SIBLING_CANDIDATES=(
    "$HOME/Projects/claude-pygame/mcp-knowledge/models/all-MiniLM-L6-v2"
    "$HOME/Projects/claude-sandbox/mcp-knowledge/models/all-MiniLM-L6-v2"
)

if [ ! -f "$MODEL_DIR/onnx/model.onnx" ]; then
    mkdir -p "$SCRIPT_DIR/models"
    linked=false
    for candidate in "${SIBLING_CANDIDATES[@]}"; do
        # readlink -f resolves through a symlink so we land on the real dir.
        real="$(readlink -f "$candidate" 2>/dev/null || true)"
        if [ -n "$real" ] && [ -f "$real/onnx/model.onnx" ]; then
            echo "Linking embedding model from $candidate..."
            ln -sfn "$real" "$MODEL_DIR"
            linked=true
            break
        fi
    done

    if ! $linked; then
        echo "Downloading all-MiniLM-L6-v2 embedding model..."
        mkdir -p "$MODEL_DIR"
        TARBALL="$MODEL_DIR/onnx.tar.gz"
        curl -fSL -o "$TARBALL" \
            "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
        tar -xzf "$TARBALL" -C "$MODEL_DIR"
        rm -f "$TARBALL"
        echo "Model downloaded to $MODEL_DIR"
    fi
fi

docker build -t mcp-dos-re-knowledge "$SCRIPT_DIR"
