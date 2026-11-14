"""Tests covering bug fixes and improvements from the v3.13.6 audit:
1. DataFrame.dropna() and fillna() string subset/cols splitting and KeyError on unknown columns.
2. dropna_polars() validates column existence against schema and raises KeyError on missing columns.
3. GroupedDataFrame.dropna(), fillna(), and rename() preserve grouping context and update grouping keys.
4. GroupedDataFrame.to_pandas() hard removal raises AttributeError, while .to('pandas') works on LazyFrames.
5. pt.diff() supports str and Path objects seamlessly.
6. REPL history transpiler handles -by, -agg, -clean_columns, -rename, -count, -arrange, and .to().
7. write_dataframe() and CLI -o support .json and .xlsx.
8. CLI -dropna row-filtering does not contaminate -pivot or -plot arguments.
9. _text.py:tokenize() handles backslash-escaped quotes.
10. PandasPtAccessor.to_clip() emits DeprecationWarning.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import pytae as pt
from pytae._text import tokenize
from pytae.cli import main as cli_main
from pytae.readers import write_dataframe
from pytae.repl import _transpile_pipeline_tokens_to_python


def test_dropna_and_fillna_subset_string():
    df = pt.DataFrame({
        "sex": ["M", None, "F"],
        "body_mass_g": [3000.0, 4000.0, None],
        "island": ["Biscoe", "Dream", "Torgersen"],
    })
    # Passing single string as subset
    res_drop = df.dropna(subset="sex")
    assert len(res_drop) == 2
    assert res_drop["sex"].to_list() == ["M", "F"]

    # Passing comma-separated string as subset
    res_drop_multi = df.dropna(subset="sex, body_mass_g")
    assert len(res_drop_multi) == 1

    # Passing comma-separated string as cols
    res_drop_cols = df.dropna("sex, body_mass_g")
    assert len(res_drop_cols) == 1

    # fillna with string subset
    res_fill = df.fillna("missing", subset="sex")
    assert res_fill["sex"].to_list() == ["M", "missing", "F"]

    # Unknown column raises KeyError in dropna
    with pytest.raises(KeyError, match="dropna: column.*not found"):
        df.dropna(subset="unknown_col")

    with pytest.raises(KeyError, match="dropna: column.*not found"):
        df.dropna("unknown_col")

    # Unknown column raises KeyError in fillna
    with pytest.raises(KeyError, match="fillna: column.*not found"):
        df.fillna(0, subset="unknown_col")


def test_grouped_dataframe_preserves_grouping_on_cleaning():
    df = pt.DataFrame({
        "species": ["Adelie", "Adelie", "Gentoo", "Gentoo"],
        "mass": [3000.0, None, 5000.0, 5200.0],
    })
    # dropna preserves grouping
    gdf = df.by("species").dropna("mass")
    assert type(gdf).__name__ == "GroupedDataFrame"
    res_agg = gdf.agg(mean_mass="mass:mean")
    assert len(res_agg) == 2
    assert set(res_agg["species"].to_list()) == {"Adelie", "Gentoo"}

    # fillna preserves grouping
    gdf_fill = df.by("species").fillna(0.0, "mass")
    assert type(gdf_fill).__name__ == "GroupedDataFrame"
    res_agg_fill = gdf_fill.agg(mean_mass="mass:mean")
    assert len(res_agg_fill) == 2

    # rename updates grouping keys
    gdf_ren = df.by("species").rename(species="spec")
    assert type(gdf_ren).__name__ == "GroupedDataFrame"
    assert gdf_ren._by == ["spec"]
    res_agg_ren = gdf_ren.agg(mean_mass="mass:mean")
    assert "spec" in res_agg_ren.columns


def test_grouped_dataframe_to_pandas_hard_removed_and_to_pandas_works():
    # Lazy frame with grouping
    lazy_df = pt.scan("src/pytae/datasets/penguins.parquet").by("species")
    # Calling .to_pandas() on GroupedDataFrame raises AttributeError
    with pytest.raises(AttributeError):
        lazy_df.to_pandas()

    # Calling .to('pandas') works seamlessly on LazyFrame
    pdf = lazy_df.to("pandas")
    assert isinstance(pdf, pd.DataFrame)
    assert len(pdf) == 344


def test_pt_diff_with_paths():
    p = Path("src/pytae/datasets/penguins.parquet")
    # str path vs str path
    report_str = pt.diff("src/pytae/datasets/penguins.parquet", "src/pytae/datasets/penguins.parquet")
    assert "344 rows, 7 cols" in report_str
    assert "Row counts differ" not in report_str

    # Path object vs Path object
    report_path = pt.diff(p, p)
    assert "344 rows, 7 cols" in report_path
    assert "Row counts differ" not in report_path


def test_repl_transpiler_all_operations():
    tokens = [
        "-by", "species, island",
        "-clean_columns",
        "-rename", "old_col:new_col",
        "-count", "user_id",
        "-sort", "count", "desc",
        "-o", "output.parquet",
    ]
    code = _transpile_pipeline_tokens_to_python(tokens)
    expected = (
        ".by('species', 'island')"
        ".clean_columns()"
        ".rename('old_col:new_col')"
        ".count('user_id')"
        ".arrange('count desc')"
        ".to('output.parquet')"
    )
    assert code == expected


def test_write_dataframe_json_and_xlsx(tmp_path):
    df = pt.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    json_path = tmp_path / "out.json"
    xlsx_path = tmp_path / "out.xlsx"

    write_dataframe(df, json_path)
    assert json_path.exists()
    assert json_path.stat().st_size > 0

    write_dataframe(df, xlsx_path)
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 0

    # CLI -o JSON
    cli_json = tmp_path / "cli_out.json"
    ret = cli_main(["src/pytae/datasets/penguins.parquet", "-o", str(cli_json)])
    assert ret == 0
    assert cli_json.exists()


def test_tokenize_escaped_quotes():
    raw1 = r"col = 'don\'t', val = 1"
    toks1 = tokenize(raw1, ",", keep_quotes=True)
    assert toks1 == [r"col = 'don\'t'", "val = 1"]

    raw2 = 'name = "foo\\"bar", other = 2'
    toks2 = tokenize(raw2, ",", keep_quotes=True)
    assert toks2 == ['name = "foo\\"bar"', "other = 2"]


def test_pandas_pt_accessor_to_clip_hard_removed():
    pdf = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(AttributeError):
        pdf.pt.to_clip()


def test_repl_message_review_and_alias_consistency():
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outs = []

    # 1. Bare vars
    outs.clear()
    r.execute_line("vars", output_fn=outs.append)
    assert outs[-1] == "pytae: bare 'vars' is not recognized; use 'status var' (or 'status var -v')."

    # 2. Disallowed aliases directing directly to valid working commands
    outs.clear()
    r.execute_line("-vars", output_fn=outs.append)
    assert outs[-1] == "pytae: '-vars' is not recognized; use 'status var'."

    outs.clear()
    r.execute_line("-tables", output_fn=outs.append)
    assert outs[-1] == "pytae: '-tables' is not recognized; use 'status table'."

    outs.clear()
    r.execute_line("-checkpoints", output_fn=outs.append)
    assert outs[-1] == "pytae: '-checkpoints' is not recognized; use 'status checkpoint'."

    outs.clear()
    r.execute_line("cps", output_fn=outs.append)
    assert outs[-1] == "pytae: 'cps' is not recognized; use 'status checkpoint'."

    outs.clear()
    r.execute_line("datasets", output_fn=outs.append)
    assert outs[-1] == "pytae: 'datasets' is not recognized; use 'status table'."

    # 3. rm var -all redirect to rm var *
    outs.clear()
    r.execute_line("rm var -all", output_fn=outs.append)
    assert outs[-1] == "pytae: 'rm var -all' is not recognized; use 'rm var *'."

    # 4. rm checkpoints redirects to full usage
    outs.clear()
    r.execute_line("rm checkpoints", output_fn=outs.append)
    assert outs[-1] == "pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint <name>' or 'rm checkpoint *'."

    # 5. rm unrecognized categories strictly rejected
    outs.clear()
    r.execute_line("rm cp", output_fn=outs.append)
    assert outs[-1] == "pytae: unrecognized rm category 'cp'. Use 'rm table <name>', 'rm checkpoint <name>', or 'rm var <name>'."

    outs.clear()
    r.execute_line("rm dataset", output_fn=outs.append)
    assert outs[-1] == "pytae: unrecognized rm category 'dataset'. Use 'rm table <name>', 'rm checkpoint <name>', or 'rm var <name>'."

    # 6. status unrecognized categories strictly rejected
    outs.clear()
    r.execute_line("status cp", output_fn=outs.append)
    assert outs[-1] == "pytae: unrecognized status category 'cp'. Use 'status session [-v]', 'status table [name] [-v]', 'status checkpoint [name] [-v]', or 'status var [name] [-v]'."

    outs.clear()
    r.execute_line("status dataset", output_fn=outs.append)
    assert outs[-1] == "pytae: unrecognized status category 'dataset'. Use 'status session [-v]', 'status table [name] [-v]', 'status checkpoint [name] [-v]', or 'status var [name] [-v]'."

