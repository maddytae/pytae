"""Unit tests for Git Bash / MSYS POSIX path normalization on Windows."""

from unittest.mock import patch

from pytae.cli_parsing import normalize_git_bash_path, parse_input_target
from pytae.readers import _normalize_source


def test_normalize_git_bash_path_unquoted_nt() -> None:
    # Unquoted MSYS drive path
    raw = "/c/Users/TAF3842/downloads/final_output.parquet"
    res = normalize_git_bash_path(raw, _force_nt=True)
    assert res == "C:/Users/TAF3842/downloads/final_output.parquet"


def test_normalize_git_bash_path_quoted_with_spaces_nt() -> None:
    # Double-quoted path containing spaces
    raw = '"/c/Users/TAF3842/downloads/New folder/final_output.parquet"'
    res = normalize_git_bash_path(raw, _force_nt=True)
    assert res == '"C:/Users/TAF3842/downloads/New folder/final_output.parquet"'


def test_normalize_git_bash_path_single_quoted_nt() -> None:
    # Single-quoted path
    raw = "'/d/risk_data/deals.parquet'"
    res = normalize_git_bash_path(raw, _force_nt=True)
    assert res == "'D:/risk_data/deals.parquet'"


def test_normalize_git_bash_path_preserves_standard_paths() -> None:
    # Standard Windows paths, relative paths, and UNC paths are completely unchanged
    cases = [
        "C:/Users/TAF3842/downloads/final_output.parquet",
        r"C:\Users\TAF3842\downloads\final_output.parquet",
        "final_output.parquet",
        "./relative/path/data.csv",
        r"\\server\share\data.parquet",
        "sample:penguins",
    ]
    for case in cases:
        assert normalize_git_bash_path(case, _force_nt=True) == case


def test_normalize_git_bash_path_posix_untouched_when_not_nt() -> None:
    # On Linux/macOS (non-NT), paths are untouched
    with patch("os.name", "posix"):
        raw = "/c/Users/TAF3842/downloads/final_output.parquet"
        assert normalize_git_bash_path(raw) == raw


def test_parse_input_target_git_bash_path() -> None:
    with patch("os.name", "nt"):
        # Without alias
        target1 = parse_input_target("/c/Users/TAF3842/downloads/final_output.parquet")
        assert target1["alias"] == "final_output"
        assert target1["path"] == "C:/Users/TAF3842/downloads/final_output.parquet"

        # With alias
        target2 = parse_input_target("df=/c/Users/TAF3842/downloads/final_output.parquet")
        assert target2["alias"] == "df"
        assert target2["path"] == "C:/Users/TAF3842/downloads/final_output.parquet"

        # With quotes and spaces
        target3 = parse_input_target('out="/d/my projects/data.parquet"')
        assert target3["alias"] == "out"
        assert target3["path"] == "D:/my projects/data.parquet"


def test_reader_source_normalization() -> None:
    with patch("os.name", "nt"):
        res = _normalize_source("/c/Users/TAF3842/downloads/final_output.parquet")
        assert res == "C:/Users/TAF3842/downloads/final_output.parquet"
