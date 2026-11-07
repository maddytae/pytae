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

