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

    # Mutate existing DataFrame + user variable, and add new ones after checkpoint
    ns["pt_df"] = ns["pt_df"].filter("val > 20")  # type: ignore[union-attr]
    ns["extra_df"] = pt.DataFrame({"z": [99]})
    ns["threshold"] = 999
    ns["after_var"] = "should_be_dropped"

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
    assert "extra_df" in restore_msg and "after_var" in restore_msg
    assert "extra_df" not in ns
    assert "after_var" not in ns
    assert isinstance(ns["pt_df"], pt.DataFrame)
    assert ns["pt_df"].shape == (4, 3)
    assert isinstance(ns["pl_df"], pl.DataFrame)
    assert isinstance(ns["pd_df"], pd.DataFrame)
    # User scalar variable was strictly rolled back to its snapshotted value
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

    # `-df` deletes remaining DataFrames while keeping user variables & callables
    ns["helper"] = lambda x: x
    msg_df = wb.free(["-df"], ns)
    assert "Freed df2" in msg_df
    assert "df2" not in ns
    assert ns["keep_int"] == 42
    assert "helper" in ns

    # `*` deletes both DataFrames and user variables while keeping callables/imports
    ns["df3"] = _sample_df()
    msg_all = wb.free(["*"], ns)
    assert "df3" in msg_all and "keep_int" in msg_all
    assert "df3" not in ns and "keep_int" not in ns
    assert "helper" in ns

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


def test_export_prunes_duplicates_and_dead_assignments(tmp_path: Path) -> None:
    wb = Workbench(load_config=False)
    history = [
        (1, "import pytae as pt"),
        (2, "import pytae as pt"),  # duplicate import
        (3, "df = pt.sample('penguins')"),
        (4, "df = pt.sample('penguins')"),  # consecutive duplicate
        (5, "x = df.filter('body_mass_g > 3000')"),  # dead: overwritten at 6 without read
        (6, "x = df.filter('body_mass_g > 4000')"),  # kept
        (7, "y = x.mutate(kg='body_mass_g / 1000')"),  # reads x, kept
        (8, "z = y.to('out.parquet')"),  # side effect -> kept even if overwritten
        (9, "z = y.head(3)"),
    ]
    out_py = tmp_path / "clean.py"
    wb.export_session(out_py, history)
    text = out_py.read_text(encoding="utf-8")
    assert text.count("import pytae as pt") == 1
    assert text.count("df = pt.sample('penguins')") == 1
    assert "3000" not in text
    assert "4000" in text
    assert "y.to(" in text and "out.parquet')" in text
    assert "z = y.head(3)" in text


def test_cli_history_from_ipython_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    from pytae.workbench import get_ipython_history_db, run_cli_history

    monkeypatch.setenv("PYTAE_HOME", str(tmp_path / "pytae_home"))
    monkeypatch.delenv("PYTAE_HISTORY_DB", raising=False)
    db_path = tmp_path / "history.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sessions (session INTEGER PRIMARY KEY, start TIMESTAMP, end TIMESTAMP, num_cmds INTEGER, remark TEXT)")
    conn.execute("CREATE TABLE history (session INTEGER, line INTEGER, source TEXT, source_raw TEXT)")
    conn.execute("INSERT INTO sessions VALUES (9, '2026-11-18 09:00:00', NULL, 2, '')")
    conn.execute("INSERT INTO sessions VALUES (10, '2026-11-19 07:00:00', NULL, 9, '')")
    rows = [
        (9, 1, "", "import pandas as pd"),
        (9, 2, "", "x = 42"),
        (10, 1, "", "import pytae as pt"),
        (10, 2, "", "df = %pt sample:penguins"),
        (10, 3, "", "df"),  # bare preview -> pruned
        (10, 4, "", "%checkpoint raw"),
        (10, 5, "", "df = df.filter('body_mass_g > 99999')"),  # rolled back
        (10, 6, "", "%restore raw"),
        (10, 7, "", "bad_runtime = 1 / 0"),  # marked failed in sidecar
        (10, 8, "", "def broken(:"),  # syntax error -> pruned
        (10, 9, "", "final = df.filter('body_mass_g > 4500')"),
    ]
    conn.executemany("INSERT INTO history VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    # Persist sidecar failed_cells for session 10
    wb = Workbench(load_config=False)
    wb.failed_cells.add(7)
    wb.save_session_meta(10)

    # 1. List sessions (plain formatted, no failed/restore noise)
    listed: list[str] = []
    rc_list = run_cli_history([], db_path=db_path, output_fn=listed.append)
    assert rc_list == 0
    list_text = "\n".join(listed)
    assert "10" in list_text and "import pytae as pt" in list_text
    assert "9" in list_text and "import pandas as pd" in list_text
    assert "failed" not in list_text.lower()
    assert "restore" not in list_text.lower()

    # 1b. List with -n 1 limits to latest session
    listed_1: list[str] = []
    assert run_cli_history(["-n", "1"], db_path=db_path, output_fn=listed_1.append) == 0
    assert any("import pytae as pt" in ln for ln in listed_1)
    assert not any("import pandas as pd" in ln for ln in listed_1)

    # 2. View raw session 10 (plain numbered cells)
    viewed: list[str] = []
    rc_view = run_cli_history(["10"], db_path=db_path, output_fn=viewed.append)
    assert rc_view == 0
    view_text = "\n".join(viewed)
    assert "Session 10" in view_text
    assert "[1] import pytae as pt" in view_text
    assert "[9] final = df.filter('body_mass_g > 4500')" in view_text
    assert "failed" not in view_text.lower()

    # 2b. Relative view (~2 -> session 9)
    viewed_rel: list[str] = []
    assert run_cli_history(["~2"], db_path=db_path, output_fn=viewed_rel.append) == 0
    assert "Session 9" in "\n".join(viewed_rel)
    assert "x = 42" in "\n".join(viewed_rel)

    # 3. Clean preview (-clean) prints pruned runnable Python to stdout
    cleaned: list[str] = []
    rc_clean = run_cli_history(["10", "-clean"], db_path=db_path, output_fn=cleaned.append)
    assert rc_clean == 0
    clean_text = "\n".join(cleaned)
    assert "df = pt.sample('penguins')" in clean_text
    assert "final = df.filter('body_mass_g > 4500')" in clean_text
    assert "99999" not in clean_text
    assert "1 / 0" not in clean_text
    assert "def broken" not in clean_text

    # 4. Search across all sessions (-search)
    searched: list[str] = []
    rc_search = run_cli_history(["-search", "penguins"], db_path=db_path, output_fn=searched.append)
    assert rc_search == 0
    assert len(searched) == 1
    assert searched[0].startswith("10/2")
    assert "sample:penguins" in searched[0]

    # 5. Export session 10 to .py via -o
    out_py = tmp_path / "rescued.py"
    exported: list[str] = []
    rc_exp = run_cli_history(["10", "-o", str(out_py)], db_path=db_path, output_fn=exported.append)
    assert rc_exp == 0
    text = out_py.read_text(encoding="utf-8")
    assert "df = pt.sample('penguins')" in text
    assert "final = df.filter('body_mass_g > 4500')" in text
    assert "99999" not in text
    assert "1 / 0" not in text
    assert "def broken" not in text
    assert "\ndf\n" not in text

    # 6. Export via ~1 to .ipynb
    out_nb = tmp_path / "rescued.ipynb"
    rc_nb = run_cli_history(["~1", "-o", str(out_nb)], db_path=db_path, output_fn=exported.append)
    assert rc_nb == 0
    nb = json.loads(out_nb.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) == 3

    # 7. Load session 10 into IPython (-load) with cell-by-cell store_history=True bootstrap
    loaded_scripts: list[str] = []
    load_msgs: list[str] = []

    def _fake_launcher(script_path: Path) -> int:
        loaded_scripts.append(script_path.read_text(encoding="utf-8"))
        return 0

    rc_load = run_cli_history(["10", "-load"], db_path=db_path, output_fn=load_msgs.append, launcher_fn=_fake_launcher)
    assert rc_load == 0
    assert len(loaded_scripts) == 1
    assert "store_history=True" in loaded_scripts[0]
    assert "pt.sample" in loaded_scripts[0] and "penguins" in loaded_scripts[0]
    assert "body_mass_g > 4500" in loaded_scripts[0]
    assert "1 / 0" not in loaded_scripts[0]
    assert any("Loading session 10" in m for m in load_msgs)

    # 7b. Reject `-load <id>` ordering (must be `<id> -load`)
    rc_bad_order = run_cli_history(["-load", "10"], db_path=db_path, output_fn=load_msgs.append, launcher_fn=_fake_launcher)
    assert rc_bad_order == 1

    # 7c. Load exported .py and .ipynb files via run_cli_load
    from pytae.workbench import run_cli_load

    py_loaded: list[str] = []
    assert run_cli_load(str(out_py), output_fn=load_msgs.append, launcher_fn=lambda p: (py_loaded.append(p.read_text(encoding="utf-8")), 0)[1]) == 0
    assert "store_history=True" in py_loaded[0]
    assert "body_mass_g > 4500" in py_loaded[0]

    nb_loaded: list[str] = []
    assert run_cli_load(str(out_nb), output_fn=load_msgs.append, launcher_fn=lambda p: (nb_loaded.append(p.read_text(encoding="utf-8")), 0)[1]) == 0
    assert "store_history=True" in nb_loaded[0]
    assert "sample:penguins" in nb_loaded[0]

    # 8. One-off -db override and persistent -set-db / -set-db reset (without touching display settings)
    db_msgs: list[str] = []
    assert run_cli_history(["-db", str(db_path), "-n", "1"], output_fn=db_msgs.append) == 0
    assert any("import pytae as pt" in m for m in db_msgs)

    set_msgs: list[str] = []
    assert run_cli_history(["-set-db", str(db_path)], output_fn=set_msgs.append) == 0
    assert get_ipython_history_db() == db_path.resolve()
    # Now bare run_cli_history without db_path uses persisted config
    persisted_list: list[str] = []
    assert run_cli_history([], output_fn=persisted_list.append) == 0
    assert any("import pytae as pt" in m for m in persisted_list)

    # Reset history_db back to default
    reset_msgs: list[str] = []
    assert run_cli_history(["-set-db", "reset"], output_fn=reset_msgs.append) == 0
    assert get_ipython_history_db() != db_path.resolve()


def test_export_auto_infers_startup_imports(tmp_path: Path) -> None:
    wb = Workbench(load_config=False)
    # Simulates a session where pt, pd, pl came from IPython exec_lines (not in In history)
    history = [
        (1, "df = pd.DataFrame({'a': [1, 2, 3]})"),
        (2, "pl_df = pl.from_pandas(df)"),
        (3, "out = pt.DataFrame(pl_df)"),
    ]
    out_py = tmp_path / "auto_imports.py"
    wb.export_session(out_py, history)
    text = out_py.read_text(encoding="utf-8")
    assert "import pytae as pt" in text
    assert "import pandas as pd" in text
    assert "import polars as pl" in text
    assert "import numpy as np" not in text  # unused -> not added

    # Must execute cleanly standalone!
    exec_ns: dict[str, object] = {}
    exec(compile(text, str(out_py), "exec"), exec_ns)
    assert isinstance(exec_ns["out"], pt.DataFrame)

    out_nb = tmp_path / "auto_imports.ipynb"
    wb.export_session(out_nb, history)
    nb = json.loads(out_nb.read_text(encoding="utf-8"))
    first_src = "".join(nb["cells"][0]["source"])
    assert "import pandas as pd" in first_src
    assert "import polars as pl" in first_src


def test_export_fluent_chain_with_round(tmp_path: Path) -> None:
    wb = Workbench(load_config=False)
    history = [
        (1, 'df = %pt "C:\\Users\\demo\\data.parquet"'),
        (
            2,
            'k = %pt df -filter "reporting_date==\'2026-09-30\' and currency==\'USD\'" '
            '-by vertical -agg "rwa=sum(post_crm_tranche_rwa)" -round 1 -arrange "rwa desc"',
        ),
    ]
    out_py = tmp_path / "fluent.py"
    wb.export_session(out_py, history)
    text = out_py.read_text(encoding="utf-8")
    assert "df = pt.read('C:\\\\Users\\\\demo\\\\data.parquet')" in text
    assert ".filter(\"reporting_date=='2026-09-30' and currency=='USD'\")" in text
    assert ".by('vertical')" in text
    assert ".agg('rwa=sum(post_crm_tranche_rwa)')" in text
    assert ".round(1)" in text
    assert ".arrange('rwa desc')" in text
    assert "eval_cli" not in text

    # Also verify DataFrame.round(1) works end-to-end
    sample = pt.DataFrame({"grp": ["a", "b"], "v": [1.234, 5.678]})
    rounded = sample.round(1)
    assert rounded._df["v"].to_list() == [1.2, 5.7]


def test_export_resolves_full_paths_by_default_and_supports_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sales = data_dir / "sales.parquet"
    _sample_df().to(sales)

    wb = Workbench(load_config=False)
    history = [
        (1, 'a = %pt data/sales.parquet -filter "val > 10" -o out/filtered.parquet'),
        (2, 'b = pt.read("data/sales.parquet").to("out/copy.csv")'),
        (3, 'c = pt.scan("data/*.parquet")'),
        (4, 'd = pt.read("s3://my-bucket/file.parquet")'),
        (5, 'recs = b.to("records")'),
    ]

    # Default: full absolute paths for inputs; outputs preserved as typed
    out_dir = tmp_path / "scripts"
    out_abs = out_dir / "abs_export.py"
    wb.export_session(out_abs, history)
    abs_text = out_abs.read_text(encoding="utf-8")
    expected_abs = str(sales.resolve())
    assert f"pt.read({expected_abs!r})" in abs_text
    assert ".to('out/filtered.parquet')" in abs_text
    assert '.to("out/copy.csv")' in abs_text
    assert f"pt.scan({str(data_dir.resolve() / '*.parquet')!r})" in abs_text
    assert "pt.read('s3://my-bucket/file.parquet')" in abs_text
    assert '.to("records")' in abs_text

    # With relative_paths=True (`-relative`): input paths relative to scripts/; outputs preserved as typed
    out_rel = out_dir / "rel_export.py"
    wb.export_session(out_rel, history, relative_paths=True)
    rel_text = out_rel.read_text(encoding="utf-8")
    assert "pt.read('../data/sales.parquet')" in rel_text or "pt.read('..\\\\data\\\\sales.parquet')" in rel_text
    assert ".to('out/filtered.parquet')" in rel_text
    assert '.to("out/copy.csv")' in rel_text
    assert "pt.read('s3://my-bucket/file.parquet')" in rel_text
    assert '.to("records")' in rel_text
