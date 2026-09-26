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

    # Single string
    assert expand_paths(str(f1)) == [f1]

    # List of strings (simulating shell expansion)
    assert expand_paths([str(f1), str(f2)]) == [f1, f2]

    # Quoted glob string
    assert expand_paths(str(tmp_path / "*.csv")) == [f1, f2]

    # Deduplication
    assert expand_paths([str(f1), str(f1), str(f2)]) == [f1, f2]

    # No match error
    with pytest.raises(SystemExit) as exc_info:
        expand_paths(str(tmp_path / "*.parquet"))
    assert "no files matched pattern" in str(exc_info.value)


