# AGENTS.md — rules for working on pdf-cleanup

Rules for any human or agent modifying this repo. This file is canonical;
`CLAUDE.md` and `.cursorrules` symlink to it, and Codex/opencode read
`AGENTS.md` directly.

## What this repo is

A small, self-contained command-line tool. `run.sh` is the entry point.

## Entry point

- `run.sh` must run the tool and keep working when called directly from
any location — resolve paths relative to the script (via `BASH_SOURCE`),
never hardcode an absolute or per-machine path.
- Keep its name and location (`run.sh` at the repo root) stable.

## Hard rules

1. Do not commit, push, merge, or create PRs unless explicitly told to.
2. **This repo may be public.** Never commit secrets, tokens, or
machine-specific paths.
3. Document runtime dependencies (e.g. a `requirements.txt`) so a fresh
checkout can be run.

## Development

- Red/green TDD: write a failing test first, make it pass, then refactor.
- Keep pure logic separately testable from IO.
