#!/usr/bin/env bash
# start-container.sh — run the mcp-dos-re container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONTAINER_NAME="mcp-dos-re"

# Revive a leftover container from a prior run if one exists; otherwise
# create a fresh one with a read-only bind of ~/Projects so the tools can
# inspect any project's files but can never modify them. (Matches the
# mcp-dos-re-knowledge mount shape.)
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    docker start "$CONTAINER_NAME" >/dev/null
else
    docker run -d \
        --name "$CONTAINER_NAME" \
        --network host \
        -v "$HOME/Projects:/opt/projects:ro" \
        -e PROJECTS_DIR=/opt/projects \
        -e KNOWLEDGE_URL=http://localhost:5176/ingest \
        mcp-dos-re
fi
