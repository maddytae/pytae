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
    assert list(result["g"]) in ([0, "heavy"], ["0", "heavy"])


def test_mutate_case_when_mixed_dtype_choices():
    result = pt.mutate(_df(), g="case_when((body_mass_g >= 3500, 'heavy'), 0)")
    assert list(result["g"]) in ([0, "heavy"], ["0", "heavy"])


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
    res = df.pt.by("grp").pt.mutate(
        "avg = mean(val), diff = val - avg, total = sum(val), cnt = n, cnt2 = n()",
    )
    assert list(res["avg"]) == [15.0, 15.0, 60.0]
    assert list(res["diff"]) == [-5.0, 5.0, 0.0]
    assert list(res["total"]) == [30.0, 30.0, 60.0]
    assert list(res["cnt"]) == [2, 2, 1]
    assert list(res["cnt2"]) == [2, 2, 1]


def test_mutate_grouped_multi_col():
    df = pd.DataFrame(
        {
            "g1": ["a", "a", "a", "b"],
            "g2": ["x", "x", "y", "x"],
            "val": [10.0, 30.0, 5.0, 100.0],
        }
    )
    res1 = df.pt.by("g1", "g2").pt.mutate("m = mean(val), cnt = n")
    assert list(res1["m"]) == [20.0, 20.0, 5.0, 100.0]
    assert list(res1["cnt"]) == [2, 2, 1, 1]

    # Positional pt.by with multiple columns
    res2 = pt.mutate(pt.by(df, "g1", "g2"), "m = mean(val)")
    assert list(res2["m"]) == [20.0, 20.0, 5.0, 100.0]


def test_mutate_grouped_spaced_brackets():
    df = pd.DataFrame({"group code": ["a", "a", "b"], "total bill": [10.0, 30.0, 50.0]})
    res = df.pt.by("group code").pt.mutate("[diff bill] = [total bill] - mean([total bill])")
    assert list(res["diff bill"]) == [-10.0, 10.0, 0.0]


def test_mutate_grouped_dropna_observed():
    df = pd.DataFrame({"grp": ["a", None, "a"], "val": [10.0, 50.0, 30.0]})
    # Default is dropna=False: computes on the NA group
    res_default = df.pt.by("grp").pt.mutate("m = mean(val)")
    assert res_default["m"].iloc[1] == 50.0
    assert res_default["m"].iloc[0] == 20.0
    assert res_default["m"].iloc[2] == 20.0

    res_dropna = df.pt.by("grp").pt.mutate("m = mean(val)", dropna=True)
    assert pd.isna(res_dropna["m"].iloc[1])
    assert res_dropna["m"].iloc[0] == 20.0
    assert res_dropna["m"].iloc[2] == 20.0

    res_keepna = df.pt.by("grp").pt.mutate("m = mean(val)", dropna=False)
    assert res_keepna["m"].iloc[1] == 50.0


def test_mutate_grouped_duplicate_index():
    df = pd.DataFrame({"grp": ["a", "b", "a"], "val": [10.0, 50.0, 30.0]}, index=[0, 1, 0])
    res = df.pt.by("grp").pt.mutate("m = mean(val)")
    assert list(res["m"]) == [20.0, 50.0, 20.0]
    assert list(res.index) == [0, 1, 0]


def test_mutate_grouped_functional_and_callable():
    df = pd.DataFrame({"grp": ["a", "a", "b"], "val": [10.0, 20.0, 60.0]})
    # Functional pt.mutate
    res1 = pt.mutate(pt.by(df, "grp"), "avg = mean(val)")
    assert list(res1["avg"]) == [15.0, 15.0, 60.0]

    # Callable inside grouped mutate
    res2 = df.pt.by("grp").pt.mutate(half_mean=lambda g: g["val"].mean() / 2)
    assert list(res2["half_mean"]) == [7.5, 7.5, 30.0]


def test_mutate_rejects_by_arg():
    df = pd.DataFrame({"grp": ["a", "b"], "val": [1, 2]})
    with pytest.raises(TypeError, match="df.pt.mutate\\(\\) does not accept 'by'"):
        df.pt.mutate("m = mean(val)", by="grp")
    with pytest.raises(TypeError, match="mutate\\(\\) does not accept 'by'"):
        pt.mutate(df, "m = mean(val)", by="grp")


def test_mutate_coalesce_scalar_broadcast():
    # Lib Issue 5
    df = pd.DataFrame({"a": [None, 2.0, None]}, index=[5, 6, 7])
    res1 = pt.mutate(df, c="coalesce(0, a)")
    assert list(res1["c"]) == [0.0, 0.0, 0.0]

    res2 = pt.mutate(df, c="coalesce(1, 2)")
    assert list(res2["c"]) == [1, 1, 1]


def test_mutate_column_named_sum_overrides_helper():
    # Lib Issue 7
    df = pd.DataFrame({"sum": [1, 2], "x": [10, 20]})
    res = df.pt.mutate(y="if_else(x > 15, sum, 0)")
    assert list(res["y"]) == [0, 2]


def test_mutate_map_preserves_explicit_null():
    # Lib Issue 11
    df = pd.DataFrame({"a": ["x", "y", "z"]})
    res = pt.mutate(df, b="map(a, {'x': 1, 'y': None}, -1)")
    assert res["b"].iloc[0] == 1.0
    assert pd.isna(res["b"].iloc[1])
    assert res["b"].iloc[2] == -1.0


def test_mutate_if_else_and_case_when_nullable_boolean():
    # Lib Issue 12
    df = pd.DataFrame({"a": pd.Series([1, pd.NA, 3], dtype="Int64")})
    res_if = pt.mutate(df, b="if_else(a > 2, 'y', 'n')")
    assert list(res_if["b"]) == ["n", "n", "y"]

    res_cw = pt.mutate(df, b="case_when((a > 2, 'y'), 'n')")
    assert list(res_cw["b"]) == ["n", "n", "y"]


def test_mutate_n_row_count_vs_col_and_helper():
    # Lib Issue 16: caller local 'n' does not shadow row count 'n' unless referenced as '@n'
    n = 999  # noqa: F841
    df = pd.DataFrame({"val": [10, 20, 30]})
    res = df.pt.mutate("cnt = n, caller_n = @n")
    assert list(res["cnt"]) == [3, 3, 3]
    assert list(res["caller_n"]) == [999, 999, 999]


def test_mutate_grouped_callable_sees_original_index():
    # Lib Issue 17: callable sees original index in grouped mutate
    s = pd.Series([100, 200, 300], index=[10, 20, 30])
    df = pd.DataFrame({"g": ["a", "b", "a"], "x": [1, 2, 3]}, index=[10, 20, 30])
    res = df.pt.by("g").pt.mutate(y=lambda d: d["x"] + s.reindex(d.index))
    assert list(res["y"]) == [101, 202, 303]
    assert list(res.index) == [10, 20, 30]


def test_mutate_scalar_if_else_and_case_when():
    # Lib Issue 1 (Review 2ec5bbba): scalar condition in if_else and case_when broadcasts across rows and groups
    df = pd.DataFrame({"val": [10, 20, 30]})
    assert df.pt.mutate(y="if_else(n > 1, 1, 0)")["y"].tolist() == [1, 1, 1]
    assert df.pt.mutate(y="case_when((n > 1, 'big'), 'small')")["y"].tolist() == ["big", "big", "big"]

    df2 = pd.DataFrame({"val": [10, 20, 30]}, index=[5, 6, 7])
    assert df2.pt.mutate(y="if_else(n > 1, 1, 0)")["y"].tolist() == [1, 1, 1]

    df3 = pd.DataFrame({"g": ["a", "a", "b"], "val": [10, 20, 30]})
    assert df3.pt.by("g").pt.mutate(y="if_else(n > 1, 1, 0)")["y"].tolist() == [1, 1, 0]


def test_mutate_lit_constant_when_column_exists():
    df = pd.DataFrame({"original": [10, 20], "val": [1, 2]})

    # Without inner quotes, passing source="original" copies the column
    assert list(df.pt.mutate(source="original")["source"]) == [10, 20]

    # With inner quotes source="'original'", assigns literal string
    res_quoted = df.pt.mutate(source="'original'")
    assert list(res_quoted["source"]) == ["original", "original"]

    # Positional string expression with inner quotes
    res_pos = df.pt.mutate("source = 'original'")
    assert list(res_pos["source"]) == ["original", "original"]

    # Grouped mutation with quoted literal
    res_grp = df.pt.by("val").pt.mutate(source="'original'")
    assert list(res_grp["source"]) == ["original", "original"]

    res_grp_str = df.pt.by("val").pt.mutate("source = 'original'")
    assert list(res_grp_str["source"]) == ["original", "original"]

    # Native Python non-string literals (int, float, bool)
    res_num = df.pt.mutate(source=42, flag=True)
    assert list(res_num["source"]) == [42, 42]
    assert list(res_num["flag"]) == [True, True]

    # Calling pt.lit() raises AttributeError pointing to quoted syntax
    with pytest.raises(AttributeError, match="pt.lit\\(\\) has been removed"):
        pt.lit("original")


def test_mutate_grouped_vectorized_all_stats():
    df = pd.DataFrame(
        {
            "grp": ["a", "a", "a", "b", "b"],
            "val": [10.0, 20.0, 30.0, 100.0, 200.0],
            "name": ["alice", "bob", "charlie", "dave", "eve"],
        }
    )
    res = df.pt.by("grp").pt.mutate(
        "avg = mean(val), tot = sum(val), med = median(val), "
        "lo = min(val), hi = max(val), sd = std(val), vr = var(val), "
        "cnt = n, cnt_fn = n(), upper_name = name.str.upper()"
    )
    assert list(res["avg"]) == [20.0, 20.0, 20.0, 150.0, 150.0]
    assert list(res["tot"]) == [60.0, 60.0, 60.0, 300.0, 300.0]
    assert list(res["med"]) == [20.0, 20.0, 20.0, 150.0, 150.0]
    assert list(res["lo"]) == [10.0, 10.0, 10.0, 100.0, 100.0]
    assert list(res["hi"]) == [30.0, 30.0, 30.0, 200.0, 200.0]
    assert list(res["cnt"]) == [3, 3, 3, 2, 2]
    assert list(res["cnt_fn"]) == [3, 3, 3, 2, 2]
    assert list(res["upper_name"]) == ["ALICE", "BOB", "CHARLIE", "DAVE", "EVE"]


def test_mutate_grouped_fallback_series_method():
    # Expressions calling custom Series methods like .cumsum() fall back to per-group evaluation
    df = pd.DataFrame({"grp": ["a", "a", "b", "b"], "val": [1, 2, 10, 20]})
    res = df.pt.by("grp").pt.mutate("cs = val.cumsum()")
    assert list(res["cs"]) == [1, 3, 10, 30]


def test_mutate_multi_col_in_place_and_chaining():
    df = pd.DataFrame({"rev": [100.0, 200.0], "cost": [40.0, 80.0], "tax": [10.0, 20.0]})
    res = df.pt.mutate("(rev, cost, tax) = _ * 1.5, profit = rev - cost - tax")
    assert list(res["rev"]) == [150.0, 300.0]
    assert list(res["cost"]) == [60.0, 120.0]
    assert list(res["tax"]) == [15.0, 30.0]
    assert list(res["profit"]) == [75.0, 150.0]


def test_mutate_multi_col_suffix_and_prefix():
    df = pd.DataFrame({"rev": [100.0, 200.0], "cost": [50.0, 100.0]})
    res_suf = df.pt.mutate("(rev, cost)_usd = _ * 1.08")
    assert list(res_suf["rev"]) == [100.0, 200.0]
    assert list(res_suf["rev_usd"]) == [pytest.approx(108.0), pytest.approx(216.0)]
    assert list(res_suf["cost_usd"]) == [pytest.approx(54.0), pytest.approx(108.0)]

    res_pre = df.pt.mutate("norm_(rev, cost) = _ / max(_)")
    assert list(res_pre["norm_rev"]) == [0.5, 1.0]
    assert list(res_pre["norm_cost"]) == [0.5, 1.0]


def test_mutate_multi_col_selectors_and_grouped():
    df = pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Gentoo", "Gentoo"],
            "bill_length_mm": [30.0, 50.0, 40.0, 60.0],
            "bill_depth_mm": [10.0, 20.0, 15.0, 25.0],
        }
    )
    res_sw = df.pt.mutate("(startswith=bill_) = _ / 10")
    assert list(res_sw["bill_length_mm"]) == [3.0, 5.0, 4.0, 6.0]
    assert list(res_sw["bill_depth_mm"]) == [1.0, 2.0, 1.5, 2.5]

    # Grouped dtype=numeric selector (automatically excludes grouping columns)
    res_grp = df.pt.by("species").pt.mutate("(dtype=numeric) = _ - mean(_)")
    assert list(res_grp["bill_length_mm"]) == [-10.0, 10.0, -10.0, 10.0]
    assert list(res_grp["bill_depth_mm"]) == [-5.0, 5.0, -5.0, 5.0]


def test_mutate_multi_col_spaced_columns():
    df = pd.DataFrame({"col a": [10, 20], "col b": [30, 40]})
    res = df.pt.mutate("([col a], [col b]) = _ + 5")
    assert list(res["col a"]) == [15, 25]
    assert list(res["col b"]) == [35, 45]


def test_mutate_map_with_spaced_columns():
    df = pd.DataFrame({"island name": ["Biscoe", "Dream", "Torgersen"]})
    res = df.pt.mutate("[island code] = map([island name], {'Biscoe': 'BIS', 'Dream': 'DRM'}, 'TOR')")
    assert list(res["island code"]) == ["BIS", "DRM", "TOR"]


def test_mutate_disallow_dot_map_method_syntax():
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island name": ["Biscoe", "Dream"]})
    with pytest.raises(ValueError, match="'.map\\(\\)' method syntax is not supported"):
        df.pt.mutate("code = species.map({'Adelie': 'AD'})")

    with pytest.raises(ValueError, match="'.map\\(\\)' method syntax is not supported"):
        df.pt.mutate("[code] = [island name].map({'Biscoe': 'BIS'})")


def test_mutate_map_column_and_expr_defaults():
    df = pt.DataFrame(
        {
            "species": ["Adelie", "Gentoo", "Chinstrap"],
            "alt_name": ["Penguin A", "Penguin G", "Penguin C"],
        }
    )
    # 1. Fallback to column itself (preserves unmapped values)
    r1 = df.mutate(mapped="map(species, {'Adelie': 'AD'}, species)")
    assert list(r1["mapped"]) == ["AD", "Gentoo", "Chinstrap"]

    # 2. 2-argument map (unmapped values become null)
    r2 = df.mutate(mapped="map(species, {'Adelie': 'AD'})")
    assert list(r2["mapped"]) == ["AD", None, None]

    # 3. Fallback to another column
    r3 = df.mutate(mapped="map(species, {'Adelie': 'AD'}, alt_name)")
    assert list(r3["mapped"]) == ["AD", "Penguin G", "Penguin C"]

    # 4. Keyword default=...
    r4 = df.mutate(mapped="map(species, {'Adelie': 'AD'}, default=species)")
    assert list(r4["mapped"]) == ["AD", "Gentoo", "Chinstrap"]


def test_mutate_smart_fillna_and_fill_null_fill_nan():
    df = pt.DataFrame(
        {
            "flt": [1.0, float("nan"), None],
            "str_col": ["alpha", None, "gamma"],
        }
    )

    # 1. fillna(col, val) -> fills both NaN and null by default (nans=True)
    r1 = df.mutate(clean="fillna(flt, 0.0)")
    assert list(r1["clean"]) == [1.0, 0.0, 0.0]

    # 2. fillna(col, val, nans=False) -> fills null only, leaves NaN intact
    r2 = df.mutate(clean="fillna(flt, 0.0, nans=False)")
    assert r2["clean"][0] == 1.0 and str(r2["clean"][1]) == "nan" and r2["clean"][2] == 0.0

    # 3. fill_null(col, val) -> strict null filling
    r3 = df.mutate(clean="fill_null(flt, 0.0)")
    assert r3["clean"][0] == 1.0 and str(r3["clean"][1]) == "nan" and r3["clean"][2] == 0.0

    # 4. fill_nan(col, val) -> strict NaN filling
    r4 = df.mutate(clean="fill_nan(flt, 0.0)")
    assert r4["clean"][0] == 1.0 and r4["clean"][1] == 0.0 and r4["clean"][2] is None

    # 5. Method syntax col.fillna(0.0)
    r5 = df.mutate(clean="flt.fillna(0.0)")
    assert list(r5["clean"]) == [1.0, 0.0, 0.0]

    # 6. fillna on string column (safely fills null without is_nan error)
    r6 = df.mutate(clean="fillna(str_col, 'MISSING')")
    assert list(r6["clean"]) == ["alpha", "MISSING", "gamma"]

    # 7. Method syntax str_col.fill_null('MISSING')
    r7 = df.mutate(clean="str_col.fill_null('MISSING')")
    assert list(r7["clean"]) == ["alpha", "MISSING", "gamma"]


def test_handle_missing_cleans_float_nans():
    df = pt.DataFrame(
        {
            "flt": [10.0, float("nan"), None, 30.0],
        }
    )
    # numeric_fill=0 fills both NaN and null
    cleaned = df.handle_missing(numeric_fill=0)
    assert list(cleaned["flt"]) == [10.0, 0.0, 0.0, 30.0]

    # numeric_fill="mean" computes mean ignoring NaNs and nulls (mean of 10 and 30 is 20)
    cleaned_mean = df.handle_missing(numeric_fill="mean")
    assert list(cleaned_mean["flt"]) == [10.0, 20.0, 20.0, 30.0]


def test_mutate_interleaved_callable_and_string_expression():
    df = pt.DataFrame({"x": [1, 2, 3]})
    # String expression 'b' references column 'a' created by callable in the same mutate call
    res = df.mutate(a=lambda d: d["x"] * 2, b="a + 10")
    assert list(res["a"]) == [2, 4, 6]
    assert list(res["b"]) == [12, 14, 16]


def test_mutate_interleaved_string_callable_string():
    df = pt.DataFrame({"x": [1, 2, 3]})
    # String 'a', Callable 'b' using 'a', String 'c' using 'b'
    res = df.mutate("a = x * 2", b=lambda d: d["a"] + 5, c="b * 10")
    assert list(res["a"]) == [2, 4, 6]
    assert list(res["b"]) == [7, 9, 11]
    assert list(res["c"]) == [70, 90, 110]


def test_mutate_grouped_interleaved_callable_and_string():
    df = pt.DataFrame({"grp": ["k", "k", "m"], "x": [1, 2, 3]})
    # Grouped mutate: callable 'a' then string 'b' referencing 'a'
    res = df.by("grp").mutate(a=lambda g: g["x"] * 2, b="a + 10")
    assert list(res["a"]) == [2, 4, 6]
    assert list(res["b"]) == [12, 14, 16]


def test_mutate_consecutive_callables_consuming_each_other():
    df = pt.DataFrame({"x": [1, 2, 3]})
    # One callable consuming another callable's output
    res = df.mutate(
        a=lambda d: d["x"] + 1,
        b=lambda d: d["a"] * 2,
        c=lambda d: d["b"] + 100,
    )
    assert list(res["a"]) == [2, 3, 4]
    assert list(res["b"]) == [4, 6, 8]
    assert list(res["c"]) == [104, 106, 108]


def test_mutate_grouped_consecutive_callables_consuming_each_other():
    df = pt.DataFrame({"grp": ["A", "A", "B"], "x": [1, 2, 10]})
    # Grouped callables consuming each other sequentially
    res = df.by("grp").mutate(
        a=lambda g: g["x"] + 1,
        b=lambda g: g["a"] * 2,
        c=lambda g: g["b"] + 100,
    )
    assert list(res["a"]) == [2, 3, 11]
    assert list(res["b"]) == [4, 6, 22]
    assert list(res["c"]) == [104, 106, 122]


def test_mutate_str_methods_and_null_checks_case_when():
    df = pt.DataFrame({
        "deal_identifier": ["D1", "D2", "D3", "D4"],
        "tranche_id": ["D1", "T2-COL-9", "T3", "T4"],
        "collateral_class": [None, None, "AAA", None],
    })
    res = df.mutate(
        tranche_type="""
        case_when(
            (deal_identifier == tranche_id, 'Main Tranche'),
            (tranche_id.str.contains('-COL-') | collateral_class.is_not_null(), 'Collateral'),
            'Guarantor'
        )
        """
    )
    assert list(res["tranche_type"]) == ["Main Tranche", "Collateral", "Collateral", "Guarantor"]

    # Also test functional is_not_null and starts_with / ends_with
    res2 = df.mutate(
        is_col=lambda d: d["tranche_id"].str.contains("-COL-"),
        has_col=df.mutate("has_col = is_not_null(collateral_class)")["has_col"],
        prefix="tranche_id.str.startswith('T2')",
        suffix="tranche_id.str.endswith('9')",
    )
    assert list(res2["prefix"]) == [False, True, False, False]
    assert list(res2["suffix"]) == [False, True, False, False]


def test_mutate_custom_function_in_expression_two_tier():
    import numpy as np

    def classify_deal(deal_id: str, tr_id: str, col_class: str | None) -> str:
        if deal_id == tr_id:
            return "Main Tranche"
        if "-COL-" in tr_id or col_class is not None:
            return "Collateral"
        return "Guarantor"

    def calc_metric(x, y):
        return x * 2.5 + np.maximum(y, 0)

    def clean_code(s):
        return s.strip().lower()

    df = pt.DataFrame({
        "deal_identifier": ["D1", "D2", "D3", "D4"],
        "tranche_id": ["D1", "T2-COL-9", "T3", "T4"],
        "collateral_class": [None, None, "AAA", None],
        "a": [1.0, 2.0, 3.0, 4.0],
        "b": [10.0, -5.0, 20.0, -1.0],
    })

    # Tier 2 scalar multi-column & Tier 1 vectorized multi-column in same mutate
    res = df.mutate(
        tranche_type="classify_deal(deal_identifier, tranche_id, collateral_class)",
        metric="calc_metric(a, b)",
        max_ab="np.maximum(a, b)",
    )
    assert list(res["tranche_type"]) == ["Main Tranche", "Collateral", "Collateral", "Guarantor"]
    assert list(res["metric"]) == [12.5, 5.0, 27.5, 10.0]
    assert list(res["max_ab"]) == [10.0, 2.0, 20.0, 4.0]

    # Across multi-column syntax with custom function
    res_across = df.mutate("(deal_identifier, tranche_id) = clean_code(_)")
    assert list(res_across["deal_identifier"]) == ["d1", "d2", "d3", "d4"]
    assert list(res_across["tranche_id"]) == ["d1", "t2-col-9", "t3", "t4"]

    # LazyFrame support
    res_lazy = df.lazy().mutate(tranche_type="classify_deal(deal_identifier, tranche_id, collateral_class)").collect()
    assert list(res_lazy["tranche_type"]) == ["Main Tranche", "Collateral", "Collateral", "Guarantor"]




