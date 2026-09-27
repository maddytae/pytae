import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_select_regex_kwarg():
    df = pd.DataFrame(
        {
            "species": [1],
            "bill_length_mm": [2],
            "bill_depth_mm": [3],
            "body_mass_g": [4],
        }
    )

    result = pt.select(df, regex="^bill")
    assert list(result.columns) == ["bill_length_mm", "bill_depth_mm"]


def test_select_regex_additive_with_explicit_name():
    df = pd.DataFrame(
        {
            "species": [1],
            "bill_length_mm": [2],
            "body_mass_g": [3],
        }
    )

    result = pt.select(df, "species", regex="bill|body")
    assert list(result.columns) == ["species", "bill_length_mm", "body_mass_g"]


def test_select_regex_invalid_pattern():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="invalid regex"):
        pt.select(df, regex="[")


def test_select_dtype_numeric_includes_uint():
    df = pd.DataFrame({"i": pd.array([1, 2], dtype="int64"), "u": pd.array([1, 2], dtype="uint8")})
    assert pt.select(df, dtype="numeric").columns.tolist() == ["i", "u"]


def test_select_dtype_datetime_includes_tz_aware():
    df = pd.DataFrame(
        {
            "d": pd.to_datetime(["2020-01-01"]),
            "dtz": pd.to_datetime(["2020-01-01"]).tz_localize("UTC"),
        }
    )
    assert pt.select(df, dtype="datetime").columns.tolist() == ["d", "dtz"]


def test_select_dtype_accepts_tuple():
    df = pd.DataFrame({"i": [1], "u": pd.array([1], dtype="uint8"), "s": ["x"]})
    assert pt.select(df, dtype=("int64", "uint8")).columns.tolist() == ["i", "u"]


def test_select_colon_column_name_exact_match_wins():
    df = pd.DataFrame({"a:b": [1, 2], "c": [3, 4]})
    assert pt.select(df, "a:b").columns.tolist() == ["a:b"]


def test_select_integer_column_names_with_contains_startswith():
    df = pd.DataFrame({0: [1, 2], "b": [3, 4]})
    assert pt.select(df, contains="0").columns.tolist() == [0]
    assert pt.select(df, startswith="0").columns.tolist() == [0]


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
    assert list(pt.select(df, contains="bill").columns) == ["bill_length_mm", "bill_depth_mm"]
    assert list(pt.select(df, startswith="bill").columns) == ["bill_length_mm", "bill_depth_mm"]
    assert list(pt.select(df, endswith="_mm").columns) == ["bill_length_mm", "bill_depth_mm"]


def test_select_dtype_numeric_and_non_numeric():
    df = pd.DataFrame({"name": ["a"], "n": [1], "x": [1.5]})
    assert list(pt.select(df, dtype="numeric").columns) == ["n", "x"]
    assert list(pt.select(df, dtype="non_numeric").columns) == ["name"]


def test_select_exclude_dtype_numeric_vs_non_numeric():
    """exclude_dtype='numeric' keeps strings; exclude_dtype='non_numeric' keeps numbers."""
    df = pd.DataFrame({"name": ["a"], "n": [1], "x": [1.5]})
    assert list(pt.select(df, exclude_dtype="numeric").columns) == ["name"]
    assert list(pt.select(df, exclude_dtype="non_numeric").columns) == ["n", "x"]
    assert list(pt.select(df, exclude_dtype="numeric").columns) != list(
        pt.select(df, exclude_dtype="non_numeric").columns
    )


def test_select_exclude_dtype_cannot_combine():
    df = pd.DataFrame({"name": ["a"], "n": [1]})
    with pytest.raises(ValueError, match="exclude_dtype cannot be combined"):
        pt.select(df, "name", exclude_dtype="numeric")


def test_select_slice_and_missing_list():
    df = _wide()
    assert list(pt.select(df, "species:bill_length_mm").columns) == [
        "species",
        "island",
        "bill_length_mm",
    ]
    with pytest.raises(KeyError, match="not found"):
        pt.select(df, ["nope"])
    with pytest.raises(KeyError, match=r"Column not found: '\^bill'"):
        pt.select(df, "^bill")


def test_select_unknown_exact_name_does_not_skip():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    with pytest.raises(KeyError, match=r"Column not found: 'd'"):
        pt.select(df, "d", "a", "b")


def test_select_everything():
    from pytae.select import everything

    df = _wide()
    # Both everything() instance and everything class
    assert list(pt.select(df, "species", everything()).columns) == list(df.columns)
    assert list(pt.select(df, "species", everything).columns) == list(df.columns)
    assert list(pt.select(df, "species", pt.everything).columns) == list(df.columns)


def test_select_negative_column_syntax():
    df = _wide()
    # Single negative column
    assert list(pt.select(df, "-species").columns) == [
        "island",
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]
    # Tilde syntax
    assert list(pt.select(df, "~island").columns) == [
        "species",
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]
    # Multiple negative columns
    assert list(pt.select(df, "-species", "-island").columns) == [
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]
    # Negative column slice
    assert list(pt.select(df, "-bill_length_mm:body_mass_g").columns) == [
        "species",
        "island",
    ]


def test_select_exclude_kwarg():
    df = _wide()
    assert list(pt.select(df, exclude="species").columns) == [
        "island",
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]
    assert list(pt.select(df, exclude=["species", "island"]).columns) == [
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]


def test_select_positive_and_negative_combination():
    df = _wide()
    # Positive slice minus one column
    res = pt.select(df, "species:body_mass_g", "-island")
    assert list(res.columns) == [
        "species",
        "bill_length_mm",
        "bill_depth_mm",
        "body_mass_g",
    ]


def test_select_negative_typo_raises_hint():
    df = _wide()
    with pytest.raises(KeyError, match=r"Column to exclude not found: 'speceis' \(did you mean 'species'\?\)"):
        pt.select(df, "-speceis")


def test_select_bracketed_names_and_slices():
    df = pd.DataFrame({
        "species": [1],
        "island name": [2],
        "bill length mm": [3],
        "body mass g": [4],
    })
    # Single bracketed name
    assert list(pt.select(df, "[island name]").columns) == ["island name"]
    # Multiple bracketed names
    assert list(pt.select(df, "[island name]", "[body mass g]").columns) == ["island name", "body mass g"]
    # Comma-separated bracketed string
    assert list(pt.select(df, "species, [bill length mm]").columns) == ["species", "bill length mm"]
    # Bracketed slice
    assert list(pt.select(df, "[island name]:[body mass g]").columns) == ["island name", "bill length mm", "body mass g"]
    # Bracketed negation
    assert list(pt.select(df, "-[island name]").columns) == ["species", "bill length mm", "body mass g"]


def test_select_contains_startswith_endswith_tuples():
    # Lib Issue 14: contains, startswith, endswith accept tuples
    df = pd.DataFrame({"bill_length_mm": [1], "bill_depth_mm": [2], "body_mass_g": [3]})
    res_c = pt.select(df, contains=("bill", "body"))
    assert list(res_c.columns) == ["bill_length_mm", "bill_depth_mm", "body_mass_g"]

    res_sw = pt.select(df, startswith=("bill", "body"))
    assert list(res_sw.columns) == ["bill_length_mm", "bill_depth_mm", "body_mass_g"]

    res_ew = pt.select(df, endswith=("mm", "g"))
    assert list(res_ew.columns) == ["bill_length_mm", "bill_depth_mm", "body_mass_g"]


def test_select_exclude_bracketed_string():
    # Issue 8: exclude with bracketed names
    df = pd.DataFrame({"col a": [1], "col b": [2], "keep": [3]})
    res = pt.select(df, exclude="[col a, col b]")
    assert list(res.columns) == ["keep"]
