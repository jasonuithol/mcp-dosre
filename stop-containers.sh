#!/usr/bin/env bash
# stop-containers.sh — shut down the dos-re MCP services.
#
# Default: SIGTERM with grace period (docker stop).
# --kill:  SIGKILL immediately (docker kill). Container is left in place
#          either way so the next start-containers.sh can revive it. For
#          full removal, use ./clean-containers.sh.
set -euo pipefail

FORCE=false
if [ "${1:-}" = "--kill" ]; then
    FORCE=true
fi

for name in mcp-dos-re mcp-dos-re-knowledge; do
    echo "Stopping $name..."
    if [ "$FORCE" = true ]; then
        docker kill "$name" 2>/dev/null && echo "  killed" || echo "  not running"
    else
        docker stop "$name" 2>/dev/null && echo "  stopped" || echo "  not running"
    fi
done

echo "Done."
