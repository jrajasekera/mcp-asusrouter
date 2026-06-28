def test_server_imports_and_has_mcp():
    import server
    assert server.mcp is not None
