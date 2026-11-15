"""Unit tests for stratified and group-aware sampling in Pytae."""

from __future__ import annotations

import pytae as pt


def test_dataframe_sample_prop_frac_n() -> None:
    df = pt.DataFrame({"id": list(range(100))})
    s_n = df.sample(n=10, seed=42)
    assert len(s_n) == 10

    s_prop = df.sample(prop=0.15, seed=42)
    assert len(s_prop) == 15

    s_frac = df.sample(frac=0.20, seed=42)
    assert len(s_frac) == 20


def test_grouped_stratified_sample() -> None:
    df = pt.DataFrame({
        "dept": ["Engineering"] * 50 + ["Sales"] * 30 + ["Marketing"] * 20,
        "val": list(range(100)),
    })

    # Sample exactly 5 rows per group
    res_n = df.by("dept").sample(n=5, seed=42)
    assert len(res_n) == 15
    counts = res_n.count("dept")
    dept_counts = dict(zip(counts["dept"].to_list(), counts["n"].to_list()))
    assert dept_counts == {"Engineering": 5, "Sales": 5, "Marketing": 5}

    # Sample proportion per group
    res_prop = df.by("dept").sample(prop=0.10, seed=42)
    prop_counts = dict(zip(res_prop.count("dept")["dept"].to_list(), res_prop.count("dept")["n"].to_list()))
    assert prop_counts["Engineering"] == 5
    assert prop_counts["Sales"] == 3
    assert prop_counts["Marketing"] == 2


def test_sample_clears_grouping() -> None:
    df = pt.DataFrame({
        "dept": ["Engineering"] * 10 + ["Sales"] * 10,
        "salary": [100.0] * 20,
    })
    # Grouping should be consumed by sample, leaving subsequent operations ungrouped
    res = df.by("dept").sample(n=2, seed=42).mutate(total_count="count()")
    assert len(res) == 4
    assert res["total_count"].to_list() == [4, 4, 4, 4]
