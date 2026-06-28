# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An MCP server that exposes ASUS router monitoring and management as 41 tools for
AI agents. It is a thin FastMCP wrapper over the [`asusrouter`](https://pypi.org/project/asusrouter/)
PyPI library — the router protocol/domain logic lives in that dependency, not in
this repo.

## Commands

This is a [`uv`](https://docs.astral.sh/uv/) project.

- Install dependencies: `uv sync`
- Run the server (MCP stdio transport): `uv run python server.py`
- Smoke-test that the module imports: `ROUTER_HOSTNAME=x ROUTER_PASSWORD=y uv run python -c "import server"`

There is **no automated test suite**. To verify the server actually serves
tools, launch it and complete an MCP `initialize` + `tools/list` handshake with
any MCP client — it should report 41 tools. Listing tools does not connect to a
router, so dummy credentials are sufficient for that check.

## Configuration

Router connection settings load from environment variables (prefix `ROUTER_`) or
a local `.env` file (`.env.example` is the template), via the `RouterSettings`
pydantic-settings class:

| Variable | Required | Default |
|----------|----------|---------|
| `ROUTER_HOSTNAME` | yes | — |
| `ROUTER_PASSWORD` | yes | — |
| `ROUTER_USERNAME` | no | `admin` |
| `ROUTER_USE_SSL` | no | `false` |

Credentials must never be hardcoded — the project was deliberately refactored
away from an in-source config dict. `.env` is git-ignored; `.env.example` is not.

## Architecture

Everything lives in `server.py` (~1400 lines):

- A single `FastMCP` instance named `mcp`, with 41 `@mcp.tool()`-decorated async
  functions. `if __name__ == "__main__": mcp.run()` serves them over stdio.
- `RouterSettings` is instantiated at **import time** as the module-level
  `settings`. Consequence: importing `server.py` fails fast with a pydantic
  `ValidationError` unless `ROUTER_HOSTNAME` and `ROUTER_PASSWORD` are available
  (env or `.env`). Set them before importing or running anything.
- `create_router_connection()` opens a fresh `aiohttp.ClientSession` +
  `AsusRouter`, connects, and returns both. Every tool uses this — there is a
  **new connection per call**, no shared/pooled session.

### Tool pattern (follow this when adding tools)

Each tool is an `async def ... -> Dict[str, Any]` with this exact shape:

```python
@mcp.tool()
async def some_tool() -> Dict[str, Any]:
    try:
        router, session = await create_router_connection()
        try:
            ...  # work
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}
```

- Read tools fetch with `router.async_get_data(AsusData.<X>)`.
- Control/mutation tools change state with `router.async_set_state(AsusState.<X>, ...)`.
- Tools never raise to the caller — failures return `{"error": ...}` (and
  "nothing to report" returns `{"message": ...}`). Preserve this contract.
- The enums/clients a tool needs (`AsusData`, `AsusState`, `AsusSystem`,
  `AsusLED`, `AsusWLAN`, `AsusAura`, etc.) are imported at the top of `server.py`
  from `asusrouter.modules.*`. Add new imports there.

## Gotchas

- **Do not vendor the `asusrouter` library into the repo.** A prior copy under
  `asusrouter/` shadowed the pip package on `sys.path` and was removed; depend on
  it through `pyproject.toml` only.
- The `dependencies=[...]` argument passed to `FastMCP(...)` is a FastMCP runtime
  hint, not the dependency source of truth — that is `pyproject.toml` / `uv.lock`.
