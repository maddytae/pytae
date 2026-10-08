# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic Pandas tools and zero-code CLI for tabular data manipulation, feature engineering, DuckDB SQL, and visualization.

`pytae` offers **one and only one right way** to perform every tabular operation across two complementary workflows:
1. **Python Library & DataFrame Accessor (`df.pt`)**: Expressive, chainable verbs (`filter`, `select`, `mutate`, `arrange`, `distinct`, `by`, `ungroup`, `pick`, `agg`, `long`, `wide`, `pivot`, `sql`, `plot`) on standard Pandas DataFrames.
2. **Unix Pipeline CLI (`pytae`)**: Inspect, filter, transform, aggregate, diff, and export files (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.sas7bdat`, `.gz`) from the terminal with zero boilerplate.

👉 **New to Pytae?** Check out **[Pytae vs. Pandas vs. dplyr (Rosetta Stone & Naming Rationale)](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas_and_dplyr.md)**.

---

## Installation

```bash
pip install pytae              # Core library and CLI
pip install "pytae[plot]"       # Includes matplotlib for plotting
pip install "pytae[sql]"        # Includes DuckDB for SQL queries
pip install "pytae[plot,sql]"   # All optional dependencies
```

---

## Quick Start: Python Library

Use verbs as standalone functions (`pt.verb(df, ...)`) or chain them via `.pt`:

```python
import pytae as pt

penguins = pt.sample("penguins")

# Clean, method-chainable pipeline with zero index wrestling
summary = (
    penguins
    .pt.filter(lambda d: d["body_mass_g"] >= 3500)
    .pt.by("species")
    .pt.mutate(
        mass_kg="body_mass_g / 1000",
        avg_mass="mean(body_mass_g)",
        diff="body_mass_g - avg_mass",
    )
    .pt.arrange("species, -mass_kg")
    .pt.select("species", "island", "mass_kg", "diff")
    .pt.agg(mean_mass="mass_kg:mean", n="n")
)
```

👉 **Full Library API Hub**: [docs/library.md](https://github.com/maddytae/pytae/blob/master/docs/library.md)

---

## Quick Start: CLI

Flags execute from left to right as an in-memory pipeline:

```bash
# 1. Zero-cost inspection (reads Parquet headers without loading rows)
pytae penguins.parquet -shape -head 5

# 2. Filter, engineer features, sort, and export
pytae penguins.parquet \
  -filter "species = 'Adelie', body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000" \
  -arrange "mass_kg desc" \
  -select "species,island,mass_kg" \
  -o heavy_adelie.csv

# 3. Grouped aggregation & reshaping
pytae penguins.parquet -by species -agg "avg_mass=body_mass_g:mean, count=n"

# 4. Deduplicate rows across key columns
pytae penguins.parquet -distinct "species,island"

# 5. Embedded DuckDB SQL
pytae sales.parquet -sql "select region, sum(revenue) from data group by 1"

# 6. Fast dataset comparison
pytae current.parquet -diff baseline.parquet
```

👉 **Full CLI Reference Hub**: [docs/cli.md](https://github.com/maddytae/pytae/blob/master/docs/cli.md)

---

## Key Syntax & Conventions

| Operation | Python (`df.pt`) | CLI Flag | Example |
| :--- | :--- | :--- | :--- |
| **Filter Rows** | `.pt.filter(...)` | `-filter "..."` | `df.pt.filter(lambda d: d['mass'] > 4000)` |
| **Group Context** | `.pt.by(*cols)` | `-by ...` | `df.pt.by("species", "island")` |
| **Clear Grouping**| `.pt.ungroup()` | N/A | `df.pt.ungroup()` |
| **Drop Null Rows** | `df.dropna(...)` | `-dropna [COLS]` | `pytae data.parquet -dropna "age,income"` |
| **Sort Rows** | `.pt.arrange(...)` | `-arrange "..."` | `df.pt.arrange("species, -mass_kg")` |
| **Pick Rows** | `.pt.pick(...)` | `-pick "..."` | `df.pt.pick("mass", n=3, order="max")` |
| **Select Columns** | `.pt.select(...)` | `-select "..."` | `df.pt.select("species", contains="bill", "-temp")`|
| **Mutate Columns** | `.pt.mutate(...)` | `-mutate "..."` | `df.pt.mutate(ratio="[bill length] / [bill depth]")` |
| **Grouped Summary**| `.pt.agg(...)` | `-by ... -agg "..."` | `df.pt.by("species").pt.agg(avg_mass="mass:mean", n="n")` |
| **2D Pivot Table** | `.pt.pivot(...)` | `-pivot "..."` | `df.pt.pivot(r="island", c="species", v="mass", a="mean")` |
| **Pure Reshape** | `.pt.long()`, `.pt.wide()`| `-long`, `-wide` | `df.pt.wide(c="metric", v="val", index="id")` |
| **Distinct Rows** | `.pt.distinct(*cols)`| `-distinct [COLS]` | `df.pt.distinct("species", "island")` |
| **DuckDB SQL** | `.pt.sql("...")` | `-sql "..."` | `df.pt.sql("select * from data order by 1")` |
| **Glimpse Table** | `.pt.glimpse()` | `-glimpse` | `df.pt.glimpse()` |
| **Copy to Clipboard**| `df.to_clip()` | `-o clip` | `df.head().to_clip()` |

---

## Documentation Directory

### Guides & Specifications
- **Architecture & Rosetta Stone**: [Pytae vs. Pandas vs. dplyr (Rationale)](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas_and_dplyr.md)
- **Library API Guide**: [docs/library.md](https://github.com/maddytae/pytae/blob/master/docs/library.md)
- **CLI Reference Hub**: [docs/cli.md](https://github.com/maddytae/pytae/blob/master/docs/cli.md)
- **CLI Feature Guides**:
  - [Row Filtering](https://github.com/maddytae/pytae/blob/master/docs/cli/filter.md) (`-filter`, `-dropna`, intervals, set membership)
  - [Row Picking](https://github.com/maddytae/pytae/blob/master/docs/cli/pick.md) (`-pick`, top/bottom N or proportion per group)
  - [Row Sorting](https://github.com/maddytae/pytae/blob/master/docs/cli/arrange.md) (`-arrange`, `-col`, `desc`, spaced columns)
  - [Distinct Rows](https://github.com/maddytae/pytae/blob/master/docs/cli/distinct.md) (`-distinct` across all or specific column subsets)
  - [Column Selection](https://github.com/maddytae/pytae/blob/master/docs/cli/select.md) (`-select`, negative drops, slices)
  - [Mutating & Computing](https://github.com/maddytae/pytae/blob/master/docs/cli/mutate.md) (`-mutate`, conditionals, window calcs)
  - [Reshaping](https://github.com/maddytae/pytae/blob/master/docs/cli/reshape.md) (`-long`, `-wide` pure 1-to-1 unmelting)
  - [2D Pivot Tables](https://github.com/maddytae/pytae/blob/master/docs/cli/pivot.md) (`-pivot` with flat 1D headers)
  - [Aggregations & Grouping](https://github.com/maddytae/pytae/blob/master/docs/cli/agg.md) (`-by`, `-agg`, grand totals)
  - [Inspection & Metadata](https://github.com/maddytae/pytae/blob/master/docs/cli/inspect.md) (`-shape`, `-cols`, `-meta`, `-freq`, `-hist`, `-value_counts`)
  - [Data Cleaning](https://github.com/maddytae/pytae/blob/master/docs/cli/clean_replace.md) (`-clean_columns`, `-replace_values`, `-handle_missing`)
  - [DuckDB SQL](https://github.com/maddytae/pytae/blob/master/docs/cli/sql.md) (`-sql`)
  - [Plotting & Figures](https://github.com/maddytae/pytae/blob/master/docs/cli/plotting.md) (`-plot`, `-finalize`)
  - [Dataset Diffing](https://github.com/maddytae/pytae/blob/master/docs/cli/diff.md) (`-diff`)
  - [File I/O & Export](https://github.com/maddytae/pytae/blob/master/docs/cli/export_io.md) (`-o`, `-out_dir`, STDIN, compression)
  - [Multi-File Pipelines](https://github.com/maddytae/pytae/blob/master/docs/cli/multi_file.md) (`-file`, `-merge`, `-concat`)
  - [Other Utilities & Modifiers](https://github.com/maddytae/pytae/blob/master/docs/cli/other_utilities.md) (`-nrows`, `-limit`, `-dlim`, `-encoding`, `-pretty`, `-round`, `-pager`, `-progress`)

### Interactive Jupyter Notebook Tutorials (`docs/library/`)
Run any interactive walkthrough directly:
- **Filtering**: [`filter.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/filter.ipynb)
- **Selection**: [`select.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/select.ipynb)
- **Feature Engineering**: [`mutate.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/mutate.ipynb)
- **Sorting**: [`arrange.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/arrange.ipynb)
- **Picking Rows**: [`pick.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/pick.ipynb)
- **Distinct Rows**: [`distinct.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/distinct.ipynb)
- **Pure Reshaping**: [`reshape.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/reshape.ipynb)
- **2D Pivot Tables**: [`pivot.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/pivot.ipynb)
- **Aggregation**: [`agg.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/agg.ipynb)
- **DuckDB SQL**: [`sql.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/sql.ipynb)
- **Plotting**: [`plotting.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/plotting.ipynb)
- **Other Utilities**: [`other_utilities.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/other_utilities.ipynb)

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
