#!/usr/bin/env bash
# Start the server-side Gradio UI with one-time PIN protection enabled.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${UNISHARP_PYTHON:-python}"

exec "$PYTHON_BIN" "$REPO_ROOT/scripts/blender_gui.py" --require-pin --pin-only "$@"
