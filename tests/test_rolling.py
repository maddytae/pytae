"""Unit tests for native rolling window functions in Pytae mutate."""

from __future__ import annotations

import pytest

import pytae as pt
from pytae import c


def test_rolling_mean_and_sum() -> None:
    df = pt.DataFrame({
        "x": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    res = df.mutate(
        rm=c.x.rolling_mean(2),
        rs=c.x.rolling_sum(2),
    )
    assert res["rm"].to_list() == [None, 15.0, 25.0, 35.0, 45.0]
    assert res["rs"].to_list() == [None, 30.0, 50.0, 70.0, 90.0]


def test_rolling_min_max_std_median() -> None:
    df = pt.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    res = df.mutate(
        r_min=c.x.rolling_min(3),
        r_max=c.x.rolling_max(3),
        r_std=c.x.rolling_std(3),
        r_med=c.x.rolling_median(3),
    )
    assert res["r_min"].to_list() == [None, None, 1.0, 2.0, 3.0]
    assert res["r_max"].to_list() == [None, None, 3.0, 4.0, 5.0]
    assert res["r_std"].to_list() == [None, None, 1.0, 1.0, 1.0]
    assert res["r_med"].to_list() == [None, None, 2.0, 3.0, 4.0]


def test_rolling_min_periods() -> None:
    df = pt.DataFrame({
        "x": [1.0, 2.0, 3.0],
    })
    res = df.mutate(
        rm=c.x.rolling_mean(2, min_periods=1),
    )
    assert res["rm"].to_list() == [1.0, 1.5, 2.5]


def test_grouped_rolling_window() -> None:
    df = pt.DataFrame({
        "group": ["A", "A", "A", "B", "B", "B"],
        "val": [10.0, 20.0, 30.0, 100.0, 200.0, 300.0],
    })
    res = df.by("group").mutate(
        rm=c.val.rolling_mean(2),
        rs=c.val.rolling_sum(2),
    )
    assert res["rm"].to_list() == [None, 15.0, 25.0, None, 150.0, 250.0]
    assert res["rs"].to_list() == [None, 30.0, 50.0, None, 300.0, 500.0]


def test_rolling_invalid_window() -> None:
    df = pt.DataFrame({"x": [1, 2, 3]})
    with pytest.raises(Exception):
        df.mutate(rm=c.x.rolling_mean(0))

    # Passing string formula raises TypeError
    with pytest.raises(TypeError, match="retired"):
        df.mutate(rm="rolling_mean(x, 2)")
