"""Unit and integration tests for terminal-native interactive -browse."""

from __future__ import annotations

import polars as pl

from pytae.tui_browser import browse_dataframe


def test_tui_browser_smoke_with_keys(capsys):
    """Verify browse_dataframe renders, sorts columns, and exits cleanly via mock keys."""
    df = pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "val": [10.5, 20.0, 5.0, 30.0, 15.0],
            "name": ["apple", "banana", "cherry", "date", "elderberry"],
        }
    )

    # Sequence: down -> right -> sort asc -> sort desc -> reset sort -> quit
    keys = iter(["down", "right", "s", "s", "r", "q"])
    browse_dataframe(df, title="test_table", input_fn=lambda: next(keys))
    captured = capsys.readouterr()
    assert "PYTAE WORKBENCH BROWSER :: test_table" in captured.out
    assert "Rows: 1–" in captured.out


def test_tui_browser_fallback_empty_table():
    """Verify empty or None table exits with clear message."""
    outputs: list[str] = []
    browse_dataframe(None, output_fn=outputs.append)
    assert any("no data to browse" in o for o in outputs)

    outputs.clear()
    empty_df = pl.DataFrame({"a": []})
    browse_dataframe(empty_df, title="empty", output_fn=outputs.append)
    assert any("empty table" in o for o in outputs)


