import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae.cli import main


@pytest.fixture
def sample_file(tmp_path):
    path = tmp_path / "penguins_sample.parquet"
    df = pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Gentoo", "Chinstrap"],
            "island": ["Torgersen", "Biscoe", "Biscoe", "Dream"],
            "body_mass_g": [3750.0, 3800.0, 5000.0, 3900.0],
            "bill_len": [39.1, 39.5, 47.5, 48.8],
            "bill_depth": [18.7, 17.4, 14.8, 18.0],
        }
    )
    df.to_parquet(path, index=False)
    return path


def test_library_bar_auto_detect_two_columns():
    df = pd.DataFrame(
        {
            "island": ["Biscoe", "Dream", "Torgersen"],
            "avg_mass": [4716.0, 3712.0, 3706.0],
        }
    )
    res = pt.bar(df)
    assert list(res.columns) == ["island", "avg_mass", "Bar"]
    assert "█" in res["Bar"].iloc[0]
    # Max value has full 20 chars by default
    assert res["Bar"].iloc[0] == "█" * 20
    # Preserves row order
    assert res["island"].tolist() == ["Biscoe", "Dream", "Torgersen"]


def test_library_bar_preserves_metadata_columns():
    df = pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo"],
            "island": ["Torgersen", "Biscoe"],
            "avg_mass": [3700.0, 5000.0],
        }
    )
    res = df.pt.bar("avg_mass")
    assert list(res.columns) == ["species", "island", "avg_mass", "Bar"]
    assert res["Bar"].iloc[1] == "█" * 20


def test_library_bar_options():
    df = pd.DataFrame(
        {
            "island": ["A", "B"],
            "val": [50.0, 100.0],
        }
    )
    # pct=True
    res_pct = pt.bar(df, "val", pct=True)
    assert "(66.7%)" in res_pct["Bar"].iloc[1]

    # custom limit and width
    res_lim = pt.bar(df, "val", limit=(0, 200), width=10)
    assert res_lim["Bar"].iloc[1] == "█" * 5  # 100 / 200 * 10 = 5

    # explicit pair
    res_pair = pt.bar(df, cat="island", val="val")
    assert list(res_pair.columns) == ["island", "val", "Bar"]


def test_library_scatter():
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [2.0, 4.0, 6.0, 8.0, 10.0],
        }
    )
    out = pt.scatter(df, "x:y", width=30, height=8)
    assert "Points: 5" in out
    assert "Corr (r): +1.000" in out
    assert "x" in out and "y" in out

    # Bare scatter on 2 numeric columns auto-detects
    out_bare = df.pt.scatter()
    assert "Points: 5" in out_bare


def test_library_corr_matrix_and_pairs():
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0],
            "b": [2.0, 4.0, 6.0, 8.0],
            "c": [4.0, 3.0, 2.0, 1.0],
            "label": ["w", "x", "y", "z"],  # non-numeric ignored
        }
    )
    # Matrix view (default)
    mat = pt.corr(df)
    assert list(mat.columns) == ["column", "a", "b", "c"]
    assert mat["column"].tolist() == ["a", "b", "c"]
    assert mat["b"].iloc[0] == 1.0
    assert mat["c"].iloc[0] == -1.0

    # Pairs view
    pairs = df.pt.corr(pairs=True)
    assert list(pairs.columns) == ["Column A", "Column B", "Corr", "Strength"]
    assert len(pairs) == 3
    assert pairs["Corr"].iloc[0] in (1.0, -1.0)
    assert "Very Strong" in pairs["Strength"].iloc[0]

    # Target screening
    tgt = df.pt.corr(target="a")
    assert list(tgt.columns) == ["Feature", "Corr", "Bar"]
    assert set(tgt["Feature"].tolist()) == {"b", "c"}
    assert "█" in tgt["Bar"].iloc[0] or "▒" in tgt["Bar"].iloc[0]


def test_library_freq_and_hist_width():
    df = pd.DataFrame({"cat": ["x", "x", "y"], "num": [10.0, 20.0, 30.0]})
    f = df.pt.freq("cat", width=30)
    assert len(f["Distribution"].iloc[0].split()[0]) == 30

    h = df.pt.hist("num:3", width=40)
    assert "█" in h["Distribution"].iloc[0]


def test_cli_bar_and_scatter_and_corr(sample_file, capsys):
    # CLI -bar
    code = main([str(sample_file), "-by", "island", "-agg", "avg_mass=body_mass_g:mean", "-bar"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Bar" in out
    assert "Biscoe" in out

    # CLI -bar with options
    code = main([str(sample_file), "-by", "island", "-agg", "avg_mass=body_mass_g:mean", "-bar", "pct=true"])
    assert code == 0
    out = capsys.readouterr().out
    assert "%" in out

    # CLI -scatter
    code = main([str(sample_file), "-scatter", "bill_len:bill_depth"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Points: 4" in out
    assert "bill_depth" in out

    # CLI -corr matrix
    code = main([str(sample_file), "-select", "bill_len,bill_depth,body_mass_g", "-corr"])
    assert code == 0
    out = capsys.readouterr().out
    assert "column" in out
    assert "bill_len" in out

    # CLI -corr pairs
    code = main([str(sample_file), "-select", "bill_len,bill_depth,body_mass_g", "-corr", "pairs"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Column A" in out
    assert "Strength" in out

    # CLI -corr target
    code = main([str(sample_file), "-corr", "target=body_mass_g"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Feature" in out
    assert "Bar" in out


def test_cli_bar_display_full_rows_up_to_250(tmp_path, capsys):
    import polars as pl

    file_path = tmp_path / "test_25.parquet"
    df = pl.DataFrame({"category": [f"item_{i:02d}" for i in range(25)], "metric": list(range(25))})
    df.write_parquet(file_path)

    code = main([str(file_path), "-bar"])
    assert code == 0
    out = capsys.readouterr().out
    # Check that ellipsis truncation is NOT present and first/middle/last items are all rendered
    assert "item_00" in out
    assert "item_12" in out
    assert "item_24" in out
    assert "…" not in out


def test_cli_plot_preserves_filter(sample_file, tmp_path, monkeypatch):
    from pytae.plotting import Plotter

    captured = []
    orig_save = Plotter.save

    def mock_save(self, path):
        captured.append(self.df.copy())
        return orig_save(self, path)

    monkeypatch.setattr(Plotter, "save", mock_save)

    out_png = tmp_path / "filtered_plot.png"
    code = main(
        [
            str(sample_file),
            "-filter",
            "species == 'Gentoo'",
            "-plot",
            "kind=scatter, x=bill_len, y=bill_depth",
            "-o",
            str(out_png),
        ]
    )
    assert code == 0
    assert len(captured) == 1
    # Sample file has 4 rows, only 1 Gentoo
    assert len(captured[0]) == 1
    assert captured[0]["species"].iloc[0] == "Gentoo"

