# Repository Inconsistencies Report

This document details inconsistencies across Pytae's CLI, REPL, Python API (`pt.*`, `DataFrame.*`, `.pt.*` accessors), help text, documentation, configuration, and VS Code extension.

---

## 1. CLI Flag Rules vs. Help Text, Parser Messages, and Cheatsheet

### 1.1 Single-Dash Policy Violated in Cheatsheet and Help Strings
- **Rule**: `PytaeParser._check_double_dash` (`src/pytae/cli.py:271-282`) strictly forbids double-dash flags (except `--help` and `--version`), raising:
  `'<flag>' uses a double dash. Use single-dash '-<flag>' instead.`
- **Contradictions**:
  1. **`src/pytae/cheatsheet.py:58-65` & `docs/cli_cheatsheet.md:127-145`**: Every example in Section 4 (`COLUMN SELECTION (-select)`) uses `--select` with a double dash (`pytae data.parquet --select "a,b,c"`, `pytae data.parquet --select "float"`, etc.). Copy-pasting any of these commands fails immediately.
  2. **`src/pytae/cli_help.py` (all 33 `KeywordHelp` entries)**: Every topic header advertises double-dash flags alongside single-dash flags (e.g., `SYNTAX: -filter / --filter "<expr>"`, `SYNTAX: -sql / --sql "<query>"`, `SYNTAX: -select / --select "<spec>"`).
  3. **`src/pytae/cli.py` help strings**:
     - Line 653: `"Column(s) to group by before subsequent operations (excluding --sql)"`
     - Line 996: `"Save output to file ..."` (references `--output` in related docs)
     - Line 1128: `"Encryption key for -mask / -unmask. Falls back to $PYTAE_SECRET_KEY if not provided."` (while `cli_help.py:1303, 1347` advertise `--key` and `--vault`).
     - Line 1151: `"Launch interactive REPL after executing any CLI pipeline flags"` (while `cli_help.py` advertises `--repl`).

### 1.2 `-tolerance` Recommended in Help Text, Immediately Rejected by Parser
- **Contradiction**:
  - `src/pytae/cli.py:385` (epilog), `src/pytae/cli.py:821` (`-diff` help), and `src/pytae/cli_help.py:543, 547, 552, 558, 570` (`diff` help topic) instruct users to pass `-tolerance 0.01` (or `-tol / -tolerance <float>`).
  - Yet `src/pytae/cli.py:900-905` registers `-tolerance` exclusively as a trap flag that errors out with:
    `'-tolerance' is not recognized; use '-tol <threshold>' instead.`

### 1.3 Outdated `"pandas eval() syntax"` Description in `-mutate` Help
- **Location**: `src/pytae/cli.py:715`
- **Inconsistency**:
  `-mutate` help states:
  `"Compute new/modified columns via 'col = expr, ...' (pandas eval() syntax)"`
  Pytae no longer uses `pandas.eval()`; it compiles expressions via its own Polars AST compiler (`_ast_to_polars_expr` in `src/pytae/polars_engine.py`).

---

## 2. Python API Signature & Return-Type Inconsistencies

### 2.1 `long()` Parameter Mismatch (`r=` Missing from Top-Level and Accessors)
| Entrypoint | Signature | Accepts `r=`? |
|---|---|---|
| `DataFrame.long` (`src/pytae/dataframe.py:1146`) | `(self, cols=None, into="variable", val="value", *, r=None, by=None)` | Yes |
| `long_polars` (`src/pytae/polars_engine.py:1892`) | `(df, cols=None, into="variable", val="value", *, r=None, by=None)` | Yes |
| `pt.long` (`src/pytae/__init__.py:259`) | `(df, cols=None, into="variable", val="value", *, by=None)` | **No** (`TypeError`) |
| `PolarsPtAccessor.long` (`src/pytae/accessor.py:123`) | `(self, cols=None, into="variable", val="value", *, by=None)` | **No** (`TypeError`) |
| `PandasPtAccessor.long` (`src/pytae/accessor.py:364`) | `(self, cols=None, into="variable", val="value", *, by=None)` | **No** (`TypeError`) |

### 2.2 `glimpse()` Return-Type Inconsistency
| Entrypoint | Return Type |
|---|---|
| `pt.glimpse(df)` (`src/pytae/__init__.py:303`) | `pytae.DataFrame` |
| `DataFrame.glimpse()` (`src/pytae/dataframe.py:1244`) | `pytae.DataFrame` |
| `PolarsPtAccessor.glimpse()` (`src/pytae/accessor.py:153`) | `pl.DataFrame \| pl.LazyFrame` (raw Polars object) |
| `PandasPtAccessor.glimpse()` (`src/pytae/accessor.py:394`) | `pd.DataFrame` (raw Pandas object) |
| `other_utilities.glimpse(df)` (`src/pytae/other_utilities.py:235`) | Raw input `df` |

### 2.3 `clean_columns()` Signature and Implementation Divergence
- `DataFrame.clean_columns` (`src/pytae/dataframe.py:1223`) defines explicit keyword-only parameters:
  `(*, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False) -> DataFrame`
- `pt.clean_columns` (`src/pytae/__init__.py:287`), `PolarsPtAccessor.clean_columns` (`src/pytae/accessor.py:141`), and `PandasPtAccessor.clean_columns` (`src/pytae/accessor.py:382`) take untyped `(**opts: Any) -> DataFrame`, sacrificing IDE autocompletion and static type checking.
- `other_utilities.clean_columns` (`src/pytae/other_utilities.py:111`) has positional boolean parameters `(df, strip=False, strip_special=False, ...)` and only supports `pd.DataFrame` (calling `df.copy()` and assigning `out.columns = ...`).

### 2.4 `mask()` / `unmask()` Signature and Return-Type Divergence
- `pt.mask` (`src/pytae/__init__.py:291`) and `DataFrame.mask` (`src/pytae/dataframe.py:1229`) expose explicit keyword parameters `(cols, method="hash", *, key=None, salt=None, vault=None, redact_val="[REDACTED]")` and always return `pytae.DataFrame`.
- `PolarsPtAccessor.mask` (`src/pytae/accessor.py:145`) and `PandasPtAccessor.mask` (`src/pytae/accessor.py:386`) accept only `(self, cols, method="hash", **kwargs: Any)`.
- `pytae.mask.mask()` (`src/pytae/mask.py:380-429`) returns the caller's native frame type (`pl.DataFrame`, `pd.DataFrame`, or `pytae.DataFrame`), whereas `pt.mask()` wraps the result in `pytae.DataFrame`.

---

## 3. `-dropna` / `dropna()` Default `how` Behavior vs. Docstrings

- **Implementation (`src/pytae/polars_engine.py:521-546`)**:
  - When `cols` is omitted (`df.dropna()` or `-dropna` with no arguments) and `how=None`, `effective_how` defaults to **`"all"`** (drops only rows where *every* column is null).
  - When `cols` are provided (`df.dropna("a,b")` or `-dropna "a,b"`) and `how=None`, `effective_how` defaults to **`"any"`** (drops rows where *any* specified column is null).
- **Inconsistency**:
  - `src/pytae/cli_help.py:684` and `docs/detailed_docs/cli/clean_replace.md` accurately document this conditional default (`all` when no columns given, `any` when columns given).
  - However, `src/pytae/dataframe.py:820` (`DataFrame.dropna` docstring), `docs/comparison_to_pandas.md`, and `docs/comparison_to_dplyr.md` equate bare `df.dropna()` with Pandas `df.dropna()` (which defaults to `how="any"` even when no columns are specified).

---

## 4. CLI vs. REPL Behavioral Inconsistencies

### 4.1 `-cols <arg>` Substring Filtering Works in REPL but Errors in CLI
- **In REPL (`src/pytae/repl.py:1810-1823`, `2705-2715`)**:
  `-cols` accepts `"asc"`, `"desc"`, `"file"`, **or any arbitrary substring** (e.g., `-cols bill` filters columns containing `"bill"` case-insensitively).
- **In CLI (`src/pytae/cli_parsing.py:714-723`, `parse_list_order`)**:
  `-cols` only accepts `"file"`, `"asc"`, or `"desc"`. Passing a substring like `pytae penguins.parquet -cols bill` raises:
  `ValueError: invalid order 'bill'; expected 'file', 'asc', or 'desc'`

### 4.2 Fast-Path Inspections Differ Between `execute_line` and `_cmd_targeted_pipeline` in REPL
- In `src/pytae/repl.py`:
  - `execute_line` (lines 1796-1889, for active table) intercepts `-shape`, `-cols`, `-dtype`, `-nulls`, `-glimpse`, `-describe`, `-head`, `-tail`.
  - `_cmd_targeted_pipeline` (lines 2694-2765, for `<tbl> -<flag>`) intercepts all of the above **plus** `-sample` (lines 2751-2764).
  - Consequently, `df1 -sample 5` runs via the targeted fast-path (using `df.sample(n=5)` directly without setting `self.last_result_df`), whereas `-sample 5` on the active table runs through `_cmd_pipeline` (which executes `_process_path` and sets `self.last_result_df`).

### 4.3 `-o clipboard` / `-o clip` Supported in CLI and REPL `-o`, Not in REPL `save`
- In CLI (`src/pytae/cli_run.py:1303`) and REPL pipeline `-o clip`, output is copied to the system clipboard.
- In REPL `save` (`src/pytae/repl.py:2902`), `save clip` attempts to write a file named `clip` and fails with `unsupported file type ''`.

---

## 5. Configuration, Packaging, and VS Code Extension Drift

### 5.1 Conflicting Python Version Targets in `pyproject.toml`
- `pyproject.toml:11`: `requires-python = ">=3.11"`
- `pyproject.toml:49`: `[tool.ruff] target-version = "py310"`
- `pyproject.toml:69`: `[tool.mypy] python_version = "3.12"`
- `.github/workflows/ci.yml`: tests on Python `3.12`.

### 5.2 VS Code Extension Version and Grammar Drift (`extensions/vscode-pytae/`)
- **Version mismatch**:
  - `extensions/vscode-pytae/package.json:5`: `"version": "3.12.8"`
  - `extensions/vscode-pytae/README.md:59`: instructs running `code --install-extension pytae-3.10.5.vsix`
  - Checked-in binary in `extensions/vscode-pytae/`: `pytae-3.11.0.vsix`
- **TextMate grammar drift (`extensions/vscode-pytae/syntaxes/pytae.tmLanguage.json`)**:
  - Line 47 highlights retired window verbs `\b(lead|lag)\b` instead of `shift`.
  - Line 29 verb regex omits `mask` and `unmask`.
  - Line 61 still highlights retired backtick column quoting (`` `[^`]*` ``), which Pytae now rejects with a syntax error recommending `[col name]`.

