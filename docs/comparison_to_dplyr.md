# Pytae vs. dplyr (R / Tidyverse) — Deep Dive & Rosetta Stone

[← Back to Master Reference](pytae.md) | [Comparison with Pandas](comparison_to_pandas.md) | [Comparison with SAS](comparison_to_sas.md)

R's **`dplyr`** and the broader **Tidyverse** revolutionized data analysis by introducing a consistent, readable, and pipe-friendly grammar of data manipulation (`filter`, `mutate`, `select`, `arrange`, `summarise`).

However, for developers and data scientists working in Python, migrating from R has historically been frustrating. Direct ports of dplyr to Python often run into Python's lexical scoping rules, quotation requirements, slow execution, and awkward metaprogramming.

`pytae` brings the elegance and fluency of the Tidyverse to Python—backed by the raw multithreaded SIMD vector speed of **Polars**—while eliminating R's quoting friction and sticky grouping bugs.

---

## Key Architectural Differences: Pytae vs. dplyr

```
┌───────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
│ Architectural Dimension       │ dplyr (R / Tidyverse)            │ Pytae (Python & CLI)             │
├───────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
│ Core Grammar                  │ Functional pipes (%>%, |>)       │ Method chaining (df.verb())      │
│ Underlying Execution Engine   │ C++ (cpp11) / R interpreter      │ Multithreaded Rust SIMD (Polars) │
│ Evaluation Model              │ Non-Standard Evaluation (NSE)    │ Clean string expressions & lambdas│
│ Grouping State                │ "Sticky" (persists until ungroup)│ Single-shot (auto-clearing)      │
│ Summarization Name            │ Dual spelling (summarise/ize)    │ One Obvious Way (agg)            │
│ Multi-Column Transformations  │ across(c(a, b), ~ .x * 10)       │ (a, b) = _ * 10                  │
│ Reshaping Grammar             │ Separate package (tidyr)         │ Unified verbs (long, wide, pivot)│
│ Command-Line Equivalence      │ None (requires Rscript)          │ 100% grammar parity via CLI      │
└───────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
```

---

## 1. Non-Standard Evaluation (NSE) vs. Ergonomic String Expressions

### The dplyr Metaprogramming Challenge
In R, `dplyr` relies heavily on Non-Standard Evaluation (NSE). While `filter(df, mass > 100)` looks clean when typed interactively, it creates major friction in functions, automation, and packages:
- Developers must learn `rlang` unquoting, quasiquotation (`!!`), and injection (`{{ col }}`).
- Passing column names dynamically requires switching between `all_of()`, `any_of()`, and `.data[[col]]`.

### The Pytae Solution
In Pytae, column expressions are cleanly expressed as readable strings or Python callables:
- Interactive code is concise: `df.filter("mass > 100")`
- Dynamic variables integrate cleanly using standard Python f-strings: `df.filter(f"{col} > {threshold}")`
- In-memory variables are referenced directly via `@var`: `df.filter("mass > @min_mass")`
- Complex business logic can always drop back to native Python callables: `df.filter(lambda d: custom_func(d['mass']))`

---

## 2. Grouping Semantics: "Sticky" Groups vs. Single-Shot Auto-Clearing

### The dplyr "Sticky Grouping" Bug
In `dplyr`, `group_by()` alters the state of the data frame, producing a `grouped_df`. This grouping **persists silently across downstream operations**:

```r
# DPLYR TRAP: Sticky groups contaminate subsequent calculations!
df_grouped <- df %>%
  group_by(region) %>%
  mutate(regional_mean = mean(sales))

# The next operation is STILL grouped by region, even if the user wanted overall stats!
df_summary <- df_grouped %>%
  mutate(global_mean = mean(sales)) # BUG: Calculates regional mean again, NOT global!

# To fix this, users must remember to defensively pipe ungroup():
df_grouped <- df %>%
  group_by(region) %>%
  mutate(regional_mean = mean(sales)) %>%
  ungroup() # Mandatory defensive ceremony
```

### The Pytae Solution: `ungroup()` is Dead
In Pytae, grouping is strictly **single-shot, non-destructive, and auto-clearing**:
- `df.by(*cols)` establishes a grouping context for the *immediate next verb* (`mutate`, `agg`, `pick`).
- As soon as that verb completes, the grouping context is automatically consumed and discarded.
- Downstream verbs immediately evaluate at the whole-table scope without any need for `ungroup()`:

```python
# PYTAE: Single-shot grouping with zero pollution
(
    df
    .by("region").mutate(regional_mean="mean(sales)") # Scoped to region
    .mutate(global_mean="mean(sales)")                # Evaluated across whole table!
    .by("department").mutate(dept_mean="mean(sales)") # Scoped to department
)
```

---

## 3. Multi-Column Operations: `across()` vs. Pytae Multi-Target Syntax

### The dplyr Syntax:
In `dplyr`, applying a function across multiple columns requires the `across()` helper:
```r
penguins %>%
  mutate(across(c(bill_length_mm, bill_depth_mm), ~ .x / 10, .names = "{.col}_cm"))
```

### The Pytae Syntax:
Pytae provides an intuitive mathematical syntax where target columns and suffix formulas are declared directly:
```python
# In-place multi-column transformation:
penguins.mutate("(bill_length_mm, bill_depth_mm) = _ / 10")

# Multi-column transformation with suffix:
penguins.mutate("(bill_length_mm, bill_depth_mm)_cm = _ / 10")
```

The underscore `_` cleanly denotes the current column, eliminating formula boilerplate.

---

## 4. Spelling Ambiguity: `summarise` vs. `summarize`

In R's `dplyr`, both `summarise()` and `summarize()` are supported to accommodate British and American English. While courteous, this introduces spelling inconsistency across codebases and team repositories, violating the Zen of Python's principle: *"There should be one-- and preferably only one --obvious way to do it."*

Pytae eliminates this ambiguity entirely by standardizing on the canonical, concise verb **`agg()`** across both Python (`df.agg()`, `df.by().agg()`) and the command line (`-agg`).

---

## 5. Performance & Speed Benchmarks: Polars Rust SIMD vs. R / dplyr

While `dplyr` is written with a C++ backend (`cpp11`), R itself is inherently single-threaded. Standard Tidyverse workflows execute sequentially on a single core and generate intermediate copy overhead during complex pipe chains. Pytae brings Tidyverse-like grammar into Python, but executes it on native **Polars multithreaded Rust SIMD**, saturating all CPU cores automatically.

### Comparative Benchmark Overview (5,000,000 Rows)
*Environment: Apple Silicon M-series (macOS), 5,000,000 rows benchmark across analytical operations.*

| Operation (5 Million Records) | R / dplyr Average | Pytae (Eager) | Pytae (Lazy Pushdown) | Pytae Advantage |
|:---|:---|:---|:---|:---|
| **End-to-End Pipeline**<br>*(Read Parquet $\to$ Filter $\to$ Mutate $\to$ Group $\to$ Summarize $\to$ Arrange)* | ~`1.85s` | `0.205s` | **`0.042s`** | **~44x faster** (Lazy)<br>**~9x faster** (Eager) |
| **Grouped Aggregation**<br>*(5M rows, multi-key group by + 3 aggregate metrics)* | ~`1.40s` | **`0.131s`** | N/A | **~10.7x faster** |
| **Row Sorting (`arrange`)**<br>*(5M rows, multi-column sort: text + numeric)* | ~`3.80s` | **`0.730s`** | N/A | **~5.2x faster** |
| **Relational Join**<br>*(1,000,000 rows $\times$ 1,000,000 rows `inner_join`)* | ~`0.55s` | **`0.052s`** | N/A | **~10.6x faster** |
| **Native Analytical SQL**<br>*(5M rows, CTE / Window / Aggregations)* | Requires DuckDB R / dbplyr | **`0.021s`** | N/A | **Instant zero-setup SQL** |

### Key Architectural Advantages over dplyr
1. **Parallel Execution Across Cores**: `dplyr` requires third-party packages like `multidplyr` or `furrr` to parallelize work across worker processes (incurring substantial inter-process serialization overhead). Pytae parallelizes natively inside Rust SIMD threads with shared memory.
2. **Lazy Execution Pipeline**: R's pipe `%>%` evaluates eagerly at every step. Pytae's `pt.scan_parquet()` builds a unified query plan that executes optimizations (predicate pushdown, branch pruning) in a single multithreaded pass.
3. **No Non-Standard Evaluation (NSE) Overhead**: Eliminates `rlang` expression parsing and NSE unquoting cycles, providing direct execution on Apache Arrow buffers.

> [!TIP]
> **Reproducibility**: Complete, self-contained benchmark scripts and interactive notebooks are available in **[`docs/benchmarks/`](benchmarks/README.md)** (executable CLI script: [`run_benchmarks.py`](benchmarks/run_benchmarks.py), interactive notebook: [`benchmarks.ipynb`](benchmarks/benchmarks.ipynb)).

---

## 6. Feature-by-Feature Rosetta Stone: Pytae vs. dplyr

### 1. Row Filtering
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Filter** | `filter(df, sales > 100)` | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `filter(df, a > 1, b == "E")` | `df.filter("a > 1 & b == 'E'")` | `-filter "a > 1, b == 'E'"` |
| **Interval / Range** | `filter(df, between(x, 10, 20))` | `df.filter(x="[10, 20]")` | `-filter "x = [10, 20]"` |
| **Set Membership** | `filter(df, cat %in% c("A", "B"))` | `df.filter(cat=['A', 'B'])` | `-filter "cat = ['A', 'B']"` |
| **Spaced Columns** | `filter(df, \`gross sales\` > 50)` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **Prefix Match** | `filter(df, str_starts(name, "A"))`| `df.filter(name=('startswith', 'A'))`| `-filter "name.startswith('A')"` |
| **Null Row Check** | `filter(df, !is.na(col))` | `df.filter("col.notna()")` | `-filter "col.notna()"` |

### 2. Feature Engineering & Column Derivations (`mutate`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Derivation** | `mutate(df, y = a / b)` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential Calculations**| `mutate(df, a = 1, b = a * 2)` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **Conditional (If/Else)** | `mutate(df, f = if_else(x > 0, "pos", "neg"))` | `df.mutate(f="if_else(x > 0, 'pos', 'neg')")` | `-mutate "f=if_else(x>0,'pos','neg')"` |
| **Multi-Branch (Case)** | `mutate(df, f = case_when(c1 ~ v1, c2 ~ v2, TRUE ~ v3))` | `df.mutate(f="case_when(c1, v1, c2, v2, v3)")` | `-mutate "f=case_when(c1,v1,v3)"` |
| **Value Recoding** | `mutate(df, x = recode(x, "A" = 1, "B" = 2))` | `df.mutate(x="map(x, {'A': 1, 'B': 2})")` | `-mutate "x=map(x, {'A':1})"` |
| **Multi-Column Transform** | `mutate(df, across(c(a, b), ~ .x * 10))` | `df.mutate("(a, b) = _ * 10")` | `-mutate "(a, b) = _ * 10"` |
| **Multi-Column + Suffix** | `mutate(df, across(c(a, b), ~ .x * 10, .names = "{.col}_cm"))` | `df.mutate("(a, b)_cm = _ * 10")` | `-mutate "(a, b)_cm = _ * 10"` |
| **Lag / Lead** | `mutate(df, prev = lag(x, 1))` | `df.mutate(prev="shift(x, 1)")` | `-mutate "prev = shift(x, 1)"` |

### 3. Column Selection & Exclusion (`select`, `rename`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Select Columns** | `select(df, a, b)` | `df.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `select(df, -c, -d)` | `df.select("-c", "-d")` | `-select "-c,-d"` |
| **Pattern Match** | `select(df, contains("bill"))` | `df.select(contains="bill")` | `-select "contains=bill"` |
| **Prefix Match** | `select(df, starts_with("b"))` | `df.select(starts_with="b")` | `-select "starts_with=b"` |
| **Inline Rename** | `select(df, new_b = a)` | `df.select("a:new_b")` | `-select "a:new_b"` |
| **Dedicated Rename** | `rename(df, new_b = a)` | `df.rename("a:new_b")` | `-rename "a:new_b"` |
| **Reorder with Rest** | `select(df, lead, everything())` | `df.select("lead", pt.everything)` | N/A |

### 4. Row Sorting (`arrange`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Ascending** | `arrange(df, sales)` | `df.arrange("sales")` | `-arrange sales` |
| **Descending** | `arrange(df, desc(sales))` | `df.arrange("sales desc")` | `-arrange "sales desc"` |
| **Multi-Column Mixed** | `arrange(df, a, desc(b))` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |
| **Spaced Columns** | `arrange(df, desc(\`gross sales\`))` | `df.arrange("[gross sales] desc")` | `-arrange "[gross sales] desc"` |

### 5. Grouped Summaries (`by` + `agg`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Group Summary** | `df %>% group_by(g) %>% summarise(m = mean(x)) %>% ungroup()` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Row Count** | `summarise(df, n = n())` | `df.by("g").agg(n="n")` | `-by g -agg n=n` |
| **Multiple Metrics** | `summarise(df, m = mean(x), s = sum(x))` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Whole-Table Summary**| `summarise(df, m = mean(x))` | `df.agg(m="x:mean", n="n")` | `-agg "m=x:mean,n=n"` |

### 6. Slicing Top / Bottom Records (`pick`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `slice_max(df, sales, n = 5)` | `df.pick("sales", n=5)` | `-pick "sales,n=5"` |
| **Bottom N Records** | `slice_min(df, sales, n = 5)` | `df.pick("sales", n=5, order="min")` | `-pick "sales,n=5,order=min"` |
| **Top Proportion** | `slice_max(df, sales, prop = 0.1)` | `df.pick("sales", prop=0.1)` | `-pick "sales,prop=0.1"` |
| **Top N per Group** | `df %>% group_by(g) %>% slice_max(x, n = 3) %>% ungroup()` | `df.by("g").pick("x", n=3)` | `-by g -pick "x,n=3"` |

### 7. Deduplication (`distinct`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Deduplicate Table** | `distinct(df)` | `df.distinct()` | `-distinct` |
| **Subset Deduplication**| `distinct(df, a, b, .keep_all = TRUE)` | `df.distinct("a", "b")` | `-distinct "a,b"` |

### 8. Reshaping & Pivoting (`wide`, `long`, `pivot`)
| Task | tidyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Wide to Long** | `pivot_longer(df, cols = c(x, y), names_to = "var", values_to = "val")` | `df.long(id_vars="id", cols=["x", "y"])` | `-long "id_vars=id, cols='x,y'"` |
| **Long to Wide (1:1)** | `pivot_wider(df, names_from = var, values_from = val)` | `df.wide(r="id", c="var", v="val")` | `-wide "r=id, c=var, v=val"` |
| **2D Pivot Matrix** | `group_by(r, c) %>% summarise(v = mean(v)) %>% pivot_wider(...)` | `df.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

### 9. Relational Joins (`join`, `concat`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Inner Join** | `inner_join(df1, df2, by = "id")` | `df1.join(df2, on="id", how="inner")` | `-join "f2.parquet,on=id"` |
| **Left Join** | `left_join(df1, df2, by = "id")` | `df1.join(df2, on="id", how="left")` | `-join "f2.parquet,on=id,how=left"` |
| **Different Key Names**| `left_join(df1, df2, by = c("a" = "b"))` | `df1.join(df2, on="a:b")` | `-join "f2.parquet,on=a:b"` |
| **Anti Join** | `anti_join(df1, df2, by = "id")` | `df1.join(df2, on="id", how="anti")` | `-join "f2.parquet,on=id,how=anti"` |
| **Row Bind (Stack)** | `bind_rows(df1, df2)` | `pt.concat([df1, df2], how="vertical")` | N/A |

### 10. Inspection & Profiling
| Task | dplyr / tibble (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Transposed Overview**| `glimpse(df)` | `df.glimpse()` *(Non-destructive)* | `-glimpse` |
| **Frequency Counts** | `count(df, col, sort = TRUE)` | `df.freq("col")` *(With ASCII bars)* | `-freq col` |
| **Dataset Comparison** | `waldo::compare(df1, df2)` | `df1.diff(df2, tol=0.01)` | `pytae f1.parquet -diff f2.parquet,tol=0.01` |
| **Clipboard Export** | `clipr::write_clip(df)` | `df.to_clip()` | `-o clip` |

### 11. Missing Data Architecture & Cleaning (`dropna`, `fillna`, `clean_columns`)
| Task | dplyr / tidyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Safe Blank Row Dropping** | `filter(df, if_any(everything(), ~ !is.na(.)))` | `df.dropna()` *(Defaults to safe `how='all'`)* | `-dropna` |
| **Targeted Key Dropping** | `drop_na(df, id, email)` | `df.dropna("id", "email")` | `-dropna id,email` |
| **Missing Imputation** | `replace_na(df, list(score = 0))` | `df.fillna({"score": 0})` | `-fillna "score=0"` |
| **Column Name Cleaning** | `janitor::clean_names(df)` | `df.clean_columns()` *(Deterministic 6-stage)* | `-clean` |
| **Preserve NA Groups in Agg** | Default behavior (keeps `NA` levels) | Default behavior (`dropna=False`) | Default behavior |

### 12. Embedded ANSI SQL Engine (`sql`)
| Task | dplyr / R | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **SQL Query on DataFrame** | Requires `dbplyr` / `tidyquery` / `sqldf` | `df.sql("SELECT species, avg(body_mass_g) FROM self GROUP BY species")` | N/A |
| **SQL Query on Disk File** | Requires database connection or DuckDB R | `pt.sql("SELECT * FROM 'data.parquet' WHERE sales > 100")` | `-sql "SELECT * FROM file.parquet WHERE sales > 100"` |

### 13. Grouped Window Calculations & Lag/Lead
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Group Mean Window** | `df %>% group_by(g) %>% mutate(m = mean(x)) %>% ungroup()` | `df.by("g").mutate(m="mean(x)")` | `-by g -mutate "m = mean(x)"` |
| **Within-Group Percentage** | `df %>% group_by(g) %>% mutate(pct = x / sum(x)) %>% ungroup()` | `df.by("g").mutate(pct="x / sum(x)")` | `-by g -mutate "pct = x / sum(x)"` |
| **Within-Group Rank** | `df %>% group_by(g) %>% mutate(r = min_rank(x)) %>% ungroup()` | `df.by("g").mutate(r="rank(x)")` | `-by g -mutate "r = rank(x)"` |
| **Grouped Shift / Lag** | `df %>% group_by(g) %>% mutate(prev = lag(x)) %>% ungroup()` | `df.by("g").mutate(prev="shift(x, 1)")` | `-by g -mutate "prev = shift(x, 1)"` |
| **Grouped Cumulative Sum** | `df %>% group_by(g) %>% mutate(cum = cumsum(x)) %>% ungroup()` | `df.by("g").mutate(cum="cum_sum(x)")` | `-by g -mutate "cum = cum_sum(x)"` |

---

## 7. End-to-End Pipeline Comparison

### In R (dplyr / Tidyverse):
```r
library(dplyr)
library(arrow)

summary_report <- read_parquet("penguins.parquet") %>%
  filter(body_mass_g > 3500, !is.na(sex)) %>%
  mutate(
    body_mass_kg = body_mass_g / 1000,
    bill_ratio = bill_length_mm / bill_depth_mm
  ) %>%
  group_by(species, island) %>%
  summarise(
    n = n(),
    avg_mass_kg = mean(body_mass_kg, na.rm = TRUE),
    max_ratio = max(bill_ratio, na.rm = TRUE),
    .groups = "drop" # Required to prevent sticky grouping!
  ) %>%
  arrange(desc(avg_mass_kg))

write_parquet(summary_report, "summary.parquet")
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

Pytae provides everything Tidyverse users love about `dplyr`—fluent method chaining, declarative verbs, and clean data thinking—while granting massive SIMD vector performance and Unix command-line superpowers.

