"""Pure, side-effect-free helpers for the ASUS router MCP tools.

Kept separate from server.py so they can be unit-tested without importing the
server module (which instantiates RouterSettings at import time and therefore
requires ROUTER_* credentials).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class ScheduleEncodingError(Exception):
    """Raised when a schedule cannot be encoded into an ASUS timemap string."""


# ASUS MULTIFILTER_MACFILTER_DAYTIME_V2 weekday numbering: Sunday=0 ... Saturday=6.
_WEEKDAYS = {
    "sun": 0, "sunday": 0, "mon": 1, "monday": 1, "tue": 2, "tuesday": 2,
    "wed": 3, "wednesday": 3, "thu": 4, "thursday": 4, "fri": 5, "friday": 5,
    "sat": 6, "saturday": 6,
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


def _parse_hhmm(value: str, label: str, allow_24: bool = False) -> tuple[int, int]:
    parts = str(value).strip().split(":")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise ValueError(f"{label} must be HH:MM, got {value!r}")
    h, m = int(parts[0]), int(parts[1])
    max_h = 24 if allow_24 else 23
    if not (0 <= h <= max_h and 0 <= m <= 59) or (h == 24 and m != 0):
        raise ValueError(f"{label} out of range: {value!r}")
    return h, m


def build_timemap(days: List[str], start_time: str, end_time: str) -> str:
    """Encode a weekly schedule into an ASUS ``MULTIFILTER_MACFILTER_DAYTIME_V2``
    timemap string.

    Produces one segment per weekday, all sharing the same daily time window,
    joined by ``<``. Each segment is ``W`` + ``1`` (enabled) + the weekday as two
    digits (Sunday=0 ... Saturday=6) + start ``HHMM`` + end ``HHMM``. An overnight
    window is expressed directly as end < start (e.g. 21:00->07:00); ``end_time``
    may be ``24:00`` to mean end-of-day. Example:
    ``build_timemap(["Mon", "Wed"], "09:00", "17:00")`` ->
    ``"W10109001700<W10309001700"``.

    The format was decoded from the router's own ``weekSchedule.js`` encoder and
    verified round-tripping against an RT-AX55.

    Args:
        days: weekday names/abbreviations, e.g. ``["Mon", "Wed"]``.
        start_time, end_time: ``"HH:MM"`` 24-hour strings.

    Raises:
        ValueError: on an unknown weekday or malformed/out-of-range time.
        ScheduleEncodingError: when ``days`` is empty.
    """
    weekdays = _validate_days(days)
    sh, sm = _parse_hhmm(start_time, "start_time")
    eh, em = _parse_hhmm(end_time, "end_time", allow_24=True)
    segments = [f"W1{wd:02d}{sh:02d}{sm:02d}{eh:02d}{em:02d}" for wd in weekdays]
    return "<".join(segments)


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
        timemap = getattr(rule, "timemap", None)
        if isinstance(timemap, str):
            # The router returns the segment separator '<' HTML-encoded as '&#60'.
            timemap = timemap.replace("&#60", "<")
        result.append({
            "mac": getattr(rule, "mac", mac),
            "name": getattr(rule, "name", "") or "",
            "type": getattr(rule_type, "name", str(rule_type)),
            "timemap": timemap,
        })
    return result
