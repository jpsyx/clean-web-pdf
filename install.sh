#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install pdf-cleanup as an executable on PATH.

Usage: ./install.sh

Environment:
  BIN_DIR  Installation directory (default: $HOME/.local/bin).

Options:
  -h, --help  Show this help and exit.

Examples:
  ./install.sh
  BIN_DIR=/tmp/bin ./install.sh
EOF
}

case "${1:-}" in
  -h|--help) usage; exit 0;;
  "") ;;
  *) usage >&2; exit 2;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
BIN_DIR="$(cd -- "$BIN_DIR" && pwd)"
PYTHON="$(command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "error: Python 3.10 or newer is required" >&2
  exit 1
fi
VENV="$SCRIPT_DIR/.venv"
if [[ ! -x "$VENV/bin/python" ]] || ! "$VENV/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt"
LAUNCHER="$BIN_DIR/pdf-cleanup"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$SCRIPT_DIR/run.sh" "\$@"
EOF
chmod 0755 "$LAUNCHER"
echo "installed pdf-cleanup -> $LAUNCHER"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "note: $BIN_DIR is not on PATH" >&2 ;;
esac
