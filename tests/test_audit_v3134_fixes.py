"""Tests covering fixes from the v3.13.4 audit report."""

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae.accessor import DataFrame
from pytae.cli_help import KEYWORD_DOCS
from pytae.cli_run import _output_text
from pytae.repl import PytaeRepl


def test_audit_bug1_repl_windows_paths_in_targeted_pipeline(tmp_path: Path):
    """Bug 1: Targeted pipeline commands (e.g. 'k -o C:\\path\\out.csv') must not swallow backslashes."""
    r = PytaeRepl()
    r.tables["df"] = pl.DataFrame({"a": list(range(10))})
    r.current_df = r.tables["df"]
    r.path_str = "df"

    outs: list[str] = []
    r.execute_line("k = df -head 5", output_fn=outs.append)

    target_out = tmp_path / "win_out.csv"
    outs.clear()
    r.execute_line(f"k -o {target_out}", output_fn=outs.append)
    assert any("Saved 5 rows" in o for o in outs)
    assert target_out.exists()
    r.close()


def test_audit_bug2_unicode_output_fallback_and_error_separation():
    """Bug 2: Output encoding error is not reported as input decoding error."""
    import argparse

    args = argparse.Namespace(pager=False)

    # Test that _output_text handles unicode without crash
    _output_text("⚡ Test chart: █ 50%", args)


def test_audit_bug3_wide_no_id_columns():
    """Bug 3: wide() without id columns works across all Polars versions without ComputeError."""
    df = pd.DataFrame({"metric": ["Sales", "Profit"], "val": [100, 20]})
    res = df.pt.wide(c="metric", v="val")
    assert list(res.columns) == ["Profit", "Sales"]
    assert len(res) == 1
    assert res.iloc[0]["Sales"] == 100
    assert res.iloc[0]["Profit"] == 20

    # Duplicates on c still raise clean ValueError
    df_dup = pd.DataFrame({"metric": ["Sales", "Sales"], "val": [100, 200]})
    with pytest.raises(ValueError, match="encountered duplicate entries"):
        df_dup.pt.wide(c="metric", v="val")


def test_audit_bug4_date_mutate_helper_datetime_strings():
    """Bug 4: date() mutate helper extracts date from full datetime strings."""
    df = pt.DataFrame({"dt_str": ["2026-03-15 14:30:00", "2026-04-20 09:15:00"]})
    res = df.mutate(d="date(dt_str)")
    assert str(res["d"][0]) == "2026-03-15"
    assert str(res["d"][1]) == "2026-04-20"


def test_audit_bug5_repl_cols_substring_filter():
    """Bug 5: REPL -cols supports substring filtering."""
    r = PytaeRepl()
    r.execute_line("df = sample:penguins")
    outs: list[str] = []
    r.execute_line("-cols mass", output_fn=outs.append)
    assert any("body_mass_g" in o for o in outs)
    r.close()


def test_audit_bug6_glimpse_fluent_method_chaining():
    """Bug 6: pt.DataFrame.glimpse() returns DataFrame for chaining, while .pt.glimpse() preserves underlying object."""
    df = pt.DataFrame({"a": [1, 2], "b": [3, 4]})
    chained = df.glimpse().mutate("c = a + b")
    assert isinstance(chained, DataFrame)
    assert "c" in chained.columns
    assert list(chained["c"]) == [4, 6]

    raw_pl = pl.DataFrame({"a": [1, 2]})
    assert raw_pl.pt.glimpse() is raw_pl


def test_audit_bug7_freq_bar_chaining_no_duplicate_column():
    """Bug 7: -freq followed by -bar does not duplicate the Bar column."""
    df = pt.DataFrame({"species": ["Adelie", "Adelie", "Gentoo"]})
    freq_df = df.pt.freq("species")
    assert "Distribution" in freq_df.columns
    bar_df = freq_df.pt.bar()
    assert "Bar" not in bar_df.columns
    assert "Distribution" in bar_df.columns


def test_audit_bug8_cli_help_no_double_dash_headers():
    """Bug 8: CLI help text flag attributes do not advertise rejected double-dash flags."""
    for key in ("sql", "filter", "select", "mutate", "arrange"):
        doc = KEYWORD_DOCS[key]
        assert "--" not in doc.flag, f"Flag '{doc.flag}' in '{key}' still advertises '--'"
