#!/usr/bin/env bash
# Entry point for `pdf-cleanup`. Safe to run directly from anywhere — it
# resolves its own directory rather than assuming a working dir.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# TODO: replace this with the real tool (e.g. exec python3 "$SCRIPT_DIR/main.py" "$@").
echo "pdf-cleanup: hello from $SCRIPT_DIR (args: $*)"
