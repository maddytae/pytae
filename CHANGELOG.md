# Changelog

All notable changes to this project are documented in this file.

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
