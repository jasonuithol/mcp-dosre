#!/usr/bin/env bash
# start.sh — spin up the dos-re MCP services.
# Service pack only; does not launch Claude.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure images are built (idempotent — setup.sh skips already-built images).
# Replaces the old preflight that just errored out and pointed at
# build-container.sh; orchestrators should self-heal, not fail with
# "go run X first".
"$SCRIPT_DIR/setup.sh"

# Each inner start-container.sh (in service/ and knowledge/) revives a stopped container if one exists,
# or creates a fresh one otherwise — so calling them repeatedly is safe.
# Use ./clean.sh if you need to force a clean rebuild.
echo "Starting mcp-dos-re..."
"$SCRIPT_DIR/service/start-container.sh"

echo "Starting mcp-dos-re-knowledge..."
"$SCRIPT_DIR/knowledge/start-container.sh"

sleep 1
echo "Done. Services listening on :5175 (dos-re) and :5176 (dos-re-knowledge)."
