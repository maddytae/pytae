# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively and completely by **Polars** across both Python library and CLI.

`pytae` offers **one and only one right way** to perform tabular operations with zero code duplication:
1. **Python Library (`pt.DataFrame` / `df.pt`)**: High-performance tabular data frame backed directly by Polars vector execution. Enter via `pt(pd_df)`, `pt(pl_df)`, `pt.read_parquet("file.parquet")`, or calling `.pt` off any Pandas or Polars DataFrame. Once entered, chain verbs naturally without repeatedly calling `.pt` (`.by()`, `.mutate()`, `.filter()`, `.arrange()`, `.agg()`, `.pivot()`, `.plot()`).
2. **Unix Pipeline CLI (`pytae`)**: Blazing-fast multithreaded SIMD vector engine sharing the exact same Polars core. Ingests tabular files (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.sas7bdat`, `.gz`), filters, transforms, aggregates, reshapes, and executes analytical ANSI SQL queries (`-sql`) with zero boilerplate.

👉 **New to Pytae?** Check out **[Pytae vs. Pandas vs. dplyr (Rosetta Stone & Naming Rationale)](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas_and_dplyr.md)**.

---

## Installation

```bash
pip install pytae              # Polars-native library and CLI
pip install "pytae[plot]"       # Includes matplotlib for plotting
```

---

## Quick Start: Python Library (Polars-Powered)

Read directly with `pt.read_parquet()`, wrap existing data with `pt(df)`, or chain off Pandas via `.pt`:

```python
import pytae as pt

# Read directly with Polars-powered fast auto-detection
df = pt.read_parquet("sales_report.parquet")

# Or chain directly off pandas or polars - only one .pt call needed!
summary = (
    df.filter("amount > 0")
    .by("region")
    .mutate(pct_total="amount / sum(amount)", prev_sale="shift(amount, 1)")
    .arrange("-amount")
    .to_pandas()  # or .to_polars(), .to_clip()
)
```

👉 **Full Master Documentation Hub**: [docs/pytae.md](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)

---

## Quick Start: CLI (Polars-Powered)

Flags execute from left to right as an in-memory pipeline powered natively by Polars:

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

# 5. Polars SQL Query
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
| **Multi-Col Mutate** | `.pt.mutate("(...) = ...")` | `-mutate "(...) = ..."` | `df.pt.mutate("(rev, cost)_usd = _ * 1.08")` |
| **Grouped Summary**| `.pt.agg(...)` | `-by ... -agg "..."` | `df.pt.by("species").pt.agg(avg_mass="mass:mean", n="n")` |
| **2D Pivot Table** | `.pt.pivot(...)` | `-pivot "..."` | `df.pt.pivot(r="island", c="species", v="mass", a="mean")` |
| **Pure Reshape** | `.pt.long()`, `.pt.wide()`| `-long`, `-wide` | `df.pt.wide(c="metric", v="val", index="id")` |
| **Distinct Rows** | `.pt.distinct(*cols)`| `-distinct [COLS]` | `df.pt.distinct("species", "island")` |
| **SQL Query (CLI)**| N/A (CLI only) | `-sql "..."` | `pytae data.parquet -sql "select * from data order by 1"` |
| **Glimpse Table** | `.pt.glimpse()` | `-glimpse` | `df.pt.glimpse()` |
| **ASCII Freq & Hist**| `.pt.freq()`, `.pt.hist()` | `-freq`, `-hist` | `df.pt.freq("species")`, `df.pt.hist("mass:10")` |
| **Copy to Clipboard**| `df.to_clip()` | `-o clip` | `df.head().to_clip()` |

---

## Documentation Directory

### Guides & Specifications
- **Master Reference & Architecture Hub**: [docs/pytae.md](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)
- **Rosetta Stone & Philosophy**: [Pytae vs. Pandas vs. dplyr (Rationale)](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas_and_dplyr.md)

### Detailed Topic Guides (`docs/detailed_docs/`)
Unified documentation covering both the Python library and CLI:
- [Data Ingestion & Sinks](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/read_write.md) (`pt.read_parquet`, `pt.read_csv`, `pt.scan_*`, `to_parquet`, `-o`, `-od`, `-fmt`, `-progress`)
- [Feature Engineering](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/mutate.md) (`mutate`, formulas, sequential assignments, quoted strings, `across`)
- [Row Filtering](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/filter.md) (`filter`, intervals, set membership, callables, pushdown)
- [Column Selection](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/select.md) (`select`, negative drops `-col`, regex, pattern matches, rename)
- [Row Sorting](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/arrange.md) (`arrange`, `-col`, `desc`, bracketed spaced columns)
- [Row Picking](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/pick.md) (`pick`, top/bottom N or proportion per group via `by`)
- [Distinct Rows](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/distinct.md) (`distinct`, deduplication across column subsets, `keep`)
- [Table Reshaping](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/reshape.md) (`long`, `wide`, pure 1-to-1 unmelting)
- [2D Pivot Tables](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/pivot.md) (`pivot`, `r, c, v, a` matrices, flat 1D headers)
- [Aggregations & Grouping](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/agg.md) (`by`, `agg`, `dropna=False` zero data loss retention)
- [Visualizations & Plotting](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/plotting.md) (`df.plot()`, `-plot`, `-finalize`, interactive walkthrough)
- [Utilities & Inspection](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/other_utilities.md) (`fillna`, `fill_null`, `fill_nan`, `dropna`, `handle_missing`, `cols`, `glimpse`, `freq`, `hist`)
- [CLI Terminal Superpowers](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli_only.md) (`-diff`, `-inspect`, `-meta`, `-file`, `-join`, `-concat`, `-sql`, batch globs)
- [Python Library Architecture](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library_only.md) (`pt()`, `.pt` accessor on Polars & Pandas, lazy evaluation pushdowns, callables)

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
