# Plan: Clean up fork & convert to a uv project

Date: 2026-06-28
Branch: `worktree-uv-conversion-cleanup`

## Goal

Audit the forked `mcp-asusrouter` repo, remove cruft, and convert it to a
modern `uv`-managed Python project so it can be reliably run as an MCP server
with the user's agents.

## Findings (audit)

1. **`paper/`** — 848 KB LaTeX thesis (UP Cebu) unrelated to the MCP server.
   Added in the "thesis paper added" commit. → delete.
2. **Vendored `asusrouter/`** — a wholesale copy of the upstream `asusrouter`
   PyPI package committed into the repo. It *shadows* the pip-installed package
   when running from the repo root, and `requirements.txt` also lists
   `asusrouter` as a dependency. Two sources of truth → delete the vendored copy
   and depend on the pip package.
3. **`requirements.txt` is wrong**: lists `fastmcp` but the code imports
   `from mcp.server.fastmcp import FastMCP` (needs the `mcp` package), and lists
   `uvicorn` which is never imported.
4. **Entry point is a no-op**: `server.py`'s `__main__` block only prints a
   message; `mcp.run()` is commented out, so the server cannot actually launch.
5. **Hardcoded plaintext credentials** in `server.py` (`ROUTER_CONFIG`).
   Flagged for the user; out of scope for this pass (separate follow-up).

## Changes

- Delete `paper/` and the vendored `asusrouter/` directory.
- Add `.serena/`, `.venv/`, and uv artifacts to `.gitignore`.
- Add `pyproject.toml` (uv project) with deps: `aiohttp`, `asusrouter`, `mcp`.
  - `requires-python = ">=3.11"`.
  - Drop bogus `fastmcp` and unused `uvicorn`.
- Replace `requirements.txt` usage with `pyproject.toml` + `uv.lock`
  (keep `requirements.txt`? — superseded; remove it).
- Enable the entry point so `uv run asusrouter-mcp` / `uv run python server.py`
  starts the server via `mcp.run()`.
- Update README install/run instructions for uv.

## Verification

- `uv sync` resolves cleanly.
- `uv run python -c "import server"` imports with no errors (proves every
  `asusrouter.*` import in `server.py` resolves against the pip package now that
  the vendored copy is gone).
- Confirm `mcp.run()` entry point starts the stdio server.

## Out of scope (follow-ups)

- Scrubbing hardcoded credentials → env/config.
- Splitting the 1400-line monolithic `server.py`.
