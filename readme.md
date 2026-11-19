# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded SIMD vector computation and backed by **Pandas & Matplotlib** for plotting across command-line, interactive shell, and Python library.

`pytae` provides **one and only one obvious way** to work with tabular data across three unified modalities:

1. **Python & Jupyter SDK (`pt.DataFrame` / `df.pt`)**: High-performance Polars-native DataFrame library with `.pt` accessor for pandas/polars DataFrames.
2. **Unix Pipeline CLI (`pytae`)**: Fast one-shot command-line data processing, format conversion, and terminal visualizations.
3. **IPython & Jupyter Workbench (`import pytae as pt`)**: Auto-activated magics (`%pt`/`%%pt`, `%checkpoint`, `%restore`, `%status`, `%free`, `%set`, `%export`, `%exit -s`) with disk-backed checkpoints and OS RAM reclaiming.

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) | [**IPython & Jupyter Workbench Guide**](https://github.com/maddytae/pytae/blob/master/docs/ipython.md) | [**Master Reference & Architecture Hub**](https://github.com/maddytae/pytae/blob/master/docs/pytae.md) | [**vs. Pandas**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_pandas.md) | [**vs. dplyr**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_dplyr.md) | [**vs. SAS**](https://github.com/maddytae/pytae/blob/master/docs/comparisons/comparison_to_sas.md) | [**Benchmarks (5M Rows)**](https://github.com/maddytae/pytae/blob/master/docs/benchmarks/README.md)

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

### Option 1: Zero-Config Global CLI via `uvx` or `pipx` (Instant, No Virtualenv Needed)
Run commands immediately anywhere in your terminal without setting up or activating virtual environments:
```bash
# Instant zero-install one-liner (executes in milliseconds via uv):
uvx pytae sales.parquet -filter "revenue > 1000" -shape

# Or install permanently into an isolated CLI tool environment:
uv tool install pytae     # via uv
# or
pipx install pytae        # via pipx
```

### Option 2: Standard Python Package Installation
```bash
pip install pytae              # Polars-native CLI, IPython workbench, and Python library
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

## 3. Quick Start: IPython & Jupyter Workbench (`import pytae as pt`)

Just `import pytae as pt` inside IPython or Jupyter — all workbench magics, display formatters, and context-aware Tab completions activate automatically (no `%load_ext` needed):

```python
import pytae as pt

# Load data via Python or %pt (immutable by default)
df = pt.sample("penguins")
# or: df = %pt sales.parquet

# Run full Pytae CLI pipelines in-process without mutating `df`
heavy = %pt df -filter "body_mass_g > 4000" -arrange "body_mass_g desc"

# Multi-line pipeline cell magic (`%%pt <target_var>`)
%%pt summary
df
-dropna "body_mass_g"
-by "species, island"
-agg "avg_mass = mean(body_mass_g), n = count()"
-arrange "avg_mass desc"

# Ephemeral Arrow IPC checkpoints (0 MB RAM), strict rollback & OS RAM reclaim
%checkpoint raw
%status                         # Tracked tables, RAM, checkpoints, OS RSS, settings
%checkpoint diff df raw         # Compare current `df` vs checkpoint `raw`
%restore raw                    # Strict DataFrame rollback + OS RSS trim
%free heavy                     # Delete `heavy`, scrub IPython Out/_ cache & trim RAM

# Persistent display settings & clean script/notebook export
%set max_rows=20 float_precision=2 comma=true
%set save                       # Persists to ~/.pytae/config.json
%export analysis.py             # Standalone runnable .py (or .ipynb); prunes errors & rollbacks
%exit -s analysis.py            # Export and exit IPython cleanly
```

👉 **Read the Full IPython Workbench Guide**: [**docs/ipython.md**](https://github.com/maddytae/pytae/blob/master/docs/ipython.md)

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

### Guides & Manuals
- **[CLI Cheat Sheet & Cookbook](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md)**: 14 curated sections of one-liner recipes and Unix shell workflows.
- **[Feature & CLI Guides](https://github.com/maddytae/pytae/tree/master/docs/guides/)**: In-depth feature guides for each verb and CLI flag (`filter`, `mutate`, `arrange`, `join`, `diff`, `mask`, `sql`, etc.).
- **[Interactive REPL Subsystem](https://github.com/maddytae/pytae/tree/master/docs/repl/)**: Deep dives on ingestion, checkpoints, SQL/Python interop, session variables, and memory management.
- **[Interactive Python Companion Notebooks](https://github.com/maddytae/pytae/tree/master/docs/notebooks/library/)**: Fully executed Jupyter notebooks for each Python API verb.

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
