import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_mutate_then_select_new_column(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"body_mass_g": [3000.0, 4000.0], "bill_length_mm": [30.0, 40.0]}),
    )

    exit_code = cli.main(
        [path, "-mutate", "bmi = body_mass_g / bill_length_mm ** 2", "-select", "bmi", "-shape"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"


def test_mutate_multiple_entries_and_chained_reference(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000.0, 4000.0]}))

    cli.main(
        [path, "-mutate", "mass_kg = body_mass_g / 1000, mass_lb = mass_kg * 2.20462",
         "-select", "mass_kg,mass_lb", "-head"]
    )
    out = capsys.readouterr().out
    assert "mass_kg" in out and "mass_lb" in out


def test_mutate_key_quoting_is_optional(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000.0, 4000.0]}))

    cli.main([path, "-mutate", "mass_kg = body_mass_g / 1000", "-select", "mass_kg", "-shape"])
    unquoted = capsys.readouterr().out.strip()

    cli.main([path, "-mutate", "'mass_kg' = body_mass_g / 1000", "-select", "mass_kg", "-shape"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted == "(2, 1)"


def test_mutate_unknown_column_reference_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000.0, 4000.0]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-mutate", "bmi = bod_mass_g / 1000", "-shape"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "-mutate" in err
    assert "body_mass_g" in err


def test_mutate_at_local_var_gives_cli_specific_error(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"n": [5, 15]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-mutate", "heavy = n >= @threshold"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "-mutate" in err
    assert "library-only" in err


def test_mutate_at_inside_quoted_string_is_not_flagged_as_local_var(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"s": ["a@b", "c"]}))

    exit_code = cli.main([path, "-mutate", "flag = s == 'a@b'"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "True" in out
    assert "False" in out


def test_mutate_load_from_file_cli(tmp_path, capsys):
    data_path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000.0, 4000.0]}))
    spec_path = tmp_path / "specs.txt"
    spec_path.write_text("mass_kg = body_mass_g / 1000\n# comment\nmass_lb = mass_kg * 2.2\n")

    exit_code = cli.main([data_path, "-mutate", f"@{spec_path}", "-select", "mass_kg,mass_lb", "-head"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "mass_kg" in out and "mass_lb" in out


def test_mutate_bracketed_column_names_cli(tmp_path, capsys):
    data_path = _write_csv(tmp_path, pd.DataFrame({"col a": [10, 20], "col b": [1, 2]}))

    exit_code = cli.main([data_path, "-mutate", "total = [col a] + [col b]", "-select", "total", "-head"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "11" in out and "22" in out


def test_mutate_coalesce_cli(tmp_path, capsys):
    data_path = _write_csv(tmp_path, pd.DataFrame({"a": [1.0, None], "b": [None, 2.0]}))

    exit_code = cli.main([data_path, "-mutate", "c = coalesce(a, b, 0.0)", "-select", "c", "-head"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "1.0" in out and "2.0" in out


def test_mutate_colon_raises_cli_error(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"body_mass_g": [3000.0, 4000.0]}))
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-mutate", "bmi: body_mass_g / 1000"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "use '='" in err
