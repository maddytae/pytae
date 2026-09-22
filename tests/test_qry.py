import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def _df():
    return pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo", "Chinstrap", "Adelie"],
            "body_mass_g": [74125, 271425, 119925, 89100],
            "code": ["A 1", "B 2", "C 3", "D 4"],
        }
    )


def test_qry_equality():
    result = pt.qry(_df(), {"species": "Adelie"})
    assert list(result.index) == [0, 3]


def test_qry_list_membership():
    result = pt.qry(_df(), {"species": ["Adelie", "Gentoo"]})
    assert list(result["species"]) == ["Adelie", "Gentoo", "Adelie"]


def test_qry_in_and_not_in():
    df = _df()
    assert list(pt.qry(df, {"species": ("in", ["Gentoo"])})["species"]) == ["Gentoo"]
    assert list(pt.qry(df, {"species": ("not in", ["Adelie", "Gentoo"])})["species"]) == ["Chinstrap"]


def test_qry_comparison():
    result = pt.qry(_df(), {"body_mass_g": (">", 81500)})
    assert list(result["species"]) == ["Gentoo", "Chinstrap", "Adelie"]


def test_qry_interval():
    result = pt.qry(_df(), {"body_mass_g": "(85000,100000)"})
    assert list(result["species"]) == ["Adelie"]
    assert result["body_mass_g"].iloc[0] == 89100


def test_qry_does_not_mutate_original():
    df = _df()
    pt.qry(df, {"species": "Adelie"})
    assert len(df) == 4


def test_qry_in_requires_list():
    with pytest.raises(ValueError, match="must be a list"):
        pt.qry(_df(), {"species": ("in", "Adelie")})


def test_qry_unknown_column_suggests_typo():
    with pytest.raises(KeyError, match=r"unknown column 'speceis' \(did you mean 'species'\?\)"):
        pt.qry(_df(), {"speceis": "Adelie"})


def test_qry_startswith():
    result = pt.qry(_df(), {"species": ("startswith", "Ad")})
    assert list(result["species"]) == ["Adelie", "Adelie"]


def test_qry_endswith():
    result = pt.qry(_df(), {"code": ("endswith", "3")})
    assert list(result["species"]) == ["Chinstrap"]


def test_qry_contains():
    result = pt.qry(_df(), {"species": ("contains", "in")})
    assert list(result["species"]) == ["Chinstrap"]


def test_qry_regex():
    result = pt.qry(_df(), {"code": ("regex", r"^[AB]")})
    assert list(result["species"]) == ["Adelie", "Gentoo"]


def test_qry_startswith_accepts_list_of_prefixes():
    result = pt.qry(_df(), {"species": ("startswith", ["Ad", "Ge"])})
    assert list(result["species"]) == ["Adelie", "Gentoo", "Adelie"]


def test_qry_string_op_on_non_string_column_raises_clear_error():
    with pytest.raises(ValueError, match="needs a string column"):
        pt.qry(_df(), {"body_mass_g": ("startswith", "1")})


def test_qry_isna():
    df = _df()
    df.loc[0, "species"] = None
    result = pt.qry(df, {"species": ("isna",)})
    assert len(result) == 1
    assert result.index[0] == 0


def test_qry_notna():
    df = _df()
    df.loc[0, "species"] = None
    result = pt.qry(df, {"species": ("notna",)})
    assert list(result["species"]) == ["Gentoo", "Chinstrap", "Adelie"]


def test_qry_string_op_treats_missing_as_no_match():
    df = _df()
    df.loc[0, "species"] = None
    result = pt.qry(df, {"species": ("startswith", "Ad")})
    assert list(result["species"]) == ["Adelie"]


def test_qry_unsupported_tuple_operator_lists_string_ops():
    with pytest.raises(ValueError, match="startswith"):
        pt.qry(_df(), {"species": ("badop", "x")})


def test_qry_unsupported_unary_operator():
    with pytest.raises(ValueError, match="Unsupported 1-element tuple operator"):
        pt.qry(_df(), {"species": ("badop",)})


def test_qry_string_expression():
    df = _df()
    res = df.pt.qry("body_mass_g > 100000")
    assert list(res["species"]) == ["Gentoo", "Chinstrap"]


def test_qry_kwargs_operator():
    df = _df()
    res = df.pt.qry(body_mass_g="> 100000")
    assert list(res["species"]) == ["Gentoo", "Chinstrap"]


def test_qry_kwargs_tuple():
    df = _df()
    res = df.pt.qry(body_mass_g=(">", 100000))
    assert list(res["species"]) == ["Gentoo", "Chinstrap"]


def test_qry_kwargs_equality():
    df = _df()
    res = df.pt.qry(species="Adelie")
    assert list(res.index) == [0, 3]


def test_qry_dict_operator_string():
    df = _df()
    res = df.pt.qry({"body_mass_g": "> 100000"})
    assert list(res["species"]) == ["Gentoo", "Chinstrap"]


def test_qry_string_expr_equals_separator():
    df = _df()
    res1 = df.pt.qry("body_mass_g= > 100000")
    res2 = df.pt.qry("body_mass_g=>100000")
    res3 = df.pt.qry("body_mass_g = > 100000")
    res4 = df.pt.qry("body_mass_g = 74125")
    assert list(res1["species"]) == ["Gentoo", "Chinstrap"]
    assert list(res2["species"]) == ["Gentoo", "Chinstrap"]
    assert list(res3["species"]) == ["Gentoo", "Chinstrap"]
    assert list(res4["species"]) == ["Adelie"]

