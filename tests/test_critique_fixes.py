"""Tests covering fixes for the 5 production critique issues:
1. Column-to-column comparison in filter() without silent footgun
2. map() boolean safety and mixed-type guard
3. DataFrame constructor with list-of-dicts
4. Unbracketed special-character column names (parentheses, etc.) in filter & mutate
5. Dynamic column resolution via col(@var) and col('name')
"""

from __future__ import annotations

import polars as pl
import pytest

import pytae as pt

# =============================================================================
# Issue 3: DataFrame Constructor with list of dicts
# =============================================================================


def test_dataframe_constructor_list_of_dicts():
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    df = pt.DataFrame(data)
    assert isinstance(df, pt.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["a", "b"]
    assert list(df["a"]) == [1, 3]
    assert list(df["b"]) == [2, 4]


def test_dataframe_constructor_single_dict_in_list():
    df = pt([{"x": 10, "y": 20}])
    assert isinstance(df, pt.DataFrame)
    assert len(df) == 1
    assert list(df.columns) == ["x", "y"]
    assert df["x"][0] == 10


# =============================================================================
# Issue 1: Filter Column-to-Column Comparison & Typo Safety
# =============================================================================


def test_filter_column_to_column_equality():
    df = pt.DataFrame(
        {
            "tranche_id": ["T1", "T2", "T3", "T4"],
            "deal_id": ["T1", "D2", "T3", "D4"],
        }
    )
    res = df.filter("tranche_id == deal_id")
    assert len(res) == 2
    assert list(res["tranche_id"]) == ["T1", "T3"]


def test_filter_column_to_column_inequality_and_ordering():
    df = pt.DataFrame(
        {
            "amount": [100, 200, 300, 400],
            "limit": [150, 150, 350, 350],
        }
    )
    # Greater than
    gt = df.filter("amount > limit")
    assert len(gt) == 2
    assert list(gt["amount"]) == [200, 400]

    # Less than or equal
    lte = df.filter("amount <= limit")
    assert len(lte) == 2
    assert list(lte["amount"]) == [100, 300]

    # Not equal
    neq = df.filter("amount != limit")
    assert len(neq) == 4


def test_filter_unquoted_non_column_raises_keyerror():
    df = pt.DataFrame({"species": ["Adelie", "Gentoo", "Chinstrap"]})
    with pytest.raises(KeyError) as exc_info:
        df.filter("species == Gentoo")
    msg = str(exc_info.value)
    assert "column 'Gentoo' not found in DataFrame" in msg
    assert "quote it like 'Gentoo'" in msg


def test_filter_quoted_scalar_still_matches():
    df = pt.DataFrame({"species": ["Adelie", "Gentoo", "Chinstrap"]})
    res = df.filter("species == 'Gentoo'")
    assert len(res) == 1
    assert res["species"][0] == "Gentoo"


def test_filter_with_at_var_scalar():
    df = pt.DataFrame({"amount": [10, 50, 100, 200]})
    threshold = 50  # noqa: F841
    res = df.filter("amount > @threshold")
    assert len(res) == 2
    assert list(res["amount"]) == [100, 200]


def test_filter_with_at_var_column_via_col():
    df = pt.DataFrame(
        {
            "tranche_id": ["T1", "T2", "T3"],
            "deal_id": ["T1", "X2", "T3"],
        }
    )
    target = "deal_id"  # noqa: F841
    res = df.filter("tranche_id == col(@target)")
    assert len(res) == 2
    assert list(res["tranche_id"]) == ["T1", "T3"]


# =============================================================================
# Issue 2: map() Boolean Safety & Mixed-Type Guards
# =============================================================================


def test_map_returns_boolean_series():
    df = pt.DataFrame({"code": ["2B", "3C", "4D"]})
    res = df.mutate("flag = map(code, {'2B': False, '3C': True}, default=False)")
    assert res["flag"].dtype == pl.Boolean
    assert list(res["flag"]) == [False, True, False]


def test_map_boolean_without_default_fills_nulls():
    df = pt.DataFrame({"code": ["2B", "3C", "4D"]})
    res = df.mutate("flag = map(code, {'2B': False, '3C': True})")
    assert res["flag"].dtype == pl.Boolean
    assert res["flag"][0] is False
    assert res["flag"][1] is True
    assert res["flag"][2] is None


def test_map_mixed_mapping_values_raises_typeerror():
    df = pt.DataFrame({"code": ["2B", "3C"]})
    with pytest.raises(TypeError) as exc_info:
        df.mutate("flag = map(code, {'2B': 'SC', '3C': False})")
    assert "cannot mix boolean and non-boolean" in str(exc_info.value)


def test_map_string_values_with_boolean_default_raises_typeerror():
    df = pt.DataFrame({"code": ["2B", "3C"]})
    with pytest.raises(TypeError) as exc_info:
        df.mutate("flag = map(code, {'2B': 'SC'}, default=False)")
    assert "cannot mix non-boolean mapping values with boolean default" in str(exc_info.value)


def test_map_boolean_values_with_string_default_raises_typeerror():
    df = pt.DataFrame({"code": ["2B", "3C"]})
    with pytest.raises(TypeError) as exc_info:
        df.mutate("flag = map(code, {'2B': False}, default='SC')")
    assert "cannot mix boolean mapping values with non-boolean default" in str(exc_info.value)


def test_map_normal_strings_and_numbers_preserved():
    df = pt.DataFrame({"code": ["2B", "3C", "9Z"]})
    res = df.mutate(
        "s_code = map(code, {'2B': 'Senior', '3C': 'Mezz'}, default='Junior')",
        "n_code = map(code, {'2B': 1, '3C': 2}, default=0)",
    )
    assert list(res["s_code"]) == ["Senior", "Mezz", "Junior"]
    assert list(res["n_code"]) == [1, 2, 0]


# =============================================================================
# Issue 4: Special Characters in Column Names
# =============================================================================


def test_special_column_names_in_mutate():
    df = pt.DataFrame({"irba_unsecured_lgd_(1g00)": [0.2, 0.7, 0.4]})
    res = df.mutate("scaled = irba_unsecured_lgd_(1g00) * 100")
    assert list(res["scaled"]) == [20.0, 70.0, 40.0]


def test_special_column_names_in_filter():
    df = pt.DataFrame({"irba_unsecured_lgd_(1g00)": [0.2, 0.7, 0.4]})
    res = df.filter("irba_unsecured_lgd_(1g00) > 0.5")
    assert len(res) == 1
    assert res["irba_unsecured_lgd_(1g00)"][0] == 0.7


def test_multiple_special_columns_in_complex_mutate():
    df = pt.DataFrame(
        {
            "irba_unsecured_lgd_(1g00)": [0.2, 0.7, 0.4],
            "post_crm_lgd_(2a)": [0.1, 0.9, 0.3],
        }
    )
    res = df.mutate(
        "diff = irba_unsecured_lgd_(1g00) - post_crm_lgd_(2a)",
        "chosen = if_else(irba_unsecured_lgd_(1g00) > 0.5, post_crm_lgd_(2a), 0.0)",
    )
    assert len(res) == 3
    assert list(res["chosen"]) == [0.0, 0.9, 0.0]


# =============================================================================
# Issue 5: Dynamic Column Resolution via col(...)
# =============================================================================


def test_col_dynamic_variable_in_mutate():
    df = pt.DataFrame({"sales_2023": [10, 20], "sales_2024": [30, 40]})
    target = "sales_2024"  # noqa: F841
    res = df.mutate("growth = col(@target) * 1.1")
    assert [round(x, 1) for x in res["growth"]] == [33.0, 44.0]


def test_col_literal_string_in_mutate():
    df = pt.DataFrame({"sales": [100, 200]})
    res = df.mutate("out = col('sales') / 2")
    assert list(res["out"]) == [50.0, 100.0]


def test_col_bare_name_in_mutate():
    df = pt.DataFrame({"sales": [100, 200]})
    res = df.mutate("out = col(sales) / 2")
    assert list(res["out"]) == [50.0, 100.0]


def test_col_with_unknown_name_raises_keyerror_with_hint():
    df = pt.DataFrame({"revenue": [100, 200]})
    with pytest.raises(KeyError) as exc_info:
        df.mutate("out = col('revenu') * 2")
    msg = str(exc_info.value)
    assert "column 'revenu' not found in DataFrame" in msg
    assert "did you mean 'revenue'?" in msg
