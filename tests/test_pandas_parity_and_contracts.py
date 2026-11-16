"""Test suite validating Pandas parity, behavioral translations, and Pytae safety contracts.

Pytae Core Contracts:
1. Zero Data Loss: Bare dropna() drops only 100% blank rows; by() + agg() preserves NA groups.
2. Pure Flat 1D DataFrames: Clean RangeIndex(0, 1, 2, ...); no MultiIndex row indices or column tuples.
3. Single-Shot Grouping: by(*cols) applies strictly to the next verb and automatically resets.
4. One Canonical Verb: filter, mutate, select, arrange, by, agg, count, distinct, long, wide, join.
"""

from __future__ import annotations

import pandas as pd
import pytest

import pytae as pt
from pytae import c

# ==============================================================================
# 1. Zero Data Loss & Missing Data Safety Contracts
# ==============================================================================


def test_pandas_groupby_zero_data_loss_contract():
    """Pandas groupby() silently drops NaN group keys by default (dropna=True).

    Pytae's contract: analytical verbs (by, agg, count, pivot) default to Zero Data Loss
    (dropna=False), preserving missing/null groups explicitly.
    """
    pdf = pd.DataFrame({
        "category": ["A", "A", None, "B", None],
        "sales": [10, 20, 30, 40, 50],
    })

    # Pandas default drops null groups: only A (30) and B (40) survive (80 lost!)
    pandas_grouped = pdf.groupby("category")["sales"].sum()
    assert len(pandas_grouped) == 2
    assert pandas_grouped.sum() == 70

    # Pytae contract: null group is preserved; total is 100% accounted for (150)
    ptdf = pt.DataFrame(pdf)
    res = ptdf.by("category").agg(total="sales:sum")
    p_res = res.to("pandas")

    assert len(p_res) == 3
    assert p_res["total"].sum() == 150
    # Null category row exists with total 80 (30 + 50)
    null_row = p_res[p_res["category"].isna()]
    assert len(null_row) == 1
    assert null_row["total"].iloc[0] == 80


def test_pandas_dropna_all_vs_any_contract():
    """Pandas dropna() defaults to how='any', deleting rows with even a single missing column.

    Pytae's contract: bare dropna() drops ONLY 100% blank rows (how='all').
    Passing column names drops rows missing any of those required columns.
    """
    pdf = pd.DataFrame({
        "id": [1, 2, 3, None],
        "name": ["Alice", "Bob", None, None],
        "optional_note": [None, "VIP", None, None],
    })

    # Pandas dropna() removes rows 0, 2, and 3 because optional_note/name is None:
    # only row 1 survives!
    pandas_dropped = pdf.dropna()
    assert len(pandas_dropped) == 1
    assert list(pandas_dropped["id"]) == [2.0]

    # Pytae contract: bare dropna() drops ONLY row 3 (completely blank)
    ptdf = pt.DataFrame(pdf)
    res_bare = ptdf.dropna()
    assert len(res_bare) == 3
    assert list(res_bare["id"][:3]) == [1.0, 2.0, 3.0]

    # Passing required columns targets those keys specifically (how='any' for specified keys)
    res_targeted = ptdf.dropna("id", "name")
    assert len(res_targeted) == 2
    assert list(res_targeted["id"]) == [1.0, 2.0]


def test_pandas_fillna_parity():
    """Test scalar fill, dictionary column mapping, and keyword fills."""
    pdf = pd.DataFrame({
        "num": [1.0, None, 3.0],
        "str_col": ["a", None, "c"],
    })
    ptdf = pt.DataFrame(pdf)

    # Scalar fill across all columns
    res_scalar = ptdf.fillna(0)
    assert res_scalar["num"][1] == 0.0

    # Column mapping fill
    res_mapping = ptdf.fillna(num=99.0, str_col="missing")
    assert res_mapping["num"][1] == 99.0
    assert res_mapping["str_col"][1] == "missing"


# ==============================================================================
# 2. Index Hierarchy vs Flat 1D DataFrames Contracts
# ==============================================================================


def test_pandas_pure_flat_1d_dataframe_contract():
    """Pandas creates hierarchical MultiIndex row indices and column tuples.

    Pytae's contract: DataFrames are always flat 2D tables with clean RangeIndex
    and simple 1D string column headers, eliminating index resets and tuple flattening.
    """
    pdf = pd.DataFrame({
        "dept": ["Eng", "Eng", "Sales", "Sales"],
        "role": ["Dev", "QA", "Rep", "Lead"],
        "salary": [120, 95, 80, 110],
        "bonus": [15, 10, 20, 25],
    })

    # In Pandas, multi-metric multi-grouping yields nested MultiIndex:
    # row index: [('Eng', 'Dev'), ...], col index: [('salary', 'mean'), ('bonus', 'max')]
    # In Pytae:
    ptdf = pt.DataFrame(pdf)
    res = ptdf.by("dept", "role").agg(
        avg_salary="salary:mean",
        max_bonus="bonus:max",
    )
    p_res = res.to("pandas")

    # Row index must be flat RangeIndex
    assert isinstance(p_res.index, pd.RangeIndex)
    assert list(p_res.index) == [0, 1, 2, 3]

    # Column index must be flat strings
    assert list(p_res.columns) == ["dept", "role", "avg_salary", "max_bonus"]
    assert all(isinstance(c, str) for c in p_res.columns)


def test_pandas_single_shot_grouping_reset_contract():
    """Pandas groupby() creates a sticky DataFrameGroupBy object.

    Pytae's contract: by(*cols) applies only to the immediate next operation,
    then automatically resets back to whole-table ungrouped context without ungroup().
    """
    pdf = pd.DataFrame({
        "dept": ["Eng", "Eng", "Sales", "Sales"],
        "salary": [100.0, 150.0, 80.0, 120.0],
    })
    ptdf = pt.DataFrame(pdf)

    # Calculate dept average, then global average, then dept max in ONE chain
    res = (
        ptdf
        .by("dept").mutate(dept_avg=c.salary.mean())
        .mutate(global_avg=c.salary.mean())
        .by("dept").mutate(dept_max=c.salary.max())
    )
    p_res = res.to("pandas")

    assert list(p_res["dept_avg"]) == [125.0, 125.0, 100.0, 100.0]
    assert list(p_res["global_avg"]) == [112.5, 112.5, 112.5, 112.5]
    assert list(p_res["dept_max"]) == [150.0, 150.0, 120.0, 120.0]


# ==============================================================================
# 3. Filtering Parity
# ==============================================================================


def test_pandas_filtering_parity():
    """Test filtering parity with Pandas boolean masks, between, isin, and strings."""
    pdf = pd.DataFrame({
        "name": ["Alice Smith", "Bob Jones", "Charlie Brown", "David Smith"],
        "age": [25, 32, 45, 52],
        "score": [85.5, 92.0, 78.0, 65.0],
        "status": ["active", "pending", "active", "suspended"],
    })
    ptdf = pt.DataFrame(pdf)

    # 1. Compound boolean logic: age > 30 and (score > 80 or status == 'active')
    f1 = ptdf.filter((c.age > 30) & ((c.score > 80) | (c.status == "active")))
    assert list(f1["name"]) == ["Bob Jones", "Charlie Brown"]

    # 2. Interval / between parity (df['age'].between(30, 50))
    f2 = ptdf.filter({"age": ("between", 30, 50)})
    assert list(f2["name"]) == ["Bob Jones", "Charlie Brown"]

    # 3. Set membership parity (df['status'].isin(['active', 'pending']))
    f3 = ptdf.filter(c.status.is_in(["active", "pending"]))
    assert len(f3) == 3
    assert "David Smith" not in list(f3["name"])

    # 4. String startswith and contains
    f4 = ptdf.filter(c.name.str.starts_with("A"))
    assert list(f4["name"]) == ["Alice Smith"]

    f5 = ptdf.filter(c.name.str.contains("Smith"))
    assert list(f5["name"]) == ["Alice Smith", "David Smith"]

    # 5. Lambda predicate
    f6 = ptdf.filter(lambda d: d["score"] > 80)
    assert len(f6) == 2


# ==============================================================================
# 4. Feature Engineering (`mutate`) Parity
# ==============================================================================


def test_pandas_mutate_feature_engineering_parity():
    """Test column derivations parity with Pandas assign, np.where, np.select, and window funcs."""
    pdf = pd.DataFrame({
        "dept": ["HR", "HR", "IT", "IT"],
        "score": [70, 85, 92, 60],
        "val": [10, 20, 30, 40],
    })
    ptdf = pt.DataFrame(pdf)

    # Sequential derivations in a single call (where step 2 uses step 1)
    res1 = ptdf.mutate(doubled=c.val * 2, quadrupled=c.doubled * 2)
    assert list(res1["quadrupled"]) == [40, 80, 120, 160]

    # Conditional logic: if_else parity with np.where
    res2 = ptdf.mutate(passed=pt.if_else(c.score >= 75, "yes", "no"))
    assert list(res2["passed"]) == ["no", "yes", "yes", "no"]

    # Multi-branch logic: case_when parity with np.select
    res3 = ptdf.mutate(
        grade=pt.case_when(
            (c.score >= 90, "A"),
            (c.score >= 80, "B"),
            (c.score >= 70, "C"),
            default="F",
        )
    )
    assert list(res3["grade"]) == ["C", "B", "A", "F"]

    # Cumulative operations: cumsum parity
    res4 = ptdf.mutate(running_total=c.val.cumsum())
    assert list(res4["running_total"]) == [10, 30, 60, 100]

    # Grouped window lag (shift)
    res5 = ptdf.by("dept").mutate(prev_val=c.val.shift(1))
    p_res5 = res5.to("pandas")
    assert pd.isna(p_res5["prev_val"][0])
    assert p_res5["prev_val"][1] == 10
    assert pd.isna(p_res5["prev_val"][2])
    assert p_res5["prev_val"][3] == 30


# ==============================================================================
# 5. Column Selection & Renaming Parity
# ==============================================================================


def test_pandas_select_and_rename_parity():
    """Test column projection, pattern-based selection, and renaming."""
    pdf = pd.DataFrame({
        "cust_id": [1, 2],
        "cust_name": ["Alice", "Bob"],
        "order_amt": [100, 200],
        "order_date": ["2026-01-01", "2026-01-02"],
    })
    ptdf = pt.DataFrame(pdf)

    # Drop columns via negation (~c.col)
    res_drop = ptdf.select(~c.cust_id, ~c.order_date)
    assert list(res_drop.columns) == ["cust_name", "order_amt"]

    # Pattern match (contains)
    res_contains = ptdf.select(contains="order")
    assert list(res_contains.columns) == ["order_amt", "order_date"]

    # Prefix match (starts_with)
    res_prefix = ptdf.select(starts_with="cust")
    assert list(res_prefix.columns) == ["cust_id", "cust_name"]

    # Slicing columns (c.start.to(c.end))
    res_slice = ptdf.select(c.cust_name.to(c.order_amt))
    assert list(res_slice.columns) == ["cust_name", "order_amt"]

    # Dedicated rename
    res_rename = ptdf.rename("cust_id:id", "order_amt:amount")
    assert "id" in res_rename.columns
    assert "amount" in res_rename.columns


# ==============================================================================
# 6. Sorting & Extremes (`arrange`, `head`, `tail`) Parity
# ==============================================================================


def test_pandas_sorting_and_extremes_parity():
    """Test multi-column sorting and nlargest/nsmallest parity."""
    pdf = pd.DataFrame({
        "dept": ["B", "A", "B", "A"],
        "score": [10, 30, 20, 30],
        "emp": ["D4", "D1", "D3", "D2"],
    })
    ptdf = pt.DataFrame(pdf)

    # Multi-column sorting: dept asc, score desc
    res_sorted = ptdf.arrange(c.dept, c.score.desc())
    assert list(res_sorted["emp"]) == ["D1", "D2", "D3", "D4"]

    # Top N overall (nlargest)
    top2 = ptdf.arrange(c.score.desc()).head(2)
    assert len(top2) == 2
    assert set(top2["emp"]) == {"D1", "D2"}

    # Top N per group
    top_per_dept = ptdf.by("dept").arrange(c.score.desc()).head(1)
    p_top = top_per_dept.to("pandas")
    assert len(p_top) == 2
    assert set(p_top["emp"]) == {"D1", "D3"}


# ==============================================================================
# 7. Deduplication (`distinct`) Parity
# ==============================================================================


def test_pandas_deduplication_distinct_parity():
    """Test deduplication across table and subset columns with keep options."""
    pdf = pd.DataFrame({
        "k": ["A", "A", "B", "A"],
        "v": [1, 2, 3, 1],
    })
    ptdf = pt.DataFrame(pdf)

    # Full row deduplication
    assert len(ptdf.distinct()) == 3

    # Subset deduplication: keep first
    res_first = ptdf.distinct("k", keep="first")
    assert list(res_first["v"]) == [1, 3]

    # Subset deduplication: keep last
    res_last = ptdf.distinct("k", keep="last")
    assert list(res_last["v"]) == [3, 1]

    # Subset deduplication: drop all duplicates (keep='none')
    res_none = ptdf.distinct("k", keep="none")
    assert list(res_none["k"]) == ["B"]


# ==============================================================================
# 8. Reshaping (`long`, `wide`, `pivot`) Parity
# ==============================================================================


def test_pandas_reshaping_long_wide_pivot_parity():
    """Test melt (long), spread (wide), and 2D pivot table parity."""
    pdf = pd.DataFrame({
        "id": [1, 2],
        "q1": [100, 200],
        "q2": [150, 250],
    })
    ptdf = pt.DataFrame(pdf)

    # Melt wide to long
    long_df = ptdf.long(id_vars="id", cols=["q1", "q2"])
    assert len(long_df) == 4
    assert set(long_df.columns) == {"id", "variable", "value"}

    # Pivot long back to wide
    wide_df = long_df.wide(r="id", c="variable", v="value")
    assert list(wide_df["id"]) == [1, 2]
    assert list(wide_df["q1"]) == [100, 200]
    assert list(wide_df["q2"]) == [150, 250]

    # 2D Contingency Matrix Pivot
    sales = pt.DataFrame({
        "dept": ["Eng", "Eng", "Sales", "Sales"],
        "year": [2025, 2026, 2025, 2026],
        "amount": [10, 15, 20, 25],
    })
    piv = sales.pivot(r="dept", c="year", v="amount", a="sum")
    assert "2025" in piv.columns or 2025 in piv.columns
    assert len(piv) == 2


# ==============================================================================
# 9. Relational Joins & Concat Parity
# ==============================================================================


def test_pandas_relational_joins_and_concat_parity():
    """Test inner, left, outer joins, key mappings, and vertical stacking."""
    df1 = pt.DataFrame({"user_id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})
    df2 = pt.DataFrame({"id": [1, 2, 4], "dept": ["Eng", "HR", "Sales"]})

    # Inner join with key mapping
    j_inner = df1.join(df2, on="user_id:id", how="inner")
    assert len(j_inner) == 2
    assert set(j_inner["name"]) == {"Alice", "Bob"}

    # Left join with key mapping
    j_left = df1.join(df2, on="user_id:id", how="left")
    assert len(j_left) == 3
    assert "Charlie" in list(j_left["name"])

    # Cardinality check
    with pytest.raises(Exception):
        dup_df2 = pt.DataFrame({"id": [1, 1], "dept": ["Eng1", "Eng2"]})
        df1.join(dup_df2, on="user_id:id", validate="1:1")

    # Vertical concatenation
    s1 = pt.DataFrame({"a": [1, 2], "b": [10, 20]})
    s2 = pt.DataFrame({"a": [3, 4], "b": [30, 40]})
    stacked = s1.concat(s2)
    assert len(stacked) == 4
    assert list(stacked["a"]) == [1, 2, 3, 4]


# ==============================================================================
# 10. Pandas .pt Accessor Parity
# ==============================================================================


def test_pandas_accessor_pt_seamless_operations():
    """Verify that pd.DataFrame.pt accessor exposes the full Pytae verb suite."""
    pdf = pd.DataFrame({
        "dept": ["IT", "IT", "HR"],
        "salary": [100, 120, 90],
    })

    # Fluent pipeline on raw pandas DataFrame via .pt accessor
    res = (
        pdf.pt
        .filter(c.salary >= 95)
        .by("dept")
        .agg(avg_sal="salary:mean")
        .arrange(c.avg_sal.desc())
    )
    p_res = res.to("pandas")
    assert len(p_res) == 1
    assert p_res["dept"].iloc[0] == "IT"
    assert p_res["avg_sal"].iloc[0] == 110.0
