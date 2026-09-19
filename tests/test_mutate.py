import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae  # noqa: F401


def _df():
    return pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo"],
            "body_mass_g": [3000.0, 4000.0],
            "bill_length_mm": [30.0, 40.0],
        }
    )


def test_mutate_basic_expression():
    result = _df().mutate("bmi: body_mass_g / bill_length_mm ** 2")
    assert list(result["bmi"]) == [pytest.approx(3.333333, rel=1e-4), pytest.approx(2.5)]


def test_mutate_multiple_entries_in_one_call():
    result = _df().mutate("heavy: body_mass_g > 3500, mass_kg: body_mass_g / 1000")
    assert list(result["heavy"]) == [False, True]
    assert list(result["mass_kg"]) == [3.0, 4.0]


def test_mutate_later_entry_references_earlier_one():
    result = _df().mutate("mass_kg: body_mass_g / 1000, mass_lb: mass_kg * 2.20462")
    assert result["mass_lb"].iloc[0] == pytest.approx(6.61386)


def test_mutate_string_comparison_needs_quotes():
    result = _df().mutate("is_adelie: species == 'Adelie'")
    assert list(result["is_adelie"]) == [True, False]


def test_mutate_does_not_modify_original():
    df = _df()
    df.mutate("bmi: body_mass_g / bill_length_mm ** 2")
    assert "bmi" not in df.columns


def test_mutate_key_quoting_is_optional():
    unquoted = _df().mutate("mass_kg: body_mass_g / 1000")
    quoted = _df().mutate("'mass_kg': body_mass_g / 1000")
    assert list(unquoted["mass_kg"]) == list(quoted["mass_kg"])


def test_mutate_overwrites_existing_column():
    result = _df().mutate("body_mass_g: body_mass_g / 1000")
    assert list(result["body_mass_g"]) == [3.0, 4.0]


def test_mutate_unknown_column_suggests_typo():
    with pytest.raises(KeyError, match="did you mean 'body_mass_g'"):
        _df().mutate("bmi: bod_mass_g / bill_length_mm")


def test_mutate_quoting_column_reference_breaks_arithmetic():
    with pytest.raises(TypeError):
        _df().mutate("bmi: 'body_mass_g' / 'bill_length_mm' ** 2")


def test_mutate_missing_colon_errors():
    with pytest.raises(ValueError, match="missing ':'"):
        _df().mutate("bmi body_mass_g / bill_length_mm")


def test_mutate_empty_spec_errors():
    with pytest.raises(ValueError, match="mutate expects entries"):
        _df().mutate("")
