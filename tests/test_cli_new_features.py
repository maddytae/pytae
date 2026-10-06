import io
import sys
from pathlib import Path

import pandas as pd
import pytest

from pytae.cli import main

PENGUINS_PATH = str(Path(__file__).resolve().parent.parent / "src" / "pytae" / "datasets" / "penguins.parquet")


def test_cli_glimpse(capsys):
    ret = main([PENGUINS_PATH, "-glimpse"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Rows: 344" in captured.out
    assert "Columns: 7" in captured.out
    assert "$ species" in captured.out
    assert "$ body_mass_g" in captured.out


def test_cli_dropna_all_columns(capsys):
    # Dropping all NaNs reduces rows from 344 to 333
    ret = main([PENGUINS_PATH, "-dropna", "-shape"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "(333, 7)" in captured.out


def test_cli_dropna_specific_columns(capsys):
    # Dropping rows with missing body_mass_g reduces rows from 344 to 342
    ret = main([PENGUINS_PATH, "-dropna", "body_mass_g", "-shape"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "(342, 7)" in captured.out


def test_cli_dropna_chained_with_agg(capsys):
    ret = main([PENGUINS_PATH, "-dropna", "body_mass_g", "-by", "species", "-agg", "count=n"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Adelie    151" in captured.out
    assert "Gentoo    123" in captured.out


def test_cli_dropna_unknown_column(capsys):
    with pytest.raises(SystemExit):
        main([PENGUINS_PATH, "-dropna", "nonexistent_col"])
    captured = capsys.readouterr()
    assert "Column 'nonexistent_col' does not exist" in captured.err or "unknown column" in captured.err.lower()


def test_cli_drop_na_deprecated(capsys):
    with pytest.raises(SystemExit) as exc:
        main([PENGUINS_PATH, "-drop_na"])
    assert exc.value.code == 2
    assert "'-drop_na' has been consolidated; use '-dropna' instead" in capsys.readouterr().err


def test_cli_auto_pipe_detection(monkeypatch, capsys):
    # Simulate piped stdin
    csv_data = b"col1,col2\n10,20\n30,40\n"
    fake_stdin = io.BytesIO(csv_data)
    fake_stdin.buffer = fake_stdin

    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(fake_stdin, "isatty", lambda: False)

    # Call main without specifying any path
    ret = main(["-head", "2"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "col1" in captured.out
    assert "10" in captured.out


def test_cli_clipboard_ingestion(monkeypatch, capsys):
    df = pd.DataFrame({"fruit": ["apple", "banana"], "price": [1.5, 2.0]})
    monkeypatch.setattr(pd, "read_clipboard", lambda **kwargs: df.copy())

    # Test pytae clip
    ret = main(["clip", "-head", "2"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "apple" in captured.out
    assert "banana" in captured.out

    # pytae from_clip and pytae clipboard are not recognized as clipboard
    with pytest.raises(SystemExit):
        main(["from_clip", "-shape"])

    with pytest.raises(SystemExit):
        main(["clipboard", "-shape"])
