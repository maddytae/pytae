import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_query_then_select_filters_like_pandas(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main(
        [path, "-query", "flt == 'A'", "-select", "keep,val", "-shape"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 2)"

def test_qry_without_braces_is_equivalent(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main([path, "-qry", "'flt': 'A'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 3)"

def test_qry_column_key_quoting_is_optional(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    cli.main([path, "-qry", "flt:'A'", "-shape"])
    unquoted = capsys.readouterr().out.strip()

    cli.main([path, "-qry", "'flt':'A'", "-shape"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted == "(2, 3)"

def test_qry_unquoted_string_value_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"flt": ["A", "B"]}))

    with pytest.raises(SystemExit, match="must be quoted"):
        cli.main([path, "-qry", "flt:A", "-shape"])

def test_qry_column_not_in_select_still_filters(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "keep": [1, 2, 3],
            "flt": ["A", "B", "A"],
            "val": [10, 20, 30],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [
            path,
            "-qry",
            "{'flt':'A'}",
            "-select",
            "'keep','val'",
            "-shape",
        ]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(2, 2)" in out

def test_qry_clip_copies_filtered_frame_without_output_op(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"month": [202606, 202607, 202607], "value": [1, 2, 3]}))

    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["frame"] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    exit_code = cli.main([path, "-qry", "{'month': 202607}", "-to_clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    pd.testing.assert_frame_equal(
        copied["frame"].reset_index(drop=True),
        pd.DataFrame({"month": [202607, 202607], "value": [2, 3]}),
    )

