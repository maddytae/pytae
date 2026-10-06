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
    4.1.  pt.qry() / df.pt.qry() — Row Filtering
    4.2.  pt.mutate() / df.pt.mutate() — Column Creation & Feature Engineering
    4.3.  pt.select() / df.pt.select() — Column Selection, Slicing & Exclusion
    4.4.  pt.arrange() / pt.slice_max() / pt.slice_min() — Sorting & Group Slicing
    4.5.  pt.agg() / df.pt.agg() — Grouped Aggregation
    4.6.  pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
    4.7.  pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
    4.8.  pt.sql() / df.pt.sql() — DuckDB SQL Engine
    4.9.  Other Utilities:
          - pt.cols() / df.pt.cols()
          - pt.glimpse() / df.pt.glimpse()
          - pt.handle_missing() / df.pt.handle_missing()
          - pt.clean_columns() / df.pt.clean_columns()
          - pt.replace_values() / df.pt.replace_values()
          - safe_reset_index(df)
          - df.to_clip() / s.to_clip() (System Clipboard Export)
    4.10. Plotter — Visualization & Dashboarding (Plotting API)
5.  CLI REFERENCE (COMMAND LINE INTERFACE)
    5.1.  Execution Model & Pipeline Architecture
    5.2.  File Formats & Zero-Cost Metadata Inspection
    5.3.  All CLI Flags & Syntax Rules
    5.4.  In-Terminal Visualizations (-freq, -hist)
    5.5.  Quoting & Delimiter Standards (: vs =)
    5.6.  Multi-File Operations (-file, -merge, -concat, -sql)
    5.7.  Batch Processing, Conversions & Clipboard (-o)
6.  FREQUENTLY ASKED QUESTIONS, PITFALLS & SYNTAX RULES
    6.1.  Why is `-select` before `-agg` redundant?
    6.2.  Why is `by` required in `pt.agg()` but optional in the CLI (`-by`)?
    6.3.  How do I apply custom functions in `mutate()`? (Vectorized vs Series vs Row)
    6.4.  Can row-level functions access newly created columns in the same `mutate()`?
    6.5.  Why does `df.pt.mutate(col=my_func)` fail when `my_func` expects a row?
    6.6.  What is the difference between `wide()` and `pivot()`?
    6.7.  How do negative column exclusions work in `select()` and CLI `-select`?
    6.8.  How do columns with spaces work across expressions?
    6.9.  Why did `-sort` or `-sort_by` fail? (Use `-arrange`)
    6.10. How do I inspect metadata without reading data into RAM?
    6.11. How do I assign literal constants in `mutate()`? (Use `pt.lit()`)
7.  END-TO-END RECIPES & EXAMPLES (PYTHON & CLI)
    Recipe 1: Master Mutate Recipe (All 11 Features in One Pipeline)
    Recipe 2: Grouped Aggregation & 2D Pivots (Python & CLI)
    Recipe 3: DuckDB SQL Query with Joining Frames
    Recipe 4: Multi-File Merge, Concat, and Export
    Recipe 5: In-Terminal Visual Inspection (-freq, -hist, -meta, -arrange)
    Recipe 6: Multi-Panel Dashboard with Secondary Y-Axis and Faceting
8.  CLI FEATURE DOCUMENTATION GUIDES (docs/cli/ & docs/cli.md)
9.  INTERACTIVE LIBRARY NOTEBOOK WALKTHROUGHS (docs/library/ & docs/library.md)
10. PHILOSOPHY & COMPARISON ROSETTA STONE (docs/comparison.md)
11. REPOSITORY DIRECTORY TREE
12. BUILD & CONFIGURATION (pyproject.toml)
13. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)
14. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)
================================================================================


1. OVERVIEW & CORE PHILOSOPHY
--------------------------------------------------------------------------------
`pytae` is an ergonomic, high-performance tabular data manipulation library and 
command-line tool built on top of Pandas, PyArrow, DuckDB, and Matplotlib.

Key principles:
1. Dual Calling Convention: Every library verb exists both as a functional 
   function `pt.verb(df, ...)` and as a Pandas DataFrame accessor `df.pt.verb(...)`.
   The accessor enables seamless method chaining with standard Pandas methods:
   `df.rename(...).pt.qry(...).pt.agg(...)`.
2. Unix Pipeline CLI: The command-line tool `pytae` processes operations in 
   the exact order flags are passed on the terminal:
   `pytae data.parquet -qry "..." -mutate "..." -select "..." -head 10`.
3. Fast & Zero-Cost Metadata Inspection: For formats containing file-level metadata 
   (Parquet, SAS7BDAT), commands like `-shape`, `-cols`, `-dtype`, `-head` inspect 
   headers without parsing full table rows.
4. Expressive & Human-Friendly: Minimizes boilerplate. Filtering supports 
   intervals `[3000, 4000]`, string operations, and keyword arguments. Grouped 
   aggregations express grouping via `by=` and concise aggregations (e.g. `tip=mean`, 
   `n=n`) without tedious `.groupby().agg()` boilerplate.
5. Non-Destructive: All library verbs return copies of DataFrames and never 
   mutate inputs in place. Original indices are preserved during filtering.
6. Honest Error Handling ("Be generous in what you accept, but strictly honest 
   when ambiguous"): Flexible inputs are accepted where unambiguous, but collisions, 
   conflicts, and invalid arguments raise clear exceptions rather than silently 
   inventing artificial column suffixes or guessing.
7. One and Only One Right Way: Distinct responsibilities per verb—pure 1:1 unmelting 
   is `wide()`, 2D aggregation is `pivot()`, column selection is `select()`.
8. Plotting Without Implicit Aggregation (Path A): Plotters focus purely on 
   visual representation—data should be aggregated explicitly first via `agg` 
   or `pivot` before plotting, avoiding hidden or surprising aggregations.


2. PACKAGE ARCHITECTURE & IMPORT PATTERNS
--------------------------------------------------------------------------------
Installation (PyPI: https://pypi.org/project/pytae/):
  pip install pytae
  pip install 'pytae[plot]'    # includes matplotlib, scipy
  pip install 'pytae[sql]'     # includes duckdb

Importing:
  import pytae as pt
  import pandas as pd

Top-Level Functions exported by `pytae`:
  - pt.select(df, *args, exclude=None, dtype=None, exclude_dtype=None, contains=None, startswith=None, endswith=None, regex=None)
  - pt.everything() / pt.everything (sentinel for select)
  - pt.qry(df, *args, **kwargs)
  - pt.mutate(df, *args, by=None, dropna=False, observed=True, params=None, **kwargs)
  - pt.arrange(df, *cols)
  - pt.slice_max(df, order_by, n=1, by=None, with_ties=True)
  - pt.slice_min(df, order_by, n=1, by=None, with_ties=True)
  - pt.agg(df, by=_UNSET, *args, a=None, dropna=False, observed=True, **kwargs)
  - pt.long(df, cols=None, id_vars=None, c="variable", v="value")
  - pt.wide(df, c="variable", v="value", index=None)
  - pt.pivot(df, r=None, c=None, v=None, a="sum", dropna=False, fill_value=None)
  - pt.sql(df, query, **frames)
  - pt.handle_missing(df, fillna=".", numeric_fill=0, cols=None, preserve_categories=True)
  - pt.cols(df, ascending=True)
  - pt.glimpse(df, width=None)
  - pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False)
  - pt.replace_values(df, v: dict, c=None, exact=True)
  - pt.safe_reset_index(df)
  - pt.sample(name)
  - pt.sample_data (Mapping of bundled datasets)
  - pt.Plotter (lazy loaded when matplotlib is installed)
  - pt.plot(df, *args, **kwargs)
  - pt.finalize(plotter=None, **kwargs)

DataFrame Accessor (`df.pt`):
  Importing pytae automatically registers the `.pt` accessor on `pd.DataFrame`.
  Methods on `df.pt`:
    df.pt.select(...)
    df.pt.qry(...)
    df.pt.mutate(...)
    df.pt.arrange(...)
    df.pt.slice_max(...)
    df.pt.slice_min(...)
    df.pt.agg(...)
    df.pt.long(...)
    df.pt.wide(...)
    df.pt.pivot(...)
    df.pt.sql(...)
    df.pt.handle_missing(...)
    df.pt.cols(...)
    df.pt.glimpse(...)
    df.pt.clean_columns(...)
    df.pt.replace_values(...)
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

4.1. pt.qry() / df.pt.qry() — Row Filtering
--------------------------------------------------------------------------------
Filters DataFrame rows based on keyword arguments, string expressions, 
plain dictionaries, or any combination of the three.

Signature:
  pt.qry(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pd.DataFrame
  df.pt.qry(*args: Any, **kwargs: Any) -> pd.DataFrame

Calling Styles:
  1. Keyword Arguments:
     df.pt.qry(species="Adelie", body_mass_g="> 5000")
  2. String Expressions (matches CLI -qry):
     df.pt.qry("body_mass_g > 5000, species = 'Adelie'")
     df.pt.qry("bill length mm > 40")   # Handles columns with spaces natively!
  3. Plain Dictionaries:
     df.pt.qry({"bill length mm": "> 40", "species": "Adelie"})
  4. Mixed Calling:
     df.pt.qry("bill length mm > 40", {"island": "Biscoe"}, species="Gentoo")
  5. Functional Style:
     pt.qry(penguins, species="Adelie")

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
  - Null Checks (unary 1-element tuples):
    Missing values:      sex=("isna",)
    Non-missing values:  sex=("notna",)

Multiple Conditions on the Same Column:
  Python kwargs cannot repeat parameter names. Solve this using:
  1. Comma-separated string:  df.pt.qry("bill_length_mm > 40, bill_length_mm < 50")
  2. Multiple string args:    df.pt.qry("bill_length_mm > 40", "bill_length_mm < 50")
  3. Interval syntax:         df.pt.qry(bill_length_mm="[40,50)")
  4. Chained calls:           df.pt.qry(bill_length_mm="> 40").pt.qry(bill_length_mm="< 50")

Error Handling:
  If a column name is misspelled, qry() raises a KeyError with fuzzy match suggestions:
  KeyError: "unknown column 'speceis' (did you mean 'species'?)"


4.2. pt.mutate() / df.pt.mutate() — Column Creation & Feature Engineering
--------------------------------------------------------------------------------
Creates or overwrites columns using expressions evaluated in order via pandas eval() 
with automatic fallback to plain Python eval on Series objects.

Signature:
  pt.mutate(
      df: pd.DataFrame,
      *args: Any,
      by: str | Sequence[str] | None = None,
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

Comprehensive Feature Set (The 10 Mutate Capabilities):
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
     Recodes values through a mapping dictionary with optional default fallback:
     df.pt.mutate(code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE'}, default='OTHER')")
  7. Caller Scope Variables (`@var`):
     Reference local variables from caller scope using `@name`:
     threshold = 4000
     df.pt.mutate(heavy="body_mass_g >= @threshold")
     Or pass explicitly via params:
     df.pt.mutate(heavy="body_mass_g >= @threshold", params={"threshold": 4000})
     (Note: In CLI, `@var` gives a helpful error explaining that caller scopes exist only in Python).
  8. Columns With Spaces (`[col]` or `` `col` ``):
     Enclose spaced column names in brackets `[body mass g]` or backticks:
     df.pt.mutate(ratio="[body mass g] / [bill length mm]")
  9. Grouped Window Transforms (`by=`, `dropna=False`, `observed=True`):
     Evaluates aggregations per group and broadcasts back to each row without collapsing rows (N -> N):
     - Injected Aggregations: mean(x), sum(x), median(x), min(x), max(x), std(x), var(x), n (or n())
     - Example:
       df.pt.mutate("avg_mass = mean(body_mass_g), diff = body_mass_g - avg_mass, group_size = n", by="species")
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
        Notice: Because `mutate()` executes sequentially, `row["mass_kg"]` is immediately
        accessible inside `classify(row)`!
   11. Literal Constants with `pt.lit()` (Python API):
       In `mutate()`, all string arguments are evaluated as formulas/column expressions,
       never as string literals:
       - If you write `source="tag"`, pytae looks for a column named `tag` and raises
         `KeyError: name 'tag' is not defined` if it does not exist.
       - If a column named `original` exists, `source="original"` silently copies that column!
       To assign a literal constant value in Python kwargs without awkward nested quotes
       (`source="'tag'"`), use `pt.lit()` (matching Polars `pl.lit` and PySpark `lit`):
       ```python
       df.pt.mutate(source=pt.lit("tag"), status=pt.lit("active"))
       ```
       Important Notes on where `pt.lit()` is **NOT** needed:
       - **Inside expressions/conditionals (`if_else`, `case_when`, `coalesce`)**: `pt.lit()` is
         **not relevant**. Inside string formulas, standard inner single quotes `'...'` already
         unambiguously distinguish string literals from column names:
         `df.pt.mutate(size="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')")`.
       - **In the CLI**: `pt.lit()` is **never needed in the CLI**. In terminal commands, standard
         inner single quotes already define string literals: `-mutate "source = 'original'"`.
       `pt.lit()` marks the value as an explicit literal constant in Python calls and is unwrapped
       directly inside `mutate()` without evaluating against DataFrame columns.


4.3. pt.select() / df.pt.select() — Column Selection, Slicing & Exclusion
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
  - regex: Regex pattern matching column names.
    df.pt.select(regex=r"^bill")
    df.pt.select("species", regex=r"mm$")
    IMPORTANT: Regex must be specified via `regex=...`. A positional string containing 
    regex characters like "^bill" is treated as an exact name and raises a KeyError!
  - contains: Substring(s) in column names (OR if list).
    df.pt.select(contains="mm")
    df.pt.select(contains=["bill", "mass"])
  - startswith: Prefix(es) in column names.
    df.pt.select(startswith="bill")
  - endswith: Suffix(es) in column names.
    df.pt.select(endswith="mm")
  - dtype: Include columns by dtype shorthand or type.
    Shorthands: 'numeric', 'datetime', 'category', 'bool'
    df.pt.select(dtype="numeric")
  - exclude_dtype: Exclude columns by dtype. Cannot be combined with other criteria.
    df.pt.select(exclude_dtype="numeric")      # keep non-numeric
    df.pt.select(exclude_dtype="non_numeric")  # keep numeric

Column Order Rules:
  Explicitly listed column names preserve YOUR specified order.
  Columns pulled in by contains, regex, or everything() follow original DataFrame order.


4.4. pt.arrange() / pt.slice_max() / pt.slice_min() — Sorting & Group Slicing
--------------------------------------------------------------------------------
Reorder rows or extract extreme records per group.

Signatures:
  pt.arrange(df: pd.DataFrame, *cols: str | Sequence[str], ascending: bool | Sequence[bool] | None = None, na_last: bool = True) -> pd.DataFrame
  pt.slice_max(df: pd.DataFrame, col: str, n: int = 1, *, by: str | Sequence[str] | None = None, with_ties: bool = False, na_last: bool = True) -> pd.DataFrame
  pt.slice_min(df: pd.DataFrame, col: str, n: int = 1, *, by: str | Sequence[str] | None = None, with_ties: bool = False, na_last: bool = True) -> pd.DataFrame

Calling Styles:
  # arrange: ascending (default), descending ("desc" or "-col"), bracketed for spaces
  df.pt.arrange("species", "body_mass_g desc")
  df.pt.arrange("species, -body_mass_g")
  df.pt.arrange("[bill length mm] desc")

  # slice_max / slice_min: top/bottom N rows overall or by group
  df.pt.slice_max("body_mass_g", n=3)
  df.pt.slice_min("body_mass_g", n=1, by="species")


4.5. pt.agg() / df.pt.agg() — Grouped Aggregation
--------------------------------------------------------------------------------
Aggregates numeric columns grouped by explicit `by=` column(s) (or `None` for a 
whole-table grand total summary). Supports string mapping specifications with bracketed 
columns `[col]` (matching CLI `-agg`), keyword arguments, or whole-frame aggregations.

Signature:
  pt.agg(
      df: pd.DataFrame,
      by: str | Sequence[str] | None = _UNSET,
      *args: Any,
      a: str | list[str] | None = None,
      dropna: bool = False,
      observed: bool = True,
      **kwargs: Any,
  ) -> pd.DataFrame

Calling Styles:
  1. String Mapping Specification (Zero Dict Unpacking! Perfect for Spaced Columns):
     df.pt.agg("smoker", "tip = mean, [total bill] = mean, n = n")
     df.pt.agg("smoker", "tip = mean", "[total bill] = mean", "n = n")
     df.pt.agg("[smoker status]", "[avg bill] = [total bill]:mean, [total count] = n")
  2. Whole-Frame Aggregation:
     df.pt.agg("species", "mean")                  # applies mean to all numeric cols
     df.pt.agg(["species", "island"], ["mean", "sum", "n"]) # multi-column grouping
     df.pt.agg(None, a=["mean", "n"])              # whole-table summary (1 row)
  3. Specific Column Aggregations (kwargs):
     df.pt.agg("species", body_mass_g="mean", flipper_length_mm="max", n="n")
     df.pt.agg("species", body_mass_g=["mean", "sum"], row_count="n")

Key Rules & Behaviors:
  - `by` is REQUIRED in the Python Library:
    In Python, `by` must be passed as the first positional argument or via `by=...` / `group_by=...`.
    To perform a whole-table summary (grand total, 1 row), explicitly pass `by=None`.
    (In CLI, `-by` is optional—omitting `-by` defaults to a whole-table summary).
  - Multi-Column Grouping:
    Pass as list `by=["species", "island"]` or comma-separated string `by="species,island"`.
  - NO REDUNDANT SELECT:
    You NEVER need a `pt.select(...)` or `-select` before `agg()`. Target columns and aggregation
    functions are declared directly inside `agg`:
    # GOOD:
    df.pt.agg("species", body_mass_g="mean")
    # REDUNDANT (discouraged):
    df.pt.select("species", "body_mass_g").pt.agg("species", body_mass_g="mean")
  - Row Count ('n'):
    Assigning a key with value 'n' produces the group row count.
    If the key is `n="n"`, the count column is named `n`.
    If the key is `count="n"`, the count column is named `count`.
  - Column Names:
    If a single aggregation is applied to a column, its original name is preserved:
    `body_mass_g='mean'` -> output column: `body_mass_g`
    If multiple aggregations are applied to a column, names become `{col}_{agg}`:
    `body_mass_g=['mean', 'max']` -> output columns: `body_mass_g_mean`, `body_mass_g_max`
  - Group Counts Only:
    If the DataFrame has no numeric columns and only 'n' is requested, it returns 
    the frequency counts of the groups.
  - dropna Default:
    `dropna=False` by default preserves missing category groups across aggregations.


4.6. pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
--------------------------------------------------------------------------------
Pure structural reshaping between long and wide formats without aggregation.

pt.long(df, cols=None, id_vars=None, c="variable", v="value"):
  Melts columns to rows. If cols is None, melts all numeric columns, keeping 
  non-numeric columns as ID variables.
  Parameters:
    cols: Column(s) to melt to rows. Can be string or list/tuple of strings.
          Supports bracketed multi-word column names `[col name]`.
    id_vars: Identifier column(s) to keep as rows.
    c: column name for melted metric names (default: "variable")
    v: column name for melted metric values (default: "value")
  Example:
    tall = df.pt.long(c="metric", v="measurement")

pt.wide(df, c="variable", v="value", index=None):
  Pivots long-format records back into column headers (exact reverse of pt.long).
  Strictly 1-to-1 without aggregation.
  Parameters:
    c: column whose unique values become headers (default: "variable")
    v: column containing values (default: "value")
    index: explicit row identifier column(s). If None, all columns except `c` and `v` are used.
  Rules:
    - Requires unique (index, c) pairs. If duplicate keys exist, raises ValueError
      guiding the user to use pt.pivot() instead.
    - c and v cannot be the same column.
    - If all columns are partitioned into `c` and `v` (no id columns), wide() reshapes cleanly.
  Example:
    wide = tall.pt.wide(c="metric", v="measurement")


4.7. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
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
      fill_value: Any = None,
  ) -> pd.DataFrame
  df.pt.pivot(r=None, c=None, v=None, a="sum", dropna=False, fill_value=None) -> pd.DataFrame

Parameters:
  r: Row grouping column(s). String (e.g. "island", "species,island") or list of strings.
     Aliases: index=, rows=, row=, by=
  c: Column dimension(s). String (e.g. "sex") or list of strings.
     Aliases: columns=, cols=, col=
  v: Value column(s) to aggregate. Optional when counting (a="n").
     Aliases: values=, value=, val=, vals=
  a: Aggregation function (default: "sum"). Supports standard aggregations
     ("mean", "sum", "median", "min", "max", "std", "var") and "n" (or "size") for row counts.
     Aliases: agg=, aggfunc=
  dropna: Whether to drop NA categories in row/column keys (default: False).
  fill_value: Scalar value for missing grid intersections. For a="n", defaults to 0.

Key Features & Conventions:
  - 1D Flat Headers: Multi-column pivots format headers cleanly (e.g. "MALE_2007", "FEMALE_2007").
  - Pure Integer Counts: Row counts (a="n") return standard int64 (or Int64) integers, not floats.
  - Zero Count Fill: Missing grid combinations in frequency tables default to 0.
  - Omit v for Counts: For frequency cross-tabulations (a="n"), v is optional.
  - RangeIndex: Index is always reset to 0, 1, 2, ... with no lingering MultiIndex.
  - No Cartesian Products: Unobserved groupings across MultiIndexes are cleanly filtered without
    generating artificial Cartesian product rows.

Examples:
  # 2D summary matrix
  df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")

  # Frequency cross-tabulation (count rows across dimensions)
  df.pt.pivot(r="island", c="species", a="n")

  # Multi-dimensional pivot with custom fill
  df.pt.pivot(r=["species", "island"], c="sex", v="body_mass_g", a="median", fill_value=0)


4.8. pt.sql() / df.pt.sql() — DuckDB SQL Engine
--------------------------------------------------------------------------------
Executes SQL queries directly over in-memory DataFrames using DuckDB.
Requires: pip install 'pytae[sql]'

Signature:
  pt.sql(df: pd.DataFrame, query: str, **frames: pd.DataFrame) -> pd.DataFrame
  df.pt.sql(query: str, **frames: pd.DataFrame) -> pd.DataFrame

Rules & Features:
  - Table 'data': The current/calling DataFrame is automatically registered as table `data`.
  - Joining Extra DataFrames: Additional DataFrames can be passed as keyword arguments:
    pt.sql(orders, "select * from data join cust using (cust_id)", cust=customers)
  - Columns with Spaces: Supported using double quotes `"col a"`, brackets `[col a]`, 
    or backticks `` `col a` `` in the SQL query:
    df.pt.sql('select [bill length mm], avg(body_mass_g) from data group by 1')
  - Query From File: Pass an external SQL file path prefixed with `@`:
    df.pt.sql("@analysis.sql")


4.9. Other Utilities
--------------------------------------------------------------------------------
- pt.cols(df, ascending=True):
  Returns list of column names.
  ascending=True  -> Alphabetical A-Z
  ascending=False -> Alphabetical Z-A
  ascending=None  -> Original DataFrame file order

- pt.glimpse(df, width=None) / df.pt.glimpse(width=None):
  Prints a transposed overview of DataFrame columns, dtypes, and inline sample values
  (inspired by dplyr::glimpse and Polars). Returns the DataFrame for non-destructive method chaining:
  `df.pt.qry("sales > 100").pt.glimpse().pt.select("region", "sales")`

- pt.handle_missing(df, fillna=".", numeric_fill=0, cols=None, preserve_categories=True):
  Sanitizes missing values with type-safe defaults:
  - Categorical columns: preserves categorical dtype (`preserve_categories=True`) and fills missing categories.
  - String/object columns: fills NaN with `fillna` (default '.') and strips whitespace.
  - Numeric columns: fills NaN with `numeric_fill` (default 0; can also be "mean", "median", or None).
  - Specific columns: pass `cols=["col1", "col2"]` to target specific subsets.

- pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False):
  Systematically sanitizes DataFrame column header names in fixed order:
  strip:          trim leading/trailing whitespace
  strip_special:  remove characters other than alphanumeric, underscore, whitespace, or fill
  squeeze:        collapse multi-space runs into single spaces
  fill:           replace whitespace characters with this string (e.g. "_")
  case:           'lower', 'upper', or 'proper' (Title Case)
  dedupe:         auto-number duplicates (e.g. 'rev', 'rev_1', 'rev_2')

- pt.replace_values(df, v: dict, c: str | list | None = None, exact=True):
  Replaces cell values in the DataFrame (wraps pandas replace).
  v:      dictionary of {old_value: new_value}
  c:      scoped column name or list of columns (default None = entire DataFrame)
  exact:  True = exact match of cell value; False = substring replacement (regex)

- pt.safe_reset_index(df) / df.pt.safe_reset_index():
  Safely resets DataFrame index, raising an informative ValueError if an index level name collides
  with an existing column to prevent ambiguous duplicate headers.

- df.to_clip() / s.to_clip() / df.pt.to_clip():
  Copies DataFrame or Series to system clipboard as tab-separated values without index.
  Attached directly to pd.DataFrame and pd.Series on import pytae (also accessible via df.pt.to_clip()).


4.10. Plotter — Visualization & Dashboarding (Plotting API)
--------------------------------------------------------------------------------
Method-chainable plotting system wrapping `pandas.plot` and `matplotlib`.
Requires: pip install 'pytae[plot]'

Key Concepts:
  - Clean Separation of Concerns (Path A — No In-Plot Aggregation):
    Plotter plots data directly without performing aggregation.
    Summarize first with `df.pt.agg()` or `df.pt.pivot()`:
    tips_avg = tips.pt.agg("day,sex", total_bill="mean")
    pt.plot(tips_avg, kind="bar", x="day", y="total_bill", by="sex").finalize()
  - Accessor & Functional Shortcuts:
    tips.pt.agg("day,sex", total_bill="mean").pt.plot(kind="bar", x="day", y="total_bill", by="sex", palette="tab10")
    pt.finalize(title="Average Bill by Day")
  - Method Chaining Pattern:
    k = pt.Plotter(figsize=(6, 4))
    (k
     .data(penguins)
     .plot(kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="Set1")
     .finalize(title="Bill Dimensions")
    )
    k.fig  # access matplotlib figure
  - Wide Data Plotting (Optional y):
    Plot multiple metrics directly from wide tables without melting:
    wide_data.pt.plot(kind="barh", x="category")
  - Box Plots (True Unaggregated Quartiles):
    pt.Plotter(penguins).plot(kind="box", x="species", y="body_mass_g", palette="Set1").finalize()
  - Heatmap Matrix:
    corr = penguins.select_dtypes("number").corr()
    pt.Plotter(corr).plot(kind="heatmap", annot=True, fmt=".2f", cmap="coolwarm", title="Correlation").finalize()
  - Multi-Panel Dashboards (Mosaic Layouts):
    mosaic = '''
    AB
    CD
    '''
    k = pt.Plotter(mosaic, figsize=(10, 8))
    (k
     .data(penguins).plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species")
     .data(tips.pt.agg("day", total_bill="mean")).plot(on="B", kind="bar", x="day", y="total_bill")
     .finalize(consolidate_legends=True)
    )
  - Secondary Y-Axis ('^'):
    Append `^` to panel name (e.g. `on="A^"` or `secondary_y=True`) to create a secondary y-axis:
    (k
     .plot(kind="bar", x="day", y="total_bill", on="A", color="skyblue")
     .plot(kind="line", x="day", y="tip", secondary_y=True, color="crimson")
     .finalize()
    )
  - Small Multiples / Auto-Faceting:
    pt.plot(penguins, by="species", ncols=3, kind="scatter", x="bill_length_mm", y="bill_depth_mm").finalize()
    pt.Plotter.facet(df, by="species", ncols=2, kind="scatter", x="bill_length_mm", y="bill_depth_mm")
  - Post-Processing (`pt.finalize` / `plotter.finalize`):
    Accepts: `title`, `xlabel`, `ylabel`, `style` (matplotlib style sheet name), `consolidate_legends=True`, `tight_layout=True`.
  - Saving:
    k.save("chart.png", dpi=300)


5. CLI REFERENCE (COMMAND LINE INTERFACE)
--------------------------------------------------------------------------------

5.1. Execution Model & Pipeline Architecture
--------------------------------------------------------------------------------
The CLI command `pytae` processes operations sequentially in the order given on 
the command line:
  pytae input.parquet -qry "body_mass_g > 3000" -mutate "mass_kg = body_mass_g / 1000" -head 5

Pipeline Rules:
1. Input Source: The first unflagged argument is the input file path, or 'clip'
   to ingest tabular data directly from the system clipboard. When data is piped via STDIN
   (e.g. `cat data.csv | pytae -head 5`), pytae auto-detects the stream without requiring an explicit
   path or `-`. (In `-file` multi-file mode, `-file` replaces the positional path).
2. Sequential Mutation: Each operation transforms the intermediate dataset in memory.
   For example, `-qry` before `-select -col` allows filtering on a column that is subsequently excluded.
3. Final Operation Determines Output: Only the last operation in the chain prints or exports, 
   unless an intermediate operation explicitly writes to disk.
4. Shell Quoting: Always quote multi-word arguments and expressions in your shell.


5.2. File Formats & Zero-Cost Metadata Inspection
--------------------------------------------------------------------------------
Supported input & output file types:
  - .parquet, .pq (columnar storage)
  - .csv (comma-delimited text)
  - .tsv (tab-delimited text)
  - .txt (tab-delimited text or custom delimiter)
  - .dat (pipe-delimited text, latin-1 encoding)
  - .jsonl, .ndjson (line-delimited JSON records)
  - .csv.gz, .txt.gz, .dat.gz, .jsonl.gz (transparent gzip compression & decompression)
  - .sas7bdat (SAS binary dataset, read-only)

Fast Zero-Cost Inspection (Metadata-Only):
  For Parquet and SAS7BDAT, the following flags inspect metadata without reading 
  the full file rows into RAM:
  - `-shape`: Returns (rows, columns)
  - `-cols`: Prints column names in order
  - `-dtype`: Shows data types
  - `-head [N]`: Reads only the first N rows from the file stream
  - `-meta`: Displays complete zero-scan Parquet metadata (row groups count, 
    column compression codecs, compression ratio, Arrow & Pandas schema) 
    without loading table records.


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
  -glimpse              Transposed column overview with dtypes and sample values (like dplyr/Polars)
  -meta                 Display zero-scan Parquet metadata (row groups, schema, compression)
  -diff PATH            Compare schema, shape, null counts, and cell values against another file
  -value_counts         Value counts for categorical/string columns (honors dropna in specs)
  -dedupe [COLS]        Drop duplicate rows across all or specified columns
  -sample [N]           Random sample of N rows (default 5)
  -seed N               Random seed for sampling
  -frac P               Sample fraction P (0.0 < P <= 1.0)
  -nrows, -limit N      Limit reading to first N rows of file
  -arrange SPEC         Sort rows by columns: e.g. -arrange "col1, col2 asc", -arrange "col1 desc", or -arrange "-col1"

In-Terminal ASCII Visualizations:
  -freq COL             Render horizontal frequency distribution bars with counts & percentages
  -hist COL[:BINS]      Render in-terminal distribution histogram for a numeric column (default: 10 bins)

Row Filtering & Slicing Flags:
  -qry CONDITIONS       pytae filter expressions (e.g. "species='Adelie', body_mass_g > 3500")
  -dropna [COLS]        Drop rows containing NaN (bare for all columns, or comma-separated columns)
  -slice_max SPEC       Extract top N rows by column (e.g. "body_mass_g:3"), group-aware with -by
  -slice_min SPEC       Extract bottom N rows by column (e.g. "body_mass_g:1"), group-aware with -by

Column Transformation Flags:
  -select SPEC          Select columns (names, slices 'a:b', contains, dtypes, negative '-col', '~col', exclude=)
  -mutate SPEC          Create/overwrite columns ("new_col = expression")
  -rename OLD:NEW,...   Rename columns using ':' delimiter (e.g. "a:alpha, b:beta")
  -replace_values SPEC  Replace values: "v='old:new', c='col', exact=True"
  -clean_columns SPECS  Clean headers: "strip=True, fill='_', case='lower', dedupe=True"
  -handle_missing [VAL] Impute missing values with type-safe defaults (default: '.')

Aggregation & Reshaping Flags:
  -by, -group_by COLS   Grouping columns for -agg, -mutate, -slice_max, -slice_min (e.g. -by species -agg mean)
  -agg [SPECS]          Aggregate columns (e.g. -by species -agg "body_mass_g=mean, count=n" or -agg mean).
                        When -by is omitted, -agg computes a whole-table summary!
  -long [SPECS]         Melt numeric columns to rows: "c=variable, v=value"
  -wide [SPECS]         Pure 1-to-1 unmelting into headers: "c=variable, v=value"
  -pivot SPECS          2D pivot table: "r=species, c=island, v=body_mass_g, a=mean" (or counts: "r=species, c=island, a=n")

SQL & Multi-File Flags:
  -sql QUERY            Run DuckDB SQL on table 'data' (or @query.sql)
  -file SPECS           Multi-file mode: "file1.parquet=df1; file2.csv=df2"
  -merge SPECS          Join files: "left=df1, right=df2, on=id, how=inner"
  -concat SPECS         Stack files: "frames='df1,df2'"

Plotting Flags (CLI Visualization):
  -plot SPEC            Render chart using pytae Plotter; e.g. -plot "kind=scatter, x=col1, y=col2"
  -finalize SPEC        Layout/legend options for -plot, e.g. -finalize "consolidate_legends=True, style=True"

Output & Formatting Flags:
  -o TARGET             Output destination: file path (.csv, .parquet, .jsonl, .csv.gz, etc.),
                        format for in-place or batch conversion ('csv', 'parquet', 'txt', 'dat',
                        'jsonl', 'csv.gz', 'jsonl.gz'), or 'clip'/'clipboard'
  -out_dir, -od DIR     Target directory for exported files (created if missing; requires -o)
  -fmt FORMAT           Input format when reading from STDIN or extensionless files (csv, parquet, jsonl, txt, tsv)
  -dlim CHAR            Delimiter character for input/output text files
  -encoding ENC         File encoding (e.g. utf-8, latin-1)
  -pretty               Pretty-print tables with bordered markdown formatting
  -pager                Pipe table or inspect outputs through system pager ($PAGER or less)
  -round N              Round numeric output columns to N decimal places
  -progress [N]         Show row-reading/writing progress (default: 200,000 rows per chunk)


5.4. In-Terminal Visualizations (-freq, -hist)
--------------------------------------------------------------------------------
Inspect distributions instantly in the terminal without opening a browser or GUI:

1. Horizontal Frequency Bars (-freq):
   pytae penguins.parquet -freq species
   Output:
   species
   Adelie     152 (44.2%)  ████████████████████████████████████████
   Gentoo     124 (36.0%)  ████████████████████████████████
   Chinstrap   68 (19.8%)  █████████████████

2. In-Terminal Distribution Histogram (-hist):
   pytae penguins.parquet -hist body_mass_g:8
   Output:
   body_mass_g (8 bins)
   [2700.0, 3150.0)    64 (18.7%)  ████████████████
   [3150.0, 3600.0)    71 (20.8%)  ██████████████████
   [3600.0, 4050.0)    65 (19.0%)  ████████████████
   [4050.0, 4500.0)    37 (10.8%)  █████████
   [4500.0, 4950.0)    36 (10.5%)  █████████
   [4950.0, 5400.0)    46 (13.5%)  ███████████
   [5400.0, 5850.0)    19  (5.6%)  ████
   [5850.0, 6300.0]     4  (1.2%)  █


5.5. Quoting & Delimiter Standards (: vs =)
--------------------------------------------------------------------------------
pytae enforces strict delimiters depending on the semantic meaning:

1. Mapping / Translation uses COLON (`:`):
   - `-rename`: "old_col:new_col, col_b:col_beta"
   - `-replace_values`: "v='old_val:new_val', c='col_name'"
   Rule: Old is mapped to New via `:`.

2. Assignment / Specification uses EQUALS (`=`):
   - `-mutate`: "new_col = expression, mass_kg = body_mass_g / 1000"
   - `-qry`: "species = 'Adelie', body_mass_g > 3500"
   - `-clean_columns`: "strip=True, fill='_', case='lower'"
   - `-merge`: "left=df1, right=df2, on=id, how=left"
   - `-agg`: "tip=mean, total_bill=mean, n=n"

Quoting Rules:
- String literals in expressions require quotes: `species = 'Adelie'`.
- Column names inside expressions must remain unquoted so they resolve as variables:
  `mass_kg = body_mass_g / 1000` (NOT `'body_mass_g' / 1000`).
- Column names containing spaces must use brackets `[col]` or backticks `` `col` ``.


5.6. Multi-File Operations (-file, -merge, -concat, -sql)
--------------------------------------------------------------------------------
When operating across multiple files, `-file` replaces the positional file path:

Syntax:
  pytae -file "PATH=ALIAS; PATH=ALIAS" -merge ...

1. Joining Files (-merge):
   pytae -file "orders.parquet=ord; customers.csv=cust" \\
         -merge "left=ord, right=cust, on=cust_id, how=inner" \\
         -select "order_id,cust_name,amount" -head 10

   Joining on differing column names:
   -merge "left=df1, right=df2, on='left_id:right_id', how=left"

   Joining multiple files in sequence ('df' represents previous merge result):
   pytae -file "a.csv=a; b.csv=b; c.csv=c" \\
         -merge "left=a, right=b, on=id" \\
         -merge "left=df, right=c, on=id"

2. Stacking Files (-concat):
   pytae -file "jan.csv=m1; feb.csv=m2; mar.csv=m3" \\
         -concat "frames='m1,m2,m3'" -shape

3. SQL Across Multiple Files:
   pytae -file "orders.parquet=ord; customers.csv=cust" \\
         -sql "select ord.id, cust.name, ord.total from ord join cust using (cust_id)"


5.7. Batch Processing, Conversions & Clipboard (-o)
--------------------------------------------------------------------------------
Convert files between formats with zero python code via -o:
  # Convert parquet to CSV
  pytae penguins.parquet -o penguins.csv

  # In-place conversion (saves penguins.csv next to penguins.parquet)
  pytae penguins.parquet -o csv

  # Batch convert all parquet files in a directory to CSV
  pytae 'data/*.parquet' -o csv

  # Filter and save to parquet
  pytae penguins.parquet -qry "body_mass_g > 4000" -o heavy_penguins.parquet

  # Copy to clipboard directly without printing to terminal
  pytae penguins.parquet -head -o clip


6. FREQUENTLY ASKED QUESTIONS, PITFALLS & SYNTAX RULES
--------------------------------------------------------------------------------

6.1. Why is `-select` before `-agg` redundant?
---------------------------------------------
In pytae, both the library `agg()` and CLI `-agg` directly declare the target columns 
and their desired aggregations. Writing a redundant `select` or `-select` before `agg` 
wastes an intermediate DataFrame transformation:
  # REDUNDANT:
  pytae penguins.parquet -select "species,body_mass_g" -by species -agg mean -round 1
  df.pt.select("species", "body_mass_g").pt.agg("species", body_mass_g="mean")

  # CLEAN & IDIOMATIC:
  pytae penguins.parquet -by species -agg body_mass_g=mean -round 1
  df.pt.agg("species", body_mass_g="mean")

6.2. Why is `by` required in `pt.agg()` but optional in CLI (`-by`)?
----------------------------------------------------------------------
- In Python library: `pt.agg(df, by, ...)` enforces explicit intent. Pass `by="species"` 
  for grouped aggregations, or explicitly pass `by=None` for a whole-table summary (1 row). 
  This prevents accidental whole-table collapses when a user forgets to pass grouping columns.
- In CLI: Command flags are composable. If `-by` is omitted, `pytae input.parquet -agg mean` 
  cleanly interprets the command as a whole-table grand total.

6.3. How do I apply custom functions in `mutate()`?
---------------------------------------------------
1. Vectorized Functions (Series -> Series): Call directly in expression strings:
   def ratio(a, b): return a / b
   df.pt.mutate(r="ratio(bill_length_mm, bill_depth_mm)")

2. Single-Column Scalar Functions (element -> element): Call Series `.apply()` in expressions:
   def clean_text(s): return s.strip().lower()
   df.pt.mutate(clean="species.apply(clean_text)")

3. Row-Wise Multi-Column Functions (row -> value): Pass a DataFrame lambda with `df.apply(fn, axis=1)`:
   def classify(row):
       if row["species"] == "Gentoo" and row["mass_kg"] > 5.0: return "Giant"
       return "Standard"
   df.pt.mutate(
       mass_kg="body_mass_g / 1000",
       tier=lambda df: df.apply(classify, axis=1),
   )

6.4. Can row-level functions access newly created columns in the same `mutate()`?
---------------------------------------------------------------------------------
YES! Because `mutate()` processes arguments in order from left to right, earlier mutations 
are immediately attached to the DataFrame. Your row function will see newly created columns 
(e.g. `row["mass_kg"]`) with zero errors.

6.5. Why does `df.pt.mutate(col=my_func)` fail when `my_func` expects a row?
----------------------------------------------------------------------------
When a callable is passed directly as `mutate(col=fn)`, `mutate` passes the **entire DataFrame** 
to `fn` (`fn(df)`). Inside a row-level function, `row["species"] == "Gentoo"` produces a 
boolean Series, raising: `ValueError: The truth value of a Series is ambiguous`. 
To run a row-level function, write: `lambda df: df.apply(my_func, axis=1)`.

6.6. What is the difference between `wide()` and `pivot()`?
-----------------------------------------------------------
- `wide()` is strictly for pure 1-to-1 structural unmelting (reversing `long()`) with NO aggregation. 
  It raises a `ValueError` if duplicate `(index, c)` keys exist.
- `pivot()` is the full 2D aggregation engine. It summarizes data across row (`r`) and column (`c`) 
  dimensions using an aggregation function `a` (or counts `a="n"`), returning a flat RangeIndex table.

6.7. How do negative column exclusions work in `select()` and CLI `-select`?
----------------------------------------------------------------------------
- In Library: Pass negative prefixes `pt.select(df, "-species", "-island")`, slice negations 
  `"-start:end"`, or keyword `exclude=["species", "island"]`.
- In CLI: Pass `-select "-species, -island"` or `-select "exclude=species,island"`.
- If only exclusions are given, pytae starts with all columns and drops the specified exclusions.

6.8. How do columns with spaces work across expressions?
--------------------------------------------------------
- In `qry()`: Handled natively in strings: `df.pt.qry("bill length mm > 40")`.
- In `mutate()` / expressions: Enclose in brackets `[col name]` or backticks `` `col name` ``:
  `df.pt.mutate(ratio="[body mass g] / [bill length mm]")`.
- In kwargs: Python syntax prohibits spaces in keyword arguments. Use dictionary unpacking:
  `df.pt.mutate(**{"body mass kg": "body_mass_g / 1000"})`.

6.9. Why did `-sort` or `-sort_by` fail? (Use `-arrange`)
--------------------------------------------------------
Pytae standardizes strictly on `-arrange` for row ordering across both the Python library 
and CLI to follow the "one and only one right way" philosophy.
Use `-arrange SPEC`, e.g. `pytae data.parquet -arrange "body_mass_g desc"`, 
`-arrange "-body_mass_g"`, or `-arrange "species, [bill length mm] asc"`.

6.10. How do I inspect metadata without reading data into RAM?
--------------------------------------------------------------
For Parquet files, use `-meta` to inspect row groups, schema, and compression codecs in 
sub-milliseconds without loading table data. Flags like `-shape`, `-cols`, `-dtype`, and 
`-head` also read purely from metadata headers for Parquet and SAS7BDAT.

6.11. How do I assign literal constants in `mutate()`? (Use `pt.lit()`)
----------------------------------------------------------------------
Because `mutate()` evaluates string keyword arguments as formulas via `pandas.eval()`, 
bare words are always interpreted as column references:
- If no column exists with that name (e.g. `df.pt.mutate(source="active")`), it raises 
  `KeyError: name 'active' is not defined`.
- If a column already exists with that name (e.g. `df.pt.mutate(source="original")`), 
  it silently copies that existing column into `source`.

In both cases, `source="word"` does not assign the string literal `"word"`.

To assign an explicit literal constant:
1. In Python kwargs: `df.pt.mutate(source=pt.lit("active"))`
   - Clean, linter/IDE-friendly, and avoids awkward nested quotes like `source="'active'"`.
   - Follows standard DataFrame conventions (like Polars `pl.lit` or PySpark `lit`).
2. Where `pt.lit()` is **NOT** needed:
   - **Inside formula expressions / conditional helpers (`if_else`, `case_when`, `coalesce`)**: `pt.lit()` is
     **completely irrelevant**. Standard inner single quotes `'...'` already distinguish string literals
     from column references: `df.pt.mutate(size="if_else(x > 10, 'Heavy', 'Standard')")`.
   - **In the CLI**: `pt.lit()` is **never needed in the CLI**. Standard inner single quotes denote string literals:
     `pytae data.parquet -mutate "source = 'original'"`

`pt.lit()` marks the value as a literal constant in Python calls and is unwrapped directly without column evaluation.


7. END-TO-END RECIPES & EXAMPLES
--------------------------------------------------------------------------------

Recipe 1: Master Mutate Recipe (All 11 Capabilities in One Pipeline)
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
    .pt.mutate(
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
        
        # 9. Grouped window transforms via by= without collapsing rows
        species_avg_mass="mean(mass_kg)",
        mass_diff="mass_kg - species_avg_mass",
        group_size="n",
        
        # 10a. DataFrame lambda
        is_large=lambda df: (df["mass_kg"] > 4.0) & (df["bill_ratio"] > 2.5),
        
        # 10b. Row-level function via lambda df: df.apply(..., axis=1)
        category=lambda df: df.apply(classify_penguin, axis=1),
        
        # 11. Literal constant via pt.lit() (prevents accidental column copying or undefined errors)
        analysis=pt.lit("species"),
        
        by="species",
    )
)
```

Recipe 2: Grouped Aggregation & 2D Pivots (Python & CLI)
--------------------------------------------------------------------------------
```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Clean grouped aggregation (no redundant select!)
agg_summary = penguins.pt.agg("species,island", mass_mean="body_mass_g:mean", count="n")

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

Recipe 3: DuckDB SQL Query on DataFrame
--------------------------------------------------------------------------------
```python
import pytae as pt

tips = pt.sample("tips")

query = \"\"\"
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
\"\"\"

result = tips.pt.sql(query)
print(result)
```

Recipe 4: Multi-File Merge, Concat, and Export
--------------------------------------------------------------------------------
```bash
# 1. Join files on shared key and filter
pytae -file "orders.parquet=ord; customers.csv=cust" \\
      -merge "left=ord, right=cust, on=cust_id, how=inner" \\
      -qry "amount > 50" \\
      -o filtered_orders.parquet

# 2. Concatenate monthly files and check row count
pytae -file "jan.parquet=m1; feb.parquet=m2; mar.parquet=m3" \\
      -concat "frames='m1,m2,m3'" \\
      -shape
```

Recipe 5: In-Terminal Visual Inspection (-freq, -hist, -meta, -arrange)
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

Recipe 6: Multi-Panel Dashboard with Secondary Y-Axis and Faceting
--------------------------------------------------------------------------------
```python
import pytae as pt

penguins = pt.sample("penguins")
tips = pt.sample("tips")

# 1. Multi-panel dashboard via mosaic layout
mosaic = \"\"\"
AB
CD
\"\"\"
k = pt.Plotter(mosaic, figsize=(10, 8))
(k
 .data(penguins).plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species")
 .data(tips.pt.agg("day", total_bill="mean")).plot(on="B", kind="bar", x="day", y="total_bill")
 .finalize(title="Executive Dashboard", consolidate_legends=True)
)
k.save("dashboard.png", dpi=300)

# 2. Small multiples / Auto-faceting
pt.plot(penguins, by="species", ncols=3, kind="scatter", x="bill_length_mm", y="bill_depth_mm").finalize()
```


================================================================================
10. REPOSITORY DIRECTORY TREE
================================================================================

.
├── .githooks
│   └── pre-commit
├── .github
│   └── workflows
│       └── ci.yml
├── .gitignore
├── LICENSE
├── changelog.md
├── contributing.md
├── docs
│   ├── cli
│   │   ├── aggregate.md
│   │   ├── clean_replace.md
│   │   ├── diff.md
│   │   ├── export_io.md
│   │   ├── filter.md
│   │   ├── inspect.md
│   │   ├── multi_file.md
│   │   ├── mutate.md
│   │   ├── other_utilities.md
│   │   ├── pivot.md
│   │   ├── plotting.md
│   │   ├── reshape.md
│   │   ├── select.md
│   │   └── sql.md
│   ├── cli.md
│   ├── comparison.md
│   ├── library
│   │   ├── agg.ipynb
│   │   ├── arrange.ipynb
│   │   ├── mutate.ipynb
│   │   ├── other_utilities.ipynb
│   │   ├── pivot.ipynb
│   │   ├── plotting.ipynb
│   │   ├── qry.ipynb
│   │   ├── reshape.ipynb
│   │   ├── select.ipynb
│   │   └── sql.ipynb
│   └── library.md
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
│       ├── _text.py
│       ├── accessor.py
│       ├── agg.py
│       ├── arrange.py
│       ├── cli.py
│       ├── cli_parsing.py
│       ├── cli_pipeline.py
│       ├── cli_run.py
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
│       ├── py.typed
│       ├── qry.py
│       ├── readers.py
│       ├── select.py
│       ├── shape.py
│       └── sql.py
├── tests
│   ├── __init__.py
│   ├── cli_helpers.py
│   ├── conftest.py
│   ├── test_accessor.py
│   ├── test_agg.py
│   ├── test_arrange_slice.py
│   ├── test_cli_agg.py
│   ├── test_cli_clean.py
│   ├── test_cli_enhancements.py
│   ├── test_cli_filter.py
│   ├── test_cli_inspect.py
│   ├── test_cli_merge.py
│   ├── test_cli_mutate.py
│   ├── test_cli_parse.py
│   ├── test_cli_reshape.py
│   ├── test_cli_sample_datasets.py
│   ├── test_cli_select.py
│   ├── test_cli_sql.py
│   ├── test_import.py
│   ├── test_mutate.py
│   ├── test_pivot.py
│   ├── test_plotter.py
│   ├── test_qry.py
│   ├── test_readers.py
│   ├── test_select.py
│   ├── test_shape.py
│   ├── test_sql.py
│   └── test_utilities.py
└── uv.lock
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

    # MANUAL_TEXT contains sections 1 to 7 and section 10 (directory tree)
    # Split MANUAL_TEXT so sections 8 and 9 (docs) sit before the directory tree
    tree_marker = "================================================================================\n10. REPOSITORY DIRECTORY TREE"
    if tree_marker in MANUAL_TEXT:
        manual_pre, manual_tree = MANUAL_TEXT.split(tree_marker, 1)
        parts.append(manual_pre.strip())
    else:
        manual_pre = MANUAL_TEXT
        manual_tree = ""
        parts.append(manual_pre.strip())

    # Section 8: CLI Feature Documentation Guides (docs/cli/ & docs/cli.md)
    parts.append("\n================================================================================")
    parts.append("8. CLI FEATURE DOCUMENTATION GUIDES (docs/cli/ & docs/cli.md)")
    parts.append("================================================================================\n")
    cli_files = [REPO_ROOT / "docs" / "cli.md"] + sorted((REPO_ROOT / "docs" / "cli").glob("*.md"))
    for f in cli_files:
        rel_path = f.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        parts.append(f"# FILE: {rel_path}")
        parts.append("################################################################################")
        parts.append(f.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 9: Interactive Library Notebook Walkthroughs (docs/library/ & docs/library.md)
    parts.append("================================================================================")
    parts.append("9. INTERACTIVE LIBRARY NOTEBOOK WALKTHROUGHS (docs/library/ & docs/library.md)")
    parts.append("================================================================================\n")
    lib_md = REPO_ROOT / "docs" / "library.md"
    parts.append("################################################################################")
    parts.append(f"# FILE: {lib_md.relative_to(REPO_ROOT)}")
    parts.append("################################################################################")
    parts.append(lib_md.read_text(encoding="utf-8").rstrip() + "\n")

    nb_files = sorted((REPO_ROOT / "docs" / "library").glob("*.ipynb"))
    for nb_path in nb_files:
        rel_path = nb_path.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        parts.append(f"# NOTEBOOK: {rel_path}")
        parts.append("################################################################################")
        parts.append(_format_notebook(nb_path).rstrip() + "\n")

    # Section 10: Philosophy & Comparison Rosetta Stone (docs/comparison.md)
    parts.append("================================================================================")
    parts.append("10. PHILOSOPHY & COMPARISON ROSETTA STONE (docs/comparison.md)")
    parts.append("================================================================================\n")
    comp_md = REPO_ROOT / "docs" / "comparison.md"
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
