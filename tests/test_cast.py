import polars as pl
import pytest

import pytae as pt
from pytae.dataframe import DataFrame


def test_dataframe_cast_kwargs():
    df = DataFrame({"a": [1.0, 2.0, 3.0], "b": ["10", "20", "30"]})
    res = df.cast(a=int, b=int)
    assert res.schema["a"] == pl.Int64
    assert res.schema["b"] == pl.Int64
    assert res["a"].to_list() == [1, 2, 3]
    assert res["b"].to_list() == [10, 20, 30]


def test_dataframe_cast_dict():
    df = DataFrame({"a": [1.0, 2.0], "b": ["10", "20"]})
    res = df.cast({"a": "int32", "b": float})
    assert res.schema["a"] == pl.Int32
    assert res.schema["b"] == pl.Float64
    assert res["a"].to_list() == [1, 2]
    assert res["b"].to_list() == [10.0, 20.0]


def test_dataframe_cast_str_spec():
    df = DataFrame({"x": ["1", "2"], "y": [3.14, 2.71]})
    res = df.cast("x:int, y:int")
    assert res.schema["x"] == pl.Int64
    assert res.schema["y"] == pl.Int64
    assert res["x"].to_list() == [1, 2]
    assert res["y"].to_list() == [3, 2]

    # Test equals syntax
    res2 = df.cast("x=int, y=str")
    assert res2.schema["x"] == pl.Int64
    assert res2.schema["y"] == pl.String


def test_functional_and_accessor_cast():
    df = DataFrame({"a": [1.0, 2.0]})
    # Functional pt.cast()
    res1 = pt.cast(df, a=int)
    assert res1.schema["a"] == pl.Int64

    # Polars accessor df.pt.cast()
    pl_df = pl.DataFrame({"a": [1.0, 2.0]})
    res2 = pl_df.pt.cast(a=int)
    assert res2.schema["a"] == pl.Int64

    # Pandas accessor df.pt.cast()
    pd_df = pl_df.to_pandas()
    res3 = pd_df.pt.cast(a=int)
    assert res3.schema["a"] == pl.Int64


def test_grouped_dataframe_cast():
    df = DataFrame({"grp": ["x", "x", "y"], "val": [1.5, 2.5, 3.5]})
    res = df.by("grp").cast(val=int)
    assert res.schema["val"] == pl.Int64
    assert res["val"].to_list() == [1, 2, 3]


def test_mutate_inline_cast_python_types():
    df = DataFrame({
        "s_num": ["10", "20", "30"],
        "f_num": [1.9, 2.1, 3.8],
        "i_num": [0, 1, 0],
    })

    # int(x), float(x), str(x), bool(x)
    res = df.mutate(
        i_from_s="int(s_num)",
        i_from_f="int(f_num)",
        f_from_s="float(s_num)",
        s_from_f="str(f_num)",
        b_from_i="bool(i_num)",
    )
    assert res.schema["i_from_s"] == pl.Int64
    assert res.schema["i_from_f"] == pl.Int64
    assert res.schema["f_from_s"] == pl.Float64
    assert res.schema["s_from_f"] == pl.String
    assert res.schema["b_from_i"] == pl.Boolean

    assert res["i_from_s"].to_list() == [10, 20, 30]
    assert res["i_from_f"].to_list() == [1, 2, 3]
    assert res["f_from_s"].to_list() == [10.0, 20.0, 30.0]
    assert res["b_from_i"].to_list() == [False, True, False]


def test_mutate_inline_cast_method_and_function():
    df = DataFrame({"val": ["100", "200"]})
    res = df.mutate(
        m_cast="val.cast('int')",
        f_cast="cast(val, 'int')",
        i32_cast="int32(val)",
        f32_cast="float32(val)",
    )
    assert res.schema["m_cast"] == pl.Int64
    assert res.schema["f_cast"] == pl.Int64
    assert res.schema["i32_cast"] == pl.Int32
    assert res.schema["f32_cast"] == pl.Float32
    assert res["m_cast"].to_list() == [100, 200]
    assert res["f_cast"].to_list() == [100, 200]


def test_mutate_multi_column_cast():
    df = DataFrame({"a": ["1", "2"], "b": ["3", "4"]})
    res = df.mutate("(a, b) = int(_)")
    assert res.schema["a"] == pl.Int64
    assert res.schema["b"] == pl.Int64
    assert res["a"].to_list() == [1, 2]
    assert res["b"].to_list() == [3, 4]


def test_cast_errors():
    df = DataFrame({"a": [1, 2]})
    with pytest.raises(KeyError, match="column 'nonexistent' not found"):
        df.cast(nonexistent=int)

    with pytest.raises(ValueError, match="Unsupported dtype"):
        df.cast(a="invalid_type_xyz")

    with pytest.raises(ValueError, match="invalid spec"):
        df.cast("a:int, invalid_token")


def test_cli_cast(tmp_path):
    from pytae.cli import main

    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1.0,10\n2.0,20\n", encoding="utf-8")

    out_file = tmp_path / "out.csv"
    # Run pytae data.csv -cast "a:int, b:int" -o out.csv
    exit_code = main([str(csv_file), "-cast", "a:int, b:int", "-o", str(out_file)])
    assert exit_code == 0

    read_back = pt.read_csv(out_file)
    assert read_back.schema["a"] == pl.Int64
    assert read_back.schema["b"] == pl.Int64
    assert read_back["a"].to_list() == [1, 2]
    assert read_back["b"].to_list() == [10, 20]
