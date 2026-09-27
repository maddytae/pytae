import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae.mutate import parse_mutate_spec


def _df():
    return pd.DataFrame(
        {
            "species": ["Adelie", "Gentoo"],
            "body_mass_g": [3000.0, 4000.0],
            "bill_length_mm": [30.0, 40.0],
        }
    )


def test_mutate_basic_expression():
    result = pt.mutate(_df(), bmi="body_mass_g / bill_length_mm ** 2")
    assert list(result["bmi"]) == [pytest.approx(3.333333, rel=1e-4), pytest.approx(2.5)]


def test_mutate_multiple_entries_in_one_call():
    result = pt.mutate(_df(), heavy="body_mass_g > 3500", mass_kg="body_mass_g / 1000")
    assert list(result["heavy"]) == [False, True]
    assert list(result["mass_kg"]) == [3.0, 4.0]


def test_mutate_later_entry_references_earlier_one():
    result = pt.mutate(_df(), mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")
    assert result["mass_lb"].iloc[0] == pytest.approx(6.61386)


def test_mutate_string_comparison_needs_quotes():
    result = pt.mutate(_df(), is_adelie="species == 'Adelie'")
    assert list(result["is_adelie"]) == [True, False]


def test_mutate_does_not_modify_original():
    df = _df()
    pt.mutate(df, bmi="body_mass_g / bill_length_mm ** 2")
    assert "bmi" not in df.columns


def test_mutate_overwrites_existing_column():
    result = pt.mutate(_df(), body_mass_g="body_mass_g / 1000")
    assert list(result["body_mass_g"]) == [3.0, 4.0]


def test_mutate_unknown_column_suggests_typo():
    with pytest.raises(KeyError, match="did you mean 'body_mass_g'"):
        pt.mutate(_df(), bmi="bod_mass_g / bill_length_mm")


def test_mutate_quoting_column_reference_breaks_arithmetic():
    with pytest.raises(TypeError):
        pt.mutate(_df(), bmi="'body_mass_g' / 'bill_length_mm' ** 2")


def test_mutate_empty_spec_errors():
    with pytest.raises(ValueError, match="mutate\\(\\) expects at least one"):
        pt.mutate(_df())


def test_mutate_if_else_basic():
    result = pt.mutate(_df(), size="if_else(body_mass_g >= 3500, 'heavy', 'light')")
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_if_else_numeric_values():
    result = pt.mutate(_df(), bonus="if_else(body_mass_g >= 3500, 100, 10)")
    assert list(result["bonus"]) == [10, 100]


def test_mutate_if_else_value_can_be_column_expression():
    result = pt.mutate(_df(), adjusted="if_else(body_mass_g >= 3500, body_mass_g / 1000, body_mass_g)")
    assert list(result["adjusted"]) == [3000.0, 4.0]


def test_mutate_if_else_wrong_arg_count_errors():
    with pytest.raises(TypeError):
        pt.mutate(_df(), size="if_else(body_mass_g >= 3500, 'heavy')")


def test_mutate_if_else_mixed_dtype_branches():
    result = pt.mutate(_df(), g="if_else(body_mass_g >= 3500, 'heavy', 0)")
    assert list(result["g"]) == [0, "heavy"]


def test_mutate_case_when_mixed_dtype_choices():
    result = pt.mutate(_df(), g="case_when((body_mass_g >= 3500, 'heavy'), 0)")
    assert list(result["g"]) == [0, "heavy"]


def test_mutate_case_when_first_match_wins():
    result = pt.mutate(
        _df(),
        grade="case_when((body_mass_g >= 3800, 'A'), (body_mass_g >= 3200, 'B'), 'C')",
    )
    assert list(result["grade"]) == ["C", "A"]


def test_mutate_case_when_no_default_gives_nan_for_unmatched():
    result = pt.mutate(_df(), grade="case_when((body_mass_g >= 3800, 'A'))")
    assert result["grade"].iloc[1] == "A"
    assert pd.isna(result["grade"].iloc[0])


def test_mutate_case_when_default_must_be_last():
    with pytest.raises(ValueError, match="case_when default .*must be the last argument"):
        pt.mutate(_df(), grade="case_when('C', (body_mass_g >= 3800, 'A'))")


def test_mutate_case_when_requires_at_least_one_entry():
    with pytest.raises(ValueError, match="case_when expects at least one"):
        pt.mutate(_df(), grade="case_when()")


def test_mutate_if_else_and_case_when_chain_with_other_entries():
    result = pt.mutate(
        _df(),
        mass_kg="body_mass_g / 1000",
        size="if_else(mass_kg >= 3.5, 'heavy', 'light')",
    )
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_local_var_reference():
    threshold = 3500.0
    result = pt.mutate(_df(), heavy="body_mass_g >= @threshold")
    assert list(result["heavy"]) == [False, True]


def test_mutate_local_var_reference_via_accessor():
    threshold = 3500.0
    result = _df().pt.mutate(heavy="body_mass_g >= @threshold")
    assert list(result["heavy"]) == [False, True]


def test_mutate_local_var_reference_in_if_else():
    threshold = 3500.0
    result = pt.mutate(_df(), size="if_else(body_mass_g >= @threshold, 'heavy', 'light')")
    assert list(result["size"]) == ["light", "heavy"]


def test_mutate_local_var_reference_in_case_when():
    low, high = 3200.0, 3800.0
    result = pt.mutate(
        _df(),
        grade="case_when((body_mass_g >= @high, 'A'), (body_mass_g >= @low, 'B'), 'C')",
    )
    assert list(result["grade"]) == ["C", "A"]


def test_mutate_unknown_local_var_suggests_typo_free_error():
    with pytest.raises(KeyError, match="threshol"):
        pt.mutate(_df(), heavy="body_mass_g >= @threshol")


def test_mutate_kwargs():
    df = _df()
    res = pt.mutate(df, bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")
    assert "bmi" in res.columns
    assert "mass_kg" in res.columns
    assert list(res["mass_kg"]) == [3.0, 4.0]


def test_mutate_rejects_unsupported_positional_types():
    df = _df()
    with pytest.raises(TypeError, match="unexpected positional argument"):
        df.pt.mutate(123)
    with pytest.raises(TypeError, match="unexpected positional argument"):
        df.pt.mutate([1, 2, 3])
    with pytest.raises(TypeError, match="callables as keyword arguments"):
        df.pt.mutate(lambda d: d)


def test_mutate_callable_lambda():
    df = _df()
    res = pt.mutate(df, bmi=lambda d: d["body_mass_g"] / d["bill_length_mm"] ** 2)
    assert "bmi" in res.columns
    assert list(res["bmi"]) == [pytest.approx(3.333333, rel=1e-4), pytest.approx(2.5)]


def test_mutate_constants():
    df = _df()
    res = pt.mutate(df, status="'active'", count=42)
    assert list(res["status"]) == ["active", "active"]
    assert list(res["count"]) == [42, 42]


def test_mutate_case_when_default_kwarg():
    df = _df()
    res = pt.mutate(df, g="case_when((body_mass_g >= 3500, 'A'), default='B')")
    assert list(res["g"]) == ["B", "A"]


def test_mutate_case_when_flat_alternating_pairs():
    df = _df()
    res = pt.mutate(df, g="case_when(body_mass_g >= 3800, 'A', body_mass_g >= 3200, 'B', default='C')")
    assert list(res["g"]) == ["C", "A"]


def test_mutate_coalesce_helper():
    df = pd.DataFrame({"a": [1.0, None, None], "b": [None, 2.0, None]})
    res = pt.mutate(df, c="coalesce(a, b, 0.0)")
    assert list(res["c"]) == [1.0, 2.0, 0.0]


def test_mutate_bracketed_and_backtick_columns_in_fallback():
    df = pd.DataFrame({"col a": [10, 20], "col b": [1, 2]})
    res1 = pt.mutate(df, c="if_else([col a] > 15, 'high', 'low')")
    assert list(res1["c"]) == ["low", "high"]
    res2 = pt.mutate(df, c="if_else(`col a` > 15, 'high', 'low')")
    assert list(res2["c"]) == ["low", "high"]
    res3 = pt.mutate(df, total="[col a] + [col b]")
    assert list(res3["total"]) == [11, 22]


def test_parse_mutate_spec_equals_and_comments():
    spec = """
    # calculate weight in kg
    mass_kg = body_mass_g / 1000
    # calculate weight in lbs
    mass_lb = mass_kg * 2.2
    """
    res = parse_mutate_spec(spec)
    assert "mass_kg" in res
    assert "mass_lb" in res
    assert res["mass_kg"] == "body_mass_g / 1000"


def test_parse_mutate_spec_rejects_colon():
    with pytest.raises(ValueError, match="use '=' for assignment"):
        parse_mutate_spec("mass_kg: body_mass_g / 1000")


def test_mutate_load_from_file(tmp_path):
    df = _df()
    file_path = tmp_path / "specs.txt"
    file_path.write_text("mass_kg = body_mass_g / 1000\n# comment\nmass_lb = mass_kg * 2.2\n")
    res = pt.mutate(df, f"@{file_path}")
    assert "mass_kg" in res.columns
    assert "mass_lb" in res.columns


def test_mutate_explicit_params():
    df = _df()
    res = pt.mutate(df, flag="body_mass_g >= @thresh", params={"thresh": 3500.0})
    assert list(res["flag"]) == [False, True]


def test_mutate_unquoted_string_literal_hint():
    df = _df()
    with pytest.raises(KeyError, match="if you intended a string literal, quote it like 'heavy'"):
        pt.mutate(df, status="if_else(body_mass_g > 3500, heavy, light)")


def test_mutate_positional_string_expr():
    df = _df()
    res = df.pt.mutate("mass_kg = body_mass_g / 1000")
    assert "mass_kg" in res.columns
    assert list(res["mass_kg"]) == [3.0, 4.0]

    # Multiple positional expressions
    res2 = df.pt.mutate("mass_kg = body_mass_g / 1000", "mass_lb = mass_kg * 2.2")
    assert "mass_kg" in res2.columns
    assert "mass_lb" in res2.columns


def test_mutate_positional_dict():
    df = _df()
    res = df.pt.mutate({"mass_kg": "body_mass_g / 1000"})
    assert list(res["mass_kg"]) == [3.0, 4.0]


def test_mutate_params_column_creation():
    df = _df()
    # Integer literal assigned to column named 'params'
    res1 = df.pt.mutate(params=10)
    assert "params" in res1.columns
    assert list(res1["params"]) == [10, 10]

    # String expression assigned to column named 'params'
    res2 = df.pt.mutate(params="body_mass_g / 1000")
    assert "params" in res2.columns
    assert list(res2["params"]) == [3.0, 4.0]


def test_mutate_explicit_underscore_params():
    df = _df()
    res = df.pt.mutate(flag="body_mass_g >= @thresh", _params={"thresh": 3500.0})
    assert list(res["flag"]) == [False, True]


def test_mutate_bracketed_columns():
    df = pd.DataFrame({"body mass g": [3000.0, 4000.0], "height": [1.5, 2.0]})
    # Target column has brackets, source has brackets
    res1 = df.pt.mutate("[mass kg] = [body mass g] / 1000")
    assert "mass kg" in res1.columns
    assert list(res1["mass kg"]) == [3.0, 4.0]

    # Mixed source columns (one with space, one without)
    res2 = df.pt.mutate("[bmi score] = [body mass g] / (height ** 2)")
    assert "bmi score" in res2.columns


def test_mutate_grouped_single_col():
    df = pd.DataFrame({"grp": ["a", "a", "b"], "val": [10.0, 20.0, 60.0]})
    res = df.pt.mutate(
        "avg = mean(val), diff = val - avg, total = sum(val), cnt = n, cnt2 = n()",
        by="grp",
    )
    assert list(res["avg"]) == [15.0, 15.0, 60.0]
    assert list(res["diff"]) == [-5.0, 5.0, 0.0]
    assert list(res["total"]) == [30.0, 30.0, 60.0]
    assert list(res["cnt"]) == [2, 2, 1]
    assert list(res["cnt2"]) == [2, 2, 1]


def test_mutate_grouped_multi_col():
    df = pd.DataFrame({
        "g1": ["a", "a", "a", "b"],
        "g2": ["x", "x", "y", "x"],
        "val": [10.0, 30.0, 5.0, 100.0],
    })
    res1 = df.pt.mutate("m = mean(val), cnt = n", by=["g1", "g2"])
    assert list(res1["m"]) == [20.0, 20.0, 5.0, 100.0]
    assert list(res1["cnt"]) == [2, 2, 1, 1]

    # Comma-separated string by="g1, g2"
    res2 = df.pt.mutate("m = mean(val)", by="g1, g2")
    assert list(res2["m"]) == [20.0, 20.0, 5.0, 100.0]


def test_mutate_grouped_spaced_brackets():
    df = pd.DataFrame({"group code": ["a", "a", "b"], "total bill": [10.0, 30.0, 50.0]})
    res = df.pt.mutate("[diff bill] = [total bill] - mean([total bill])", by="group code")
    assert list(res["diff bill"]) == [-10.0, 10.0, 0.0]


def test_mutate_grouped_dropna_observed():
    df = pd.DataFrame({"grp": ["a", None, "a"], "val": [10.0, 50.0, 30.0]})
    res_dropna = df.pt.mutate("m = mean(val)", by="grp", dropna=True)
    assert pd.isna(res_dropna["m"].iloc[1])
    assert res_dropna["m"].iloc[0] == 20.0
    assert res_dropna["m"].iloc[2] == 20.0

    res_keepna = df.pt.mutate("m = mean(val)", by="grp", dropna=False)
    assert res_keepna["m"].iloc[1] == 50.0


def test_mutate_grouped_duplicate_index():
    df = pd.DataFrame({"grp": ["a", "b", "a"], "val": [10.0, 50.0, 30.0]}, index=[0, 1, 0])
    res = df.pt.mutate("m = mean(val)", by="grp")
    assert list(res["m"]) == [20.0, 50.0, 20.0]
    assert list(res.index) == [0, 1, 0]


def test_mutate_grouped_functional_and_callable():
    df = pd.DataFrame({"grp": ["a", "a", "b"], "val": [10.0, 20.0, 60.0]})
    # Functional pt.mutate
    res1 = pt.mutate(df, "avg = mean(val)", by="grp")
    assert list(res1["avg"]) == [15.0, 15.0, 60.0]

    # Callable inside grouped mutate
    res2 = df.pt.mutate(half_mean=lambda g: g["val"].mean() / 2, by="grp")
    assert list(res2["half_mean"]) == [7.5, 7.5, 30.0]


def test_mutate_grouped_unknown_col():
    df = pd.DataFrame({"grp": ["a", "b"], "val": [1, 2]})
    with pytest.raises(KeyError, match="grouping column 'grp_typo' not found"):
        df.pt.mutate("m = mean(val)", by="grp_typo")



