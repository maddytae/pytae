"""Unit tests for key-aware fuzzy joining in Pytae."""

from __future__ import annotations

import pytest

import pytae as pt


def test_fuzzy_join_left_and_inner() -> None:
    df1 = pt.DataFrame({
        "id": [1, 2, 3, 4],
        "company": ["Google Inc", "Apple Corp", "Amazon Web Svc", "Unknown Co"],
    })
    df2 = pt.DataFrame({
        "company": ["Googlr Inc", "Apple Corporation", "Amazon Web Services", "Netflix Inc"],
        "revenue": [1000, 2000, 3000, 4000],
    })

    # Left join with score column
    left_res = df1.join(df2, on="company", how="left", fuzzy=0.80, score="sim_score")
    assert len(left_res) == 4
    assert left_res["sim_score"][0] == 0.9000
    assert left_res["revenue"][0] == 1000
    assert left_res["sim_score"][1] is None
    assert left_res["revenue"][1] is None
    assert left_res["sim_score"][2] == 0.8485
    assert left_res["revenue"][2] == 3000

    # Inner join without score column
    inner_res = df1.join(df2, on="company", how="inner", fuzzy=0.80)
    assert len(inner_res) == 2
    assert "sim_score" not in inner_res.columns
    assert set(inner_res["id"].to_list()) == {1, 3}
    assert set(inner_res["revenue"].to_list()) == {1000, 3000}


def test_fuzzy_join_differing_keys() -> None:
    df1 = pt.DataFrame({
        "cust": ["Microsoft Corp", "Tesla Motors"],
    })
    df2 = pt.DataFrame({
        "client": ["Microsft Corp", "Tesla Inc"],
        "tier": ["Gold", "Silver"],
    })

    res = df1.join(df2, left_on="cust", right_on="client", how="inner", fuzzy=0.85, score="score")
    assert len(res) == 1
    assert res["cust"][0] == "Microsoft Corp"
    assert res["tier"][0] == "Gold"
    assert res["score"][0] > 0.90


def test_fuzzy_join_invalid_threshold() -> None:
    df1 = pt.DataFrame({"k": ["a"]})
    df2 = pt.DataFrame({"k": ["a"]})
    with pytest.raises(ValueError, match="fuzzy threshold must be between 0.0 and 1.0"):
        df1.join(df2, on="k", fuzzy=1.5)
