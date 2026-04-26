#!/usr/bin/env bash
# build-container.sh — build the mcp-dos-re container image
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building mcp-dos-re image..."
docker build -f "$SCRIPT_DIR/Dockerfile" -t mcp-dos-re "$SCRIPT_DIR"
echo "Done. Run with: $SCRIPT_DIR/start-container.sh"
