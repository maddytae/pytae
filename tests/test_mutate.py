import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def _df():
    return pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo"],
            "body_mass_g": [3000.0, 4000.0],
            "bill_length_mm": [30.0, 40.0],
        }
    )


def test_mutate_basic_expression():
    result = pt.mutate(_df(), "bmi: body_mass_g / bill_length_mm ** 2")
    assert list(result["bmi"]) == [pytest.approx(3.333333, rel=1e-4), pytest.approx(2.5)]


def test_mutate_multiple_entries_in_one_call():
    result = pt.mutate(_df(), "heavy: body_mass_g > 3500, mass_kg: body_mass_g / 1000")
    assert list(result["heavy"]) == [False, True]
    assert list(result["mass_kg"]) == [3.0, 4.0]


def test_mutate_later_entry_references_earlier_one():
    result = pt.mutate(_df(), "mass_kg: body_mass_g / 1000, mass_lb: mass_kg * 2.20462")
    assert result["mass_lb"].iloc[0] == pytest.approx(6.61386)


def test_mutate_string_comparison_needs_quotes():
    result = pt.mutate(_df(), "is_adelie: species == 'Adelie'")
    assert list(result["is_adelie"]) == [True, False]


def test_mutate_does_not_modify_original():
    df = _df()
    pt.mutate(df, "bmi: body_mass_g / bill_length_mm ** 2")
    assert "bmi" not in df.columns


def test_mutate_key_quoting_is_optional():
    unquoted = pt.mutate(_df(), "mass_kg: body_mass_g / 1000")
    quoted = pt.mutate(_df(), "'mass_kg': body_mass_g / 1000")
    assert list(unquoted["mass_kg"]) == list(quoted["mass_kg"])


def test_mutate_overwrites_existing_column():
    result = pt.mutate(_df(), "body_mass_g: body_mass_g / 1000")
    assert list(result["body_mass_g"]) == [3.0, 4.0]


def test_mutate_unknown_column_suggests_typo():
    with pytest.raises(KeyError, match="did you mean 'body_mass_g'"):
        pt.mutate(_df(), "bmi: bod_mass_g / bill_length_mm")


def test_mutate_quoting_column_reference_breaks_arithmetic():
    with pytest.raises(TypeError):
        pt.mutate(_df(), "bmi: 'body_mass_g' / 'bill_length_mm' ** 2")


def test_mutate_missing_colon_errors():
    with pytest.raises(ValueError, match="missing ':'"):
        pt.mutate(_df(), "bmi body_mass_g / bill_length_mm")


def test_mutate_empty_spec_errors():
    with pytest.raises(ValueError, match="mutate expects entries"):
        pt.mutate(_df(), "")


def test_mutate_if_else_basic():
    result = pt.mutate(_df(), "size: if_else(body_mass_g >= 3500, 'heavy', 'light')")
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_if_else_numeric_values():
    result = pt.mutate(_df(), "bonus: if_else(body_mass_g >= 3500, 100, 10)")
    assert list(result["bonus"]) == [10, 100]


def test_mutate_if_else_value_can_be_column_expression():
    result = pt.mutate(_df(), "adjusted: if_else(body_mass_g >= 3500, body_mass_g / 1000, body_mass_g)")
    assert list(result["adjusted"]) == [3000.0, 4.0]


def test_mutate_if_else_wrong_arg_count_errors():
    with pytest.raises(TypeError):
        pt.mutate(_df(), "size: if_else(body_mass_g >= 3500, 'heavy')")


def test_mutate_if_else_mixed_dtype_branches():
    # a string branch and a numeric branch have no common numpy dtype -- falls
    # back to an object array instead of crashing with DTypePromotionError
    result = pt.mutate(_df(), "g: if_else(body_mass_g >= 3500, 'heavy', 0)")
    assert list(result["g"]) == [0, "heavy"]


def test_mutate_case_when_mixed_dtype_choices():
    result = pt.mutate(_df(), "g: case_when((body_mass_g >= 3500, 'heavy'), 0)")
    assert list(result["g"]) == [0, "heavy"]


def test_mutate_case_when_first_match_wins():
    result = pt.mutate(_df(), 
        "grade: case_when((body_mass_g >= 3800, 'A'), (body_mass_g >= 3200, 'B'), 'C')"
    )
    assert list(result["grade"]) == ["C", "A"]


def test_mutate_case_when_no_default_gives_nan_for_unmatched():
    result = pt.mutate(_df(), "grade: case_when((body_mass_g >= 3800, 'A'))")
    assert result["grade"].iloc[1] == "A"
    assert pd.isna(result["grade"].iloc[0])


def test_mutate_case_when_default_must_be_last():
    with pytest.raises(ValueError, match="case_when default .*must be the last argument"):
        pt.mutate(_df(), "grade: case_when('C', (body_mass_g >= 3800, 'A'))")


def test_mutate_case_when_requires_at_least_one_entry():
    with pytest.raises(ValueError, match="case_when expects at least one"):
        pt.mutate(_df(), "grade: case_when()")


def test_mutate_if_else_and_case_when_chain_with_other_entries():
    result = pt.mutate(_df(), 
        "mass_kg: body_mass_g / 1000, size: if_else(mass_kg >= 3.5, 'heavy', 'light')"
    )
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_local_var_reference():
    threshold = 3500.0
    result = pt.mutate(_df(), "heavy: body_mass_g >= @threshold")
    assert list(result["heavy"]) == [False, True]


def test_mutate_local_var_reference_via_accessor():
    threshold = 3500.0
    result = _df().pt.mutate("heavy: body_mass_g >= @threshold")
    assert list(result["heavy"]) == [False, True]


def test_mutate_local_var_reference_in_if_else():
    threshold = 3500.0
    result = pt.mutate(_df(), "size: if_else(body_mass_g >= @threshold, 'heavy', 'light')")
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_local_var_reference_in_case_when():
    low, high = 3200.0, 3800.0
    result = pt.mutate(_df(), 
        "grade: case_when((body_mass_g >= @high, 'A'), (body_mass_g >= @low, 'B'), 'C')"
    )
    assert list(result["grade"]) == ["C", "A"]


def test_mutate_unknown_local_var_suggests_typo_free_error():
    with pytest.raises(KeyError, match="threshol"):
        pt.mutate(_df(), "heavy: body_mass_g >= @threshol")
