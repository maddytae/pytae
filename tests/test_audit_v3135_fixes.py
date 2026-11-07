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
    """Verify Model A: only dataframes explicitly converted to Pytae DataFrame are registered; RAM is cleaned."""
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



