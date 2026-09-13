# Changelog

All notable changes to this project are documented in this file.

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
