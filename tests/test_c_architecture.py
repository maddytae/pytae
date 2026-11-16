"""Comprehensive unit and integration test suite for the c. architecture in Pytae."""

from __future__ import annotations

from typing import Any

import pytest

import pytae as pt
from pytae import c


@pytest.fixture
def sample_df() -> pt.DataFrame:
    return pt.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["alice", "bob", "charlie", "david"],
            "age": [25, 35, 45, 30],
            "salary": [50000, 70000, None, 80000],
            "revenue": [100, 200, 300, 400],
            "cost": [50, 40, 100, 80],
            "dept": ["IT", "IT", "HR", "HR"],
            "ssn": ["111", "222", "333", "444"],
        }
    )


def test_c_filter(sample_df: pt.DataFrame) -> None:
    res = sample_df.filter(c.age > 28, c.dept == "IT")
    assert len(res) == 1
    assert res.to("pandas").iloc[0]["name"] == "bob"


def test_c_filter_bitwise_or(sample_df: pt.DataFrame) -> None:
    res = sample_df.filter((c.age < 28) | (c.age > 40))
    assert len(res) == 2
    names = set(res.to("pandas")["name"])
    assert names == {"alice", "charlie"}


def test_c_mutate_arithmetic(sample_df: pt.DataFrame) -> None:
    res = sample_df.mutate(ratio=c.revenue / c.cost, bonus=c.salary * 0.1)
    pdf = res.to("pandas")
    assert pdf.loc[0, "ratio"] == 2.0
    assert pdf.loc[1, "bonus"] == 7000.0


def test_c_mutate_string_methods(sample_df: pt.DataFrame) -> None:
    res = sample_df.mutate(
        upper_name=c.name.str.to_upper(),
        name_len=c.name.str.len(),
        is_a=c.name.str.starts_with("a"),
    )
    pdf = res.to("pandas")
    assert pdf.loc[0, "upper_name"] == "ALICE"
    assert pdf.loc[0, "name_len"] == 5
    assert bool(pdf.loc[0, "is_a"]) is True
    assert bool(pdf.loc[1, "is_a"]) is False


def test_c_select_columns(sample_df: pt.DataFrame) -> None:
    res = sample_df.select(c.id, c.name, c.dept)
    assert res.columns == ["id", "name", "dept"]


def test_c_select_range(sample_df: pt.DataFrame) -> None:
    res = sample_df.select(c.name.to(c.salary), c.dept)
    assert res.columns == ["name", "age", "salary", "dept"]


def test_c_select_drop(sample_df: pt.DataFrame) -> None:
    res = sample_df.select(~c.ssn)
    assert "ssn" not in res.columns
    assert "id" in res.columns
    assert len(res.columns) == 7


def test_c_select_drop_range(sample_df: pt.DataFrame) -> None:
    res = sample_df.select(~c.age.to(c.cost))
    assert res.columns == ["id", "name", "dept", "ssn"]


def test_c_select_rename(sample_df: pt.DataFrame) -> None:
    res = sample_df.select(c.name, user_id=c.id)
    assert res.columns == ["name", "user_id"]
    assert res.to("pandas").iloc[0]["user_id"] == 1


def test_c_by_agg(sample_df: pt.DataFrame) -> None:
    res = sample_df.by(c.dept).agg(avg_age=c.age.mean(), count=c.id.count())
    pdf = res.to("pandas")
    assert len(pdf) == 2
    it_row = pdf[pdf["dept"] == "IT"].iloc[0]
    assert it_row["avg_age"] == 30.0
    assert it_row["count"] == 2


def test_c_arrange(sample_df: pt.DataFrame) -> None:
    res = sample_df.arrange(c.dept.asc(), c.age.desc())
    pdf = res.to("pandas")
    # HR department should come first alphabetically
    assert pdf.iloc[0]["dept"] == "HR"
    assert pdf.iloc[0]["age"] == 45
    assert pdf.iloc[1]["age"] == 30


def test_c_fillna_constant_and_expression(sample_df: pt.DataFrame) -> None:
    res = sample_df.fillna(c.salary.fill(0))
    pdf = res.to("pandas")
    assert pdf.loc[2, "salary"] == 0

    # Fill with computed expression
    res2 = sample_df.fillna(c.salary.fill(c.age * 1000))
    pdf2 = res2.to("pandas")
    assert pdf2.loc[2, "salary"] == 45000


def test_c_distinct_and_count(sample_df: pt.DataFrame) -> None:
    res = sample_df.distinct(c.dept)
    assert len(res) == 2

    cnt = sample_df.count(c.dept)
    assert len(cnt) == 2
    assert "n" in cnt.columns


def test_c_special_characters_bracket() -> None:
    df = pt.DataFrame({"Annual Revenue": [100, 200], "Customer ID": [1, 2]})
    res = df.filter(c["Annual Revenue"] > 150)
    assert len(res) == 1
    assert res.to("pandas").iloc[0]["Customer ID"] == 2


def test_c_cli_full_pipeline(tmp_path: Any, capsys: Any) -> None:
    import pandas as pd

    from pytae import cli

    df = pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Gentoo"],
            "island": ["Torgersen", "Biscoe", "Biscoe"],
            "body_mass_g": [3750.0, 3200.0, 5000.0],
        }
    )
    p = str(tmp_path / "data.csv")
    df.to_csv(p, index=False)

    cli.main(
        [
            p,
            "-filter",
            "c.species == 'Adelie' and c.body_mass_g > 3500",
            "-mutate",
            "mass_kg = c.body_mass_g / 1000",
            "-arrange",
            "c.mass_kg.desc()",
            "-select",
            "c.species, c.island, c.mass_kg",
            "-shape",
        ]
    )
    out = capsys.readouterr().out.strip()
    assert out == "(1, 3)"
