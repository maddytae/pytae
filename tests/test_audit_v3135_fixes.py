"""Tests covering bug fixes and improvements from the v3.13.5 review:
1. GroupedDataFrame.arrange() preserves descending order on grouping columns.
2. GroupedDataFrame.count() supports additional columns without misinterpreting strings as booleans.
3. GroupedDataFrame.__getattr__ drops stale grouping keys when columns are projected away via select().
4. Single-hyphen CLI flag consistency for -ready and -v / -verbose.
5. with_ties=True with mixed multi-column sort directions raises clean ValueError.
6. Plotter.show() runs silently without emitting UserWarning on non-interactive backends.
"""

from __future__ import annotations

import warnings

import pytest

import pytae as pt
from pytae.cli import build_parser
from pytae.plotting import Plotter
from pytae.repl import PytaeRepl


def test_grouped_arrange_descending_group_column():
    """Bug 2: GroupedDataFrame.arrange() must respect 'desc' on grouping keys."""
    df = pt.DataFrame(
        {
            "species": ["Adelie", "Gentoo", "Chinstrap"],
            "val": [10, 20, 30],
        }
    )
    g = df.by("species").arrange("species desc")
    res = g.to_pandas()
    unique_species = list(res["species"].unique())
    assert unique_species == ["Gentoo", "Chinstrap", "Adelie"]


def test_grouped_count_with_extra_columns():
    """Bug 3: GroupedDataFrame.count('col') must include extra columns in count instead of treating them as booleans."""
    df = pt.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Gentoo", "Gentoo"],
            "island": ["Torgersen", "Biscoe", "Biscoe", "Biscoe"],
        }
    )
    # Count grouped by species and island
    res = df.by("species").count("island")
    assert "species" in res.columns
    assert "island" in res.columns
    assert "n" in res.columns
    assert len(res) == 3

    # Count grouped strictly by species (default)
    res_default = df.by("species").count()
    assert "species" in res_default.columns
    assert "island" not in res_default.columns
    assert len(res_default) == 2


def test_grouped_select_drops_group_key_returns_flat_dataframe():
    """Bug 4: Dropping grouping keys via select() must return a flat DataFrame instead of a corrupted GroupedDataFrame."""
    df = pt.DataFrame(
        {
            "species": ["Adelie", "Gentoo", "Adelie"],
            "val": [10, 20, 30],
        }
    )
    # Project away the grouping column 'species'
    projected = df.by("species").select("val")
    assert isinstance(projected, pt.DataFrame)
    assert not isinstance(projected, pt.dataframe.GroupedDataFrame)
    assert "species" not in projected.columns

    # Subsequent aggregation should work cleanly without ColumnNotFoundError
    agg_res = projected.agg("mean")
    assert "val" in agg_res.columns
    assert agg_res["val"][0] == 20.0


def test_cli_flags_single_hyphen_ready_and_verbose():
    """Bug 1: CLI parser registers single-hyphen flags -ready and -v / -verbose without double-dash aliases."""
    parser = build_parser()
    opt_strings = {opt for action in parser._actions for opt in action.option_strings}

    assert "-ready" in opt_strings
    assert "--ready" not in opt_strings

    assert "-v" in opt_strings
    assert "-verbose" in opt_strings
    assert "--verbose" not in opt_strings


def test_with_ties_mixed_directions_raises_value_error():
    """Bug 5: with_ties=True across multiple sort columns with opposite directions raises clean ValueError."""
    df = pt.DataFrame(
        {
            "cat": ["A", "A", "B", "B"],
            "score": [10, 20, 20, 10],
        }
    )
    with pytest.raises(ValueError, match="with_ties=True across multiple sort columns"):
        df.pt.arrange("cat asc, score desc").head(2, with_ties=True)


def test_plotter_show_non_interactive_no_warning():
    """Bug 6: Plotter.show() does not emit UserWarning on non-interactive backends."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pt.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    plotter = Plotter().data(df).plot(kind="line", x="x", y="y")

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        ret = plotter.show()

    assert ret is plotter
    plt.close("all")

    # Verify no UserWarning about FigureCanvasAgg being non-interactive
    interactive_warnings = [
        w for w in recorded if "non-interactive" in str(w.message).lower()
    ]
    assert not interactive_warnings, f"Unexpected non-interactive warning: {interactive_warnings}"


def test_repl_unregistered_bare_word_not_recognized():
    """Verify that typing an unregistered bare word in REPL is cleanly rejected without crashing on args.stats."""
    import polars as pl

    from pytae.repl import PytaeRepl

    r = PytaeRepl(df=pl.DataFrame({"a": [1, 2, 3]}))
    outs: list[str] = []
    r.execute_line("py k=df.to_pandas()", output_fn=outs.append)
    r.execute_line("k", output_fn=outs.append)
    r.close()

    assert any(
        "is not recognized as a command, table, or flag" in o for o in outs
    ), f"Expected clean rejection message, got: {outs}"


def test_repl_py_model_a_explicit_registration_and_cleanup():
    """Verify Ephemeral Python Sandboxing: only dataframes explicitly converted to Pytae DataFrame are registered; RAM is cleaned."""
    import polars as pl

    from pytae.repl import PytaeRepl

    r = PytaeRepl(df=pl.DataFrame({"x": [10, 20, 30], "y": ["a", "b", "c"]}))
    outs: list[str] = []

    # 1. Unconverted pandas dataframe: not registered, gone from RAM
    r.execute_line("py temp_pd = df.to_pandas()", output_fn=outs.append)
    assert "temp_pd" not in r.tables
    outs.clear()
    r.execute_line("py temp_pd", output_fn=outs.append)
    assert any("name 'temp_pd' is not defined" in o for o in outs)

    # 2. Converted using pt(k): registered into self.tables and accessible at REPL prompt
    outs.clear()
    r.execute_line("py k = pt(df.to_pandas())", output_fn=outs.append)
    assert "k" in r.tables
    assert any("Registered table 'k'" in o for o in outs)
    outs.clear()
    r.execute_line("k -cols", output_fn=outs.append)
    assert "x\ny" in outs[-1]

    # 3. Accessor proxy .pt is rejected from table registration with tip to use .to_pytae()
    outs.clear()
    r.execute_line("py m = df.to_pandas().pt", output_fn=outs.append)
    assert "m" not in r.tables
    assert any("accessor proxy" in o and "to_pytae()" in o for o in outs)

    # 4. Converted using .to_pytae() method: registered into self.tables
    outs.clear()
    r.execute_line("py p = df.to_pandas().to_pytae()", output_fn=outs.append)
    assert "p" in r.tables
    assert any("Registered table 'p'" in o for o in outs)

    # 5. Updating active df explicitly with .pt: updates active table
    outs.clear()
    r.execute_line("py df = df.filter('x > 10')", output_fn=outs.append)
    assert any("Updated active table 'df'" in o for o in outs)
    assert r.current_df.shape == (2, 2)

    r.close()


def test_repl_py_ram_cleanup_and_rss_release():
    """Verify that temporary large variables created in py mode are completely purged from RAM and scope."""
    import polars as pl

    from pytae.repl import PytaeRepl, _get_process_rss_mb, _release_memory

    r = PytaeRepl(df=pl.DataFrame({"x": [1, 2, 3]}))
    outs: list[str] = []

    # 1. RSS measurement helper returns a valid positive number
    rss_mb = _get_process_rss_mb()
    assert rss_mb is None or rss_mb > 0

    # 2. Allocate an ephemeral large object in py execution
    r.execute_line("py big_scratch = [i * 2 for i in range(500_000)]", output_fn=outs.append)

    # 3. Must not be registered as a table or variable
    assert "big_scratch" not in r.tables
    assert "big_scratch" not in r.variables

    # 4. On subsequent command, accessing it raises NameError confirming scope eviction
    outs.clear()
    r.execute_line("py big_scratch[0]", output_fn=outs.append)
    assert any("name 'big_scratch' is not defined" in o for o in outs)

    # 5. Calling _release_memory() executes without errors
    _release_memory()
    r.close()


def test_repl_ephemeral_ipc_checkpoint_and_switch():
    """Verify ephemeral Arrow IPC disk checkpoints (0 MB RAM) and switch/restore commands."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outs: list[str] = []

    r.execute_line("t1 = sample:penguins", output_fn=outs.append)
    r.execute_line("t2 = sample:tips", output_fn=outs.append)
    r.execute_line("val_limit = 50", output_fn=outs.append)

    # 1. Switch active dataset with 'switch'
    outs.clear()
    r.execute_line("switch t2", output_fn=outs.append)
    assert r.path_str == "t2"
    assert "Switched active dataset to 't2'" in outs[0]
    assert "deprecated" not in outs[0]

    # 2. Legacy 'use' works with deprecation notice
    outs.clear()
    r.execute_line("use t1", output_fn=outs.append)
    assert r.path_str == "t1"
    assert "Switched active dataset to 't1'" in outs[0]
    assert "'use' is deprecated" in outs[0]

    # 3. Save ephemeral IPC checkpoint
    outs.clear()
    r.execute_line("checkpoint v1", output_fn=outs.append)
    assert "Saved checkpoint 'v1'" in outs[0]
    assert "v1" in r.checkpoints

    # Verify temp dir and .ipc files on disk
    assert r._cp_dir is not None
    assert r._cp_dir.exists()
    ipc_files = list(r._cp_dir.glob("v1__*.ipc"))
    assert len(ipc_files) >= 2  # at least t1 and t2
    for f in ipc_files:
        assert f.stat().st_size > 0
    vars_file = r._cp_dir / "v1__vars.json"
    assert vars_file.exists()
    assert "val_limit" in vars_file.read_text(encoding="utf-8")

    # 4. Status checkpoint shows disk size and 0 MB RAM
    outs.clear()
    r.execute_line("status checkpoint", output_fn=outs.append)
    st = "\n".join(outs)
    assert "v1" in st
    assert "0 MB RAM" in st

    # 4b. Status session telemetry displays ephemeral disk and 0 MB RAM
    outs.clear()
    r.execute_line("status session", output_fn=outs.append)
    st_sess = "\n".join(outs)
    assert "Checkpoints   : 1 saved (latest: v1)" in st_sess
    assert "ephemeral disk, 0 MB RAM" in st_sess

    # 4c. Overwrite checkpoint reports "Updated" instead of "Saved"
    outs.clear()
    r.execute_line("checkpoint v1", output_fn=outs.append)
    assert "Updated checkpoint 'v1'" in outs[0]

    # 5. Mutate table
    r.execute_line('t1 = -mutate "extra_col = 12345"', output_fn=outs.append)
    assert "extra_col" in r.tables["t1"].columns

    # 5b. Milestone diffing compares active table against checkpoint version
    outs.clear()
    r.execute_line("-diff v1", output_fn=outs.append)
    diff_out = "\n".join(outs)
    assert "Comparing 't1' vs 'checkpoint:v1':" in diff_out
    assert "extra_col" in diff_out

    # 5c. Milestone diffing with explicit checkpoint table target
    outs.clear()
    r.execute_line("-diff v1:t1", output_fn=outs.append)
    diff_out2 = "\n".join(outs)
    assert "Comparing 't1' vs 'checkpoint:v1:t1':" in diff_out2

    # 6. Restore checkpoint reverts state
    outs.clear()
    r.execute_line("restore v1", output_fn=outs.append)
    assert "Restored checkpoint 'v1'" in outs[0]
    assert "extra_col" not in r.tables["t1"].columns

    # 7. Rollback works as deprecated alias
    outs.clear()
    r.execute_line('t1 = -mutate "temp_col = 999"', output_fn=outs.append)
    r.execute_line("rollback v1", output_fn=outs.append)
    assert any("'rollback' is deprecated" in o for o in outs)
    assert "extra_col" not in r.tables["t1"].columns
    assert "temp_col" not in r.tables["t1"].columns

    # 8. Bare restore restores latest checkpoint
    outs.clear()
    r.execute_line("restore", output_fn=outs.append)
    assert any("Restored checkpoint 'v1'" in o for o in outs)

    # 9. Clean exit purges ephemeral IPC temp dir completely
    cp_temp_path = r._cp_dir
    r.close()
    assert not cp_temp_path.exists()

    # 10. Interactive run() loop exit purges ephemeral IPC temp dir completely
    r2 = PytaeRepl()
    r2.execute_line("t = sample:tips")
    r2.execute_line("checkpoint snap")
    temp_dir2 = r2._cp_dir
    assert temp_dir2 is not None and temp_dir2.exists()

    inputs = iter(["exit"])
    r2.run(input_fn=lambda _: next(inputs), output_fn=lambda _: None)
    assert not temp_dir2.exists()


def test_repl_audit_ux_polish_improvements():
    """Verify the 4 UX polish enhancements:
    1. Bare variable evaluation without '@'.
    2. Bare 'status' displays session status directly; 'status session' emits deprecation note.
    3. Multi-table prompt marks active table with asterisk.
    4. Bare '-diff' auto-compares active table against latest milestone checkpoint.
    """
    outputs: list[str] = []
    r = PytaeRepl()

    # 1. Bare variable evaluation
    r.execute_line("min_spend = 50.0", output_fn=outputs.append)
    assert "Set @min_spend = 50.0" in outputs[-1]

    outputs.clear()
    r.execute_line("min_spend", output_fn=outputs.append)
    assert outputs[-1] == "50.0"

    # Nested config bare evaluation
    r.execute_line("cfg = {'mode': 'fast', 'limit': 100}", output_fn=outputs.append)
    outputs.clear()
    r.execute_line("cfg.mode", output_fn=outputs.append)
    assert outputs[-1] == "'fast'"

    # 2. Bare 'status' displays unified session status overview
    outputs.clear()
    r.execute_line("status", output_fn=outputs.append)
    st = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st
    assert "Active Table  : (none)" in st

    # 'status session' emits deprecation note
    outputs.clear()
    r.execute_line("status session", output_fn=outputs.append)
    st_sess = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st_sess
    assert "'status session' is deprecated" in st_sess

    # 3. Multi-table prompt marks active table with asterisk
    r.execute_line("t1 = sample:tips", output_fn=outputs.append)
    assert r._build_prompt() == "pytae [t1: 244x7]> "

    r.execute_line("t2 = sample:iris", output_fn=outputs.append)
    assert r._build_prompt() == "pytae [t1, t2*]> "

    r.execute_line("switch t1", output_fn=outputs.append)
    assert r._build_prompt() == "pytae [t1*, t2]> "

    # 4. Bare '-diff' auto-compares active table against latest milestone checkpoint
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    r.execute_line('t1 = -mutate "bonus = tip * 2"', output_fn=outputs.append)

    outputs.clear()
    r.execute_line("-diff", output_fn=outputs.append)
    diff_out = "\n".join(outputs)
    assert "Comparing 't1' vs 'checkpoint:v1':" in diff_out
    assert "bonus" in diff_out


def test_load_and_scan_deprecation(tmp_path):
    """Test deprecation notes for 'load' and 'scan' in favor of direct variable assignment."""
    csv_file = tmp_path / "customers.csv"
    csv_file.write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")

    r = PytaeRepl()
    outputs = []

    # 1. 'load <path> as <alias>' emits deprecation note
    r.execute_line(f"load {csv_file} as cust", output_fn=outputs.append)
    load_out = "\n".join(outputs)
    assert "Loaded customers.csv as 'cust'" in load_out
    assert "(Note: 'load' is deprecated; use '<alias> = <path>' instead.)" in load_out

    # 2. 'load <path>' emits deprecation note
    outputs.clear()
    r.execute_line(f"load {csv_file}", output_fn=outputs.append)
    load_bare = "\n".join(outputs)
    assert "(Note: 'load' is deprecated; use '<var> = <path>' instead.)" in load_bare

    # 3. Bare 'load' usage emits deprecation note
    outputs.clear()
    r.execute_line("load", output_fn=outputs.append)
    usage_out = "\n".join(outputs)
    assert "deprecated; use '<var> = <path>'" in usage_out

    # 4. 'scan <path> as <alias>' emits deprecation note
    outputs.clear()
    r.execute_line(f"scan {csv_file} as cust_lazy", output_fn=outputs.append)
    scan_out = "\n".join(outputs)
    assert "(Note: 'scan <path> as <alias>' is deprecated; use '<alias> = scan <path>' instead.)" in scan_out

    # 5. Preferred direct assignment '<alias> = <path> [options]' loads cleanly without deprecation note
    outputs.clear()
    r.execute_line(f'direct_cust = {csv_file} -dlim ","', output_fn=outputs.append)
    direct_out = "\n".join(outputs)
    assert "Loaded customers.csv as 'direct_cust'" in direct_out
    assert "deprecated" not in direct_out
    assert "direct_cust" in r.tables
    assert r.tables["direct_cust"].shape == (2, 2)


def test_syntax_deduplication_audit(tmp_path):
    """Test deprecations and deduplications for export, save, checkpoint rm, revert, cheatsheet, and colon removal."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    r = PytaeRepl()
    outputs = []

    # 1. export for data file emits deprecation note; -o is preferred
    r.execute_line(f"df = {csv_file}", output_fn=outputs.append)
    outputs.clear()
    out_pq = tmp_path / "out.parquet"
    r.execute_line(f"export {out_pq}", output_fn=outputs.append)
    export_out = "\n".join(outputs)
    assert "(Note: 'export <path>' for data is deprecated; use '-o " in export_out

    # 1b. export script works cleanly
    outputs.clear()
    script_out = tmp_path / "pipeline.pt"
    r.execute_line(f"export script {script_out}", output_fn=outputs.append)
    assert any("Exported Pytae script" in o for o in outputs)

    # 2. save script <path> emits deprecation note pointing to export script
    outputs.clear()
    script_py = tmp_path / "pipeline.py"
    r.execute_line(f"save script {script_py}", output_fn=outputs.append)
    save_script_out = "\n".join(outputs)
    assert "(Note: 'save script' is deprecated; use 'export script <path>' instead.)" in save_script_out

    # 2b. history -s emits deprecation note
    outputs.clear()
    r.execute_line("history -s", output_fn=outputs.append)
    hist_out = "\n".join(outputs)
    assert "'history -s' is not supported (deprecated)" in hist_out

    # 3. checkpoint rm emits deprecation note pointing to rm checkpoint
    r.execute_line("checkpoint cp1", output_fn=outputs.append)
    assert "cp1" in r.checkpoints
    outputs.clear()
    r.execute_line("checkpoint rm cp1", output_fn=outputs.append)
    cp_rm_out = "\n".join(outputs)
    assert "(Note: 'checkpoint rm' is deprecated; use 'rm checkpoint <name>' or 'rm checkpoint *' instead.)" in cp_rm_out
    assert "cp1" not in r.checkpoints

    # 4. revert emits deprecation note pointing to restore
    r.execute_line("checkpoint cp2", output_fn=outputs.append)
    r.execute_line('df = -mutate "c = a + 10"', output_fn=outputs.append)
    outputs.clear()
    r.execute_line("revert cp2", output_fn=outputs.append)
    revert_out = "\n".join(outputs)
    assert "(Note: 'revert' is deprecated; use 'restore [name]' instead.)" in revert_out

    # 4b. restore works cleanly without deprecation note
    outputs.clear()
    r.execute_line("restore cp2", output_fn=outputs.append)
    restore_out = "\n".join(outputs)
    assert "deprecated" not in restore_out

    # 5. -cheatsheet works cleanly, while legacy quick_start / cheatsheet emit deprecation notes
    outputs.clear()
    r.execute_line("-cheatsheet", output_fn=outputs.append)
    cs_out = "\n".join(outputs)
    assert "PYTAE CLI CHEAT SHEET" in cs_out
    assert "(Note: " not in cs_out

    outputs.clear()
    r.execute_line("cheatsheet", output_fn=outputs.append)
    cs_bare_out = "\n".join(outputs)
    assert "(Note: 'cheatsheet' is deprecated; use '-cheatsheet' instead.)" in cs_bare_out

    outputs.clear()
    r.execute_line("quick_start", output_fn=outputs.append)
    qs_out = "\n".join(outputs)
    assert "(Note: 'quick_start' is deprecated; use '-cheatsheet' instead.)" in qs_out


def test_cli_rejects_save_flag():
    """Verify that CLI explicitly rejects '-save' with guidance to '-export' and '-o'."""
    import io
    import sys

    from pytae.cli import main

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        ret = main(["-save", "something"])
        err_msg = sys.stderr.getvalue()
        assert ret == 1
        assert "'-save' is not a CLI option" in err_msg
    finally:
        sys.stderr = old_stderr






