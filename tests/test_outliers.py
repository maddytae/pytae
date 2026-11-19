import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae.dataframe import DataFrame
from pytae.polars_engine import outliers_polars


def test_outliers_polars_iqr_basic():
    df = pl.DataFrame({
        "v": [10.0, 11.0, 12.0, 10.5, 11.5, 100.0, -50.0],
    })
    res = outliers_polars(df, ["v"], method="iqr", threshold=1.5)
    assert res.shape == (2, 1)
    vals = set(res["v"].to_list())
    assert vals == {100.0, -50.0}

    # Invert (drop=True) to retain inliers
    inliers = outliers_polars(df, ["v"], method="iqr", threshold=1.5, drop=True)
    assert inliers.shape == (5, 1)
    assert 100.0 not in inliers["v"].to_list()
    assert -50.0 not in inliers["v"].to_list()


def test_outliers_polars_zscore():
    df = pl.DataFrame({
        "v": [10.0] * 50 + [100.0],
    })
    # Outlier at 100.0 has large z-score
    res = outliers_polars(df, ["v"], method="zscore", threshold=3.0)
    assert res.shape == (1, 1)
    assert res["v"][0] == 100.0


def test_outliers_polars_mad():
    df = pl.DataFrame({
        "v": [10.0, 10.1, 9.9, 10.2, 10.0, 100.0],
    })
    res = outliers_polars(df, ["v"], method="mad", threshold=3.5)
    assert res.shape == (1, 1)
    assert res["v"][0] == 100.0


def test_outliers_polars_grouped():
    df = pl.DataFrame({
        "cat": ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"],
        "val": [1.0, 2.0, 1.5, 1.8, 100.0, 50.0, 52.0, 51.0, 49.0, 2.0],
    })
    # In group A: 100 is outlier; in group B: 2 is outlier
    res = outliers_polars(df, ["val"], method="iqr", by_cols=["cat"])
    assert res.shape == (2, 2)
    assert set(res["val"].to_list()) == {100.0, 2.0}


def test_outliers_polars_lazy():
    df = pl.DataFrame({
        "v": [10.0, 11.0, 12.0, 10.5, 11.5, 100.0],
    }).lazy()
    res = outliers_polars(df, ["v"])
    assert isinstance(res, pl.LazyFrame)
    collected = res.collect()
    assert collected.shape == (1, 1)
    assert collected["v"][0] == 100.0


def test_outliers_polars_auto_numeric_columns():
    df = pl.DataFrame({
        "name": ["a", "b", "c", "d", "e", "f", "g"],
        "score": [10.0, 11.0, 12.0, 10.5, 11.5, 100.0, 10.0],
    })
    # Auto-detects score as only numeric column
    res = outliers_polars(df)
    assert res.shape == (1, 2)
    assert res["name"][0] == "f"


def test_outliers_polars_multi_column_which():
    df = pl.DataFrame({
        "a": [1.0, 2.0, 1.5, 1.8, 100.0, 1.5],
        "b": [1.0, 2.0, 1.5, 1.8, 1.5, 200.0],
    })
    # which='any': row 4 (a=100) or row 5 (b=200)
    res_any = outliers_polars(df, ["a", "b"], which="any")
    assert res_any.shape == (2, 2)

    # which='all': neither row is outlier in both
    res_all = outliers_polars(df, ["a", "b"], which="all")
    assert res_all.shape == (0, 2)


def test_outliers_polars_edge_cases():
    # Constant column (std == 0)
    const_df = pl.DataFrame({"v": [5.0, 5.0, 5.0, 5.0, 5.0]})
    res_z = outliers_polars(const_df, ["v"], method="zscore")
    assert res_z.shape == (0, 1)
    res_mad = outliers_polars(const_df, ["v"], method="mad")
    assert res_mad.shape == (0, 1)

    # Empty frame
    empty_df = pl.DataFrame({"v": []}, schema={"v": pl.Float64})
    res_empty = outliers_polars(empty_df, ["v"])
    assert res_empty.shape == (0, 1)

    # Unknown column raises KeyError
    with pytest.raises(KeyError, match="unknown column"):
        outliers_polars(const_df, ["missing"])

    # Non-numeric column raises TypeError
    str_df = pl.DataFrame({"txt": ["x", "y", "z"]})
    with pytest.raises(TypeError, match="not numeric"):
        outliers_polars(str_df, ["txt"])

    # No numeric columns raises ValueError
    with pytest.raises(ValueError, match="no numeric columns"):
        outliers_polars(str_df)


def test_pytae_dataframe_outliers():
    pydf = DataFrame({
        "cat": ["X", "X", "X", "X", "X"],
        "val": [10.0, 11.0, 12.0, 10.5, 100.0],
    })
    # DataFrame.outliers()
    res = pydf.outliers("val")
    assert isinstance(res, DataFrame)
    assert len(res) == 1
    assert res["val"][0] == 100.0

    # Inverted drop=True
    inliers = pydf.outliers("val", drop=True)
    assert len(inliers) == 4

    # GroupedDataFrame.outliers()
    grouped = pydf.by("cat")
    res_grp = grouped.outliers("val")
    assert len(res_grp) == 1

    # Top-level pt.outliers()
    res_top = pt.outliers(pydf, "val")
    assert len(res_top) == 1

    # Pandas accessor
    pdf = pd.DataFrame({"val": [10.0, 11.0, 12.0, 10.5, 100.0]})
    res_acc = pdf.pt.outliers("val")
    assert len(res_acc) == 1


def test_cli_outliers_execution(tmp_path):
    fpath = tmp_path / "data.parquet"
    df = pl.DataFrame({
        "region": ["East", "East", "East", "East", "East", "West", "West", "West", "West", "West"],
        "sales": [10.0, 11.0, 12.0, 10.5, 100.0, 50.0, 52.0, 51.0, 49.0, 1.0],
    })
    df.write_parquet(fpath)

    from pytae.cli import main

    # Bare -outliers
    assert main([str(fpath), "-outliers"]) == 0

    # Keyed -outliers sales
    assert main([str(fpath), "-outliers", "sales"]) == 0

    # Grouped with -by region
    assert main([str(fpath), "-by", "region", "-outliers", "sales"]) == 0

    # Custom method
    assert main([str(fpath), "-outliers", "sales,method=zscore,thresh=2.0"]) == 0

    # Invert / drop
    assert main([str(fpath), "-outliers", "sales,drop=true"]) == 0


def test_cli_outlier_rejection(tmp_path):
    fpath = tmp_path / "data.parquet"
    df = pl.DataFrame({"v": [1, 2, 3]})
    df.write_parquet(fpath)

    from pytae.cli import main

    with pytest.raises(SystemExit):
        main([str(fpath), "-outlier"])

    with pytest.raises(SystemExit):
        main([str(fpath), "--outlier"])






