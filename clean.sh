#!/usr/bin/env bash
# clean.sh — undo setup.sh. Removes both containers AND their images so a
# fresh clean → setup → start cycle returns the repo to a verifiable bare
# state. Supersedes the old clean-containers.sh (which only removed
# containers, not images).
#
# Does NOT touch host-mounted state (knowledge/knowledge/ ChromaDB index)
# — that's data, not setup. Delete it manually for a totally fresh KB.
set -euo pipefail

# Containers first (must be removed before their image can be deleted).
for name in mcp-dos-re mcp-dos-re-knowledge; do
    if docker container inspect "$name" >/dev/null 2>&1; then
        echo "Removing container $name..."
        docker rm -f "$name" >/dev/null
    fi
done

for image in mcp-dos-re mcp-dos-re-knowledge; do
    if docker image inspect "$image" >/dev/null 2>&1; then
        echo "Removing image $image..."
        docker rmi -f "$image" >/dev/null
    fi
done

echo "Done."
