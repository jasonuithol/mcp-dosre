#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The embedding model is baked into the image (see Dockerfile) — no
# host-side download or sibling-symlink dance.
docker build -t mcp-dos-re-knowledge "$SCRIPT_DIR"
