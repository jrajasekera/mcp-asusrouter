import asyncio

import server


def _tool_names():
    tools = asyncio.run(server.mcp.list_tools())
    return {t.name for t in tools}


def test_read_tools_registered():
    names = _tool_names()
    assert {"get_ddns_status", "list_parental_control_rules"} <= names


def test_block_tools_registered():
    names = _tool_names()
    assert {"block_device", "unblock_device"} <= names


def test_schedule_tool_registered_and_total_count():
    names = _tool_names()
    assert "schedule_device_block" in names
    assert len(names) == 46
