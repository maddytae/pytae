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
    4.3.  pt.select() / df.pt.select() — Column Selection & Reordering
    4.4.  pt.agg_df() / df.pt.agg_df() — Grouped Aggregation
    4.5.  pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
    4.6.  pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
    4.7.  pt.sql() / df.pt.sql() — DuckDB SQL Engine
    4.8.  Other Utilities:
          - pt.cols() / df.pt.cols()
          - pt.handle_missing() / df.pt.handle_missing()
          - pt.clean_columns() / df.pt.clean_columns()
          - pt.replace_values() / df.pt.replace_values()
          - df.to_clip() (DataFrame & Series method)
    4.9.  Plotter — Visualization & Dashboarding (Plotting API)
5.  CLI REFERENCE (COMMAND LINE INTERFACE)
    5.1.  Execution Model & Pipeline Architecture
    5.2.  File Formats & Zero-Cost Metadata Inspection
    5.3.  All CLI Flags & Syntax Rules
    5.4.  Quoting & Delimiter Standards (: vs =)
    5.5.  Multi-File Operations (-file, -merge, -concat, -sql)
    5.6.  Batch Processing & Conversions
6.  COMMON PITFALLS, SYNTAX RULES, AND EDGE CASES
7.  END-TO-END RECIPES & EXAMPLES (PYTHON & CLI)
8.  REPOSITORY DIRECTORY TREE
9.  BUILD & CONFIGURATION (pyproject.toml)
10. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)
11. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)
================================================================================


1. OVERVIEW & CORE PHILOSOPHY
--------------------------------------------------------------------------------
`pytae` is an ergonomic, high-performance tabular data manipulation library and 
command-line tool built on top of Pandas, PyArrow, DuckDB, and Matplotlib.

Key principles:
1. Dual Calling Convention: Every library verb exists both as a functional 
   function `pt.verb(df, ...)` and as a Pandas DataFrame accessor `df.pt.verb(...)`.
   The accessor enables seamless method chaining with standard Pandas methods:
   `df.rename(...).pt.qry(...).pt.select(...).pt.agg_df(...)`.
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


2. PACKAGE ARCHITECTURE & IMPORT PATTERNS
--------------------------------------------------------------------------------
Installation (PyPI: https://pypi.org/project/pytae/):
  pip install pytae            # latest release: 3.7.0
  pip install 'pytae[plot]'    # includes matplotlib, scipy
  pip install 'pytae[sql]'     # includes duckdb

Importing:
  import pytae as pt
  import pandas as pd

Top-Level Functions exported by `pytae`:
  - pt.select(df, *args, **kwargs)
  - pt.everything() (sentinel for select)
  - pt.qry(df, *args, **kwargs)
  - pt.mutate(df, *args, **kwargs)
  - pt.agg_df(df, *args, **kwargs)
  - pt.agg(df, *args, **kwargs) (alias for agg_df)
  - pt.long(df, cols=None, id_vars=None, c="variable", v="value")
  - pt.wide(df, c="variable", v="value")
  - pt.pivot(df, r=None, c=None, v=None, a="sum", dropna=False, fill_value=None)
  - pt.sql(df, query, **frames)
  - pt.handle_missing(df, fillna=".")
  - pt.cols(df, ascending=True)
  - pt.clean_columns(df, **kwargs)
  - pt.replace_values(df, v, c=None, exact=True)
  - pt.sample(name)
  - pt.sample_data (Mapping of bundled datasets)
  - pt.Plotter (lazy loaded when matplotlib is installed)
  - pt.plot(df, *args, **kwargs)
  - pt.finalize(plotter=None, **kwargs)

DataFrame Accessor:
  Importing pytae automatically registers the `.pt` accessor on `pd.DataFrame`.
  Methods on `df.pt`:
    df.pt.select(...)
    df.pt.qry(...)
    df.pt.mutate(...)
    df.pt.agg_df(...)
    df.pt.agg(...)
    df.pt.long(...)
    df.pt.wide(...)
    df.pt.pivot(...)
    df.pt.sql(...)
    df.pt.handle_missing(...)
    df.pt.cols(...)
    df.pt.clean_columns(...)
    df.pt.replace_values(...)
    df.pt.plot(...)
    df.pt.finalize(...)


3. SAMPLE DATASETS
--------------------------------------------------------------------------------
`pytae` includes pre-packaged datasets stored in parquet format inside the library.
Access methods:
  df = pt.sample("penguins")
  df = pt.sample_data["penguins"]

List available dataset names:
  pt.sample_data.keys()
  Available datasets include:
  - 'penguins': Palmer penguins dataset (species, island, bill_length_mm, 
    bill_depth_mm, flipper_length_mm, body_mass_g, sex, year).
  - 'tips': Restaurant tips dataset (total_bill, tip, sex, smoker, day, time, size).
  - 'titanic': Titanic passenger survival data (survived, pclass, sex, age, ...).
  - 'healthexp': Healthcare spending and life expectancy.
  - 'fmri': Functional MRI time points and BOLD signal.
  - 'flights', 'diamonds', 'iris', 'planets', etc.


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
  5. Library Function:
     pt.qry(penguins, species="Adelie")

Supported Condition Types & Operators:
  - Equality:
    species="Adelie"
    "species = Adelie" or "species = 'Adelie'"
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
  pt.mutate(df: pd.DataFrame, *args: Any, by: str | Sequence[str] | None = None, dropna: bool = False, observed: bool = True, params: dict | None = None, **kwargs: Any) -> pd.DataFrame
  df.pt.mutate(*args: Any, by: str | Sequence[str] | None = None, dropna: bool = False, observed: bool = True, params: dict | None = None, **kwargs: Any) -> pd.DataFrame

Calling Styles:
  1. Keyword Arguments:
     df.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")
  2. Dictionary Unpacking (for column names containing spaces):
     df.pt.mutate(**{"body mass kg": "body_mass_g / 1000"})
  3. External Spec File:
     df.pt.mutate("@features.txt")
  4. Callables / Lambdas:
     df.pt.mutate(is_heavy=lambda d: d["body_mass_g"] > 4000)

Key Behaviors & Features:
  - Sequential Chaining: Later expressions can reference columns created earlier 
    in the SAME mutate() call:
    df.pt.mutate(mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")
  - Columns With Spaces:
    When referencing existing columns that contain spaces in expressions, 
    surround them in SQL brackets `[col]` or backticks `` `col` ``:
    df.pt.mutate(ratio="[body mass g] / [bill length mm]")
    df.pt.mutate(ratio="`body mass g` / `bill length mm`")
  - Local Scope Variables (@local_var):
    Reference local variables from caller scope using `@name`:
    threshold = 4000
    df.pt.mutate(heavy="body_mass_g >= @threshold")
    Or pass explicitly via params:
    df.pt.mutate(heavy="body_mass_g >= @threshold", params={"threshold": 4000})

Injected Helper Functions in Expressions:
  - if_else(condition, true_value, false_value):
    df.pt.mutate(category="if_else(body_mass_g > 4000, 'Heavy', 'Light')")
  - case_when((cond1, val1), (cond2, val2), ..., default=val):
    Evaluated in order, first match wins. Accepts tuples or flat alternating pairs:
    df.pt.mutate(size="case_when((body_mass_g >= 4500, 'L'), (body_mass_g >= 3500, 'M'), default='S')")
    df.pt.mutate(size="case_when(body_mass_g >= 4500, 'L', body_mass_g >= 3500, 'M', default='S')")
  - coalesce(col1, col2, ..., default):
    Returns the first non-null value per row:
    df.pt.mutate(phone="coalesce(mobile, home, work, 'None')")
  - map(column, {key: value, ...}[, default]):
    Recodes values via dictionary lookup:
    df.pt.mutate(code="map(species, {'Adelie': 'A', 'Gentoo': 'G'}, default='Other')")
  - Series Methods Fallback:
    Method chains on Series work seamlessly:
    df.pt.mutate(initial="species.str[0]", rounded="bill_length_mm.round()")

Grouped Window Operations (by=..., dropna=False, observed=True):
  Evaluates window calculations and group summaries broadcast back to every row (N -> N):
  - Injected Aggregations: mean(x), sum(x), median(x), min(x), max(x), std(x), var(x), n (or n())
  - Sequential Derivation:
    df.pt.mutate("avg_tip = mean(tip), diff = tip - avg_tip, sz = n", by="day")
  - Multi-Column Grouping:
    df.pt.mutate("avg = mean(val)", by=["species", "island"])
  - Handling Missing Group Keys (dropna):
    - dropna=False (default across pytae): Rows with NA in grouping columns form their own group
      and compute group metrics across all NA rows together.
    - dropna=True: Rows with NA in grouping columns receive NaN in new columns;
      row count and alignment are strictly preserved.
      df.pt.mutate("avg = mean(val)", by="grp", dropna=True)
      (In CLI: pass -dropna true to exclude NA groups)

External Spec File Format (@file.txt):
  Lines in `@specs.txt` are evaluated sequentially. Supports `#` comments and empty lines:
  # Feature engineering specs
  mass_kg = body_mass_g / 1000
  mass_lb = mass_kg * 2.20462
  bill_ratio = [bill length mm] / [bill depth mm]


4.3. pt.select() / df.pt.select() — Column Selection & Reordering
--------------------------------------------------------------------------------
Selects and reorders columns using names, ranges/slices, data types, patterns, or predicates.

Signature:
  pt.select(
      df: pd.DataFrame,
      *args: Any,
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
  - pt.everything():
    Pulls in all remaining unselected columns in their original order:
    df.pt.select("species", pt.everything())  # species first, then the rest
  - Predicate Callable:
    df.pt.select(lambda c: c.startswith("b"))

Keyword Arguments:
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


4.4. pt.agg_df() / df.pt.agg_df() / df.pt.agg() — Grouped Aggregation
--------------------------------------------------------------------------------
Aggregates a DataFrame grouped by explicit `by=` column(s) (or None for whole-table
summary) and aggregates numeric columns. Supports string mapping specifications
with bracketed columns `[col]` (matching CLI `-agg`), keyword arguments, or
whole-frame aggregations.

Signature:
  pt.agg_df(
      df: pd.DataFrame,
      by: str | Sequence[str] | None,
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
     dropna=False by default retains missing category groups across aggregations.


4.5. pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
--------------------------------------------------------------------------------
Pure structural reshaping between long and wide formats without aggregation.

pt.long(df, cols=None, id_vars=None, c="variable", v="value"):
  Melts columns to rows. If cols is None, melts all numeric columns, keeping 
  non-numeric columns as ID variables.
  Parameters:
    cols: Column(s) to melt to rows. Can be string or list/tuple of strings.
    id_vars: Identifier column(s) to keep as rows.
    c: column name for melted metric names (default: "variable")
    v: column name for melted metric values (default: "value")
  Example:
    tall = df.pt.long(c="metric", v="measurement")

pt.wide(df, c="variable", v="value"):
  Pivots long-format records back into column headers (exact reverse of pt.long).
  Strictly 1-to-1 without aggregation.
  Parameters:
    c: column whose unique values become headers (default: "variable")
    v: column containing values (default: "value")
  Rules:
    - Requires unique (index, c) pairs. If duplicate keys exist, raises ValueError
      guiding the user to use pt.pivot() instead.
    - c and v cannot be the same column.
  Example:
    wide = tall.pt.wide(c="metric", v="measurement")


4.6. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
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
     Alias: index=, rows=
  c: Column dimension(s). String (e.g. "sex") or list of strings.
     Alias: columns=, cols=
  v: Value column(s) to aggregate. Optional when counting (a="n").
     Alias: values=
  a: Aggregation function (default: "sum"). Supports standard aggregations
     ("mean", "sum", "median", "min", "max", "std", "var") and "n" for row counts.
     Alias: aggfunc=
  dropna: Whether to drop NA categories in row/column keys (default: False).
  fill_value: Scalar value for missing grid intersections. For a="n", defaults to 0.

Key Features & Conventions:
  - 1D Flat Headers: Multi-column pivots format headers cleanly (e.g. "MALE_2007", "FEMALE_2007").
  - Pure Integer Counts: Row counts (a="n") return standard int64 (or Int64) integers, not floats.
  - Zero Count Fill: Missing grid combinations in frequency tables default to 0.
  - Omit v for Counts: For frequency cross-tabulations (a="n"), v is optional.
  - RangeIndex: Index is always reset to 0, 1, 2, ... with no lingering MultiIndex.

Examples:
  # 2D summary matrix
  df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")

  # Frequency cross-tabulation (count rows across dimensions)
  df.pt.pivot(r="island", c="species", a="n")

  # Multi-dimensional pivot with custom fill
  df.pt.pivot(r=["species", "island"], c="sex", v="body_mass_g", a="median", fill_value=0)


4.7. pt.sql() / df.pt.sql() — DuckDB SQL Engine
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


4.8. Other Utilities
--------------------------------------------------------------------------------
- pt.cols(df, ascending=True):
  Returns list of column names.
  ascending=True  -> Alphabetical A-Z
  ascending=False -> Alphabetical Z-A
  ascending=None  -> Original DataFrame file order

- pt.handle_missing(df, fillna="."):
  Sanitizes missing values:
  - Category columns are converted to object.
  - String columns: fills NaN with `fillna` (default '.') and strips whitespace.
  - Numeric columns: fills NaN with `0`.

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

- df.to_clip() / s.to_clip():
  Copies DataFrame or Series to system clipboard as tab-separated values without index. Attached directly to pd.DataFrame and pd.Series on import pytae (no pt. or df.pt. needed).


4.9. Plotter — Visualization & Dashboarding (Plotting API)
--------------------------------------------------------------------------------
Method-chainable plotting system wrapping `pandas.plot` and `matplotlib`.
Requires: pip install 'pytae[plot]'

Key Concepts:
  - Fluent Accessor & Functional Shortcuts:
    tips.pt.plot(kind="bar", x="day", y="total_bill", by="sex", aggfunc="mean", palette="tab10").pt.finalize()
    pt.plot(tips, kind="bar", x="day", y="total_bill", aggfunc="mean").finalize()
  - Chain Pattern:
    k = pt.Plotter(figsize=(6, 4))
    (k
     .data(df)
     .plot(kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="Set1")
     .finalize()
    )
    k.fig  # access matplotlib figure
  - Auto-Aggregation:
    No need to pre-aggregate data. Pass `by=` and `aggfunc=`:
    k.data(tips).plot(kind="bar", x="day", y="total_bill", by="sex", aggfunc="mean").finalize()
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
     .data(tips).plot(on="B", kind="bar", x="day", y="total_bill", aggfunc="mean")
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
  - Saving:
    k.save("chart.png", dpi=300)


5. CLI REFERENCE (COMMAND LINE INTERFACE)
--------------------------------------------------------------------------------

5.1. Execution Model & Pipeline Architecture
--------------------------------------------------------------------------------
The CLI command `pytae` processes operations sequentially in the order given on 
the command line:
  pytae input.parquet -qry "body_mass_g > 3000" -select "species,body_mass_g" -head 5

Pipeline Rules:
1. Positional Path: The first unflagged argument is the input file path.
   (Except in `-file` multi-file mode, where `-file` replaces the positional path).
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
Inspection & Comparison Flags:
  -head [N]             Print first N rows (default 5)
  -tail [N]             Print last N rows (default 5)
  -shape                Print row and column counts
  -cols [ORDER]         Print column names (ORDER: asc, desc, none)
  -dtype [ORDER]        Print column data types
  -nulls [ORDER]        Print null value counts per column
  -describe             Descriptive statistics for numeric columns
  -info                 DataFrame summary (dtypes, non-null counts, memory)
  -meta                 Display zero-scan Parquet metadata (row groups, schema, compression)
  -diff PATH            Compare schema, shape, null counts, and cell values against another file
  -value_counts         Value counts for categorical/string columns
  -unique               Count of unique values per column
  -sample [N]           Random sample of N rows
  -seed N               Random seed for sampling
  -frac P               Sample fraction P (0.0 to 1.0)
  -nrows N              Limit reading to first N rows of file

Row Filtering Flags:
  -qry CONDITIONS       pytae filter expressions (e.g. "species='Adelie', body_mass_g > 3500")
  -query EXPR           pandas query() expression passed to numexpr

Column Transformation Flags:
  -select SPEC          Select columns (names, slices 'a:b', contains, dtypes, negative '-col', exclude=)
  -mutate SPEC          Create/overwrite columns ("new_col = expression")
  -rename OLD:NEW,...   Rename columns using ':' delimiter (e.g. "a:alpha, b:beta")
  -replace_values SPEC  Replace values: "v='old:new', c='col', exact=True"
  -clean_columns SPECS  Clean headers: "strip=True, fill='_', case='lower'"

Aggregation & Reshaping Flags:
  -by, -group_by COLS   Grouping columns for -agg and -mutate (e.g. -by species -agg mean)
  -agg, -agg_df SPECS   Aggregate columns (e.g. -by species -agg "body_mass_g=mean, count=n" or -agg mean)
  -dropna BOOL          Control NA group handling for -agg, -mutate, -pivot, -wide (true/false, default: false)
  -long [SPECS]         Melt numeric columns to rows: "c=variable, v=value"
  -wide [SPECS]         Pure 1-to-1 unmelting into headers: "c=variable, v=value"
  -pivot SPECS          2D pivot table: "r=species, c=island, v=body_mass_g, a=mean" (or counts: "r=species, c=island, a=n")
  -crosstab SPECS       Frequency crosstabulation (delegates to -pivot): "index=species, columns=sex"

SQL & Multi-File Flags:
  -sql QUERY            Run DuckDB SQL on table 'data' (or @query.sql)
  -file SPECS           Multi-file mode: "file1.parquet=df1; file2.csv=df2"
  -merge SPECS          Join files: "left=df1, right=df2, on=id, how=inner"
  -concat SPECS         Stack files: "frames='df1,df2'"

Output & Formatting Flags:
  -o TARGET             Output destination: file path (.csv, .parquet, .jsonl, .csv.gz, etc.),
                        format for in-place or batch conversion ('csv', 'parquet', 'txt', 'dat',
                        'jsonl', 'csv.gz', 'jsonl.gz'), or 'clip'/'clipboard'
  -out_dir, -od DIR     Target directory for exported files (created if missing; requires -o)
  -dlim CHAR            Delimiter character for input/output text files
  -encoding ENC         File encoding (e.g. utf-8, latin-1)
  -pretty               Pretty-print tables with bordered markdown formatting
  -pager                Pipe table or inspect outputs through system pager ($PAGER or less)
  -round N              Round numeric output columns to N decimal places
  -progress [N]         Show row-reading/writing progress (default: 200,000 rows per chunk)


5.4. Quoting & Delimiter Standards (: vs =)
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

Quoting Rules:
- String literals in expressions require quotes: `species = 'Adelie'`.
- Column names inside expressions must remain unquoted so they resolve as variables:
  `mass_kg = body_mass_g / 1000` (NOT `'body_mass_g' / 1000`).
- Column names containing spaces must use brackets `[col]` or backticks `` `col` ``.


5.5. Multi-File Operations (-file, -merge, -concat, -sql)
--------------------------------------------------------------------------------
When operating across multiple files, `-file` replaces the positional file path:

Syntax:
  pytae -file "PATH=ALIAS; PATH=ALIAS" -merge ...

1. Joining Files (-merge):
   pytae -file "orders.parquet=ord; customers.csv=cust"          -merge "left=ord, right=cust, on=cust_id, how=inner"          -select "order_id,cust_name,amount" -head 10

   Joining on differing column names:
   -merge "left=df1, right=df2, on='left_id:right_id', how=left"

   Joining multiple files in sequence ('data' represents previous merge result):
   pytae -file "a.csv=a; b.csv=b; c.csv=c"          -merge "left=a, right=b, on=id"          -merge "left=data, right=c, on=id"

2. Stacking Files (-concat):
   pytae -file "jan.csv=m1; feb.csv=m2; mar.csv=m3"          -concat "frames='m1,m2,m3'" -shape

3. SQL Across Multiple Files:
   pytae -file "orders.parquet=ord; customers.csv=cust"          -sql "select ord.id, cust.name, ord.total from ord join cust using (cust_id)"


5.6. Batch Processing & Conversions (-o)
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


6. COMMON PITFALLS, SYNTAX RULES, AND EDGE CASES
--------------------------------------------------------------------------------
1. Spaced Column Names:
   - In `df.pt.qry()`: String expressions handle spaces directly:
     `df.pt.qry("bill length mm > 40")`.
   - In `df.pt.mutate()`: Python kwargs syntax cannot have spaces (`col name = ...` is a SyntaxError).
     Must unpack a dictionary:
     `df.pt.mutate(**{"col name": "a + b"})`.
   - Inside expressions: Always enclose spaced names in brackets `[col name]` or backticks `` `col name` ``.
2. Select Regex vs Positional String:
   - Calling `pt.select(df, "^bill")` will search for a literal column named `^bill` and fail.
   - You MUST use `regex=`: `pt.select(df, regex=r"^bill")`.
3. Aggregation Grouping Logic:
   - `agg_df` automatically groups by EVERY non-numeric column when by= is omitted.
   - If your DataFrame has 10 string columns, it groups by all 10.
   - Always filter columns first if you only want to group by 1 or 2 columns, or specify `by=`:
     `df.pt.select("species", "body_mass_g").pt.agg_df("mean")`.
4. The Count Column 'n':
   - 'n' is a reserved aggregation token in `agg_df`, `pivot`, and grouped `mutate(..., by=...)`.
   - If your input table already has a real numeric column named 'n', rename it first to avoid collision.
5. In-Place Modification:
   - pytae NEVER modifies DataFrames in place. Always assign the returned DataFrame:
     `df = df.pt.mutate(...)` or chain operations.
6. Null Checks in qry():
   - Null checks are 1-element tuples: `sex=('isna',)` or `sex=('notna',)`.
   - Do NOT pass a second element.
7. Reshaping: wide() vs pivot():
   - `wide()` is strictly for pure 1-to-1 structural unmelting (reversing long()) without aggregation.
   - For 2D cross-tabulations, aggregations across dimensions, or when duplicate keys exist, use `pivot()`:
     `df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")`.


7. END-TO-END RECIPES & EXAMPLES
--------------------------------------------------------------------------------

Recipe 1: Full Python Data Engineering Pipeline
--------------------------------------------------------------------------------
```python
import pytae as pt

# Load bundled dataset
penguins = pt.sample("penguins")

# Clean pipeline: filter -> derive features -> select -> aggregate
summary = (
    penguins
    # 1. Filter: Adelie & Gentoo with known sex and body mass >= 3500g
    .pt.qry(
        species=["Adelie", "Gentoo"],
        sex=("notna",),
        body_mass_g=">= 3500",
    )
    # 2. Derive features: convert mass, calculate ratio, categorize size
    .pt.mutate(
        mass_kg="body_mass_g / 1000",
        bill_ratio="bill_length_mm / bill_depth_mm",
        size_class="if_else(mass_kg > 4.5, 'Large', 'Regular')",
    )
    # 3. Create a column with spaces using dict unpacking
    .pt.mutate(**{
        "normalized bill": "bill_length_mm / bill_length_mm.max()",
    })
    # 4. Narrow to columns of interest
    .pt.select("species", "size_class", "mass_kg", "bill_ratio")
    # 5. Grouped aggregation: mean mass, max ratio, group counts
    .pt.agg_df(
        mass_kg="mean",
        bill_ratio="max",
        n="n",
    )
)
print(summary)
```

Recipe 2: DuckDB SQL Query on DataFrame
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

Recipe 3: Advanced CLI Pipeline One-Liners
--------------------------------------------------------------------------------
```bash
# 1. Inspect schema and row count without loading full data into memory
pytae raw_data.parquet -shape -cols

# 2. Filter, engineer columns, clean headers, and inspect head
pytae penguins.parquet \\
  -qry "species = 'Adelie', body_mass_g > 3500" \\
  -mutate "mass_kg = body_mass_g / 1000, is_heavy = mass_kg > 4.0" \\
  -clean_columns "strip=True, fill='_', case='lower'" \\
  -select "species,island,mass_kg,is_heavy" \\
  -head 5

# 3. Fast Join Across Two Files and Export to Parquet
pytae -file "transactions.csv=tx; customers.parquet=cust" \\
      -merge "left=tx, right=cust, on='customer_id', how='inner'" \\
      -qry "amount > 100" \\
      -o high_value_tx.parquet

# 4. Grouped Window Calculation with Missing Group Key Retention (-dropna false default)
pytae penguins.parquet \\
  -by sex \\
  -mutate "avg_mass = mean(body_mass_g), diff = body_mass_g - avg_mass" \\
  -select "species,sex,body_mass_g,avg_mass,diff" \\
  -head 5
```

Recipe 4: 2D Pivot Tables & Frequency Matrices (Python & CLI)
--------------------------------------------------------------------------------
```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. 2D Summary Grid (Mean Body Mass by Island and Species)
grid = penguins.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")
print(grid)

# 2. 2D Frequency Matrix (Counts with a="n")
counts = penguins.pt.pivot(r="island", c="species", a="n")
print(counts)
```

```bash
# CLI 2D Pivot Summary
pytae penguins.parquet -pivot "r=island, c=species, v=body_mass_g, a=mean"

# CLI 2D Frequency Counts
pytae penguins.parquet -pivot "r=island, c=species, a=n"
```


================================================================================
8. REPOSITORY DIRECTORY TREE
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
│   │   ├── pivot.md
│   │   ├── plotting.md
│   │   ├── reshape.md
│   │   ├── select.md
│   │   └── sql.md
│   ├── cli.md
│   ├── library
│   │   ├── agg.ipynb
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
│       ├── agg_df.py
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
│   ├── test_agg_df.py
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


def generate_reference() -> None:
    parts: list[str] = [MANUAL_TEXT.strip()]

    # Section 9: pyproject.toml
    pyproject_path = REPO_ROOT / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8").strip()

    parts.append("\n================================================================================")
    parts.append("9. BUILD & CONFIGURATION (pyproject.toml)")
    parts.append("================================================================================\n")
    parts.append("File: pyproject.toml")
    parts.append("----------------------------------------")
    parts.append(pyproject_content)

    # Section 10: Underlying Python Implementation Source Code (src/pytae/)
    parts.append("\n================================================================================")
    parts.append("10. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)")
    parts.append("================================================================================\n")

    src_dir = REPO_ROOT / "src" / "pytae"
    src_files = sorted(src_dir.glob("*.py"))
    for f in src_files:
        rel_path = f.relative_to(REPO_ROOT)
        parts.append("################################################################################")
        parts.append(f"# FILE: {rel_path}")
        parts.append("################################################################################")
        parts.append(f.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 11: Test Suite Implementation Source Code (tests/)
    parts.append("================================================================================")
    parts.append("11. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)")
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
