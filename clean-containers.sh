#!/usr/bin/env bash
# clean-containers.sh — remove the dos-re MCP service containers entirely.
#
# Unlike stop-containers.sh (which leaves stopped containers in place so
# the next start-containers.sh can revive them), this force-removes them.
# Use after rebuilding an image, or when a container's state is wedged and
# revive semantics are hurting rather than helping.
#
# Host-mounted state (e.g. knowledge/knowledge/ ChromaDB data) is NOT
# touched — only the containers themselves.
set -euo pipefail

for name in mcp-dos-re mcp-dos-re-knowledge; do
    echo "Removing $name container..."
    docker rm -f "$name" 2>/dev/null && echo "  removed" || echo "  not present"
done

echo "Done."
