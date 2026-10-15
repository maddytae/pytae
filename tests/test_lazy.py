import os
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text(
        "id,group,score,comment\n"
        "1,alpha,10.5,good\n"
        "2,beta,20.0,better\n"
        "3,alpha,15.5,best\n"
        "4,beta,30.0,great\n"
        "5,alpha,,missing\n",
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def sample_parquet(tmp_path: Path) -> Path:
    pq_file = tmp_path / "sample.parquet"
    df = pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "category": ["A", "B", "A", "B", "C"],
            "val1": [10, 20, 30, 40, 50],
            "val2": [100.0, 200.0, 300.0, 400.0, 500.0],
        }
    )
    df.write_parquet(pq_file)
    return pq_file


def test_scan_csv(sample_csv: Path):
    df = pt.scan(sample_csv)
    assert df.is_lazy
    assert "id" in df.columns
    assert "score" in df.columns
    assert df.shape == (5, 4)

    # Chaining preserves laziness
    filtered = df.filter("score > 12")
    assert filtered.is_lazy

    mutated = filtered.mutate(doubled="score * 2")
    assert mutated.is_lazy

    arranged = mutated.arrange("-doubled")
    assert arranged.is_lazy

    selected = arranged.select("id", "group", "doubled")
    assert selected.is_lazy

    # Materialize
    collected = selected.collect()
    assert not collected.is_lazy
    assert list(collected.columns) == ["id", "group", "doubled"]
    assert len(collected) == 3
    assert collected["doubled"].to_list() == [60.0, 40.0, 31.0]


def test_scan_parquet(sample_parquet: Path):
    df = pt.scan(sample_parquet)
    assert df.is_lazy
    assert df.columns == ["id", "category", "val1", "val2"]
    assert df.shape == (5, 4)
    assert len(df) == 5

    res = (
        df.filter("category in ['A', 'B']")
        .mutate(total="val1 + val2")
        .arrange("total desc")
        .select("id", "total")
        .collect()
    )
    assert not res.is_lazy
    assert len(res) == 4
    assert res["total"].to_list() == [440.0, 330.0, 220.0, 110.0]


def test_lazy_explain(sample_parquet: Path):
    df = pt.scan(sample_parquet).filter("val1 > 20").select("id", "category")
    assert df.is_lazy
    explanation = df.explain()
    assert isinstance(explanation, str)
    assert "FILTER" in explanation or "SELECT" in explanation or "val1" in explanation


def test_lazy_conversion():
    eager_df = pt.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    assert not eager_df.is_lazy

    lazy_df = eager_df.lazy()
    assert lazy_df.is_lazy

    # Collecting returns eager pt.DataFrame
    back = lazy_df.collect()
    assert not back.is_lazy
    assert back["x"].to_list() == [1, 2, 3]


def test_lazy_verbs(sample_parquet: Path):
    df = pt.scan(sample_parquet)

    # distinct
    d = df.distinct("category")
    assert d.is_lazy
    assert len(d.collect()) == 3

    # dropna
    dn = df.dropna("val1")
    assert dn.is_lazy
    assert len(dn.collect()) == 5

    # pick
    p = df.pick("val1", n=2, order="max")
    assert p.is_lazy
    assert len(p.collect()) == 2
    assert p.collect()["val1"].to_list() == [50, 40]

    # replace_values
    rv = df.replace_values({"A": "ALPHA"}, c="category")
    assert rv.is_lazy
    cats = rv.collect()["category"].to_list()
    assert "ALPHA" in cats
    assert "A" not in cats

    # clean_columns
    cc = df.clean_columns(case="upper")
    assert cc.is_lazy
    assert "CATEGORY" in cc.collect().columns


def test_lazy_grouped_operations(sample_parquet: Path):
    df = pt.scan(sample_parquet)

    # Grouped mutate on LazyFrame
    g_mut = df.by("category").mutate(mean_val1="mean(val1)")
    assert g_mut.is_lazy
    collected_mut = g_mut.collect()
    assert "mean_val1" in collected_mut.columns

    # Grouped agg on LazyFrame
    g_agg = df.by("category").agg(sum_val1="val1:sum", mean_val2="val2:mean")
    assert g_agg.is_lazy
    collected_agg = g_agg.collect()
    assert "sum_val1" in collected_agg.columns
    assert "mean_val2" in collected_agg.columns
    assert len(collected_agg) == 3


def test_lazy_sinking(tmp_path: Path, sample_parquet: Path):
    df = pt.scan(sample_parquet).filter("val1 >= 30")
    assert df.is_lazy

    out_pq = tmp_path / "output.parquet"
    df.to_parquet(out_pq)
    assert out_pq.exists()
    assert len(pl.read_parquet(out_pq)) == 3

    out_csv = tmp_path / "output.csv"
    df.to_csv(out_csv)
    assert out_csv.exists()
    assert len(pl.read_csv(out_csv)) == 3


def test_cli_lazy_execution(sample_parquet: Path, tmp_path: Path):
    out_file = tmp_path / "cli_out.csv"
    # Run CLI using python module
    cmd = [
        sys.executable,
        "-m",
        "pytae",
        str(sample_parquet),
        "-filter",
        "val1 > 15",
        "-mutate",
        "calc = val1 * 10",
        "-select",
        "id, calc",
        "-o",
        str(out_file),
    ]
    import subprocess

    subprocess.check_call(cmd)
    assert out_file.exists()
    res = pl.read_csv(out_file)
    assert list(res.columns) == ["id", "calc"]
    assert len(res) == 4
    assert res["calc"].to_list() == [200, 300, 400, 500]
