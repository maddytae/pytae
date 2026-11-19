import pytest
import polars as pl
import pandas as pd
import pytae as pt
from pytae.dataframe import DataFrame
from pytae.polars_engine import dups_polars


def test_dups_polars_all_columns():
    df = pl.DataFrame({
        "a": [1, 2, 1, 3, 2, 4],
        "b": ["x", "y", "x", "z", "y", "w"],
    })
    res = dups_polars(df)
    assert res.shape == (4, 2)
    # Rows for (1, x) and (2, y) are duplicates and sorted by (a, b)
    assert res.to_dicts() == [
        {"a": 1, "b": "x"},
        {"a": 1, "b": "x"},
        {"a": 2, "b": "y"},
        {"a": 2, "b": "y"},
    ]


def test_dups_polars_subset_columns():
    df = pl.DataFrame({
        "cust_id": [101, 102, 101, 103, 102],
        "order_val": [50, 60, 70, 80, 90],
    })
    res = dups_polars(df, ["cust_id"])
    assert res.shape == (4, 2)
    assert res["cust_id"].to_list() == [101, 101, 102, 102]
    assert res["order_val"].to_list() == [50, 70, 60, 90]


def test_dups_polars_no_duplicates():
    df = pl.DataFrame({
        "a": [1, 2, 3],
        "b": ["x", "y", "z"],
    })
    res = dups_polars(df)
    assert res.shape == (0, 2)
    assert res.columns == ["a", "b"]


def test_dups_polars_empty():
    df = pl.DataFrame({"a": [], "b": []}, schema={"a": pl.Int64, "b": pl.String})
    res = dups_polars(df)
    assert res.shape == (0, 2)


def test_dups_polars_unknown_column():
    df = pl.DataFrame({"a": [1, 2]})
    with pytest.raises(KeyError, match="unknown column"):
        dups_polars(df, ["nonexistent"])


def test_dups_polars_lazy():
    df = pl.DataFrame({
        "a": [1, 2, 1, 3],
        "b": ["x", "y", "x", "z"],
    }).lazy()
    res = dups_polars(df)
    assert isinstance(res, pl.LazyFrame)
    collected = res.collect()
    assert collected.shape == (2, 2)
    assert collected["a"].to_list() == [1, 1]


def test_pytae_dataframe_dups():
    pydf = DataFrame({
        "a": [1, 2, 1, 3, 2],
        "b": ["m", "n", "m", "o", "p"],
    })
    # bare dups
    bare = pydf.dups()
    assert isinstance(bare, DataFrame)
    assert len(bare) == 2
    assert bare.to_dict(as_series=False) == {"a": [1, 1], "b": ["m", "m"]}

    # subset dups
    sub = pydf.dups("a")
    assert len(sub) == 4
    assert sub["a"].to_list() == [1, 1, 2, 2]

    # top level function
    top = pt.dups(pydf, "a")
    assert len(top) == 4

    # pandas accessor
    pdf = pd.DataFrame({"a": [1, 2, 1, 3], "b": ["x", "y", "x", "z"]})
    acc = pdf.pt.dups()
    assert isinstance(acc, DataFrame)
    assert len(acc) == 2


def test_pytae_dataframe_dups_errors():
    pydf = DataFrame({"a": [1, 2]})
    with pytest.raises(TypeError, match="takes column names as positional arguments"):
        pydf.dups(["a"])

    with pytest.raises(KeyError, match="not found in DataFrame"):
        pydf.dups("missing_col")


def test_cli_dups_execution(tmp_path):
    fpath = tmp_path / "test.parquet"
    df = pl.DataFrame({
        "k": [1, 2, 1, 3, 2],
        "v": ["a", "b", "a", "c", "d"],
    })
    df.write_parquet(fpath)

    from pytae.cli import main

    # Bare -dups
    rc = main([str(fpath), "-dups"])
    assert rc == 0

    # Subset -dups
    rc2 = main([str(fpath), "-dups", "k"])
    assert rc2 == 0


def test_cli_dup_rejection_error(tmp_path):
    fpath = tmp_path / "test.parquet"
    df = pl.DataFrame({"a": [1, 2]})
    df.write_parquet(fpath)

    from pytae.cli import main

    with pytest.raises(SystemExit):
        main([str(fpath), "-dup"])

    with pytest.raises(SystemExit):
        main([str(fpath), "--dup"])








