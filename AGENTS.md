# AGENTS.md: rules for working on clean-web-pdf

Rules for any human or agent modifying this repo. This file is canonical;
`CLAUDE.md` and `.cursorrules` symlink to it, and Codex/opencode read
`AGENTS.md` directly.

## What this repo is

A Python command-line tool that cleans browser-printed article PDFs. `run.sh`
is the clone-local entry point and `install.sh` installs a real executable.

## Entry points

- `run.sh` must run the tool and keep working when called directly from
any location — resolve paths relative to the script (via `BASH_SOURCE`),
never hardcode an absolute or per-machine path.
- Keep its name and location (`run.sh` at the repo root) stable.
- `install.sh` installs one fixed `clean-web-pdf` launcher under `BIN_DIR`,
  defaulting to `$HOME/.local/bin`, and is safe to run repeatedly.

## Hard rules

1. Do not commit, push, merge, or create PRs unless explicitly told to.
2. **This repo may be public.** Never commit secrets, tokens, or
machine-specific paths.
3. Document runtime dependencies in `requirements.txt` and test-only
dependencies in `requirements-dev.txt`.

## Development

- Red/green TDD: write a failing test first, make it pass, then refactor.
- Keep pure logic separately testable from IO.
- Run `.venv/bin/python -m unittest discover -s tests -v` before handoff.
