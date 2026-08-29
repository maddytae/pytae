import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae  # noqa: F401


def _df():
    return pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo", "Chinstrap", "Adelie"],
            "body_mass_g": [74125, 271425, 119925, 89100],
            "code": ["A 1", "B 2", "C 3", "D 4"],
        }
    )


def test_qry_equality():
    result = _df().qry({"species": "Adelie"})
    assert list(result.index) == [0, 3]


def test_qry_list_membership():
    result = _df().qry({"species": ["Adelie", "Gentoo"]})
    assert list(result["species"]) == ["Adelie", "Gentoo", "Adelie"]


def test_qry_in_and_not_in():
    df = _df()
    assert list(df.qry({"species": ("in", ["Gentoo"])})["species"]) == ["Gentoo"]
    assert list(df.qry({"species": ("not in", ["Adelie", "Gentoo"])})["species"]) == ["Chinstrap"]


def test_qry_comparison():
    result = _df().qry({"body_mass_g": (">", 81500)})
    assert list(result["species"]) == ["Gentoo", "Chinstrap", "Adelie"]


def test_qry_interval():
    result = _df().qry({"body_mass_g": "(85000,100000)"})
    assert list(result["species"]) == ["Adelie"]
    assert result["body_mass_g"].iloc[0] == 89100


def test_qry_does_not_mutate_original():
    df = _df()
    df.qry({"species": "Adelie"})
    assert len(df) == 4


def test_qry_in_requires_list():
    with pytest.raises(ValueError, match="must be a list"):
        _df().qry({"species": ("in", "Adelie")})
