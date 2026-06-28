# DDNS + Per-Device Parental-Control Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 MCP tools to `mcp-asusrouter` exposing DDNS status (read) and per-device parental-control rules (list/block/schedule/unblock).

**Architecture:** Pure, side-effect-free logic (rule formatting, schedule validation) lives in a new `tool_helpers.py` so it is unit-testable without importing `server.py` (which validates `ROUTER_*` credentials at import). The 5 `@mcp.tool()` wrappers in `server.py` stay thin and follow the existing connection-per-call pattern. A minimal `pytest` setup tests the pure logic and tool registration; the actual router apply is covered by a hardware checklist.

**Tech Stack:** Python 3.11+, uv, `mcp` (FastMCP), `asusrouter` 1.21.3, `pydantic-settings`, `pytest` (new dev dependency).

## Global Constraints

- Tools never raise to the caller: success returns a data dict or `{"message": ...}`; failure returns `{"error": str(e)}`. (Existing contract.)
- Every tool opens its own connection via `create_router_connection()` and always `async_disconnect()` + `session.close()` in an inner `try/finally`.
- Write tools MUST call `await router.async_get_data(AsusData.PARENTAL_CONTROL)` before `async_set_state`, or other rules are wiped.
- Importing `server.py` requires `ROUTER_HOSTNAME` and `ROUTER_PASSWORD` to be set (RouterSettings validates at import).
- `asusrouter` is depended on via `pyproject.toml` only — never re-vendored.
- After this change the server exposes exactly **46** tools (41 existing + 5 new).
- DDNS is read-only (library has no DDNS set path). No connection "kick" exists.

---

### Task 1: Test scaffolding + pytest dev dependency

**Files:**
- Modify: `pyproject.toml` (add dev dependency + pytest config)
- Create: `conftest.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a working `uv run pytest`; dummy `ROUTER_*` env available to all tests so `import server` works.

- [ ] **Step 1: Add pytest as a dev dependency**

Run: `uv add --dev pytest`
Expected: `pyproject.toml` gains a `[dependency-groups]` `dev = ["pytest..."]`; `uv.lock` updates; pytest installs.

- [ ] **Step 2: Add pytest config to `pyproject.toml`**

Append this block to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `conftest.py` (repo root) to provide dummy credentials**

```python
import os

# Allow importing server.py (RouterSettings validates ROUTER_* at import time)
# without real credentials. list_tools / pure helpers never connect.
os.environ.setdefault("ROUTER_HOSTNAME", "test.local")
os.environ.setdefault("ROUTER_PASSWORD", "testpass")
```

- [ ] **Step 4: Write the smoke test**

Create `tests/test_smoke.py`:

```python
def test_server_imports_and_has_mcp():
    import server
    assert server.mcp is not None
```

- [ ] **Step 5: Run the smoke test**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock conftest.py tests/test_smoke.py
git commit -m "test: add pytest scaffolding and dummy-credential conftest"
```

---

### Task 2: `format_pc_rules` helper

**Files:**
- Create: `tool_helpers.py`
- Test: `tests/test_tool_helpers.py`

**Interfaces:**
- Consumes: `asusrouter.modules.parental_control.ParentalControlRule`, `PCRuleType` (for tests).
- Produces: `format_pc_rules(pc_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]` — each item `{"mac", "name", "type", "timemap"}` where `type` is the `PCRuleType` name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tool_helpers.py`:

```python
from asusrouter.modules.parental_control import ParentalControlRule, PCRuleType

from tool_helpers import format_pc_rules


def test_format_pc_rules_extracts_fields():
    rule = ParentalControlRule(
        mac="AA:BB:CC:DD:EE:FF", name="Tablet",
        type=PCRuleType.BLOCK, timemap="W03E21000700",
    )
    out = format_pc_rules({"rules": {"AA:BB:CC:DD:EE:FF": rule}})
    assert out == [{
        "mac": "AA:BB:CC:DD:EE:FF", "name": "Tablet",
        "type": "BLOCK", "timemap": "W03E21000700",
    }]


def test_format_pc_rules_handles_empty_and_none():
    assert format_pc_rules(None) == []
    assert format_pc_rules({}) == []
    assert format_pc_rules({"rules": {}}) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tool_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tool_helpers'`.

- [ ] **Step 3: Create `tool_helpers.py` with `format_pc_rules`**

```python
"""Pure, side-effect-free helpers for the ASUS router MCP tools.

Kept separate from server.py so they can be unit-tested without importing the
server module (which instantiates RouterSettings at import time and therefore
requires ROUTER_* credentials).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_pc_rules(pc_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten parental-control data into a clean list of rule dicts.

    Accepts the dict returned by ``async_get_data(AsusData.PARENTAL_CONTROL)``,
    which contains a ``"rules"`` mapping of MAC -> ParentalControlRule.
    """
    if not isinstance(pc_data, dict):
        return []
    rules = pc_data.get("rules") or {}
    result: List[Dict[str, Any]] = []
    for mac, rule in rules.items():
        rule_type = getattr(rule, "type", None)
        result.append({
            "mac": getattr(rule, "mac", mac),
            "name": getattr(rule, "name", "") or "",
            "type": getattr(rule_type, "name", str(rule_type)),
            "timemap": getattr(rule, "timemap", None),
        })
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tool_helpers.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add tool_helpers.py tests/test_tool_helpers.py
git commit -m "feat: add format_pc_rules helper"
```

---

### Task 3: `build_timemap` helper (validation + gated encoding)

**Files:**
- Modify: `tool_helpers.py`
- Test: `tests/test_tool_helpers.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ScheduleEncodingError(Exception)` and `build_timemap(days: List[str], start_time: str, end_time: str) -> str`. Raises `ValueError` on malformed day/time, `ScheduleEncodingError` on empty days and on otherwise-valid input (encoding intentionally not performed until hardware-verified).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tool_helpers.py`:

```python
import pytest

from tool_helpers import build_timemap, ScheduleEncodingError


def test_build_timemap_rejects_unknown_day():
    with pytest.raises(ValueError):
        build_timemap(["Funday"], "21:00", "07:00")


def test_build_timemap_rejects_bad_time():
    with pytest.raises(ValueError):
        build_timemap(["Mon"], "25:00", "07:00")


def test_build_timemap_rejects_empty_days():
    with pytest.raises(ScheduleEncodingError):
        build_timemap([], "21:00", "07:00")


def test_build_timemap_valid_input_raises_until_verified():
    # Encoding is gated on hardware verification; valid input still raises.
    with pytest.raises(ScheduleEncodingError):
        build_timemap(["Mon", "Tue"], "21:00", "07:00")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tool_helpers.py -k build_timemap -v`
Expected: FAIL with `ImportError: cannot import name 'build_timemap'`.

- [ ] **Step 3: Add `ScheduleEncodingError` and `build_timemap` to `tool_helpers.py`**

Add after the imports / before `format_pc_rules`:

```python
class ScheduleEncodingError(Exception):
    """Raised when a schedule cannot be encoded into an ASUS timemap string."""


_WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3, "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def _validate_days(days: List[str]) -> List[int]:
    if not days:
        raise ScheduleEncodingError("At least one weekday is required.")
    out = []
    for d in days:
        key = str(d).strip().lower()
        if key not in _WEEKDAYS:
            raise ValueError(f"Unknown weekday: {d!r}")
        out.append(_WEEKDAYS[key])
    return sorted(set(out))


def _validate_hhmm(value: str, label: str) -> str:
    parts = str(value).strip().split(":")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise ValueError(f"{label} must be HH:MM, got {value!r}")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"{label} out of range: {value!r}")
    return f"{h:02d}{m:02d}"


def build_timemap(days: List[str], start_time: str, end_time: str) -> str:
    """Encode a weekly schedule into an ASUS MULTIFILTER_MACFILTER_DAYTIME_V2
    timemap string.

    Validates inputs, then raises ``ScheduleEncodingError``: the exact wire
    format is undocumented and unverified for this firmware, so automatic
    encoding is intentionally not performed yet. Callers should pass a raw
    ``timemap`` string instead. Once the format is confirmed on hardware (see
    the plan's hardware checklist), replace the final ``raise`` with the real
    encoder — inputs are already validated by this point.
    """
    _validate_days(days)
    _validate_hhmm(start_time, "start_time")
    _validate_hhmm(end_time, "end_time")
    raise ScheduleEncodingError(
        "Automatic schedule encoding is not yet verified for this router. "
        "Pass a raw `timemap` string instead (capture one by setting the "
        "schedule in the router web UI and reading it back via "
        "list_parental_control_rules)."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tool_helpers.py -v`
Expected: PASS (6 tests total).

- [ ] **Step 5: Commit**

```bash
git add tool_helpers.py tests/test_tool_helpers.py
git commit -m "feat: add build_timemap with validation, encoding gated on hardware verification"
```

---

### Task 4: DDNS + list read tools

**Files:**
- Modify: `server.py` (imports near top; new tools appended before the `if __name__ == "__main__"` block)
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `format_pc_rules` (Task 2); existing `create_router_connection`, `AsusData`, `@mcp.tool()`.
- Produces: tools `get_ddns_status` and `list_parental_control_rules`; test helper that lists registered tool names via `server.mcp.list_tools()`.

- [ ] **Step 1: Write the failing registration test**

Create `tests/test_server_tools.py`:

```python
import asyncio

import server


def _tool_names():
    tools = asyncio.run(server.mcp.list_tools())
    return {t.name for t in tools}


def test_read_tools_registered():
    names = _tool_names()
    assert {"get_ddns_status", "list_parental_control_rules"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server_tools.py -v`
Expected: FAIL (assert: the two names are not in the set).

- [ ] **Step 3: Add the import for `format_pc_rules`**

In `server.py`, just after the line `from pydantic_settings import BaseSettings, SettingsConfigDict`, add:

```python
from tool_helpers import format_pc_rules
```

(Tasks 5 and 6 add their own imports for the names they introduce, so each
task's diff only imports what it uses.)

- [ ] **Step 4: Append the two read tools to `server.py`**

Insert immediately before the `# Main execution` / `if __name__ == "__main__":` block:

```python
@mcp.tool()
async def get_ddns_status() -> Dict[str, Any]:
    """Get Dynamic DNS (DDNS) status.

    Reports whether DDNS is active, the registered hostname, and the latest
    status code with a human-readable hint. Read-only.

    Returns:
        Dict[str, Any]: {"ddns": <status data>} or a message if unavailable.
    """
    try:
        router, session = await create_router_connection()
        try:
            data = await router.async_get_data(AsusData.DDNS)
            if data is None:
                return {"message": "No DDNS data available"}
            return {"ddns": data}
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def list_parental_control_rules() -> Dict[str, Any]:
    """List per-device parental-control rules.

    Returns each rule's MAC, friendly name, type (BLOCK/TIME/DISABLE), and raw
    timemap schedule string.

    Returns:
        Dict[str, Any]: {"rules": [{"mac", "name", "type", "timemap"}, ...]}.
    """
    try:
        router, session = await create_router_connection()
        try:
            data = await router.async_get_data(AsusData.PARENTAL_CONTROL)
            return {"rules": format_pc_rules(data)}
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_server_tools.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server_tools.py
git commit -m "feat: add get_ddns_status and list_parental_control_rules tools"
```

---

### Task 5: `block_device` + `unblock_device`

**Files:**
- Modify: `server.py` (append two tools)
- Test: `tests/test_server_tools.py` (extend)

**Interfaces:**
- Consumes: `ParentalControlRule`, `PCRuleType` (imported in Task 4); `format_pc_rules`.
- Produces: tools `block_device(mac, name="")` and `unblock_device(mac)`.

- [ ] **Step 1: Extend the registration test (failing)**

Append to `tests/test_server_tools.py`:

```python
def test_block_tools_registered():
    names = _tool_names()
    assert {"block_device", "unblock_device"} <= names
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_server_tools.py::test_block_tools_registered -v`
Expected: FAIL.

- [ ] **Step 3: Add the parental-control import, then append the two tools to `server.py`** (before the `__main__` block)

First, just after the `from tool_helpers import format_pc_rules` line added in Task 4, add:

```python
from asusrouter.modules.parental_control import ParentalControlRule, PCRuleType
```

Then append:

```python
@mcp.tool()
async def block_device(mac: str, name: str = "") -> Dict[str, Any]:
    """Block a device's internet access by MAC address (persistent).

    Adds a BLOCK parental-control rule. Existing rules are preserved.

    Parameters:
        mac (str): Device MAC address, e.g. "AA:BB:CC:DD:EE:FF".
        name (str): Optional friendly name for the rule.

    Returns:
        Dict[str, Any]: Confirmation or error.
    """
    try:
        router, session = await create_router_connection()
        try:
            # Populate router state so the merge preserves other rules.
            await router.async_get_data(AsusData.PARENTAL_CONTROL)
            rule = ParentalControlRule(mac=mac, name=name, type=PCRuleType.BLOCK)
            success = await router.async_set_state(rule, expect_modify=True)
            if success:
                return {"message": f"Device {mac} blocked."}
            return {"error": f"Failed to block device {mac}."}
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def unblock_device(mac: str) -> Dict[str, Any]:
    """Remove the parental-control rule for a device by MAC address.

    Parameters:
        mac (str): Device MAC address.

    Returns:
        Dict[str, Any]: Confirmation, or a message if no such rule exists.
    """
    try:
        router, session = await create_router_connection()
        try:
            data = await router.async_get_data(AsusData.PARENTAL_CONTROL)
            existing = {r["mac"] for r in format_pc_rules(data)}
            if mac not in existing:
                return {"message": f"No parental-control rule found for {mac}"}
            rule = ParentalControlRule(mac=mac, type=PCRuleType.REMOVE)
            success = await router.async_set_state(rule, expect_modify=True)
            if success:
                return {"message": f"Rule for {mac} removed."}
            return {"error": f"Failed to remove rule for {mac}."}
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_server_tools.py -v`
Expected: PASS (all registration tests).

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server_tools.py
git commit -m "feat: add block_device and unblock_device tools"
```

---

### Task 6: `schedule_device_block`

**Files:**
- Modify: `server.py` (append one tool)
- Test: `tests/test_server_tools.py` (extend, assert total count 46)

**Interfaces:**
- Consumes: `build_timemap`, `ScheduleEncodingError` (imported Task 4); `ParentalControlRule`, `PCRuleType`.
- Produces: tool `schedule_device_block(mac, name="", days=None, start_time=None, end_time=None, timemap=None)`.

- [ ] **Step 1: Extend the registration test (failing)**

Append to `tests/test_server_tools.py`:

```python
def test_schedule_tool_registered_and_total_count():
    names = _tool_names()
    assert "schedule_device_block" in names
    assert len(names) == 46
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_server_tools.py::test_schedule_tool_registered_and_total_count -v`
Expected: FAIL.

- [ ] **Step 3: Extend the tool_helpers import, then append the tool to `server.py`** (before the `__main__` block)

First, update the `from tool_helpers import format_pc_rules` line (added in Task 4) to:

```python
from tool_helpers import build_timemap, format_pc_rules, ScheduleEncodingError
```

Then append:

```python
@mcp.tool()
async def schedule_device_block(
    mac: str,
    name: str = "",
    days: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    timemap: Optional[str] = None,
) -> Dict[str, Any]:
    """Block a device on a recurring time schedule.

    Adds a TIME-type parental-control rule. Provide EITHER a raw ``timemap``
    string (ASUS MULTIFILTER_MACFILTER_DAYTIME_V2 format — the trusted path),
    OR friendly ``days`` + ``start_time`` + ``end_time``. Note: automatic
    encoding of friendly inputs is not yet verified for all firmware and may
    return an error asking for a raw ``timemap``. With no schedule args the
    router's default schedule is used. Existing rules are preserved.

    Parameters:
        mac (str): Device MAC address.
        name (str): Optional friendly name.
        days (list[str]): Weekday names, e.g. ["Mon", "Tue"].
        start_time (str): "HH:MM" 24h.
        end_time (str): "HH:MM" 24h.
        timemap (str): Raw ASUS timemap string (overrides days/start/end).

    Returns:
        Dict[str, Any]: Confirmation or error.
    """
    try:
        if timemap:
            resolved_timemap: Optional[str] = timemap
        elif days or start_time or end_time:
            if not (days and start_time and end_time):
                return {"error": "Provide days, start_time and end_time together, or pass a raw timemap."}
            try:
                resolved_timemap = build_timemap(days, start_time, end_time)
            except (ValueError, ScheduleEncodingError) as e:
                return {"error": str(e)}
        else:
            resolved_timemap = None  # library default schedule

        router, session = await create_router_connection()
        try:
            await router.async_get_data(AsusData.PARENTAL_CONTROL)
            if resolved_timemap is not None:
                rule = ParentalControlRule(
                    mac=mac, name=name, type=PCRuleType.TIME, timemap=resolved_timemap
                )
            else:
                rule = ParentalControlRule(mac=mac, name=name, type=PCRuleType.TIME)
            success = await router.async_set_state(rule, expect_modify=True)
            if success:
                return {"message": f"Scheduled block applied for {mac}."}
            return {"error": f"Failed to apply scheduled block for {mac}."}
        finally:
            await router.async_disconnect()
            await session.close()
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_server_tools.py -v`
Expected: PASS; total tool count is 46.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server_tools.py
git commit -m "feat: add schedule_device_block tool"
```

---

### Task 7: Full verification + docs

**Files:**
- Modify: `README.md` (add the 5 tools), `CLAUDE.md` (update tool count 41 → 46)
- Create: `docs/superpowers/plans/2026-06-28-hardware-verification-checklist.md` (router-required checks)

**Interfaces:**
- Consumes: everything above.
- Produces: passing suite, updated docs, a hardware checklist.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (smoke + 6 helper tests + 4 registration tests).

- [ ] **Step 2: Confirm the server serves 46 tools over stdio**

Run (dummy creds, full handshake):

```bash
ROUTER_HOSTNAME=x ROUTER_PASSWORD=y uv run python - <<'PY'
import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os

async def main():
    env = {**os.environ}
    params = StdioServerParameters(command=sys.executable, args=["server.py"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOL_COUNT", len(tools.tools))
asyncio.run(main())
PY
```

Expected: `TOOL_COUNT 46`.

- [ ] **Step 3: Update `README.md`** — add a "Dynamic DNS" entry for `get_ddns_status` and four entries under "Network Security & Management" for `list_parental_control_rules`, `block_device`, `schedule_device_block`, `unblock_device`, each with a one-line description and an example prompt, matching the existing numbered style.

- [ ] **Step 4: Update `CLAUDE.md`** — change the two "41 tools" references to "46 tools".

- [ ] **Step 5: Create the hardware verification checklist**

Create `docs/superpowers/plans/2026-06-28-hardware-verification-checklist.md`:

```markdown
# Hardware verification checklist (requires the live router)

Set real `ROUTER_HOSTNAME`/`ROUTER_PASSWORD` (and optionally `.env`), then:

- [ ] `get_ddns_status` returns real status (active/inactive, hostname, hint).
- [ ] `block_device(mac)` then `list_parental_control_rules` shows the new BLOCK
      rule AND every previously-existing rule (confirms no wipe).
- [ ] `unblock_device(mac)` removes only that rule; others remain.
- [ ] Decode the timemap format: in the router web UI create a parental-control
      schedule (e.g. Mon+Tue 21:00–07:00), then `list_parental_control_rules`
      and record the `timemap` string. Repeat for 2–3 schedules to derive the
      encoding, then implement it in `build_timemap` (replace the raise) and add
      exact-string unit tests.
- [ ] `schedule_device_block(mac, timemap="<captured string>")` applies and
      reads back correctly.
```

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md docs/superpowers/plans/2026-06-28-hardware-verification-checklist.md
git commit -m "docs: document new tools and add hardware verification checklist"
```

---

## Self-Review

**Spec coverage:**
- get_ddns_status → Task 4. ✓
- list_parental_control_rules → Task 4 (+ format_pc_rules Task 2). ✓
- block_device → Task 5. ✓
- unblock_device (incl. no-rule message) → Task 5. ✓
- schedule_device_block (hybrid: raw + friendly + default) → Task 6 (+ build_timemap Task 3). ✓
- Pre-fetch PARENTAL_CONTROL before write → Tasks 5 & 6. ✓
- Timemap gated/raises → Task 3; raw path trusted → Task 6. ✓
- 46-tool count → Task 6 test. ✓
- Hardware verification → Task 7 checklist. ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete; the `build_timemap` raise is intentional documented behavior, not a placeholder.

**Type consistency:** `format_pc_rules`/`build_timemap`/`ScheduleEncodingError` names and signatures are identical across Tasks 2/3/4/6. Tool names identical across server tasks and tests (`get_ddns_status`, `list_parental_control_rules`, `block_device`, `unblock_device`, `schedule_device_block`).
