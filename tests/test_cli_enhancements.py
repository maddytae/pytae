import io
import sys

import pandas as pd
import pytest

from pytae import cli
from pytae.readers import write_dataframe
from tests.cli_helpers import _write_csv


def test_parquet_mixed_object_coercion(tmp_path):
    df = pd.DataFrame({"Profit_Centre": [100.5, 200.0, "0828"], "val": [1, 2, 3]})
    dest = tmp_path / "mixed.parquet"
    with pytest.warns(UserWarning, match="contained mixed object types; coerced to string"):
        write_dataframe(df, dest)
    res = pd.read_parquet(dest)
    assert list(res["Profit_Centre"]) == ["100.5", "200.0", "0828"]
    assert res["val"].tolist() == [1, 2, 3]


class MockStdin:
    def __init__(self, raw_bytes: bytes) -> None:
        self.buffer = io.BytesIO(raw_bytes)


def test_stdin_csv_head_and_shape(monkeypatch, capsys):
    csv_bytes = b"a,b\n1,x\n2,y\n3,z\n"
    monkeypatch.setattr(sys, "stdin", MockStdin(csv_bytes))

    exit_code = cli.main(["-", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"

    monkeypatch.setattr(sys, "stdin", MockStdin(csv_bytes))
    exit_code = cli.main(["-", "-head", "2"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "1" in out and "2" in out and "3" not in out


def test_stdin_parquet_streaming(monkeypatch, capsys):
    df = pd.DataFrame({"col_x": [10, 20], "col_y": ["alpha", "beta"]})
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()

    monkeypatch.setattr(sys, "stdin", MockStdin(parquet_bytes))
    exit_code = cli.main(["-", "-cols"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "col_x" in out and "col_y" in out


def test_stdin_with_sql_and_export(tmp_path, monkeypatch, capsys):
    csv_bytes = b"id,val\n1,10\n2,20\n3,30\n"
    monkeypatch.setattr(sys, "stdin", MockStdin(csv_bytes))
    dest = tmp_path / "filtered.csv"

    exit_code = cli.main(["-", "-sql", "select * from data where id > 1", "-o", str(dest)])
    assert exit_code == 0
    read_back = pd.read_csv(dest)
    assert len(read_back) == 2
    assert read_back["id"].tolist() == [2, 3]


def test_stdin_jsonl_streaming(monkeypatch, capsys):
    jsonl_bytes = b'{"name": "alice", "score": 95}\n{"name": "bob", "score": 88}\n'
    monkeypatch.setattr(sys, "stdin", MockStdin(jsonl_bytes))

    exit_code = cli.main(["-", "-fmt", "jsonl", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 2)"


def test_freq_categorical_bars(tmp_path, capsys):
    df = pd.DataFrame({"category": ["apple", "apple", "apple", "banana", "banana", "cherry"]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-freq", "category"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "category" in out and "Count" in out and "Distribution" in out
    assert "apple" in out and "3" in out and "(50.0%)" in out
    assert "banana" in out and "2" in out and "(33.3%)" in out
    assert "cherry" in out and "1" in out and "(16.7%)" in out
    assert "█" in out


def test_freq_dropna_default_and_flags(tmp_path, capsys):
    df = pd.DataFrame({"category": ["apple", None, "apple"]})
    path = _write_csv(tmp_path, df)

    # Default is dropna=false: retains NA category
    exit_code = cli.main([path, "-freq", "category"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "apple" in out
    assert "NaN" in out or "<NA>" in out or "None" in out or "nan" in out

    # Explicit -dropna true: drops NA category
    exit_code_drop = cli.main([path, "-freq", "category", "-dropna", "true"])
    assert exit_code_drop == 0
    out_drop = capsys.readouterr().out
    assert "apple" in out_drop
    assert "NaN" not in out_drop and "<NA>" not in out_drop and "None" not in out_drop


def test_hist_numeric_distribution(tmp_path, capsys):
    df = pd.DataFrame({"score": [10, 12, 14, 50, 52, 90]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-hist", "score:3"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Range" in out and "Count" in out and "Distribution" in out
    assert "█" in out


def test_cli_plot_save_png(tmp_path, capsys):
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    path = _write_csv(tmp_path, df)
    out_img = tmp_path / "chart.png"

    exit_code = cli.main([path, "-plot", "kind=scatter, x=x, y=y", "-o", str(out_img)])
    assert exit_code == 0
    assert out_img.exists()
    assert out_img.stat().st_size > 0
    assert f"Saved plot to {out_img}" in capsys.readouterr().out


def test_cli_plot_with_finalize(tmp_path, capsys):
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    path = _write_csv(tmp_path, df)
    out_svg = tmp_path / "chart.svg"

    exit_code = cli.main([path, "-plot", "kind=line, x=x, y=y", "-finalize", "style=True", "-o", str(out_svg)])
    assert exit_code == 0
    assert out_svg.exists()
    assert out_svg.stat().st_size > 0


def test_library_plot_save_kwarg(tmp_path):
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    out_file = tmp_path / "lib_plot.png"
    plotter = df.pt.plot(kind="scatter", x="x", y="y", save=str(out_file))
    assert plotter is not None
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_cli_plot_forwards_dropna(tmp_path):
    df = pd.DataFrame({"cat": ["A", "B", None], "val": [10, 20, 30]})
    path = _write_csv(tmp_path, df)
    out_png = tmp_path / "chart.png"

    exit_code = cli.main([path, "-plot", "kind=bar, x=cat, y=val", "-dropna", "true", "-o", str(out_png)])
    assert exit_code == 0
    assert out_png.exists()

