# Pytae Comparison & Philosophy: Pytae vs. Pandas vs. dplyr

[← Back to Documentation](../readme.md)

A detailed comparison of **`pytae`**, **Pandas**, and R's **`dplyr`**, including the architectural philosophy and naming rationale behind Pytae's concise vocabulary.

---

## Contents

- [The Core Philosophy: "One and Only One Right Way"](#the-core-philosophy-one-and-only-one-right-way)
- [Naming Rationale: Why `qry`, `dedupe`, `arrange`?](#naming-rationale-why-qry-dedupe-arrange)
- [Feature-by-Feature Rosetta Stone](#feature-by-feature-rosetta-stone)
  - [1. Row Filtering](#1-row-filtering)
  - [2. Feature Engineering & Column Derivations](#2-feature-engineering--column-derivations)
  - [3. Column Selection & Exclusion](#3-column-selection--exclusion)
  - [4. Row Sorting](#4-row-sorting)
  - [5. Slicing Top / Bottom Records](#5-slicing-top--bottom-records)
  - [6. Grouped Aggregation](#6-grouped-aggregation)
  - [7. Reshaping & Pivoting](#7-reshaping--pivoting)
  - [8. Fast Inspection](#8-fast-inspection)
- [Summary: Why Use Pytae?](#summary-why-use-pytae)

---

## The Core Philosophy: "One and Only One Right Way"

In Python, the Zen of Python states: *"There should be one-- and preferably only one --obvious way to do it."*

However, in standard **Pandas**, common tasks often suffer from multiple competing paradigms, verbose boilerplate, and inconsistent APIs:
- Filtering can be done via boolean masks `df[df['a'] > 1]`, `.loc[...]`, `.query(...)`, or `.filter()`.
- Renaming columns and index management require constant defensive resets: `.reset_index()`, `.rename_axis(None)`, and multi-line flattening.
- Reshaping produces hierarchical `MultiIndex` objects that disrupt downstream chaining.

In R's **`dplyr`**, the grammar of data manipulation is elegant and highly readable (`filter`, `select`, `mutate`, `arrange`, `summarise`), but porting it to Python is notoriously difficult due to Python's lexical scoping, quotation rules, and execution models.

**`pytae` bridges this gap:**
1. **Zero Redundancy**: Exactly one canonical verb per action across both Python (`df.pt.<verb>()`, `pt.<verb>(df)`) and CLI (`-<verb>`).
2. **Predictable Types**: Output is always flat 1D columns with clean `RangeIndex(0, 1, 2, ...)` — no lingering MultiIndexes or index traps.
3. **Ergonomic Shell & Code Alignment**: The exact same syntax that powers your interactive Jupyter session runs identically on the command line.

---

## Naming Rationale: Why `qry`, `dedupe`, `arrange`?

Pytae carefully chooses concise, intention-revealing names that prevent keyword collisions and ambiguous syntax:

### 1. `qry` instead of `query` or `filter`
- **Why not `filter`?** In Python, `filter` is a built-in function (`filter(predicate, iterable)`). Overriding it shadows built-in globals. Furthermore, in Pandas, `df.filter()` only filters column/index labels, not row values.
- **Why `qry` over `query`?** Pandas has a native `df.query()` method that passes strings to `numexpr`. Using `qry` (`df.pt.qry(...)`) avoids colliding with Pandas' native method while signaling enhanced capabilities: support for mathematical intervals (`"[3000, 4500]"`), dictionary syntax (`{"col": "> 5"}`), and seamless column names with spaces without awkward backtick escaping.

### 2. `dedupe` instead of `unique` or `drop_duplicates`
- **Why not `drop_duplicates`?** In Python, `df.drop_duplicates()` is native, but on the CLI typing `-drop_duplicates` is needlessly verbose.
- **Why not `unique`?** In Pandas, `.unique()` is a Series method returning a numpy array of distinct scalar values, whereas deduplication preserves the entire 2D table row structure. Calling it `dedupe` (`-dedupe [COLS]`) directly conveys that rows are deduplicated across columns.

### 3. `arrange` instead of `sort` or `sort_by`
- **Why not `sort`?** Python's list has `.sort()`, and Pandas previously had `.sort()` (deprecated in favor of `.sort_values()`). In CLI flags, `-sort` is ambiguous (does it sort rows, columns, or files?).
- **Why not `sort_by`?** `arrange` is the canonical tidyverse verb for row ordering. It cleanly conveys ordering rows without implying whether index or values are being sorted. It supports leading `-col` shorthand, explicit `asc`/`desc`, and square brackets `[col name]`.

### 4. `agg` instead of `agg_df` or `summarise`
- **Why not `summarise`?** In Python, `summarise` vs `summarize` introduces spelling ambiguity (British vs American English).
- **Why `agg`?** `agg` is universally recognized in Pandas (`.agg()`). By elevating `agg` (`df.pt.agg()` and CLI `-agg`), pytae eliminates legacy confusion while providing declarative named aggregations (`avg_mass="body_mass_g.mean()"`, `n="n"`).

### 5. `long` and `wide` instead of `melt`, `stack`, `unstack`, `pivot_wider`
- Pytae uses strictly complementary, intuitive English opposites: `long` turns wide tables into tall records; `wide` spreads long records back into headers. Both use identical `c=` (column dimension), `v=` (value column), and `r=` (row identifiers) vocabularies.

---

## Feature-by-Feature Rosetta Stone

### 1. Row Filtering

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Simple Filter** | `df[df['x'] > 10]` | `filter(df, x > 10)` | `df.pt.qry("x > 10")` | `-qry "x > 10"` |
| **Interval / Range** | `df[(df['x'] >= 10) & (df['x'] <= 20)]` | `filter(df, between(x, 10, 20))` | `df.pt.qry(x="[10, 20]")` | `-qry "x = [10, 20]"` |
| **List Membership** | `df[df['cat'].isin(['A', 'B'])]` | `filter(df, cat %in% c('A', 'B'))` | `df.pt.qry(cat=['A', 'B'])` | `-qry "cat = ['A', 'B']"` |
| **Spaced Columns** | `df[df['col name'] > 5]` | `filter(df, `col name` > 5)` | `df.pt.qry("[col name] > 5")` | `-qry "[col name] > 5"` |

---

### 2. Feature Engineering & Column Derivations

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Formulas** | `df.assign(y=df['a'] / df['b'])` | `mutate(df, y = a / b)` | `df.pt.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential** | Requires multiple `.assign()` or statements | `mutate(df, a=1, b=a*2)` | `df.pt.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **If-Else** | `np.where(df['x'] > 0, 'pos', 'neg')` | `if_else(x > 0, 'pos', 'neg')` | `df.pt.mutate(flag="if_else(x > 0, 'pos', 'neg')")` | `-mutate "flag=if_else(x > 0, 'pos', 'neg')"` |
| **Grouped Window** | `df.groupby('g')['x'].transform('mean')` | `df %>% group_by(g) %>% mutate(m = mean(x))` | `df.pt.mutate(m="mean(x)", by="g")` | `-by g -mutate "m = mean(x)"` |

---

### 3. Column Selection & Exclusion

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Select Columns** | `df[['a', 'b']]` | `select(df, a, b)` | `df.pt.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `df.drop(columns=['a', 'b'])` | `select(df, -a, -b)` | `df.pt.select("-a", "-b")` | `-select "-a,-b"` |
| **Pattern Match** | `df.filter(like='score')` | `select(df, contains("score"))` | `df.pt.select(contains="score")` | `-select "contains=score"` |
| **Reorder with Rest** | `df[['lead'] + [c for c in df if c != 'lead']]` | `select(df, lead, everything())` | `df.pt.select("lead", pt.everything)` | N/A |

---

### 4. Row Sorting

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Ascending** | `df.sort_values('x')` | `arrange(df, x)` | `df.pt.arrange("x")` | `-arrange x` |
| **Descending** | `df.sort_values('x', ascending=False)` | `arrange(df, desc(x))` | `df.pt.arrange("x desc")` or `df.pt.arrange("-x")` | `-arrange "x desc"` or `-arrange "-x"` |
| **Multi-Column** | `df.sort_values(['a', 'b'], ascending=[True, False])` | `arrange(df, a, desc(b))` | `df.pt.arrange("a", "-b")` | `-arrange "a, -b"` |

---

### 5. Slicing Top / Bottom Records

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Top N Overall** | `df.nlargest(3, 'x')` | `slice_max(df, x, n = 3)` | `df.pt.slice_max("x", n=3)` | `-slice_max "x:3"` |
| **Bottom N Overall**| `df.nsmallest(3, 'x')` | `slice_min(df, x, n = 3)` | `df.pt.slice_min("x", n=3)` | `-slice_min "x:3"` |
| **Top N per Group** | `df.groupby('g').apply(lambda d: d.nlargest(2, 'x')).reset_index(drop=True)` | `df %>% group_by(g) %>% slice_max(x, n = 2)` | `df.pt.slice_max("x", n=2, by="g")` | `-by g -slice_max "x:2"` |

---

### 6. Grouped Aggregation

| Operation | Pandas | dplyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Simple Group** | `df.groupby('g')['x'].mean().reset_index()` | `df %>% group_by(g) %>% summarise(mean_x = mean(x))` | `df.pt.agg("g", x="mean")` | `-by g -agg x=mean` |
| **With Row Count**| `df.groupby('g').agg(mean_x=('x', 'mean'), n=('x', 'size')).reset_index()` | `df %>% group_by(g) %>% summarise(mean_x = mean(x), n = n())` | `df.pt.agg("g", mean_x="x:mean", n="n")` | `-by g -agg "mean_x=x:mean, n=n"` |
| **Whole-Table Total**| `df[['x']].agg('mean').to_frame().T` | `summarise(df, mean_x = mean(x))` | `df.pt.agg(None, x="mean")` | `-agg x=mean` |

---

### 7. Reshaping & Pivoting

| Operation | Pandas | tidyr (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Wide to Long** | `pd.melt(df, id_vars=['id'], value_vars=['x', 'y'])` | `pivot_longer(df, cols = c(x, y))` | `df.pt.long(id_vars="id", cols=["x", "y"])` | `-long "r=id, c='x,y'"` |
| **Long to Wide (1:1)**| `df.pivot(index='id', columns='var', values='val').reset_index()` | `pivot_wider(df, names_from = var, values_from = val)` | `df.pt.wide(c="var", v="val", index="id")` | `-wide "c=var, v=val, r=id"` |
| **2D Pivot Table** | `pd.pivot_table(df, index='r', columns='c', values='v', aggfunc='mean').reset_index()` | `df %>% group_by(r, c) %>% summarise(...) %>% pivot_wider(...)` | `df.pt.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

---

### 8. Fast Inspection

| Operation | Pandas | dplyr / tibble (R) | Pytae (`df.pt`) | Pytae CLI |
|---|---|---|---|---|
| **Transposed View** | `df.info()` or `df.T.head()` | `glimpse(df)` | `df.pt.glimpse()` | `-glimpse` |
| **Sorted Column List**| `sorted(df.columns)` | `names(df)` | `df.pt.cols()` | `-cols asc` |
| **Copy to Clipboard**| `df.to_clipboard(index=False)` | `clipr::write_clip(df)` | `df.to_clip()` | `-o clip` |

---

## Summary: Why Use Pytae?

- **Zero Cognitive Overhead**: You don't have to remember when to call `.reset_index()`, whether `axis=0` or `axis=1` is required, or how to unpack MultiIndex tuples.
- **Fluent & Composable**: Every operation returns a clean, standard Pandas DataFrame that seamlessly integrates with existing Python code.
- **Identical Terminal Experience**: Any workflow developed in Python notebooks translates verbatim into shell pipelines with `pytae`.
