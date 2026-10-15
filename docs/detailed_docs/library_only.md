# Python Library Architecture & Features (`library_only`)

While Pytae's concise verbs match the command line 1:1, the Python library provides deep integrations with the Python data ecosystem: universal DataFrame wrapping, `.pt` namespace accessors, lazy query planning with query pushdown, Python callables/lambdas, bundled datasets, and zero-copy interoperability with Polars and Pandas.

---

## Table of Contents

- [Universal Constructor (`pt.DataFrame`)](#universal-constructor)
- [The `.pt` Namespace Accessor](#the-pt-namespace-accessor)
- [Dual-Mode Execution & Lazy Evaluation](#dual-mode-execution)
- [Python Lambdas & Custom Callables](#lambdas-and-callables)
- [Zero-Copy Interoperability (`to_polars`, `to_pandas`)](#interoperability)
- [Bundled Sample Datasets (`pt.sample`)](#sample-datasets)

---

<a id="universal-constructor"></a>
## Universal Constructor (`pt.DataFrame`)

`pt.DataFrame(data)` (or the shorthand `pt(data)`) converts arbitrary tabular data into an optimized `pytae.DataFrame` backed directly by a Polars execution core:

```python
import pytae as pt
import pandas as pd
import polars as pl

# 1. From Python dictionary
df1 = pt.DataFrame({
    "species": ["Adelie", "Gentoo"],
    "mass_g": [3750, 5050]
})

# 2. From standard Pandas DataFrame
pd_df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
df2 = pt(pd_df)

# 3. From native Polars DataFrame
pl_df = pl.DataFrame({"x": [10.5, 20.2]})
df3 = pt(pl_df)

# 4. From native Polars LazyFrame
lazy_pl = pl.scan_parquet("orders.parquet")
df4 = pt(lazy_pl)  # Creates lazy pytae.DataFrame (is_lazy == True)
```

---

<a id="the-pt-namespace-accessor"></a>
## The `.pt` Namespace Accessor

Pytae registers the `.pt` accessor across **all major tabular types**:
- `pandas.DataFrame.pt`
- `pandas.Series.pt`
- `polars.DataFrame.pt`
- `polars.LazyFrame.pt`

Once you access `.pt`, you enter Pytae's concise grammar and can chain verbs continuously without repeatedly invoking `.pt`:

```python
import pandas as pd
import pytae as pt

# Chain directly off any Pandas DataFrame
pd_df = pd.read_csv("raw.csv")
clean_df = (
    pd_df.pt
    .filter("status == 'active'")
    .mutate(tax="total * 0.08")
    .by("region")
    .agg(total_rev="sum(total)", avg_tax="mean(tax)")
)
```

### Transparent Polars Verb Delegation
Any Polars method not explicitly shadowed by Pytae (e.g. `.describe()`, `.estimated_size()`, `.glimpse()`, `.explode()`, `.with_columns()`) automatically delegates to the underlying Polars DataFrame or LazyFrame:

```python
# Polars methods work seamlessly on pytae.DataFrame
df = pt.read_parquet("sales.parquet")
print(df.estimated_size())
```

---

<a id="dual-mode-execution"></a>
## Dual-Mode Execution & Lazy Evaluation

Pytae operates in two execution modes:

```python
df_eager = pt.read_parquet("small.parquet")  # df_eager.is_lazy == False
df_lazy  = pt.scan_parquet("huge.parquet")   # df_lazy.is_lazy == True
```

### 1. Zero-Cost Schema & Metadata Inspection
On a lazy dataset, querying schema, column names, or dimensions does not read row data:
```python
lazy_df = pt.scan_parquet("terabyte_table.parquet")

# Instant metadata access (reads file footer only)
print(lazy_df.columns)
print(lazy_df.schema)
print(lazy_df.is_lazy)  # True
```

### 2. Just-In-Time Materialization (`.collect()`)
Chain verbs as a pure computation graph. Call `.collect()` only when you need the in-memory results:

```python
result = (
    pt.scan_parquet("sales_100M.parquet")
    .filter("year == 2024")
    .select("store_id", "revenue")
    .by("store_id")
    .agg(total_rev="sum(revenue)")
    .arrange("-total_rev")
    .head(5)
    .collect()  # Pushdowns optimize reading; only top 5 rows returned
)
```

### 3. Out-Of-Core Streaming Sinks
You don't even need to call `.collect()` to write large files:
```python
# Streams out-of-core directly to Parquet or CSV without consuming RAM:
(
    pt.scan_parquet("raw_lake/*.parquet")
    .filter("status == 'valid'")
    .to_parquet("clean_lake.parquet")
)
```

---

<a id="lambdas-and-callables"></a>
## Python Lambdas & Custom Callables

While string formulas (`"x > 10"`) are vectorized and fast, Pytae allows arbitrary Python functions and lambdas inside `.filter()` and `.mutate()`:

```python
# Complex boolean filter using Python lambda
penguins.filter(lambda d: (d["body_mass_g"] > 4000) & (d["species"].str.contains("Ad")))

# Custom feature derivation
def compute_score(d):
    return d["bill_length_mm"] * 1.5 + d["bill_depth_mm"]

penguins.mutate(custom_score=compute_score)
```

---

<a id="interoperability"></a>
## Zero-Copy Interoperability (`to_polars`, `to_pandas`)

Switch between Pytae, Polars, and Pandas with zero overhead:

```python
df = pt.read_parquet("data.parquet")

# Return native Polars DataFrame or LazyFrame
pl_df = df.to_polars()

# Return native Pandas DataFrame (via PyArrow zero-copy buffer)
pd_df = df.to_pandas()
```

---

<a id="sample-datasets"></a>
## Bundled Sample Datasets (`pt.sample`)

Pytae includes bundled sample datasets for prototyping, documentation examples, and testing without downloading external files:

```python
import pytae as pt

# Load sample datasets as pytae.DataFrames
penguins = pt.sample("penguins")
titanic  = pt.sample("titanic")
diamonds = pt.sample("diamonds")
flights  = pt.sample("flights")

# Access all available sample names
print(list(pt.sample_data.keys()))
```
