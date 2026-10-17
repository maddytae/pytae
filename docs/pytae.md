# Pytae — Master Reference & Architecture Guide

`pytae` is a modern, high-performance tabular data manipulation framework that provides a single, unified grammar across both **Python code** (`df.<verb>()`, `pt.<verb>(df)`) and the **Command Line** (`pytae <file> -<verb>`). Backed by a 100% native multithreaded SIMD Polars core, Pytae eliminates boilerplate, index headaches, and performance bottlenecks.

---

## The Core Philosophy: "One and Only One Obvious Way"

In Python, the Zen of Python famously asserts:
> *"There should be one-- and preferably only one --obvious way to do it."*

Yet for over a decade, tabular data engineering and data science have drifted far from this ideal:

- **Pandas** offers four to six competing ways to accomplish nearly every basic operation:
  - Row filtering can be done via boolean masks `df[df['a'] > 1]`, `.loc[...]`, `.iloc[...]`, `.query(...)`, or `.filter()`.
  - Column derivations require choosing between bracket assignment `df['c'] = ...`, `.assign()`, `.apply()`, or `transform()`.
  - Index management demands constant, defensive ceremony: `.reset_index()`, `.set_index()`, `.rename_axis(None)`, and unpacking nested `MultiIndex` tuples after every aggregation.
  - Silent data loss traps abound: `df.groupby(..., dropna=True)` silently discards rows with missing group keys, while `df.dropna()` defaults to `how='any'`, wiping out valuable records missing even a single optional column.
- **dplyr (R / Tidyverse)** introduced an elegant functional pipeline, but porting its concepts to Python introduces severe friction:
  - Non-Standard Evaluation (NSE) creates quoting ambiguity and makes programmatic column passing cumbersome (requiring `{{ col }}`, `across()`, or `.data[[col]]`).
  - Grouping is stateful and "sticky": `group_by()` produces a persistent grouped data frame that silently alters downstream verbs until the user remembers to chain an explicit `ungroup()`.
  - Spelling ambiguity (British `summarise` vs. American `summarize`) introduces unnecessary cognitive overhead.
  - There is zero native parity with the Unix shell or command-line pipelines.
- **SAS (Statistical Analysis System)** has long served as the enterprise standard in clinical trials, banking, and government, but remains locked in disjoint legacy paradigms:
  - Analytics are fragmented across two distinct execution engines: the procedural row-by-row `DATA` step and `PROC SQL`, alongside dozens of specialized procedures (`PROC SORT`, `PROC MEANS`, `PROC FREQ`, `PROC TRANSPOSE`, `PROC COMPARE`).
  - Window calculations and lag/lead operations require manual sort steps followed by stateful row loops with `RETAIN`, `FIRST.`, and `LAST.` flags.
  - Merging datasets (`MERGE ... BY ...`) strictly requires all input datasets to be pre-sorted on disk by the merge keys, with failure to do so resulting in fatal runtime aborts.
  - Missing numeric values (`.`) are sorted internally as smaller than negative infinity ($-\infty$), creating a notorious bug where `IF score < 50` evaluates to true for missing records!
  - Execution relies on heavy batch runs (`.sas` scripts producing voluminous `.log` and `.lst` spool files) with no interactive shell composability.

### The 7 Pillars of Pytae's Philosophy

`pytae` resolves these pain points by establishing **"One and Only One Obvious Way"** as an absolute, non-negotiable architectural doctrine:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE 7 PILLARS OF PYTAE ARCHITECTURE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ONE CANONICAL VERB     │ Exactly one obvious verb per task: filter, mutate, arrange, │
│                           │ by, agg, pick, distinct, wide, long, pivot, join.          │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 2. ZERO SYNTAX AMBIGUITY  │ No competing shortcuts or dual APIs. Explicit 'desc' for   │
│                           │ sorting; explicit predicate strings for missing checks.    │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 3. DUAL-MODALITY PARITY   │ 100% grammar symmetry between Python library & terminal    │
│                           │ CLI: df.filter(...) in code == -filter "..." in shell.     │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 4. PURE FLAT STRUCTURES   │ No indexes, no MultiIndex traps. Every operation returns   │
│                           │ flat 1D columns with clean RangeIndex(0, 1, 2, ...).       │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 5. ZERO DATA LOSS         │ Non-destructive Option B defaults: bare dropna() drops     │
│                           │ only 100% blank rows; agg/pivot retain NA groups.          │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 6. SINGLE-SHOT GROUPING   │ df.by(*cols) scopes only the immediate next verb and auto- │
│                           │ ungroups. Sticky groups are eliminated; ungroup is dead.   │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 7. 100% POLARS SIMD CORE  │ Multithreaded Rust SIMD vector execution under the hood,   │
│                           │ bypassing Python GIL bottlenecks with zero overhead.      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Pytae Architecture: "One Grammar, Two Modalities"

Whether you are writing a production Python service, conducting exploratory analysis in a Jupyter notebook, or processing massive data streams in a Unix terminal, Pytae uses identical concepts, expression syntax, and naming:

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
        .agg(total_rev="sum(sales)", n="n")           -agg "total_rev = sum(sales), n = n"
        .arrange("total_rev desc")                    -arrange "total_rev desc"
                      │                                       │
                      ▼                                       ▼
              In-Memory Result                          Stdout / Export
           Clean, flat DataFrame                      Table view, -o lake/
```

---

## Deep Architectural Comparison: Pytae vs. Pandas vs. dplyr vs. SAS

The following sections provide an extensive, feature-by-feature comparison across all key tabular operations.

> [!TIP]
> **Looking for ecosystem-specific deep dives and migration guides?**
> - **[Pytae vs. Pandas Deep Dive](comparison_to_pandas.md)**: Comprehensive guide on index elimination, Zero Data Loss semantics, and Polars SIMD multithreading.
> - **[Pytae vs. dplyr Deep Dive](comparison_to_dplyr.md)**: Deep dive into Tidyverse syntax mapping, eliminating Non-Standard Evaluation (NSE), and single-shot grouping.
> - **[Pytae vs. SAS Migration Guide](comparison_to_sas.md)**: Comprehensive guide for clinical, biostatistical, and enterprise SAS programmers covering `.sas7bdat` ingestion, missing value semantics, and `PROC` translations.

### 1. Row Filtering & Conditional Slicing

#### Architectural Paradigm
- **Pandas**: Employs multiple overlapping mechanisms. Boolean masks (`df[df['a'] > 1]`) force verbose repetition of the DataFrame variable name. `.query()` uses `numexpr` with a restricted syntax that chokes on Python functions and spaced columns.
- **dplyr**: Elegant `filter()` with tidy evaluation, but requires complex unquoting (`!!`, `{{ }}`) when expressions or column names are passed dynamically.
- **SAS**: Offers two mechanisms: `WHERE` (evaluated during dataset input before observation processing) and `IF` (evaluated during row processing in the DATA step). Confusingly, calculated variables cannot be used in `WHERE` clauses.
- **Pytae ("One Obvious Way")**: Standardizes on `filter()`. Supports clean string predicates, bracketed spaced columns (`"[bill length mm] > 40"`), mathematical intervals (`"[3000, 4500]"`), list membership (`cat=['A', 'B']`), string operations (`species=('startswith', ['Ad', 'Ge'])`), and arbitrary Python callables/lambdas.

#### Rosetta Stone: Row Filtering
| Feature | Pandas | dplyr (R) | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|:---|:---|
| **Simple Filter** | `df[df['sales'] > 100]` | `filter(df, sales > 100)` | `WHERE sales > 100;` | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `df[(df['a'] > 1) & (df['b'] == 'E')]` | `filter(df, a > 1, b == "E")` | `WHERE a > 1 AND b = 'E';` | `df.filter("a > 1 & b == 'E'")` | `-filter "a > 1, b == 'E'"` |
| **Mathematical Interval**| `df[df['x'].between(10, 20)]` | `filter(df, between(x, 10, 20))` | `WHERE 10 <= x <= 20;` | `df.filter(x="[10, 20]")` | `-filter "x = [10, 20]"` |
| **Set Membership** | `df[df['cat'].isin(['A', 'B'])]` | `filter(df, cat %in% c("A", "B"))`| `WHERE cat IN ('A', 'B');` | `df.filter(cat=['A', 'B'])` | `-filter "cat = ['A', 'B']"` |
| **Spaced Columns** | `df[df['gross sales'] > 50]` | `filter(df, \`gross sales\` > 50)` | `WHERE 'gross sales'n > 50;` | `df.filter("[gross sales] > 50")`| `-filter "[gross sales] > 50"` |
| **String Prefix Match**| `df[df['name'].str.startswith('A')]`| `filter(df, str_starts(name, "A"))`| `WHERE name LIKE 'A%';` | `df.filter(name=('startswith', 'A'))`| `-filter "name.startswith('A')"` |
| **Null Row Check** | `df[df['col'].notna()]` | `filter(df, !is.na(col))` | `WHERE col IS NOT MISSING;` | `df.filter("col.notna()")` | `-filter "col.notna()"` |

#### Code Comparison: Filtering
```python
# --- PYTAE (Python) ---
df.filter("body_mass_g > 3500 & sex.notna()")

# --- PYTAE (CLI) ---
# pytae penguins.parquet -filter "body_mass_g > 3500, sex.notna()"
```
```python
# --- PANDAS ---
df[(df['body_mass_g'] > 3500) & (df['sex'].notna())]
```
```r
# --- DPLYR (R) ---
penguins %>% filter(body_mass_g > 3500, !is.na(sex))
```
```sas
/* --- SAS --- */
DATA filtered;
  SET penguins;
  WHERE body_mass_g > 3500 AND NOT MISSING(sex);
RUN;
```

---

### 2. Feature Engineering & Column Derivations (`mutate`)

#### Architectural Paradigm
- **Pandas**: Direct assignment `df['y'] = df['a'] / df['b']` mutates in place, breaking method chains. `.assign()` returns copies but cannot reference newly created variables sequentially within the same call without awkward nested lambdas (`df.assign(a=1).assign(b=lambda d: d['a']*2)`).
- **dplyr**: `mutate()` allows sequential dependencies and `across()` transformations, but `across()` syntax is notoriously verbose and changes frequently across tidyverse releases.
- **SAS**: The `DATA` step is fundamentally a row-by-row procedural loop. Sequential assignment is natural, but requires boilerplate `DATA ...; SET ...; RUN;` blocks and manual memory management (`LENGTH`, `FORMAT`).
- **Pytae ("One Obvious Way")**: `mutate()` handles mathematical formulas, sequential dependencies in a single step, multi-column `across` with suffix generation (`"(a, b)_usd = _ * 1.08"`), `if_else`, `case_when`, dictionary value mapping (`map`), and lag/lead (`shift`).

#### Rosetta Stone: Column Derivations
| Feature | Pandas | dplyr (R) | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|:---|:---|
| **Simple Formula** | `df.assign(y=df['a'] / df['b'])` | `mutate(df, y = a / b)` | `y = a / b;` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential Derivation**| Multiple chained `.assign()` calls | `mutate(df, a=1, b=a*2)` | `a = 1; b = a * 2;` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **Conditional (If/Else)**| `np.where(df['x'] > 0, 'pos', 'neg')`| `if_else(x > 0, "pos", "neg")`| `IF x > 0 THEN f='pos'; ELSE f='neg';` | `df.mutate(f="if_else(x > 0, 'pos', 'neg')")` | `-mutate "f=if_else(x>0,'pos','neg')"` |
| **Multi-Branch (Case)** | `np.select([c1, c2], [v1, v2], default=v3)` | `case_when(c1 ~ v1, c2 ~ v2, TRUE ~ v3)` | `SELECT; WHEN(c1) f=v1; OTHERWISE f=v3; END;` | `df.mutate(f="case_when(c1, v1, c2, v2, v3)")` | `-mutate "f=case_when(c1,v1,v3)"` |
| **Value Mapping** | `df['x'].map({'A': 1, 'B': 2})` | `recode(x, 'A'=1, 'B'=2)` | `PROC FORMAT; ... PUT(x, fmt.);` | `df.mutate(x="map(x, {'A': 1, 'B': 2})")` | `-mutate "x=map(x, {'A':1})"` |
| **Multi-Column Transform**| Loop over columns or complex `apply` | `mutate(df, across(c(a,b), ~ .x * 10))` | `ARRAY cols(*) a b; DO i=1 TO 2; ...` | `df.mutate("(a, b) = _ * 10")` | `-mutate "(a, b) = _ * 10"` |
| **Multi-Column + Suffix**| Loop + dictionary comprehension | `mutate(df, across(c(a,b), ~ .x*10, .names="{.col}_cm"))` | Complex SAS macro loop | `df.mutate("(a, b)_cm = _ * 10")`| `-mutate "(a, b)_cm = _ * 10"` |

#### Code Comparison: Feature Engineering
```python
# --- PYTAE (Python) ---
df.mutate(
    mass_kg="body_mass_g / 1000",
    ratio="bill_length_mm / bill_depth_mm",
    category="if_else(mass_kg > 4.5, 'Heavy', 'Normal')"
)

# --- PYTAE (CLI) ---
# pytae penguins.parquet -mutate "mass_kg = body_mass_g / 1000, ratio = bill_length_mm / bill_depth_mm, category = if_else(mass_kg > 4.5, 'Heavy', 'Normal')"
```
```python
# --- PANDAS ---
df.assign(
    mass_kg=df['body_mass_g'] / 1000,
    ratio=df['bill_length_mm'] / df['bill_depth_mm'],
    category=np.where(df['body_mass_g'] / 1000 > 4.5, 'Heavy', 'Normal')
)
```
```r
# --- DPLYR (R) ---
penguins %>% mutate(
  mass_kg = body_mass_g / 1000,
  ratio = bill_length_mm / bill_depth_mm,
  category = if_else(mass_kg > 4.5, "Heavy", "Normal")
)
```
```sas
/* --- SAS --- */
DATA engineered;
  SET penguins;
  mass_kg = body_mass_g / 1000;
  ratio = bill_length_mm / bill_depth_mm;
  IF mass_kg > 4.5 THEN category = 'Heavy';
  ELSE category = 'Normal';
RUN;
```

---

### 3. Column Selection, Renaming & Exclusion (`select`, `rename`)

#### Architectural Paradigm
- **Pandas**: Selection uses `df[['a', 'b']]`. Dropping requires `df.drop(columns=['c'])`. Pattern matching requires `df.filter(like='score')`. Renaming requires `df.rename(columns={'old': 'new'})`. These disparate methods use different keywords and return types.
- **dplyr**: Provides expressive `select()` with negative indexing (`-c`) and selection helpers (`contains()`, `starts_with()`).
- **SAS**: Uses `KEEP` and `DROP` statements or dataset options `(KEEP=...)`, `(DROP=...)`, and `(RENAME=(old=new))`.
- **Pytae ("One Obvious Way")**: Unifies column management into `select()` and `rename()`. Supports inclusion, drop prefixes (`"-col"` / `"!col"`), pattern matching (`contains="score"`, `starts_with="bill_"`), inline renaming (`"old:new"`), and reordering helpers (`pt.everything`).

#### Rosetta Stone: Selection & Renaming
| Feature | Pandas | dplyr (R) | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|:---|:---|
| **Select Columns** | `df[['species', 'island']]` | `select(df, species, island)` | `KEEP species island;` | `df.select("species", "island")` | `-select "species,island"` |
| **Drop Columns** | `df.drop(columns=['sex'])` | `select(df, -sex)` | `DROP sex;` | `df.select("-sex")` | `-select "-sex"` |
| **Pattern Match** | `df.filter(like='bill')` | `select(df, contains("bill"))`| SAS Macro regex array | `df.select(contains="bill")` | `-select "contains=bill"` |
| **Inline Rename** | `df[['a']].rename(columns={'a': 'b'})`| `select(df, b = a)` | `KEEP a; RENAME a=b;` | `df.select("a:b")` | `-select "a:b"` |
| **Dedicated Rename**| `df.rename(columns={'a': 'b'})` | `rename(df, b = a)` | `RENAME a=b;` | `df.rename("a:b")` | `-rename "a:b"` |
| **Reorder with Rest**| `df[['lead'] + [c for c in df if c != 'lead']]` | `select(df, lead, everything())` | Complex `RETAIN` order | `df.select("lead", pt.everything)`| N/A |

---

### 4. Row Sorting & Ordering (`arrange`)

#### Architectural Paradigm
- **Pandas**: `sort_values()` requires cumbersome arguments: `df.sort_values(by=['sales', 'region'], ascending=[False, True])`.
- **dplyr**: `arrange()` uses `desc()` wrapper functions: `arrange(df, desc(sales), region)`.
- **SAS**: Row sorting is not a method—it requires an external procedure: `PROC SORT DATA=in OUT=out; BY DESCENDING sales region; RUN;`.
- **Pytae ("One Obvious Way")**: Standardizes on `arrange("sales desc", "region")`. In strict adherence to "One and Only One Obvious Way", leading minus shorthand (e.g., `-sales`) is rejected to prevent ambiguity with hyphenated column names or mathematical negation. Descending order is always explicitly declared with `desc` (or `descending`).

#### Rosetta Stone: Row Sorting
| Feature | Pandas | dplyr (R) | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|:---|:---|
| **Ascending Sort** | `df.sort_values('mass')` | `arrange(df, mass)` | `PROC SORT; BY mass; RUN;` | `df.arrange("mass")` | `-arrange mass` |
| **Descending Sort** | `df.sort_values('mass', ascending=False)` | `arrange(df, desc(mass))` | `PROC SORT; BY DESCENDING mass; RUN;` | `df.arrange("mass desc")` | `-arrange "mass desc"` |
| **Multi-Column Sort**| `df.sort_values(['a', 'b'], ascending=[True, False])` | `arrange(df, a, desc(b))` | `PROC SORT; BY a DESCENDING b; RUN;` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |
| **Spaced Columns** | `df.sort_values('body mass')` | `arrange(df, \`body mass\`)`| `PROC SORT; BY 'body mass'n; RUN;` | `df.arrange("[body mass] desc")` | `-arrange "[body mass] desc"` |

---

### 5. Grouped Aggregations & Grouping Context (`by` + `agg`)

#### Architectural Paradigm
- **Pandas**:
  - `df.groupby()` creates a lazy `DataFrameGroupBy` object.
  - Aggregation produces a hierarchical `MultiIndex` across columns and index rows, forcing every user to call `.reset_index()` defensively.
  - **Silent Data Loss**: `df.groupby()` defaults to `dropna=True`, silently dropping rows where the grouping key contains `NaN` or `None`!
- **dplyr**:
  - `group_by()` produces a "sticky" grouped data frame. Downstream operations remain grouped until `ungroup()` is manually invoked, leading to subtle grouping pollution bugs.
  - Spelling ambiguity: `summarise()` vs. `summarize()`.
- **SAS**:
  - Requires `PROC MEANS` or `PROC SUMMARY` with extensive boilerplate: `CLASS`, `VAR`, `OUTPUT OUT=... (DROP=_TYPE_ _FREQ_)`.
  - Alternatively requires `PROC SQL; SELECT species, mean(mass) FROM penguins GROUP BY species; QUIT;`.
- **Pytae ("One Obvious Way")**:
  - **Single-Shot Scope**: `df.by(*cols)` sets a grouping context for the *immediate next verb* and automatically ungroups upon completion. No `ungroup()` is ever required.
  - **Flat 1D Output**: Never produces a `MultiIndex`. Output is always a clean, flat DataFrame.
  - **Zero Data Loss**: Defaults to `dropna=False`, preserving `null`/`NaN` grouping categories explicitly.
  - **Named Aggregations**: Intuitive syntax: `df.by("species").agg(n="n", avg_mass="body_mass_g:mean")`.

#### Rosetta Stone: Grouped Aggregations
| Feature | Pandas | dplyr (R) | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|:---|:---|
| **Group Context** | `df.groupby(['species', 'island'])` | `group_by(df, species, island)` | `CLASS species island;` | `df.by("species", "island")` | `-by species,island` |
| **Clear Grouping** | `df.reset_index()` | `ungroup(df)` *(Mandatory)* | N/A (Procedural end) | Auto-cleared *(ungroup obsolete)* | Auto-cleared |
| **Group Summary** | `df.groupby('g')['x'].mean().reset_index()` | `df %>% group_by(g) %>% summarise(m = mean(x)) %>% ungroup()` | `PROC MEANS NWAY; CLASS g; VAR x; OUTPUT OUT=out MEAN=m; RUN;` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Row Count** | `df.groupby('g').size().reset_index(name='n')` | `summarise(df, n = n())` | `OUTPUT OUT=out N=n;` | `df.by("g").agg(n="n")` | `-by g -agg n=n` |
| **Keep NA Groups** | `df.groupby('g', dropna=False).mean().reset_index()` *(Defaults to dropping!)* | Preserves NA groups by default | `PROC MEANS MISSING;` *(Defaults to dropping!)* | `dropna=False` by default *(Zero Data Loss)* | `-by g -agg ...` *(Preserves NAs)* |
| **Whole-Table Agg**| `df.agg({'x': 'mean'}).to_frame().T` | `summarise(df, m = mean(x))` | `PROC MEANS; VAR x; RUN;` | `df.agg(m="x:mean", n="n")` | `-agg "m=x:mean, n=n"` |

#### Code Comparison: Grouped Aggregation
```python
# --- PYTAE (Python) ---
(
    penguins
    .by("species", "island")
    .agg(
        n="n",
        avg_mass="body_mass_g:mean",
        max_flipper="flipper_length_mm:max"
    )
    .arrange("avg_mass desc")
)

# --- PYTAE (CLI) ---
# pytae penguins.parquet -by species,island -agg "n = n, avg_mass = mean(body_mass_g), max_flipper = max(flipper_length_mm)" -arrange "avg_mass desc"
```
```python
# --- PANDAS ---
(
    penguins
    .groupby(["species", "island"], dropna=False)
    .agg(
        n=("body_mass_g", "size"),
        avg_mass=("body_mass_g", "mean"),
        max_flipper=("flipper_length_mm", "max")
    )
    .reset_index()
    .sort_values("avg_mass", ascending=False)
)
```
```r
# --- DPLYR (R) ---
penguins %>%
  group_by(species, island) %>%
  summarise(
    n = n(),
    avg_mass = mean(body_mass_g, na.rm = TRUE),
    max_flipper = max(flipper_length_mm, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(desc(avg_mass))
```
```sas
/* --- SAS --- */
PROC MEANS DATA=penguins NWAY NOPRINT MISSING;
  CLASS species island;
  VAR body_mass_g flipper_length_mm;
  OUTPUT OUT=summary (DROP=_TYPE_ _FREQ_)
    N(body_mass_g)=n
    MEAN(body_mass_g)=avg_mass
    MAX(flipper_length_mm)=max_flipper;
RUN;

PROC SORT DATA=summary;
  BY DESCENDING avg_mass;
RUN;
```

---

### 6. Grouped Window Calculations & Lag/Lead

#### Architectural Paradigm
- **Pandas**: Window operations require calling `.transform()` on grouped objects or aligning series manually, which frequently leads to index alignment bugs.
- **dplyr**: Supports window operations inside `group_by() %>% mutate()`, but requires defensive `ungroup()` afterwards.
- **SAS**: Demands a prior `PROC SORT`, followed by a `DATA` step using `BY` variables, `RETAIN` statements, and manual tracking of `FIRST.` and `LAST.` boolean flags.
- **Pytae ("One Obvious Way")**: Combine `df.by()` with `mutate()`. The grouping is applied to the window calculation and immediately discarded:
  ```python
  df.by("species").mutate(
      pct_of_group="body_mass_g / sum(body_mass_g)",
      mass_rank="rank(body_mass_g)",
      prev_mass="shift(body_mass_g, 1)"
  )
  ```

---

### 7. Extreme Record Slicing (`pick`)

#### Architectural Paradigm
- **Pandas**: Uses `df.nlargest()` and `df.nsmallest()`. For grouped operations, requires `.groupby().apply(lambda d: d.nlargest(3, 'x')).reset_index(drop=True)`.
- **dplyr**: Uses `slice_max()` and `slice_min()`.
- **SAS**: Requires sorting the dataset descending, then using `DATA out; SET in; BY group; IF FIRST.group; RUN;` (or tracking an observation counter `obs + 1`).
- **Pytae ("One Obvious Way")**: Standardizes on `pick()`. Supports top $N$ (`df.pick("sales", n=5)`), bottom $N$ (`df.pick("sales", n=5, order="min")`), top percentage (`df.pick("sales", prop=0.1)`), and group-aware picking (`df.by("region").pick("sales", n=3)`).

---

### 8. Deduplication & Distinct Records (`distinct`)

#### Architectural Paradigm
- **Pandas**: `df.drop_duplicates(subset=['a', 'b']).reset_index(drop=True)`.
- **dplyr**: `distinct(df, a, b, .keep_all = TRUE)`.
- **SAS**: `PROC SORT DATA=in OUT=out NODUPKEY; BY a b; RUN;` (or `NODUPRECS` for whole-record deduplication).
- **Pytae ("One Obvious Way")**: `distinct()` handles whole-table deduplication (`df.distinct()`), subset deduplication (`df.distinct("a", "b")`), and retention policies (`keep="first"`, `keep="last"`, `keep="none"`).

---

### 9. Reshaping & Pivoting (`wide`, `long`, `pivot`)

#### Architectural Paradigm
- **Pandas**:
  - Melting: `pd.melt(df, id_vars=..., value_vars=...)`.
  - Unmelting: `df.pivot(index=..., columns=..., values=...)` produces an index with a lingering name (`columns.name`).
  - Aggregation matrix: `pd.pivot_table(...)` leaves behind multi-level index columns.
- **dplyr / tidyr**: `pivot_longer()` and `pivot_wider()`.
- **SAS**: `PROC TRANSPOSE DATA=in OUT=out; BY id; ID metric; VAR val; RUN;`. Generates esoteric automatic columns (`_NAME_`, `COL1`) requiring renaming cleanup.
- **Pytae ("One Obvious Way")**:
  - `df.long()`: Converts wide tables into tall records.
  - `df.wide()`: Strictly for pure 1-to-1 structural unmelting without aggregation.
  - `df.pivot()`: Generates 2D cross-tabulation aggregation matrices (`r=`, `c=`, `v=`, `a=`).
  - Output is **always 100% flat 1D columns** with clean headers and no MultiIndex traps.

---

### 10. Relational Joins & Set Operations (`join`, `concat`)

#### Architectural Paradigm
- **Pandas**: `pd.merge(left, right, left_on='id', right_on='customer_id', how='left')`.
- **dplyr**: `left_join(x, y, by = c("id" = "customer_id"))`.
- **SAS**: The `MERGE` statement in a `DATA` step requires both datasets to be pre-sorted on disk by the merge keys:
  ```sas
  PROC SORT DATA=a; BY id; RUN;
  PROC SORT DATA=b; BY id; RUN;
  DATA merged;
    MERGE a (IN=in_a) b (IN=in_b);
    BY id;
    IF in_a; /* Left join */
  RUN;
  ```
  Failure to pre-sort causes immediate runtime failure. Alternatively, users must write `PROC SQL; SELECT * FROM a LEFT JOIN b ON a.id = b.id; QUIT;`.
- **Pytae ("One Obvious Way")**:
  - `df.join(other, on="id", how="left")`.
  - Colon cross-name matching: `on="id:customer_id"`.
  - Integrity validation: `validate="1:m"`, `validate="m:1"`, `validate="1:1"`.
  - Multi-table concatenation: `pt.concat([df1, df2], how="vertical")`.

---

### 11. Missing Data Architecture: "Zero Data Loss by Default"

#### The Silent Corruption Problem
In standard data science workflows, accidental data loss is one of the most common causes of skewed metrics and corrupted reporting. A single missing optional field—such as a customer's secondary phone number—should **never** silently obliterate an entire transaction from a dataset.

#### Comparative Breakdown of Missing Data Semantics
| Behavior | Pandas | Polars | R / dplyr | SAS | Pytae (Option B) |
|:---|:---|:---|:---|:---|:---|
| **Bare Call (`df.dropna()`)** | Drops row if *any* column is NA (`how='any'`) | Drops row if *any* column is `null` | Requires explicit `tidyr::drop_na()` | Must write custom `IF` filter | **Drops only 100% blank rows (`how='all'`)** |
| **Float `NaN` vs Arrow `null`** | Conflates both into `np.nan` / `pd.NA` | Differentiates; `drop_nulls()` **ignores** `NaN`! | Differentiates `NA` and `NaN` | Treats missing as `.` (number) or `' '` (char) | **Cleans both `null` and `NaN` (`drop_nans=True`)** |
| **Analytical Verbs (`agg`, `pivot`)** | `dropna=True` *(Drops missing groups!)* | Preserves `null` group keys | `group_by()` preserves `NA` groups | Drops missing groups unless `MISSING` option passed | **`dropna=False` by default (Zero Data Loss)** |
| **Targeted Columns (`df.dropna("a", "b")`)** | `subset=['a', 'b']`, drops if any is NA | `subset=['a', 'b']`, drops if any is null | `tidyr::drop_na(a, b)` | `WHERE a IS NOT MISSING AND b IS NOT MISSING;` | **Drops if any specified column is NA (`how='any'`)** |
| **Numeric Sorting Trap** | NAs sorted at end (or start) via `na_position` | Nulls sorted at end (or start) | NAs sorted at end | **Missing `.` sorted as $< -\infty$!** *(Massive trap)* | **Safe Polars sorting with explicit `nulls_last`** |
| **Column Name Cleaning** | Third-party (`skimpy`, `janitor`) | Custom regex | Custom macro loops | No built-in tool | **Deterministic 6-stage `clean_columns()`** |

---

### 12. In-Flight Profiling & Inspection (`glimpse`, `freq`, `hist`, `diff`)

#### Architectural Paradigm
- **Pandas**: `df.info()`, `df.describe()`, `df['c'].value_counts()`. `df.compare()` is fragile and fails completely if index labels or columns do not align exactly.
- **dplyr / R**: `glimpse(df)`, `count(df, c)`.
- **SAS**: `PROC CONTENTS DATA=in; RUN;`, `PROC FREQ DATA=in; TABLES col; RUN;`, and `PROC COMPARE BASE=a COMPARE=b CRITERION=0.01; RUN;`.
- **Pytae ("One Obvious Way")**:
  - `df.glimpse()`: Non-destructive R `tibble::glimpse` overview showing row count, column count, dtypes, and inline data previews without breaking method chains.
  - `df.freq("species")`: Categorical frequency distribution with ASCII proportional bars.
  - `df.hist("body_mass_g", bins=6)`: Numeric distribution histogram with rendered ASCII bars and percentage breakdowns.
  - `df.diff(df2, tol=0.01)`: Structural schema drift detection, shape comparison, and cell-level mismatch reporting with floating-point tolerance.

---

### 13. Embedded SQL Engine (`sql`)

#### Architectural Paradigm
- **Pandas**: Requires installing external third-party libraries like `duckdb` or `pandasql` / `sqldf`.
- **dplyr**: Requires `dbplyr` or `tidyquery` connected to external database backends.
- **SAS**: `PROC SQL` is a core pillar of SAS, often used as an escape hatch when DATA step syntax becomes too verbose.
- **Pytae ("One Obvious Way")**: Native zero-setup ANSI SQL query execution directly on frames or disk files via `df.sql(...)`, `pt.sql(...)`, and CLI `-sql`.

---

### 14. Command-Line Interface (CLI) as a First-Class Citizen

#### Architectural Paradigm
- **Pandas**: No CLI. Requires writing a boilerplate Python script or launching a heavy Jupyter kernel.
- **dplyr**: No native CLI. Requires invoking `Rscript -e 'library(dplyr); ...'`.
- **SAS**: Batch execution via `sas -sysin job.sas` which produces heavy `.log` and `.lst` spool files on disk.
- **Pytae ("One Obvious Way")**: Complete 100% grammar equivalence in the terminal:
  ```bash
  pytae penguins.parquet \
    -filter "body_mass_g > 3500, sex.notna()" \
    -by species,island \
    -agg "n = n, avg_mass = mean(body_mass_g)" \
    -arrange "avg_mass desc" \
    -o summary.parquet
  ```

---

## Detailed Documentation Directory

All comprehensive guides, API signatures, CLI flags, walkthroughs, and edge cases are documented under **`docs/detailed_docs/`** in two dedicated folders:
- **`detailed_docs/library/`**: Interactive, fully executed Jupyter Notebooks (`.ipynb`)
- **`detailed_docs/cli/`**: Comprehensive Command Line Markdown guides (`.md`)

| Category | Python Library (Notebook) | CLI Guide (Markdown) | Key Capabilities & Verbs |
|:---|:---|:---|:---|
| **Data I/O** | **[read_write.ipynb](detailed_docs/library/read_write.ipynb)** | **[read_write.md](detailed_docs/cli/read_write.md)** | `pt.read_*`, `pt.scan_*`, `write_*`, `-o`, `-od`, `-fmt`, `-progress`, STDIN, clipboard |
| **Derivations** | **[mutate.ipynb](detailed_docs/library/mutate.ipynb)** | **[mutate.md](detailed_docs/cli/mutate.md)** | `mutate`, formulas, sequential assignments, `if_else`, `case_when`, `map`, `shift`, `@var` |
| **Row Filtering** | **[filter.ipynb](detailed_docs/library/filter.ipynb)** | **[filter.md](detailed_docs/cli/filter.md)** | `filter`, intervals `[10, 20]`, set membership `in`, `or`/`and`, string methods, callables |
| **Columns** | **[select.ipynb](detailed_docs/library/select.ipynb)** | **[select.md](detailed_docs/cli/select.md)** | `select`, drop with `-` / `!`, regex/patterns, inline rename, `pt.everything` |
| **Sorting** | **[arrange.ipynb](detailed_docs/library/arrange.ipynb)** | **[arrange.md](detailed_docs/cli/arrange.md)** | `arrange`, ascending, descending `col desc`, multi-column ordering, null positioning |
| **Aggregation** | **[agg.ipynb](detailed_docs/library/agg.ipynb)** | **[agg.md](detailed_docs/cli/agg.md)** | `by`, `agg`, `n`, `mean`, `sum`, `std`, `median`, `min`, `max`, `dropna=False` Zero Data Loss |
| **Cross-Tab** | **[pivot.ipynb](detailed_docs/library/pivot.ipynb)** | **[pivot.md](detailed_docs/cli/pivot.md)** | `pivot`, `r=`, `c=`, `v=`, `a=`, `f_v=`, flat 1D columns (no MultiIndex traps) |
| **Deduplication** | **[distinct.ipynb](detailed_docs/library/distinct.ipynb)** | **[distinct.md](detailed_docs/cli/distinct.md)** | `distinct`, whole-table deduplication, subset uniqueness, `keep='first'\|'last'\|'none'` |
| **Slicing** | **[pick.ipynb](detailed_docs/library/pick.ipynb)** | **[pick.md](detailed_docs/cli/pick.md)** | `pick`, top/bottom $N$ records, top percentage `prop=`, grouped top-$N$ per category |
| **Reshaping** | **[reshape.ipynb](detailed_docs/library/reshape.ipynb)** | **[reshape.md](detailed_docs/cli/reshape.md)** | `long` (unpivoting) and `wide` (1:1 pivoting) with identical intuitive vocabularies |
| **Relational Joins**| **[join.ipynb](detailed_docs/library/join.ipynb)** | **[join.md](detailed_docs/cli/join.md)** | `df.join`, `pt.join`, `pt.concat`, inner/left/right/full/semi/anti/cross, colon keys, `validate` |
| **Utilities** | **[other_utilities.ipynb](detailed_docs/library/other_utilities.ipynb)** | **[clean_replace.md](detailed_docs/cli/clean_replace.md)**<br>**[diff.md](detailed_docs/cli/diff.md)** | `fillna`, `dropna`, `clean_columns`, `diff` (with `tol=`), `glimpse`, `cols`, `to_clip` |
| **Inspection** | **[other_utilities.ipynb](detailed_docs/library/other_utilities.ipynb)** | **[inspect.md](detailed_docs/cli/inspect.md)** | `-cols`, `-dtype`, `-shape`, `-nulls`, `-head`, `-tail`, `-glimpse`, `-summary`, `-freq`, `-hist` |
| **Multi-File** | **[join.ipynb](detailed_docs/library/join.ipynb)** | **[multi_file.md](detailed_docs/cli/multi_file.md)** | `-file` pipelines, multi-table joining, batch inputs, pipes, Unix redirection |
| **SQL Engine** | **[sql.ipynb](detailed_docs/library/sql.ipynb)** | **[sql.md](detailed_docs/cli/sql.md)** | `df.sql()`, `pt.sql()`, `-sql` DuckDB/Polars SQL engine on data and files |
| **Plotting** | **[plotting.ipynb](detailed_docs/library/plotting.ipynb)** | **[plotting.md](detailed_docs/cli/plotting.md)** | `df.plot()`, `-plot`, `-finalize`, bar, line, scatter, hist, box, violin, corr, heat |
| **Comparisons** | **[vs. Pandas](comparison_to_pandas.md)**<br>**[vs. dplyr](comparison_to_dplyr.md)**<br>**[vs. SAS](comparison_to_sas.md)** | — | Pytae vs. Pandas vs. dplyr vs. SAS, naming rationale, "one and only one obvious way" |

---

## 30-Second Quickstart

### In Python:
```python
import pytae as pt

# Eager read or lazy scan
penguins = pt.read_parquet("penguins.parquet")

report = (
    penguins.filter("body_mass_g > 3500 & sex.notna()")
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
    .arrange("avg_mass_kg desc")
)

# Export results
report.to_parquet("summary.parquet")
```

### On the Command Line:
The exact same logic translates directly to the terminal:

```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500, sex.notna()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm, status = 'verified'" \
  -by species,island \
  -agg "n = n, avg_mass_kg = mean(body_mass_kg), max_ratio = max(bill_ratio)" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```
