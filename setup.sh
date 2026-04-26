#!/usr/bin/env bash
# setup.sh — one-time setup for mcp-dosre: build the two container images.
# Idempotent: skips images that are already built. Use clean.sh to undo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# image_name → subdir holding its build-container.sh (image name and subdir
# name diverge here for historical reasons: subdirs are service/ + knowledge/
# but images keep their original mcp-dos-re-* naming).
declare -A SUBDIR=( [mcp-dos-re]=service [mcp-dos-re-knowledge]=knowledge )

for image in mcp-dos-re mcp-dos-re-knowledge; do
    if docker image inspect "$image" >/dev/null 2>&1; then
        echo "Image $image already built — skipping."
    else
        echo "Building image $image..."
        "$SCRIPT_DIR/${SUBDIR[$image]}/build-container.sh"
    fi
done

echo "Done."
