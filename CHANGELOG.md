# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- `mutate()` / `-mutate`: create or overwrite columns from a `qry()`-style spec string, each entry evaluated in order via pandas `eval()` — a plain formula per column, no lambda required (e.g. `df.mutate("bmi: body_mass_g / bill_length_mm ** 2")`, or `-mutate "bmi: body_mass_g / bill_length_mm ** 2"` on the CLI). Entries are `"new_col: expression"`, comma-separated for multiple in one call; quoting the key is optional (matches `-qry`), but column names *inside* the expression must stay unquoted, since `eval()` treats a quoted name as a string literal, not a column reference. Later entries can reference columns derived by earlier entries in the same call. `eval()` has no if/else — a two-branch numeric condition can be built with boolean arithmetic, but string outcomes or 3+ branches need plain pandas (`df.assign(col=lambda d: np.where(...))`) instead. New `notebooks/mutate.ipynb` walkthrough.
- `mutate()` / `-mutate`: dplyr-style `if_else(condition, true_value, false_value)` and `case_when(cond1: val1, cond2: val2, ..., True: default)` expression forms, e.g. `df.mutate("weight_class: if_else(body_mass_g > 4000, 'heavy', 'light')")` or `df.mutate("size_class: case_when(body_mass_g >= 4500: 'large', body_mass_g >= 3500: 'medium', True: 'small')")`. These are detected by name and evaluated via `np.where()`/`np.select()` instead of `eval()` (which cannot express conditionals), closing the string-outcome/3+ branch gap noted above without needing a lambda. `case_when()` conditions are checked in order, first match wins; the literal `True` is an optional catch-all default (matches dplyr's `TRUE ~ default`) and must be listed last — unmatched rows are `NaN` without it. `notebooks/mutate.ipynb` updated with `if_else()`/`case_when()` examples in place of the old "no if/else" limitation note.

### Fixed
- `-qry`: column-name keys can now be quoted or unquoted (`species: 'Adelie'` == `'species': 'Adelie'`), matching `-select`'s convention. Values still need Python-literal quoting when they're strings (e.g. `'Adelie'`); numbers/tuples/lists already worked unquoted.
- `-rename`: quoting an old/new name (e.g. `-rename "'old col':'new col'"`) previously left the literal quote characters in the parsed mapping, silently renaming nothing since no real column matched. Quoting is now optional and stripped if present, matching the rest of the CLI.

### Changed
- `-clean_columns`'s `strip_special` now keeps the `fill` character in place instead of stripping it (it already removed all other punctuation, including quotes) — e.g. `-clean_columns "strip_special,fill='-'"` keeps `-` while still removing quotes/`%`/`$`/etc.
- New [Quoting conventions](docs/CLI.md#quoting) section in `docs/CLI.md` summarizing where quoting matters (protecting an embedded comma/colon) vs where it's just optional/harmless.

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
