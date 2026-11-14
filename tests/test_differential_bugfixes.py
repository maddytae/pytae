import pytest
import polars as pl
import pandas as pd
import pytae as pt


def test_mutate_count_col_counts_non_nulls():
    df = pt.DataFrame(pl.DataFrame({
        "g": [1, 1, 1, 2, 2],
        "x": [10.0, None, 30.0, None, None]
    }))
    # Whole-table count(x) vs count()
    res = df.mutate(cnt_x="count(x)", cnt_all="count()")
    assert res._df["cnt_x"].to_list() == [2, 2, 2, 2, 2]
    assert res._df["cnt_all"].to_list() == [5, 5, 5, 5, 5]

    # Grouped count(x) vs count()
    res_g = df.by("g").mutate(cnt_x="count(x)", cnt_all="count()")
    assert res_g._df["cnt_x"].to_list() == [2, 2, 2, 0, 0]
    assert res_g._df["cnt_all"].to_list() == [3, 3, 3, 2, 2]


def test_mutate_cumulative_funcs():
    df = pt.DataFrame(pl.DataFrame({"y": [1, 2, 3, 4]}))
    res = df.mutate(
        cs="cumsum(y)",
        cs2="cum_sum(y)",
        cm="cummax(y)",
        cmn="cummin(y)"
    )
    assert res._df["cs"].to_list() == [1, 3, 6, 10]
    assert res._df["cs2"].to_list() == [1, 3, 6, 10]
    assert res._df["cm"].to_list() == [1, 2, 3, 4]
    assert res._df["cmn"].to_list() == [1, 1, 1, 1]


def test_filter_unary_not_and_negation():
    df = pt.DataFrame(pl.DataFrame({"x": [-2, 0, 1, 3, 5]}))
    assert df.filter("not (x > 1)")._df["x"].to_list() == [-2, 0, 1]
    assert df.filter("not x > 1")._df["x"].to_list() == [-2, 0, 1]

    # ~ and ! are retired in filter in favor of 'not'
    with pytest.raises(ValueError, match="'~' is not supported in filter.*use 'not'"):
        df.filter("~(x > 1)")
    with pytest.raises(ValueError, match="'!' is not supported in filter.*use 'not'"):
        df.filter("!(x > 1)")
    with pytest.raises(ValueError, match="'!' is not supported in filter.*use 'not'"):
        df.filter("!x > 1")


def test_filter_arithmetic_lhs():
    df = pt.DataFrame(pl.DataFrame({"x": [1, 2, 3, 4, 5], "y": [-10, 0, 10, 20, 30]}))
    assert df.filter("x * 2 > 4")._df["x"].to_list() == [3, 4, 5]
    assert df.filter("x % 2 == 0")._df["x"].to_list() == [2, 4]
    assert df.filter("-y < -10")._df["y"].to_list() == [20, 30]
    assert df.filter("x ** 2 > 9")._df["x"].to_list() == [4, 5]


def test_filter_chained_comparison():
    df = pt.DataFrame(pl.DataFrame({"y": [-2, 0, 1, 3, 5, 8]}))
    assert df.filter("0 < y < 5")._df["y"].to_list() == [1, 3]
    assert df.filter("0 <= y <= 5")._df["y"].to_list() == [0, 1, 3, 5]


def test_filter_bare_boolean_column():
    df = pt.DataFrame(pl.DataFrame({"id": [1, 2, 3], "is_active": [True, False, True]}))
    assert df.filter("is_active")._df["id"].to_list() == [1, 3]
    assert df.filter("not is_active")._df["id"].to_list() == [2]


def test_filter_string_methods_unprefixed():
    df = pt.DataFrame(pl.DataFrame({"s": ["apple", "banana", "apricot", "cherry"]}))
    assert df.filter("s.starts_with('ap')")._df["s"].to_list() == ["apple", "apricot"]
    assert df.filter("s.contains('an')")._df["s"].to_list() == ["banana"]
    with pytest.raises(ValueError, match="'startswith\\(\\)' is retired in favor of canonical 'starts_with\\(\\)'"):
        df.filter("s.startswith('ap')")


def test_mutate_negative_powers():
    df = pt.DataFrame(pl.DataFrame({"y": [-2, -1, 1, 2]}))
    res = df.mutate(p1="y ** -1", p2="2 ** y")
    assert res._df["p1"].to_list() == [-0.5, -1.0, 1.0, 0.5]
    assert res._df["p2"].to_list() == [0.25, 0.5, 2.0, 4.0]


def test_select_starts_with_and_ends_with_aliases():
    df = pt.DataFrame(pl.DataFrame({"bill_len": [1], "bill_depth": [2], "mass_g": [3]}))
    # Method kwarg
    assert df.select(starts_with="bill").columns.tolist() == ["bill_len", "bill_depth"]
    assert df.select(ends_with="_g").columns.tolist() == ["mass_g"]
    with pytest.raises(ValueError, match="select\\(\\): 'startswith' is retired in favor of canonical 'starts_with'"):
        df.select(startswith="bill")
    with pytest.raises(ValueError, match="select\\(\\): 'endswith' is retired in favor of canonical 'ends_with'"):
        df.select(endswith="_g")

    # Functional pt.select
    assert pt.select(df, starts_with="bill").columns.tolist() == ["bill_len", "bill_depth"]
    assert pt.select(df, ends_with="_g").columns.tolist() == ["mass_g"]
    with pytest.raises(ValueError, match="select\\(\\): 'startswith' is retired in favor of canonical 'starts_with'"):
        pt.select(df, startswith="bill")

    # String expressions in filter
    df_str = pt.DataFrame(pl.DataFrame({"name": ["alice", "bob", "albert"]}))
    assert df_str.filter("name.starts_with('al')")._df["name"].to_list() == ["alice", "albert"]
    assert df_str.filter("name.ends_with('rt')")._df["name"].to_list() == ["albert"]
    with pytest.raises(ValueError, match="'startswith\\(\\)' is retired in favor of canonical 'starts_with\\(\\)'"):
        df_str.filter("name.startswith('al')")
    with pytest.raises(ValueError, match="'endswith\\(\\)' is retired in favor of canonical 'ends_with\\(\\)'"):
        df_str.filter("name.endswith('rt')")

    # Mutate multi-column syntax
    res1 = df.mutate("(starts_with=bill) = _ * 10")
    assert res1._df["bill_len"].to_list() == [10]
    with pytest.raises(ValueError, match="mutate: multi-column selector 'startswith=' is retired in favor of canonical 'starts_with='"):
        df.mutate("(startswith=bill) = _ * 10")


def test_mutate_n_removed_in_favor_of_count():
    # 1. n() raises ValueError pointing to canonical count()
    df = pt.DataFrame(pl.DataFrame({"x": [10, 20, 30]}))
    with pytest.raises(ValueError, match="n\\(\\) is not supported in expressions.*canonical 'count\\(\\)'"):
        df.mutate("cnt = n()")

    # 2. Bare n when no column n exists raises KeyError pointing to count()
    with pytest.raises(KeyError, match="column 'n' not found in DataFrame.*use canonical 'count\\(\\)'"):
        df.mutate("cnt = n")

    # 3. Bare n when column n exists correctly accesses column n
    df_with_n = pt.DataFrame(pl.DataFrame({"n": [1, 2, 3], "val": [10, 20, 30]}))
    res = df_with_n.mutate("doubled = n * 2")
    assert res._df["doubled"].to_list() == [2, 4, 6]

    # 4. Canonical count() works ungrouped and grouped
    res_cnt = df.mutate("cnt = count()")
    assert res_cnt._df["cnt"].to_list() == [3, 3, 3]

