# Contributing

Thanks for your interest in improving ASUS Router MCP. This project is a thin
[FastMCP](https://github.com/modelcontextprotocol/python-sdk) wrapper over the
[`asusrouter`](https://pypi.org/project/asusrouter/) library — most new work is
exposing more of that library's capabilities as MCP tools.

## Development setup

This is a [uv](https://docs.astral.sh/uv/) project (Python ≥ 3.11).

```bash
uv sync                 # install runtime + dev dependencies
uv run pytest -q        # run the test suite
```

The tests do not connect to a real router. A root `conftest.py` injects dummy
`ROUTER_*` credentials so `server.py` can be imported (it validates credentials
at import time).

## Project layout

- `server.py` — the single `FastMCP` instance and all `@mcp.tool()` tools.
- `tool_helpers.py` — pure, side-effect-free helpers (e.g. `format_pc_rules`,
  `build_timemap`). Keep logic that can be unit-tested without a router here; it
  must not import `server.py`.
- `tests/` — `pytest` suite covering the pure helpers and tool registration.
- `CLAUDE.md` — architecture, conventions, and gotchas in depth. Read it before
  making non-trivial changes.

## Adding a tool

Every tool is an `async def ... -> Dict[str, Any]` decorated with `@mcp.tool()`,
placed before the `if __name__ == "__main__":` block, and follows this shape:

```python
@mcp.tool()
async def my_tool(arg: str) -> Dict[str, Any]:
    """One-line summary the MCP client shows to the model."""
    try:
        router, session = await create_router_connection()
        try:
            ...  # read with router.async_get_data(AsusData.X)
                 # or change state with router.async_set_state(AsusState.X, ...)
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}
```

Conventions (enforced by review):

- **Never raise to the caller.** Return a data dict, `{"message": ...}` for
  "nothing to report", or `{"error": str(e)}` on failure.
- **One connection per call**, always closed in the inner `finally`.
- **Parental-control writes must pre-fetch.** Call
  `await router.async_get_data(AsusData.PARENTAL_CONTROL)` before
  `async_set_state`, or the library wipes all other rules.
- Put non-trivial pure logic in `tool_helpers.py` with unit tests.

## Verifying

```bash
uv run pytest -q
```

To confirm the server serves your tool end-to-end, launch it and complete an MCP
`initialize` + `tools/list` handshake with any MCP client; it should list the
new tool. Anything that actually touches the router needs a real device.

## Pull requests

Keep changes focused, match the surrounding style, and update the README's tool
list when you add a tool.
