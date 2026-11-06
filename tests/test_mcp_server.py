"""Unit tests covering the Pytae Model Context Protocol (MCP) JSON-RPC 2.0 server."""

from __future__ import annotations

import io
import json

from pytae.doc_search import run_mcp_server


def test_mcp_server_initialize_and_ping(monkeypatch):
    """Test MCP server initialize handshake and ping."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ]
    stdin_data = "\n".join(json.dumps(r) for r in requests) + "\n"

    mock_stdin = io.StringIO(stdin_data)
    mock_stdout = io.StringIO()

    monkeypatch.setattr("sys.stdin", mock_stdin)
    monkeypatch.setattr("sys.stdout", mock_stdout)

    code = run_mcp_server()
    assert code == 0

    lines = [line.strip() for line in mock_stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2  # initialize + ping (notifications produce no response)

    # 1. Check initialize response
    init_resp = json.loads(lines[0])
    assert init_resp["id"] == 1
    assert init_resp["result"]["serverInfo"]["name"] == "pytae-docs-mcp"

    # 2. Check ping response
    ping_resp = json.loads(lines[1])
    assert ping_resp["id"] == 2
    assert ping_resp["result"] == {}


def test_mcp_server_tools_list_and_call(monkeypatch):
    """Test MCP tools/list and tools/call execution."""
    requests = [
        {"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "pytae_doc", "arguments": {"query": "explode", "limit": 2}},
        },
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}},
        },
    ]
    stdin_data = "\n".join(json.dumps(r) for r in requests) + "\n"

    mock_stdin = io.StringIO(stdin_data)
    mock_stdout = io.StringIO()

    monkeypatch.setattr("sys.stdin", mock_stdin)
    monkeypatch.setattr("sys.stdout", mock_stdout)

    code = run_mcp_server()
    assert code == 0

    lines = [line.strip() for line in mock_stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 3

    # 1. tools/list
    tools_resp = json.loads(lines[0])
    assert tools_resp["id"] == 10
    tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
    assert "pytae_doc" in tool_names

    # 2. tools/call pytae_doc
    call_resp = json.loads(lines[1])
    assert call_resp["id"] == 11
    content_text = call_resp["result"]["content"][0]["text"]
    assert "explode" in content_text.lower()

    # 3. tools/call invalid tool
    err_resp = json.loads(lines[2])
    assert err_resp["id"] == 12
    assert "error" in err_resp
    assert "Unknown tool" in err_resp["error"]["message"]
