#!/usr/bin/env bash
# start-containers.sh — spin up the dos-re MCP services.
# Service pack only; does not launch Claude.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Preflight: both images must already be built locally. Podman's default
# registry config refuses short-name pulls, which produces a confusing
# error if the user forgot to run build-container.sh first.
# Image names stay as 'mcp-dos-re' and 'mcp-dos-re-knowledge' (set by the
# inner build-container.sh scripts); subdir names are service/ + knowledge/.
declare -A SUBDIR=( [mcp-dos-re]=service [mcp-dos-re-knowledge]=knowledge )
for image in mcp-dos-re mcp-dos-re-knowledge; do
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        echo "Error: image '$image' is not built."
        echo "  Build it first:"
        echo "    $SCRIPT_DIR/${SUBDIR[$image]}/build-container.sh"
        exit 1
    fi
done

# Each inner start-container.sh revives a stopped container if one exists,
# or creates a fresh one otherwise — so calling them repeatedly is safe.
# Use ./clean-containers.sh if you need to force a clean rebuild.
echo "Starting mcp-dos-re..."
"$SCRIPT_DIR/service/start-container.sh"

echo "Starting mcp-dos-re-knowledge..."
"$SCRIPT_DIR/knowledge/start-container.sh"

sleep 1
echo "Done. Services listening on :5175 (dos-re) and :5176 (dos-re-knowledge)."
