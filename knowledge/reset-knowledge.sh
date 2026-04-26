#!/usr/bin/env bash
# reset-knowledge.sh — wipe the dos-re ChromaDB store and restart the container.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker rm -f mcp-dos-re-knowledge 2>/dev/null || true
rm -rf "$SCRIPT_DIR/knowledge"
mkdir -p "$SCRIPT_DIR/knowledge"

"$SCRIPT_DIR/start-container.sh"
echo "Reset complete."
