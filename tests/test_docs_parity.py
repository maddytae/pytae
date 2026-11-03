"""Automated documentation parity and freshness tests.

Guarantees that:
1. Every CLI flag registered in build_parser() is documented in KEYWORD_DOCS.
2. Every KeywordHelp entry has complete syntax, options, and descriptions.
3. In-terminal help (pytae -help <flag>) provides exact cards for known flags
   and automatically falls back to full-text documentation search for concepts/synonyms.
4. Reference artifacts (Copilot manuals, instructions, and FTS5 search index)
   are present, populated, and fully synchronized.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pytae.cli import build_parser
from pytae.cli_help import KEYWORD_ALIASES, KEYWORD_DOCS, get_keyword_help

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_flags_parity_with_keyword_docs() -> None:
    """Every CLI option in build_parser() must be covered by KEYWORD_DOCS or KEYWORD_ALIASES."""
    parser = build_parser()
    ignored_system_flags = {"h", "help", "version", "cheatsheet"}

    missing_flags: list[list[str]] = []
    for action in parser._actions:
        names = [opt.lstrip("-") for opt in action.option_strings if opt.lstrip("-")]
        if not names:
            continue
        # Skip standard system flags
        if any(name in ignored_system_flags for name in names):
            continue

        # Verify either the primary name or an alias resolves to a KEYWORD_DOCS entry
        is_covered = any(
            name in KEYWORD_DOCS or KEYWORD_ALIASES.get(name) in KEYWORD_DOCS
            for name in names
        )
        if not is_covered:
            missing_flags.append(names)

    assert not missing_flags, (
        f"The following CLI flags are missing documentation in KEYWORD_DOCS (src/pytae/cli_help.py): "
        f"{missing_flags}. Please add KeywordHelp entries or KEYWORD_ALIASES for them."
    )


def test_keyword_docs_attributes() -> None:
    """Every KeywordHelp entry in KEYWORD_DOCS must be complete and well-formed."""
    for key, doc in KEYWORD_DOCS.items():
        assert doc.name, f"Entry '{key}' missing name"
        assert doc.flag, f"Entry '{key}' missing flag"
        assert doc.syntax, f"Entry '{key}' missing syntax"
        assert doc.summary, f"Entry '{key}' missing summary"
        assert doc.description, f"Entry '{key}' missing description"
        assert len(doc.examples) > 0, f"Entry '{key}' must provide at least one runnable example"
        for ex in doc.examples:
            assert ex.startswith("pytae ") or ex.startswith("cat "), (
                f"Example '{ex}' in entry '{key}' must begin with 'pytae ' or 'cat '"
            )


def test_help_unified_routing() -> None:
    """pytae -help <flag> returns exact card; free-text queries fall back to doc search."""
    # 1. Exact flag lookup
    diff_help = get_keyword_help("diff")
    assert "PYTAE CLI KEYWORD HELP: -diff" in diff_help
    assert "on=key" in diff_help
    assert "-tol" in diff_help

    # 2. Leading hyphen stripped cleanly
    opts_help = get_keyword_help("-opts")
    assert "PYTAE CLI KEYWORD HELP: -opts" in opts_help
    assert "sheet=" in opts_help

    # 3. Known alias lookup
    limit_help = get_keyword_help("limit")
    assert "PYTAE CLI KEYWORD HELP: -nrows" in limit_help

    # 4. Synonym / conceptual query falls back to FTS5 search
    unnest_help = get_keyword_help("unnest")
    assert "No exact flag match for 'unnest'" in unnest_help
    assert "explode" in unnest_help.lower()

    # 5. Composite search query
    phrase_help = get_keyword_help("diff on key")
    assert "diff" in phrase_help.lower()

    # 6. Completely unknown nonsense query gives helpful suggestions without crashing
    unknown_help = get_keyword_help("xyz_completely_unknown_12345")
    assert "No dedicated help topic for keyword" in unknown_help
    assert "pytae -doc <phrase>" in unknown_help

    # 7. Checkpoint, convert, and session keyword help
    cp_help = get_keyword_help("checkpoint")
    assert "convert = all" in cp_help
    assert "checkpoint_format" in cp_help

    convert_help = get_keyword_help("convert")
    assert "convert = all" in convert_help
    assert "checkpoint_format" in convert_help

    session_help = get_keyword_help("session")
    assert "session save" in session_help
    assert "status session" in session_help


def test_bare_subcommands_retired(capsys: pytest.CaptureFixture[str]) -> None:
    """Bare subcommands (doc, mcp, check, repl) are retired with clear redirect errors."""
    import pytest

    from pytae.cli import main

    with pytest.raises(SystemExit):
        main(["doc", "explode"])
    err = capsys.readouterr().err
    assert "'pytae doc' has been retired; use 'pytae -doc'" in err

    with pytest.raises(SystemExit):
        main(["mcp"])
    err = capsys.readouterr().err
    assert "'pytae mcp' has been retired; use 'pytae -mcp'" in err

    with pytest.raises(SystemExit):
        main(["check"])
    err = capsys.readouterr().err
    assert "'pytae check' has been retired; use 'pytae -check'" in err

    with pytest.raises(SystemExit):
        main(["repl"])
    err = capsys.readouterr().err
    assert "'pytae repl' has been retired; use 'pytae -i'" in err


def test_reference_artifacts_exist_and_non_empty() -> None:
    """Verify generated Copilot reference manuals and SQLite FTS search DB are valid."""
    ref_dir = REPO_ROOT / "reference"
    assert ref_dir.exists(), "reference/ directory must exist"

    # Copilot reference text manual
    copilot_ref_txt = ref_dir / "pytae_copilot_reference.txt"
    assert copilot_ref_txt.exists(), "reference/pytae_copilot_reference.txt must exist"
    lines = copilot_ref_txt.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 5000, f"Copilot reference manual is unexpectedly truncated ({len(lines)} lines)"

    # Copilot instructions prompt card
    copilot_instr_txt = ref_dir / "pytae_copilot_instructions.txt"
    assert copilot_instr_txt.exists(), "reference/pytae_copilot_instructions.txt must exist"
    instr_text = copilot_instr_txt.read_text(encoding="utf-8")
    assert "CRITICAL SYNTAX & USAGE RULES" in instr_text
    assert "-opts" in instr_text
    assert "-file" in instr_text  # Mentions deprecation of -file
    assert len(instr_text) <= 8000, f"Instructions card exceeds Copilot Studio 8000 char limit ({len(instr_text)} chars)"

    # SQLite FTS5 search database
    db_path = ref_dir / "pytae_docs.db"
    assert db_path.exists(), "reference/pytae_docs.db must exist"
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("SELECT count(*) FROM docs_fts;")
        count = cur.fetchone()[0]
        assert count > 30, f"Expected >30 indexed doc chunks in docs_fts, got {count}"
    finally:
        conn.close()

