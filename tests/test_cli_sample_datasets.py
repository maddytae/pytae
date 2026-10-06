"""Integration tests against pytae's bundled real datasets (pytae.sample_data).

Unlike the tiny hand-crafted frames in test_cli_order.py (kept deliberately
minimal for exact, easy-to-verify assertions), these exercise the CLI against
real, messier data: multiple categories, real NaNs, larger row counts. This is
also where docs/cli.md's "Sample datasets" section examples are regression
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


# Mirrors docs/cli.md's "Sample datasets" section — keep in sync with those examples.
_DOC_EXAMPLES = [
    ("penguins.parquet", ["-qry", "species = 'Adelie'", "-by", "species", "-agg", "mean"]),
    ("penguins.parquet", ["-pivot", "r=species,c=island,v=sex,a=n"]),
    ("tips.parquet", ["-select", "day,total_bill,tip", "-by", "day", "-mutate", "avg_tip = mean(tip)"]),
    ("titanic.parquet", ["-freq", "survived"]),
    ("diamonds.parquet", ["-select", "cut,price", "-by", "cut", "-agg", "mean"]),
    ("mpg.parquet", ["-select", "origin,mpg", "-arrange", "mpg desc", "-head", "5"]),
    ("flights.parquet", ["-wide", "c=month,v=passengers,r=year", "-head", "5"]),
]


@pytest.mark.parametrize("filename, extra_args", _DOC_EXAMPLES)
def test_docs_sample_dataset_examples_run_cleanly(sample_dataset_dir, filename, extra_args, capsys):
    exit_code = cli.main([str(sample_dataset_dir / filename), *extra_args])
    assert exit_code == 0, capsys.readouterr().err


def test_pivot_a_n_counts_on_real_penguins(sample_parquet, capsys):
    path = sample_parquet("penguins")

    exit_code = cli.main([path, "-pivot", "r=species,c=island,v=sex,a=n"])
    assert exit_code == 0
    wide_out = capsys.readouterr().out

    def _row(line):
        return [int(tok) for tok in line.split()[1:]]

    wide_rows = {line.split()[0]: _row(line) for line in wide_out.strip().splitlines()[1:]}
    assert wide_rows["Adelie"] == [44, 56, 52]
    assert wide_rows["Chinstrap"] == [0, 68, 0]
    assert wide_rows["Gentoo"] == [124, 0, 0]


def test_wide_pure_reshape_on_real_flights(sample_parquet, capsys):
    path = sample_parquet("flights")

    exit_code = cli.main([path, "-wide", "c=month,v=passengers,r=year", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols[0] == "year"
    assert "Jan" in cols
    assert "Dec" in cols


def test_agg_groups_by_diamonds_cut_categories(sample_parquet, capsys):
    path = sample_parquet("diamonds")

    exit_code = cli.main([path, "-select", "cut,price", "-by", "cut", "-agg", "mean", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip() == "(5, 2)"  # 5 known cut categories: Fair/Good/Very Good/Premium/Ideal


def test_group_by_agg_sum_matches_known_flights_totals(sample_parquet, capsys):
    path = sample_parquet("flights")

    exit_code = cli.main([
        path, "-by", "year", "-agg", "passengers = sum", "-head", "3",
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
