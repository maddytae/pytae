import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae  # noqa: F401  — registers df.select()


def test_select_regex_kwarg():
    df = pd.DataFrame(
        {
            "species": [1],
            "bill_length_mm": [2],
            "bill_depth_mm": [3],
            "body_mass_g": [4],
        }
    )

    result = df.select(regex="^bill")
    assert list(result.columns) == ["bill_length_mm", "bill_depth_mm"]


def test_select_regex_additive_with_explicit_name():
    df = pd.DataFrame(
        {
            "species": [1],
            "bill_length_mm": [2],
            "body_mass_g": [3],
        }
    )

    result = df.select("species", regex="bill|body")
    assert list(result.columns) == ["species", "bill_length_mm", "body_mass_g"]


def test_select_regex_invalid_pattern():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="invalid regex"):
        df.select(regex="[")


def _wide():
    return pd.DataFrame(
        {
            "species": [1],
            "island": [2],
            "bill_length_mm": [3],
            "bill_depth_mm": [4],
            "body_mass_g": [5],
        }
    )


def test_select_contains_startswith_endswith():
    df = _wide()
    assert list(df.select(contains="bill").columns) == ["bill_length_mm", "bill_depth_mm"]
    assert list(df.select(startswith="bill").columns) == ["bill_length_mm", "bill_depth_mm"]
    assert list(df.select(endswith="_mm").columns) == ["bill_length_mm", "bill_depth_mm"]


def test_select_dtype_numeric_and_non_numeric():
    df = pd.DataFrame({"name": ["a"], "n": [1], "x": [1.5]})
    assert list(df.select(dtype="numeric").columns) == ["n", "x"]
    assert list(df.select(dtype="non_numeric").columns) == ["name"]


def test_select_exclude_dtype_numeric_vs_non_numeric():
    """exclude_dtype='numeric' keeps strings; exclude_dtype='non_numeric' keeps numbers."""
    df = pd.DataFrame({"name": ["a"], "n": [1], "x": [1.5]})
    assert list(df.select(exclude_dtype="numeric").columns) == ["name"]
    assert list(df.select(exclude_dtype="non_numeric").columns) == ["n", "x"]
    assert list(df.select(exclude_dtype="numeric").columns) != list(
        df.select(exclude_dtype="non_numeric").columns
    )


def test_select_exclude_dtype_cannot_combine():
    df = pd.DataFrame({"name": ["a"], "n": [1]})
    with pytest.raises(ValueError, match="exclude_dtype cannot be combined"):
        df.select("name", exclude_dtype="numeric")


def test_select_slice_and_missing_list():
    df = _wide()
    assert list(df.select("species:bill_length_mm").columns) == [
        "species",
        "island",
        "bill_length_mm",
    ]
    with pytest.raises(KeyError, match="not found"):
        df.select(["nope"])
    with pytest.raises(KeyError, match=r"Column not found: '\^bill'"):
        df.select("^bill")


def test_select_unknown_exact_name_does_not_skip():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    with pytest.raises(KeyError, match=r"Column not found: 'd'"):
        df.select("d", "a", "b")


def test_select_everything():
    from pytae.select import everything

    df = _wide()
    assert list(df.select("species", everything()).columns) == list(df.columns)
