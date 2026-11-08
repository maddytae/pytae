# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded SIMD vector computation and backed by **Pandas & Matplotlib** for plotting across command-line, interactive shell, and Python library.

`pytae` provides **one and only one obvious way** to work with tabular data across three unified modalities:

1. **Python & Jupyter SDK (`pt.DataFrame` / `df.pt`)**: High-performance Polars-native DataFrame library with `.pt` accessor for pandas/polars DataFrames.
2. **Unix Pipeline CLI (`pytae`)**: Fast one-shot command-line data processing, format conversion, and terminal visualizations.
3. **Interactive REPL Shell (`pytae -i`)**: Stateful in-memory workbench with disk-backed checkpoints, multi-table joins, and ANSI SQL.

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](docs/cli_cheatsheet.md) | [**Interactive REPL Guide**](docs/pytae.md#interactive-repl-shell-pytae--i) | [**Standalone Binaries (Zero-Python)**](docs/binary_distribution.md) | [**Master Reference & Architecture Hub**](docs/pytae.md) | [**vs. Pandas**](docs/comparisons_with_other_tools/comparison_to_pandas.md) | [**vs. dplyr**](docs/comparisons_with_other_tools/comparison_to_dplyr.md) | [**vs. SAS**](docs/comparisons_with_other_tools/comparison_to_sas.md) | [**Benchmarks (5M Rows)**](docs/benchmarks/README.md)

---

## The Pytae Advantage: "One and Only One Obvious Way"

| Architectural Dimension | Legacy Workflows (Pandas / dplyr / SAS) | Pytae Guarantee |
|:---|:---|:---|
| **API Philosophy** | 4–6 competing ways per task (`query`, `loc`, `assign`, `[]`, NSE) | **One canonical verb per operation** (`filter`, `mutate`, `arrange`, `select`, `agg`) |
| **Index Hierarchy** | Complex row indexes, `MultiIndex` tuples, constant `.reset_index()` | **Pure flat 1D DataFrames**: clean `RangeIndex(0, 1, 2, ...)` always |
| **Data Safety** | Silent loss: `groupby(dropna=True)` drops groups; `dropna()` wipes partials | **Zero Data Loss**: bare `dropna()` drops 100% blanks; `agg`/`pivot` retain NA groups |
| **Grouping Scope** | Sticky grouped state requiring defensive `ungroup()` | **Single-shot grouping**: `df.by(*cols)` scopes the immediate verb and auto-resets |
| **Execution Engine** | Single-threaded Python GIL / memory-copy bottlenecks | **100% native multithreaded Polars Rust SIMD** core with predicate pushdown |
| **Modality Parity** | Disconnected CLI tools, incompatible shell scripts | **100% grammar symmetry**: `df.filter(...)` in Python == `-filter "..."` in terminal |

---

## Installation

### Option 1: Standalone Portable Binary (Zero Python Required)
For locked-down corporate laptops, air-gapped environments, or instant setup without installing Python, download the single-file executable from [GitHub Releases](https://github.com/maddytae/pytae/releases):
- **Windows**: `pytae-windows-x64.zip` (Fast pre-extracted folder bundle)
- **macOS**: `pytae-macos-arm64` (Apple Silicon)
- **Linux**: `pytae-linux-x86_64`

See [Standalone Binary Distribution](docs/binary_distribution.md) for details.

### Option 2: Via Python Package Managers
```bash
pip install pytae              # Polars-native CLI, REPL, and Python library
pip install "pytae[plot]"       # Includes matplotlib for plotting & dashboards
```

---

## 1. Quick Start: Python & Jupyter SDK

Need expressive, readable data transformations in Python scripts, Airflow, or Jupyter? `import pytae as pt` gives you fluent method chaining backed by multithreaded Rust:

```python
import pytae as pt

# Read directly with Polars-powered fast auto-detection
df = pt.read_parquet("sales_report.parquet")

# Or chain directly off pandas or polars - only one .pt call needed!
summary = (
    df.filter("amount > 0")
    .by("region")
    .mutate(pct_total="amount / sum(amount)", prev_sale="shift(amount, 1)")
    .arrange("amount desc")
    .to_pandas()  # or .to_polars(), .to_clip()
)
```

### Visualizations & Dashboards (Compute in Polars, Visualize in Pandas)

While **Polars** provides multithreaded SIMD speed for transformations, **Pandas** and **Matplotlib** provide the richest visualization ecosystem. Calling `.plot()` automatically converts prepared data into Pandas and delegates directly to `pandas.DataFrame.plot()`:

```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Fluent method chaining
(
    penguins
    .filter("body_mass_g.is_not_null()")
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass", title="Average Penguin Mass (g)")
    .finalize(save="mass_by_species.png")
)

# 2. Multi-panel dashboard layouts with pt.Plotter
plotter = pt.Plotter("""
    AAAB
    AAAC
""", figsize=(12, 6))

plotter.add("A", penguins, kind="scatter", x="bill_length_mm", y="bill_depth_mm", color="species")
plotter.add("B", penguins.by("species").count(), kind="bar", x="species", y="n")
plotter.add("C", penguins, kind="box", y="body_mass_g", by="species")
plotter.finalize(title="Penguin Morphology Dashboard", save="dashboard.png")
```

👉 **Plotting Guides**: [Plotting Notebook](docs/detailed_docs/plotting/plotting.ipynb) | [CLI Plotting Guide](docs/detailed_docs/cli/cli_plots.md)

---

## 2. Quick Start: Command-Line (CLI)

Flags execute from left to right as an in-memory pipeline powered natively by Polars multithreading:

```bash
# 1. Zero-cost inspection & schema summary (columns, types, nulls %, unique count)
pytae penguins.parquet -schema
pytae penguins.parquet -head 5
pytae penguins.parquet -sample 5% -seed 42

# 2. In-memory pipeline: filter, engineer features, sort, and export
pytae penguins.parquet \
  -filter "species == 'Adelie' and body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000" \
  -arrange "mass_kg desc" \
  -select "species,island,mass_kg" \
  -o heavy_adelie.parquet

# 3. Frequency tables, terminal ASCII visualizations & ANSI SQL
pytae penguins.parquet -freq species -bar
pytae sales.parquet -sql "SELECT region, sum(revenue) FROM data GROUP BY 1"

# 4. Multi-file relational operations (-join, -concat)
pytae ord=orders.parquet cust=customers.csv \
  -join "left=ord,right=cust,on=customer_id,how=left" -head 5

# 5. Instant format conversion & dataset diff
pytae legacy.sas7bdat -o clean.parquet
pytae yesterday.parquet -diff today.parquet -tol 1e-4

# 6. Sensitive PII masking and encryption
pytae users.csv -mask "email=hash, ssn=encrypt" -key "SecretKey123" -o secure.parquet
```

👉 **CLI Quick Reference**: [**Cheat Sheet & Cookbook**](docs/cli_cheatsheet.md) or run `pytae -cheatsheet` in your terminal! | **Full CLI Manuals**: [docs/detailed_docs/cli/](docs/detailed_docs/cli/)

---

## 3. Quick Start: Interactive REPL Shell (`pytae -i`)

Instead of re-reading multi-gigabyte files from disk on every command, the **Pytae REPL** loads datasets into memory **once** and provides an instantaneous interactive workbench with zero syntax bloat:

```bash
# Launch the interactive workbench
pytae -i
```

### In-Memory Multi-Table Workbench
Load datasets interactively (local files or bundled `sample:<name>`), explore with instant previews, and transform data:

```text
pytae> df1 = sample:penguins
Loaded penguins.parquet as 'df1' (344 rows x 7 cols).

# Fast non-destructive inspection (does not truncate active data)
pytae [df1: 344x7]> -schema
pytae [df1: 344x7]> -head 3
pytae [df1: 344x7]> -sample 5%

# Exploratory previews (safe, non-mutating preview matching CLI output)
pytae [df1: 344x7]> -filter "species == 'Gentoo' and body_mass_g > 5000"

# State mutation via explicit assignment
pytae [df1: 344x7]> df1 = -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"
Updated 'df1' (188 rows x 7 cols).

pytae [df1: 188x7]> df1 = -mutate "mass_kg = body_mass_g / 1000" -select "species,island,mass_kg"
Updated 'df1' (188 rows x 3 cols).

# Multi-table workflows, relational joins & ANSI SQL
pytae [df1: 188x3]> df2 = sample:tips
pytae [df1, df2]> df3 = -join "left=df1,right=df2,how=cross"
pytae [df1, df2, df3]> df4 = -sql "SELECT df1.species, count(*) as n FROM df1 GROUP BY 1"

# Instant rollbacks, checkpoints & reproducible history
pytae> reset                      # Revert to baseline
pytae> checkpoint baseline       # Save named snapshot
pytae> restore baseline          # Revert to snapshot
pytae> exit -s                   # Save self-contained session history to ./history.txt
```

> [!TIP]
> **Reproducible Sessions**: Because datasets are loaded interactively (e.g. `df = penguins.parquet`), every command is saved to session history. You can replay the entire session at any time with `pytae -i < history.txt`.

👉 **Read the Full REPL Manual**: [Interactive REPL Guide](docs/pytae.md#interactive-repl-shell-pytae--i) | [REPL Topic Guides](docs/detailed_docs/repl/)

---

## Ecosystem Rosetta Stone & Comparisons

| Operation | Pandas | dplyr (R) | SAS | Pytae (Python & CLI) |
|:---|:---|:---|:---|:---|
| **Filter rows** | `df[df['a'] > 1]`<br>`df.query('a > 1')` | `filter(df, a > 1)` | `DATA out; SET in;`<br>`IF a > 1; RUN;` | `df.filter("a > 1")`<br>`pytae in.csv -filter "a > 1"` |
| **Add columns** | `df['c'] = df['a'] + df['b']`<br>`df.assign(c=...)` | `mutate(df, c = a + b)` | `DATA out; SET in;`<br>`c = a + b; RUN;` | `df.mutate(c="a + b")`<br>`pytae in.csv -mutate "c = a + b"` |
| **Grouped agg** | `df.groupby('k').agg(...)`<br>*(MultiIndex hell)* | `df %>% group_by(k) %>%`<br>`summarise(...) %>% ungroup()` | `PROC MEANS DATA=in;`<br>`CLASS k; VAR v; RUN;` | `df.by("k").agg(avg="v:mean")`<br>`pytae in.csv -by k -agg "avg=v:mean"` |
| **Sort rows** | `df.sort_values(['a', 'b'],`<br>`ascending=[True, False])` | `arrange(df, a, desc(b))` | `PROC SORT DATA=in;`<br>`BY a DESCENDING b; RUN;` | `df.arrange("a", "b desc")`<br>`pytae in.csv -arrange "a, b desc"` |
| **Cross-Tab Pivot** | `pd.pivot_table(df, ...)`<br>*(Hierarchical tuples)* | `pivot_wider(df, ...)` | `PROC TRANSPOSE DATA=in ...;`<br>`BY ...; RUN;` | `df.pivot(r='x', c='y', v='z')`<br>`pytae in.csv -pivot "r=x,c=y,v=z"` |

Detailed migration guides with line-by-line syntax comparisons:
- **[Pytae vs. Pandas Deep Dive](docs/comparisons_with_other_tools/comparison_to_pandas.md)**: Index traps, `MultiIndex` flattening, silent `dropna` data loss, memory copies.
- **[Pytae vs. dplyr Deep Dive](docs/comparisons_with_other_tools/comparison_to_dplyr.md)**: Eliminating sticky grouping (`ungroup`), Non-Standard Evaluation quoting ambiguity, CLI parity.
- **[Pytae vs. SAS Migration Guide](docs/comparisons_with_other_tools/comparison_to_sas.md)**: Unifying `DATA` step + `PROC SQL` + procedures, sorting requirements for merge, negative infinity missing values.

---

## Documentation Directory

### Architecture, Philosophy & Ecosystem
- **[Master Reference & Architecture Hub](docs/pytae.md)**: Philosophy, the 7 pillars, naming rationale, eager vs. lazy execution, and architecture guide.
- **[Ecosystem Comparisons](docs/comparisons_with_other_tools/)**: Detailed Rosetta Stone guides for [Pandas](docs/comparisons_with_other_tools/comparison_to_pandas.md), [dplyr](docs/comparisons_with_other_tools/comparison_to_dplyr.md), and [SAS](docs/comparisons_with_other_tools/comparison_to_sas.md).
- **[Performance Benchmarks (5M Rows)](docs/benchmarks/README.md)**: Reproducible speed benchmarks vs. Pandas across realistic analytical workloads.
- **[Standalone Portable Binaries](docs/binary_distribution.md)**: Single-binary setup and execution guide (Zero-Python).

### Guides & Manuals
- **[CLI Cheat Sheet & Cookbook](docs/cli_cheatsheet.md)**: 14 curated sections of one-liner recipes and Unix shell workflows.
- **[Detailed CLI Topic Manuals](docs/detailed_docs/cli/)**: In-depth feature guides for each CLI flag (`filter`, `mutate`, `arrange`, `join`, `diff`, `mask`, `sql`, etc.).
- **[Interactive REPL Subsystem](docs/detailed_docs/repl/)**: Deep dives on ingestion, checkpoints, SQL/Python interop, session variables, and memory management.
- **[Interactive Python Notebooks](docs/detailed_docs/library/)**: Fully executed Jupyter notebooks for each Python API verb.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
