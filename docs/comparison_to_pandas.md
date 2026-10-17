# Pytae vs. Pandas — Deep Dive & Rosetta Stone

[← Back to Master Reference](pytae.md) | [Comparison with dplyr](comparison_to_dplyr.md) | [Comparison with SAS](comparison_to_sas.md)

Pandas has been the cornerstone of data analysis in Python for over fifteen years. However, its expansive, organically grown API has accumulated significant friction: competing ways to perform identical operations, complex index hierarchies, silent data loss traps, and single-threaded performance bottlenecks.

`pytae` is built from the ground up on native **Polars** vector execution to provide a clean, modern alternative centered on **"One and Only One Obvious Way"**.

---

## Key Architectural Differences: Pytae vs. Pandas

```
┌───────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
│ Architectural Dimension       │ Pandas                           │ Pytae                            │
├───────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
│ Core Philosophy               │ Multiple competing APIs per task │ One and Only One Obvious Way     │
│ Underlying Execution Engine   │ Single-threaded Python & NumPy   │ Multithreaded Rust SIMD (Polars) │
│ Index Hierarchy               │ Index, MultiIndex, Series index  │ None (Pure flat RangeIndex)      │
│ Output Columns                │ Hierarchical MultiIndex tuples   │ Always flat 1D string headers    │
│ Grouping Scope                │ Stateful DataFrameGroupBy object │ Single-shot context (auto-clears)│
│ Aggregation Missing Keys      │ dropna=True (Drops missing keys!)│ dropna=False (Zero Data Loss)    │
│ Default Row-Dropping          │ dropna() drops if ANY column NA  │ dropna() drops only 100% blanks  │
│ Float NaN vs Arrow Null       │ Conflated into np.nan / pd.NA    │ Differentiated; dual-cleaned     │
│ Command-Line Equivalence      │ None (requires Python script)    │ 100% grammar parity via CLI      │
└───────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
```

---

## 1. Index Hell: The MultiIndex Nightmare vs. Flat 1D DataFrames

### The Pandas Trap
In Pandas, nearly every structural operation creates or manipulates an `Index`:
1. Grouped aggregations move group columns into the row index:
   ```python
   # Pandas produces a DataFrame where ('species', 'island') is an index, not columns!
   agg_df = df.groupby(['species', 'island']).mean()
   # Forgetting this line breaks subsequent joins, filtering, and exports:
   agg_df = agg_df.reset_index()
   ```
2. Multi-metric aggregations generate nested `MultiIndex` column tuples:
   ```python
   agg_df = df.groupby('species').agg({'mass': ['mean', 'max']})
   # Columns are now: [('mass', 'mean'), ('mass', 'max')]
   # Flattening requires manual list comprehensions:
   agg_df.columns = ['_'.join(c).strip() for c in agg_df.columns.values]
   ```
3. Pivoting leaves lingering dimension names (`columns.name = 'variable'`) that contaminate CSV and Parquet schemas.

### The Pytae Solution
In Pytae, **data structures are always pure, flat 2D tables**:
- There is no custom index to manage. All DataFrames use standard `RangeIndex(0, 1, 2, ...)`.
- Aggregations always return normal columns without needing `.reset_index()`.
- Reshaping verbs (`wide()`, `long()`, `pivot()`) produce flat, clean 1D column headers.

```python
# Pytae: Always flat, always predictable, immediately chainable
(
    penguins
    .by("species", "island")
    .agg(avg_mass="body_mass_g:mean", max_mass="body_mass_g:max")
    .filter("avg_mass > 4000")
)
```

---

## 2. Silent Data Loss Traps: Pandas Defaults vs. Pytae "Zero Data Loss"

### Trap A: Silent Group Elimination (`dropna=True`)
In Pandas, `df.groupby()` defaults to `dropna=True`. If any row contains a missing value (`NaN` or `None`) in a grouping key, **Pandas silently discards the entire row from the aggregated result**:

```python
# PANDAS: Any penguin with sex=NaN is completely omitted from the summary!
penguins.groupby('sex').size()
# Output: Female: 165, Male: 168 (Total = 333 rows; 11 rows vanished silently!)
```

In Pytae, analytical verbs (`by`, `agg`, `pivot`, `freq`) default to **`dropna=False` (Zero Data Loss by Default)**. Unclassified, missing, or orphan records remain visible:

```python
# PYTAE: Missing groups are preserved explicitly
penguins.by("sex").agg(n="n")
# Output: Female: 165, Male: 168, null: 11 (Total = 344 rows; 100% accounted for)
```

### Trap B: Aggressive Row Deletion (`dropna()`)
In Pandas, calling `df.dropna()` without arguments defaults to `how='any'`. If a dataset has 100 columns and a single optional column (e.g., `apartment_suite_number`) is missing, **the entire customer record is deleted**:

```python
# PANDAS: Accidental data catastrophe
df.dropna()  # Deletes rows missing ANY column
```

In Pytae, bare `df.dropna()` defaults to `how='all'`. Only completely blank rows (100% missing across all columns) are dropped. When you want to drop rows missing specific required columns, you pass those columns explicitly:

```python
# PYTAE: Non-destructive Option B semantics
df.dropna()                       # Drops only 100% blank rows
df.dropna("customer_id", "email") # Drops rows missing required keys (how='any')
```

---

## 3. Grouping Semantics: Lazy `DataFrameGroupBy` vs. Single-Shot `by()`

### The Pandas Trap
In Pandas, `.groupby()` returns a lazy intermediate `DataFrameGroupBy` object. This object splits the API: some methods work on it, others do not. You cannot chain regular DataFrame methods without aggregating first or invoking complex `.apply()` functions that cause severe performance degradation.

### The Pytae Solution
In Pytae, grouping is **single-shot, non-destructive, and auto-clearing**:
- `df.by(*cols)` sets a transient grouping context for the *immediate next verb* (`mutate`, `agg`, `pick`).
- The operation evaluates within each group and **immediately returns a clean, ungrouped DataFrame**.
- You can transition seamlessly across different grouping levels in a single method chain without resetting:

```python
# Calculate group mean, then overall mean, then subgroup mean in ONE chain:
(
    df
    .by("region").mutate(reg_avg="mean(sales)")
    .mutate(global_avg="mean(sales)")
    .by("region", "department").mutate(dept_avg="mean(sales)")
)
```

---

## 4. Performance: Single-Threaded GIL vs. Native Polars SIMD

| Metric | Pandas | Pytae |
|:---|:---|:---|
| **Architecture** | Python interpreter + C/NumPy arrays | 100% Native Rust + Apache Arrow |
| **Multithreading** | Single-threaded; blocked by Python GIL | Automatically parallelized across all CPU cores |
| **Vectorization** | Limited NumPy SIMD | Full AVX-512 / AVX2 / NEON vector pipelines |
| **Memory Usage** | High (object pointers, duplicate copies) | Minimal (Arrow chunked memory, string cache) |
| **Lazy Execution** | No native lazy engine | `pt.scan_parquet()` query planning |

---

## 5. Feature-by-Feature Rosetta Stone: Pytae vs. Pandas

### 1. Row Filtering
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Boolean Mask** | `df[df['sales'] > 100]` | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `df[(df['a'] > 1) & (df['b'] == 'E')]` | `df.filter("a > 1 & b == 'E'")` | `-filter "a > 1, b == 'E'"` |
| **Interval / Range** | `df[df['x'].between(10, 20)]` | `df.filter(x="[10, 20]")` | `-filter "x = [10, 20]"` |
| **Set Membership** | `df[df['cat'].isin(['A', 'B'])]` | `df.filter(cat=['A', 'B'])` | `-filter "cat = ['A', 'B']"` |
| **Spaced Columns** | `df[df['gross sales'] > 50]` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **String Prefix** | `df[df['name'].str.startswith('A')]` | `df.filter(name=('startswith', 'A'))` | `-filter "name.startswith('A')"` |
| **Null Row Check** | `df[df['col'].notna()]` | `df.filter("col.notna()")` | `-filter "col.notna()"` |
| **Callable / Lambda** | `df[lambda d: d['x'] > 5]` | `df.filter(lambda d: d['x'] > 5)` | N/A |

### 2. Feature Engineering & Column Derivations (`mutate`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Basic Formula** | `df.assign(y=df['a'] / df['b'])` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential Calculations**| Chained `.assign(a=...).assign(b=lambda ...)` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **If / Else** | `np.where(df['x'] > 0, 'pos', 'neg')` | `df.mutate(f="if_else(x > 0, 'pos', 'neg')")` | `-mutate "f=if_else(x>0,'pos','neg')"` |
| **Multi-Branch (Case)** | `np.select([c1, c2], [v1, v2], default=v3)` | `df.mutate(f="case_when(c1, v1, c2, v2, v3)")` | `-mutate "f=case_when(c1,v1,v3)"` |
| **Value Mapping** | `df['x'].map({'A': 1, 'B': 2})` | `df.mutate(x="map(x, {'A': 1, 'B': 2})")` | `-mutate "x=map(x, {'A':1})"` |
| **Multi-Column Transform**| Loop over columns or complex `apply` | `df.mutate("(a, b) = _ * 10")` | `-mutate "(a, b) = _ * 10"` |
| **Multi-Column + Suffix**| Loop + dictionary comprehension | `df.mutate("(a, b)_cm = _ * 10")` | `-mutate "(a, b)_cm = _ * 10"` |
| **Grouped Window Calculation**| `df.groupby('g')['x'].transform('mean')` | `df.by("g").mutate(m="mean(x)")` | `-by g -mutate "m = mean(x)"` |
| **Lag / Shift** | `df.groupby('g')['x'].shift(1)` | `df.by("g").mutate(prev="shift(x, 1)")` | `-by g -mutate "prev=shift(x,1)"` |

### 3. Column Selection, Renaming & Exclusion (`select`, `rename`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Select Columns** | `df[['a', 'b']]` | `df.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `df.drop(columns=['c', 'd'])` | `df.select("-c", "-d")` | `-select "-c,-d"` |
| **Pattern Match** | `df.filter(like='bill')` | `df.select(contains="bill")` | `-select "contains=bill"` |
| **Prefix Match** | `df[[c for c in df if c.startswith('b')]]`| `df.select(starts_with="b")` | `-select "starts_with=b"` |
| **Inline Rename** | `df[['a']].rename(columns={'a': 'b'})` | `df.select("a:b")` | `-select "a:b"` |
| **Dedicated Rename** | `df.rename(columns={'a': 'b'})` | `df.rename("a:b")` | `-rename "a:b"` |
| **Reorder with Rest** | `df[['lead'] + [c for c in df if c != 'lead']]` | `df.select("lead", pt.everything)` | N/A |

### 4. Row Sorting (`arrange`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Ascending** | `df.sort_values('sales')` | `df.arrange("sales")` | `-arrange sales` |
| **Descending** | `df.sort_values('sales', ascending=False)` | `df.arrange("sales desc")` | `-arrange "sales desc"` |
| **Multi-Column Mixed** | `df.sort_values(['a', 'b'], ascending=[True, False])` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |
| **Spaced Columns** | `df.sort_values('gross sales')` | `df.arrange("[gross sales] desc")` | `-arrange "[gross sales] desc"` |

### 5. Grouped Aggregation (`by` + `agg`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Group & Summarize** | `df.groupby('g')['x'].mean().reset_index()` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Row Count** | `df.groupby('g').size().reset_index(name='n')` | `df.by("g").agg(n="n")` | `-by g -agg n=n` |
| **Multiple Metrics** | `df.groupby('g').agg(m=('x','mean'), s=('x','sum')).reset_index()` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Keep NA Groups** | `df.groupby('g', dropna=False).mean().reset_index()` | Default behavior (`dropna=False`) | Default behavior |
| **Whole-Table Summary**| `df.agg({'x': 'mean'}).to_frame().T` | `df.agg(m="x:mean", n="n")` | `-agg "m=x:mean,n=n"` |

### 6. Slicing Top / Bottom Records (`pick`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `df.nlargest(5, 'sales')` | `df.pick("sales", n=5)` | `-pick "sales,n=5"` |
| **Bottom N Records** | `df.nsmallest(5, 'sales')` | `df.pick("sales", n=5, order="min")` | `-pick "sales,n=5,order=min"` |
| **Top Percentage** | `df.nlargest(int(len(df)*0.1), 'sales')` | `df.pick("sales", prop=0.1)` | `-pick "sales,prop=0.1"` |
| **Top N per Group** | `df.groupby('g').apply(lambda d: d.nlargest(3, 'x')).reset_index(drop=True)` | `df.by("g").pick("x", n=3)` | `-by g -pick "x,n=3"` |

### 7. Deduplication (`distinct`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Deduplicate Table** | `df.drop_duplicates().reset_index(drop=True)` | `df.distinct()` | `-distinct` |
| **Subset Deduplication**| `df.drop_duplicates(subset=['a', 'b']).reset_index(drop=True)` | `df.distinct("a", "b")` | `-distinct "a,b"` |
| **Keep Last Occurrence**| `df.drop_duplicates(subset=['a'], keep='last').reset_index(drop=True)` | `df.distinct("a", keep="last")` | `-distinct "a,keep=last"` |

### 8. Reshaping & Pivoting (`wide`, `long`, `pivot`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Wide to Long (Melt)** | `pd.melt(df, id_vars=['id'], value_vars=['x', 'y'])` | `df.long(id_vars="id", cols=["x", "y"])` | `-long "id_vars=id, cols='x,y'"` |
| **Long to Wide (Spread)**| `df.pivot(index='id', columns='var', values='val').reset_index()` | `df.wide(r="id", c="var", v="val")` | `-wide "r=id, c=var, v=val"` |
| **2D Pivot Matrix** | `pd.pivot_table(df, index='r', columns='c', values='v', aggfunc='mean').reset_index()` | `df.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

### 9. Relational Joins (`join`, `concat`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Inner Join** | `pd.merge(df1, df2, on='id', how='inner')` | `df1.join(df2, on="id", how="inner")` | `-join "file2.parquet,on=id"` |
| **Left Join** | `pd.merge(df1, df2, on='id', how='left')` | `df1.join(df2, on="id", how="left")` | `-join "file2.parquet,on=id,how=left"` |
| **Different Key Names** | `pd.merge(df1, df2, left_on='a', right_on='b')` | `df1.join(df2, on="a:b")` | `-join "file2.parquet,on=a:b"` |
| **Cardinality Check** | `pd.merge(df1, df2, on='id', validate='1:m')` | `df1.join(df2, on="id", validate="1:m")` | `-join "f2.parquet,on=id,validate=1:m"` |
| **Vertical Stack** | `pd.concat([df1, df2], ignore_index=True)` | `pt.concat([df1, df2], how="vertical")` | N/A |

### 10. In-Flight Inspection & Profiling
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Schema & Glimpse** | `df.info()` | `df.glimpse()` *(Non-destructive)* | `-glimpse` |
| **Categorical Frequency**| `df['col'].value_counts(dropna=False)` | `df.freq("col")` *(With ASCII bars)* | `-freq col` |
| **Histogram Bins** | `pd.cut(df['x'], 10).value_counts()` | `df.hist("x", bins=10)` *(With ASCII bars)*| `-hist x:10` |
| **Dataset Comparison** | `df1.compare(df2)` *(Fails on misaligned index)*| `df1.diff(df2, tol=0.01)` | `pytae f1.parquet -diff f2.parquet,tol=0.01` |
| **Clipboard Export** | `df.to_clipboard(index=False)` | `df.to_clip()` | `-o clip` |

---

## 6. End-to-End Pipeline Comparison

### The Task:
From a raw dataset of penguin observations:
1. Filter for penguins heavier than 3.5 kg with non-null sex.
2. Calculate mass in kg and the ratio of bill length to depth.
3. Group by species and island.
4. Calculate count, average mass, and maximum bill ratio.
5. Sort by average mass descending.
6. Export to Parquet.

### In Pandas:
```python
import pandas as pd
import numpy as np

df = pd.read_parquet("penguins.parquet")

# 1. Filtering
filtered = df[(df["body_mass_g"] > 3500) & (df["sex"].notna())].copy()

# 2. Feature Engineering
filtered["body_mass_kg"] = filtered["body_mass_g"] / 1000
filtered["bill_ratio"] = filtered["bill_length_mm"] / filtered["bill_depth_mm"]

# 3 & 4. Grouping & Aggregation (defensive dropna=False and reset_index)
summary = (
    filtered
    .groupby(["species", "island"], dropna=False)
    .agg(
        n=("body_mass_g", "size"),
        avg_mass_kg=("body_mass_kg", "mean"),
        max_ratio=("bill_ratio", "max")
    )
    .reset_index()
)

# 5. Sorting
sorted_summary = summary.sort_values("avg_mass_kg", ascending=False)

# 6. Export
sorted_summary.to_parquet("summary.parquet", index=False)
```

### In Pytae (Python Library):
```python
import pytae as pt

(
    pt.read_parquet("penguins.parquet")
    .filter("body_mass_g > 3500 & sex.notna()")
    .mutate(body_mass_kg="body_mass_g / 1000", bill_ratio="bill_length_mm / bill_depth_mm")
    .by("species", "island")
    .agg(n="n", avg_mass_kg="mean(body_mass_kg)", max_ratio="max(bill_ratio)")
    .arrange("avg_mass_kg desc")
    .to_parquet("summary.parquet")
)
```

### In Pytae (Unix CLI Pipeline):
```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500, sex.notna()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -by species,island \
  -agg "n = n, avg_mass_kg = mean(body_mass_kg), max_ratio = max(bill_ratio)" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

Notice the stark contrast: Pytae eliminates intermediate variables, eliminates `.copy()`, eliminates `.reset_index()`, eliminates `index=False`, and translates 1:1 into a single high-performance terminal command.

