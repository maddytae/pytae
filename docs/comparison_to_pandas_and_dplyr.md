# Pytae Comparison & Philosophy: Pytae vs. Pandas vs. dplyr

[← Back to Documentation](../readme.md) | **Dedicated Deep Dives:** [Pytae vs. Pandas](comparison_to_pandas.md) | [Pytae vs. dplyr](comparison_to_dplyr.md) | [Pytae vs. SAS](comparison_to_sas.md)

A detailed comparison of **`pytae`**, **Pandas**, and R's **`dplyr`**, including the architectural philosophy and naming rationale behind Pytae's concise vocabulary. For comprehensive deep dives tailored to specific ecosystems, see the dedicated guides linked above.

---

## Contents

- [The Core Philosophy: "One and Only One Obvious Way"](#the-core-philosophy-one-and-only-one-obvious-way)
- [Naming Rationale: Why `filter`, `distinct`, `by`, `arrange`?](#naming-rationale-why-filter-distinct-by-arrange)
- [Feature-by-Feature Rosetta Stone](#feature-by-feature-rosetta-stone)
  - [1. Row Filtering](#1-row-filtering)
  - [2. Feature Engineering & Column Derivations](#2-feature-engineering--column-derivations)
  - [3. Column Selection & Exclusion](#3-column-selection--exclusion)
  - [4. Row Sorting](#4-row-sorting)
  - [5. Slicing Top / Bottom Records](#5-slicing-top--bottom-records)
  - [6. Grouped Aggregation & Grouping Context](#6-grouped-aggregation--grouping-context)
  - [7. Deduplication & Distinct Records](#7-deduplication--distinct-records)
  - [8. Reshaping & Pivoting](#8-reshaping--pivoting)
  - [9. Fast Inspection](#9-fast-inspection)
- [Summary: Why Use Pytae?](#summary-why-use-pytae)

---

## The Core Philosophy: "One and Only One Obvious Way"

In Python, the Zen of Python states: *"There should be one-- and preferably only one --obvious way to do it."*

However, in standard **Pandas**, common tasks often suffer from multiple competing paradigms, verbose boilerplate, and inconsistent APIs:
- Filtering can be done via boolean masks `df[df['a'] > 1]`, `.loc[...]`, `.query(...)`, or `.filter()`.
- Renaming columns and index management require constant defensive resets: `.reset_index()`, `.rename_axis(None)`, and multi-line flattening.
- Reshaping produces hierarchical `MultiIndex` objects that disrupt downstream chaining.

In R's **`dplyr`**, the grammar of data manipulation is elegant and highly readable (`filter`, `select`, `mutate`, `arrange`, `distinct`, `summarise`), but porting it to Python is notoriously difficult due to Python's lexical scoping, quotation rules, and execution models.

**`pytae` bridges this gap:**
1. **Zero Redundancy**: Exactly one canonical verb per action across both Python (`df.<verb>()`, `pt.<verb>(df)`) and CLI (`-<verb>`). (When working on external Pandas/Polars frames, `df.pt.<verb>()` is also supported).
2. **Predictable Types**: Output is always flat 1D columns with clean `RangeIndex(0, 1, 2, ...)` — no lingering MultiIndexes or index traps.
3. **Ergonomic Shell & Code Alignment**: The exact same syntax that powers your interactive Jupyter session runs identically on the command line.

---

## Naming Rationale: Why `filter`, `distinct`, `by`, `arrange`?

Pytae carefully chooses concise, intention-revealing names that prevent keyword collisions and ambiguous syntax:

### 1. `filter` instead of `query` or `qry`
- **Why `filter`?** `filter` is the canonical, intuitive verb across data science (R `dplyr`, SQL `FILTER`, Polars, Spark). Calling it `filter` provides immediate familiarity.
- **Why not `df.query()`?** Pandas' native `df.query()` is string-only and passes strings to `numexpr`. In contrast, `df.filter()` supports:
  - **Bare Callables / Lambdas**: `df.filter(lambda d: d['mass'] > 4000)` with full Python expressions and functions.
  - **Mathematical Intervals**: `"[3000, 4500]"` or `"(0, 100)"`.
  - **Set Membership & Operators**: lists `['A', 'B']`, tuples `('startswith', 'Ad')`.
  - **Spaced Columns**: bracketed column names `"[bill length mm] > 40"` without backticks.
  - **Dictionary Syntax**: `{"col": "> 5"}` or keyword arguments.
- **CLI Alignment**: The CLI uses `-filter "expr"`. (The legacy `-qry` has been deprecated in favor of canonical `-filter`).

### 2. `distinct` instead of `dedupe`, `unique`, or `drop_duplicates`
- **Why `distinct`?** `distinct` is the universally recognized term in SQL (`SELECT DISTINCT`) and dplyr (`distinct()`). It clearly describes returning unique, deduplicated rows.
- **Why not `unique`?** In Pandas, `.unique()` is a Series method returning a 1D numpy array of scalar values, not a DataFrame. Using `unique` would conflate scalar distinct values with row deduplication.
- **CLI Alignment**: The CLI uses `-distinct "species,island"`, with optional `keep=first|last|false` control.

### 3. `by` for Single-Shot Scoped Grouping (Why `ungroup` is Obsolete)
- **Why `by` over `groupby`?** In Pandas, `.groupby()` creates a lazy `DataFrameGroupBy` object that breaks standard DataFrame method chaining and produces multi-level index outputs upon aggregation.
- In R's `dplyr`, `group_by()` produces a sticky grouped tibble that persists across operations unless the user manually chains `%>% ungroup()`.
- **In Pytae, grouping is strictly single-shot and auto-ungrouped**:
  - `df.by(*cols)` sets an active grouping context for the *immediate next verb*.
  - `.mutate()` executes window calculations partitioned by group, consumes the grouping, and immediately returns a clean, ungrouped `DataFrame`.
  - `.pick()` slices extreme rows per group and returns an ungrouped `DataFrame`.
  - `.agg()` collapses per group and returns an ungrouped `DataFrame`.
  - Because grouping is never sticky, subsequent operations naturally evaluate at the whole-table scope without needing an `ungroup()` verb.
- **Fluent Re-Grouping**: You can seamlessly transition between group scopes and overall table scopes in one chain:
  ```python
  df.by("region").mutate(reg_avg="mean(sales)").mutate(overall_avg="mean(sales)").by("product").mutate(prod_avg="mean(sales)")
  ```
- **Strict `*args` Only**: `df.by("species", "island")` requires `*args`. Nested lists (`df.by(["species"])`) and `df.by(None)` are strictly rejected with clear errors.
- **Precedence**: If a second `.by()` is called, it cleanly overwrites the previous grouping context.

### 4. `arrange` instead of `sort` or `sort_by`
- **Why not `sort`?** Python's list has `.sort()`, and Pandas previously had `.sort()` (deprecated in favor of `.sort_values()`). In CLI flags, `-sort` is ambiguous (does it sort rows, columns, or files?).
- **Why not `sort_by`?** `arrange` is the canonical tidyverse verb for row ordering. It cleanly conveys ordering rows without implying whether index or values are being sorted. It supports leading `-col` shorthand, explicit `asc`/`desc`, and square brackets `[col name]`.

### 5. `agg` instead of `summarise` or `summarize`
- **Why not `summarise`?** In Python, `summarise` vs `summarize` introduces spelling ambiguity (British vs American English). Having both violates "one and only one obvious way".
- **Why `agg`?** `agg` is universally recognized in Pandas (`.agg()`). By elevating `agg` (`df.agg()` and CLI `-agg`), pytae eliminates legacy confusion while providing declarative named aggregations (`avg_mass="body_mass_g.mean()"`, `n="n"`).

### 6. `long` and `wide` instead of `melt`, `stack`, `unstack`, `pivot_wider`
- Pytae uses strictly complementary, intuitive English opposites: `long` turns wide tables into tall records; `wide` spreads long records back into headers. Both use identical `c=` (column dimension), `v=` (value column), and `r=` (row identifiers) vocabularies.

### 7. Zero Data Loss by Default: Non-Destructive `dropna` and Option B Semantics
- **Pandas Trap (`dropna=True` and `how='any'`)**: In Pandas, `df.dropna()` without arguments defaults to `how='any'`, silently wiping out rows that have even one optional column missing. In `df.groupby(..., dropna=True)`, Pandas drops rows where grouping keys contain `NaN` or `None` by default! This causes silent data loss in analytical pipelines, hiding unclassified, orphan, or missing data records unless the user explicitly remembers to pass `dropna=False`.
- **Pytae Design (Option B & Zero Data Loss)**:
  - **Bare `dropna()`**: Defaults to `how='all'`. Only completely blank rows (100% null/NaN across all columns) are dropped.
  - **Targeted `dropna("col1", "col2")`**: Defaults to `how='any'` over the specified subset, guaranteeing that only rows missing *required* keys are dropped.
  - **Analytical Verbs (`agg`, `mutate`, `pivot`, `freq`)**: Default to **`dropna=False`**. Missing values (`NaN`/`null`) in grouping or pivot dimensions are retained as visible, explicit group rows/columns.
  - **Dual Missing Value Cleaning**: Drops both Arrow `null` and IEEE-754 float `NaN` by default (`drop_nans=True`), preventing float NaN arithmetic poisoning.
  - **One Obvious Way**: Only `dropna` is used everywhere across library functions, methods, accessors, keyword arguments, and CLI (`-dropna`). Retired aliases (`drop_nulls`, `drop_na`) fail fast with clean redirect guidance.
  - *For deep architectural details and side-by-side examples, see [pytae.md](file:///Users/maddy/Documents/my_repos/pytae/docs/pytae.md).*
- **dplyr Alignment**: This non-destructive default matches R's `dplyr` (which treats `NA` group levels as valid grouping keys by default rather than discarding them).
- **CLI Consistency**: Top-level `-dropna [COLS]` performs row-level dropping across the dataset, whereas scoped `dropna=bool` parameters inside `-agg` or `-pivot` specs specifically control grouping and dimension key retention.

---

## Feature-by-Feature Rosetta Stone

### 1. Row Filtering

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Simple Filter** | `df[df['x'] > 10]` | `filter(df, x > 10)` | `df.filter("x > 10")` | `-filter "x > 10"` |
| **Callable / Lambda** | `df[df['x'] > 10]` | `filter(df, x > 10)` | `df.filter(lambda d: d['x'] > 10)` | N/A |
| **Interval / Range** | `df[(df['x'] >= 10) & (df['x'] <= 20)]` | `filter(df, between(x, 10, 20))` | `df.filter(x="[10, 20]")` | `-filter "x = [10, 20]"` |
| **List Membership** | `df[df['cat'].isin(['A', 'B'])]` | `filter(df, cat %in% c('A', 'B'))` | `df.filter(cat=['A', 'B'])` | `-filter "cat = ['A', 'B']"` |
| **Spaced Columns** | `df[df['col name'] > 5]` | `filter(df, `col name` > 5)` | `df.filter("[col name] > 5")` | `-filter "[col name] > 5"` |

---

### 2. Feature Engineering & Column Derivations

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Formulas** | `df.assign(y=df['a'] / df['b'])` | `mutate(df, y = a / b)` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Multi-Column (`across`)** | `df[['a', 'b']] = df[['a', 'b']] * 1.08` | `mutate(df, across(c(a, b), ~ .x * 1.08))` | `df.mutate("(a, b) = _ * 1.08")` | `-mutate "(a, b) = _ * 1.08"` |
| **Multi-Column + Suffix** | `for c in ['a','b']: df[f'{c}_usd'] = df[c]*1.08` | `mutate(df, across(c(a, b), ~ .x * 1.08, .names="{.col}_usd"))` | `df.mutate("(a, b)_usd = _ * 1.08")` | `-mutate "(a, b)_usd = _ * 1.08"` |
| **Sequential** | Requires multiple `.assign()` or statements | `mutate(df, a=1, b=a*2)` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **If-Else** | `np.where(df['x'] > 0, 'pos', 'neg')` | `if_else(x > 0, 'pos', 'neg')` | `df.mutate(flag="if_else(x > 0, 'pos', 'neg')")` | `-mutate "flag=if_else(x > 0, 'pos', 'neg')"` |
| **Value Mapping / Recoding** | `df['x'].replace({'A': 'B'})` / `df['x'].map({'A': 'B'}).fillna(df['x'])` | `case_match(x, 'A' ~ 'B', .default = x)` | `df.mutate(x="map(x, {'A': 'B'})")` | `-mutate "x = map(x, {'A': 'B'})"` |
| **Missing Imputation** | `df['x'].fillna(0)` | `coalesce(x, 0)` / `replace_na(x, 0)` | `df.mutate(x="fillna(x, 0)")` | `-mutate "x = fillna(x, 0)"` |
| **Inline Type Casting** | `df['x'].astype(int)` | `as.integer(x)` | `df.mutate(x="int(x)")` | `-mutate "x = int(x)"` |
| **Grouped Window** | `df.groupby('g')['x'].transform('mean')` | `df %>% group_by(g) %>% mutate(m = mean(x))` | `df.by("g").mutate(m="mean(x)")` | `-by g -mutate "m = mean(x)"` |
| **Shift / Lag** | `df.groupby('g')['x'].shift(1)` | `lag(x)` | `df.by("g").mutate(prev="shift(x, 1)")` | `-by g -mutate "prev = shift(x, 1)"` |
| **Diff & Returns** | `df.groupby('g')['x'].diff()` | `x - lag(x)` | `df.by("g").mutate(d="x - shift(x, 1)")` | `-by g -mutate "d = x - shift(x, 1)"` |
| **Group Baseline (`first`/`last`)** | `df.groupby('g')['x'].transform('first')` | `first(x)` | `df.by("g").mutate(base="first(x)")` | `-by g -mutate "base = first(x)"` |

---

### 3. Column Selection & Exclusion

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Select Columns** | `df[['a', 'b']]` | `select(df, a, b)` | `df.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `df.drop(columns=['a', 'b'])` | `select(df, -a, -b)` | `df.select("-a", "-b")` | `-select "-a,-b"` |
| **Pattern Match** | `df.filter(like='score')` | `select(df, contains("score"))` | `df.select(contains="score")` | `-select "contains=score"` |
| **Reorder with Rest** | `df[['lead'] + [c for c in df if c != 'lead']]` | `select(df, lead, everything())` | `df.select("lead", pt.everything)` | N/A |

---

### 4. Row Sorting

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Ascending** | `df.sort_values('x')` | `arrange(df, x)` | `df.arrange("x")` | `-arrange x` |
| **Descending** | `df.sort_values('x', ascending=False)` | `arrange(df, desc(x))` | `df.arrange("x desc")` | `-arrange "x desc"` |
| **Multi-Column** | `df.sort_values(['a', 'b'], ascending=[True, False])` | `arrange(df, a, desc(b))` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |

---

### 5. Picking Top / Bottom Records (`pick`)

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Top N Overall** | `df.nlargest(3, 'x')` | `slice_max(df, x, n = 3)` | `df.pick("x", n=3)` | `-pick "x,n=3"` |
| **Top Proportion** | `df.nlargest(int(len(df)*0.1), 'x')` | `slice_max(df, x, prop = 0.1)` | `df.pick("x", prop=0.1)` | `-pick "x,prop=0.1"` |
| **Bottom N Overall**| `df.nsmallest(3, 'x')` | `slice_min(df, x, n = 3)` | `df.pick("x", n=3, order="min")` | `-pick "x,n=3,order=min"` |
| **Top N per Group** | `df.groupby('g').apply(lambda d: d.nlargest(2, 'x')).reset_index(drop=True)` | `df %>% group_by(g) %>% slice_max(x, n = 2)` | `df.by("g").pick("x", n=2)` | `-by g -pick "x,n=2"` |

---

### 6. Grouped Aggregation & Grouping Context

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Group Context** | `df.groupby(['g1', 'g2'])` | `group_by(df, g1, g2)` | `df.by("g1", "g2")` | `-by "g1,g2"` |
| **Clear Grouping**| `df.reset_index()` | `ungroup(df)` | Auto-cleared (not needed) | N/A |
| **Simple Group Agg** | `df.groupby('g')['x'].mean().reset_index()` | `df %>% group_by(g) %>% summarise(mean_x = mean(x))` | `df.by("g").agg(x="mean")` | `-by g -agg x=mean` |
| **Keep NA Groups (Default)** | `df.groupby('g', dropna=False)['x'].mean().reset_index()` *(Defaults to dropping NAs!)* | `df %>% group_by(g) %>% summarise(mean_x = mean(x))` *(Keeps NAs by default)* | `df.by("g").agg(x="mean")` *(Defaults to `dropna=False`, non-destructive)* | `-by g -agg x=mean` *(Preserves `NaN` group)* |
| **With Row Count**| `df.groupby('g').agg(mean_x=('x', 'mean'), n=('x', 'size')).reset_index()` | `df %>% group_by(g) %>% summarise(mean_x = mean(x), n = n())` | `df.by("g").agg(mean_x="x:mean", n="n")` | `-by g -agg "mean_x=x:mean, n=n"` |
| **Whole-Table Total**| `df[['x']].agg('mean').to_frame().T` | `summarise(df, mean_x = mean(x))` | `df.agg(None, x="mean")` | `-agg x=mean` |

---

### 7. Deduplication & Distinct Records

| Operation | Pandas | dplyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Distinct All Rows** | `df.drop_duplicates().reset_index(drop=True)` | `distinct(df)` | `df.distinct()` | `-distinct` |
| **Distinct by Subset** | `df.drop_duplicates(subset=['a', 'b']).reset_index(drop=True)` | `distinct(df, a, b)` | `df.distinct("a", "b")` | `-distinct "a,b"` |
| **Keep Last Match** | `df.drop_duplicates(keep='last').reset_index(drop=True)` | N/A | `df.distinct(keep="last")` | `-distinct "keep=last"` |

---

### 8. Reshaping & Pivoting

| Operation | Pandas | tidyr (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Wide to Long** | `pd.melt(df, id_vars=['id'], value_vars=['x', 'y'])` | `pivot_longer(df, cols = c(x, y))` | `df.long(id_vars="id", cols=["x", "y"])` | `-long "id_vars=id, cols='x,y'"` |
| **Long to Wide (1:1)**| `df.pivot(index='id', columns='var', values='val').reset_index()` | `pivot_wider(df, names_from = var, values_from = val)` | `df.wide(r="id", c="var", v="val")` | `-wide "r=id, c=var, v=val"` |
| **2D Pivot Table** | `pd.pivot_table(df, index='r', columns='c', values='v', aggfunc='mean').reset_index()` | `df %>% group_by(r, c) %>% summarise(...) %>% pivot_wider(...)` | `df.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

---

### 9. Fast Inspection

| Operation | Pandas | dplyr / tibble (R) | Pytae (DataFrame) | Pytae CLI |
|---|---|---|---|---|
| **Transposed View** | `df.info()` or `df.T.head()` | `glimpse(df)` | `df.glimpse()` | `-glimpse` |
| **ASCII Freq Bars** | `df['c'].value_counts(dropna=False)` | `count(df, c)` | `df.freq("c")` | `-freq c` |
| **ASCII Histogram** | `pd.cut(df['x'], 10).value_counts()` | `hist(df$x)` | `df.hist("x:10")` | `-hist x:10` |
| **Sorted Column List**| `sorted(df.columns)` | `names(df)` | `df.cols()` | `-cols asc` |
| **Copy to Clipboard**| `df.to_clipboard(index=False)` | `clipr::write_clip(df)` | `df.to_clip()` | `-o clip` |

---

## Summary: Why Use Pytae?

- **Zero Cognitive Overhead**: You don't have to remember when to call `.reset_index()`, whether `axis=0` or `axis=1` is required, or how to unpack MultiIndex tuples.
- **Fluent & Composable**: Every operation returns a clean, standard Pandas DataFrame that seamlessly integrates with existing Python code.
- **Identical Terminal Experience**: Any workflow developed in Python notebooks translates verbatim into shell pipelines with `pytae`.
