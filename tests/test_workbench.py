"""Unit tests for the pure-Python Pytae Workbench engine."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae.workbench import DisplaySettings, Workbench, is_dataframe


def _sample_df() -> pt.DataFrame:
    return pt.DataFrame({"id": [1, 2, 3, 4], "grp": ["a", "a", "b", "b"], "val": [10.0, 20.0, 30.0, 40.0]})


def test_display_settings_apply_save_load_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTAE_HOME", str(tmp_path))
    s = DisplaySettings()
    assert s.max_rows == 10
    assert s.comma is False

    msg = s.apply_spec("max_rows=25 max_cols=8 float_precision=3 comma=true")
    assert "max_rows=25" in msg
    assert s.max_rows == 25
    assert s.max_cols == 8
    assert s.float_precision == 3
    assert s.comma is True

    save_msg = s.apply_spec("save")
    assert "config.json" in save_msg
    assert (tmp_path / "config.json").exists()

    s2 = DisplaySettings()
    s2.load()
    assert s2.max_rows == 25
    assert s2.max_cols == 8
    assert s2.float_precision == 3
    assert s2.comma is True

    s2.apply_spec("reset")
    assert s2.max_rows == 10
    assert s2.max_cols is None
    assert s2.float_precision is None
    assert s2.comma is False


def test_checkpoint_and_strict_restore_preserves_types() -> None:
    wb = Workbench(load_config=False)
    ns: dict[str, object] = {
        "pt_df": _sample_df(),
        "pl_df": pl.DataFrame({"x": [1, 2]}),
        "pd_df": pd.DataFrame({"y": [3, 4]}),
        "threshold": 25,
    }

    msg = wb.checkpoint("raw", ns, cell_index=1)
    assert "3 tables" in msg
    assert "raw" in wb.checkpoints

    # Mutate existing and add a new table after checkpoint
    ns["pt_df"] = ns["pt_df"].filter("val > 20")  # type: ignore[union-attr]
    ns["extra_df"] = pt.DataFrame({"z": [99]})

    diff_txt = wb.diff_against_checkpoint("pt_df", "raw", ns)
    assert "4 -> 2" in diff_txt

    scrubbed_ids: list[set[int] | None] = []
    restore_msg = wb.restore(
        "raw",
        ns,
        cell_index=4,
        cache_scrub_fn=lambda ids: (scrubbed_ids.append(ids) or 0),
    )
    assert "Restored checkpoint 'raw'" in restore_msg
    assert "dropped: extra_df" in restore_msg
    assert "extra_df" not in ns
    assert isinstance(ns["pt_df"], pt.DataFrame)
    assert ns["pt_df"].shape == (4, 3)
    assert isinstance(ns["pl_df"], pl.DataFrame)
    assert isinstance(ns["pd_df"], pd.DataFrame)
    # Non-DataFrame Python variables remain intact
    assert ns["threshold"] == 25
    assert len(scrubbed_ids) == 1
    assert wb.restore_events == [(1, 4)]

    wb.cleanup()


def test_free_deletes_and_scrubs() -> None:
    wb = Workbench(load_config=False)
    df1 = _sample_df()
    df2 = _sample_df()
    ns: dict[str, object] = {"df1": df1, "df2": df2, "keep_int": 42}

    seen_ids: list[set[int] | None] = []
    msg = wb.free(["df1"], ns, cache_scrub_fn=lambda ids: (seen_ids.append(ids) or 2))
    assert "Freed df1" in msg
    assert "df1" not in ns
    assert "df2" in ns
    assert "keep_int" in ns
    assert seen_ids[0] is not None and id(df1) in seen_ids[0]

    msg_all = wb.free(["*"], ns)
    assert "Freed df2" in msg_all
    assert "df2" not in ns
    assert ns["keep_int"] == 42

    msg_gc = wb.free([], ns, cache_scrub_fn=lambda ids: 1)
    assert "Reclaimed memory" in msg_gc


def test_run_pt_is_immutable_and_supports_line_and_cell(tmp_path: Path) -> None:
    wb = Workbench(load_config=False)
    df = _sample_df()
    ns: dict[str, object] = {"df": df, "cutoff": 15}

    # Line magic: immutable filter with @var interpolation
    res = wb.run_pt('df -filter "val > @cutoff" -arrange "val desc"', ns)
    assert isinstance(res, pt.DataFrame)
    assert res.shape == (3, 3)
    assert res._df["val"].to_list() == [40.0, 30.0, 20.0]
    # Original df is untouched!
    assert ns["df"].shape == (4, 3)  # type: ignore[union-attr]

    # Cell magic assigning to a target variable
    cell_body = """
    df
    -by grp
    -agg "total = sum(val)"
    -arrange "grp"
    """
    out = wb.run_pt("agg_res", ns, cell=cell_body)
    assert out is None
    assert "agg_res" in ns
    assert isinstance(ns["agg_res"], pt.DataFrame)
    assert ns["agg_res"]._df["total"].to_list() == [30.0, 70.0]

    # Read from disk via %pt
    pq = tmp_path / "data.parquet"
    df.to(pq)
    loaded = wb.run_pt(f'{pq} -filter "id >= 3"', ns)
    assert isinstance(loaded, pt.DataFrame)
    assert loaded.shape == (2, 3)

    # Standalone SQL across ns DataFrames
    sql_res = wb.run_pt('-sql "SELECT grp, SUM(val) AS s FROM df GROUP BY grp ORDER BY grp"', ns)
    assert isinstance(sql_res, pt.DataFrame)
    assert sql_res._df["s"].to_list() == [30.0, 70.0]

    # Non-DF terminal op prints and returns None
    captured: list[str] = []
    shape_res = wb.run_pt("df -shape", ns, output_fn=captured.append)
    assert shape_res is None
    assert any("4" in line and "3" in line for line in captured)

    wb.cleanup()


def test_export_session_prunes_rollbacks_and_inspection(tmp_path: Path) -> None:
    wb = Workbench(load_config=False)
    wb.restore_events.append((2, 5))

    history = [
        (1, "import pytae as pt\ndf = pt.sample('penguins')"),
        (2, "%checkpoint raw"),
        (3, "df = df.filter('body_mass_g > 99999')"),  # rolled back
        (4, "%status"),  # rolled back
        (5, "%restore raw"),  # rolled back
        (6, "%status df"),  # inspection magic -> pruned
        (7, "clean = df.dropna('body_mass_g')"),
        (8, "%export out.py"),  # inspection magic -> pruned
    ]

    py_out = tmp_path / "pipeline.py"
    msg_py = wb.export_session(py_out, history)
    assert "Exported 2 cell(s)" in msg_py
    text = py_out.read_text(encoding="utf-8")
    assert "pt.sample('penguins')" in text
    assert "clean = df.dropna('body_mass_g')" in text
    assert "99999" not in text
    assert "%status" not in text
    assert "%checkpoint" not in text

    nb_out = tmp_path / "pipeline.ipynb"
    wb.export_session(nb_out, history)
    nb = json.loads(nb_out.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) == 2
    assert is_dataframe(_sample_df())
