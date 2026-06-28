"""Pure, side-effect-free helpers for the ASUS router MCP tools.

Kept separate from server.py so they can be unit-tested without importing the
server module (which instantiates RouterSettings at import time and therefore
requires ROUTER_* credentials).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


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
