"""Tests for pytae documentation search engine (SQLite FTS5) and MCP server."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytae as pt
from pytae.doc_search import (
    _sanitize_fts_query,
    build_search_index,
    cli_doc_search,
    format_search_results,
    search_docs,
)


def test_sanitize_fts_query() -> None:
    assert _sanitize_fts_query("") == ""
    assert _sanitize_fts_query("   ") == ""
    res = _sanitize_fts_query("-diff 'on=key'")
    assert "diff" in res
    assert "key" in res


def test_doc_search_direct_keywords(tmp_path: Path) -> None:
    test_db = tmp_path / "test_docs.db"
    build_search_index(test_db)
    assert test_db.exists()

    # Test explode
    res_explode = search_docs("explode", limit=3, db_path=test_db)
    assert len(res_explode) > 0
    assert any("explode" in r.topic.lower() or "explode" in r.title.lower() for r in res_explode)

    # Test diff
    res_diff = search_docs("diff", limit=3, db_path=test_db)
    assert len(res_diff) > 0
    assert any("diff" in r.topic.lower() or "diff" in r.title.lower() for r in res_diff)

    # Test assert
    res_assert = search_docs("assert", limit=3, db_path=test_db)
    assert len(res_assert) > 0
    assert any("assert" in r.topic.lower() or "assert" in r.title.lower() for r in res_assert)


def test_doc_search_synonyms(tmp_path: Path) -> None:
    test_db = tmp_path / "test_docs.db"
    build_search_index(test_db)

    # "flatten list" should rank explode at or near the top
    res_flatten = search_docs("flatten list", limit=3, db_path=test_db)
    assert len(res_flatten) > 0
    assert any("explode" in r.topic.lower() or "explode" in r.title.lower() for r in res_flatten)

    # "schema drift" should match diff
    res_drift = search_docs("schema drift", limit=3, db_path=test_db)
    assert len(res_drift) > 0
    assert any("diff" in r.topic.lower() or "diff" in r.title.lower() for r in res_drift)


def test_doc_search_no_match(tmp_path: Path) -> None:
    test_db = tmp_path / "test_docs.db"
    build_search_index(test_db)

    res = search_docs("xyz_completely_nonexistent_token_12345", limit=3, db_path=test_db)
    assert len(res) == 0

    fmt = format_search_results(res, query="xyz_completely_nonexistent_token_12345")
    assert "No documentation found" in fmt


def test_cli_doc_search_output() -> None:
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = cli_doc_search(["explode"])
    assert code == 0
    output = captured.getvalue()
    assert "explode" in output.lower()
    assert "Syntax:" in output


def test_pt_doc_function() -> None:
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        pt.doc("assert")
    output = captured.getvalue()
    assert "assert" in output.lower()


def test_mcp_server_protocol() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytae", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert proc.stdin is not None
        assert proc.stdout is not None

        # 1. initialize
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp1 = json.loads(line)
        assert resp1["id"] == 1
        assert "serverInfo" in resp1["result"]

        # 2. tools/list
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp2 = json.loads(line)
        assert resp2["id"] == 2
        tool_names = [t["name"] for t in resp2["result"]["tools"]]
        assert "pytae_doc" in tool_names

        # 3. tools/call
        proc.stdin.write(
            json.dumps({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "pytae_doc", "arguments": {"query": "explode"}},
            })
            + "\n"
        )
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp3 = json.loads(line)
        assert resp3["id"] == 3
        content = resp3["result"]["content"][0]["text"]
        assert "explode" in content.lower()

        # 4. ping
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"}) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp4 = json.loads(line)
        assert resp4["id"] == 4

        # 5. unknown tool error
        proc.stdin.write(
            json.dumps({
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool"},
            })
            + "\n"
        )
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp5 = json.loads(line)
        assert resp5["id"] == 5
        assert "error" in resp5

    finally:
        proc.terminate()
        proc.wait(timeout=2)
