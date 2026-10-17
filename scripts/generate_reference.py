#!/usr/bin/env python
"""Generate and update reference/pytae_reference.txt with latest documentation and code."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MANUAL_TEXT = """================================================================================
PYTAE COMPREHENSIVE KNOWLEDGE BASE & AGENT TRAINING REFERENCE MANUAL
================================================================================

TABLE OF CONTENTS
--------------------------------------------------------------------------------
1.  OVERVIEW & CORE PHILOSOPHY
2.  PACKAGE ARCHITECTURE & IMPORT PATTERNS
3.  SAMPLE DATASETS
4.  PYTHON LIBRARY REFERENCE (API VERBS)
    4.1.  pt.filter() / df.pt.filter() — Row Filtering (formerly qry)
    4.2.  pt.by() / df.pt.by() — Single-Shot Scoped Grouping
    4.3.  pt.mutate() / df.pt.mutate() — Column Creation & Feature Engineering
    4.4.  pt.select() / df.pt.select() — Column Selection, Slicing & Exclusion
    4.5.  pt.arrange() / df.pt.arrange() — Row Sorting
    4.6.  pt.pick() / df.pt.pick() — Extreme Row Slicing (formerly slice_max/min)
    4.7.  pt.distinct() / df.pt.distinct() — Deduplication
    4.8.  pt.agg() / df.pt.agg() — Grouped Aggregation
    4.9.  pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
    4.10. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
    4.11. Other Utilities:
          - pt.dropna() / df.pt.dropna()
          - pt.cols() / df.pt.cols()
          - pt.glimpse() / df.pt.glimpse()
          - pt.freq() / df.pt.freq()
          - pt.hist() / df.pt.hist()
          - pt.join() / df.pt.join() / df.join() (Polars Join Engine)
          - pt.concat() / df.pt.concat() / df.concat() (Stacking Engine)
          - Transparent Polars Verb Delegation (__getattr__)
          - pt.handle_missing() / df.pt.handle_missing()
          - pt.clean_columns() / df.pt.clean_columns()
          - safe_reset_index(df)
          - df.to_clip() / s.to_clip() (System Clipboard Export)
    4.12. Plotter — Visualization & Dashboarding (Plotting API)
5.  CLI REFERENCE (COMMAND LINE INTERFACE)
    5.1.  Execution Model & Pipeline Architecture
    5.2.  File Formats & Zero-Cost Metadata Inspection
    5.3.  All CLI Flags & Syntax Rules
    5.4.  In-Terminal Visualizations (-freq, -hist)
    5.5.  Quoting & Delimiter Standards (: vs =)
    5.6.  Multi-File Operations (-file, -join, -concat, -sql)
    5.7.  Batch Processing, Conversions & Clipboard (-o)
6.  FREQUENTLY ASKED QUESTIONS, PITFALLS & SYNTAX RULES
    6.1.  When should I use `-select` before `-agg`?
    6.2.  Why is `by` strictly standalone across all verbs?
    6.3.  Why does every chained method call start on a new line?
    6.4.  What are the key verb deprecations (filter, pick, distinct)?
    6.5.  How do I apply custom functions in `mutate()`? (Vectorized vs Series vs Row)
    6.6.  Can row-level functions access newly created columns in the same `mutate()`?
    6.7.  Why does `df.pt.mutate(col=my_func)` fail when `my_func` expects a row?
    6.8.  What is the difference between `wide()` and `pivot()`?
    6.9.  How do negative column exclusions work in `select()` and CLI `-select`?
    6.10. How do columns with spaces work across expressions?
    6.11. Why did `-sort` or `-sort_by` fail? (Use `-arrange`)
    6.12. How do I inspect metadata without reading data into RAM?
    6.13. How do I assign literal constants in `mutate()`? (Use quoted strings e.g. status="'active'")
    6.14. How do I apply the same formula across multiple columns in `mutate()`? (Use `(col1, col2) = _ * 2`)
7.  END-TO-END RECIPES & EXAMPLES (PYTHON & CLI)
    Recipe 1: Master Mutate Recipe (All 12 Features in One Pipeline)
    Recipe 2: Grouped Aggregation & 2D Pivots (Python & CLI)
    Recipe 3: Group-Aware Extreme Row Selection (pt.by + pt.pick)
    Recipe 4: Polars SQL Query in CLI Pipeline
    Recipe 5: Multi-File Join, Concat, and Export
    Recipe 6: In-Terminal Visual Inspection (-freq, -hist, -meta, -arrange)
    Recipe 7: Multi-Panel Dashboard with Secondary Y-Axis and Faceting
8.  DETAILED FEATURE DOCUMENTATION GUIDES (docs/detailed_docs/)
9.  MASTER DOCUMENTATION & ARCHITECTURE GUIDE (docs/pytae.md)
10. PHILOSOPHY & COMPARISON ROSETTA STONE (docs/comparison_to_pandas_and_dplyr.md)
11. REPOSITORY DIRECTORY TREE
12. BUILD & CONFIGURATION (pyproject.toml)
13. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)
14. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)
================================================================================


1. OVERVIEW & CORE PHILOSOPHY
--------------------------------------------------------------------------------
`pytae` is an ergonomic, high-performance tabular data manipulation library and 
command-line tool powered by a 100% native multithreaded SIMD Polars engine with 
seamless Pandas interoperability, PyArrow, and Matplotlib.

Key principles:
1. Unified SIMD Vector Engine: Every library verb and CLI operation executes 
   natively on Polars vector memory, delivering 10x–20x performance speedups, 
   zero-copy operations, and lazy evaluation (`pt.scan()`).
2. Zero Data Loss by Default: Missing values (`null`/`NaN`) are preserved across 
   analytical operations (`agg`, `pivot`, `mutate`, `freq`) by default (`dropna=False`).
   The `dropna()` / `drop_nulls()` verb defaults to `how='all'` (dropping only 100%
   blank rows), protecting partial-row business data from accidental loss.
3. Seamless Pandas & Polars Interoperability: Works seamlessly with both Pandas and 
   Polars DataFrames. Use `df.pt.<verb>()` or `pt.<verb>(df)`. Converts back to 
   Pandas anytime via `.to_pandas()` while preserving original indices.
4. Fast & Zero-Cost Metadata Inspection: For formats containing file-level metadata 
   (Parquet, SAS7BDAT), commands like `-shape`, `-cols`, `-dtype`, `-head` inspect 
   headers without parsing full table rows.
5. Expressive & Human-Friendly: Minimizes boilerplate. Filtering supports 
   intervals `[3000, 4000]`, string operations, and keyword arguments. Grouped 
   aggregations express grouping via standalone `pt.by()` and concise aggregations 
   (e.g. `body_mass_g=mean`, `n=n`) without tedious `.groupby().agg()` boilerplate.
6. Non-Destructive: All library verbs return copies of DataFrames and never 
   mutate inputs in place. Original indices are preserved during filtering.
7. Honest Error Handling ("Be generous in what you accept, but strictly honest 
   when ambiguous"): Flexible inputs are accepted where unambiguous, but collisions, 
   conflicts, and invalid arguments raise clear exceptions rather than silently 
   inventing artificial column suffixes or guessing.
8. One and Only One Obvious Way: Distinct responsibilities per verb—pure 1:1 unmelting 
   is `wide()`, 2D aggregation is `pivot()`, column selection is `select()`, 
   grouping is strictly standalone `pt.by()`.
9. Plotting Without Implicit Aggregation (Path A): Plotters focus purely on 
   visual representation—data should be aggregated explicitly first via `agg` 
   or `pivot` before plotting, avoiding hidden or surprising aggregations.


2. PACKAGE ARCHITECTURE & IMPORT PATTERNS
--------------------------------------------------------------------------------
Installation (PyPI: https://pypi.org/project/pytae/):
  pip install pytae
  pip install 'pytae[plot]'    # includes matplotlib, scipy

Importing:
  import pytae as pt
  import pandas as pd
  import polars as pl

Top-Level Functions exported by `pytae`:
  - pt.read_parquet(source, **kwargs) -> DataFrame (Eager Parquet reader)
  - pt.read_csv(source, **kwargs) -> DataFrame (Eager CSV reader)
  - pt.read_ndjson(source, **kwargs) -> DataFrame (Eager NDJSON reader)
  - pt.read_json(source, **kwargs) -> DataFrame (Eager JSON reader)
  - pt.read_ipc(source, **kwargs) -> DataFrame (Eager Arrow IPC reader)
  - pt.read_excel(source, **kwargs) -> DataFrame (Eager Excel reader)
  - pt.read_database(query, conn, **kwargs) -> DataFrame (Eager SQL query)
  - pt.scan_parquet(source, **kwargs) -> DataFrame (Lazy Parquet scanner)
  - pt.scan_csv(source, **kwargs) -> DataFrame (Lazy CSV scanner)
  - pt.scan_ndjson(source, **kwargs) -> DataFrame (Lazy NDJSON scanner)
  - pt.scan_ipc(source, **kwargs) -> DataFrame (Lazy Arrow IPC scanner)
  - pt.fillna(df, value, *cols, subset=None, nans=True) -> DataFrame (Fill null/NaN)
  - pt.fill_null(df, value, *cols, subset=None) -> DataFrame (Fill null)
  - pt.fill_nan(df, value, *cols, subset=None) -> DataFrame (Fill float NaN)
  - pt.select(df, *args, exclude=None, dtype=None, exclude_dtype=None, contains=None, startswith=None, endswith=None, regex=None)
  - pt.everything() / pt.everything (sentinel for select)
  - pt.filter(df, *args, **kwargs)
  - pt.by(df, *cols)
  - pt.mutate(df, *args, dropna=False, observed=True, params=None, **kwargs)
  - pt.arrange(df, *cols, ascending=None, na_last=True)
  - pt.pick(df, order_by, n=1, prop=None, order="max", with_ties=False, na_last=True)
  - pt.distinct(df, *cols, keep="first")
  - pt.dropna(df, *cols, how=None, drop_nans=True)
  - pt.agg(df, *args, a=None, dropna=False, observed=True, **kwargs)
  - pt.long(df, cols=None, id_vars=None, c="variable", v="value")
  - pt.wide(df, r=None, c="variable", v="value")
  - pt.pivot(df, r=None, c=None, v=None, a="sum", dropna=False, f_v=None)
  - pt.handle_missing(df, fillna=".", numeric_fill=0, cols=None, preserve_categories=True)
  - pt.cols(df, ascending=True)
  - pt.glimpse(df, width=None)
  - pt.freq(df, col=None, *, dropna=False)
  - pt.hist(df, col=None, bins=10)
  - pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False)
  - pt.safe_reset_index(df)
  - pt.sample(data_or_name="penguins", n=None, frac=None, seed=None)
  - pt.sample_data (Mapping of bundled datasets)
  - pt.Plotter (lazy loaded when matplotlib is installed)
  - pt.plot(df, *args, **kwargs)
  - pt.finalize(plotter=None, **kwargs)

DataFrame Accessor (`df.pt`):
  Importing pytae automatically registers the `.pt` accessor on `pd.DataFrame` and `pl.DataFrame`.
  Methods on `df.pt`:
    df.pt.select(...)
    df.pt.filter(...)
    df.pt.by(...)
    df.pt.mutate(...)
    df.pt.arrange(...)
    df.pt.pick(...)
    df.pt.sample(...)
    df.pt.distinct(...)
    df.pt.dropna(...)
    df.pt.agg(...)
    df.pt.long(...)
    df.pt.wide(...)
    df.pt.pivot(...)
    df.pt.handle_missing(...)
    df.pt.cols(...)
    df.pt.glimpse(...)
    df.pt.freq(...)
    df.pt.hist(...)
    df.pt.clean_columns(...)
    df.pt.safe_reset_index(...)
    df.pt.to_clip(...)
    df.pt.plot(...)

Clipboard Methods (attached directly to Pandas on import pytae):
  df.to_clip()  # Copies DataFrame to clipboard as TSV without index
  s.to_clip()   # Copies Series to clipboard without index


3. SAMPLE DATASETS
--------------------------------------------------------------------------------
`pytae` includes pre-packaged datasets stored in parquet format inside the library.
Access methods:
  df = pt.sample("penguins")
  df = pt.sample_data["penguins"]

List available dataset names:
  list(pt.sample_data.keys())
  Available datasets include:
  - 'penguins': Palmer penguins dataset (species, island, bill_length_mm, 
    bill_depth_mm, flipper_length_mm, body_mass_g, sex, year).
  - 'tips': Restaurant tips dataset (total_bill, tip, sex, smoker, day, time, size).
  - 'titanic': Titanic passenger survival data (survived, pclass, sex, age, ...).
  - 'healthexp': Healthcare spending and life expectancy.
  - 'fmri': Functional MRI time points and BOLD signal.
  - 'flights', 'diamonds', 'iris', 'planets', 'taxis', 'seaice', 'mpg', etc.


4. PYTHON LIBRARY REFERENCE (API VERBS)
--------------------------------------------------------------------------------

4.1. pt.filter() / df.pt.filter() — Row Filtering
--------------------------------------------------------------------------------
Filters DataFrame rows based on callables, string expressions, plain dictionaries, 
or keyword arguments.

Signature:
  pt.filter(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pd.DataFrame
  df.pt.filter(*args: Any, **kwargs: Any) -> pd.DataFrame

Calling Styles:
  1. Callables / Lambdas:
     df.pt.filter(lambda d: d["body_mass_g"] > 5000)
  2. Keyword Arguments:
     df.pt.filter(species="Adelie", body_mass_g="> 5000")
  3. String Expressions (matches CLI -filter):
     df.pt.filter("body_mass_g > 5000, species == 'Adelie'")
     df.pt.filter("bill length mm > 40")   # Handles columns with spaces natively!
  4. Plain Dictionaries:
     df.pt.filter({"bill length mm": "> 40", "species": "Adelie"})
  5. Mixed Calling:
     df.pt.filter("bill length mm > 40", {"island": "Biscoe"}, species="Gentoo")
  6. Functional Style:
     pt.filter(penguins, species="Adelie")

Supported Condition Types & Operators:
  - Equality:
    species="Adelie"
    "species = Adelie" or "species = 'Adelie'" or "species == 'Adelie'"
    {"species": "Adelie"}
  - Membership (in list):
    species=["Adelie", "Gentoo"]
    species=("in", ["Adelie", "Gentoo"])
  - Exclusion (not in list):
    sex=("not in", ["Male"])
  - Comparison Operators:
    Supported operators: '>', '>=', '<', '<=', '==', '!='
    As string condition: body_mass_g="> 5000"
    As tuple condition:  body_mass_g=(">", 5000)
    Note: For numeric columns, values are converted to float automatically.
  - Interval Notation (range queries on a single column):
    Open interval:       body_mass_g="(3500,4500)"    -> 3500 < x < 4500
    Half-open interval:  bill_length_mm="[40,50)"     -> 40 <= x < 50
    Closed interval:     body_mass_g="[3500,4000]"    -> 3500 <= x <= 4000
    String interval:     island="(Biscoe,Dream]"      -> Alphabetical range
  - String Accessor Operations (requires string-dtype column; na=False):
    Prefix match:        species=("startswith", "Ad")
    Multi-prefix match:  species=("startswith", ["Ad", "Ge"])  # accepts list/tuple
    Suffix match:        code=("endswith", "3")
    Substring match:     species=("contains", "in")    # regex=False, search-anywhere
    Regex match:         species=("regex", r"^[AB]")   # regex=True, search-anywhere
  - Null Checks (predicate expressions):
    Missing values:      "sex.isna()" or "sex is null"
    Non-missing values:  "sex.notna()" or "sex is not null"

Multiple Conditions on the Same Column:
  Python kwargs cannot repeat parameter names. Solve this using:
  1. Comma-separated string:  df.pt.filter("bill_length_mm > 40, bill_length_mm < 50")
  2. Multiple string args:    df.pt.filter("bill_length_mm > 40", "bill_length_mm < 50")
  3. Interval syntax:         df.pt.filter(bill_length_mm="[40,50)")
  4. Chained calls:           df.pt.filter(bill_length_mm="> 40").pt.filter(bill_length_mm="< 50")

Error Handling:
  If a column name is misspelled, filter() raises a KeyError with fuzzy match suggestions:
  KeyError: "unknown column 'speceis' (did you mean 'species'?)"


4.2. pt.by() / df.pt.by() — Single-Shot Scoped Grouping
--------------------------------------------------------------------------------
Sets active grouping state on a DataFrame. In pytae, grouping is strictly SINGLE-SHOT:
verbs (`mutate`, `pick`, `agg`) NEVER accept `by=`. They inherit active grouping 
strictly from `pt.by()`. If passed `by=`, verbs immediately raise a `TypeError`.

Signature:
  pt.by(df: DataFrame, *cols: str) -> GroupedDataFrame
  df.pt.by(*cols: str) -> GroupedDataFrame

Key Rules & Behaviors:
  - Single-Shot Scoped Grouping: Grouping applies strictly to the immediate next operation.
    Every operation (`mutate()`, `agg()`, `pick()`) automatically ungroups upon completion,
    returning a clean, flat, ungrouped DataFrame.
  - No Ungroup Needed: Because grouping never persists, subsequent operations naturally
    evaluate across the whole table without requiring `ungroup()`.
  - Fluent Transition: You can transition between group scopes and overall table scopes in one chain:
    df.by("region").mutate(r_avg="mean(sales)").mutate(all_avg="mean(sales)").by("product").mutate(p_avg="mean(sales)")
  - Precedence: If a second `.pt.by()` is called, it cleanly overwrites the previous grouping context.


4.3. pt.mutate() / df.pt.mutate() — Column Creation & Feature Engineering
--------------------------------------------------------------------------------
Creates or overwrites columns using expressions evaluated in order via pandas eval() 
with automatic fallback to plain Python eval on Series objects. Inherits active grouping 
strictly from `pt.by()`.

Signature:
  pt.mutate(
      df: pd.DataFrame,
      *args: Any,
      dropna: bool = False,
      observed: bool = True,
      params: dict | None = None,
      **kwargs: Any,
  ) -> pd.DataFrame

Calling Styles:
  1. Keyword Arguments:
     df.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")
  2. Dictionary Unpacking (for column names containing spaces):
     df.pt.mutate(**{"body mass kg": "body_mass_g / 1000"})
  3. String Expressions (matching CLI -mutate):
     df.pt.mutate("mass_kg = body_mass_g / 1000, [mass lbs] = mass_kg * 2.20462")
  4. External Spec File:
     df.pt.mutate("@features.txt")
  5. Callables / Lambdas:
     df.pt.mutate(is_heavy=lambda d: d["body_mass_g"] > 4000)

Comprehensive Feature Set (The 12 Mutate Capabilities):
  1. Normal Mutate: Standard arithmetic and boolean derivations.
  2. Sequential Chaining: Later expressions can reference columns created earlier 
     in the SAME mutate() call:
     df.pt.mutate(mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")
  3. Binary Conditionals (`if_else`):
     df.pt.mutate(size="if_else(body_mass_g >= 4000, 'Heavy', 'Standard')")
  4. Multi-Condition Tiers (`case_when`):
     Ordered evaluation (first match wins). Accepts (cond, value) tuples or flat pairs:
     df.pt.mutate(tier="case_when((mass_kg >= 5.0, 'XL'), (mass_kg >= 4.0, 'L'), default='S')")
     df.pt.mutate(tier="case_when(mass_kg >= 5.0, 'XL', mass_kg >= 4.0, 'L', default='S')")
  5. First Non-Null Resolution (`coalesce`):
     Resolves the first non-null candidate per row:
     df.pt.mutate(contact="coalesce(mobile, home, work, 'Unknown')")
  6. Dictionary Lookup (`map`):
     Recodes values through a mapping dictionary with optional fallback (supports literal 'OTHER', column itself like species to keep unmatched values, or another column):
     df.pt.mutate(code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE'}, species)")
     df.pt.mutate(code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE'}, default='OTHER')")
  7. Missing & NaN Value Filling (`fillna`, `fill_null`, `fill_nan`):
     fillna(col, val, nans=True) fills both float NaN and Arrow nulls by default. Set nans=False to fill null only.
     df.pt.mutate(clean_rate="fillna(profit / revenue, 0.0)")
     df.pt.mutate(clean_str="fill_null(notes, 'N/A')")
  8. Caller Scope Variables (`@var`):
     Reference local variables from caller scope using `@name`:
     threshold = 4000
     df.pt.mutate(heavy="body_mass_g >= @threshold")
     Or pass explicitly via params:
     df.pt.mutate(heavy="body_mass_g >= @threshold", params={"threshold": 4000})
     (Note: In CLI, `@var` gives a helpful error explaining that caller scopes exist only in Python).
  8. Columns With Spaces (`[col]` or `` `col` ``):
     Enclose spaced column names in brackets `[body mass g]` or backticks:
     df.pt.mutate(ratio="[body mass g] / [bill length mm]")
  9. Grouped Window Transforms (Inherited from `pt.by()`, `dropna=False`, `observed=True`):
     Evaluates aggregations per group via fast vectorized `GroupBy.transform()` and broadcasts back to each row without collapsing rows (N -> N):
     - Injected Aggregations: mean(x), sum(x), median(x), min(x), max(x), std(x), var(x), n (or n())
     - Example:
       (
           df
           .pt.by("species")
           .pt.mutate("avg_mass = mean(body_mass_g), diff = body_mass_g - avg_mass, group_size = n")
       )
     - `dropna=False` (default across pytae): Missing group categories form their own distinct group.
     - `dropna=True`: Rows with NA in grouping columns receive NaN in new columns while preserving index alignment.
  10. Custom Functions & Callables in `mutate()`:
      - Vectorized Functions: If your function takes Series or arrays, call it directly:
        df.pt.mutate(ratio="calc_ratio(bill_length_mm, bill_depth_mm)")
      - Series Method `.apply()`: Directly call `.apply()` on columns in expressions:
        df.pt.mutate(clean="species.apply(clean_species)")
      - Whole-DataFrame Callables: Pass a lambda taking the accumulated DataFrame:
        df.pt.mutate(is_large=lambda df: (df["mass_kg"] > 4.0) & (df["bill_ratio"] > 2.5))
      - Row-Level Functions (`lambda df: df.apply(my_func, axis=1)`):
        When custom business logic requires a function expecting a single row (`Series`):
        def classify(row):
            if pd.isna(row["mass_kg"]): return "Missing"
            return "Heavy" if row["mass_kg"] > 4.5 and row["species"] == "Gentoo" else "Standard"
        df.pt.mutate(
            mass_kg="body_mass_g / 1000",
            category=lambda df: df.apply(classify, axis=1),
        )
   11. Literal Constants (Python API & CLI):
       In `mutate()`, standard identifiers refer to columns/expressions.
       To assign an explicit literal string constant, wrap it in inner quotes:
       df.pt.mutate(source="'tag'", status="'active'")
       Numbers and booleans are passed directly: df.pt.mutate(count=10, flag=True).
   12. Multi-Column Transforms (`[prefix](col1, col2)[suffix] = expr`):
       Apply the same formula across multiple columns at once using parenthesized target specs and `_` as the current column placeholder:
       - In-place overwrite: `df.pt.mutate("(rev, cost) = _ * 1.08")`
       - Suffix/prefix new columns: `df.pt.mutate("(rev, cost)_usd = _ * 1.08")` or `df.pt.mutate("norm_(rev, cost) = _ / max(_)")`
       - Pattern & dtype selectors: `df.pt.mutate("(startswith=bill_) = _ / 10")` or `df.pt.by("species").pt.mutate("z_(dtype=numeric) = (_ - mean(_)) / std(_)")` (automatically excludes active grouping columns).


4.4. pt.select() / df.pt.select() — Column Selection, Slicing & Exclusion
--------------------------------------------------------------------------------
Selects, reorders, or excludes columns using names, ranges/slices, criteria keywords, 
or negative exclusions.

Signature:
  pt.select(
      df: pd.DataFrame,
      *args: Any,
      exclude: str | Sequence[str] | None = None,
      dtype: str | type | Sequence[str | type] | None = None,
      exclude_dtype: str | type | Sequence[str | type] | None = None,
      contains: str | Sequence[str] | None = None,
      startswith: str | Sequence[str] | None = None,
      endswith: str | Sequence[str] | None = None,
      regex: str | Sequence[str] | None = None,
  ) -> pd.DataFrame

Argument Types for *args:
  - Exact Column Names:
    df.pt.select("species", "island")
  - List of Names:
    df.pt.select(["species", "island"])
  - Slice Range ('start:end'):
    Contiguous slice from start to end (inclusive of both bounds):
    df.pt.select("bill_length_mm:body_mass_g")
    Open slices: ":body_mass_g" (from start), "body_mass_g:" (to end)
  - pt.everything() (or pt.everything):
    Pulls in all remaining unselected columns in their original order:
    df.pt.select("species", pt.everything())  # species first, then the rest
  - Predicate Callable:
    df.pt.select(lambda c: c.startswith("b"))

Negative Column Selection & Exclusions:
  - Positional Negation: Pass names prefixed with `-` or `~`:
    df.pt.select("-species")                      # Drop species, keep the rest
    df.pt.select("-species", "-island")           # Drop multiple
    df.pt.select("-bill_length_mm:body_mass_g")   # Drop contiguous slice range
  - Keyword Exclusion (`exclude=`):
    df.pt.select(exclude="species")
    df.pt.select(exclude=["species", "island"])
    df.pt.select(exclude="[col a, col b]")
  - Automatic Inversion: If ONLY exclusions are specified, `select()` automatically starts 
    with all columns and drops the excluded ones.

Criteria Keyword Arguments:
  - regex: Regex pattern matching column names: `df.pt.select(regex=r"^bill")`.
  - contains: Substring(s) in column names: `df.pt.select(contains="mm")`.
  - startswith: Prefix(es) in column names: `df.pt.select(startswith="bill")`.
  - endswith: Suffix(es) in column names: `df.pt.select(endswith="mm")`.
  - dtype: Include columns by dtype shorthand ('numeric', 'datetime', 'category', 'bool').
  - exclude_dtype: Exclude columns by dtype. Cannot be combined with other criteria.


4.5. pt.arrange() / df.pt.arrange() — Row Sorting
--------------------------------------------------------------------------------
Reorders rows by one or more columns with inline directions or bracketed names.

Signature:
  pt.arrange(
      df: pd.DataFrame,
      *cols: str | Sequence[str],
      ascending: bool | Sequence[bool] | None = None,
      na_last: bool = True,
  ) -> pd.DataFrame

Calling Styles:
  # Ascending (default), descending ("desc" or leading "-"), bracketed for spaces
  df.pt.arrange("species", "body_mass_g desc")
  df.pt.arrange("species, -body_mass_g")
  df.pt.arrange("[bill length mm] desc")


4.6. pt.pick() / df.pt.pick() — Extreme Row Slicing
--------------------------------------------------------------------------------
Selects extreme top or bottom N rows (or proportion of rows) ordered by a target column.
Inherits active grouping strictly from `pt.by()`. Rejects `by=` in kwargs with TypeError.

Signature:
  pt.pick(
      df: pd.DataFrame,
      order_by: str,
      n: int | None = 1,
      prop: float | None = None,
      order: str = "max",
      with_ties: bool = False,
      na_last: bool = True,
  ) -> pd.DataFrame

Calling Styles:
  # Top / bottom rows overall
  df.pt.pick("body_mass_g", n=3)                 # Top 3 (default order="max")
  df.pt.pick("body_mass_g", n=1, order="min")    # Lightest penguin
  df.pt.pick("body_mass_g", prop=0.1)            # Top 10%

  # Group-aware extreme selection:
  (
      penguins
      .pt.by("species")
      .pt.pick("body_mass_g", n=1)
      .pt.select("species", "island", "body_mass_g")
  )


4.7. pt.distinct() / df.pt.distinct() — Deduplication
--------------------------------------------------------------------------------
Removes duplicate rows across all columns or a specified subset of columns.
Resets the index cleanly to a standard RangeIndex(0, 1, 2, ...).

Signature:
  pt.distinct(df: pd.DataFrame, *cols: str, keep: str | bool = "first") -> pd.DataFrame
  df.pt.distinct(*cols: str, keep: str | bool = "first") -> pd.DataFrame

Calling Styles:
  df.pt.distinct()                        # Deduplicate across all columns (keep="first")
  df.pt.distinct("species", "island")     # Deduplicate on subset of columns
  df.pt.distinct(keep="last")             # Keep last occurrence
  df.pt.distinct("species", keep=False)   # Drop all duplicate occurrences


4.8. pt.agg() / df.pt.agg() — Grouped Aggregation
--------------------------------------------------------------------------------
Aggregates numeric columns grouped by active grouping set beforehand via `pt.by()`.
If no grouping is set, computes a whole-table summary (1 row). Rejects `by=` in kwargs.

Signature:
  pt.agg(
      df: pd.DataFrame,
      *args: Any,
      a: str | list[str] | None = None,
      dropna: bool = False,
      observed: bool = True,
      **kwargs: Any,
  ) -> pd.DataFrame

Calling Styles:
  1. Grouped Aggregation via Method Chaining:
     (
         penguins
         .pt.by("species")
         .pt.agg(avg_mass="body_mass_g:mean", count="n")
     )
  2. String Mapping Specification (Zero Dict Unpacking!):
     (
         tips
         .pt.by("smoker")
         .pt.agg("tip = mean, [total bill] = mean, n = n")
     )
  3. Whole-Frame Aggregations:
     (
         penguins
         .pt.by("species")
         .pt.agg("mean")
     )
  4. Whole-Table Grand Total (Ungrouped summary, 1 row):
     penguins.pt.agg("mean, n")
     penguins.pt.agg(avg_mass="body_mass_g:mean", n="n")

Key Rules & Behaviors:
  - NO REDUNDANT SELECT:
    You NEVER need a `pt.select(...)` or `-select` before `agg()`. Target columns and aggregation
    functions are declared directly inside `agg`.
  - Row Count ('n'):
    Assigning a key with value 'n' produces the group row count: `count="n"`.
  - Column Names:
    If a single aggregation is applied, the original name is preserved: `body_mass_g='mean'`.
    If multiple aggregations are applied, names become `{col}_{agg}`: `body_mass_g=['mean', 'max']`.
  - dropna Default:
    `dropna=False` by default preserves missing category groups across aggregations.


4.9. pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
--------------------------------------------------------------------------------
Pure structural reshaping between long and wide formats without aggregation.

pt.long(df, cols=None, id_vars=None, c="variable", v="value"):
  Melts columns to rows. If cols is None, melts all numeric columns, keeping 
  non-numeric columns as ID variables.
  Parameters:
    cols: Column(s) to melt to rows. Supports bracketed names `[col name]`.
    id_vars: Identifier column(s) to keep as rows.
    c: column name for melted metric names (default: "variable")
    v: column name for melted metric values (default: "value")

pt.wide(df, r=None, c="variable", v="value"):
  Pivots long-format records back into column headers (exact reverse of pt.long).
  Strictly 1-to-1 without aggregation.
  Parameters:
    r: explicit row identifier column(s). If None, all remaining columns are used.
    c: column whose unique values become headers (default: "variable")
    v: column containing values (default: "value")
  Rules:
    - Requires unique (r, c) pairs. If duplicate keys exist, raises ValueError
      guiding the user to use pt.pivot() instead.


4.10. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
--------------------------------------------------------------------------------
Full multi-dimensional 2D pivot table and frequency cross-tabulation engine.
Automatically flattens multi-level column hierarchies to clean 1D string names 
and resets the index to standard RangeIndex(0, 1, 2, ...).

Signature:
  pt.pivot(
      df: pd.DataFrame,
      r: str | Sequence[str] | None = None,
      c: str | Sequence[str] | None = None,
      v: str | Sequence[str] | None = None,
      a: str | Callable | Sequence[str | Callable] = "sum",
      dropna: bool = False,
      f_v: Any = None,
  ) -> pd.DataFrame

Parameters:
  r: Row grouping column(s).
  c: Column dimension(s) to spread as headers.
  v: Value column(s) to aggregate. Optional when counting (a="n").
  a: Aggregation function (default: "sum"; use "n" for row counts).
  dropna: Whether to drop NA categories in row/column keys (default: False).
  f_v: Scalar value for missing grid intersections (default: 0 for a="n").

Examples:
  df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")
  df.pt.pivot(r="island", c="species", a="n")


4.11. Other Utilities
--------------------------------------------------------------------------------
- pt.dropna(df, *cols, how=None, drop_nans=True) / df.pt.dropna(...) / pt.drop_nulls(...) / pt.drop_na(...):
  Drops rows with missing values (Arrow null and float NaN). Defaults to how='all' (Zero Data Loss) when cols is empty,
  or how='any' when columns are explicitly passed. Supports aliases drop_nulls and drop_na across library and CLI.
- pt.cols(df, ascending=True):
  Returns list of column names (ascending=True for A-Z, False for Z-A, None for file order).
- pt.glimpse(df, width=None) / df.pt.glimpse(width=None):
  Prints transposed overview of DataFrame columns, dtypes, and sample values (returns self).
- pt.freq(df, col=None, *, dropna=False) / df.pt.freq(col=None, *, dropna=False):
  Computes frequency distribution DataFrame with counts, percentages, and ASCII bars.
- pt.hist(df, col=None, bins=10) / df.pt.hist(col=None, bins=10):
  Computes numeric histogram DataFrame with bin intervals, counts, and ASCII bars; accepts "col:bins" shorthand.
- pt.join(df, right, on=None, how="inner", suffix="_right", suffixes=None, validate=None, coalesce=None) / df.pt.join(...) / df.join(...):
  Joins two DataFrames on keys using high-performance Polars engine. Supports how="inner"|"left"|"right"|"full"|"semi"|"anti"|"cross",
  colon notation on="id:uid", validation ("1:1", "1:m", "m:1", "m:m"), auto-discovery of common keys, and preserves LazyFrame query plans.
- pt.concat(dfs, how="vertical") / df.pt.concat(other, how="vertical") / df.concat(other, how="vertical"):
  Stacks DataFrames vertically (how="vertical", with automatic fallback to diagonal relaxed stacking on schema mismatches)
  or horizontally (how="horizontal", with automatic column deduplication).
- Transparent Polars Verb Delegation (__getattr__):
  Any native Polars method (e.g. .with_columns(), .slice(), .describe(), .explode()) can be called directly on pytae.DataFrame.
  Arguments are auto-unwrapped and results are rewrapped into pytae.DataFrame so method chains never break.
- pt.handle_missing(df, fillna=".", numeric_fill=0, cols=None, preserve_categories=True):
  Sanitizes missing values with type-safe defaults.
- pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False):
  Systematically sanitizes DataFrame header names.
- pt.safe_reset_index(df) / df.pt.safe_reset_index():
  Safely resets DataFrame index, raising an informative ValueError on collision.
- df.to_clip() / s.to_clip() / df.pt.to_clip():
  Copies DataFrame or Series to clipboard as TSV without index.


4.12. Plotter — Visualization & Dashboarding (Plotting API)
--------------------------------------------------------------------------------
Method-chainable plotting system wrapping `pandas.plot` and `matplotlib`.
Requires: pip install 'pytae[plot]'

Key Concepts:
  - Clean Separation of Concerns (Path A — No In-Plot Aggregation):
    Summarize first with `df.pt.by(...).pt.agg()` or `df.pt.pivot()`.
  - Multi-Panel Dashboards (Mosaic Layouts):
    k = pt.Plotter('''
    AB
    CD
    ''', figsize=(10, 8))
  - Secondary Y-Axis ('^' or secondary_y=True).
  - Small Multiples / Auto-Faceting:
    pt.plot(penguins, by="species", ncols=3, kind="scatter", x="bill_length_mm", y="bill_depth_mm").finalize()


5. CLI REFERENCE (COMMAND LINE INTERFACE)
--------------------------------------------------------------------------------

5.1. Execution Model & Pipeline Architecture
--------------------------------------------------------------------------------
The CLI command `pytae` processes operations sequentially in the order given on 
the command line:
  pytae input.parquet -filter "body_mass_g > 3000" -mutate "mass_kg = body_mass_g / 1000" -head 5

Pipeline Rules:
1. Input Source: The first unflagged argument is the input file path, or 'clip'
   to ingest tabular data directly from the system clipboard. STDIN is auto-detected.
2. Sequential Mutation: Each operation transforms the intermediate dataset in memory.
3. Final Operation Determines Output: Only the last operation prints or exports.
4. Shell Quoting: Always quote multi-word arguments and expressions in your shell.
5. Vectorized Polars Execution: CLI pipelines execute natively via an internal SIMD
   Polars engine with lazy evaluation, streaming files and intermediate operations
   in vector memory at 10x–20x speedups with seamless fallback to Pandas.


5.2. File Formats & Zero-Cost Metadata Inspection
--------------------------------------------------------------------------------
Supported input & output file types:
  - .parquet, .pq (columnar storage)
  - .csv, .tsv, .txt, .dat, .jsonl, .ndjson
  - .csv.gz, .txt.gz, .dat.gz, .jsonl.gz (transparent gzip)
  - .sas7bdat (SAS binary dataset, read-only)

Fast Zero-Cost Inspection (Metadata-Only):
  - `-shape`: Returns (rows, columns)
  - `-cols`: Prints column names in order
  - `-dtype`: Shows data types
  - `-head [N]`: Reads only first N rows
  - `-meta`: Displays complete zero-scan Parquet metadata


5.3. All CLI Flags & Syntax Rules
--------------------------------------------------------------------------------
Inspection & Summary Flags:
  -head [N]             Print first N rows (default 5)
  -tail [N]             Print last N rows (default 5)
  -shape                Print row and column counts (rows, cols)
  -cols [ORDER]         Print column names (ORDER: asc, desc, file)
  -dtype [ORDER]        Print column data types (ORDER: asc, desc, file)
  -nulls [ORDER]        Print null value counts per column (ORDER: asc, desc, file)
  -describe             Descriptive statistics for numeric columns
  -info                 DataFrame summary (dtypes, non-null counts, memory)
  -glimpse              Transposed column overview with dtypes and sample values
  -meta                 Display zero-scan Parquet metadata
  -diff PATH            Compare schema, shape, null counts against another file
  -value_counts         Value counts for categorical/string columns
  -distinct [SPEC]      Drop duplicate rows across all or specified columns, with keep=first|last|false
  -sample [N]           Random sample of N rows (default 5)
  -seed N               Random seed for sampling
  -frac P               Sample fraction P (0.0 < P <= 1.0)
  -nrows, -limit N      Limit reading to first N rows of file
  -arrange SPEC         Sort rows by columns: e.g. -arrange "col1, col2 asc" or -arrange "col1 desc"

In-Terminal ASCII Visualizations:
  -freq COL             Render horizontal frequency distribution bars with counts & percentages
  -hist COL[:BINS]      Render in-terminal distribution histogram for a numeric column (default: 10 bins)

Row Filtering & Slicing Flags:
  -filter CONDITIONS    pytae filter expressions (e.g. "species='Adelie', body_mass_g > 3500")
  -dropna [COLS]        Drop rows with missing values (bare defaults to how=all; cols defaults to how=any)
  -pick SPEC            Extract extreme rows by column (e.g. "body_mass_g,n=3" or "body_mass_g,order=min"), group-aware with -by

Column Transformation Flags:
  -select SPEC          Select columns (names, slices 'a:b', contains, dtypes, negative '-col', '~col', exclude=)
  -mutate SPEC          Create/overwrite columns ("new_col = expr" or multi-column "[prefix](col1, col2)[suffix] = expr" using _ placeholder)
  -rename OLD:NEW,...   Rename columns using ':' delimiter (e.g. "a:alpha, b:beta")
  -clean_columns SPECS  Clean headers: "strip=True, fill='_', case='lower', dedupe=True"
  -handle_missing [VAL] Impute missing values with type-safe defaults (default: '.')

Aggregation & Reshaping Flags:
  -by COLS              Grouping columns for -agg, -mutate, -pick (e.g. -by species -agg mean)
  -agg [SPECS]          Aggregate columns (e.g. -by species -agg "body_mass_g=mean, count=n" or -agg mean).
                        When -by is omitted, -agg computes a whole-table summary!
  -long [SPECS]         Melt numeric columns to rows: "c=variable, v=value"
  -wide [SPECS]         Pure 1-to-1 unmelting into headers: "c=variable, v=value"
  -pivot SPECS          2D pivot table: "r=species, c=island, v=body_mass_g, a=mean" (or counts: "r=species, c=island, a=n")

SQL & Multi-File Flags:
  -sql QUERY            Run Polars SQL on table 'data' (or @query.sql)
  -file SPECS           Multi-file mode: "file1.parquet=df1; file2.csv=df2"
  -join SPECS           Join files: "left=df1, right=df2, on=id, how=inner"
  -concat SPECS         Stack files: "frames='df1,df2'"

Output & Formatting Flags:
  -o TARGET             Output destination (file path, format for batch conversion, or 'clip')
  -out_dir, -od DIR     Target directory for exported files
  -pretty               Pretty-print tables with bordered markdown formatting
  -pager                Pipe output through system pager ($PAGER or less)
  -round N              Round numeric output columns to N decimal places


5.4. In-Terminal Visualizations (-freq, -hist)
--------------------------------------------------------------------------------
1. Horizontal Frequency Bars (-freq):
   pytae penguins.parquet -freq species

2. In-Terminal Distribution Histogram (-hist):
   pytae penguins.parquet -hist body_mass_g:8


5.5. Quoting & Delimiter Standards (: vs =)
--------------------------------------------------------------------------------
1. Mapping / Translation uses COLON (`:`):
   - `-rename`: "old_col:new_col, col_b:col_beta"
2. Assignment / Specification uses EQUALS (`=`):
   - `-mutate`: "new_col = expression, mass_kg = body_mass_g / 1000"
   - `-filter`: "species = 'Adelie', body_mass_g > 3500"
   - `-clean_columns`: "strip=True, fill='_', case='lower'"
   - `-join`: "left=df1, right=df2, on=id, how=left"
   - `-agg`: "tip=mean, total_bill=mean, n=n"


5.6. Multi-File Operations (-file, -join, -concat, -sql)
--------------------------------------------------------------------------------
pytae -file "orders.parquet=ord; customers.csv=cust" \
      -join "left=ord, right=cust, on=cust_id, how=inner" \
      -select "order_id,cust_name,amount" -head 10


5.7. Batch Processing, Conversions & Clipboard (-o)
--------------------------------------------------------------------------------
pytae penguins.parquet -o penguins.csv
pytae penguins.parquet -o csv
pytae 'data/*.parquet' -o csv
pytae penguins.parquet -filter "body_mass_g > 4000" -o heavy_penguins.parquet
pytae penguins.parquet -head -o clip


6. FREQUENTLY ASKED QUESTIONS, PITFALLS & SYNTAX RULES
--------------------------------------------------------------------------------

6.1. When should I use `-select` before `-agg`?
-----------------------------------------------
When declaring specific columns inside `-agg` (e.g. `-agg "avg_mass = body_mass_g:mean, n = n"`),
pytae automatically restricts output to grouping keys and target columns.
When computing bulk summaries (e.g. `-agg mean`), using `-select` beforehand prunes unneeded columns.

6.2. Why is `by` strictly standalone across all verbs?
------------------------------------------------------
To adhere strictly to the "one and only one obvious way" philosophy:
- `by` is never an argument inside verbs (`mutate`, `pick`, `agg`).
- Grouping must always be declared beforehand via `pt.by(df, *cols)` or `.pt.by(*cols)`.
- Verbs inherit grouping from `df.attrs['_pt_by']` and raise a `TypeError` if passed `by=`.

6.3. Why does every chained method call start on a new line?
------------------------------------------------------------
In all pytae code, pipelines, and Jupyter notebooks, every chained method call must start on 
its own new line:
```python
(
    penguins
    .pt.by("species")
    .pt.pick("body_mass_g", n=1)
    .pt.select("species", "island", "body_mass_g")
)
```
This ensures readable git diffs, clean execution tracebacks, and syntactic consistency.

6.4. What are the key canonical verbs (filter, pick, distinct)?
-----------------------------------------------------------------
Pytae standardizes on canonical modern naming:
- `pt.filter()` / `df.pt.filter()` / `-filter`: Replaces `qry`
- `pt.pick()` / `df.pt.pick()` / `-pick`: Replaces `slice_max` and `slice_min` (the legacy `slice_max`/`slice_min` functions and flags have been completely removed with no backward compatibility).
- `pt.distinct()` / `df.pt.distinct()` / `-distinct`: Standard deduplication verb (the legacy `dedupe` function and flag have been completely removed with no backward compatibility).

6.5. How do I apply custom functions in `mutate()`?
---------------------------------------------------
- Dictionary Value Recoding: Use formula `map(col, mapping[, fallback])` inside string expressions:
  `df.pt.mutate(code="map(species, {'Adelie': 'AD'}, 'Other')")`
- Vectorized Array / Math Functions: Pass callables directly on columns:
  `df.pt.mutate(adj=lambda d: np.maximum(d["a"], 0) * 1.5)`
- Row-Wise Scalar Functions: Pass callables wrapping scalar functions in Python's standard `map()`:
  `df.pt.mutate(shipping=lambda d: map(route_order, d["origin"], d["dest"]))`
(Formula `map()` is strictly for dictionary lookups; `lambda d:` is for Python functions.)

6.6. Can row-level functions access newly created columns in the same `mutate()`?
---------------------------------------------------------------------------------
YES! Because `mutate()` executes sequentially, earlier mutations are immediately attached.

6.7. Why does `df.pt.mutate(col=my_func)` fail when `my_func` expects a row?
----------------------------------------------------------------------------
When passed directly, `mutate` passes the entire DataFrame to `my_func`. Use `lambda df: df.apply(my_func, axis=1)`.

6.8. What is the difference between `wide()` and `pivot()`?
-----------------------------------------------------------
`wide()` is strictly 1-to-1 unmelting without aggregation. `pivot()` is a 2D aggregation matrix engine.

6.9. How do negative column exclusions work in `select()` and CLI `-select`?
----------------------------------------------------------------------------
Pass negative prefixes `pt.select(df, "-species", "-island")` or `exclude=["species", "island"]`.

6.10. How do columns with spaces work across expressions?
---------------------------------------------------------
In expressions, enclose in brackets `[body mass g]` or backticks `` `body mass g` ``.
In `filter()`, spaces in conditions are handled natively: `df.pt.filter("bill length mm > 40")`.

6.11. Why did `-sort` or `-sort_by` fail? (Use `-arrange`)
----------------------------------------------------------
Pytae standardizes strictly on `-arrange` for row ordering.

6.12. How do I inspect metadata without reading data into RAM?
--------------------------------------------------------------
For Parquet files, use `-meta` or inspection flags (`-shape`, `-cols`, `-dtype`, `-head`).

6.13. How do I assign literal constants in `mutate()`?
-------------------------------------------------------
In Python kwargs: use inner quotes `df.pt.mutate(source="'active'")`.
Unquoted `source="active"` references a column named `active`.
Numbers and booleans: `df.pt.mutate(count=10, flag=True)`.

6.14. How do I apply the same formula across multiple columns in `mutate()`? (Use `(col1, col2) = _ * 2`)
---------------------------------------------------------------------------------------------------------
Use parenthesized target syntax `[prefix](target_cols)[suffix] = expr` with `_` as the current column placeholder:
- In-place: `df.pt.mutate("(rev, cost, tax) = _ * 1.08")`
- New columns (suffix/prefix): `df.pt.mutate("(rev, cost)_usd = _ * 1.08")` or `df.pt.mutate("norm_(rev, cost) = _ / max(_)")`
- Selectors & grouped: `df.pt.by("species").pt.mutate("z_(dtype=numeric) = (_ - mean(_)) / std(_)")`


7. END-TO-END RECIPES & EXAMPLES
--------------------------------------------------------------------------------

Recipe 1: Master Mutate Recipe (All 12 Capabilities in One Pipeline)
--------------------------------------------------------------------------------
```python
import numpy as np
import pandas as pd
import pytae as pt

penguins = pt.sample("penguins")

# Caller-scope variable referenced via @ prefix
target_threshold = 4.2

# Custom row-level function
def classify_penguin(row):
    if pd.isna(row["mass_kg"]): return "Incomplete"
    if row["species"] == "Gentoo" and row["mass_kg"] > 5.0: return "Giant Gentoo"
    return "Standard"

master_df = (
    penguins
    .pt.by("species")
    .pt.mutate(
        # 12. Multi-column transform creating new _cm columns via _ placeholder
        "(bill_length_mm, bill_depth_mm)_cm = _ / 10",

        # 1. Normal mutate: standard arithmetic derivation
        bill_ratio="bill_length_mm / bill_depth_mm",
        mass_kg="body_mass_g / 1000",
        
        # 2. Sequential referencing of newly created col (mass_kg)
        bmi="mass_kg / ((flipper_length_mm / 1000) ** 2)",
        
        # 7. Local caller-scope variable reference (@target_threshold)
        above_target="mass_kg > @target_threshold",
        
        # 3. Binary conditional logic (if_else)
        size_label="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')",
        
        # 4. Multi-condition tiered categorization (case_when)
        weight_tier="case_when((mass_kg >= 5.0, 'XL'), (mass_kg >= 4.0, 'Large'), default='Small')",
        
        # 5. Null fallback (coalesce)
        effective_sex="coalesce(sex, 'Undetermined')",
        
        # 6. Dictionary category lookup (map)
        species_code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE', 'Chinstrap': 'CH'}, 'OTHER')",
        
        # 8. Spaced column creation via dict unpacking & bracket referencing
        **{"mass lbs": "mass_kg * 2.20462"},
        heavy_lbs="[mass lbs] > 9.5",
        
        # 9. Grouped window transforms inherited from pt.by("species") without collapsing rows
        species_avg_mass="mean(mass_kg)",
        mass_diff="mass_kg - species_avg_mass",
        group_size="n",
        
        # 10a. DataFrame lambda
        is_large=lambda df: (df["mass_kg"] > 4.0) & (df["bill_ratio"] > 2.5),
        
        # 10b. Row-level function via lambda df: df.apply(..., axis=1)
        category=lambda df: df.apply(classify_penguin, axis=1),
        
        # 11. Literal constant via inner quotes
        analysis="'species'",
    )
)
```

Recipe 2: Grouped Aggregation & 2D Pivots (Python & CLI)
--------------------------------------------------------------------------------
```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Clean grouped aggregation (no redundant select!)
agg_summary = (
    penguins
    .pt.by("species", "island")
    .pt.agg(mass_mean="body_mass_g:mean", count="n")
)

# 2. 2D Summary Matrix (Mean body mass across dimensions)
grid = penguins.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")

# 3. Frequency Cross-Tabulation (Counts across dimensions, v is omitted)
counts = penguins.pt.pivot(r="island", c="species", a="n")
```

```bash
# Equivalent CLI One-Liners:
pytae penguins.parquet -by "species,island" -agg "mass_mean=body_mass_g:mean, count=n"
pytae penguins.parquet -pivot "r=island, c=species, v=body_mass_g, a=mean"
pytae penguins.parquet -pivot "r=island, c=species, a=n"
```

Recipe 3: Group-Aware Extreme Row Selection (pt.by + pt.pick)
--------------------------------------------------------------------------------
```python
import pytae as pt

tips = pt.sample("tips")

# 1. Heaviest tip per day via method chaining
top_daily = (
    tips
    .pt.by("day")
    .pt.pick("tip", n=1)
    .pt.select("day", "total_bill", "tip")
)

# 2. Standalone functional pick overall
top_bill = pt.pick(tips, "total_bill", n=1)[["day", "total_bill", "tip"]]
```

```bash
# Equivalent CLI:
pytae tips.parquet -by day -pick "tip,n=1" -select "day,total_bill,tip"
```

Recipe 4: Polars SQL Query in CLI Pipeline
--------------------------------------------------------------------------------
```bash
# Single-file analytical query against table 'data'
pytae tips.parquet -sql "
select 
    day, 
    time, 
    count(*) as total_orders,
    round(avg(total_bill), 2) as avg_bill,
    round(avg(tip), 2) as avg_tip
from data
where total_bill > 15
group by day, time
order by avg_bill desc
"

# Cross-file analytical join in -file mode
pytae -file "customers.csv=c; orders.parquet=o" \
      -sql "select c.name, sum(o.amount) as total from c join o on c.cust_id = o.cust_id group by c.name"
```

Recipe 5: Multi-File Join, Concat, and Export
--------------------------------------------------------------------------------
```bash
# 1. Join files on shared key and filter
pytae -file "orders.parquet=ord; customers.csv=cust" \
      -join "left=ord, right=cust, on=cust_id, how=inner" \
      -filter "amount > 50" \
      -o filtered_orders.parquet

# 2. Concatenate monthly files and check row count
pytae -file "jan.parquet=m1; feb.parquet=m2; mar.parquet=m3" \
      -concat "frames='m1,m2,m3'" \
      -shape
```

Recipe 6: In-Terminal Visual Inspection (-freq, -hist, -meta, -arrange)
--------------------------------------------------------------------------------
```bash
# 1. Zero-scan Parquet metadata
pytae penguins.parquet -meta

# 2. Frequency distribution bars for categorical column
pytae penguins.parquet -freq species

# 3. Terminal histogram for numeric distribution (8 bins)
pytae penguins.parquet -hist body_mass_g:8

# 4. Sort and view top rows
pytae penguins.parquet -arrange "body_mass_g desc" -head 5
```

Recipe 7: Multi-Panel Dashboard with Secondary Y-Axis and Faceting
--------------------------------------------------------------------------------
```python
import pytae as pt

penguins = pt.sample("penguins")
tips = pt.sample("tips")

# 1. Multi-panel dashboard via mosaic layout
mosaic = \"\"\"\nAB\nCD\n\"\"\"
k = pt.Plotter(mosaic, figsize=(10, 8))
(k
 .data(penguins).plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species")
 .data(tips.pt.by("day").pt.agg(total_bill="mean")).plot(on="B", kind="bar", x="day", y="total_bill")
 .finalize(title="Executive Dashboard", consolidate_legends=True)
)
k.save("dashboard.png", dpi=300)

# 2. Small multiples / Auto-faceting
pt.plot(penguins, by="species", ncols=3, kind="scatter", x="bill_length_mm", y="bill_depth_mm").finalize()
```

================================================================================
11. REPOSITORY DIRECTORY TREE
================================================================================

.
├── LICENSE
├── changelog.md
├── contributing.md
├── docs
│   ├── comparison_to_pandas_and_dplyr.md
│   ├── detailed_docs
│   │   ├── agg.md
│   │   ├── arrange.md
│   │   ├── cli_only.md
│   │   ├── distinct.md
│   │   ├── filter.md
│   │   ├── join.md
│   │   ├── library_only.md
│   │   ├── mutate.md
│   │   ├── other_utilities.md
│   │   ├── pick.md
│   │   ├── pivot.md
│   │   ├── plotting.ipynb
│   │   ├── plotting.md
│   │   ├── read_write.md
│   │   ├── reshape.md
│   │   └── select.md
│   └── pytae.md
├── pyproject.toml
├── readme.md
├── reference
│   └── pytae_reference.txt
├── scripts
│   ├── generate_reference.py
│   └── run_notebooks.py
├── src
│   └── pytae
│       ├── __init__.py
│       ├── __main__.py
│       ├── _parsing.py
│       ├── _text.py
│       ├── accessor.py
│       ├── cli.py
│       ├── cli_help.py
│       ├── cli_parsing.py
│       ├── cli_pipeline.py
│       ├── cli_run.py
│       ├── dataframe.py
│       ├── datasets
│       │   ├── anagrams.parquet
│       │   ├── anscombe.parquet
│       │   ├── attention.parquet
│       │   ├── brain_networks.parquet
│       │   ├── car_crashes.parquet
│       │   ├── diamonds.parquet
│       │   ├── dots.parquet
│       │   ├── dowjones.parquet
│       │   ├── exercise.parquet
│       │   ├── flights.parquet
│       │   ├── fmri.parquet
│       │   ├── geyser.parquet
│       │   ├── glue.parquet
│       │   ├── healthexp.parquet
│       │   ├── iris.parquet
│       │   ├── mpg.parquet
│       │   ├── penguins.parquet
│       │   ├── planets.parquet
│       │   ├── seaice.parquet
│       │   ├── taxis.parquet
│       │   ├── tips.parquet
│       │   └── titanic.parquet
│       ├── mutate.py
│       ├── other_utilities.py
│       ├── plotting.py
│       ├── polars_engine.py
│       ├── py.typed
│       ├── readers.py
│       └── select.py
└── tests
    ├── __init__.py
    ├── cli_helpers.py
    ├── conftest.py
    ├── test_accessor.py
    ├── test_agg.py
    ├── test_arrange_slice.py
    ├── test_cli_agg.py
    ├── test_cli_clean.py
    ├── test_cli_enhancements.py
    ├── test_cli_filter.py
    ├── test_cli_inspect.py
    ├── test_cli_join.py
    ├── test_cli_mutate.py
    ├── test_cli_new_features.py
    ├── test_cli_parse.py
    ├── test_cli_reshape.py
    ├── test_cli_sample_datasets.py
    ├── test_cli_select.py
    ├── test_cli_sql.py
    ├── test_import.py
    ├── test_join_concat.py
    ├── test_lazy.py
    ├── test_mutate.py
    ├── test_pivot.py
    ├── test_plotter.py
    ├── test_polars_engine.py
    ├── test_readers.py
    ├── test_select.py
    ├── test_shape.py
    ├── test_utilities.py
    └── test_verbs_v39.py
"""


def _format_notebook(nb_path: Path) -> str:
    import json

    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    out_lines: list[str] = [f"# Notebook: {nb_path.name}\n"]
    for cell in nb.get("cells", []):
        cell_type = cell.get("cell_type")
        source = "".join(cell.get("source", [])).strip()
        if not source:
            continue
        if cell_type == "markdown":
            out_lines.append(source)
            out_lines.append("")
        elif cell_type == "code":
            out_lines.append("```python")
            out_lines.append(source)
            out_lines.append("```")
            for out in cell.get("outputs", []):
                if "text" in out:
                    text_str = "".join(out["text"]).strip()
                    if text_str:
                        out_lines.append("Output:")
                        out_lines.append("```text")
                        out_lines.append(text_str)
                        out_lines.append("```")
                elif "data" in out and "text/plain" in out["data"]:
                    data_val = out["data"]["text/plain"]
                    text_str = ("".join(data_val) if isinstance(data_val, list) else str(data_val)).strip()
                    if text_str:
                        out_lines.append("Output:")
                        out_lines.append("```text")
                        out_lines.append(text_str)
                        out_lines.append("```")
            out_lines.append("")
    return "\n".join(out_lines)


def generate_reference() -> None:
    parts: list[str] = []

    # MANUAL_TEXT contains sections 1 to 7 and section 11 (directory tree)
    # Split MANUAL_TEXT so sections 8, 9, 10 sit before the directory tree
    tree_marker = "================================================================================\n11. REPOSITORY DIRECTORY TREE"
    if tree_marker in MANUAL_TEXT:
        manual_pre, manual_tree = MANUAL_TEXT.split(tree_marker, 1)
        parts.append(manual_pre.strip())
    else:
        manual_pre = MANUAL_TEXT
        manual_tree = ""
        parts.append(manual_pre.strip())

    # Section 8: Detailed Feature Documentation Guides (docs/detailed_docs/)
    parts.append("\n================================================================================")
    parts.append("8. DETAILED FEATURE DOCUMENTATION GUIDES (docs/detailed_docs/)")
    parts.append("================================================================================\n")
    detailed_docs = sorted(
        list((REPO_ROOT / "docs" / "detailed_docs").glob("**/*.md"))
        + list((REPO_ROOT / "docs" / "detailed_docs").glob("**/*.ipynb")),
        key=lambda p: str(p.relative_to(REPO_ROOT)),
    )
    for doc_path in detailed_docs:
        rel_path = doc_path.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        if doc_path.suffix == ".ipynb":
            parts.append(f"# NOTEBOOK: {rel_path}")
            parts.append("################################################################################")
            parts.append(_format_notebook(doc_path).rstrip() + "\n")
        else:
            parts.append(f"# FILE: {rel_path}")
            parts.append("################################################################################")
            parts.append(doc_path.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 9: Master Documentation & Architecture Guide (docs/pytae.md)
    pytae_md = REPO_ROOT / "docs" / "pytae.md"
    if pytae_md.exists():
        parts.append("================================================================================")
        parts.append("9. MASTER DOCUMENTATION & ARCHITECTURE GUIDE (docs/pytae.md)")
        parts.append("================================================================================\n")
        parts.append("################################################################################")
        parts.append(f"# FILE: {pytae_md.relative_to(REPO_ROOT)}")
        parts.append("################################################################################")
        parts.append(pytae_md.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 10: Philosophy & Comparison Rosetta Stone (docs/comparison_to_pandas_and_dplyr.md)
    parts.append("================================================================================")
    parts.append("10. PHILOSOPHY & COMPARISON ROSETTA STONE (docs/comparison_to_pandas_and_dplyr.md)")
    parts.append("================================================================================\n")
    comp_md = REPO_ROOT / "docs" / "comparison_to_pandas_and_dplyr.md"
    parts.append("################################################################################")
    parts.append(f"# FILE: {comp_md.relative_to(REPO_ROOT)}")
    parts.append("################################################################################")
    parts.append(comp_md.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 11: Repository Directory Tree (from manual_tree)
    if manual_tree:
        parts.append("================================================================================")
        parts.append("11. REPOSITORY DIRECTORY TREE")
        parts.append(manual_tree.strip())

    # Section 12: pyproject.toml
    pyproject_path = REPO_ROOT / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8").strip()

    parts.append("\n================================================================================")
    parts.append("12. BUILD & CONFIGURATION (pyproject.toml)")
    parts.append("================================================================================\n")
    parts.append("File: pyproject.toml")
    parts.append("----------------------------------------")
    parts.append(pyproject_content)

    # Section 13: Underlying Python Implementation Source Code (src/pytae/)
    parts.append("\n================================================================================")
    parts.append("13. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)")
    parts.append("================================================================================\n")

    src_dir = REPO_ROOT / "src" / "pytae"
    src_files = sorted(src_dir.glob("*.py"))
    for f in src_files:
        rel_path = f.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        parts.append(f"# FILE: {rel_path}")
        parts.append("################################################################################")
        parts.append(f.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 14: Test Suite Implementation Source Code (tests/)
    parts.append("================================================================================")
    parts.append("14. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)")
    parts.append("================================================================================\n")

    test_dir = REPO_ROOT / "tests"
    test_files = sorted(test_dir.glob("*.py"))
    for f in test_files:
        rel_path = f.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        parts.append(f"# FILE: {rel_path}")
        parts.append("################################################################################")
        parts.append(f.read_text(encoding="utf-8").rstrip() + "\n")

    output_path = REPO_ROOT / "reference" / "pytae_reference.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"Successfully generated {output_path} ({len(output_path.read_text(encoding='utf-8').splitlines())} lines)")


if __name__ == "__main__":
    generate_reference()
