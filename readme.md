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

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) | [**Interactive REPL Guide**](https://github.com/maddytae/pytae/blob/master/docs/pytae.md#interactive-repl-shell-pytae--i) | [**Standalone Binaries (Zero-Python)**](https://github.com/maddytae/pytae/blob/master/docs/binary_distribution.md) | [**Master Reference & Architecture Hub**](https://github.com/maddytae/pytae/blob/master/docs/pytae.md) | [**vs. Pandas**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_pandas.md) | [**vs. dplyr**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_dplyr.md) | [**vs. SAS**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_sas.md) | [**Benchmarks (5M Rows)**](https://github.com/maddytae/pytae/blob/master/docs/benchmarks/README.md)

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

See [Standalone Binary Distribution](https://github.com/maddytae/pytae/blob/master/docs/binary_distribution.md) for details.

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

# Read files, globs, lists, or partitioned directories with Polars-powered fast auto-detection
df = pt.read("sales_report.parquet")
# or pt.read(["jan.parquet", "feb.parquet"])
# or pt.scan("data/**/*.csv")

# Fluent method chaining
summary = (
    df.filter("amount > 0")
    .by("region")
    .mutate(pct_total="amount / sum(amount)", prev_sale="shift(amount, 1)")
    .arrange("amount desc")
    .to("summary.parquet")  # output to disk and returns self
)

# Export to in-memory formats with zero friction
records = summary.to("records")  # FastAPI/JSON dicts: [{"region": "East", ...}]
tbl = summary.to("arrow")        # Zero-copy PyArrow Table
pdf = summary.to("pandas")       # Pandas DataFrame
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

👉 **Plotting Guides**: [Plotting Notebook](https://github.com/maddytae/pytae/blob/master/docs/notebooks/plotting/plotting.ipynb) | [CLI Plotting Guide](https://github.com/maddytae/pytae/blob/master/docs/guides/cli_plots.md)

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

# 7. One-command shell tab-completion setup (Zsh, Bash, Fish)
pytae --install-completion
```

👉 **CLI Quick Reference**: [**Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) or run `pytae -cheatsheet` in your terminal! | **Full CLI & Engine Guides**: [docs/guides/](https://github.com/maddytae/pytae/tree/master/docs/guides/)

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

# Instant rollbacks, checkpoints & reproducible pipeline export
pytae> reset                      # Revert to baseline
pytae> checkpoint baseline       # Save named snapshot
pytae> restore baseline          # Revert to snapshot
pytae> export pipeline.pt        # Export clean pipeline to Pytae script (or .py)
pytae> export pipeline.pt -relative # Export with portable relative paths
pytae> exit -s                   # Save clean, pruned pipeline on exit to ./session.pt
```

> [!TIP]
> **Reproducible Pipelines & Code Handoffs**:
> - **In-Session Export**: Run `export pipeline.pt` (or `export pipeline.py`). Add `-relative` for portable paths across machines and Git repos.
> - **Export on Exit**: Run `exit -s` (saves clean `./session.pt`), `exit -s py`, or `exit -s <path> [-relative]`.
> - **CLI Post-Hoc Export**: Rescue any flight-recorder session log with `pytae -export <history.txt> -o pipeline.pt` (or `-o pipeline.py`).
> - **Strict Domain Execution**:
>   - Pytae pipelines: Run headlessly with `pytae pipeline.pt`, or stay inside REPL with `pytae -i pipeline.pt`.
>   - Python scripts: Run with standard Python via `python pipeline.py` (or `python -i pipeline.py`).

👉 **Read the Full REPL Manual**: [Interactive REPL Guide](https://github.com/maddytae/pytae/blob/master/docs/pytae.md#interactive-repl-shell-pytae--i) | [REPL Topic Guides](https://github.com/maddytae/pytae/tree/master/docs/repl/)

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
- **[Pytae vs. Pandas Deep Dive](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_pandas.md)**: Index traps, `MultiIndex` flattening, silent `dropna` data loss, memory copies.
- **[Pytae vs. dplyr Deep Dive](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_dplyr.md)**: Eliminating sticky grouping (`ungroup`), Non-Standard Evaluation quoting ambiguity, CLI parity.
- **[Pytae vs. SAS Migration Guide](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_sas.md)**: Unifying `DATA` step + `PROC SQL` + procedures, sorting requirements for merge, negative infinity missing values.

---

## Documentation Directory

### Architecture, Philosophy & Ecosystem
- **[Master Reference & Architecture Hub](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)**: Philosophy, the 7 pillars, naming rationale, eager vs. lazy execution, and architecture guide.
- **[Ecosystem Comparisons](https://github.com/maddytae/pytae/tree/master/docs/comparisons/)**: Detailed Rosetta Stone guides for [Pandas](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_pandas.md), [dplyr](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_dplyr.md), and [SAS](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_sas.md).
- **[Performance Benchmarks (5M Rows)](https://github.com/maddytae/pytae/blob/master/docs/benchmarks/README.md)**: Reproducible speed benchmarks vs. Pandas across realistic analytical workloads.
- **[Standalone Portable Binaries](https://github.com/maddytae/pytae/blob/master/docs/binary_distribution.md)**: Single-binary setup and execution guide (Zero-Python).

### Guides & Manuals
- **[CLI Cheat Sheet & Cookbook](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md)**: 14 curated sections of one-liner recipes and Unix shell workflows.
- **[Feature & CLI Guides](https://github.com/maddytae/pytae/tree/master/docs/guides/)**: In-depth feature guides for each verb and CLI flag (`filter`, `mutate`, `arrange`, `join`, `diff`, `mask`, `sql`, etc.).
- **[Interactive REPL Subsystem](https://github.com/maddytae/pytae/tree/master/docs/repl/)**: Deep dives on ingestion, checkpoints, SQL/Python interop, session variables, and memory management.
- **[Interactive Python Companion Notebooks](https://github.com/maddytae/pytae/tree/master/docs/notebooks/library/)**: Fully executed Jupyter notebooks for each Python API verb.

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
