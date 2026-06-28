import asyncio

import server


def _tool_names():
    tools = asyncio.run(server.mcp.list_tools())
    return {t.name for t in tools}


def test_read_tools_registered():
    names = _tool_names()
    assert {"get_ddns_status", "list_parental_control_rules"} <= names
