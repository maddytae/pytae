# Changelog

## 3.12.8

- Support and documentation for custom persistent REPL session directories (`PYTAE_SESSIONS_DIR`).
- Enhanced REPL session commands and reference documentation.

## 3.12.7

- Sequential `-by` grouping in CLI with single-shot zero-pollution scoping.
- Top N per group chained pipeline recipes.
- Microsoft Copilot Studio RAG knowledge base & agent instructions.
- Shell quoting standards and Twin Proof grounding protocol.

## 3.12.6

- REPL non-destructive preview by default (`-filter`, `-head`, `-distinct`) and explicit mutation via assignment.
- CLI output parity in REPL (formatted table display matching CLI).
- Resolved `-distinct` followed by `-head` active row truncation.
- Table-specific reset (`reset <table_name>`) and exploratory `-sample` preview.
- Windows 64-bit RAM trimming (`EmptyWorkingSet`) and memory-map tuning.
- Standalone zero-Python executable distributions for Linux, macOS, and Windows.

## 3.12.5

- Disk-backed session checkpoints (Arrow IPC, 0 RAM overhead).
- Automatic milestone undo baseline reset on `checkpoint <name>` freeing intermediate RAM.
- Strict RAM isolation and post-checkpoint table purging on `restore <name>`.
- Immediate memory reclamation on `rm` with decoupled disk checkpoints.

## 3.12.4

- Fixed lazy pipeline preservation in `-plot`, `-describe`, and `-diff` when combined with `-filter`, `-mutate`, or `-select`.
- Enforced strict canonical `clear` and wildcard deletion (`rm *`, `rm checkpoint *`).
- Preserved CLI reader options (`-encoding`, `-dlim`, `-nrows`) when launching REPL with `-i`.

## 3.12.3

- Standardized README documentation links to absolute repository URLs for seamless navigation on PyPI.

## 3.12.2

- Session-wide REPL checkpoints preserving entire multi-table workbench state and inline reader options (`-encoding`, `-dlim`, `-nrows`).

## 3.12.1

- Automatic sample dataset resolution for bundled datasets and refined REPL prompt state indicators.

## 3.12.0

- Added syntax support and snippets for Interactive REPL Shell (`pt.repl()`, `df.repl()`) and single-dash CLI flag standardization.

## 3.11.0

- Added support and syntax highlighting for sensitive data masking, encryption, and tokenization (`mask`, `unmask`).

## 3.10.5

- Enhanced CSV/TXT reader schema inference and resilient format conversion.

## 3.10.4

- Updated syntax highlighting and snippets for unified method-token standard in `filter` (`is_null()`, `is_not_null()`, `is_nan()`, `is_not_nan()`).

## 3.10.3

- Initial release of the Pytae Visual Studio Code extension.
- Added TextMate grammar injection for Python files (`source.python`).
- Highlighting for `.mutate()`, `.filter()`, `.select()`, `.arrange()`, `.agg()`, and `.by()` string expressions.
- Support for tagged strings with `# pytae` comment header.
- Added 9 productive snippets (`pt-mutate`, `pt-case-when`, `pt-validate`, etc.).

