#!/usr/bin/env python
"""Generate and update reference/pytae_reference.txt with latest documentation and code."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_version() -> str:
    """Read the latest package version from pyproject.toml or src/pytae/__init__.py."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        import re

        m = re.search(r'version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    init_path = REPO_ROOT / "src" / "pytae" / "__init__.py"
    if init_path.exists():
        import re

        m = re.search(r'__version__\s*=\s*"([^"]+)"', init_path.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "3.12.4"


MANUAL_TEXT = """================================================================================
PYTAE COMPREHENSIVE KNOWLEDGE BASE & AGENT TRAINING REFERENCE MANUAL
RELEASE VERSION: __PYTAE_VERSION__
================================================================================

TABLE OF CONTENTS
--------------------------------------------------------------------------------
0.  CRITICAL AGENT GROUND TRUTH & SYNTAX ENFORCEMENT RULES (READ FIRST)
1.  OVERVIEW & CORE PHILOSOPHY
2.  PACKAGE ARCHITECTURE & IMPORT PATTERNS
3.  SAMPLE DATASETS
4.  PYTHON LIBRARY REFERENCE (API VERBS)
    4.1.  pt.filter() / df.pt.filter() — Row Filtering (formerly qry)
    4.2.  pt.by() / df.pt.by() — Single-Shot Scoped Grouping
    4.3.  pt.mutate() / df.pt.mutate() — Column Creation & Feature Engineering
    4.4.  pt.select() / df.pt.select() — Column Selection, Slicing & Exclusion
    4.5.  pt.arrange() / df.pt.arrange() — Row Sorting
    4.6.  head() / tail() — Group-Aware & Proportion-Aware Row Slicing
    4.7.  pt.distinct() / df.pt.distinct() — Deduplication
    4.8.  pt.count() / df.pt.count() — Frequency & Group Counting
    4.9.  pt.agg() / df.pt.agg() — Grouped Aggregation
    4.10. pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
    4.11. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
    4.12. Other Utilities:
          - pt.dropna() / df.pt.dropna()
          - pt.cols() / df.pt.cols()
          - pt.glimpse() / df.pt.glimpse()
          - pt.freq() / df.pt.freq()
          - pt.hist() / df.pt.hist()
          - pt.bar() / df.pt.bar()
          - pt.scatter() / df.pt.scatter()
          - pt.corr() / df.pt.corr()
          - pt.join() / df.pt.join() / df.join() (Polars Join Engine)
          - pt.concat() / df.pt.concat() / df.concat() (Stacking Engine)
          - Transparent Polars Verb Delegation (__getattr__)
          - pt.fillna() / df.pt.fillna()
          - pt.mask() / df.pt.mask() / pt.unmask() / df.pt.unmask() (Sensitive Data Masking)
          - pt.clean_columns() / df.pt.clean_columns()
          - safe_reset_index(df)
          - df.to_clip() / s.to_clip() (System Clipboard Export)
    4.13. Plotter — Visualization & Dashboarding (Plotting API)
    4.14. pt.repl() / df.pt.repl() / df.repl() — Interactive REPL Shell
    4.15. pt.clear() / r.clear() — Terminal Screen Clearing
5.  CLI REFERENCE (COMMAND LINE INTERFACE)
    5.1.  Execution Model & Pipeline Architecture
    5.2.  File Formats & Zero-Cost Metadata Inspection
    5.3.  All CLI Flags & Syntax Rules
    5.4.  In-Terminal Visualizations (-freq, -hist, -bar, -scatter, -corr)
    5.5.  Quoting & Delimiter Standards (: vs =) and Shell Quoting Rules
    5.6.  Multi-File Operations (-file, -join, -concat, -sql)
    5.7.  Batch Processing, Conversions & Clipboard (-o)
    5.8.  Interactive REPL Shell (pytae -i, pytae <file> -i)
6.  FREQUENTLY ASKED QUESTIONS, PITFALLS & SYNTAX RULES
    6.1.  When should I use `-select` before `-agg`?
    6.2.  Why is `by` strictly standalone across all verbs?
    6.3.  Why does every chained method call start on a new line?
    6.4.  What are the key canonical verbs (filter, head/tail, distinct)?
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
    6.15. How does terminal clearing and table removal work in the REPL? (clear, rm *, rm checkpoint *)
    6.16. How do I get Top N records per group in the CLI? (Sequential -by)
    6.17. Why did my filter fail with unrecognized token / missing quote in terminal?
    6.18. Error Message Catalog & Troubleshooting Index
7.  END-TO-END RECIPES & EXAMPLES (PYTHON & CLI)
    Recipe 1: Master Mutate Recipe (All 12 Features in One Pipeline)
    Recipe 2: Grouped Aggregation & 2D Pivots (Python & CLI)
    Recipe 3: Group-Aware Row Slicing (pt.by + arrange + head)
    Recipe 4: Polars SQL Query in CLI Pipeline
    Recipe 5: Multi-File Join, Concat, and Export
    Recipe 6: In-Terminal Visual Inspection (-freq, -hist, -meta, -arrange)
    Recipe 7: Multi-Panel Dashboard with Secondary Y-Axis and Faceting
    Recipe 8: Interactive REPL Multi-Table Exploration & Snapshots
    Recipe 9: Top N per Group across Chained Pipelines (CLI, Python & SQL)
8.  DETAILED FEATURE DOCUMENTATION GUIDES (docs/detailed_docs/)
9.  MASTER DOCUMENTATION & ARCHITECTURE GUIDE (docs/pytae.md)
10. ECOSYSTEM COMPARISONS & MIGRATION GUIDES (Pandas, dplyr, SAS)
11. REPOSITORY DIRECTORY TREE
12. BUILD & CONFIGURATION (pyproject.toml)
13. UNDERLYING PYTHON IMPLEMENTATION SOURCE CODE (src/pytae/)
14. TEST SUITE IMPLEMENTATION SOURCE CODE (tests/)
================================================================================


0. CRITICAL AGENT GROUND TRUTH & SYNTAX ENFORCEMENT RULES (READ FIRST)
================================================================================
ATTENTION AI ASSISTANTS / COPILOT AGENTS:
When generating commands, scripts, or explanations for pytae users, you MUST strictly adhere to the following non-negotiable rules. Hallucinating syntax from other libraries (dplyr, pandas, polars, bash) is strictly forbidden.

RULE 1: STRICT CANONICAL VERBS ONLY
- Row filtering: ALWAYS `-filter` (CLI) or `df.filter()` (Python). 
  * NEVER output `-qry`, `-query`, or `df.query()`.
- Row sorting: ALWAYS `-arrange` (CLI) or `df.arrange()` (Python).
  * Explicit descending: `body_mass_g desc`.
  * NEVER output `-sort`, `-sort_by`, or `-order`.
  * NEVER prefix columns with `-` (e.g. `-arrange "-col"` is an error; use `-arrange "col desc"`).
- Deduplication: ALWAYS `-distinct` (CLI) or `df.distinct()` (Python).
  * NEVER output `-dedupe` or `df.drop_duplicates()`.
- Counting: ALWAYS `-count` (CLI) or `df.count()` (Python) or `agg(total="count")`.
  * NEVER output `df.tally()`.
- Reshaping: Pure unmelting is `wide()` / `-wide`; 2D aggregation matrix is `pivot()` / `-pivot`.

RULE 2: SHELL QUOTING STANDARD (BASH / ZSH)
- In terminal CLI commands, ALWAYS wrap expression arguments in double quotes `""` and wrap string literals inside expressions in single quotes `''`:
  * Correct: `pytae data.parquet -filter "species == 'Gentoo'"`
  * Correct: `pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30']"`
  * Correct: `pytae data.parquet -mutate "status = 'active'"`
  * INCORRECT: `pytae data.parquet -filter "species == Gentoo"` (Gentoo is parsed as a column identifier and fails with ColumnNotFound!)
  * INCORRECT: `pytae data.parquet -filter 'species == "Gentoo"'` (Bash outer single quotes prevent variable expansion; Polars treats inner double quotes as column identifiers).
- Column identifiers must remain UNQUOTED (e.g. `body_mass_g > 3500`).
- If a column name contains spaces, enclose it in square brackets `[col name]`:
  * Example: `pytae data.parquet -filter "[body mass g] > 3500"`
  * Example: `pytae data.parquet -arrange "[bill length mm] desc"`

RULE 3: SINGLE-SHOT ZERO-POLLUTION GROUPING (`-by` / `df.by()`)
- In Pytae, grouping is strictly single-shot and auto-clearing.
- `-by col` scopes ONLY the immediate next verb (`mutate`, `agg`, `head`, `tail`, `count`), and then IMMEDIATELY RESETS to the clean ungrouped table scope.
- In Python: `df.by("col").mutate(...)` returns a clean, ungrouped DataFrame.
- There is NO persistent grouped state. There is NO `ungroup()` verb. Calling `df.ungroup()` is an error.
- In Python: `by` is NEVER an argument inside verbs (e.g. `df.mutate(..., by="region")` raises TypeError). Always call `df.by("region").mutate(...)`.

RULE 4: CHAINED PIPELINES & SEQUENTIAL `-by` (TOP N RECIPE)
- Pytae CLI allows sequential `-by` flags in a single command. Each `-by` scopes the next verb, allowing multi-stage aggregation, whole-table sorting, and group-aware slicing:
  ```bash
  # Top 2 species by average body mass for each island:
  pytae sample:penguins \
    -by island,species -agg "avg_mass=mean(body_mass_g)" \
    -arrange "island, avg_mass desc" \
    -by island -head 2
  ```
  * Step 1: `-by island,species -agg ...` groups by island & species and collapses to summary rows.
  * Step 2: `-arrange "island, avg_mass desc"` sorts all rows globally (whole-table scope).
  * Step 3: `-by island -head 2` groups by island and takes top 2 rows per island, then resets.
- ANSI SQL Alternative via `-sql`:
  ```bash
  pytae sample:penguins -sql "
    WITH ranked AS (
      SELECT island, species, AVG(body_mass_g) AS avg_mass,
             ROW_NUMBER() OVER (PARTITION BY island ORDER BY AVG(body_mass_g) DESC) AS rnk
      FROM data
      GROUP BY island, species
    )
    SELECT island, species, avg_mass FROM ranked WHERE rnk <= 2
  "
  ```

RULE 5: INTERACTIVE REPL (`pytae -i`, `pytae <file> -i`)
- 1:1 CLI flag parity: Verbs in REPL must start with a leading hyphen: `-filter "..."`, `-mutate "..."`, `-head 5`, `-cols`.
- Non-destructive previews: Inspection commands (`-head`, `-tail`, `-shape`, `-cols`, `-describe`, `-glimpse`) preview data WITHOUT truncating or mutating the dataset.
- Clean confirmation: Transformations output concise shape confirmations (e.g. `-> penguins.parquet: 188 rows x 7 cols`) without dumping full tables.
- Deletion: Enforce wildcard `rm *` (all tables) or `rm checkpoint *` (all snapshots). Singular `rm checkpoint <name>`. Never use `rm checkpoints` or `-all`.
- Screen clearing: ALWAYS `clear`. Never `cls`.

RULE 6: DUAL-MODALITY PARITY
- CLI and Python APIs map 100% symmetrically:
  * CLI: `pytae data.parquet -filter "a > 1" -by b -agg c=mean`
  * Python: `df.filter("a > 1").by("b").agg(c="mean")`
  * Standalone Python: `pt.agg(pt.by(pt.filter(df, "a > 1"), "b"), c="mean")`

RULE 7: PREFER BUILT-IN SAMPLE DATASETS FOR IMMEDIATE RUNNABILITY
- Whenever answering questions or demonstrating functionality, ALWAYS prefer using built-in sample datasets (e.g. `sample:penguins`, `sample:tips`, `sample:titanic`, `sample:flights`, `sample:diamonds`) in examples instead of hypothetical placeholder filepaths (`/path/to/file.parquet` or `my_data.csv`).
- Why? Built-in sample datasets require ZERO setup or downloads from the user. Users can immediately copy and paste the command or Python snippet directly into their shell or notebook and see verified real results!
  * CLI: `pytae sample:penguins -filter "species == 'Gentoo'" -head 3`
  * Python: `penguins = pt.sample("penguins")`
================================================================================


1. OVERVIEW & CORE PHILOSOPHY
--------------------------------------------------------------------------------
Package: pytae (Current Release Version: __PYTAE_VERSION__)

`pytae` is an ergonomic, high-performance tabular data manipulation library and 
command-line tool powered by a 100% native multithreaded SIMD Polars engine with 
seamless Pandas interoperability, PyArrow, and Matplotlib.

Key principles:
1. Unified SIMD Vector Engine: Every library verb and CLI operation executes 
   natively on Polars vector memory, delivering 10x–20x performance speedups, 
   zero-copy operations, and lazy evaluation (`pt.scan()`).
2. Zero Data Loss by Default: Missing values (`null`/`NaN`) are preserved across 
   analytical operations (`agg`, `pivot`, `mutate`, `freq`) by default (`dropna=False`).
   The `dropna()` verb defaults to `how='all'` (dropping only 100%
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
   (e.g. `body_mass_g=mean`, `total=count`) without tedious `.groupby().agg()` boilerplate.
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
Installation (PyPI: https://pypi.org/project/pytae/__PYTAE_VERSION__/):
  pip install pytae==__PYTAE_VERSION__
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
  - pt.select(df, *args, dtype=None, exclude_dtype=None, contains=None, startswith=None, endswith=None, regex=None)
  - pt.everything() / pt.everything (sentinel for select)
  - pt.filter(df, *args, params=None)
  - pt.by(df, *cols)
  - pt.mutate(df, *args, dropna=False, observed=True, params=None, **kwargs)
  - pt.arrange(df, *cols, ascending=None, na_last=True)
  - pt.head(df, n=None, *, prop=None, with_ties=False) -> DataFrame
  - pt.tail(df, n=None, *, prop=None, with_ties=False) -> DataFrame
  - pt.distinct(df, *cols, keep="first")
  - pt.dropna(df, *cols, how=None, drop_nans=True)
  - pt.agg(df, *args, a=None, dropna=False, observed=True, **kwargs)
  - pt.long(df, cols=None, id_vars=None, c="variable", v="value")
  - pt.wide(df, r=None, c="variable", v="value")
  - pt.pivot(df, r=None, c=None, v=None, a="sum", dropna=False, f_v=None)
  - pt.fillna(df, value=None, *cols, subset=None, nans=True, **kwargs)
  - pt.cols(df, ascending=True)
  - pt.glimpse(df, width=None)
  - pt.freq(df, col=None, *, dropna=False)
  - pt.hist(df, col=None, bins=10)
  - pt.bar(df, col=None, val_col=None, *, width=None, dropna=False)
  - pt.scatter(df, x, y, *, width=None, height=None, braille=True, trend=False, stats=True)
  - pt.corr(df, *cols, method="pearson", pairwise=False, width=None)
  - pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False)
  - pt.safe_reset_index(df)
  - pt.sample(data_or_name="penguins", n=None, frac=None, seed=None)
  - pt.sample_data (Mapping of bundled datasets)
  - pt.validate_pipeline(pipeline, source, **kwargs) -> DataFrame (Zero-data pre-flight pipeline validator)
  - pt.check_dsl_string(verb, spec) -> list[str] (Validate DSL syntax without data)
  - pt.check_dsl_file(file_path) -> list[DSLDiagnostic] (Static DSL linter for Python file)
  - pt.check_dsl_paths(paths) -> tuple[int, list[DSLDiagnostic]] (Static DSL linter for paths)
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
    df.pt.head(...)
    df.pt.tail(...)
    df.pt.sample(...)
    df.pt.distinct(...)
    df.pt.dropna(...)
    df.pt.agg(...)
    df.pt.long(...)
    df.pt.wide(...)
    df.pt.pivot(...)
    df.pt.fillna(...)
    df.pt.cols(...)
    df.pt.glimpse(...)
    df.pt.freq(...)
    df.pt.hist(...)
    df.pt.bar(...)
    df.pt.scatter(...)
    df.pt.corr(...)
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
Filters DataFrame rows based on string expressions, plain dictionaries,
or callables.

Signature:
  pt.filter(df: DataFrame, *args: Any, params: dict[str, Any] | None = None) -> DataFrame
  df.filter(*args: Any, params: dict[str, Any] | None = None) -> DataFrame

Calling Styles:
  1. String Expressions (matches CLI -filter):
     df.filter("body_mass_g > 5000 and species == 'Gentoo'")
     df.filter("[bill length mm] > 40")   # Bracketed spaced columns
     df.filter("exposure > limit")        # Bare column-to-column comparison
     df.filter("tranche_id == deal_id")
     df.filter("sex.is_not_null()")       # Pure Polars null checks
     df.filter("score.is_nan()")          # IEEE 754 float NaN checks
  2. Plain Dictionaries:
     df.filter({"species": "Gentoo"})
     df.filter({"body_mass_g": (">", 5000)})
     df.filter({"species": ["Adelie", "Chinstrap"]})
     df.filter({"sex": "is_null()"})                              # Canonical null check
     df.filter({"score": "is_nan()"})                             # Canonical NaN check
     df.filter({"body_mass_g": ("between", 3000, 4000)})          # Option 1 range
     df.filter({"body_mass_g": ((">=", 3000), ("<=", 4000))})    # Option 2 range
  3. Callables / Lambdas:
     df.filter(lambda d: d["body_mass_g"] > 5000)

Supported Condition Types & Operators:
  - Equality:
    "species == 'Gentoo'"  (Strictly requires '=='; single '=' raises diagnostic error)
    {"species": "Gentoo"}
  - Membership (in list):
    "species in ['Adelie', 'Gentoo']"
    {"species": ["Adelie", "Gentoo"]}
  - Exclusion (not in list):
    "species not in ['Gentoo']"
    {"sex": ("not in", ["Male"])}
  - Comparison Operators:
    Supported operators: '>', '>=', '<', '<=', '==', '!='
    As string condition: "body_mass_g > 5000"
    As tuple condition:  {"body_mass_g": (">", 5000)}
  - Ranges & Intervals:
    Option 1 ('between'):       {"body_mass_g": ("between", 3500, 4500)}
    Option 2 (operator tuples): {"body_mass_g": ((">=", 3500), ("<=", 4500))}
    String expression:          "body_mass_g >= 3500 and body_mass_g <= 4500"
  - String Accessor Operations:
    Prefix match:        {"species": ("startswith", "Ad")}
    Multi-prefix match:  {"species": ("startswith", ["Ad", "Ge"])}
    Suffix match:        {"species": ("endswith", "strap")}
    Substring match:     {"species": ("contains", "adel")}
    Regex match:         {"species": ("regex", r"^[AB]")}
  - Null & NaN Checks:
    String expressions:  "sex.is_null()" or "sex.is_not_null()"
    Float NaN checks:    "score.is_nan()" or "score.is_not_nan()"
    Dictionaries:        {"sex": "is_null()"} or {"score": "is_nan()"}
    (Strict: Parentheses '()' strictly required; bare words without parens like 'is_null' or 'nan' and None/float('nan') raise ValueError)

Strict Syntax Rules & Error Diagnostics:
  1. No keyword arguments: df.filter(species="Gentoo") raises TypeError. Use '==' in strings or dicts.
  2. Single '=' disallowed: df.filter("species = 'Gentoo'") raises an explicit error reminding you that '=' is for mutate.
  3. No string-mashed ranges: Use clean operator tuples ((">=", 3000), ("<=", 4000)).
  4. Bare column-to-column comparison: "exposure > limit" works directly without col() wrapper.
  5. SQL 'is null' disallowed: df.filter("sex is null") raises an explicit error pointing to 'sex.is_null()' or dict {'sex': 'is_null()'}. Use -sql for SQL syntax.
  6. Typo suggestions: If a column name is misspelled, filter() raises a KeyError with fuzzy match suggestions.


4.2. pt.by() / df.pt.by() — Single-Shot Scoped Grouping
--------------------------------------------------------------------------------
Sets active grouping state on a DataFrame. In pytae, grouping is strictly SINGLE-SHOT:
verbs (`mutate`, `agg`, `head`, `tail`) NEVER accept `by=`. They inherit active grouping 
strictly from `pt.by()`. If passed `by=`, verbs immediately raise a `TypeError`.

Signature:
  pt.by(df: DataFrame, *cols: str) -> GroupedDataFrame
  df.pt.by(*cols: str) -> GroupedDataFrame

Key Rules & Behaviors:
  - Single-Shot Scoped Grouping: Grouping applies strictly to the immediate next operation.
    Every operation (`mutate()`, `agg()`, `head()`, `tail()`) automatically ungroups upon completion,
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
  - Positional Negation: Pass names prefixed with `!` (or `-` / `~`):
    df.pt.select("!species")                      # Drop species, keep the rest
    df.pt.select("!species", "!island")           # Drop multiple
    df.pt.select("!bill_length_mm:body_mass_g")   # Drop contiguous slice range
    df.pt.select("![col a]", "![col b]")          # Drop columns with spaces
  - Note: 'exclude=' is retired in favor of positional '!' negation.
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


4.6. head() / tail() — Group-Aware & Proportion-Aware Row Slicing
--------------------------------------------------------------------------------
Selects the first or last N rows (or proportion of rows via `prop=`), with boundary 
tie-breaking (`with_ties=True`) and complete group awareness via `df.by()`.
Extreme row selection (formerly `pick`) is achieved canonically by composing `arrange()` 
with `head()` or `tail()`:

Signature:
  df.head(n: int | str | None = None, *, prop: float | None = None, with_ties: bool = False) -> DataFrame
  df.tail(n: int | str | None = None, *, prop: float | None = None, with_ties: bool = False) -> DataFrame
  pt.head(df, n=None, *, prop=None, with_ties=False) -> DataFrame
  pt.tail(df, n=None, *, prop=None, with_ties=False) -> DataFrame

Calling Styles:
  # Basic slice overall (default n=5)
  df.head(5)
  df.tail(5)

  # Proportion slice (10% or float)
  df.head(prop=0.1)
  df.head("10%")

  # Extreme top/bottom rows via arrange
  df.arrange("body_mass_g desc").head(3)     # Heaviest 3 penguins
  df.arrange("body_mass_g").head(3)          # Lightest 3 penguins (or df.arrange("body_mass_g desc").tail(3))

  # Group-aware row slicing:
  (
      penguins
      .by("species")
      .arrange("body_mass_g desc")
      .head(1)
      .select("species", "island", "body_mass_g")
  )

  # Boundary ties included:
  df.arrange("body_mass_g desc").head(3, with_ties=True)


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


4.8. pt.count() / df.pt.count() — Frequency & Group Counting
--------------------------------------------------------------------------------
Counts occurrences of unique combinations of columns (or total rows).
Defaults to sorting descending by the count column (`sort=True`, `name="n"`).

Signature:
  pt.count(df: DataFrame, *cols: str, sort: bool = True, name: str = "n") -> DataFrame
  df.count(*cols: str, sort: bool = True, name: str = "n") -> DataFrame
  df.by(*cols).count(sort: bool = True, name: str = "n") -> DataFrame

Calling Styles:
  df.count("species")                     # Count by column, sorted descending by n
  df.count("species", "island")           # Count combinations of columns
  df.count("species", sort=False)         # Count preserving original encounter order
  df.count("species", name="total")       # Custom count column name
  df.by("species").count()                # Count within established grouping keys
  df.count()                              # Whole-table row count (1 row, column n)


4.9. pt.agg() / df.pt.agg() — Grouped Aggregation
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
         .pt.agg(avg_mass="body_mass_g:mean", total="count")
     )
  2. String Mapping Specification (Zero Dict Unpacking!):
     (
         tips
         .pt.by("smoker")
         .pt.agg("tip = mean, [total bill] = mean, total = count")
     )
  3. Whole-Frame Aggregations:
     (
         penguins
         .pt.by("species")
         .pt.agg("mean")
     )
  4. Whole-Table Grand Total (Ungrouped summary, 1 row):
     penguins.pt.agg("mean, n")
     penguins.pt.agg(avg_mass="body_mass_g:mean", total="count")

Key Rules & Behaviors:
  - NO REDUNDANT SELECT:
    You NEVER need a `pt.select(...)` or `-select` before `agg()`. Target columns and aggregation
    functions are declared directly inside `agg`.
  - Row Count ('count' / 'n'):
    Assigning a key with value 'count' (or legacy alias 'n') produces the row count: `total="count"` or `n="count"`.
  - Column Names:
    If a single aggregation is applied, the original name is preserved: `body_mass_g='mean'`.
    If multiple aggregations are applied, names become `{col}_{agg}`: `body_mass_g=['mean', 'max']`.
  - dropna Default:
    `dropna=False` by default preserves missing category groups across aggregations.


4.10. pt.long() / pt.wide() / df.pt.long() / df.pt.wide() — Reshaping (Pure 1-to-1)
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


4.11. pt.pivot() / df.pt.pivot() — 2D Pivot Tables (Excel-Style)
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
  v: Value column(s) to aggregate. Optional when counting (a="count").
  a: Aggregation function (default: "sum"; use "count" for row counts).
  dropna: Whether to drop NA categories in row/column keys (default: False).
  f_v: Scalar value for missing grid intersections (default: 0 for a="count").

Examples:
  df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")
  df.pt.pivot(r="island", c="species", a="count")


4.12. Other Utilities
--------------------------------------------------------------------------------
- pt.dropna(df, *cols, how=None, drop_nans=True) / df.pt.dropna(...):
  Drops rows with missing values (Arrow null and float NaN). Defaults to how='all' (Zero Data Loss) when cols is empty,
  or how='any' when columns are explicitly passed. Pass drop_nans=False to drop only Arrow nulls and preserve float NaNs.
- pt.cols(df, ascending=True):
  Returns list of column names (ascending=True for A-Z, False for Z-A, None for file order).
- pt.glimpse(df, width=None) / df.pt.glimpse(width=None):
  Prints transposed overview of DataFrame columns, dtypes, and sample values (returns self).
- pt.freq(df, col=None, *, dropna=False) / df.pt.freq(col=None, *, dropna=False):
  Computes frequency distribution DataFrame with counts, percentages, and ASCII bars.
- pt.hist(df, col=None, bins=10) / df.pt.hist(col=None, bins=10):
  Computes numeric histogram DataFrame with bin intervals, counts, and ASCII bars; accepts "col:bins" shorthand.
- pt.bar(df, col=None, val_col=None, *, width=None, dropna=False) / df.pt.bar(...):
  Computes categorical horizontal bar chart DataFrame with auto-frequency, numeric aggregation, or multi-column comparison.
- pt.scatter(df, x, y, *, width=None, height=None, braille=True, trend=False, stats=True) / df.pt.scatter(...):
  Renders terminal scatter plot with high-resolution braille 2x4 dot sub-character grid, regression trendline, and summary stats.
- pt.corr(df, *cols, method="pearson", pairwise=False, width=None) / df.pt.corr(...):
  Computes Pearson correlation matrix heatmap with terminal shading blocks or pairwise ranked correlation table.
- pt.join(df, right, on=None, how="inner", suffix="_right", suffixes=None, validate=None, coalesce=None) / df.pt.join(...) / df.join(...):
  Joins two DataFrames on keys using high-performance Polars engine. Supports how="inner"|"left"|"right"|"full"|"semi"|"anti"|"cross",
  colon notation on="id:uid", validation ("1:1", "1:m", "m:1", "m:m"), auto-discovery of common keys, and preserves LazyFrame query plans.
- pt.concat(dfs, how="vertical") / df.pt.concat(other, how="vertical") / df.concat(other, how="vertical"):
  Stacks DataFrames vertically (how="vertical", with automatic fallback to diagonal relaxed stacking on schema mismatches)
  or horizontally (how="horizontal", with automatic column deduplication).
- Transparent Polars Verb Delegation (__getattr__):
  Any native Polars method (e.g. .with_columns(), .slice(), .describe(), .explode()) can be called directly on pytae.DataFrame.
  Arguments are auto-unwrapped and results are rewrapped into pytae.DataFrame so method chains never break.
- pt.fillna(df, value=None, *cols, subset=None, nans=True, **kwargs) / df.pt.fillna(...):
  Imputes missing values (Arrow null and/or float NaN) across the entire DataFrame or specific columns.
- pt.mask(df, spec, *, salt="", key=None, vault=None, redact_val="***") / df.pt.mask(...):
  Masks sensitive columns using SHA-256 hashing ("hash"/"sha256"), character redaction ("redact"),
  authenticated symmetric encryption ("encrypt" with key="..."), or persistent pseudonym tokenization ("tokenize" with vault="...").
- pt.unmask(df, cols, *, key=None, vault=None) / df.pt.unmask(...):
  Reverses authenticated encryption (using key="...") or pseudonym tokenization (using vault="...") back to original values and data types.
- pt.clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False):
  Systematically sanitizes DataFrame header names.
- pt.safe_reset_index(df) / df.pt.safe_reset_index():
  Safely resets DataFrame index, raising an informative ValueError on collision.
- df.to_clip() / s.to_clip() / df.pt.to_clip():
  Copies DataFrame or Series to clipboard as TSV without index.


4.13. Plotter — Visualization & Dashboarding (Plotting API)
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


4.14. pt.repl() / df.pt.repl() / df.repl() — Interactive REPL Shell
--------------------------------------------------------------------------------
Launch an interactive Read-Eval-Print Loop (REPL) directly from Python:
  pt.repl(df)
  df.pt.repl()
  df.repl()

Features:
  - Drops into a stateful, interactive terminal session pre-loaded with the DataFrame.
  - Returns the final transformed DataFrame on exit (Ctrl-D or 'exit' / 'quit').
  - Full access to pipeline transformations, inspections, undo/redo, snapshots, and SQL.


4.15. pt.clear() / r.clear() — Terminal Screen Clearing
--------------------------------------------------------------------------------
Clear the terminal screen cleanly across all platforms:
  pt.clear()
  r.clear()  # Inside REPL / session object

Features:
  - Canonical clear command across POSIX (clear) and Windows (cls) terminals.
  - Legacy 'cls' aliases are removed from pytae public namespace to enforce "One and Only One Obvious Way".


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
  -glimpse              Transposed column overview with dtypes and sample values
  -meta                 Display zero-scan Parquet metadata
  -diff PATH            Compare schema, shape, null counts against another file
  -distinct [SPEC]      Drop duplicate rows across all or specified columns, with keep=first|last|false
  -count [SPEC]         Count occurrences of unique combinations of columns (or rows per group with -by)
  -sample [N]           Random sample of N rows (default 5)
  -seed N               Random seed for sampling
  -frac P               Sample fraction P (0.0 < P <= 1.0)
  -nrows, -limit N      Limit reading to first N rows of file
  -arrange SPEC         Sort rows by columns: e.g. -arrange "col1, col2 asc" or -arrange "col1 desc"

In-Terminal Visualizations:
  -freq COL             Render horizontal frequency distribution bars with counts & percentages
  -hist COL[:BINS]      Render in-terminal distribution histogram for a numeric column (default: 10 bins)
  -bar COL [VAL]        Render categorical horizontal bar chart (auto-frequency or numeric aggregation)
  -scatter X Y [OPTS]   Render in-terminal scatter plot with braille dots and optional trendline
  -corr [COLS] [OPTS]   Render in-terminal Pearson correlation matrix heatmap

Row Filtering & Slicing Flags:
  -filter CONDITIONS    pytae filter expressions (e.g. "species == 'Adelie' and body_mass_g > 3500")
  -dropna [COLS]        Drop rows with missing values (bare defaults to how=all; cols defaults to how=any)
  -fillna [VAL]         Impute missing values (e.g. -fillna 0 or -fillna "col:val")
  -head [LIMIT]         Extract first N rows, percentage (e.g. 10%), or ties ("3, ties=true"); group-aware with -by
  -tail [LIMIT]         Extract last N rows, percentage (e.g. 10%), or ties ("3, ties=true"); group-aware with -by

Column Transformation Flags:
  -select SPEC          Select columns (names, slices 'a:b', contains, dtypes, negative '!col', '-col', '~col')
  -mutate SPEC          Create/overwrite columns ("new_col = expr" or multi-column "[prefix](col1, col2)[suffix] = expr" using _ placeholder)
  -rename OLD:NEW,...   Rename columns using ':' delimiter (e.g. "a:alpha, b:beta")
  -clean_columns SPECS  Clean headers: "strip=True, fill='_', case='lower', dedupe=True"

Aggregation & Reshaping Flags:
  -by COLS              Grouping columns for -agg, -mutate, -head, -tail (e.g. -by species -arrange "mass desc" -head 1)
  -agg [SPECS]          Aggregate columns (e.g. -by species -agg "body_mass_g=mean, total=count" or -agg mean).
                        When -by is omitted, -agg computes a whole-table summary!
  -long [SPECS]         Melt numeric columns to rows: "c=variable, v=value"
  -wide [SPECS]         Pure 1-to-1 unmelting into headers: "c=variable, v=value"
  -pivot SPECS          2D pivot table: "r=species, c=island, v=body_mass_g, a=mean" (or counts: "r=species, c=island, a=count")

SQL & Multi-File Flags:
  -sql QUERY            Run Polars SQL on table 'data' (or @query.sql)
  -file SPECS           Multi-file mode: "file1.parquet=df1; file2.csv=df2"
  -join SPECS           Join files: "left=df1, right=df2, on=id, how=inner"
  -concat SPECS         Stack files: "frames='df1,df2'"

Data Masking, Encryption & Privacy Flags:
  -mask SPECS           Mask sensitive columns: e.g. "email=hash, ssn=encrypt, user=tokenize"
  -unmask COLS          Unmask, decrypt, or de-tokenize columns: e.g. "ssn" or "user"
  -key KEY              Secret password/key for reversible authenticated stream encryption & decryption
  -salt SALT            Custom salt string appended prior to SHA-256 hashing
  -vault PATH           File path to persistent tokenization vault (Parquet, CSV, NDJSON, or JSON)

Output & Formatting Flags:
  -o TARGET             Output destination (file path, format for batch conversion, or 'clip')
  -out_dir, -od DIR     Target directory for exported files
  -pager                Pipe output through system pager ($PAGER or less)
  -round N              Round numeric output columns to N decimal places

DSL Validation & Linting:
  check, -check [PATHS] Statically inspect Python scripts and check pytae DSL expressions for syntax errors


5.4. In-Terminal Visualizations (-freq, -hist, -bar, -scatter, -corr)
--------------------------------------------------------------------------------
1. Horizontal Frequency Bars (-freq):
   pytae penguins.parquet -freq species

2. In-Terminal Distribution Histogram (-hist):
   pytae penguins.parquet -hist body_mass_g:8

3. In-Terminal Categorical Bar Charts (-bar):
   pytae penguins.parquet -bar species
   pytae penguins.parquet -bar species body_mass_g
   pytae penguins.parquet -bar species "bill_length_mm,bill_depth_mm"

4. In-Terminal Scatter Plot (-scatter):
   pytae penguins.parquet -scatter bill_length_mm bill_depth_mm
   pytae penguins.parquet -scatter bill_length_mm body_mass_g trend=true

5. In-Terminal Pearson Correlation Heatmap (-corr):
   pytae penguins.parquet -corr
   pytae penguins.parquet -corr "bill_length_mm,bill_depth_mm,body_mass_g"
   pytae penguins.parquet -corr pairwise=true


5.5. Quoting & Delimiter Standards (: vs =) and Shell Quoting Rules
--------------------------------------------------------------------------------
1. Mapping / Translation uses COLON (`:`):
   - `-rename`: "old_col:new_col, col_b:col_beta"
2. Assignment / Specification uses EQUALS (`=`):
   - `-mutate`: "new_col = expression, mass_kg = body_mass_g / 1000"
   - `-clean_columns`: "strip=True, fill='_', case='lower'"
   - `-join`: "left=df1, right=df2, on=id, how=left"
   - `-agg`: "tip=mean, total_bill=mean, total=count"
3. Comparison & Filtering uses EQUALITY (`==`) and Boolean (`and`, `or`):
   - `-filter`: "species == 'Adelie' and body_mass_g > 3500"

4. Terminal Shell Quoting Rules (Bash / Zsh / PowerShell):
   - Wrap the entire flag argument in double quotes `""`: `-filter "..."`, `-mutate "..."`
   - Wrap string values inside the expression in single quotes `''`:
     `pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30', '2026-08-31']"`
     `pytae data.parquet -mutate "status = 'active'"`
   - Column identifiers must NOT be quoted: `body_mass_g > 4000` (correct) vs `'body_mass_g' > 4000` (incorrect).
   - If a column name has spaces, use square brackets: `[body mass g] > 4000` or `[total bill] = mean`.


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


5.8. Interactive REPL Shell (pytae -i, pytae <file> -i)
--------------------------------------------------------------------------------
Launch the stateful interactive REPL shell from the command line:
  pytae -i                              # Launch empty multi-table workbench
  pytae penguins.parquet -i             # Focused exploration on a single table
  pytae data.csv -encoding latin1 -i    # Preserves CLI reader options into REPL
  pytae -session analysis               # Launch or resume named persistent session
  pytae -sessions                       # List all saved persistent sessions on disk

Two Dedicated Operation Modes:
1. Mode 1: Single-Table Exploration (pytae [df: 344x7]>)
   - Focused on manipulating, filtering, and mutating a single active table.
   - Operations output concise confirmation headers (e.g. `-> df: 344 rows x 3 cols`).
   - Use `-head`, `-tail`, `-sample`, `-shape`, `-cols`, `-describe`, `-glimpse` for previews.

2. Mode 2: Multi-Table Workbench (pytae [df1, df2]>)
   - Load multiple datasets: `df1 = orders.parquet`, `df2 = customers.csv -dlim ";"`.
   - Subject-first operations: `df1 -filter "amount > 100"`, `df2 -head 5`.
   - Relational joins & assignments: `df3 = df1 -join df2 on=cust_id`.
   - Polars ANSI SQL engine: `df4 = -sql "SELECT df1.order_id, df2.name FROM df1 JOIN df2 ON df1.cust_id = df2.id"`.

State Management & Rollback Commands:
  - `undo`                    : Revert the last applied transformation.
  - `redo`                    : Re-apply the last undone transformation.
  - `reset`                   : Rollback to latest saved checkpoint (or initial dataset read if none).
  - `reset initial`           : Strictly rollback to initial dataset read (bypassing checkpoints).
  - `history`                 : Display audit log with sequential step numbers and *checkpoint: <name>* banners.

Session-Wide Checkpoints:
  - `checkpoint <name>`       : Freeze snapshot of entire workbench (all tables in session).
  - `checkpoints`             : List all saved checkpoints and their constituent tables.
  - `restore <name>`          : Restore entire workbench state back to named snapshot.

Persistent Sessions (~/.pytae/sessions/<name>/):
  - `session`                 : Display active session name, disk path, and checkpoints.
  - `session save <name>`     : Save or promote current session checkpoints under <name>.
  - `session load <name>`     : Switch to persistent session and restore its latest checkpoint.
  - `sessions`                : List all saved persistent sessions on disk.
  - `rm session <name>`       : Delete a saved persistent session directory from disk.
  * Note: Only checkpoints are persisted; uncheckpointed scratch tables/columns drop on exit.

Strict Deletion Syntax (Wildcard):
  - `rm <table_name>` / `rm df`: Remove specific table or active dataset from memory (undoable).
  - `rm *`                    : Remove all in-memory tables from memory (undoable).
  - `rm checkpoint <name>`    : Delete a named checkpoint snapshot.
  - `rm checkpoint *`         : Delete all saved checkpoint snapshots.
  * Note: Legacy '-all' or 'all' flags are rejected; use '*' wildcard syntax. Plural 'rm checkpoints' is rejected; use singular 'rm checkpoint'.

Terminal Control & Utilities:
  - `clear`                   : Clear the terminal screen.
  - `status`                  : Display active dataset name, dimensions, memory usage, undo depth.
  - `tables`                  : List all loaded tables in memory with shapes and memory footprints.
  - `<cmd> | <sh>`            : Pipe command output to external shell tools (e.g. `-cols | grep bill`).
  - `py <expr>`               : Evaluate arbitrary Python expression with `df` and `pldf` in scope.
  - `exit` / `quit` / Ctrl-D  : Exit REPL.


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
- `by` is never an argument inside verbs (`mutate`, `agg`, `head`, `tail`).
- Grouping must always be declared beforehand via `pt.by(df, *cols)` or `.pt.by(*cols)`.
- Verbs inherit grouping from `df.attrs['_pt_by']` and raise a `TypeError` if passed `by=`.

6.3. Why does every chained method call start on a new line?
------------------------------------------------------------
In all pytae code, pipelines, and Jupyter notebooks, every chained method call must start on 
its own new line:
```python
(
    penguins
    .by("species")
    .arrange("body_mass_g desc")
    .head(1)
    .select("species", "island", "body_mass_g")
)
```
This ensures readable git diffs, clean execution tracebacks, and syntactic consistency.

6.4. What are the key canonical verbs (filter, head/tail, distinct, count)?
-----------------------------------------------------------------
Pytae standardizes on canonical modern naming:
- `pt.filter()` / `df.filter()` / `-filter`: Replaces `qry`
- `head()` & `tail()` / `-head` & `-tail`: Group-aware, proportion-aware, tie-aware row slicing replacing legacy `pick`, `slice_max`, and `slice_min` (which have been completely removed with no backward compatibility).
- `pt.distinct()` / `df.distinct()` / `-distinct`: Standard deduplication verb (the legacy `dedupe` function and flag have been completely removed with no backward compatibility).
- `pt.count()` / `df.count()` / `-count`: Dedicated tallying and frequency counting verb; `count` is also the canonical counting operation in `agg()` (e.g. `total="count"`).

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
Pass negative prefix '!' (or '-' / '~'): `pt.select(df, "!species", "!island")` or in CLI `-select "!species,!island"`.
Note: `exclude=` is retired in favor of positional '!' negation.

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

6.15. How does terminal clearing and table removal work in the REPL?
--------------------------------------------------------------------------------
1. Canonical `clear`:
   To maintain "One and Only One Obvious Way", Pytae standardizes strictly on `clear`
   across the REPL prompt, CLI, and Python API (`pt.clear()`, `r.clear()`).
   Passing `cls`, `-cls`, `--cls`, `-clear`, or `--clear` produces an immediate clear error
   directing the user to `clear`.

2. Wildcard Deletion `rm *` and `rm checkpoint *`:
   Pytae standardizes on standard wildcard `*` syntax rather than ad-hoc flags (`-all`, `all`):
   - `rm *` removes all loaded tables from memory (fully undoable via `undo`).
   - `rm checkpoint *` deletes all saved checkpoint snapshots.
   - Singular `rm checkpoint <name>` is enforced strictly; plural `rm checkpoints` is redirected.

6.16. How do I get Top N records per group in the CLI? (Sequential -by)
--------------------------------------------------------------------------------
Chain sequential `-by` flags in the pipeline! In Pytae, `-by` is strictly single-shot: it scopes only the immediate next verb and resets.
Example: Get top 2 species by average body mass for each island from the penguins dataset:
```bash
pytae sample:penguins \
  -by island,species -agg "avg_mass=mean(body_mass_g)" \
  -arrange "island, avg_mass desc" \
  -by island -head 2
```
How it executes:
1. `-by island,species -agg "avg_mass=mean(body_mass_g)"`: Aggregates and collapses to island-species pairs. Grouping auto-resets.
2. `-arrange "island, avg_mass desc"`: Sorts globally by island and descending average mass.
3. `-by island -head 2`: Slices top 2 species for each island, then auto-resets.

In Python:
```python
(
    pt.sample("penguins")
    .by("island", "species")
    .agg(avg_mass="body_mass_g:mean")
    .arrange("island", "avg_mass desc")
    .by("island")
    .head(2)
)
```

In ANSI SQL (`-sql`):
```bash
pytae sample:penguins -sql "
  WITH ranked AS (
    SELECT island, species, AVG(body_mass_g) AS avg_mass,
           ROW_NUMBER() OVER (PARTITION BY island ORDER BY AVG(body_mass_g) DESC) AS rnk
    FROM data
    GROUP BY island, species
  )
  SELECT island, species, avg_mass FROM ranked WHERE rnk <= 2
"
```

6.17. Why did my filter fail with unrecognized token / missing quote in terminal?
--------------------------------------------------------------------------------
In Unix shells (bash, zsh), unquoted strings inside `-filter` expressions are treated as column identifiers by Polars.
- Error: `ColumnNotFound: column 'CAD' not found`
- Cause: You ran `-filter "currency == CAD"` instead of `-filter "currency == 'CAD'"`.
- Fix: Always quote string literals with inner single quotes:
  `pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30']"`

6.18. Error Message Catalog & Troubleshooting Index
--------------------------------------------------------------------------------
When encountering an error in Pytae, consult this catalog for the root cause and immediate fix:

| Exact Error Output | Root Cause | Immediate Fix |
|---|---|---|
| `unrecognized arguments: -sort` or `-sort_by` | Used deprecated/invalid sort flag | Use `-arrange "col desc"` |
| `unrecognized arguments: -qry` or `-query` | Used deprecated query flag | Use `-filter "expr"` |
| `unrecognized arguments: -dedupe` | Used deprecated dedupe flag | Use `-distinct "cols"` |
| `ColumnNotFound: column 'XYZ' not found` | Column name misspelled, wrong casing, or string literal unquoted | Check `-cols`; quote string values (`col == 'XYZ'`); use `[col name]` if name has spaces |
| `TypeError: pt.mutate() got an unexpected keyword argument 'by'` | Passed `by=` as a parameter inside a verb | Call `df.by("col").mutate(...)` first; `by` is strictly standalone |
| `AttributeError: ... has no attribute 'ungroup'` | Tried to ungroup a DataFrame | Pytae grouping is single-shot and auto-clearing; no `ungroup()` exists or is needed |
| `Invalid syntax: rm checkpoints` | Plural form used in REPL | Use singular: `rm checkpoint <name>` or `rm checkpoint *` |
| `Invalid syntax: cls / -clear` | Non-canonical clear used | Use canonical `clear` |
| `Missing argument for -agg` with grouped mutation | Grouped window mutation attempted with `-agg` | Use `-by col -mutate "mean_val = mean(col)"` to avoid collapsing rows |
| `PolarsComputeError: duplicate column name` | Operation produced colliding column names | Explicitly rename output columns (e.g. `avg_val = col:mean`) |


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
counts = penguins.pt.pivot(r="island", c="species", a="count")
```

```bash
# Equivalent CLI One-Liners:
pytae penguins.parquet -by "species,island" -agg "mass_mean=body_mass_g:mean, total=count"
pytae penguins.parquet -pivot "r=island, c=species, v=body_mass_g, a=mean"
pytae penguins.parquet -pivot "r=island, c=species, a=count"
```

Recipe 3: Group-Aware Row Slicing (pt.by + arrange + head)
--------------------------------------------------------------------------------
```python
import pytae as pt

tips = pt.sample("tips")

# 1. Heaviest tip per day via method chaining
top_daily = (
    tips
    .by("day")
    .arrange("tip desc")
    .head(1)
    .select("day", "total_bill", "tip")
)

# 2. Standalone functional slice overall
top_bill = pt.head(pt.arrange(tips, "total_bill desc"), 1)[["day", "total_bill", "tip"]]
```

```bash
# Equivalent CLI:
pytae tips.parquet -by day -arrange "tip desc" -head 1 -select "day,total_bill,tip"
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

Recipe 8: Interactive REPL Multi-Table Exploration & Snapshots
--------------------------------------------------------------------------------
```bash
# Launch interactive workbench with reader options
pytae -i

# Load multiple datasets with custom delimiters and encodings
pytae> df1 = orders.csv -encoding latin1 -dlim ";"
pytae> df2 = customers.parquet

# Subject-first manipulation
pytae [df1, df2]> df1 -filter "amount > 100"
pytae [df1, df2]> df1 -mutate "tax = amount * 0.08"

# Save named snapshot of all tables in session
pytae [df1, df2]> checkpoint baseline

# Perform join and SQL exploration
pytae [df1, df2]> df3 = df1 -join df2 on=cust_id
pytae [df1, df2, df3]> -sql "SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id"

# Revert to snapshot
pytae [df1, df2, df3]> restore baseline
Restored checkpoint 'baseline' (2 tables: df1, df2; active: df2).

# Clean removal using wildcard syntax
pytae [df1, df2]> rm checkpoint *
Cleared all saved checkpoints.
pytae [df1, df2]> rm *
Removed all tables from memory.
```

Recipe 9: Top N per Group across Chained Pipelines (CLI, Python & SQL)
--------------------------------------------------------------------------------
Finding the top N entities per group (e.g. top 2 species by average body mass for each island from penguins dataset):

CLI Pipeline (Sequential -by):
```bash
pytae sample:penguins \
  -by island,species -agg "avg_mass=mean(body_mass_g)" \
  -arrange "island, avg_mass desc" \
  -by island -head 2
```

Output:
| island    | species   |   avg_mass |
|:----------|:----------|-----------:|
| Biscoe    | Gentoo    |    5076.02 |
| Biscoe    | Adelie    |    3709.66 |
| Dream     | Chinstrap |    3733.09 |
| Dream     | Adelie    |    3688.39 |
| Torgersen | Adelie    |    3706.37 |

Python Fluent Method Chaining:
```python
import pytae as pt

top_species = (
    pt.sample("penguins")
    .by("island", "species")
    .agg(avg_mass="body_mass_g:mean")
    .arrange("island", "avg_mass desc")
    .by("island")
    .head(2)
)
```

ANSI SQL (-sql):
```bash
pytae sample:penguins -sql "
  WITH ranked AS (
    SELECT island, species, AVG(body_mass_g) AS avg_mass,
           ROW_NUMBER() OVER (PARTITION BY island ORDER BY AVG(body_mass_g) DESC) AS rnk
    FROM data
    GROUP BY island, species
  )
  SELECT island, species, avg_mass FROM ranked WHERE rnk <= 2
"
```

================================================================================
11. REPOSITORY DIRECTORY TREE
================================================================================

.
├── LICENSE
├── changelog.md
├── contributing.md
├── docs
│   ├── benchmarks
│   │   ├── README.md
│   │   ├── benchmark_summary.png
│   │   ├── benchmarks.ipynb
│   │   └── run_benchmarks.py
│   ├── cli_cheatsheet.md
│   ├── comparison_to_dplyr.md
│   ├── comparison_to_pandas.md
│   ├── comparison_to_sas.md
│   ├── pytae.md
│   ├── repl.md
│   ├── detailed_docs
│   │   ├── cli
│   │   │   ├── agg.md
│   │   │   ├── arrange.md
│   │   │   ├── clean_replace.md
│   │   │   ├── cli_plots.md
│   │   │   ├── diff.md
│   │   │   ├── distinct.md
│   │   │   ├── filter.md
│   │   │   ├── head_tail.md
│   │   │   ├── inspect.md
│   │   │   ├── join.md
│   │   │   ├── mask.md
│   │   │   ├── multi_file.md
│   │   │   ├── mutate.md
│   │   │   ├── other_utilities.md
│   │   │   ├── pivot.md
│   │   │   ├── read_write.md
│   │   │   ├── reshape.md
│   │   │   ├── select.md
│   │   │   └── sql.md
│   │   ├── library
│   │   │   ├── agg.ipynb
│   │   │   ├── arrange.ipynb
│   │   │   ├── distinct.ipynb
│   │   │   ├── filter.ipynb
│   │   │   ├── head_tail.ipynb
│   │   │   ├── join.ipynb
│   │   │   ├── mutate.ipynb
│   │   │   ├── other_utilities.ipynb
│   │   │   ├── pivot.ipynb
│   │   │   ├── read_write.ipynb
│   │   │   ├── reshape.ipynb
│   │   │   ├── select.ipynb
│   │   │   └── sql.ipynb
│   │   └── plotting
│   │       └── plotting.ipynb
│   └── pytae.md
├── pyproject.toml
├── readme.md
├── reference
│   └── pytae_reference.txt
├── scripts
│   ├── generate_reference.py
│   ├── run_notebooks.py
│   └── update_doc_outputs.py
├── src
│   └── pytae
│       ├── __init__.py
│       ├── __main__.py
│       ├── _parsing.py
│       ├── _text.py
│       ├── accessor.py
│       ├── cheatsheet.py
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
│       ├── mask.py
│       ├── other_utilities.py
│       ├── plotting.py
│       ├── polars_engine.py
│       ├── py.typed
│       ├── readers.py
│       ├── repl.py
│       ├── select.py
│       └── validation.py
└── tests
    ├── __init__.py
    ├── cli_helpers.py
    ├── conftest.py
    ├── test_accessor.py
    ├── test_agg.py
    ├── test_arrange_slice.py
    ├── test_cli_agg.py
    ├── test_cli_clean.py
    ├── test_cli_diff_tol.py
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
    ├── test_cli_subprocess.py
    ├── test_cli_visualizations.py
    ├── test_count.py
    ├── test_critique_fixes.py
    ├── test_fillna.py
    ├── test_import.py
    ├── test_join_concat.py
    ├── test_lazy.py
    ├── test_mask.py
    ├── test_mutate.py
    ├── test_pivot.py
    ├── test_plotter.py
    ├── test_polars_engine.py
    ├── test_readers.py
    ├── test_repl.py
    ├── test_select.py
    ├── test_shape.py
    ├── test_utilities.py
    ├── test_validation.py
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
    version = get_version()
    rendered_manual = MANUAL_TEXT.replace("__PYTAE_VERSION__", version)

    # rendered_manual contains sections 1 to 7 and section 11 (directory tree)
    # Split rendered_manual so sections 8, 9, 10 sit before the directory tree
    tree_marker = "================================================================================\n11. REPOSITORY DIRECTORY TREE"
    if tree_marker in rendered_manual:
        manual_pre, manual_tree = rendered_manual.split(tree_marker, 1)
        parts.append(manual_pre.strip())
    else:
        manual_pre = rendered_manual
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

    cheatsheet_md = REPO_ROOT / "docs" / "cli_cheatsheet.md"
    if cheatsheet_md.exists():
        parts.append("================================================================================")
        parts.append("CLI CHEATSHEET & COOKBOOK (docs/cli_cheatsheet.md)")
        parts.append("================================================================================\n")
        parts.append("################################################################################")
        parts.append(f"# FILE: {cheatsheet_md.relative_to(REPO_ROOT)}")
        parts.append("################################################################################")
        parts.append(cheatsheet_md.read_text(encoding="utf-8").rstrip() + "\n")

    repl_md = REPO_ROOT / "docs" / "repl.md"
    if repl_md.exists():
        parts.append("================================================================================")
        parts.append("INTERACTIVE REPL SHELL GUIDE (docs/repl.md)")
        parts.append("================================================================================\n")
        parts.append("################################################################################")
        parts.append(f"# FILE: {repl_md.relative_to(REPO_ROOT)}")
        parts.append("################################################################################")
        parts.append(repl_md.read_text(encoding="utf-8").rstrip() + "\n")

    # Section 10: Ecosystem Comparisons & Migration Guides (Pandas, dplyr, SAS)
    parts.append("================================================================================")
    parts.append("10. ECOSYSTEM COMPARISONS & MIGRATION GUIDES (Pandas, dplyr, SAS)")
    parts.append("================================================================================\n")
    for comp_name in ["comparison_to_pandas.md", "comparison_to_dplyr.md", "comparison_to_sas.md"]:
        comp_md = REPO_ROOT / "docs" / comp_name
        if comp_md.exists():
            parts.append("################################################################################")
            parts.append(f"# FILE: {comp_md.relative_to(REPO_ROOT)}")
            parts.append("################################################################################")
            parts.append(comp_md.read_text(encoding="utf-8").rstrip() + "\n\n")

    benchmarks_dir = REPO_ROOT / "docs" / "benchmarks"
    if benchmarks_dir.exists():
        bench_readme = benchmarks_dir / "README.md"
        if bench_readme.exists():
            parts.append("################################################################################")
            parts.append(f"# FILE: {bench_readme.relative_to(REPO_ROOT)}")
            parts.append("################################################################################")
            parts.append(bench_readme.read_text(encoding="utf-8").rstrip() + "\n\n")
        bench_py = benchmarks_dir / "run_benchmarks.py"
        if bench_py.exists():
            parts.append("################################################################################")
            parts.append(f"# FILE: {bench_py.relative_to(REPO_ROOT)}")
            parts.append("################################################################################")
            parts.append(bench_py.read_text(encoding="utf-8").rstrip() + "\n\n")

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

    # --------------------------------------------------------------------------
    # Generate Copilot-optimized Knowledge Base (Docs, Recipes, Guides, FAQs)
    # Excludes raw unit tests and internal source code to eliminate RAG vector noise!
    # --------------------------------------------------------------------------
    copilot_parts: list[str] = [
        manual_pre.strip(),
        "\n================================================================================",
        "8. DETAILED FEATURE DOCUMENTATION GUIDES (docs/detailed_docs/)",
        "================================================================================\n",
    ]
    for doc_path in detailed_docs:
        rel_path = doc_path.relative_to(REPO_ROOT)
        copilot_parts.append("################################################################################")
        if doc_path.suffix == ".ipynb":
            copilot_parts.append(f"# NOTEBOOK: {rel_path}")
            copilot_parts.append("################################################################################")
            copilot_parts.append(_format_notebook(doc_path).rstrip() + "\n")
        else:
            copilot_parts.append(f"# FILE: {rel_path}")
            copilot_parts.append("################################################################################")
            copilot_parts.append(doc_path.read_text(encoding="utf-8").rstrip() + "\n")

    if pytae_md.exists():
        copilot_parts.append("================================================================================")
        copilot_parts.append("9. MASTER DOCUMENTATION & ARCHITECTURE GUIDE (docs/pytae.md)")
        copilot_parts.append("================================================================================\n")
        copilot_parts.append("################################################################################")
        copilot_parts.append(f"# FILE: {pytae_md.relative_to(REPO_ROOT)}")
        copilot_parts.append("################################################################################")
        copilot_parts.append(pytae_md.read_text(encoding="utf-8").rstrip() + "\n")

    if cheatsheet_md.exists():
        copilot_parts.append("================================================================================")
        copilot_parts.append("CLI CHEATSHEET & COOKBOOK (docs/cli_cheatsheet.md)")
        copilot_parts.append("================================================================================\n")
        copilot_parts.append("################################################################################")
        copilot_parts.append(f"# FILE: {cheatsheet_md.relative_to(REPO_ROOT)}")
        copilot_parts.append("################################################################################")
        copilot_parts.append(cheatsheet_md.read_text(encoding="utf-8").rstrip() + "\n")

    if repl_md.exists():
        copilot_parts.append("================================================================================")
        copilot_parts.append("INTERACTIVE REPL SHELL GUIDE (docs/repl.md)")
        copilot_parts.append("================================================================================\n")
        copilot_parts.append("################################################################################")
        copilot_parts.append(f"# FILE: {repl_md.relative_to(REPO_ROOT)}")
        copilot_parts.append("################################################################################")
        copilot_parts.append(repl_md.read_text(encoding="utf-8").rstrip() + "\n")

    copilot_parts.append("================================================================================")
    copilot_parts.append("10. ECOSYSTEM COMPARISONS & MIGRATION GUIDES (Pandas, dplyr, SAS)")
    copilot_parts.append("================================================================================\n")
    for comp_name in ["comparison_to_pandas.md", "comparison_to_dplyr.md", "comparison_to_sas.md"]:
        comp_md = REPO_ROOT / "docs" / comp_name
        if comp_md.exists():
            copilot_parts.append("################################################################################")
            copilot_parts.append(f"# FILE: {comp_md.relative_to(REPO_ROOT)}")
            copilot_parts.append("################################################################################")
            copilot_parts.append(comp_md.read_text(encoding="utf-8").rstrip() + "\n\n")

    copilot_parts.append("================================================================================")
    copilot_parts.append("11. BUILD & CONFIGURATION (pyproject.toml)")
    copilot_parts.append("================================================================================\n")
    copilot_parts.append(pyproject_content)

    copilot_ref_path = REPO_ROOT / "reference" / "pytae_copilot_reference.md"
    copilot_ref_path.write_text("\n".join(copilot_parts), encoding="utf-8")
    print(f"Successfully generated {copilot_ref_path} ({len(copilot_ref_path.read_text(encoding='utf-8').splitlines())} lines)")

    # --------------------------------------------------------------------------
    # Generate Copilot Agent System Instructions Prompt Card
    # Ready to paste directly into Copilot Studio's System Prompt
    # --------------------------------------------------------------------------
    copilot_instructions_content = f"""# Pytae Microsoft Copilot Agent System Instructions

Copy and paste the text block below directly into the **Instructions** (System Prompt) field of your Microsoft Copilot Studio Custom Agent:

```text
You are the official expert AI assistant for Pytae (v{version}), a high-performance tabular data manipulation framework powered natively by Polars SIMD with seamless Pandas and Matplotlib integration.

You provide accurate, idiomatic, and concise Pytae commands (CLI `-flag`), Python method chains (`df.<verb>()`), and interactive REPL commands (`pytae -i`).

CRITICAL SYNTAX & USAGE RULES (NON-NEGOTIABLE):

1. CANONICAL VERBS ONLY:
   - Row filtering: ALWAYS `-filter` (CLI) or `df.filter()` (Python). NEVER use `-qry`, `-query`, or `df.query()`.
   - Row sorting: ALWAYS `-arrange` (CLI) or `df.arrange()` (Python). For descending sort use `col desc` (e.g. `-arrange "col desc"`). NEVER use `-sort`, `-sort_by`, or `-order`. NEVER use `-arrange "-col"`.
   - Deduplication: ALWAYS `-distinct` (CLI) or `df.distinct()` (Python). NEVER use `-dedupe` or `drop_duplicates()`.
   - Frequency / Counting: ALWAYS `-count` or `pt.count(df)` or `agg(total="count")`.
   - Reshaping: Pure unmelting is `wide()` / `-wide`; 2D aggregation matrix is `pivot()` / `-pivot`.

2. SHELL QUOTING STANDARD (BASH / ZSH / POWERSHELL):
   - In CLI commands, ALWAYS wrap expression arguments in double quotes `""` and wrap string values inside expressions in single quotes `''`:
     * Correct: pytae file.parquet -filter "species == 'Gentoo'"
     * Correct: pytae file.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30']"
     * Correct: pytae file.parquet -mutate "status = 'active'"
     * INCORRECT: pytae file.parquet -filter "species == Gentoo" (Fails with ColumnNotFound because unquoted tokens are treated as column identifiers).
   - Column identifiers must remain UNQUOTED (e.g. `body_mass_g > 3500`).
   - If a column name contains spaces, wrap it in square brackets: `[body mass g] > 3500`.

3. SINGLE-SHOT ZERO-POLLUTION GROUPING:
   - Grouping via `-by` (CLI) or `df.by()` (Python) is strictly single-shot. It scopes ONLY the immediate next verb (`mutate`, `agg`, `head`, `tail`, `count`), and then auto-resets.
   - Subsequent operations evaluate at whole-table scope.
   - There is NO persistent grouped state. There is NO `ungroup()` verb. Calling `df.ungroup()` is an error.
   - In Python, `by` is NEVER an argument inside verbs (e.g. `df.mutate(by="region")` raises TypeError). Always call `df.by("region").mutate(...)`.

4. TOP N PER GROUP & CHAINED PIPELINES:
   - To get top N entities per group in CLI, chain sequential `-by` operations:
     `pytae sample:penguins -by island,species -agg "avg_mass=mean(body_mass_g)" -arrange "island, avg_mass desc" -by island -head 2`
   - In Python:
     `(penguins.by("island", "species").agg(avg_mass="body_mass_g:mean").arrange("island", "avg_mass desc").by("island").head(2))`
   - In ANSI SQL:
     `pytae file -sql "WITH ranked AS (SELECT island, species, AVG(body_mass_g) AS avg_mass, ROW_NUMBER() OVER (PARTITION BY island ORDER BY AVG(body_mass_g) DESC) AS rnk FROM data GROUP BY island, species) SELECT island, species, avg_mass FROM ranked WHERE rnk <= 2"`

5. INTERACTIVE REPL (`pytae -i`):
   - REPL verbs require leading hyphens (`-filter`, `-mutate`, `-arrange`, `-head 5`).
   - Table inspection (`-head`, `-tail`, `-shape`, `-cols`) is non-destructive preview.
   - Deletion uses wildcard: `rm *` (all tables) or `rm checkpoint *` (all snapshots). Singular `rm checkpoint <name>`. Never use `rm checkpoints`.
   - Screen clearing is strictly `clear`. Never `cls`.

6. PREFER BUILT-IN SAMPLE DATASETS FOR IMMEDIATE RUNNABILITY:
   - When demonstrating functionality or providing examples, ALWAYS prefer using built-in sample datasets (e.g. `sample:penguins`, `sample:tips`, `sample:titanic`, `sample:flights`, `sample:diamonds`) instead of abstract placeholder paths (`file.parquet`, `data.csv`).
   - Built-in sample datasets require ZERO setup or downloads from the user:
     * CLI: `pytae sample:penguins -filter "species == 'Gentoo'" -head 3`
     * Python: `penguins = pt.sample("penguins")`
   - This empowers the user to immediately copy, paste, and run your command in their terminal or notebook to see real results!

When answering questions:
- Favor testing and demonstrating with built-in sample datasets (`sample:penguins`, `sample:tips`, etc.) as much as feasible so users can run code immediately.
- Provide both the CLI command and Python equivalent when appropriate.
- Explain the pipeline step-by-step.
- Ensure all string values in shell commands are properly quoted with single quotes inside double quotes.
```
"""
    copilot_instr_path = REPO_ROOT / "reference" / "pytae_copilot_instructions.md"
    copilot_instr_path.write_text(copilot_instructions_content, encoding="utf-8")
    print(f"Successfully generated {copilot_instr_path}")


if __name__ == "__main__":
    generate_reference()

