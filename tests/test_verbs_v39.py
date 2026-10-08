from __future__ import annotations

import pandas as pd
import pytest

import pytae as pt


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Gentoo", "Gentoo", "Chinstrap"],
            "island": ["Biscoe", "Biscoe", "Biscoe", "Dream", "Dream"],
            "mass": [3800, 4200, 5000, 5200, 3900],
            "bill": [39.1, 40.5, 49.2, 48.5, 50.0],
        }
    )


# ==============================================================================
# 1. Tests for filter()
# ==============================================================================

def test_filter_callable_lambda():
    df = _sample_df()
    # Bare lambda on df.pt
    res = df.pt.filter(lambda d: d["mass"] > 4000)
    assert len(res) == 3
    assert list(res["mass"]) == [4200, 5000, 5200]

    # Functional verb pt.filter
    res2 = pt.filter(df, lambda d: d["species"] == "Adelie")
    assert len(res2) == 2


def test_filter_string_and_kwargs():
    df = _sample_df()
    res = df.pt.filter("mass > 4000", species="Gentoo")
    assert len(res) == 2
    assert list(res["species"]) == ["Gentoo", "Gentoo"]


def test_filter_rejects_mixing_callable():
    df = _sample_df()
    with pytest.raises(TypeError, match="callable/lambda predicates cannot be mixed"):
        df.pt.filter(lambda d: d["mass"] > 4000, species="Gentoo")


# ==============================================================================
# 2. Tests for distinct()
# ==============================================================================

def test_distinct_all_columns():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    res = df.pt.distinct()
    assert len(res) == 2
    assert list(res["a"]) == [1, 2]
    assert list(res.index) == [0, 1]


def test_distinct_positional_args():
    df = pd.DataFrame({"species": ["A", "A", "B"], "island": ["X", "Y", "X"], "val": [1, 2, 3]})
    res = df.pt.distinct("species")
    assert len(res) == 2
    assert list(res["species"]) == ["A", "B"]

    res_multi = df.pt.distinct("species", "island")
    assert len(res_multi) == 3


def test_distinct_rejects_lists():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(TypeError, match="distinct\\(\\) takes column names as positional arguments.*Lists are not accepted"):
        df.pt.distinct(["a", "b"])


# ==============================================================================
# 3. Tests for by() and ungroup()
# ==============================================================================

def test_by_rejects_lists():
    df = _sample_df()
    with pytest.raises(TypeError, match="df\\.pt\\.by\\(\\) takes column names as positional arguments.*Lists are not accepted"):
        df.pt.by(["species", "island"])


def test_by_rejects_none():
    df = _sample_df()
    with pytest.raises(TypeError, match="df\\.pt\\.by\\(None\\) is not supported"):
        df.pt.by(None)


def test_by_requires_args():
    df = _sample_df()
    with pytest.raises(ValueError, match="df\\.pt\\.by\\(\\) takes at least one column name"):
        df.pt.by()


def test_by_chains_into_mutate():
    df = _sample_df()
    # df.pt.by("species").pt.mutate("mean_mass = mean(mass)")
    res = df.pt.by("species").pt.mutate("mean_mass = mean(mass)")
    assert "mean_mass" in res.columns
    # Adelie mass mean: (3800 + 4200) / 2 = 4000
    assert res.loc[res["species"] == "Adelie", "mean_mass"].iloc[0] == 4000.0


def test_by_chains_into_agg_and_clears_grouping():
    df = _sample_df()
    # df.pt.by("species").pt.agg("mean")
    grouped = df.pt.by("species")
    res = grouped.pt.agg("mean")
    assert "_pt_by" not in res.attrs
    assert len(res) == 3
    assert list(res["species"]) == ["Adelie", "Chinstrap", "Gentoo"]

    # Verify input df was never mutated
    assert "_pt_by" not in df.attrs


def test_by_overwritten_by_second_by():
    df = _sample_df()
    df_by = df.pt.by("species").pt.by("island")
    assert df_by.attrs["_pt_by"] == ("island",)
    assert "_pt_by" not in df.attrs


def test_ungroup_clears_by():
    df = _sample_df()
    grouped = df.pt.by("species", "island")
    assert "_pt_by" in grouped.attrs
    assert "_pt_by" not in df.attrs
    ungrouped = grouped.pt.ungroup()
    assert "_pt_by" not in ungrouped.attrs


def test_by_non_destructive_input_isolation():
    df = _sample_df()
    grouped = pt.by(df, "species")
    assert grouped is not df
    assert "_pt_by" in grouped.attrs
    assert "_pt_by" not in df.attrs

    # Functional agg does not touch input attrs, clears on output
    res = pt.agg(grouped, "mean")
    assert "_pt_by" not in res.attrs
    assert "_pt_by" in grouped.attrs
    assert "_pt_by" not in df.attrs

    # pick does not touch input attrs, clears on output
    res_pick = pt.pick(grouped, "mass", n=1)
    assert "_pt_by" not in res_pick.attrs
    assert "_pt_by" in grouped.attrs
    assert "_pt_by" not in df.attrs


def test_by_chains_into_slice_max():
    df = _sample_df()
    res = df.pt.by("species").pt.slice_max("mass", n=1)
    assert len(res) == 3
    # Check max per species
    assert set(res["mass"]) == {4200, 5200, 3900}
    assert "_pt_by" not in res.attrs
    assert "_pt_by" not in df.attrs

