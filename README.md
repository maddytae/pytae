# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Pandas helpers for everyday data-science tasks (filtering, selection, reshaping, aggregation, plotting), plus a `pytae` CLI that exposes the same operations for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`) without writing any Python.

## Install

```bash
pip install pytae             # Core library and CLI
pip install "pytae[plot]"      # Adds Plotter (matplotlib, scipy)
pip install "pytae[sql]"       # Adds SQL engine (duckdb)
```

## CLI

```bash
pytae data.parquet -head
pytae data.parquet -qry "species='Adelie'" -select "species,body_mass_g" -o subset.csv
pytae data.parquet -sql "select species, avg(body_mass_g) from data group by species"
pytae -file "data1.parquet=df1; data2.parquet=df2" -merge "left=df1,right=df2,on=id"
```

See [docs/CLI.md](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) for the full CLI reference and flag guide, and [docs/CLI_MULTI_FILE.md](https://github.com/maddytae/pytae/blob/master/docs/CLI_MULTI_FILE.md) for `-file`/`-merge`/`-concat`.

## Plotting

`Plotter`: method-chainable plots on top of `pandas.plot()` (`pip install pytae[plot]`).

```python
from pytae.plotting import Plotter

Plotter().data(penguins).plot(
    x="bill_length_mm", y="bill_depth_mm", kind="scatter", c="species", cmap="viridis"
).finalize()
```

See [docs/PLOTTING.md](https://github.com/maddytae/pytae/blob/master/docs/PLOTTING.md) for more examples with sample data.

## Library

Import `pytae as pt`. Same verbs work as `pt.select(df, ...)` or as `df.pt.select(...)` (mix with pandas: `df.rename(...).pt.agg_df(...)`). Notebooks use the accessor chain. CLI flags (`-select`, `-qry`, …) are unchanged.

```python
import pytae as pt
penguins = pt.sample("penguins")
pt.select(penguins, "species", contains="bill")
(penguins
 .pt.select("species", "island", "bill_length_mm", "body_mass_g")
 .pt.agg_df(a=["mean", "n"])
)
```

- **Filtering** — `pt.qry()` / `df.pt.qry()`: string expressions, dicts, or keyword filters (equality, lists, `in`/`not in`, comparisons, intervals)
- **Selection** — `pt.select()`: columns by name, regex, dtype, or name pattern
- **Mutating** — `pt.mutate()`: create/overwrite columns via formulas, `if_else()`, `case_when()`, `map()`
- **Reshaping** — `pt.long()` / `pt.wide()`: melt numeric columns to rows, pivot back to columns
- **Aggregation** — `pt.agg_df()`: auto-detects group columns and aggregates the rest
- **Utilities** — `df.to_clip()`, `pt.handle_missing()`, `pt.cols()`, `pt.group_x()`, `pt.clean_columns()`, `pt.replace_values()`
- **SQL** — `pt.sql()` / `df.pt.sql()` via duckdb (`pip install pytae[sql]`); the frame is table `data`

See [docs/LIBRARY.md](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md) for examples of each.

## Key Conventions & Syntax Cheat Sheet

| Task | Syntax | Example |
|---|---|---|
| **Copy to Clipboard** | `df.to_clip()` in Python; `-o clip` in CLI | `df.head().to_clip()` vs. `pytae data.parquet -head -o clip` |
| **Mapping vs. Assignment** | `:` maps old to new; `=` assigns values | `-rename "old:new"` vs. `-mutate "col = expr"` |
| **Spaced Columns (Filter)** | String expressions handle spaces directly | `df.pt.qry("bill length mm > 40")` |
| **Spaced Columns (Create)** | Unpack dictionary with `**` | `df.pt.mutate(**{"body mass kg": "body_mass_g / 1000"})` |
| **Spaced Columns (Expr)** | Reference via brackets `[col]` or backticks `` `col` `` | `df.pt.mutate(ratio="[bill length mm] / [bill depth mm]")` |
| **Selective Grouping** | `agg_df` groups by all non-numeric cols; select first | `df.pt.select("species", "body_mass_g").pt.agg_df("mean")` |

## License

MIT — see [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE).
