import polars as pl
import pytest

import pytae as pt
from pytae import cli
from pytae.validation import (
    PipelineValidationError,
    check_dsl_file,
    check_dsl_paths,
    check_dsl_string,
    validate_pipeline,
)


def test_validate_pipeline_dict_schema():
    schema = {"weight": float, "height": float, "species": str}

    def pipeline(df):
        return df.filter("species == 'Adelie'").mutate("bmi = weight / (height ** 2)").select("species", "bmi")

    res = validate_pipeline(pipeline, schema)
    assert res.columns == ["species", "bmi"]
    assert res.shape == (0, 2)


def test_validate_pipeline_polars_schema():
    schema = pl.Schema({"a": pl.Int64, "b": pl.Float64})

    def pipeline(df):
        return df.mutate("c = a + b").select("c")

    res = validate_pipeline(pipeline, schema)
    assert res.columns == ["c"]
    assert res.shape == (0, 1)


def test_validate_pipeline_parquet_source(tmp_path):
    parquet_path = tmp_path / "sample.parquet"
    pl.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]}).write_parquet(parquet_path)

    def pipeline(df):
        return df.mutate("z = x * y").filter("z > 0")

    res = validate_pipeline(pipeline, parquet_path)
    assert res.columns == ["x", "y", "z"]


def test_validate_pipeline_dataframe_source():
    df = pt.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})

    def pipeline(d):
        return d.mutate("is_adult = age >= 18")

    res = validate_pipeline(pipeline, df)
    assert "is_adult" in res.columns


def test_validate_pipeline_catches_column_typo():
    schema = {"weight": float, "height": float}

    def bad_pipeline(df):
        return df.mutate("bmi = weigt / (height ** 2)")

    with pytest.raises(PipelineValidationError, match=r"column 'weigt' not found"):
        validate_pipeline(bad_pipeline, schema)


def test_validate_pipeline_catches_syntax_error():
    schema = {"weight": float, "height": float}

    def bad_syntax(df):
        return df.mutate("bmi = weight / (height ** 2")

    with pytest.raises(PipelineValidationError, match=r"was never closed"):
        validate_pipeline(bad_syntax, schema)


def test_check_dsl_string_mutate():
    # Valid
    assert check_dsl_string("mutate", "bmi = weight / (height ** 2)") == []
    assert check_dsl_string("mutate", "status = case_when((score > 700, 'A'), default='B')") == []
    assert check_dsl_string("mutate", "flag = if_else(score > 700, 1, 0)") == []

    # Invalid syntax
    errs = check_dsl_string("mutate", "bmi = weight / (height ** 2")
    assert len(errs) > 0
    assert "never closed" in errs[0]

    # Invalid if_else
    errs = check_dsl_string("mutate", "flag = if_else(score > 700, 1)")
    assert any("takes exactly 3 arguments" in e for e in errs)


def test_check_dsl_string_select():
    # Valid
    assert check_dsl_string("select", "!col1, !col2") == []
    assert check_dsl_string("select", "dtype=numeric") == []

    # Retired exclude=
    errs = check_dsl_string("select", "exclude=col1")
    assert any("retired in favor of '!' negation" in e for e in errs)

    # Unknown criteria
    errs = check_dsl_string("select", "foo=bar")
    assert any("unrecognized select criteria" in e for e in errs)


def test_check_dsl_string_arrange():
    # Valid
    assert check_dsl_string("arrange", "a desc, b asc") == []

    # Invalid direction
    errs = check_dsl_string("arrange", "a descc")
    assert any("invalid sort direction" in e for e in errs)


def test_check_dsl_string_agg():
    # Valid
    assert check_dsl_string("agg", "total = count, avg_x = x:mean") == []

    # Legacy n = n
    errs = check_dsl_string("agg", "n = n")
    assert any("use 'count' instead" in e for e in errs)


def test_check_dsl_file_and_paths(tmp_path):
    good_file = tmp_path / "pipeline.py"
    good_file.write_text(
        """
import pytae as pt

def run():
    df = pt.scan_parquet('data.parquet')
    return df.filter('age >= 18').mutate('is_adult = 1').select('!species')
"""
    )

    bad_file = tmp_path / "bad.py"
    bad_file.write_text(
        """
import pytae as pt

def run():
    df = pt.scan_parquet('data.parquet')
    return df.mutate('x = a + (').select(exclude='col')
"""
    )

    good_diags = check_dsl_file(good_file)
    assert len(good_diags) == 0

    bad_diags = check_dsl_file(bad_file)
    assert len(bad_diags) == 2
    assert any("never closed" in d.message for d in bad_diags)
    assert any("retired in favor of '!'" in d.message for d in bad_diags)

    num_files, all_diags = check_dsl_paths([tmp_path])
    assert num_files == 2
    assert len(all_diags) == 2


def test_cli_check_command(tmp_path, capsys):
    test_file = tmp_path / "script.py"
    test_file.write_text(
        """
import pytae as pt
df = pt.scan_parquet('test.parquet')
df = df.mutate('val = x + 1')
"""
    )

    exit_code = cli.main(["check", str(test_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "passed validation" in out

    # Test file with error
    bad_file = tmp_path / "bad_script.py"
    bad_file.write_text(
        """
import pytae as pt
df = pt.scan_parquet('test.parquet')
df = df.select(exclude='val')
"""
    )

    exit_code = cli.main(["check", str(bad_file)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Found 1 DSL syntax error" in out


def test_validate_pipeline_txt_and_feather_sources(tmp_path):
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("x\ty\n1.0\t3.0\n2.0\t4.0\n")

    feather_path = tmp_path / "sample.feather"
    pl.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]}).write_ipc(feather_path)

    def pipeline(df):
        return df.mutate("z = x + y").select("x", "z")

    res_txt = validate_pipeline(pipeline, txt_path)
    assert res_txt.columns == ["x", "z"]

    res_feather = validate_pipeline(pipeline, feather_path)
    assert res_feather.columns == ["x", "z"]
