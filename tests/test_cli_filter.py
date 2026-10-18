import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_query_deprecated_raises_helpful_error(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main([path, "-qry", "flt == 'A'"])
    assert exc.value.code == 2
    assert "'-qry' has been removed; use '-filter' instead" in capsys.readouterr().err


def test_filter_without_braces_is_equivalent(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main([path, "-filter", "'flt' = 'A'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 3)"


def test_filter_column_key_quoting_is_optional(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    cli.main([path, "-filter", "flt='A'", "-shape"])
    unquoted = capsys.readouterr().out.strip()

    cli.main([path, "-filter", "'flt'='A'", "-shape"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted == "(2, 3)"


def test_filter_unquoted_string_value_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"flt": ["A", "B"]}))

    with pytest.raises(SystemExit, match="must be quoted"):
        cli.main([path, "-filter", "flt=A", "-shape"])


def test_filter_column_not_in_select_still_filters(tmp_path, capsys):
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
            "-filter",
            "flt = 'A'",
            "-select",
            "'keep','val'",
            "-shape",
        ]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(2, 2)" in out


def test_filter_clip_copies_filtered_frame_without_output_op(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"month": [202606, 202607, 202607], "value": [1, 2, 3]}))

    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["frame"] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    exit_code = cli.main([path, "-filter", "month = 202607", "-o", "clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    pd.testing.assert_frame_equal(
        copied["frame"].reset_index(drop=True),
        pd.DataFrame({"month": [202607, 202607], "value": [2, 3]}),
    )


def test_filter_direct_comparison(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000, 4000, 5000]}))

    exit_code = cli.main([path, "-filter", "body_mass_g > 3500", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"


def test_filter_colon_raises_error(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000, 4000, 5000]}))

    with pytest.raises(SystemExit, match="use '='"):
        cli.main([path, "-filter", "body_mass_g: > 3500", "-shape"])


def test_filter_equals_separator(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000, 4000, 5000]}))

    # col= > val
    exit_code = cli.main([path, "-filter", "body_mass_g= > 3500", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"

    # col=>val
    exit_code = cli.main([path, "-filter", "body_mass_g=>3500", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"

    # col = > val
    exit_code = cli.main([path, "-filter", "body_mass_g = > 3500", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"

    # col = val
    exit_code = cli.main([path, "-filter", "body_mass_g = 4000", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 1)"


def test_filter_cli_bracket_interval(tmp_path, capsys):
    # CLI Issue 3: -qry "body_mass_g = [3000, 3200]" treats as interval
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000, 3100, 3200, 4000]}))
    exit_code = cli.main([path, "-filter", "body_mass_g = [3000, 3200]", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 1)"


def test_filter_cli_str_methods_and_null_checks(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame(
            {
                "species": ["Adelie", "Gentoo", "Chinstrap"],
                "island": ["Torgersen", "Biscoe", "Dream"],
                "sex": ["MALE", None, "FEMALE"],
            }
        ),
    )

    # -filter "island.str.contains('org')"
    exit_code = cli.main([path, "-filter", "island.str.contains('org')", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 3)"

    # -filter "species.str.starts_with('Gen')"
    exit_code = cli.main([path, "-filter", "species.str.starts_with('Gen')", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 3)"

    # -filter "sex.is_not_null()"
    exit_code = cli.main([path, "-filter", "sex.is_not_null()", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 3)"


def test_filter_cli_notna_spaced_column(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame(
            {
                "bill length mm": [39.1, None, 40.5, None, 45.2],
                "body mass g": [3750, 3800, None, 4000, 4200],
            }
        ),
    )

    # 1. Bracket notation [bill length mm].notna()
    exit_code = cli.main([path, "-filter", "[bill length mm].notna()", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"

    # 2. SQL style [bill length mm] is not null
    exit_code = cli.main([path, "-filter", "[bill length mm] is not null", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"

    # 3. Functional notna([bill length mm])
    exit_code = cli.main([path, "-filter", "notna([bill length mm])", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"

    # 4. Inequality [bill length mm] != None
    exit_code = cli.main([path, "-filter", "[bill length mm] != None", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"


def test_filter_string_column_unquoted_number_fails(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"id": ["1", "9", "a"], "val": [10, 20, 30]}),
    )

    # Bare equality with unquoted int
    with pytest.raises(SystemExit):
        cli.main([path, "-filter", "id = 9"])
    assert "column 'id' has String type" in capsys.readouterr().err

    # Double equality with unquoted int
    with pytest.raises(SystemExit):
        cli.main([path, "-filter", "id == 9"])
    assert "column 'id' has String type" in capsys.readouterr().err

    # Inequality with unquoted int (prevents lexicographical bugs)
    with pytest.raises(SystemExit):
        cli.main([path, "-filter", "id > 9"])
    assert "column 'id' has String type" in capsys.readouterr().err


def test_filter_string_column_quoted_number_succeeds(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"id": ["1", "9", "a"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main([path, "-filter", "id = '9'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 2)"

    exit_code = cli.main([path, "-filter", "id == '9'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 2)"


def test_filter_unquoted_comparison_word_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"species": ["Adelie", "Gentoo"]}))

    with pytest.raises(SystemExit, match="must be quoted"):
        cli.main([path, "-filter", "species == Adelie", "-shape"])


