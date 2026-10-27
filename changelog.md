# Changelog

All notable changes to this project are documented in this file.

## [3.12.6] - 2026-10-27

### Added
- **REPL Non-Destructive Preview Framework & Explicit Assignment Mutation**:
  - Running pipeline commands (`-filter`, `-head`, `-distinct`, etc.) and targeted pipelines (`k -filter`, `k -head`) now previews results without mutating active or target DataFrames.
  - Mutations occur explicitly via assignment (`k = df`, `filtered_k = df -filter ...`, `k = k -filter ...`, `df = -filter ...`).
  - Previews output formatted tables directly matching CLI output parity rather than being suppressed.
- **Standalone Zero-Python Executable Packaging**:
  - Added `scripts/build_binary.py` supporting single-file binaries on Linux (`pytae-linux-x86_64`) and macOS ARM64 (`pytae-macos-arm64`), plus an optimized pre-extracted `--onedir` zip bundle on Windows (`pytae-windows-x64.zip`) for instant startup.
  - Added standalone binary release workflow in `.github/workflows/build_binaries.yml` targeting release publishing.
- **REPL Granular Table Reset (`reset <table_name>`)**:
  - Added ability to reset a single table back to its original loaded file state without affecting any other loaded workbench tables.

### Fixed
- **REPL `-distinct` Followed by `-head` Truncation**:
  - Fixed an issue where chained transformation flags inadvertently truncated the underlying DataFrame in-place.
- **Windows REPL Memory Management**:
  - Configured 64-bit Windows process working set trimming (`EmptyWorkingSet` / `SetProcessWorkingSetSize`) and disabled parquet memory mapping to prevent process RAM growth and return unmapped pages to the OS.
- **REPL Exception Shielding**:
  - Wrapped interactive runner loop to prevent unexpected command crashes from terminating active REPL sessions.

## [3.12.5] - 2026-10-26

### Added
- **Disk-Backed Session Checkpoints (Arrow IPC)**:
  - Checkpoints are now serialized to session temporary storage via high-performance, zero-copy Polars Arrow IPC (`.ipc`), consuming **0 MB of active RAM**.
  - On-demand streaming/querying from checkpoints (`-sql`, `py`, `-join`, and assignments) loads tables on-the-fly without keeping redundant copies pinned in RAM.
  - Cross-platform sanitized filenames ensure robust operation across Windows, macOS, and Linux without illegal character collision.

### Changed
- **Milestone Undo Baseline Reset on `checkpoint`**:
  - Running `checkpoint <name>` establishes an explicit milestone and immediately clears `self.undo_stack` and `self.redo_stack`.
  - All accumulated intermediate DataFrame clones from prior exploration are instantly dereferenced and reclaimed via `gc.collect()`.
  - Transformations performed *after* the checkpoint push to a fresh undo stack, allowing users to experiment and undo back to their milestone cleanly.
- **Strict RAM Isolation on `restore`**:
  - Running `restore <name>` completely purges all post-checkpoint tables, derived temporary tables, and undo history from memory.
  - Automatically reloads strictly the tables recorded in the checkpoint and triggers `gc.collect()`, guaranteeing that active RAM reflects the restored milestone only.
- **Immediate Memory Reclamation on `rm`**:
  - `rm <table_name>` and `rm *` delete in-memory table references and invoke `gc.collect()` to reclaim RAM immediately.
  - Checkpoints saved on disk remain completely independent and can restore removed tables at any time.
- **Disk File Deletion on Checkpoint Removal**:
  - `rm checkpoint <name>`, `checkpoint rm <name>`, `rm checkpoint *`, and `checkpoint rm *` safely remove the saved checkpoint files and directory trees from disk.
  - REPL exit and session close (`r.close()`) automatically clean up all temporary session checkpoint storage.

## [3.12.4] - 2026-10-26

### Fixed
- **Lazy Pipeline Preservation in `-plot`, `-describe`, and `-diff`**:
  - Fixed a critical issue in `_Pipeline.dataframe()` where `self._pldf` was only converted to pandas if it was an instance of `pl.DataFrame`. When operations such as `-filter`, `-mutate`, `-select`, or `-distinct` produced a `pl.LazyFrame`, `_Pipeline.dataframe()` silently fell back to re-reading the original file from disk, losing all prior pipeline transformations.
  - Updated `_Pipeline.dataframe()` to properly collect `self._pldf` via `self.polars_frame()` whenever present, guaranteeing that downstream operations (`-plot`, `-describe`, `-diff`) receive the fully filtered and transformed data.
- **CLI Reader Options Forwarded to REPL on `-i`**:
  - Reader CLI options (`-encoding`, `-dlim`, `-nrows`) are now preserved and forwarded when launching an interactive REPL session with `pytae <file> [options] -i`.
- **Unified Reader Schema Inference & Fallbacks**:
  - Synchronized CSV and text parsing fallback logic between CLI and REPL, ensuring identical schema inference, encoding handling (`latin1`, `cp1252`, etc.), and delayed type conversion.
- **Cross-Platform REPL Arrow Key & History Navigation**:
  - Added Windows terminal history and up/down arrow key navigation via `pyreadline3`.
  - Added Git Bash / MinTTY terminal support by parsing standard ANSI escape sequences (`\x1b[A`, `\x1b[B`).

### Changed
- **Strict Terminal Clearing (`clear`)**:
  - Standardized on the canonical `clear` command across the REPL shell and public Python API (`pt.clear()`, `r.clear()`).
  - Completely removed the `cls` alias from `pytae.__all__` and the public API.
  - REPL commands `cls`, `-cls`, `--cls`, `-clear`, or `--clear` are cleanly rejected with an immediate redirection message to `clear`.
- **Strict Wildcard Syntax for `rm`**:
  - Standardized memory table and checkpoint removal on `*` wildcard syntax: `rm *` (removes all in-memory tables) and `rm checkpoint *` (deletes all saved snapshots).
  - Legacy flag `-all` and bare argument `all` are cleanly rejected with clear guidance directing the user to `*`.
- **Strict Singular `rm checkpoint`**:
  - Enforced singular `rm checkpoint` strictly; plural `rm checkpoints` is rejected with immediate redirection to `rm checkpoint`.

### Added
- **Proactive Headless Linux Plotting Guidance**:
  - When `-plot` is run on Linux without `-o` and Matplotlib falls back to the headless `Agg` backend (unable to open a GUI window), `pytae` outputs actionable diagnostic guidance on `stderr` explaining how to install GUI libraries (`python3-tk`, `PyQt6`) or save to a file using `-o <file.png>`.

## [3.12.3] - 2026-10-25

### Fixed
- **PyPI Documentation Links**:
  - Replaced all relative document and directory links in `readme.md` with absolute GitHub repository URLs (`https://github.com/maddytae/pytae/blob/master/...` and `/tree/master/...`).
  - Resolves PyPI 404 navigation errors when users click documentation links directly on [pypi.org/project/pytae/](https://pypi.org/project/pytae/).
  - Added dedicated `Changelog` link to project URLs in package metadata.

## [3.12.2] - 2026-10-25

### Added
- **Session-Wide Checkpoint Architecture**:
  - `checkpoint <name>` freezes the state of the entire workbench session (all loaded DataFrames in memory, their file sources, and the active dataset pointer) completely independent of the active table.
  - `restore <name>` non-destructively restores the complete multi-table workbench to the checkpoint snapshot, removing intermediate tables created after the checkpoint and restoring the previous active dataset.
  - `checkpoints` displays a comprehensive breakdown of all tables frozen within each named snapshot (e.g., `maddy: df1 (344x7), df2 (244x7) [active: df2]`).
- **Inline Reader Options on REPL Assignment & Load**:
  - Both `<var> = <path>` and `load <path> as <alias>` now support inline reader flags directly from the prompt:
    - `-encoding <enc>`: Custom character encoding (e.g., `-encoding latin1`).
    - `-dlim <char>`: Custom column delimiter (e.g., `-dlim ";"`, `-dlim "\t"`).
    - `-nrows <N>`: Read row limit for exploratory sampling (e.g., `-nrows 1000`).
  - Examples: `df1 = raw_data.csv -encoding latin1 -dlim ";"` and `load sales.csv as df2 -nrows 500`.

## [3.12.1] - 2026-10-25

### Added
- **Automatic Bundled Sample Dataset Resolution**:
  - The CLI and REPL now automatically resolve bundled sample datasets (`penguins.parquet`, `tips.parquet`, `titanic.parquet`, etc.) without requiring an explicit path or `sample:` prefix.
  - Commands such as `df1=penguins.parquet`, `pytae penguins.parquet -shape`, or `load tips.parquet as df2` work directly out-of-the-box in any directory.

### Changed
- **REPL Multi-Table & Checkpoint State Separation**:
  - Cleanly distinguished in-memory tables from saved checkpoints. Checkpoints are kept in dedicated snapshot storage (`checkpoints`) and do not pollute the table prompt (`[df1, df2]`).
  - Single-table REPL prompt displays table name and dimensions (`pytae [df1: 344x7]>`), while multi-table REPL displays concise loaded tables (`pytae [df1, df2]>`).
  - `tables` displays source filenames and highlights the active table with an asterisk marker and `[active]` flag.

## [3.12.0] - 2026-10-25

### Added
- **Interactive REPL Shell (`pytae -i`, `pt.repl()`, `df.repl()`)**:
  - Implemented an interactive Read-Eval-Print Loop (REPL) for stateful data exploration, interactive debugging, and pipeline prototyping without repeatedly reloading datasets from disk.
  - **Two Dedicated Operation Modes**:
    - **Mode 1: Single-Table Exploration**: Focused session on a single active table with full rollback and checkpoint support (`pytae [df]>`).
    - **Mode 2: Multi-Table Workbench**: Ingest, manage, join, and query multiple tables simultaneously (`pytae [df1, df2]>`).
  - **Zero-Cost State Management & History**:
    - `reset`: Instantly restore the original dataset as loaded from disk ($O(1)$ memory reference switch, zero disk re-reads).
    - `undo`: Revert the last applied transformation step across session history.
    - `redo`: Re-apply the last undone transformation step.
    - `checkpoint <name>` / `restore <name>`: Freeze and restore named table states.
    - `checkpoints`: List all saved checkpoints with shapes and dimensions.
    - `history`: Display numbered sequence of applied transformations in the active session.
    - `tables`: List all loaded tables in Multi-Table Workbench mode with row counts, column counts, and memory footprints.
  - **Model 2 Clean Terminal Workflow**:
    - State mutations confirm with concise, clean shape confirmations (`-> df: 10,000 rows x 3 cols`) without spewing wide tables across the terminal.
    - Dedicated inspection flags (`-head`, `-tail`, `-sample`, `-shape`, `-cols`, `-dtype`, `-nulls`, `-glimpse`, `-describe`) provide non-destructive previews on demand.
  - **1:1 Parity with CLI Syntax**:
    - REPL commands accept the exact single-dash CLI flag syntax (`-filter`, `-mutate`, `-select`, `-arrange`, `-by ... -agg`, `-distinct`, `-dropna`, `-fillna`, `-mask`, `-unmask`, `-sql`).
    - Bare pipeline verbs (e.g. `filter`, `mutate`, `select`) and bare inspections (e.g. `head`, `shape`) are cleanly rejected with clear, helpful guidance directing users to single-dash CLI flags (`-filter`, `-head`).
  - **Integrated Multi-Table SQL & Python Expressions**:
    - `-sql "<query>"`: Execute vectorized ANSI SQL queries directly against loaded in-memory tables via Polars `SQLContext`.
    - `py <expr>`: Evaluate arbitrary Python expressions with `df` (pytae) and `pldf` (polars) in scope.
  - **Multi-Interface Support**:
    - CLI: `pytae <file> -i`, `pytae -i`, `pytae <file1> <file2> -i`, or pre-seeding pipelines `pytae <file> -filter ... -i`.
    - Python SDK: `pt.repl(df)`, `df.repl()`, and pandas `.pt` accessor `df.pt.repl()`, returning the final transformed DataFrame on exit.

### Changed
- **CLI Flag Single-Dash Standardization & Parity**:
  - Standardized all command-line interface flags to single hyphens (`-flag`) for consistent readability and cross-platform compatibility.
  - Double-dash flags (e.g. `--filter`, `--help`) raise clear, actionable diagnostic errors guiding users to the canonical single-dash syntax.
  - Retired confusing redundant aliases in favor of "One and Only One Obvious Way":
    - `-output` $\to$ `-o <target>`
    - `-od`, `-out-dir` $\to$ `-out_dir <dir>`
    - `-limit` $\to$ `-nrows <N>`
    - `-tolerance` $\to$ `-tol <threshold>`
    - `-repl`, `-interactive` $\to$ `-i`
    - `-examples` $\to$ `-cheatsheet`
- **Documentation Overhaul & Link Validation**:
  - `README.md` streamlined and modernized with interactive REPL highlighted as a core pillar alongside the Python Library and CLI.
  - Added structured Documentation Directory Table mapping every feature to its interactive Jupyter Notebook and CLI Markdown guide.
  - Audited and verified 100% of internal file links (148) and anchor links (221) across all documentation and guides.
- **Python Support Baseline & Security Hardening**:
  - Set minimum Python requirement to `requires-python = ">=3.11"`.
  - Upgraded transitive dependency `pillow` in `uv.lock` from legacy `12.3.0` to `13.0.0`, eliminating 39 Dependabot vulnerabilities.
  - Updated CI test matrix to Python 3.11–3.14.

## [3.11.0] - 2026-10-23

### Added
- **Sensitive Data Masking, Authenticated Encryption & Tokenization (`mask`, `unmask`, `-mask`, `-unmask`)**:
  - Implemented end-to-end PII and sensitive data protection supporting both one-way irreversible and two-way reversible workflows across the CLI and Python library (`pt.mask()`, `pt.unmask()`, `df.mask()`, `df.unmask()`, and pandas `.pt` accessors).
  - **One-Way Irreversible Masking**:
    - Cryptographic SHA-256 hashing (`col=hash` / `col=sha256`) for non-reversible anonymization.
    - Custom salt support (`-salt`, `salt=`) to thwart rainbow table and dictionary lookup attacks.
    - String and value redaction (`col=redact`), replacing non-null cell values with asterisks (`***`) or customizable redaction values.
  - **Reversible Option 1: Key-Based Authenticated Encryption**:
    - Zero-dependency authenticated symmetric stream cipher (HMAC-SHA256 CTR) using Python standard library (`hashlib`, `hmac`, `os.urandom`, `base64`).
    - Random per-cell initialization vectors (IVs) and HMAC integrity validation to prevent tampering and corruption.
    - Reversible via `-unmask "col" -key "password"` / `df.unmask(cols, key="password")`. Strictly raises clear error on incorrect key.
  - **Reversible Option 2: Pseudonym Tokenization with Persistent Vault**:
    - Pseudonym tokenization (`col=tokenize`, `-vault <path>`) generating consistent tokens (e.g. `user_0001`, `user_0002`).
    - Maintains entity relationships, frequency distributions, and table joinability across runs.
    - Persistent token vault supporting `.parquet`, `.csv`, `.ndjson`, and `.json`.
    - Type-aware: vault records native column data types (`Int64`, `Float64`, `String`, etc.), allowing `-unmask` / `df.unmask(..., vault=...)` to automatically cast columns back to their original data types upon restoration.
  - **CLI Pipeline Integration**:
    - Added CLI flags: `-mask`, `-unmask`, `-key`, `-salt`, `-vault`.
    - CLI keyword help documentation and aliases (`pytae -help mask`, `pytae -help unmask`).
    - Section 12 in cheatsheets (`pytae -cheatsheet`, `docs/cli_cheatsheet.md`).
    - Dedicated CLI guide: `docs/detailed_docs/cli/mask.md`.

## [3.10.5] - 2026-10-22

### Fixed
- **Robust CSV & Delimited Text Schema Inference and Conversion**:
  - Fixed `polars.exceptions.ComputeError` during CSV parsing and format conversion (e.g. `pytae *.csv -o parquet`) caused by Polars' default 100-row schema inference (`infer_schema_length=100`) misclassifying late-appearing floating-point decimal columns as integers (`i64`).
  - Set default `infer_schema_length=10000` across `CsvReader`, `TxtReader`, `pt.read_csv()`, and `pt.scan_csv()`.
  - Added resilient two-tier error fallback: if a `ComputeError` occurs during reader evaluation or lazy frame collection, pytae automatically retries with full-scan schema inference (`infer_schema_length=None`) and seamlessly falls back to robust pandas parsing with `low_memory=False` when necessary.
  - Optimized CLI pipeline format conversion (`-o parquet` / `-o csv`) to stream lazily via `sink_parquet()` while ensuring robust fallback if mixed schema exceptions arise.

## [3.10.4] - 2026-10-21

### Added
- **Unified Method-Token Standard for Null & NaN Filtering**:
  - Standardized missing value (`null`) and non-finite float (`NaN`) filtering on canonical Polars predicates across both string expressions and dictionaries in Python and CLI:
    - Missing data (`null`): `is_null()`, `is_not_null()`
    - Float non-finites (`NaN`): `is_nan()`, `is_not_nan()`
  - Supported in string expressions (`"sex.is_null()"`, `"score.is_nan()"`, `"[bill length mm].is_not_null()"`).
  - Supported in dictionaries (`{"sex": "is_null()"}`, `{"score": "is_nan()"}`, `{"bill length mm": "is_not_null()"}`) and CLI dictionaries (`-filter "{sex: is_null()}"`, `-filter "{score: is_nan()}"`).
  - Enables clean dynamic programmatic query construction without splitting filters into string and dict parts.

### Changed & Enforced
- **Strict Method-Token Validation ("No Forgiving")**:
  - Parentheses `()` are strictly required for method tokens in dictionaries (`"is_null()"`, `"is_nan()"`). Bare words without parentheses (`"is_null"`, `"nan"`) strictly raise `ValueError` with clear guidance.
  - Passing `None` or `float("nan")` in filter dictionaries strictly raises `ValueError` pointing users directly to `'is_null()'` or `'is_nan()'`.
  - Disallowed SQL-style `is null` / `is not null` in `-filter`, pointing users to `sex.is_null()` / `sex.is_not_null()` (or `-sql`).
  - Removed internal sentinel objects and exported sentinels from `__init__.py`, keeping the public API clean and zero-cost.

### Documentation
- Updated CLI filter guide (`docs/detailed_docs/cli/filter.md`), cheatsheets (`docs/cli_cheatsheet.md`, `src/pytae/cheatsheet.py`), and reference manual (`reference/pytae_reference.txt`).
- Updated interactive filter notebook (`docs/detailed_docs/library/filter.ipynb`) with dedicated working examples for null and NaN in expressions and dictionaries.
- Synchronized all 15 documentation notebooks with 100% clean execution.

## [3.10.3] - 2026-10-21

### Added
- **Unified `rcva` Reshaping Grammar Across `long`, `wide`, and `pivot`**:
  - Extended the canonical `rcva` grammar (`r=`, `c=`, `v=`) to `-long` and `df.long()` (with `r=` as the row identifier alias for `id_vars`).
  - Now all three table reshaping operations share identical parameter vocabulary:
    - `pivot`: `r` (row index), `c` (pivot columns), `v` (values), `a` (aggregation)
    - `wide`: `r` (row index), `c` (header source), `v` (values)
    - `long`: `r` (row identifiers to keep), `c` (unpivoted metric name), `v` (unpivoted value name)
- **Standardized Negation Prefix (`!col`)**:
  - Supported standard Unix/zsh exclamation prefix `!col` for column exclusions across `--select "!col1,!col2"` and `df.select("!col1", "!col2")`.
  - Completely avoids `argparse` flag collision issues with leading hyphens (e.g. `-sex` being misidentified as a CLI argument).
- **Lazy Streaming Out-of-Core Sinks**:
  - Implemented streaming file export for `pl.LazyFrame` in `write_dataframe` via native Polars sinks (`sink_parquet`, `sink_csv`, `sink_ndjson`).
  - Pipeline commands like `pytae data.parquet -filter ... -o out.parquet` now execute completely lazily via Polars' streaming engine without materializing intermediate tables into memory.

### Deprecated & Retired (Zero Backward Compatibility Cruft)
- **Exhaustive Deprecation Cleanup & Single Obvious Way Enforcement**:
  - Eliminated all lingering residue, documentation references, and legacy methods for previously deprecated features across the engine, CLI, notebooks, and reference manual.
  - Standardized missing value handling exclusively on `fillna(value, *cols, nans=True/False)` and `dropna(*cols, how='all'|'any', drop_nans=True/False)`. Completely removed legacy aliases (`fill_null`, `fill_nan`, `drop_nulls`, `drop_na`, `-handle_missing`).
  - Removed pandas-compatibility stub `df.query()` in favor of canonical `df.filter()`.
  - Updated `slice_max` and `slice_min` redirect errors to point directly to canonical `arrange(...).head(n)` / `arrange(...).tail(n)`.
  - Cleaned `__all__` in `__init__.py` to remove retired stub functions (`pick`, `read`, `scan`).
  - Enforced strict clipboard output validation (`-o clip` strictly; `-o clipboard` raises informative redirect error).
  - Cleaned CLI docs and reference manual to retire `-replace_values`, `-handle_missing`, `-info`, `-value_counts`, and `-pretty`.

### Optimized & Refactored
- **Native Polars Rust I/O Delegation**:
  - Refactored `ParquetReader.to_dataframe()`, `CsvReader.to_dataframe()`, and `TxtReader.to_dataframe()` in `readers.py` to delegate directly to Polars' native multithreaded Rust readers (`self.to_polars().to_pandas()`).
  - Bypassed legacy Python 200,000-row chunk concatenation for standard UTF-8 files, yielding 3x–5x faster CSV and Parquet ingestion.
- **Pure Relational Flat Table Architecture**:
  - Dropped fragile `_orig_index` tracking and restoration loops from DataFrame transformations, guaranteeing clean 1D RangeIndex tables with zero MultiIndex traps.
- **Pure Polars AST Expression Compilation**:
  - Refactored formula and predicate compilation (`_rewrite_col_refs`) in `_parsing.py` and `polars_engine.py` to be 100% native Polars expressions (`pl.Expr`) without legacy Python `eval()` fallbacks.

### Documentation
- **Comprehensive Notebook Re-Execution & Output Synchronization**:
  - Re-run and synchronized all 15 documentation Jupyter Notebooks (`.ipynb`) and reproducible benchmark figures.
  - Updated CLI Cheatsheet (`docs/cli_cheatsheet.md`, `src/pytae/cheatsheet.py`), in-terminal interactive help (`src/pytae/cli_help.py`), topic guides (`docs/detailed_docs/cli/`), and reference manual (`reference/pytae_reference.txt`).

## [3.10.1] - 2026-10-18

### Added
- **Interactive In-Terminal Visualizers (`-bar`, `-scatter`, `-corr`)**:
  - Horizontal bar charts via `-bar [COL] [VAL_COL]` (and Python `pt.bar()`, `df.bar()`) supporting:
    - Automatic categorical frequency distributions when a single column is specified (`pytae penguins.parquet -bar species`).
    - Numeric aggregation when two columns are provided (`pytae penguins.parquet -bar species body_mass_g`).
    - Multi-column comparison when multiple value columns are specified (`pytae penguins.parquet -bar species "bill_length_mm,bill_depth_mm"`).
  - Braille scatter plots via `-scatter X Y [OPTS]` (and Python `pt.scatter()`, `df.scatter()`) supporting:
    - High-resolution braille 2×4 dot sub-character grid rendering (`braille=True`).
    - Standard ASCII character fallback (`braille=False`).
    - Linear regression trendline fit with Pearson correlation coefficient display (`trend=True`).
    - Key bivariate summary statistics ($N$, $R$, $R^2$, slope, intercept, min/max).
  - Pearson correlation matrix heatmap via `-corr [COLS] [OPTS]` (and Python `pt.corr()`, `df.corr()`) supporting:
    - Automatic selection of all numeric columns when omitted.
    - Shaded terminal blocks (`█`, `▓`, `▒`, `░`) representing correlation strength and direction.
    - Pairwise ranked correlation table mode (`pairwise=True`).
  - Unified `width` parameter and summary statistics across all terminal visualizers (`-freq`, `-hist`, `-bar`, `-scatter`, `-corr`).
  - Dedicated CLI help topics: `pytae --help-topic bar`, `pytae --help-topic scatter`, and `pytae --help-topic corr`.

### Fixed
- **Strict String Quoting in `-filter` & `df.filter()`**:
  - Enforced strict string quoting for string columns in `polars_engine.py` and `cli_parsing.py`.
  - Non-string values (e.g. unquoted numbers `id = 9` or unquoted literals) passed to string columns now raise an explicit, actionable `TypeError` guiding the user to wrap strings in single quotes (e.g. `id = '9'`).
  - Eliminates silent, confusing lexicographical comparison bugs where numbers were auto-coerced to strings (such as `'10' < '9'`).
- **Terminal Table Output Truncation & DataFrame Formatting**:
  - Unwrapped `pytae.dataframe.DataFrame` to underlying Polars DataFrame in `_format_table` and `_apply_round` in `cli_run.py`.
  - Increased the default terminal table display threshold from 100 to 250 rows before truncating (`tbl_rows = max(n_rows, 10) if n_rows <= 250 else 10`), ensuring queries returning up to 250 rows (such as `-by x -agg y=col:sum -bar`) show all rows in full.
  - Stored raw Polars DataFrames in `pipeline._pldf` across `-freq`, `-hist`, `-bar`, and `-corr` for seamless downstream terminal rendering.

### Documentation
- **CLI & Library Plotting Documentation Separation**:
  - Renamed `docs/detailed_docs/cli/plotting.md` to `docs/detailed_docs/cli/cli_plots.md`.
  - Clarified documentation boundaries so `cli_plots.md` focuses purely on CLI terminal and headless plotting, while `plotting.ipynb` focuses entirely on the Python plotting library.
  - Updated `docs/detailed_docs/cli/filter.md` with explicit guidelines and alerts regarding strict string quoting requirements.

## [3.10.0] - 2026-10-17

### Added
- **Full Polars-Native Library & CLI Architecture**:
  - `pytae` is now natively and completely powered by **Polars** across both the Python library and CLI, sharing a unified core execution engine with zero code duplication.
  - First-class `pt.DataFrame` container backed directly by Polars `pl.DataFrame` (and `pl.LazyFrame`), delivering blazing-fast multithreaded SIMD vector execution.
  - Fluid chaining: calling `.pt` off any Pandas or Polars DataFrame enters `pt.DataFrame` on the first call, allowing subsequent chained verbs (`.by()`, `.mutate()`, `.filter()`, `.arrange()`, `.count()`, `.agg()`, `.pivot()`, `.plot()`) to be called directly without repeatedly invoking `.pt`.
  - Seamless universal reader `pt.read()` / `pt.scan()` with auto-detection of formats (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.ipc`, `.xlsx`) powered by Polars.
  - Native constructors: `pt(pandas_df)` or `pt(polars_df)` automatically detects and wraps tabular data into `pt.DataFrame`.
  - Effortless exports: `.to_pandas()`, `.to_polars()`, and `.to_clip()` (system clipboard export via Polars string serialization).
  - Preserved metadata and Pandas testing interoperability hooks (`pd.testing.assert_frame_equal` and `pd.melt`).
  - **Transparent Polars Verb Delegation**: `pt.DataFrame.__getattr__` dynamically forwards any Polars DataFrame/LazyFrame method (e.g. `.with_columns()`, `.slice()`, `.describe()`, `.explode()`) while auto-unwrapping `pt.DataFrame` inputs and auto-rewrapping Polars outputs to preserve fluent chaining.
- **First-Class `count` Verb Across Python Library & CLI**:
  - Introduced dedicated, first-class `count` verb across `DataFrame.count(*cols, sort=True, name="n")`, `GroupedDataFrame.count(sort=True, name="n")`, `pt.count(df, ...)`, Pandas and Polars `.pt.count(...)` accessors, and CLI flag `-count` / `--count`.
  - Intuitively defaults to sorting descending by the count column (`sort=True`) with output column `name="n"`, matching exploratory intuition.
  - Supports `sort=False` to preserve original encounter order, and `name="<name>"` to customize the count column name.
  - Calling `df.count()` without arguments outputs total row count in a single-row DataFrame.
  - Seamlessly integrates with single-shot grouping: `df.by("species").count()` or `pytae data.parquet -by species -count`.
  - Detects and cleanly rejects collisions where `name` matches an active grouping key with a friendly, actionable `ValueError`.
- **Canonical `count` Normalization in `agg`**:
  - `count` (and `count()`) is now the canonical operation name for row counting inside `agg()` and CLI `-agg`.
  - Supports custom destinations without awkward tautologies: `df.by("species").agg(total="count", avg_mass="body_mass_g:mean")` or string expressions `df.by("species").agg("total = count(), avg_mass = mean(body_mass_g)")`.
  - Preserves backward compatibility for `"n"`, `"n()"`, `"len"`, and `"size"` as aliases.
- **Zero-Data-Loss Safety Defaults**:
  - `df.dropna()`: bare call defaults to Zero-Data-Loss safety semantics (drops only 100% blank rows); targeted columns `df.dropna("a", "b")` drop rows missing any specified key (`how='any'`).
  - Differentiated float `NaN` and Arrow `null` cleaning via `drop_nans=True` (default), ensuring numeric floating-point `NaN` values are never missed.
  - `df.fillna()`: unified type-aware filling across numeric, string, boolean, and temporal columns.
  - Grouping and aggregation (`by`, `agg`, `pivot`, `freq`) default to `dropna=False`, ensuring missing, unclassified, or orphan records are never silently dropped.
- **Group-Aware & Proportion-Aware Row Slicing (`head` & `tail`)**:
  - `df.head()` and `df.tail()` (and standalone `pt.head()`, `pt.tail()`, and CLI `-head`, `-tail`) now provide comprehensive row slicing supporting:
    - Fixed row counts (`n=5`, `-head 5`).
    - Percentages and proportions (`prop=0.1`, `n="10%"`, `-head 10%`, `-head 0.1`).
    - Boundary tie-breaking (`with_ties=True`, `-head "3, ties=true"`).
    - Group awareness: `df.by("species").arrange("mass desc").head(3)` or `pytae penguins.parquet -by species -arrange "mass desc" -head 3`.
- **Native Polars Joins & Concatenation (`join`, `concat`)**:
  - `pt.join()`, `df.pt.join()`, `df.join()`: high-performance Polars join supporting inner, left, right, full, semi, anti, and cross joins, colon shorthand `on="left_key:right_key"`, auto-discovery of common join keys, and validation (`"1:1"`, `"1:m"`, `"m:1"`, `"m:m"`). Preserves `LazyFrame` query plans for predicate pushdown.
  - `pt.concat()`, `df.pt.concat()`, `df.concat()`: fast vertical and horizontal stacking with automatic schema mismatch handling (relaxed diagonal fallback) and automatic horizontal column deduplication.
- **Recoding & Advanced Window Functions in `mutate`**:
  - Categorical and value mapping via `mutate(status="map(code, {'A': 'Active', 'I': 'Inactive'})")`.
  - First and last window functions in grouped expressions: `df.by("id").mutate(first_val="first(val)", last_val="last(val)")`.
  - Multi-column transformations with `_` placeholder: `(col1, col2) = _ / 10`.
- **Reproducible Performance Benchmarks & Ecosystem Migration Guides**:
  - Dedicated comprehensive guides for migrating from [Pandas](docs/comparison_to_pandas.md), [dplyr](docs/comparison_to_dplyr.md), and [SAS](docs/comparison_to_sas.md).
  - Self-contained, reproducible 5,000,000-row benchmark suite in [`docs/benchmarks/`](docs/benchmarks/README.md) (`run_benchmarks.py`, `benchmarks.ipynb`, and speedup visualizations).

### Removed & Breaking Changes ("One and Only One Obvious Way")
- **Complete Retirement of `pick` in Favor of Canonical `arrange().head()` / `arrange().tail()`**:
  - In adherence to *"One and Only One Obvious Way"*, the niche verb `pick` and CLI flag `-pick` have been completely removed across the Python library and CLI.
  - Slicing top records is simply `df.arrange("col desc").head(n)`.
  - Slicing bottom records is `df.arrange("col").head(n)` (or `df.arrange("col desc").tail(n)`).
  - Grouped extreme slicing is `df.by("g").arrange("col desc").head(n)`.
  - Calling `df.pick()`, `pt.pick()`, or CLI `-pick` raises an immediate, helpful redirect error guiding users to compose `arrange` and `head`/`tail`.
- **Removal of Obsolete `ungroup()`**:
  - In Polars and Pytae, `.by()` is an ephemeral, single-shot scoping context for the immediate next operation (`mutate()`, `agg()`, `count()`, `head()`, `tail()`).
  - Because grouping automatically clears upon operation completion and never persists on the resulting `DataFrame`, `ungroup()` was completely redundant and has been removed from `DataFrame`, accessors, and the public API.
  - Chaining from grouped calculations directly into whole-table calculations or new grouping keys works seamlessly without intermediate cleanup.
- **Clean Break: Eradication of `merge` in Favor of `join`**:
  - Renamed CLI flag `-merge` / `--merge` to `-join` / `--join` (`pytae -file "a.csv=a; b.csv=b" -join "left=a,right=b,on=id"`).
  - Eradicated `merge` keyword across Python library and CLI; use native `join` exclusively.
- **Zero-Data-Loss Safety Defaults Terminology**:
  - Standardized all documentation, docstrings, and error messages to use **"Zero-Data-Loss Safety Defaults"** (retiring internal "Option B" terminology).
- **Core Philosophy Standardization**:
  - Standardized core design philosophy across codebase, errors, and documentation on *"One and Only One Obvious Way"*.

## [3.9.0] - 2026-10-14

### Added
- **Native Vectorized Polars Execution Engine for CLI**:
  - Full multithreaded SIMD vectorization across readers and all core CLI verbs:
    - `-filter`: intervals, comparisons, set membership, string patterns.
    - `-select`: positive, slice, and negative exclusions.
    - `-arrange`: ascending/descending with nulls handling and spaced column names.
    - `-distinct`: deduplication with `keep=first|last|none`.
    - `-dropna`: row-level null drops.
    - `-rename`: fast column renaming.
    - `-pivot`: 1D, 2D, and whole-table pivot engine with rich metric expressions (`v="rev = sales:sum, orders = count"`), multi-func shorthand (`v="sales:[mean, sum]"`), optional `v` (defaults to row counts `'count'`), strict `f_v` fill parameter, and unprefixed 2D column headers for single metrics.
    - `-mutate`: AST expression compiler translating arithmetic, scientific notation (`1e6`), bracketed spaced columns (`[col name]`), `if_else`, functional `map()`, and `.over(by)` window functions into native Polars vector expressions.
    - `-pick`: extreme row selection (canonical verb replacing deprecated slice_max/min).
    - `-value_counts`: multi-column frequency counting with automated collision avoidance.
    - `-long` / `-wide`: fast unpivoting and 1-to-1 pivoting.
    - `-handle_missing`: type-aware vectorized null filling (mean/median/numeric, string fill & strip, preserving bool/datetime).
    - `-clean_columns`: vectorized header cleaning (strip, squeeze, fill, case, dedupe).
  - Native Polars readers for `.csv`, `.parquet`, `.txt`, `.jsonl` / `.ndjson`, and `.dat`.
  - Lazy dual-state caching in `_Pipeline` ensuring end-to-end vector execution without Pandas row materialization until final terminal display or plotting.
  - Transparent, resilient fallback to Pandas if any unsupported expression or construct is encountered.
  - 10x–20x performance improvement across CLI data processing tasks.
- **Pure Pandas Python Library**:
  - `pytae` Python library (`import pytae as pt`, `df.pt`) is 100% Pandas-based with zero Polars import overhead. Polars is exclusively isolated to the CLI pipeline.
- **Native Polars SQLContext**:
  - Replaced DuckDB in CLI multi-file `-sql` with native `polars.SQLContext`, eliminating external SQL dependencies and running queries directly on Polars DataFrames in memory.
- **CLI Native Boxed Tables & Auto-TTY Formatting**:
  - Direct Polars terminal table formatting when stdout is a TTY.
  - Clean TSV/whitespace streaming when piping to other tools or redirecting to files.
  - Silent deprecation of `-pretty` (rendered unnecessary by automatic TTY detection).
- **Fixed `-pick` Interaction with `show_all`**:
  - Ensured standalone `-pick` correctly suppresses full-dataset display without requiring an explicit `-head`.

### Removed & Breaking Changes ("One and Only One Obvious Way")
- **Eradicated `-slice_max` and `-slice_min` CLI flags**:
  - Eradicated completely in CLI; use `-pick "col desc"` or `-pick "col asc"` exclusively.
- **Removed `-group_by` in multi-file CLI**:
  - Removed in favor of canonical `-by`.
- **Strict `f_v` Fill Parameter in Pivot**:
  - Standardized on `f_v` exclusively across `pt.pivot()`, `df.pt.pivot()`, and CLI `-pivot`. Legacy aliases `fill` and `fill_value` are rejected with clear errors.
- **Pivot Column Header Naming**:
  - Single-metric 2D pivots no longer prefix column headers derived from `c` (e.g. `2020`, `2021` instead of `sales_sum_2020`). Prefixing is strictly reserved for multi-metric pivots (`len(metrics) > 1`).

## [3.8.4] - 2026-10-12

### Added
- **CLI Pipeline Timing & Benchmarking (`-time [N]` / `--time [N]`)**:
  - Bare `-time` (or `-time 1`) runs the pipeline once, prints normal output, and appends `Elapsed (1 run): <ms> ms`.
  - `-time N` (e.g., `-time 10` or `-time 1000`) runs the pipeline `N` times (printing normal stdout on the first run and suppressing duplicate stdout on runs `2..=N`) and prints `Elapsed (N runs): avg <ms> ms | min <ms> ms | max <ms> ms | total <ms> ms`.
  - Added dedicated CLI keyword help (`pytae -h time`).

## [3.8.3] - 2026-10-11

### Added
- **Multi-Column Transformations in `mutate` (`(col1, col2) = ...`)**:
  - Support transforming multiple columns simultaneously in both Python library `pt.mutate()` / `df.pt.mutate()` and CLI `-mutate`.
  - Placeholder `_` represents the current column being transformed:
    - In-place mutation: `(bill_length_mm, bill_depth_mm) = _ / 10`
    - Suffix / prefix column generation: `(bill_length_mm, bill_depth_mm)_cm = _ / 10`
    - Dynamic column selector predicates: `(startswith=bill_) = _ / 10`, `(dtype=numeric) = (_ - mean(_)) / std(_)`
- **Isolated Documentation Testing & Automation Tool**:
  - Added `scripts/update_doc_outputs.py` for headless execution in isolated temporary environments with pre-loaded sample datasets (`penguins`, `tips`, `titanic`, `diamonds`, `mpg`, `flights`).
  - Automatic conversion of tabular DataFrame outputs into native GitHub-Flavored Markdown (GFM) scrollable tables (`| col1 | col2 | ... |`).
  - Full output parity across all 31 Markdown documentation files in `docs/` and `docs/cli/`.

### Removed & Breaking Changes ("One and Only One Obvious Way")
- **Removed `qry` from Library and CLI**:
  - `pt.qry()`, `df.pt.qry()`, and module `pytae.qry` have been completely removed.
  - The CLI `-qry` / `--qry` flag has been removed. Passing `-qry` now produces an immediate clear error directing users to `-filter`.
  - Canonical row filtering is strictly `pt.filter()` / `df.pt.filter()` / `-filter`.

## [3.8.2] - 2026-10-07

### Added
- **`keep` Control in CLI `-distinct`**:
  - `-distinct` now supports `keep=` spec tokens: `keep=first` (default), `keep=last`, and `keep=false` (or `keep=none`).
  - Examples: `pytae penguins.parquet -distinct "species,island,keep=last"` or `pytae events.parquet -distinct "keep=last"`.

### Removed & Breaking Changes ("One and Only One Obvious Way")
- **Removed `dedupe` Backward Compatibility**:
  - The legacy `dedupe` function (`pt.dedupe`), DataFrame accessor method (`df.pt.dedupe`), and CLI flag (`-dedupe`) have been completely removed without backward compatibility.
  - Passing `-dedupe` on the CLI produces an immediate clear error directing users to `-distinct`.
  - Canonical deduplication is strictly `pt.distinct()` / `df.pt.distinct()` / `-distinct`.

## [3.8.1] - 2026-10-07

### Added
- **Standalone Grouping Verbs (`pt.by()`, `pt.ungroup()`)**:
  - Introduced standalone `pt.by(df, *cols)` / `df.pt.by(*cols)` and `pt.ungroup(df)` / `df.pt.ungroup()`.
  - Non-destructive execution: returns a shallow copy with isolated grouping metadata, preserving the input DataFrame unchanged.
- **Modernized Canonical Verbs (`filter`, `pick`, `distinct`)**:
  - `pt.filter()` / `df.pt.filter()` and CLI `-filter`: Canonical row filtering verb (with backwards-compatible `qry` deprecation alias).
  - `pt.pick()` / `df.pt.pick()` and CLI `-pick`: Canonical extreme row selection with `order='max'` and `order='min'` (with `slice_max`/`slice_min` deprecation aliases).
  - `pt.distinct()` / `df.pt.distinct()` and CLI `-distinct`: Canonical row deduplication verb (with `dedupe` deprecation alias).
- **Parquet & I/O Grouping Isolation**:
  - Automatic stripping of `_pt_by` metadata on write and read boundaries to prevent accidental grouping persistence across file serialization.

### Changed & Deprecated ("One and Only One Obvious Way")
- **Disallowed `by=` in Verbs**:
  - Verbs (`mutate`, `pick`, `agg`, `slice_max`, `slice_min`) strictly reject `by=` arguments with an explicit `TypeError` instructing users to use `pt.by(...)` or `.pt.by(...)`.
  - Terminal/collapsing verbs (`agg`) and slicing verbs (`pick`) automatically clear active grouping on output.
- **Notebook Multi-Line Pipeline Standards**:
  - All interactive documentation notebooks standardized so every chained method call starts on its own line.

## [3.8.0] - 2026-10-05

### Added
- **Row Sorting Verb (`arrange`)**:
  - Added `pt.arrange(df, *cols)` / `df.pt.arrange(*cols)` in the Python library and `-arrange SPEC` in the CLI.
  - Supports column reordering with explicit direction (`asc`, `desc`), leading minus shorthand (`-col`), and bracket notation `[col name]` for column names containing spaces.
- **Group-Aware Slicing Verbs (`slice_max`, `slice_min`)**:
  - Added `pt.slice_max(df, order_by, n=1, by=...)` / `df.pt.slice_max(...)` and `pt.slice_min(...)` / `df.pt.slice_min(...)`.
  - Added CLI flags `-slice_max SPEC` and `-slice_min SPEC` supporting `col:N`, `col,N`, `col,n=N`, and bracket notation `[col name]:N`.
  - Fully group-aware when combined with `-by` (or `by=...` in Python), returning the top/bottom records within each group.
- **Top-Level `-dropna [COLS]` in CLI**:
  - Consolidated row-filtering missing value drops to `-dropna [COLS]` matching pandas `df.dropna(subset=...)`.
  - Scoped `dropna=bool` remains supported inside `-pivot` and `-agg` specs.
- **Deduplication Flag (`-dedupe`)**:
  - Added CLI flag `-dedupe [COLS]` to drop duplicate rows across the intermediate DataFrame (or a specific column subset).

### Deprecated & Removed ("One and Only One Obvious Way")
- **`agg_df` $\rightarrow$ `agg`**:
  - Removed `df.pt.agg_df()` in favor of `df.pt.agg()` and `pt.agg()`. `df.pt.agg_df()` raises an explicit, helpful `AttributeError`.
  - Removed CLI `-agg_df` in favor of canonical `-agg`. Passing `-agg_df` yields a fatal CLI error pointing to `-agg`.
- **`-query` $\rightarrow$ `-qry`**:
  - Removed CLI `-query`. Passing `-query` raises an informative error pointing to `-qry`.
- **`-sort_by` / `-sort` $\rightarrow$ `-arrange`**:
  - Removed CLI `-sort_by` and `-sort`. Passing either raises an informative error pointing to `-arrange`.
- **`-unique` $\rightarrow$ `-dedupe`**:
  - Removed CLI `-unique`. Passing `-unique` raises an informative error pointing to `-dedupe`.
- **`-drop_na` $\rightarrow$ `-dropna`**:
  - Removed CLI `-drop_na`. Passing `-drop_na` raises an informative error pointing to `-dropna`.

## [3.7.3] - 2026-10-04

### Added
- **Transposed Summary (`glimpse`)**:
  - Added `-glimpse` to the CLI and `df.pt.glimpse(width=None)` / `pt.glimpse(df)` to the Python library (inspired by `dplyr::glimpse` and Polars).
  - Provides a transposed overview of rows count, columns count, column data types, and inline sample values.
  - In Python, returns the original DataFrame `self` for non-destructive inspection mid-pipeline.
- **Auto-Pipe Detection (CLI)**:
  - `pytae` automatically detects when data is piped via standard input (`stdin`) or redirected via shell, eliminating the requirement to pass a trailing `-` (e.g. `cat file.csv | pytae -head 5` works directly).
  - Explicit `-` continues to be fully supported for standard unix pipeline workflows.
- **Clipboard Ingestion (`pytae clip`)**:
  - Added `clip` as the canonical input target (`pytae clip [flags...]`).
  - Reads tabular data directly from the system clipboard into the pipeline via `pd.read_clipboard()`, with optional delimiter override via `-dlim`.
  - Strictly adheres to the "one and only one obvious way" philosophy: backward compatibility aliases `from_clip` and `clipboard` are removed.
- **Dedicated Row-Dropping Flag (`-drop_na`)**:
  - Added `-drop_na [COLS]` to the CLI pipeline.
  - Bare `-drop_na` drops rows containing `NaN` across any column; `-drop_na col1,col2` drops rows where specified columns are `NaN`.
  - Runs in the cleaning/filtering stage before aggregations and transformations.

## [3.7.2] - 2026-10-04

### Fixed
- **Documentation & PyPI Link Targets**:
  - Converted relative links in `readme.md` to absolute GitHub URLs so that documentation and Jupyter tutorial links resolve correctly on PyPI.

## [3.7.1] - 2026-10-04

### Documentation
- **Explicit Literal Constants with `pt.lit()`**:
  - Clarified that `pt.lit("str")` is used exclusively in Python `pt.mutate()` when assigning string constants that match existing column names to avoid column aliasing.
  - Clarified that `pt.lit()` is never required in the CLI or inside conditional expressions (`if_else`, `case_when`).

## [3.7.0] - 2026-09-29

### Added
- **2D Pivot Tables (`pt.pivot()` and CLI `-pivot`)**:
  - Full multi-dimensional Excel-style pivot table engine with universal `r`, `c`, `v`, `a` vocabulary.
  - Automatically resets index to standard `RangeIndex(0, 1, 2, ...)` with flat 1D string column headers.
  - Returns `int64` standard integers for count aggregations (`a="n"` / `a="size"`), with empty intersections filled as `0`.
  - Value column `v` is optional for row counts (`a="n"`).
  - Unobserved groupings across MultiIndexes are cleanly filtered without generating artificial Cartesian product rows.
  - Preserves hierarchical outer column keys across multi-column pivots (e.g. `2023_Q1`).
  - Validates duplicate dimensions in `r`/`c` and duplicate values in `v`.
- **Plotter Enhancements & Modernization**:
  - `Plotter.finalize()` accepts `title`, `xlabel`, `ylabel`, `tight_layout`, and stylesheet names via `style=`.
  - Added chainable `Plotter.show()` method for interactive inspection.
  - Supports plotting wide data directly with optional `y` (e.g. `df.pt.plot(kind="barh", x="day")`).
  - Seamlessly handles integer column coordinates when column index is integer-typed.
  - Safely links `sharex`/`sharey` across 3+ axes in mosaic layouts.
- **Aggregation & Reshaping**:
  - `agg_df` accepts comma-separated grouping strings (e.g. `by="day,sex"` or `by="species,island"`).
  - `wide()` supports reshaping when all columns are partitioned into `c` and `v` (no id columns).
  - `long()` supports bracketed multi-word column names in `cols` and `id_vars`.

### Changed & Refactored
- **Plotter Simplified (Path A)**:
  - Removed implicit aggregation and `aggfunc=`/`aggregate=` parameters from `Plotter`.
  - `Plotter` focuses exclusively on clean visualization—aggregate first with `df.pt.agg()` or `df.pt.pivot()`.
- **Strictly Honest Error Handling Principle**:
  - Standardized on *"Be generous in what you accept, but strictly honest when ambiguous"*.
  - Replaced magical column renaming with clear, descriptive `ValueError` and `TypeError` exceptions.
  - `agg_df` checks for duplicate output column names and collisions with grouping columns.
  - Grouped KDE/density requires at least 2 non-null observations per group, raising `ValueError` on singletons.
  - Validates that `by` column exists across all plot kinds (`line`, `bar`, `barh`, `area`, `scatter`, `kde`, `hist`, `box`).
  - CLI `-plot` wraps user errors cleanly with exit code 2.
  - `safe_reset_index()` raises `ValueError` when an index level name collides with an existing column.
  - `long()` raises `ValueError` if `cols` and `id_vars` overlap.
  - `wide()` raises `ValueError` if `c == v` or if `c`/`v` are in `index`, and strictly limits to 1-to-1 reshaping.
  - `qry()` raises `ValueError` when non-numeric interval bounds are passed to numeric columns.
  - `-rename` rejects conflicting mappings for the same column with a clear error.
  - `-value_counts` fails cleanly when both `count` and `n` exist in columns.
- **Uniform `dropna=False` Default**:
  - Standardized `dropna=False` default across all operations (`pivot`, `wide`, `agg`, `mutate`, `freq`, `value_counts`, and plotting).
  - When `dropna=True` is passed to `Plotter`, NA values in `x` or `by` are dropped cleanly before reshaping/plotting across heatmap, line, bar, barh, and area.

## [3.6.0] - 2026-09-27

### Breaking Changes
- **Grouped Mutations (`group_x` removed)**:
  - Folded grouped window mutations directly into `pt.mutate(df, by=...)` / `df.pt.mutate(by=...)`.
  - `group_x` is completely eliminated from the package namespace, DataFrame accessor, and CLI flags.
- **CLI `-drop` flag retired**:
  - Retired `-drop` in favor of unified negative column selection on `-select` (e.g. `-select -col1,-col2` or `-select exclude=col1,col2`).
- **CLI output routing unified under `-o, --output`**:
  - Removed redundant `-convert` and `-to_clip` flags.
  - `-o <filename>.<ext>`: exports to explicit file path (format inferred from extension: `csv`, `tsv`, `parquet`, `json`, `jsonl`, `xlsx`).
  - `-o <format>`: in-place conversion adjacent to source file (`csv`, `parquet`, `json`, `jsonl`, etc.) or batch conversion for glob matches (e.g. `pytae 'data/*.parquet' -o csv`).
  - `-o clip` / `-o clipboard`: copies result to clipboard while suppressing stdout.
  - Terminal non-DataFrame inspection flags (`-shape`, `-cols`, `-dtype`, `-nulls`, `-info`) are barred from tabular file export but support clipboard copy via `-o clip`.
- **Aggregation syntax standardized**:
  - Unified on `by=` parameter across library (`pt.agg(df, by="category", ...)`) and CLI (`-by category -agg ...`), deprecating auto-grouping and legacy pandas agg syntax.
- **Python Library Crosstab**:
  - Removed `pt.crosstab` from the Python library API in favor of pandas native `pd.crosstab` while keeping and expanding `-crosstab` in the CLI.

### Added
- **Library Verbs**:
  - `pt.mutate()` / `df.pt.mutate()`:
    - Added `by=` parameter for grouped window mutations.
    - Added `dropna=` keyword argument for grouped mutations to cleanly align output lengths with missing groups.
    - Accepted positional string expressions (`pt.mutate(df, "rev = price * qty")`) and plain dictionaries (`pt.mutate(df, {"rev": "price * qty"})`) alongside `**kwargs`.
  - `pt.select()` / `df.pt.select()`:
    - Support for negative column selection (e.g. `pt.select(df, "-col1", "-col2")`).
    - Added `exclude=` keyword argument for column exclusion.
    - Support `pt.everything` / `everything()` as either class or callable instance.
  - `pt.handle_missing()` / `df.pt.handle_missing()`:
    - Preserves categorical dtypes.
    - Added `numeric_fill` parameter for custom numeric placeholder replacement.
    - Added `cols=` parameter to target missing value imputation on specific subsets of columns.
  - `pt.shape` (`long()` / `wide()`):
    - `long()` supports melting non-numeric columns via explicit `cols` and `id_vars`.
    - `wide()` supports explicit index specification.
  - `safe_reset_index()` utility:
    - Safely resets DataFrame index, raising an informative ValueError if an index level name collides with an existing column to prevent ambiguous duplicate headers.
  - Standardized bracket syntax (`[Column Name]`) across all verbs and queries for columns with spaces and special characters.
  - Type checking: Added `py.typed` marker (PEP 561 compliance) for strict type checker integration.
- **CLI Features**:
  - Output directory `-od <DIR>`: directs outputs to a target directory with automatic stem collision avoidance.
  - Transparent gzip compression when output extension ends in `.gz` (e.g. `-o data.csv.gz`).
  - Dataset diffing via `-diff <other_file>` to compare schema and data between two datasets.
  - Streaming & chunked IO via `-chunk_size <N>` and `-progress [N]` progress bars.
  - Parquet metadata inspection via `-meta` without reading the entire dataset.
  - Built-in terminal pager `-p` for long and wide tabular outputs.
  - Unquoted wildcards and multiple positional files support for multi-file operations.
  - Enhanced `-crosstab`: added percentage calculations, margins, formatting, and row index preservation for downstream chaining (`-sort_by`, `-qry`, `-select`, `-head`).
- **Plotting Subsystem**:
  - Auto-faceting support for wrapped subplots and grid layouts.
  - Standalone `pt.finalize(**kwargs)` function for post-processing matplotlib figures.
  - Support for dictionary-based line styling and width mapping with integer/non-string series keys (`style={0: '--'}`).
- **Documentation & Testing**:
  - Modularized CLI guides into dedicated feature guides in `docs/cli/`.
  - Normalized all documentation filenames to lowercase (`readme.md`, `changelog.md`, `contributing.md`, `library.md`, `plotting.md`).
  - Added automated notebook runner `scripts/run_notebooks.py` covering all 8 tutorials across `docs/library/` and `docs/plotting/`.
  - Added full reference manual in `reference/pytae_reference.txt`.

### Fixed
- Fixed scalar conditions in `if_else` and `case_when` returning 0-d numpy arrays that boxed into length-1 Series, causing NaNs on remaining rows.
- Fixed duplicate column collisions on `_write_jsonl` and `sample` when exporting crosstab DataFrames.
- Fixed duplicate `is_clip` check in CLI `-crosstab` that overwrote rounded clipboard copies with raw unrounded values.
- Fixed clipboard export in `-head` and `-tail` to include row labels when working with indexed tables.
- Fixed `finalize()` font size reset on tick parameters to apply across both x and y axes after spine displacement.
- Fixed `qry()` handling for multiple conditions on the same column without overwriting previous conditions.
- Fixed delimited file readers scanning entire files for shape/dtype discovery when quoted newlines were present.
- Fixed heatmap numeric cell annotation contrast and luminance thresholding.
- Fixed duplicate row index collisions in grouped histogram and density plots.


## [3.5.2] - 2026-09-24

### Breaking Changes
- `to_clip()` has been removed from the package namespace (`pt.to_clip()`) and DataFrame accessor (`df.pt.to_clip()`). Clipboard copying is now attached directly as methods on `pd.DataFrame.to_clip()` and `pd.Series.to_clip()` upon `import pytae`, allowing direct calls like `df.to_clip()` and `df.head().to_clip()`.

### Added
- First-class `df.to_clip()` and `s.to_clip()` methods attached directly to `pd.DataFrame` and `pd.Series` on `import pytae`, restoring convenient clipboard copying without needing `.pt.` (`df.to_clip()` / `df.head().to_clip()`).
- Documented handling of spaced column names across verbs in `README.md` and `docs/LIBRARY.md` (dictionary unpacking for creation, bracketed/backtick identifiers for formulas).
- Added optional extras (`pytae[plot]`, `pytae[sql]`) to the `Install` section and added a Key Conventions & Syntax Cheat Sheet table in `README.md`.

## [3.5.1] - 2026-09-23

### Added
- Flexible argument support in `pt.qry()` and `df.pt.qry()`: accepts positional string expressions (e.g. `df.pt.qry("bill length mm > 40")`) and plain dictionaries (e.g. `df.pt.qry({"bill length mm": "> 40"})`) for querying columns with spaces without dictionary unpacking, alongside `**kwargs`.
- First-class CLI `-rename` support: can be used standalone or anywhere in a pipeline without requiring `-convert`.

### Changed
- Consolidated `docs/FLAGS.md` into `docs/CLI.md` with an integrated "Which flag should I use?" decision guide, polarity chaining patterns, and `c=`/`v=`/`a=` parameter conventions.

## [3.5.0] - 2026-09-22

### Breaking Changes
- **Python library: Strict keyword arguments only** for `qry()`, `mutate()`, and `agg_df()`.
  - Positional dictionaries or strings now immediately raise a helpful `TypeError` instructing users to use keyword arguments (e.g. `df.pt.mutate(bmi='...')`, `df.pt.qry(col='> 5')`, `df.pt.agg_df(body_mass_g='mean')`). File loading via `@filename.txt` remains supported as positional string.
  - Removed dictionary acceptance across `qry()`, `mutate()`, and `agg_df()`.
- **CLI: Strict separation between assignments (`=`) and translation mappings (`:`):**
  - Assignments (`-mutate`, `-agg_df`, `-qry`) strictly require `=`. Colon (`:`) is rejected and raises an informative error.
  - Translation mappings (`-rename`, `-replace_values`'s `v=`) strictly require `:` (`old:new`). Equals (`=`) is rejected and raises an informative error, directly matching Python dictionary syntax (`{'old': 'new'}`).

### Changed
- Library verbs are package functions (`import pytae as pt` then `pt.select(df, ...)`)
  **and** a DataFrame accessor (`df.pt.select(...).pt.agg_df(...)`). Mix with pandas
  methods: `df.rename(...).pt.agg_df(...)`. Notebooks use the accessor chain.
- Notebook formatting standard: every method call in a chain begins on its own line across all notebooks.

### Added
- `docs/FLAGS.md` — one-page "which flag?" card. Pytae kwargs stay `c=` / `v=` / `a=`.
- Ruff in CI (`ruff check src tests`) and mypy on 3.12 (`mypy` over `src/pytae`).
- `df.pt` DataFrame accessor; `@` locals in `df.pt.mutate()` resolve in the calling scope.
- Library `pt.sql(df, query)` / `df.pt.sql(query)` — same duckdb/`data` table as CLI `-sql`
  (`pip install pytae[sql]`). Extra keyword frames register as extra tables. Supports
  loading queries from `@query.txt` and bracketed/backtick column identifiers (`[col a]`, `` `col a` ``).
- Enhanced `pt.mutate()` / `df.pt.mutate()`:
  - Clean keyword arguments syntax (`col="expr"`, `col=callable`, or constants).
  - Supports loading mutation specs from file (`@specs.txt`), multiline specs, and comment lines starting with `#`.
  - Added built-in `coalesce(*cols, default)` functional helper for first non-null resolution.
  - `case_when()` now supports `default=` keyword argument and flat alternating pairs (`case_when(c1, v1, c2, v2, default=d)`).
  - Bracketed identifiers (`[col a]`) and backticks (`` `col a` ``) are now fully supported in Python eval fallback mode.
  - Added explicit `params=` dictionary for passing scoped variables without global/frame inspection.
- Enhanced `pt.agg_df()` / `df.pt.agg_df()`:
  - Accepts column keyword arguments directly (e.g. `df.pt.agg_df(body_mass_g="mean", count="n")`), with group columns and aggregated output columns following argument order.
- CLI enhancements:
  - Standardized on `=` for assignments (`-mutate`, `-agg_df`, `-qry`) and strict `:` for mappings (`-rename`, `-replace_values`).
  - `-sql` and `-mutate` support loading queries/specs from quoted and unquoted files (`@query.txt`, `'@query.txt'`) with relative, absolute, and Windows backslash paths.
  - `-sql` supports bracketed column names (`[col a]`).
  - `-qry` supports direct comparison expressions (`col > 5`), operator prefixes (`col = > 5`), and assignment delimiters (`col= > 3500`, `col=>3500`, `col=3500`).
  - `-concat` and `-merge` support unquoted comma-separated lists (`frames=a,b,c`, `on=id:id,code:code`).

## [3.4.3] - 2026-09-20

### Added
- CLI `-drop`: subtract exact column names at that point in the pipeline (`df.drop(columns=...)`).
  Names only — no `dtype=` / `contains=` / `regex=` / slices (those stay on `-select`). Remaining
  columns keep their order. Repeatable; missing names error with a typo hint; dropping every
  remaining column is an error.

### Documentation
- `docs/CLI.md`: `-mutate` example for string concat via `species.str.cat(island, sep='_')`
  (pandas `eval()` does not support `+` for strings).

## [3.4.2] - 2026-09-20

### Changed
- CLI specs are two families: **kwargs** (`key=value`, quote a value only when it contains a
  comma) and **names/mappings** (`a,b` lists and `name: payload` for `-qry`/`-mutate`/`-rename`
  / slices). Examples, help, and `docs/CLI.md` follow that; simple values are unquoted.
- `-sort_by` is one spec (`-sort_by "species,body_mass_g desc"`), not a column list plus a
  sibling `asc`/`desc` argv token.
- `-agg_df` no longer accepts Python list/dict literals. Use a name (`mean`), a comma list
  (`mean,sum`), or a mapping (`body_mass_g: mean, n: n`).
- `-dropna` is the only NA-key switch for `-group_x` and `-wide` as well (the `dropna=` spec
  keys are gone). `-group_x`'s undocumented `observed=` CLI key is gone too.
- `mutate()` / `-mutate` `case_when()`: the catch-all is a last argument with no colon
  (`case_when(x >= 4500: 'large', x >= 3500: 'medium', 'small')`), like SQL ELSE, not
  `True: 'small'`.

## [3.4.1] - 2026-09-20

### Changed
- CLI: an `unrecognized arguments: ...` error (typically caused by forgetting to wrap a
  multi-word `-select`/`-qry`/`-mutate`/etc. spec in shell quotes, so the shell splits it
  into extra argv tokens) now includes a hint to wrap the whole spec in quotes, when the
  leftover tokens look like plain words rather than another `-flag`. `docs/CLI.md`'s
  Quoting conventions section now explains the two separate layers of quoting (shell vs.
  pytae's own internal syntax) and fixes an inaccurate `-select` table row that implied
  quoting was required for column names with spaces (it never was — only an embedded
  comma requires it). CLI examples now wrap every `-select` spec in `""` the same
  way as `-qry`/`-mutate` (still optional when the spec has no spaces; one
  counterexample in Quoting conventions is left unquoted on purpose).

## [3.4.0] - 2026-09-20

### Added
- `mutate()` / `-mutate`: create or overwrite columns from a `qry()`-style spec string, each entry evaluated in order via pandas `eval()` — a plain formula per column, no lambda required (e.g. `df.mutate("bmi: body_mass_g / bill_length_mm ** 2")`, or `-mutate "bmi: body_mass_g / bill_length_mm ** 2"` on the CLI). Entries are `"new_col: expression"`, comma-separated for multiple in one call; quoting the key is optional (matches `-qry`), but column names *inside* the expression must stay unquoted, since `eval()` treats a quoted name as a string literal, not a column reference. Later entries can reference columns derived by earlier entries in the same call. New `notebooks/mutate.ipynb` walkthrough.
- `mutate()` / `-mutate`: dplyr-style `if_else(condition, true_value, false_value)` and `case_when(cond1: val1, cond2: val2, ..., True: default)` expression forms, e.g. `df.mutate("weight_class: if_else(body_mass_g > 4000, 'heavy', 'light')")` or `df.mutate("size_class: case_when(body_mass_g >= 4500: 'large', body_mass_g >= 3500: 'medium', True: 'small')")`. These are detected by name and evaluated via `np.where()`/`np.select()` instead of `eval()` (which cannot express conditionals). `case_when()` conditions are checked in order, first match wins; the literal `True` is an optional catch-all default (matches dplyr's `TRUE ~ default`) and must be listed last — unmatched rows are `NaN` without it. Branches with incompatible dtypes (e.g. a string branch and a numeric branch) fall back to an object array instead of crashing with numpy's `DTypePromotionError`.
- `mutate()`: expressions can reference a local variable from the calling scope with an `@` prefix (e.g. `df.mutate("heavy: body_mass_g >= @threshold")`), matching pandas `eval()`/`query()`'s own `@` convention. Library-only — `-mutate` on the CLI now gives a dedicated error naming this (`@` locals aren't available there since the CLI has no user Python scope to resolve them against).
- `qry()` / `-qry`: new tuple-condition operators — `('startswith', v)`, `('endswith', v)`, `('contains', v)`, `('regex', pattern)` for string matching (backed by pandas' `.str` accessor; missing values never match, `na=False`; `'contains'`/`'regex'` both search anywhere in the string like `re.search`, `'regex'` is `'contains'` with `regex=True`; `startswith`/`endswith` also accept a list of prefixes/suffixes), plus one-element-tuple null checks `('isna',)`/`('notna',)`. E.g. `df.qry({"species": ("startswith", "Ad")})` or `-qry "species: ('startswith', 'Ad')"` on the CLI.
- `Plotter.facet(df, by, ncols=None, **plot_kwargs)`: build a small-multiples grid, one axis per distinct value of `by`, plotting the same chart (`x=`/`y=`/`kind=`/etc.) on each group's own subset of rows. Grid defaults to a roughly square layout (`ceil(sqrt(n))` columns) when `ncols=` is omitted; when the group count doesn't tile the grid exactly (e.g. 5 groups in a 2-column grid needs 3 rows, one cell left over), the leftover cell(s) are left blank rather than becoming empty/unused axes. Each facet's axis is keyed by its group's stringified value (e.g. `plotter.axd["Adelie"]`) and titled with it by default (`titles=False` to disable); a `category`-dtype `by=` column keeps its own defined category order instead of being sorted (`sort=False` for first-appearance order on a plain column). `plotter.df` is restored to the full input frame afterward (not left as just the last group's subset); `ncols` less than 1 raises a clear error. Returns a regular `Plotter` — chain `.finalize()` etc. as usual. New docs/PLOTTING.md "Faceting" section.
- `Plotter`: each plot kind now validates its own required kwargs up front (e.g. `kind="scatter"` needs `x=`/`y=`, `kind="pie"` needs `by=`/`y=`, `kind="hist"`/`kind="kde"`/`kind="density"` need `column=` only — `by=` is optional for a single-column density, matching `hist`) and raises a clear `ValueError` naming what's missing, instead of a cryptic pandas `KeyError` surfacing later from deep inside pivoting.
- `Plotter.save(path, **kwargs)`: thin chainable wrapper around `fig.savefig(path, **kwargs)`.
- `Plotter.supported_kwargs(kind)`: lists which kwargs are ignored (with a warning) for a given plot kind, plus pytae's own control kwargs (`on=`, `print_data=`, `clip_data=`, `aggregate=`, …) that are never forwarded to pandas.
- `Plotter.finalize(style=True)`: set `style=False` to skip pytae's opinionated spine-hiding/blank-axis tick cleanup and leave matplotlib's own defaults untouched.

### Changed
- `Plotter` internals: the duplicated per-kind "filter kwargs + warn about unsupported ones" boilerplate across `_plot_scatter`/`_plot_hexbin`/`_plot_pie`/`_plot_line`/`_plot_other`/`_plot_density`/`_plot_hist` is now driven by one `_KIND_SPECS` table + a shared `_prepare_plot_kwargs()` helper — no behavior change, just less duplicated code (also fixes `_plot_other` computing the same pivot twice). `_adjust_ticks_and_spines()` now detects a blank/unplotted axis via matplotlib's own `Axes.has_data()` instead of pattern-matching its default tick label text (`['0.0', '0.2', ..., '1.0']`), which could previously misfire if real data happened to span exactly that range.
- `.dat` files now default to `latin-1` encoding (both reading and writing) instead of falling through to pandas' own inference. `.txt`/`.csv` are unaffected (still pandas' default inference); `-encoding`/`encoding=` still override it explicitly either way.
- `-clean_columns`'s `strip_special` now keeps the `fill` character in place instead of stripping it (it already removed all other punctuation, including quotes) — e.g. `-clean_columns "strip_special,fill='-'"` keeps `-` while still removing quotes/`%`/`$`/etc.
- New Quoting conventions section in `docs/pytae.md` summarizing where quoting matters (protecting an embedded comma/colon) vs where it's just optional/harmless.

### Documentation
- `notebooks/plotter.ipynb` significantly expanded: one clean example per plot kind on a different bundled dataset each, `aggregate=False`/`dropna=` controls, faceting variations (`sort=False`, category-dtype order, `titles=False`), per-axis legends, mosaic as a list-of-lists, an error-handling cookbook, and a "post-plot manipulation" section covering real-world dashboard patterns (building a mosaic by looping over groups, custom tick formatting, per-axis-type y-limits/percent formatters, reference lines that still land in a consolidated legend, mirrored/diverging-bar tick relabeling) plus general matplotlib fine control (data labels on bars, highlighting a single bar, shaded regions with annotated peaks, and an embedded inset zoom `Axes`).
- `docs/PLOTTING.md`'s "Enhancing a plot after finalize()" section expanded with worked examples for per-axis-type branching and data-labels/highlighting/annotations, matching the notebook.

### Performance
- `-sql`: when it's the first thing to touch the view, duckdb now scans the source `.parquet`/`.csv`/`.txt`/`.dat` file **directly** instead of first materializing it through pandas — measured ~2-4x faster on a 5M-row benchmark (parquet: ~1.5s → ~0.5s; CSV: ~2.5s → ~0.6s), and correctness-verified identical results. Falls back to the previous pandas-backed-view behavior (unchanged) when something earlier in the pipeline already ran, `-progress` was passed, the source is `.sas7bdat` (no native duckdb reader), or a non-UTF-8 `-encoding` was given.

### Fixed
A full-repo review (`.grok/full-review-2026-09-20.md`) surfaced ~20 issues; all were reproduced, verified, and fixed in this pass:
- `handle_missing()` no longer corrupts non-string `object` columns (e.g. bool/mixed-Python-object columns): only columns actually holding strings (including pandas' own dedicated string dtype) get `fillna`/`.str.strip()`; `fillna(0)` is now scoped to numeric columns only, so datetime/bool columns are left alone.
- `select(dtype="numeric"/"non_numeric")` and `exclude_dtype="numeric"` now include unsigned integers (`uint8/16/32/64`), matching pandas' own `select_dtypes(include="number")`.
- `select(dtype="datetime")` now includes timezone-aware datetime columns, not just naive ones.
- `select(dtype=(...))` (a tuple) is now accepted like a list, instead of raising `UnboundLocalError`.
- A column name containing `:` (e.g. `"a:b"`) is now matched exactly before `:` is treated as slice syntax.
- Integer column names no longer crash `select(contains=/startswith=/endswith=)` or `clean_columns()` — names are coerced to `str` first, same as the existing `regex=` path.
- `agg_df([...])` (single remaining aggregation, list form) now raises a clear error instead of silently overwriting a real column named `n` with row counts, when both are requested together.
- `clean_columns(dedupe=True)` no longer emits new duplicate names — a generated `_N` suffix is skipped if it collides with an existing column.
- `group_x()` now raises a clear error instead of silently overwriting an existing `n`/`x` column, and raises a friendly message (instead of pandas' raw `"No group keys passed!"`) when there are no non-numeric columns to group by and none were given explicitly.
- `replace_values(..., exact=False)` on a non-string column now raises a clear error instead of crashing with a raw `TypeError` (or silently no-op-ing).
- `-nrows` is no longer ignored by `-head`/`-tail`: both now route through the same `nrows`-aware load path when `-nrows` is set.
- Reading an empty parquet file with `-progress` or `-nrows` set no longer drops the column schema.
- CSV/TXT `shape()` (and therefore `-tail`) no longer miscounts rows when a field contains an embedded newline inside quotes; row counting now goes through the real CSV parser instead of counting raw physical lines. An empty CSV/TXT file now raises a friendly `ValueError` instead of pandas' raw `EmptyDataError`.
- `-merge how=cross` no longer requires `on=` (pandas cross joins don't take one); passing `on=` together with `how=cross` is now a clear error instead of a confusing pandas failure.
- `Plotter`'s pie chart no longer overwrites `self.df` with its aggregated 2-column frame — later `.plot()` calls in the same chain see the original data again, like every other plot kind.
- An unknown mosaic `on=` key now raises a clear error instead of silently drawing on axis `'A'`.
- `get_pivot_data()` no longer casts a datetime `x` column to `object` (which broke matplotlib's date locators) — only non-datetime x columns are cast.
- `pytae.sample()`/`sample_data[...]` now return a copy each time, so mutating a returned DataFrame no longer poisons later calls in the same process.
- `sample_data.keys()` now returns a plain tuple of dataset names instead of a bare `KeysView` repr.
- `long()` now raises a clear error when there are no numeric columns to melt, instead of silently returning an empty result.
- README.md/docs/LIBRARY.md's scatter example now uses `c=`/`cmap=` (which `kind="scatter"` actually reads) instead of `by=` (which it ignores).
- `-file`'s help text no longer claims it "requires -merge" (it also accepts `-concat`/`-sql` as the first op); `-dlim`'s help/docs no longer claim it applies to `.sas7bdat` (which has no delimiter concept); `-file`'s "need at least two entries" error message no longer name-drops `-merge` specifically.
- Added `.venv/` to `.gitignore`; added Python 3.11 to the CI test matrix so it matches the `classifiers` already listed in `pyproject.toml`.

A follow-up re-review (`.grok/full-review-rerun.md`) confirmed all of the above and found a handful of new issues in the same session's new APIs, also fixed:
- `mutate()`'s `if_else()`/`case_when()` no longer crash with numpy's `DTypePromotionError` when branches/choices have incompatible dtypes (e.g. a string branch and a numeric branch) — falls back to an object array.
- `qry()`'s string operators (`startswith`/`endswith`/`contains`/`regex`) on a non-string column now raise a clear `ValueError` naming the column and dtype instead of a raw pandas `AttributeError`; `startswith`/`endswith` now accept a list of prefixes/suffixes (coerced to the tuple pandas' own `.str.startswith()`/`.str.endswith()` expect) instead of raising `TypeError`.
- `Plotter.facet()` now restores `plotter.df` to the full input frame afterward (was left as just the last group's subset) and rejects `ncols < 1` instead of silently falling back to the default layout.
- `kind="kde"`/`"density"` no longer require `by=` — a single-column density works with just `column=`, matching `hist`.
- `-mutate` with an `@name` local-variable reference now gives a dedicated CLI error instead of a confusing "local variable is not defined" message; the `@` detector now ignores `@` characters inside quoted string literals (e.g. `-mutate "flag: s == 'a@b'"`), so it no longer misfires on emails or other literal `@` text.
- `-qry`: column-name keys can now be quoted or unquoted (`species: 'Adelie'` == `'species': 'Adelie'`), matching `-select`'s convention. Values still need Python-literal quoting when they're strings (e.g. `'Adelie'`); numbers/tuples/lists already worked unquoted.
- `-rename`: quoting an old/new name (e.g. `-rename "'old col':'new col'"`) previously left the literal quote characters in the parsed mapping, silently renaming nothing since no real column matched. Quoting is now optional and stripped if present, matching the rest of the CLI.
- `plot`/`dev` extras now include `scipy` (pandas' own `kind="kde"`/`"density"` backend imports it internally) — previously only the `notebooks` extra had it, so a `pip install pytae[dev]`/`pytae[plot]`-only environment could hit `ModuleNotFoundError: No module named 'scipy'` the moment a kde/density chart was actually rendered.

## [3.3.1] - 2026-09-13

### Changed
- **Breaking:** `-replace` renamed to `-replace_values`, matching the new `replace_values()` library method (see below). Same syntax/behavior, just the flag name.

### Added
- `clean_columns()` and `replace_values()` added to the library (`other_utilities.py`, registered on `pd.DataFrame`) — the same logic the `-clean_columns`/`-replace_values` CLI flags use, now callable directly in Python. `replace_values()` is named to avoid shadowing pandas' own `DataFrame.replace()`; its parameters (`v=`, `c=`, `exact=`) match the CLI flag's key names.

## [3.3.0] - 2026-09-13

### Added
- `-replace` flag: replace values at a point in the pipeline (pandas `replace()`). Value is `key=value` tokens: `v=` (required) an `old:new` mapping, `c=` (optional) restrict to specific columns, `exact=` (optional bool, default `true`) — `true` matches whole cell values, `false` matches a substring anywhere in the cell.
- `-clean_columns` flag: clean column header names, in a fixed order (`strip` -> `strip_special` -> `squeeze` -> `fill` -> `case` -> `dedupe`). Booleans accept a bare key as shorthand for `=true`; `fill` defaults to `'_'` when bare; `case` (`lower`/`upper`/`proper`) always needs a value.
- `-file`/`-merge`/`-concat` flags: a new multi-file pipeline mode. `-file "path1=alias1; path2=alias2"` loads two or more named files (with optional per-file `,dlim=`/`,encoding=` overrides) instead of the positional `path`; `-merge` (pandas `merge()`, repeatable) or `-concat` (pandas `concat()`, always resets the index, repeatable) then combine them — both accept the literal alias `df` to fold in one more file onto the running result. See `docs/CLI_MULTI_FILE.md`.
- `-sql` extended: usable as the founding op in `-file` mode instead of `-merge`/`-concat`, with every `-file` alias registered as its own queryable duckdb table (in addition to `df`, once something has produced a current view).
- `docs/CLI_MULTI_FILE.md`: dedicated reference for `-file`/`-merge`/`-concat`.
- `docs/PLOTTING.md`: dedicated `Plotter` reference with rendered example images (scatter, grouped bar, pie, secondary axis, multi-panel mosaic dashboard, post-`finalize()` axis looping) using pytae's bundled sample datasets.

### Changed
- The positional `path` argument is now optional — required only when not using `-file`; `-file` and the positional `path` are mutually exclusive.
- `src/pytae/cli.py` split into `cli.py` (argparse + main loop), `cli_parsing.py` (flag-value parsers), and `cli_pipeline.py` (`_Pipeline` + ordered argparse actions) — internal refactor, no behavior change.
- `README.md` restructured into three top-level sections, in order: CLI, Plotting, Library.
- `docs/CLI.md`: intro updated to mention `-replace`/`-clean_columns`/`-merge`/`-concat`; its Plotting and Multi-file sections now summarize and link out to the new dedicated `docs/PLOTTING.md`/`docs/CLI_MULTI_FILE.md` pages instead of holding the full reference inline.

## [3.2.0] - 2026-09-13

### Added
- `-sql` flag: run a real SQL query against the current view at that point in the pipeline, via `duckdb` (optional dependency, install with `pip install pytae[sql]`). The view is queryable as table `df` only — no file-derived alias, since the file is already named on the command line. `table` is a reserved SQL keyword and is deliberately **not** registered as an alias.
- `pytae[sql]` optional extra (`duckdb>=0.9`), needed for `-sql`.
- `pytae[plot]` optional extra (`matplotlib`), needed for `Plotter`.
- `scripts/run_notebooks.py` executes every notebook under `notebooks/` end-to-end and is wired up as a local pre-commit hook (`.githooks/pre-commit`, enable with `git config core.hooksPath .githooks`); deliberately **not** part of the `pytest` suite. `pytae[notebooks]` optional extra (`nbclient`, `nbformat`, `ipykernel`, `scipy`) provides what it needs to run.

### Changed
- Docs: `-rename` is now cross-linked from the `-sql` section as an alternative to escaping spaced column names, and surfaced in the Contents TOC (`Conversion — -convert / -rename`).

## [3.1.2]

### Added
- `-crosstab`'s `index=` now accepts a comma-separated list of columns for a multi-level row index (like `-group_by`); `columns=` stays single-column.
- `-crosstab`'s `margins_name=` to rename the totals row/column (requires `margins=true`).
- `-wide`'s `a=` now accepts `'n'` as an alias for pandas' `'size'` (group row count), matching `agg_df`'s convention — `-wide "c=...,v=...,a='n'"` now works as a one-step count matrix.
- `docs/CLI.md`: new "Pandas defaults vs pytae-specific" section, with `-wide` vs `-crosstab` and `-agg_df` vs `-group_by`+`-agg` comparison subsections.

### Fixed
- `docs/CLI.md`: a `-crosstab` example used `dropna=false` as a spec key, which was never actually supported — `dropna` is the shared top-level `-dropna` flag; corrected to `-crosstab "..." -dropna false`.
- `docs/CLI.md`: an early draft of the "Pandas defaults" table incorrectly listed `-dropna` as pytae-specific; it's pandas' own `dropna=` parameter (shared by `groupby()`/`value_counts()`/`crosstab()`), just exposed as one CLI flag instead of repeated per operation.

## [3.1.1]

### Added
- `-seed` flag: random seed for `-sample`, for reproducible rows.
- `-frac` flag: sample a fraction of rows instead of `-sample`'s row count.
- `-crosstab` flag: cross-tabulate two columns into a matrix (pandas `crosstab()`), with `values=`/`aggfunc=`, `normalize=`, and `margins=`; honors the shared `-dropna` flag.
- Integration tests against pytae's bundled sample datasets (`tests/conftest.py`, `tests/test_cli_sample_datasets.py`).

### Fixed
- `docs/CLI.md`: `-qry ... -select dtype=numeric -agg_df mean` recipe errored on real data (`-select dtype=numeric` strips every group-by column `-agg_df` needs); corrected to `-qry ... -agg_df mean`.
- `docs/CLI.md`: the `-wide` reshape examples referenced `tall.csv` before the example that creates it; reordered so it's created first.
- `README.md` / `docs/CLI.md`: dropped unnecessary `{}` braces from `-qry` examples (braces are optional).

### Changed
- `docs/CLI.md`: reorganized with a linked table of contents, real section headers, grouped flag-reference tables, and a new "Sample datasets" section showing how to use pytae's bundled datasets (`penguins`, `tips`, `titanic`, `diamonds`, `mpg`, `flights`, …) directly from the CLI.
- `docs/CLI.md`: examples now run against the real bundled `penguins.parquet` (and others) instead of a generic, unverifiable `data.parquet` placeholder.
