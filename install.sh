#!/usr/bin/env bash
# Install or update the command from this checkout.
set -euo pipefail

usage() {
  printf '%s\n' 'Install or update clean-web-pdf as an executable command.

Usage: ./install.sh [--name <command>] [-h|--help]

Options:
  --name <command>  Command filename (default: clean-web-pdf).
  -h, --help        Show this help without installing anything.

Environment:
  BIN_DIR          Installation directory (default: $HOME/.local/bin).

Examples:
  ./install.sh
  BIN_DIR="$HOME/bin" ./install.sh --name clean-web-pdf-dev'
}

for arg in "$@"; do
  case "$arg" in -h|--help) usage; exit 0 ;; esac
done

command_name="clean-web-pdf"
while (($#)); do
  case "$1" in
    --name)
      if (($# < 2)); then usage >&2; exit 2; fi
      command_name="$2"
      shift 2
      ;;
    *) usage >&2; exit 2 ;;
  esac
done
case "$command_name" in
  ''|[.-]*|*..*|*[!a-zA-Z0-9_.-]*) usage >&2; exit 2 ;;
esac
if ((${#command_name} > 100)); then usage >&2; exit 2; fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${BIN_DIR:-$HOME/.local/bin}"
mkdir -p -- "$bin_dir"
bin_dir="$(cd -- "$bin_dir" && pwd)"
destination="$bin_dir/$command_name"
if [[ -d "$destination" ]]; then
  printf 'Cannot replace directory: %s\n' "$destination" >&2
  exit 1
fi
PYTHON="$(command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "error: Python 3.10 or newer is required" >&2
  exit 1
fi
VENV="$script_dir/.venv"
if [[ ! -x "$VENV/bin/python" ]] || ! "$VENV/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$script_dir/requirements.txt"
temporary="$(mktemp "$bin_dir/.install.XXXXXXXX")"
trap 'rm -f -- "$temporary"' EXIT
{
  printf '#!/usr/bin/env bash\n'
  printf 'exec %q "$@"\n' "$script_dir/run.sh"
} > "$temporary"
chmod 755 "$temporary"
mv -f -- "$temporary" "$destination"
[[ -f "$destination" && -x "$destination" ]]
printf 'Installed %s\n' "$destination"

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "note: $bin_dir is not on PATH" >&2 ;;
esac
