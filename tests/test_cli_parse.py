import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))



def test_parse_sort_by_trailing_direction():
    from pytae.cli_parsing import parse_sort_by
    assert parse_sort_by("val") == (["val"], "asc")
    assert parse_sort_by("val desc") == (["val"], "desc")
    assert parse_sort_by("species,body_mass_g desc") == (["species", "body_mass_g"], "desc")
    assert parse_sort_by("bill length mm desc") == (["bill length mm"], "desc")


def test_expand_paths_single_and_list(tmp_path):
    import pytest

    from pytae.cli_parsing import expand_paths

    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_text("a,b\n1,2\n")
    f2.write_text("a,b\n3,4\n")

    assert expand_paths(str(f1)) == [f1]
    assert expand_paths([str(f1), str(f2)]) == [f1, f2]
    assert expand_paths(str(tmp_path / "*.csv")) == [f1, f2]
    assert expand_paths([str(f1), str(f1), str(f2)]) == [f1, f2]

    with pytest.raises(SystemExit) as exc_info:
        expand_paths(str(tmp_path / "*.parquet"))
    assert "no files matched pattern" in str(exc_info.value)


def test_parse_rename_conflicting_mappings():
    import pytest

    from pytae.cli_parsing import parse_rename

    assert parse_rename("old:new, other:target") == {"old": "new", "other": "target"}
    with pytest.raises(SystemExit) as exc_info:
        parse_rename("col:new1, col:new2")
    assert "conflicting mappings for 'col'" in str(exc_info.value)


def test_cli_keyword_help(capsys):
    from pytae.cli import main

    # test `pytae -help sql`
    code = main(["-help", "sql"])
    assert code == 0
    out = capsys.readouterr().out
    assert "PYTAE CLI KEYWORD HELP: -sql" in out
    assert "FLAG:     -sql, --sql QUERY" in out
    assert "select species" in out

    # test `pytae -h mutate`
    code = main(["-h", "mutate"])
    assert code == 0
    out = capsys.readouterr().out
    assert "PYTAE CLI KEYWORD HELP: -mutate" in out
    assert "mass_kg = body_mass_g / 1000" in out

    # test unknown keyword fallback
    code = main(["-help", "nonexistent_keyword"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No dedicated help topic for keyword 'nonexistent_keyword'" in out
    assert "Available keywords with help:" in out



