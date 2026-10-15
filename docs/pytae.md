# Pytae — Master Reference & Architecture Guide

`pytae` is a modern, high-performance tabular data manipulation framework that provides a single, unified grammar across both **Python code** (`df.pt.<verb>()`, `pt.<verb>(df)`) and the **Command Line** (`pytae <file> -<verb>`). Backed by a 100% native multithreaded SIMD Polars core, Pytae eliminates boilerplate, index headaches, and performance bottlenecks.

---

## The Pytae Architecture: "One Grammar, Two Modalities"

```
                              ┌────────────────────────┐
                              │      Source File       │
                              │ (.parquet, .csv, etc.) │
                              └───────────┬────────────┘
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
           Python Library API                         Command Line (CLI)
         import pytae as pt                         $ pytae file.parquet
    df = pt.read_parquet("file.parquet")                     │
                     │                                       │
     df.filter("sales > 100")                        -filter "sales > 100"
       .mutate(tax="sales * 0.08")                   -mutate "tax = sales * 0.08"
       .by("region")                                 -by region
       .agg(total_rev="sum(sales)")                  -agg "total_rev = sum(sales)"
       .arrange("-total_rev")                        -arrange "-total_rev"
                     │                                       │
                     ▼                                       ▼
             In-Memory Result                          Stdout / Export
          Clean, flat DataFrame                      Table view, -o lake/
```

---

## Detailed Documentation Directory

All comprehensive guides, API signatures, CLI flags, walkthroughs, and edge cases are documented in **`docs/detailed_docs/`**:

| Category | Guide | Key Capabilities |
|:---|:---|:---|
| **Data I/O** | **[Data Ingestion & Sinks](detailed_docs/read_write.md)** | `pt.read_parquet`, `pt.read_csv`, `pt.scan_*`, `to_parquet`, `-o`, `-od`, `-fmt`, `-progress`, STDIN, clipboard |
| **Derivations** | **[Feature Engineering (`mutate`)](detailed_docs/mutate.md)** | `mutate`, formulas, sequential assignments, quoted strings, `if_else`, `across`, window calculations |
| **Row Filtering** | **[Predicate Evaluation (`filter`)](detailed_docs/filter.md)** | `filter`, interval ranges `[10, 20]`, set membership `in`, string patterns, lambdas, predicate pushdown |
| **Columns** | **[Selection & Reordering (`select`)](detailed_docs/select.md)** | `select`, drop with `-` / `!`, regex/patterns, inline rename, `pt.everything`, projection pushdown |
| **Sorting** | **[Row Sorting (`arrange`)](detailed_docs/arrange.md)** | `arrange`, ascending, descending `-col` / `col desc`, multi-column ordering, null positioning |
| **Aggregation** | **[Grouping & Summary (`by` & `agg`)](detailed_docs/agg.md)** | `by`, `agg`, `n`, `mean`, `sum`, `std`, `n_distinct`, `dropna=False` Zero Data Loss retention |
| **Cross-Tab** | **[2D Contingency Tables (`pivot`)](detailed_docs/pivot.md)** | `pivot`, `r=`, `c=`, `v=`, `a=`, flat 1D columns (no MultiIndex traps), `fill_value=0` |
| **Deduplication** | **[Distinct Records (`distinct`)](detailed_docs/distinct.md)** | `distinct`, whole-table deduplication, subset uniqueness, `keep='first'\|'last'\|'none'` |
| **Slicing** | **[Top / Bottom Records (`pick`)](detailed_docs/pick.md)** | `pick`, top/bottom $N$ records, top percentage `prop=`, grouped top-$N$ per category |
| **Reshaping** | **[Table Reshaping (`long` & `wide`)](detailed_docs/reshape.md)** | `long` (unpivoting) and `wide` (1:1 pivoting) with identical intuitive vocabularies |
| **Inspection** | **[Inspection & Utilities (`other_utilities`)](detailed_docs/other_utilities.md)** | `fillna`, `fill_null`, `fill_nan`, `dropna`, `handle_missing`, `cols`, `glimpse`, `freq`, `hist`, `clean_columns` |
| **Plotting** | **[Visualizations & Charts (`plotting`)](detailed_docs/plotting.md)** | Terminal ASCII charts (`freq`, `hist`) and Matplotlib publication figures (`.plot()`, `-plot`) |
| **CLI Only** | **[CLI Terminal Features (`cli_only`)](detailed_docs/cli_only.md)** | `-diff`, `-inspect`, `-meta`, `-file` multi-file pipelines, `-sql`, batch globbing, completions |
| **Library Only**| **[Python Library Architecture (`library_only`)](detailed_docs/library_only.md)** | Constructor `pt()`, `.pt` accessor on Polars & Pandas, lazy evaluation pushdowns, callables |
| **Philosophy** | **[Rosetta Stone & Comparison](comparison_to_pandas_and_dplyr.md)** | Pytae vs. Pandas vs. dplyr, naming rationale, "one and only one obvious way" |

---

## Missing Data Architecture: "Zero Data Loss by Default"

In standard data science workflows, accidental data loss is one of the most common causes of skewed metrics and corrupted reporting. A single missing optional field—such as a customer's secondary phone number—should **never** silently obliterate an entire transaction from a dataset.

Pytae adheres strictly to the principle of **Zero Data Loss by Default**:

1. **Conservative Row Elimination (`how="all"`)**:
   - Calling `df.dropna()` without arguments defaults to `how="all"`. Only rows that are completely blank (100% null/NaN across every column) are dropped.
2. **Intentional Filtering on Subsets (`how="any"`)**:
   - Calling `df.dropna("user_id", "email")` defaults to `how="any"` over the specified subset, guaranteeing that only rows missing required keys are dropped.
3. **Preservation of NA Groups in Aggregations (`dropna=False`)**:
   - Analytical operations (`agg`, `pivot`, `freq`, `mutate`) default to `dropna=False`. Missing grouping keys (like `sex=NaN`) remain visible as explicit rows/columns in reports.
4. **Dual Missing Value Cleaning (`drop_nans=True`)**:
   - Cleans both Apache Arrow `null` and IEEE-754 floating-point `NaN` values by default, preventing float NaN arithmetic poisoning.
5. **Smart Symmetrical Imputation (`fillna`)**:
   - `df.fillna(value, nans=True)` replaces both Arrow `null` and floating-point `NaN` across columns.
   - Specific helpers `fill_null()` and `fill_nan()` provide strict format-isolated cleaning.

### Comparison Table: Missing Data Handling

| Behavior | Pandas | Polars | R / dplyr | Pytae (Option B) |
|:---|:---|:---|:---|:---|
| **Bare Call (`df.dropna()`)** | Drops row if *any* column is NA (`how='any'`) | Drops row if *any* column is `null` | Requires explicit `tidyr::drop_na()` | **Drops only 100% blank rows (`how='all'`)** |
| **Float `NaN` vs Arrow `null`** | Conflates both into `np.nan` / `pd.NA` | Differentiates; `drop_nulls()` **ignores** `NaN`! | Treats `NA` and `NaN` distinctly | **Drops both `null` and `NaN` (`drop_nans=True`)** |
| **Analytical Verbs (`agg`, `pivot`)** | `dropna=True` (drops missing groups!) | Preserves `null` group keys | `group_by()` preserves `NA` groups | **`dropna=False` by default (Zero Data Loss)** |
| **Targeted Columns (`df.dropna("a", "b")`)** | `subset=['a', 'b']`, drops if any is NA | `subset=['a', 'b']`, drops if any is null | `tidyr::drop_na(a, b)` | **Drops if any specified column is NA (`how='any'`)** |
| **CLI & Library Aliasing** | `dropna()` only | `drop_nulls()` only | `drop_na()` | **`dropna`, `drop_nulls`, `drop_na` (100% interchangeable)** |

---

## 30-Second Quickstart

### In Python:
```python
import pytae as pt

# Eager read or lazy scan
penguins = pt.read_parquet("penguins.parquet")

report = (
    penguins
    .filter("body_mass_g > 3500 & sex.is_not_null()")
    .mutate(
        body_mass_kg="body_mass_g / 1000",
        bill_ratio="bill_length_mm / bill_depth_mm",
        status="'verified'"
    )
    .by("species", "island")
    .agg(
        n="n",
        avg_mass_kg="mean(body_mass_kg)",
        max_ratio="max(bill_ratio)"
    )
    .arrange("-avg_mass_kg")
)

# Export results
report.to_parquet("summary.parquet")
```

### On the Command Line:
The exact same logic translates directly to the terminal:

```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500, sex.is_not_null()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm, status = 'verified'" \
  -by species,island \
  -agg "n = n, avg_mass_kg = mean(body_mass_kg), max_ratio = max(bill_ratio)" \
  -arrange "-avg_mass_kg" \
  -o summary.parquet
```
