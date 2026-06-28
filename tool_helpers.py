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
