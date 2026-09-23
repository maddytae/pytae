# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

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
- New [Quoting conventions](docs/CLI.md#quoting) section in `docs/CLI.md` summarizing where quoting matters (protecting an embedded comma/colon) vs where it's just optional/harmless.

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
