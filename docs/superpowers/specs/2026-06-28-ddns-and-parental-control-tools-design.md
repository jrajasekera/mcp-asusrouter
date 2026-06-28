# Design: DDNS status + per-device parental-control tools

Date: 2026-06-28
Status: Approved (pending spec review)

## Goal

Add new MCP tools to `mcp-asusrouter` exposing two `asusrouter` capabilities not
currently surfaced by the existing 41 tools:

1. **DDNS status** (read-only).
2. **Per-device parental-control rules** — block a device, block it on a
   schedule, list rules, and remove a rule.

These were chosen after a gap analysis of the installed `asusrouter` 1.21.3 API
against the existing tools.

## Library reality (constraints discovered)

- **DDNS is read-only in the library.** `AsusData.DDNS` is wired for reads, but
  the `ddns` module has no `set_state` and the state dispatcher maps
  `AsusState.DDNS → None`. There is no enable/configure path. (A service
  `DDNS_RESTART` exists but is out of scope.)
- **There is no connection "kick".** `AsusState.CONNECTION` is read-only status
  (`CONNECTED`/`DISCONNECTED`), with no set-state handler. Blocking a device is
  done through **parental-control rules** (`PC_RULE`), which is how ASUS routers
  block devices.
- **Applying a rule merges against the router's cached state.**
  `AsusRouter.async_set_state` passes `router_state=self._state` into
  `parental_control.set_rule`, which reads existing rules from
  `self._state[AsusData.PARENTAL_CONTROL].data["rules"]`. If that cache is empty,
  `write_pc_rules` writes **only the new rule and wipes all others**. Therefore
  every write tool MUST first call `async_get_data(AsusData.PARENTAL_CONTROL)` to
  populate the cache before `async_set_state`.

## Tools

All tools live in `server.py`, follow the existing pattern (one
`create_router_connection()` per call; inner `try/finally` that always
`async_disconnect()` + `session.close()`; outer `try/except` returning
`{"error": str(e)}`; success returns `{"message": ...}` or a data dict), and are
decorated with `@mcp.tool()`. After this change the server exposes 46 tools.

### Reads

#### `get_ddns_status() -> Dict[str, Any]`
- Calls `router.async_get_data(AsusData.DDNS)`.
- Returns `{"ddns": <data>}`, or `{"message": "No DDNS data available"}` when
  `None`. The `ddns` data includes active/inactive status plus a status code and
  human-readable hint (via the library's `process_ddns` / status-hint maps).

#### `list_parental_control_rules() -> Dict[str, Any]`
- Calls `router.async_get_data(AsusData.PARENTAL_CONTROL)`.
- Extracts the `rules` dict (`mac -> ParentalControlRule`) and returns a clean
  list: `{"rules": [{"mac", "name", "type", "timemap"}, ...]}` where `type` is the
  `PCRuleType` name (e.g. `BLOCK`, `TIME`, `DISABLE`). Returns
  `{"rules": []}` when none. This formats what `get_parental_control` only
  returns raw.

### Controls

Shared write pattern:

```python
router, session = await create_router_connection()
try:
    await router.async_get_data(AsusData.PARENTAL_CONTROL)  # preserve existing rules
    rule = ParentalControlRule(mac=mac, name=name, type=<PCRuleType>, timemap=<...>)
    success = await router.async_set_state(rule, expect_modify=True)
    return {"message": ...} if success else {"error": ...}
finally:
    await router.async_disconnect()
    await session.close()
```

#### `block_device(mac: str, name: str = "") -> Dict[str, Any]`
- `ParentalControlRule(mac, name, type=PCRuleType.BLOCK)` (persistent block).

#### `schedule_device_block(mac: str, name: str = "", days: Optional[List[str]] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, timemap: Optional[str] = None) -> Dict[str, Any]`
- `type=PCRuleType.TIME`.
- Timemap resolution (hybrid):
  1. If `timemap` is provided → use it verbatim (trusted path).
  2. Else if `days` + `start_time` + `end_time` are provided → encode via
     `build_timemap()` (see below).
  3. Else → omit `timemap` so the library applies `DEFAULT_PC_TIMEMAP`.
- `days`: list of weekday names/abbreviations (e.g. `["Mon","Tue"]`).
  `start_time`/`end_time`: `"HH:MM"` 24h strings.

#### `unblock_device(mac: str) -> Dict[str, Any]`
- `ParentalControlRule(mac, type=PCRuleType.REMOVE)` → routed to `remove_rule`.
- If `mac` is not among the current rules, the underlying `remove_rule` is a
  no-op. The tool detects this from the pre-fetched rules and returns
  `{"message": "No parental-control rule found for <mac>"}` rather than implying
  a change was made.

### Timemap encoder — `build_timemap(days, start_time, end_time) -> str`

- Target format key: `MULTIFILTER_MACFILTER_DAYTIME_V2`. Library default:
  `W03E21000700<W04122000800`. Segments are joined by `<`; each begins with `W`
  and encodes a weekday set plus a time window.
- **The exact encoding is not documented and could not be verified offline.**
  `build_timemap` will implement the best-understood interpretation, but it is
  **gated**: it must be validated against the router web UI (create a known
  schedule there, read it back via `list_parental_control_rules`, and confirm the
  generated string matches) before it is trusted. Until validated, callers should
  prefer the raw `timemap` override. This caveat is documented in the
  `schedule_device_block` docstring.
- If `build_timemap` cannot confidently encode the request, it raises, and the
  tool surfaces a clear `{"error": ...}` telling the caller to pass a raw
  `timemap`.

## Imports added to `server.py`

```python
from asusrouter.modules.parental_control import ParentalControlRule, PCRuleType
```
(`AsusData`, `AsusState` already imported.) DDNS uses only `AsusData.DDNS`.

## Error handling

Unchanged contract: tools never raise to the caller; failures return
`{"error": str(e)}`, "nothing there" returns `{"message": ...}`. A failed apply
(`success` falsy) returns an `{"error": ...}` describing the failure.

## Verification

Offline (no router required):
- `uv run python -c "import server"` with dummy `ROUTER_*` set imports cleanly.
- The stdio handshake lists **46** tools (41 existing + 5 new).
- Unit-check `build_timemap` against the library default and a couple of known
  cases (once the format is confirmed) and its raise-on-uncertain path.
- Assert the rule dispatch resolves: constructing `ParentalControlRule(...)` and
  confirming `get_datatype`/module resolution points at `parental_control`
  (without calling the network callback).

Hardware (requires the live router — listed as a manual checklist, NOT claimed
as done by the implementation):
- `get_ddns_status` returns real status.
- `block_device` then `list_parental_control_rules` shows the rule and other
  rules are preserved.
- `unblock_device` removes only that rule.
- `schedule_device_block` with friendly inputs produces the same string the web
  UI produces for the same schedule (validates `build_timemap`).

## Out of scope

- DDNS enable/configure (library has no set path).
- Connection "kick"/disconnect (not supported by the library).
- Refactoring the monolithic `server.py`.
- Credential rotation / git-history scrub (tracked separately).
