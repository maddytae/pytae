"""Integration tests against pytae's bundled real datasets (pytae.sample_data).

Unlike the tiny hand-crafted frames in test_cli_order.py (kept deliberately
minimal for exact, easy-to-verify assertions), these exercise the CLI against
real, messier data: multiple categories, real NaNs, larger row counts. This is
also where docs/CLI.md's "Sample datasets" section examples are regression
tested, so a broken documented command fails CI instead of only being caught
by manually re-running the docs.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli

_SAMPLE_DATASET_NAMES = ("penguins", "tips", "titanic", "diamonds", "mpg", "flights")


@pytest.fixture(scope="module")
def sample_dataset_dir(tmp_path_factory):
    """Write every bundled sample dataset to parquet once, shared across this module's tests."""
    import pytae
    directory = tmp_path_factory.mktemp("sample_datasets")
    for name in _SAMPLE_DATASET_NAMES:
        pytae.sample_data[name].to_parquet(directory / f"{name}.parquet")
    return directory


# Mirrors docs/CLI.md's "Sample datasets" section — keep in sync with those examples.
_DOC_EXAMPLES = [
    ("penguins.parquet", ["-qry", "'species': 'Adelie'", "-agg_df", "mean"]),
    ("penguins.parquet", ["-crosstab", "index='species',columns='island'"]),
    ("tips.parquet", ["-select", "day,total_bill,tip", "-group_x", "group='day',v='tip',a='mean'"]),
    ("titanic.parquet", ["-crosstab", "index='pclass',columns='survived',margins=true"]),
    ("diamonds.parquet", ["-select", "cut,price", "-agg_df", "mean"]),
    ("mpg.parquet", ["-select", "origin,mpg", "-sort_by", "mpg", "desc", "-head", "5"]),
    ("flights.parquet", ["-group_by", "year", "-agg", "column='passengers',aggfunc='sum'"]),
]


@pytest.mark.parametrize("filename, extra_args", _DOC_EXAMPLES)
def test_docs_sample_dataset_examples_run_cleanly(sample_dataset_dir, filename, extra_args, capsys):
    exit_code = cli.main([str(sample_dataset_dir / filename), *extra_args])
    assert exit_code == 0, capsys.readouterr().err


def test_crosstab_counts_match_known_penguins_distribution(sample_parquet, capsys):
    path = sample_parquet("penguins")

    exit_code = cli.main([path, "-crosstab", "index='species',columns='island'"])

    out = capsys.readouterr().out
    assert exit_code == 0
    lines = {line.split()[0]: line.split()[1:] for line in out.strip().splitlines()[2:]}
    assert lines["Adelie"] == ["44", "56", "52"]
    assert lines["Chinstrap"] == ["0", "68", "0"]
    assert lines["Gentoo"] == ["124", "0", "0"]


def test_crosstab_margins_match_known_titanic_totals(sample_parquet, capsys):
    path = sample_parquet("titanic")

    exit_code = cli.main([path, "-crosstab", "index='pclass',columns='survived',margins=true"])

    out = capsys.readouterr().out
    assert exit_code == 0
    last_line = out.strip().splitlines()[-1].split()
    assert last_line == ["All", "549", "342", "891"]


def test_agg_df_groups_by_diamonds_cut_categories(sample_parquet, capsys):
    path = sample_parquet("diamonds")

    exit_code = cli.main([path, "-select", "cut,price", "-agg_df", "mean", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip() == "(5, 2)"  # 5 known cut categories: Fair/Good/Very Good/Premium/Ideal


def test_group_by_agg_sum_matches_known_flights_totals(sample_parquet, capsys):
    path = sample_parquet("flights")

    exit_code = cli.main([
        path, "-group_by", "year", "-agg", "column='passengers',aggfunc='sum'", "-head", "3",
    ])

    out = capsys.readouterr().out
    assert exit_code == 0
    rows = [line.split() for line in out.strip().splitlines()[1:]]
    assert rows == [["1949", "1520"], ["1950", "1676"], ["1951", "2042"]]


def test_handle_missing_fills_real_titanic_nans(sample_parquet, capsys):
    # titanic has genuine NaNs in numeric (age) and object (deck) columns.
    path = sample_parquet("titanic")

    exit_code = cli.main([path, "-handle_missing", "-select", "age,deck", "-nulls"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines() == ["age     0", "deck    0"]
