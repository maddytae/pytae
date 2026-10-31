================================================================================
PYTAE COMPREHENSIVE KNOWLEDGE BASE & AGENT TRAINING REFERENCE MANUAL
RELEASE VERSION: 3.12.8
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
          - pt.assert_() / df.pt.assert_() / df.assert_() (Data Quality Assertion)
          - pt.explode() / df.pt.explode() / df.explode() (List Unnesting)
          - pt.diff() / df.pt.diff() / df.diff() (Key-Aware Dataset Diffing)
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
    6.18. How do I change where REPL sessions and checkpoints are saved? (PYTAE_SESSIONS_DIR)
    6.19. Error Message Catalog & Troubleshooting Index
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
  pytae sample:penguins     -by island,species -agg "avg_mass=mean(body_mass_g)"     -arrange "island, avg_mass desc"     -by island -head 2
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

RULE 7: THE "TWIN PROOF" RULE (GROUND ON SAMPLE DATASETS)
- When a user asks a complex question about their own hypothetical or custom dataset (e.g. "top N customers by avg profit per zone in sales.parquet"):
  1. Direct Solution: FIRST, provide the exact tailored solution using their specified dataset and column names.
  2. Twin Proof on Sample Data: SECOND, ALWAYS provide a runnable "Twin Proof" on an equivalent built-in sample dataset (e.g. sample:penguins, sample:tips, sample:titanic) with an explicit 1-to-1 column mapping.
  3. Why? This provides two critical benefits:
     * Grounding: It anchors the agent's internal reasoning to verified canonical syntax, preventing hallucination.
     * Instant Dry-Run: It allows the user to copy-paste and verify the pipeline in their terminal with real table outputs in 10ms before touching production data!
  - Example:
    * User Query: "Top 2 customers by avg profit for each zone in sales.parquet"
    * Direct Solution:
      pytae sales.parquet         -by zone,customer -agg "avg_profit=mean(profit)"         -arrange "zone, avg_profit desc"         -by zone -head 2
    * Twin Proof on sample:penguins (zone -> island, customer -> species, profit -> body_mass_g):
      pytae sample:penguins         -by island,species -agg "avg_mass=mean(body_mass_g)"         -arrange "island, avg_mass desc"         -by island -head 2
================================================================================


1. OVERVIEW & CORE PHILOSOPHY
--------------------------------------------------------------------------------
Package: pytae (Current Release Version: 3.12.8)

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
Installation (PyPI: https://pypi.org/project/pytae/3.12.8/):
  pip install pytae==3.12.8
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
- pt.assert_(df, *conditions, params=None, **kwargs) / df.pt.assert_(...) / df.assert_(...):
  Enforces data quality and validation invariants across all rows without filtering. Raises ValidationError displaying the number of failing rows and sample violations if any condition fails; returns the unmodified DataFrame on success for chaining.
- pt.explode(df, *cols) / df.pt.explode(...) / df.explode(...):
  Flattens and unnests list, array, or iterable columns into separate rows, duplicating non-exploded column values.
- pt.diff(left, right, tol=0.0, rtol=0.0, *, on=None) / df.pt.diff(...) / df.diff(...):
  Compares schema, dimensions, null count variations, and cell values between two datasets. Use on="id" or on=["id", "date"] for key-aligned row comparison with added/removed key reporting and cell mismatches across matching keys, even when row counts or ordering differ.
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
  -diff PATH[,on=...]   Compare schema, shape, null counts against another file; optionally align by key (on=id) & set tolerance (tol=1e-4)
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
  -assert CONDITIONS    Enforce data quality invariants across all rows; halts pipeline with sample errors if violated
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
  -explode COLS         Unnest/flatten list or array columns into rows (e.g. -explode tags or -explode "items,qty")

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
pytae -file "orders.parquet=ord; customers.csv=cust"       -join "left=ord, right=cust, on=cust_id, how=inner"       -select "order_id,cust_name,amount" -head 10


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
  - `history -cli`            : Export reproducible one-shot CLI command string reconstructing the session.
  - `history -py`             : Export runnable Python script reconstructing the session with pt/DataFrame calls.

Session-Wide Checkpoints:
  - `checkpoint <name>`       : Freeze snapshot of entire workbench (all tables in session).
  - `checkpoints`             : List all saved checkpoints and their constituent tables.
  - `restore <name>`          : Restore entire workbench state back to named snapshot.

Persistent Sessions (~/.pytae/sessions/<name>/ or $PYTAE_SESSIONS_DIR/<name>/):
  - `session`                 : Display active session name, disk path, and checkpoints.
  - `session save <name>`     : Save or promote current session checkpoints under <name>.
  - `session load <name>`     : Switch to persistent session and restore its latest checkpoint.
  - `sessions`                : List all saved persistent sessions on disk.
  - `rm session <name>`       : Delete a saved persistent session directory from disk.
  * Note: Default location is ~/.pytae/sessions/<name>/. Set the PYTAE_SESSIONS_DIR environment variable to customize session storage location.
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
pytae sample:penguins   -by island,species -agg "avg_mass=mean(body_mass_g)"   -arrange "island, avg_mass desc"   -by island -head 2
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

6.18. How do I change where REPL sessions and checkpoints are saved? (PYTAE_SESSIONS_DIR)
--------------------------------------------------------------------------------
By default, Pytae saves interactive REPL sessions and checkpoints to `~/.pytae/sessions/<session_name>/`.
Each checkpoint is saved as an Arrow IPC binary file (`.ipc`) preserving exact Polars SIMD schemas and types.

To store REPL sessions in a custom directory (e.g. project workspace, shared drive, or scratch volume), set the `PYTAE_SESSIONS_DIR` environment variable:

In Unix Shell (bash / zsh):
```bash
export PYTAE_SESSIONS_DIR="$HOME/my_project/.pytae_sessions"
pytae -session project_work
```

In Fish Shell:
```fish
set -gx PYTAE_SESSIONS_DIR "$HOME/my_project/.pytae_sessions"
pytae -session project_work
```

In Windows PowerShell:
```powershell
$env:PYTAE_SESSIONS_DIR = "C:\my_project\.pytae_sessions"
pytae -session project_work
```

In Python:
```python
import os
os.environ["PYTAE_SESSIONS_DIR"] = "/path/to/custom/sessions"
import pytae as pt
pt.repl()
```

Verify in REPL:
Inside the interactive REPL, run `session` to inspect the active directory:
```
pytae> session
Active session: 'default' (2 checkpoints; location: /path/to/custom/sessions/default)
```

6.19. Error Message Catalog & Troubleshooting Index
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
pytae -file "customers.csv=c; orders.parquet=o"       -sql "select c.name, sum(o.amount) as total from c join o on c.cust_id = o.cust_id group by c.name"
```

Recipe 5: Multi-File Join, Concat, and Export
--------------------------------------------------------------------------------
```bash
# 1. Join files on shared key and filter
pytae -file "orders.parquet=ord; customers.csv=cust"       -join "left=ord, right=cust, on=cust_id, how=inner"       -filter "amount > 50"       -o filtered_orders.parquet

# 2. Concatenate monthly files and check row count
pytae -file "jan.parquet=m1; feb.parquet=m2; mar.parquet=m3"       -concat "frames='m1,m2,m3'"       -shape
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
mosaic = """
AB
CD
"""
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
pytae sample:penguins   -by island,species -agg "avg_mass=mean(body_mass_g)"   -arrange "island, avg_mass desc"   -by island -head 2
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
8. DETAILED FEATURE DOCUMENTATION GUIDES (docs/detailed_docs/)
================================================================================

################################################################################
# FILE: docs/detailed_docs/cli/agg.md
################################################################################
# CLI Feature Guide: Aggregations & Grouping

[← Back to Master Reference](../../pytae.md)

Group, aggregate, and calculate window statistics using pytae's unified `-by` + `-agg` framework and grouped mutations (`-by` + `-mutate`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Group Aggregations (`-by` + `-agg`)](#group-aggregations--by--agg)
  - [Single Function across Numeric Columns](#single-function-across-numeric-columns)
  - [Multiple Functions (`"mean,count"`)](#multiple-functions-meancount)
  - [Column-Specific Mapping](#column-specific-mapping)
  - [Named Outputs (`total = col:aggfunc`)](#named-outputs-total--colaggfunc)
  - [Top N per Group in Aggregated Pipelines](#top-n-per-group-in-aggregated-pipelines)
- [Whole-Table Summaries (Grand Totals)](#whole-table-summaries-grand-totals)
- [Grouped Transforms (`-by` + `-mutate`)](#grouped-transforms--by--mutate)
- [Handling Missing Group Keys](#handling-missing-group-keys)

---

## Overview & Differences

| Flag | Group Columns | Numeric Columns | Collapses Rows? | Description |
|---|---|---|---|---|
| `-by COLS -agg [SPEC]` | Declared via `-by` | Aggregated | **Yes** | Group summary ($N \to K$ rows) |
| `-agg [SPEC]` (no `-by`) | None (whole table) | Aggregated | **Yes** | Grand total (1 row) |
| `-by COLS -mutate "..."` | Declared via `-by` | Evaluated per group | **No** | Window transform without collapsing ($N \to N$ rows) |

---

<a id="group-aggregations--by--agg"></a>
## Group Aggregations (`-by` + `-agg`)

Specify grouping column(s) with `-by` (or `--by`), and aggregation function(s) with `-agg` (or `--agg`). Defaults to `sum` if `-agg` is given without an argument.

Supported function names: `mean`, `sum`, `std`, `min`, `max`, `median`, `count` (row count), etc.

> [!TIP]
> **Column Scoping in Aggregations**:
> - **Direct named targets**: When you declare specific columns inside `-agg` (e.g. `-by species -agg "body_mass_g=mean, n=count"`), pytae automatically restricts the output to those columns and the grouping keys without needing a pre-`-select`.
> - **Bulk aggregations & column pruning**: When using bulk functions (e.g. `-agg mean` across all numeric columns) or working with wide files where you want to load only relevant columns into RAM, using `-select` beforehand (e.g. `-select "species,contains=mass" -by species -agg mean`) is completely valid and recommended for performance.

### Single Function across Numeric Columns

Average body mass by species (specify the metric directly in `-agg` without a pre-`-select`):

```bash
pytae penguins.parquet -by species -agg body_mass_g=mean -round 1
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |        3700.7 |
| Chinstrap |        3733.1 |
| Gentoo    |        5076   |

### Multiple Functions (`"mean,count"`)

Compute mean and sample size simultaneously:

```bash
pytae penguins.parquet -by species -agg "body_mass_g=mean, n=count" -round 1
```

**Output:**

| species   |   body_mass_g |   n |
|:----------|--------------:|----:|
| Adelie    |        3700.7 | 152 |
| Chinstrap |        3733.1 |  68 |
| Gentoo    |        5076   | 124 |

### Column-Specific Mapping

Assign different aggregate functions to specific columns:

```bash
pytae penguins.parquet \
  -by species \
  -agg "body_mass_g = mean, flipper_length_mm = max, n = count" \
  -round 1
```

**Output:**

| species | body_mass_g | flipper_length_mm | n |
|:---|---:|---:|---:|
| Adelie | 3700.7 | 210.0 | 152 |
| Chinstrap | 3733.1 | 212.0 | 68 |
| Gentoo | 5076.0 | 231.0 | 124 |

### Named Outputs (`total = col:aggfunc`)

Rename aggregated outputs cleanly using `new_name = col:aggfunc`:

```bash
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = body_mass_g:mean, max_mass = body_mass_g:max, count = count" \
  -round 1
```

**Output:**

| species   |   avg_mass |   max_mass |   count |
|:----------|-----------:|-----------:|--------:|
| Adelie    |     3700.7 |       4775 |     152 |
| Chinstrap |     3733.1 |       4800 |      68 |
| Gentoo    |     5076   |       6300 |     124 |

### Columns with Spaces (`[col]`)

Columns with spaces can be enclosed in square brackets `[col]` anywhere in `-by` and `-agg`:

```bash
pytae tips.parquet \
  -filter "day in ['Sat', 'Sun'] and time == 'Dinner' and size >= 2 and total_bill > 10" \
  -rename "total_bill:[total bill]" \
  -by smoker \
  -agg "tip = mean, [total bill] = mean, n = count"
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| No       | 3.22546 |      20.7059 |  97 |
| Yes      | 3.08772 |      23.2323 |  57 |

Multiple grouping columns can be passed comma-separated: `-by "species,island"` or `-by "[group a],[group b]"`.

### Top N per Group in Aggregated Pipelines

To compute group-level metrics and then filter for the top $N$ entities within a higher-level group (e.g. top 2 species by average body mass for each island), chain sequential `-by` operations:

```bash
pytae sample:penguins \
  -by island,species -agg "avg_mass=mean(body_mass_g)" \
  -arrange "island, avg_mass desc" \
  -by island -head 2
```

**Output:**

| island    | species   |   avg_mass |
|:----------|:----------|-----------:|
| Biscoe    | Gentoo    |    5076.02 |
| Biscoe    | Adelie    |    3709.66 |
| Dream     | Chinstrap |    3733.09 |
| Dream     | Adelie    |    3688.39 |
| Torgersen | Adelie    |    3706.37 |

> [!NOTE]
> **Single-Shot Zero-Pollution Scoping**: In Pytae CLI, `-by` is strictly single-shot and auto-clears after the verb that consumes it:
> 1. `-by island,species` scopes `-agg "avg_mass=mean(body_mass_g)"` and collapses rows to island-species pairs.
> 2. `-arrange "island, avg_mass desc"` sorts all rows globally (whole-table scope).
> 3. `-by island` scopes `-head 2`, slicing the top 2 rows for each island before resetting to clean ungrouped state.

Alternatively, you can compute this using ANSI SQL via `-sql`:

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

---

## Whole-Table Summaries (Grand Totals)

Omit `-by` to compute a grand total across all rows (producing a 1-row summary):

```bash
pytae penguins.parquet -agg "body_mass_g = mean, count = count" -round 1
```

**Output:**

|   body_mass_g |   count |
|--------------:|--------:|
|        4201.8 |     344 |

Or compute an aggregation across all numeric columns at once:

```bash
pytae penguins.parquet -agg mean -round 1
```

**Output:**

| bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g |
|---:|---:|---:|---:|
| 43.9 | 17.2 | 200.9 | 4201.8 |

---

<a id="grouped-transforms--by--mutate"></a>
## Grouped Transforms (`-by` + `-mutate`)

Appends group statistics and window calculations back to every individual row without collapsing the dataset (equivalent to Pandas `transform` or SQL `OVER (PARTITION BY ...)`).

Grouped mutations are evaluated per group by combining `-by` with `-mutate`:
- Available aggregations in `-mutate`: `mean(col)`, `sum(col)`, `median(col)`, `min(col)`, `max(col)`, `std(col)`, `var(col)`, `count()` (or `count(col)`).
- Multiple sequential calculations can be combined in one `-mutate` flag.
- Custom target column names are supported freely.

```bash
# Calculate maximum species mass and deviation from maximum without collapsing rows
pytae penguins.parquet \
  -select "species,sex,body_mass_g" \
  -by species \
  -mutate "max_mass = max(body_mass_g), diff = body_mass_g - max_mass" \
  -head 4
```

**Output:**

| species   | sex    |   body_mass_g |   max_mass |   diff |
|:----------|:-------|--------------:|-----------:|-------:|
| Adelie    | Male   |          3750 |       4775 |  -1025 |
| Adelie    | Female |          3800 |       4775 |   -975 |
| Adelie    | Female |          3250 |       4775 |  -1525 |
| Adelie    | nan    |           nan |       4775 |    nan |

For more examples including group counts (`count()`), multi-column grouping, and spaced column names, see the [Mutating & Computing Guide](mutate.md#grouped-mutations--by--mutate).


---

## Handling Missing Group Keys

By default, missing values (`NaN`) in group columns form their own group (`dropna=false`) to prevent silent data loss:

```bash
# Keep missing sex as its own group (default)
pytae penguins.parquet -by sex -agg "body_mass_g=mean, dropna=false" -round 1
```

**Output:**

| sex | body_mass_g |
|:---|---:|
| Female | 3862.3 |
| Male | 4545.7 |
| NaN | 4005.6 |

To drop rows with missing group keys, either specify `dropna=true` inside the `-agg` mapping or chain the top-level `-dropna` flag:

```bash
# In-spec dropna=true
pytae penguins.parquet -by sex -agg "body_mass_g=mean, dropna=true" -round 1
```

**Output:**

| sex | body_mass_g |
|:---|---:|
| Female | 3862.3 |
| Male | 4545.7 |

```bash
# Or chain -dropna beforehand
pytae penguins.parquet -dropna sex -by sex -agg mean -round 1
```

**Output:**

| sex | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g |
|:---|---:|---:|---:|---:|
| Female | 42.1 | 16.4 | 197.4 | 3862.3 |
| Male | 45.9 | 17.9 | 204.5 | 4545.7 |

################################################################################
# FILE: docs/detailed_docs/cli/arrange.md
################################################################################
# CLI Feature Guide: Row Sorting (`-arrange`)

[← Back to Master Reference](../../pytae.md)

Order DataFrame rows by one or more columns with full support for descending orders (`desc`) and bracket notation for columns with spaces.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Ascending Sort (Default)](#ascending-sort-default)
- [Descending Sort (`desc`)](#descending-sort-desc)
- [Multi-Column Sorting](#multi-column-sorting)
- [Columns With Spaces (`[col name]`)](#columns-with-spaces-col-name)

---

## Overview & Quick Reference

| Flag | Syntax / Format | Description |
|---|---|---|
| `-arrange SPEC` | `col` | Sort ascending (default) |
| `-arrange SPEC` | `col desc` | Sort descending |
| `-arrange SPEC` | `col1, col2 desc` | Multi-column hierarchical sort |
| `-arrange SPEC` | `"[col name] desc"` | Sort columns containing spaces |

---

## Ascending Sort (Default)

By default, `-arrange` sorts rows in ascending order:

```bash
# Sort ascending by body mass
pytae penguins.parquet -arrange body_mass_g -select "species,island,body_mass_g" -head 5
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Chinstrap | Dream | 2700.0 |
| Adelie | Biscoe | 2850.0 |
| Adelie | Biscoe | 2850.0 |
| Adelie | Torgersen | 2900.0 |
| Adelie | Dream | 2900.0 |

---

## Descending Sort (`desc`)

In line with *"one and only one obvious way"*, specify descending order explicitly by appending `desc` or `descending` to the column name:

```bash
# Explicit 'desc'
pytae penguins.parquet -arrange "body_mass_g desc" -select "species,island,body_mass_g" -head 5
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Gentoo | Biscoe | 6300.0 |
| Gentoo | Biscoe | 6050.0 |
| Gentoo | Biscoe | 6000.0 |
| Gentoo | Biscoe | 6000.0 |
| Gentoo | Biscoe | 5950.0 |

---

## Multi-Column Sorting

Pass multiple columns separated by commas:

```bash
# Species ascending, body mass descending
pytae penguins.parquet -arrange "species, body_mass_g desc" -select "species,island,body_mass_g" -head 6
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Adelie | Biscoe | 4775.0 |
| Adelie | Biscoe | 4725.0 |
| Adelie | Torgersen | 4700.0 |
| Adelie | Torgersen | 4675.0 |
| Adelie | Dream | 4650.0 |
| Adelie | Dream | 4600.0 |

---

## Columns With Spaces (`[col name]`)

Columns with spaces are cleanly referenced using square brackets:

```bash
pytae sales.csv -arrange "[annual revenue] desc" -head 5
```

**Output:**

| annual revenue | region |
|---:|:---|
| 450000 | Central |
| 310000 | East |
| 180000 | Pacific |
| 120000 | North |
| 95000 | West |

################################################################################
# FILE: docs/detailed_docs/cli/clean_replace.md
################################################################################
# CLI Feature Guide: Data Cleaning, Imputation, & Renaming

Standardize messy column headers (`-clean` / `-clean_columns`), impute missing values (`-fillna`), drop missing rows (`-dropna`), rename columns (`-rename`), and recode cell values via `-mutate "map(...)"`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Header Standardization](#header-standardization)
  - [Supported Pipeline Steps](#supported-pipeline-steps)
  - [Cleaning Examples](#cleaning-examples)
- [Missing Value Imputation (`-fillna`)](#missing-value-imputation--fillna)
- [Dropping Missing Values](#dropping-missing-values)
- [Column Renaming (`-rename`)](#column-renaming--rename)
- [Recoding Categorical Values (`-mutate "map(...)"`)](#recoding-categorical-values--mutate-map)

---

## Overview & Quick Reference

| Flag | Scope | Delimiter / Syntax | Description |
|---|---|---|---|
| `-clean` / `-clean_columns` | Column headers | `,` / `=` | Standardizes headers (strip, squeeze, fill, case, dedupe) |
| `-fillna` | Cell contents | Scalar or `val=..., cols=...` | Replaces null / NaN with replacement values |
| `-dropna` | Rows | Bare or `col1, col2` | Drops null / NaN rows (Zero Data Loss default) |
| `-rename` | Column headers | `old:new` | Explicitly renames column names |
| `-mutate "col = map(...)"` | Cell contents | Dictionary mapping | Vectorized value recoding via Polars engine |

---

## Header Standardization

### Supported Pipeline Steps

Clean messy column names automatically. Options execute in this order:
1. `strip`: Remove leading and trailing whitespace.
2. `strip_special`: Remove non-alphanumeric punctuation (except `_`).
3. `squeeze`: Collapse multiple consecutive spaces into a single space.
4. `fill[=STR]`: Replace spaces with a separator (default `_`).
5. `case=lower|upper|proper`: Transform casing.
6. `dedupe`: Append suffixes (`_1`, `_2`) to disambiguate duplicated column names.

### Cleaning Examples

```bash
# Clean leading spaces, punctuation, lowercase, and replace spaces with underscores:
pytae messy.parquet -clean_columns "strip,strip_special,case=lower,fill=_"
```

**Before:**
```text
  Old Name    Score %      Status
hello world      10.5 draft_stage
    bad_val       NaN    approved
        NaN      30.2 draft_stage
```

**After:**
```text
   old_name  score_      status
hello world    10.5 draft_stage
    bad_val     NaN    approved
        NaN    30.2 draft_stage
```

---

## Missing Value Imputation (`-fillna`)

Replace missing values (`null` and `NaN`) across the dataset or within specific columns:

```bash
# Impute all numeric missing values with 0
pytae dataset.parquet -fillna 0 -head 5

# Impute specific columns
pytae dataset.parquet -fillna "val='Unknown', cols='status, category'" -head 5

# Only replace Arrow nulls (leave float NaNs intact)
pytae dataset.parquet -fillna "val=0, nans=false" -head 5
```

---

## Dropping Missing Values

Pytae adheres to a **Zero Data Loss by Default** philosophy for missing values (Arrow `null`s and IEEE-754 float `NaN`s).

- **Bare `-dropna`**: Defaults to `how="all"`. Drops **only completely empty rows** (rows where every column is null/NaN), preserving partially populated rows.
- **Targeted `-dropna "col1, col2"`**: Defaults to `how="any"`. Drops rows missing *any* of the specified columns.
- **Explicit `how=any`**: Drops rows containing *any* missing value across all columns.
- **Optional `drop_nans=false`**: Drops only Arrow nulls, preserving float IEEE-754 NaNs.

```bash
# Bare flag defaults to how='all' (Zero Data Loss: keeps 344 rows in penguins)
pytae penguins.parquet -dropna -shape
# (344, 7)

# Drop rows missing specific required columns (344 -> 342 rows)
pytae penguins.parquet -dropna body_mass_g -shape
# (342, 7)

# Explicit how=any drops rows with any missing value (344 -> 333 rows)
pytae penguins.parquet -dropna how=any -shape
# (333, 7)
```

> [!NOTE]
> - **Top-level `-dropna [COLS]`**: Operates as a row filter. Bare calls use `how="all"` (Zero Data Loss), while targeted calls use `how="any"` on the specified columns. Both Arrow `null` and float `NaN` are cleaned by default.
> - **Scoped `dropna=bool`**: In `-pivot` and `-agg`, default is `dropna=false` (retains missing group keys without silent data loss). Pass `dropna=true` inside the spec (e.g. `-agg "a=mean, dropna=true"`) to exclude NA groups.

---

## Column Renaming (`-rename`)

Rename columns explicitly at any point in the pipeline using the `old:new` mapping convention:

```bash
pytae dataset.parquet -rename "Status:review_status,Old Name:clean_name"
```

**Output:**
```text
 clean_name    Score % review_status
hello world       10.5   draft_stage
    bad_val        NaN      approved
        NaN       30.2   draft_stage
```

---

## Recoding Categorical Values (`-mutate "map(...)"`)

Recode cell values cleanly via vectorized dictionary mapping directly in `-mutate`:

```bash
# 1. Two-argument: recode mapped values, preserve unmapped values intact
pytae penguins.parquet -mutate "species_code = map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})" -head 5

# 2. Three-argument with constant fallback: replace unmapped rows with 'Other'
pytae penguins.parquet -mutate "species_code = map(species, {'Adelie': 'AD'}, 'Other')" -head 5

# 3. Three-argument with column fallback: pull fallback value from another column
pytae deals.parquet -mutate "broker = map(deal_type, {'Direct': 'DIR'}, broker_code)" -head 5
```

################################################################################
# FILE: docs/detailed_docs/cli/cli_plots.md
################################################################################
# CLI Feature Guide: CLI Plotting & Visualizations (`cli_plots`)

[← Back to Master Reference](../../pytae.md)

`pytae` includes first-class visualization and plotting capabilities directly from the command line:
- **Terminal In-Line Visualizations**: Instant ASCII and Braille charts rendered directly in console scrollback (`-freq`, `-hist`, `-bar`, `-scatter`, `-corr`).
- **Command-Line Figure Plotting**: Full Matplotlib publication-grade plotting directly from CLI pipelines via `-plot` and `-finalize`, with automatic figure export (`-o plot.png`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Terminal Frequency Distribution (`-freq`)](#terminal-frequency-distribution--freq)
- [Terminal Numeric Histograms (`-hist`)](#terminal-numeric-histograms--hist)
- [Terminal Metric Value Bars (`-bar`)](#terminal-metric-value-bars--bar)
- [Terminal 2D Braille Scatter Plot (`-scatter`)](#terminal-2d-braille-scatter-plot--scatter)
- [Terminal Correlation Matrix & Pairs (`-corr`)](#terminal-correlation-matrix--pairs--corr)
- [Headless Figure Plotting](#headless-figure-plotting)
  - [1. Single Plots with Explicit Pipeline Aggregation](#1-single-plots-with-explicit-pipeline-aggregation)
  - [2. Multi-Dimensional Categorical Grouping (`by=`)](#2-multi-dimensional-categorical-grouping-by)
  - [3. Distribution Plots (`box`, `kde`, `hist`)](#3-distribution-plots-box-kde-hist)
  - [4. Custom Styling & Finalization (`-finalize`)](#4-custom-styling--finalization--finalize)
  - [5. Exporting Figures (`-o`)](#5-exporting-figures--o)
- [Interactive Viewing](#interactive-viewing)

---

## Overview & Quick Reference

| Flag | Category | Purpose | Example |
|---|---|---|---|
| `-freq COL` | Terminal ASCII | Categorical distribution bar chart | `pytae penguins.parquet -freq species` |
| `-hist COL[:BINS]` | Terminal ASCII | Numeric binned distribution histogram | `pytae penguins.parquet -hist body_mass_g:8` |
| `-bar [SPEC]` | Terminal ASCII | Metric value magnitude bars across categories | `pytae penguins.parquet -by island -agg avg=mass:mean -bar` |
| `-scatter [SPEC]` | Terminal Braille | 2D in-terminal high-res bivariate scatter plot | `pytae penguins.parquet -scatter "bill_len:bill_depth"` |
| `-corr [SPEC]` | Terminal ASCII | Pairwise correlation matrix or ranked pairs | `pytae penguins.parquet -corr pairs` |
| `-plot SPEC` | Figure Plot | Draw bar, line, scatter, box, area, kde | `pytae data.csv -plot "kind=bar,x=cat,y=val"` |
| `-finalize SPEC` | Figure Style | Title, axis labels, styles, tight layout | `pytae data.csv -finalize "title='Sales',style=dark_background"` |
| `-o TARGET.ext` | Export | Save figure to PNG, SVG, PDF, etc. | `-o chart.png -out_dir ./figures` |

---

## Terminal Frequency Distribution (`-freq`)

Render instant ASCII horizontal bars with exact counts and percentages for any categorical column:

```bash
pytae penguins.parquet -freq species
```

**Output:**
```text
species    count
Adelie       152  ████████████████████ (44.2%)
Gentoo       124  ████████████████     (36.0%)
Chinstrap     68  █████████            (19.8%)
```

Respects `-dropna` (excludes missing categories from the count and distribution):
```bash
pytae penguins.parquet -dropna sex -freq sex
```

**Output:**
```text
   sex  Count                 Distribution
  Male    168 ████████████████████ (50.5%)
Female    165 ████████████████████ (49.5%)
```

---

## Terminal Numeric Histograms (`-hist`)

Inspect numeric distributions, spreads, and peaks directly in your console:

```bash
pytae penguins.parquet -hist body_mass_g:6
```

**Output:**
```text
body_mass_g            count
[2700.0, 3300.0)          63  ████████████
[3300.0, 3900.0)         105  ████████████████████
[3900.0, 4500.0)          69  █████████████
[4500.0, 5100.0)          57  ███████████
[5100.0, 5700.0)          40  ████████
[5700.0, 6300.0]           8  ██
```

- If bins count is omitted (`-hist body_mass_g`), defaults to 10 bins.
- Automatically handles missing values and filters out non-numeric rows.

---

## Terminal Metric Value Bars (`-bar`)

While `-freq` visualizes row counts, `-bar` visualizes **pre-aggregated metric values** (such as averages, sums, or calculated ratios) directly in your terminal table.

### 1. Bare `-bar` with 2 Columns (Auto-detect)
When grouping and aggregating down to 2 columns (1 numeric, 1 non-numeric), bare `-bar` automatically targets the value:
```bash
pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean -bar
```

**Output:**
```text
┌───────────┬─────────────┬──────────────────────┐
│ island    ┆ avg_mass    ┆ Bar                  │
╞═══════════╪═════════════╪══════════════════════╡
│ Biscoe    ┆ 4716.017964 ┆ ████████████████████ │
│ Dream     ┆ 3712.903226 ┆ ████████████████     │
│ Torgersen ┆ 3706.372549 ┆ ████████████████     │
└───────────┴─────────────┴──────────────────────┘
```

### 2. Multi-Column Tables (Preserves Metadata)
Target a specific value column while preserving other grouping dimensions:
```bash
pytae penguins.parquet -by species,island -agg avg_mass=body_mass_g:mean -bar avg_mass
```

### 3. Percentages & Custom Bounds
Append percentage of total (`pct=true`) or set custom bounds (`limit=(min,max)`):
```bash
pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean -bar "pct=true"
pytae data.csv -bar "island:avg_mass,limit=(3000,5000),width=30"
```

---

## Terminal 2D Braille Scatter Plot (`-scatter`)

Inspect bivariate correlation, non-linear trends, and outliers directly inside your terminal using high-resolution Unicode Braille characters (2×4 subpixels per character cell):

```bash
pytae penguins.parquet -scatter "bill_length_mm:bill_depth_mm"
```

**Output:**
```text
 bill_depth_mm
    21.5 ┤     ⠠      ⠠⠠   ⠠ ⠄      ⠁                        
         │          ⡀  ⠠⠂    ⠐                ⠐   ⠈          
         │           ⡤ ⠄ ⠐ ⠌⠐      ⠁     ⢀ ⠠ ⢀⠁ ⡄⢀   ⢀       
         │      ⠄ ⠠⡀⢄  ⠐    ⠤⠄  ⠈  ⠄     ⠆ ⠄⠇ ⠠              
         │   ⠐  ⠠⠈ ⠄⠨⡀⠑⣄⠬⠄⠦⠃ ⠁⠘   ⢀⠠⠄     ⠂⢠⠘⢜⠐⠄             
         │    ⢀⡂  ⠂⠊⡐⣍ ⠈⡐⠐⠑⡹ ⠂⠖⢀    ⡈ ⠠  ⢀⢈ ⠒⢀⢀              
         │      ⠂⠁⠊⠂⠂⢀⠐⡂⠶⠈⠂⡀⠁ ⡀ ⠈ ⠐ ⠐⠂     ⠂⠐            ⠐   
    17.3 ┤    ⠄⠠ ⡁⢦ ⢀⢆⢠⠅⠅⢠⡄⠁ ⠐   ⠂ ⡢⠁⠐  ⠈ ⠐ ⠐  ⡄     ⢀      ⢀
         │       ⠡⠠⢈⠂⢀  ⠂ ⠰  ⠐⠠   ⢠  ⡠⠐⢀  ⠐  ⡀               
         │  ⠐   ⢀⠂⠂  ⠄               ⠂  ⠡⠂⢢⡃⡀⠉      ⠄        
         │ ⠄                     ⠁⠌ ⠘⡄⡄⠐⠈⠈⠁⣈⠈  ⠐ ⠁⠈          
         │                  ⡀  ⠈ ⡀⢀⠂⢕ ⠐⠊⠘⢘⠐⠃⠃                
         │                    ⡐⢂ ⠄⠊⢊⡒⡌⢘⠠⢃⠐ ⠠ ⢀               
         │                ⠠  ⠠⠄⠑⡂ ⠤⠆  ⠌                      
    13.1 ┤                  ⠈ ⡀⠁  ⠂ ⠌                        
         ┼──────────────────────────────────────────────────
          32.1                   45.9                   59.6  bill_length_mm

  Points: 342 (2 nulls excluded) | Corr (r): -0.235
```

- **Bare `-scatter`**: If the table contains exactly 2 numeric columns (e.g. after `-select "x,y"`), bare `-scatter` auto-selects them!
- Custom dimensions: `-scatter "x:y,width=60,height=20"`.

---

## Terminal Correlation Matrix & Pairs (`-corr`)

Compute Pearson or Spearman correlation coefficients across numeric columns with pairwise null handling:

### 1. Symmetric Correlation Matrix (Default)
```bash
pytae penguins.parquet -select "bill_length_mm,bill_depth_mm,body_mass_g" -corr
```
```text
┌────────────────┬────────────────┬───────────────┬─────────────┐
│ column         ┆ bill_length_mm ┆ bill_depth_mm ┆ body_mass_g │
╞════════════════╪════════════════╪═══════════════╪═════════════╡
│ bill_length_mm ┆ 1.0            ┆ -0.24         ┆ 0.6         │
│ bill_depth_mm  ┆ -0.24          ┆ 1.0           ┆ -0.47       │
│ body_mass_g    ┆ 0.6            ┆ -0.47         ┆ 1.0         │
└────────────────┴───────────────┴───────────────┴─────────────┘
```

### 2. Ranked Correlation Pairs (`-corr pairs`)
Unnest the matrix into unique pairs sorted by correlation strength with visual bars:
```bash
pytae penguins.parquet -corr pairs
```
```text
┌───────────────────┬───────────────────┬───────┬───────────────────────┐
│ Column A          ┆ Column B          ┆ Corr  ┆ Strength              │
╞═══════════════════╪═══════════════════╪═══════╪═══════════════════════╡
│ flipper_length_mm ┆ body_mass_g       ┆ 0.87  ┆ █████████ Very Strong │
│ bill_length_mm    ┆ flipper_length_mm ┆ 0.66  ┆ ███████ Strong        │
│ bill_length_mm    ┆ body_mass_g       ┆ 0.6   ┆ ██████ Moderate       │
│ bill_depth_mm     ┆ flipper_length_mm ┆ -0.58 ┆ ▒▒▒▒▒▒ Moderate (-)   │
│ bill_depth_mm     ┆ body_mass_g       ┆ -0.47 ┆ ▒▒▒▒▒ Moderate (-)    │
│ bill_length_mm    ┆ bill_depth_mm     ┆ -0.24 ┆ ▒▒ Weak (-)           │
└───────────────────┴───────────────────┴───────┴───────────────────────┘
```

### 3. Single-Target Screening
Screen all numeric features against a specific target column:
```bash
pytae penguins.parquet -corr "target=body_mass_g"
```

---

## Headless Figure Plotting

`-plot` renders publication-grade charts directly from the command-line pipeline. Any pipeline can end with a plot and route directly to disk or interactive screen.

### 1. Single Plots with Explicit Pipeline Aggregation

Filter, aggregate, and plot in one pipeline:

```bash
pytae penguins.parquet \
  -by species \
  -agg "avg_mass=body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass" \
  -finalize "title='Average Body Mass by Species', ylabel='Mass (g)'" \
  -o avg_mass.png
```

### 2. Multi-Dimensional Categorical Grouping (`by=`)

Produce multi-series bar or scatter plots with automated color mapping:

```bash
pytae penguins.parquet \
  -filter "sex.is_not_null()" \
  -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, by=species" \
  -finalize "title='Bill Length vs Body Mass', tight_layout=true" \
  -o scatter.png
```

### 3. Distribution Plots (`box`, `kde`, `hist`)

Visualise unaggregated distributions grouped by category:

```bash
pytae penguins.parquet \
  -plot "kind=box, x=species, y=flipper_length_mm" \
  -finalize "title='Flipper Length Distribution by Species'" \
  -o flipper_box.png
```

### 4. Custom Styling & Finalization (`-finalize`)

Pass any figure-level customization keys to `-finalize`:

```bash
pytae tips.parquet \
  -by day -agg "avg_bill=total_bill:mean" \
  -plot "kind=bar, x=day, y=avg_bill" \
  -finalize "title='Average Bill by Day', style=seaborn-v0_8-whitegrid, xlabel='Day of Week', ylabel='Average Bill ($)'" \
  -o daily_bill.svg
```

Supported `-finalize` keys:
- `title='...'`: Figure or chart title
- `xlabel='...'`, `ylabel='...'`: Axis labels
- `style='...'`: Matplotlib style sheet (e.g. `seaborn-v0_8-whitegrid`, `dark_background`)
- `tight_layout=true`: Apply tight bounding box
- `sharex=true`, `sharey=true`: Link axis scales across subplots

### 5. Exporting Figures (`-o`)

When `-o` specifies an image extension (`.png`, `.svg`, `.pdf`, `.jpg`, `.jpeg`), `pytae` automatically switches to the non-interactive Matplotlib backend (`Agg`) and saves the figure directly to the destination:

```bash
# Save to current working directory
pytae data.parquet -plot "kind=bar,x=cat,y=val" -o chart.png

# Save to dedicated output directory (created automatically if missing)
pytae data.parquet -plot "kind=bar,x=cat,y=val" -o chart.png -out_dir ./reports/figures
```

---

## Interactive Viewing

If `-o` is omitted and the output is not redirected, `pytae` invokes `plt.show()` so you can inspect charts interactively in a desktop window:

```bash
pytae penguins.parquet -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, by=species"
```

### Linux Interactive Window Notes

On Windows and macOS, Matplotlib includes native GUI window backends out of the box (`TkAgg` on Windows, `MacOSX` on macOS). On Linux, Python does not bundle a GUI toolkit by default. If no GUI toolkit is detected, Matplotlib silently falls back to the headless `Agg` backend and cannot open a window.

To enable interactive plot windows on Linux:
- **Ubuntu / Debian / Mint**: `sudo apt install python3-tk`
- **Fedora / RHEL / CentOS**: `sudo dnf install python3-tkinter`
- **Arch Linux**: `sudo pacman -S tk`
- **Pure pip / Virtualenv (no sudo)**: `pip install PyQt6` (or `pip install PySide6`)
- **Remote / Headless / SSH**: If connecting over SSH or headless servers without an X11/Wayland display server (`$DISPLAY`), export to an image file directly with `-o plot.png` or use SSH X11 forwarding (`ssh -X`).

################################################################################
# FILE: docs/detailed_docs/cli/diff.md
################################################################################
# CLI Feature Guide: Dataset & Schema Diffing

[← Back to Master Reference](../../pytae.md)

Compare schemas, dimensions, added/removed columns, data type drift, null count variations, and cell values against another tabular dataset using `-diff`.

---

## Contents

- [Overview & Use Cases](#overview--use-cases)
- [Basic Usage](#basic-usage)
- [Detailed Diff Output Breakdown](#detailed-diff-output-breakdown)
  - [1. Shape Comparison](#1-shape-comparison)
  - [2. Column Additions & Removals](#2-column-additions--removals)
  - [3. Schema Drift & Type Changes](#3-schema-drift--type-changes)
  - [4. Null Count Variations](#4-null-count-variations)
  - [5. Value Mismatches Across Matching Rows](#5-value-mismatches-across-matching-rows)
- [Filtering / Transforming Before Diffing](#filtering--transforming-before-diffing)
- [Key-Aware Diffing (`on=key`)](#key-aware-diffing-onkey)
- [Python API (`df.diff` / `pt.diff`)](#python-api-dfdiff--ptdiff)
- [Copying Diff Reports to Clipboard (`-o clip`)](#copying-diff-reports-to-clipboard--o-clip)
- [Batch Diffing Across Multiple Files](#batch-diffing-across-multiple-files)

---

## Overview & Use Cases

Data validation and migration testing frequently require comparing an incoming file against a baseline:
- Did an ETL pipeline drop or rename columns?
- Did an integer column unexpectedly drift into floats or strings?
- Did the null count increase?
- Are the cell values identical between two formats (e.g. parquet vs csv)?

The `-diff` flag conducts these inspections instantly without needing to write custom comparison scripts.

---

## Basic Usage

Compare two datasets directly:

```bash
pytae v1.parquet -diff v2.parquet
```

**Output:**
```text
Comparing:
  Left (source):  v1.parquet (4 rows, 4 cols)
  Right (target): v2.parquet (4 rows, 4 cols)

Shape:
  Rows: 4 vs 4 (+0)
  Cols: 4 vs 4 (+0)

Columns:
  + Added in left (1):   old_status
  - Removed in left (1): new_metric
  Common (3):        id, name, score

Schema Drift:
  None (all common columns have matching dtypes)

Null Counts:
  * score: 1 vs 0 nulls (+1)

Values:
  Mismatches found in 3 cells across common columns.
```

---

## Detailed Diff Output Breakdown

### 1. Shape Comparison
Compares row count and column count between left (source) and right (target), highlighting deltas with signed indicators (`+` / `-`).

### 2. Column Additions & Removals
- `+ Added in left`: Columns present in the source but missing from the target.
- `- Removed in left`: Columns present in the target but absent from the source.
- `Common`: Columns existing in both datasets.

### 3. Schema Drift & Type Changes
Reports any column where data types do not match (e.g. `int64 (right) -> float64 (left)`).

### 4. Null Count Variations
Identifies columns where the number of `NaN` or missing values differs, showing the before-and-after count and delta.

### 5. Value Mismatches Across Matching Rows
When row counts match, pytae compares cell values across all common columns:
- If all values match: `Identical: all cell values match exactly.`
- If discrepancies are found: Reports the total count of mismatched cells.

### 6. Numeric Tolerance Threshold (`-tol`)
When comparing floating-point numbers subject to rounding or precision differences, specify an absolute tolerance threshold with `-tol`:

```bash
# Ignore floating point differences smaller than 0.01:
pytae v1.parquet -diff v2.parquet -tol 0.01

# Fine-grained threshold:
pytae v1.parquet -diff v2.parquet -tol 1e-4
```
Differences within the tolerance window are treated as matching cells.

---

## Filtering / Transforming Before Diffing

Because `-diff` runs as part of the pipeline, you can filter or transform the left dataset before diffing:

```bash
# Compare only active records against baseline
pytae incoming.parquet \
  -filter "status == 'ACTIVE'" \
  -select "user_id,email,balance" \
  -diff baseline.parquet
```

---

## Key-Aware Diffing (`on=key`)

When comparing tables where rows may be inserted, deleted, reordered, or filtered, direct positional row matching may fail or report misleading cell differences. Use the `on=` parameter inside `-diff` to align rows by primary or composite keys:

```bash
# Key alignment on a single column:
pytae v1.parquet -diff "v2.parquet,on=id"

# Key alignment with numeric tolerance:
pytae v1.parquet -diff "v2.parquet,on=id,tol=1e-4,rtol=1e-5"

# Composite key alignment:
pytae v1.parquet -diff "v2.parquet,on=customer_id:order_date"
```

**Key Alignment Output:**
```text
Key Alignment (on id):
  Matched keys:    1,420
  + Added in left (2):   [1051, 1052]
  - Removed in left (1): [994]

Values:
  Tolerance: tol=0.0001 (for numeric columns)
  Identical: all cell values match within tolerance.
```

When `on=` is specified:
1. Keys present only in the left or right dataset are identified and reported.
2. Matching keys are aligned directly to compare cell values across common non-key columns, regardless of physical row order.

---

## Python API (`df.diff` / `pt.diff`)

Dataset diffing is also available directly in Python pipelines via `pt.diff()` or `DataFrame.diff()`:

```python
import pytae as pt

left = pt.read_parquet("left.parquet")
right = pt.read_parquet("right.parquet")

# Simple diff
report = left.diff(right)
print(report)

# Key-aware diff with tolerance:
report = pt.diff(left, right, on="id", tol=1e-3)
print(report)

# Or via the pt accessor:
report = df.pt.diff(df_ref, on=["user_id", "date"], tol=0.01)
```

---

## Copying Diff Reports to Clipboard (`-o clip`)

Copy the complete text report to your system clipboard for pasting into pull requests, tickets, or chat:

```bash
pytae v1.parquet -diff v2.parquet -o clip
```

---

## Batch Diffing Across Multiple Files

Compare multiple partitions or daily batch files against a shared reference baseline:

```bash
pytae daily_batches/*.parquet -diff baseline.parquet
```

################################################################################
# FILE: docs/detailed_docs/cli/distinct.md
################################################################################
# CLI Feature Guide: Distinct Rows (`-distinct`)

[← Back to Master Reference](../../pytae.md)

Drop duplicate rows across the intermediate DataFrame with full control over column subsets.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Deduplicating Across All Columns](#deduplicating-across-all-columns)
- [Deduplicating Across Specific Columns](#deduplicating-across-specific-columns)
- [Chaining in Pipelines](#chaining-in-pipelines)

---

## Overview & Quick Reference

| Flag | Syntax / Format | Description |
|---|---|---|
| `-distinct` | Bare flag | Drop duplicate rows checking all columns (`keep=first`) |
| `-distinct COLS` | Comma-separated list | Drop duplicate rows based on specified subset of columns |
| `-distinct "...keep=last"` | `keep=last` | Keep last occurrence instead of first |
| `-distinct "...keep=false"` | `keep=false` or `keep=none` | Drop all duplicate occurrences |

`-distinct` keeps unique combinations and resets the index to `0, 1, ...`. In the Python library, the equivalent is `df.distinct(*cols, keep="first")` (or `pt.distinct(df, *cols, keep="first")`).

---

## Deduplicating Across All Columns

Run `-distinct` as a bare flag to eliminate identical rows across the entire working dataset (equivalent to `df.distinct()` or pandas `df.drop_duplicates()`):

```bash
# Keep only unique species and island pairs
pytae penguins.parquet -distinct "species,island"
```

**Output:**

| species   | island    |
|:----------|:----------|
| Adelie    | Torgersen |
| Adelie    | Biscoe    |
| Adelie    | Dream     |
| Chinstrap | Dream     |
| Gentoo    | Biscoe    |

---

## Controlling Which Duplicates to Keep (`keep=`)

Use `keep=` within the `-distinct` argument to control duplicate retention:

```bash
# Keep the last occurrence of each unique customer
pytae orders.parquet -distinct "customer_id,keep=last"

# Drop all duplicates (keep only rows that appeared exactly once)
pytae orders.parquet -distinct "customer_id,keep=false"

# Keep last duplicate across all columns
pytae events.parquet -distinct "keep=last"
```

---

## Deduplicating Across Specific Columns

Pass column names to restrict duplicate checks to specific identifiers, keeping the matching record for all other columns:

```bash
# Deduplicate based on composite keys
pytae penguins.parquet -distinct "species,island"
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Biscoe | 37.8 | 18.3 | 174.0 | 3400.0 | Female |
| Adelie | Dream | 39.5 | 16.7 | 178.0 | 3250.0 | Female |
| Chinstrap | Dream | 46.5 | 17.9 | 192.0 | 3500.0 | Female |
| Gentoo | Biscoe | 46.1 | 13.2 | 211.0 | 4500.0 | Female |

---

## Chaining in Pipelines

`-distinct` operates seamlessly anywhere inside a multi-step pipeline:

```bash
# Filter rows -> select subset -> distinct -> sort -> output
pytae penguins.parquet \
  -filter "body_mass_g > 4000" \
  -select "species,island" \
  -distinct \
  -arrange species
```

**Output:**

| species | island |
|:---|:---|
| Adelie | Torgersen |
| Adelie | Dream |
| Adelie | Biscoe |
| Chinstrap | Dream |
| Gentoo | Biscoe |

################################################################################
# FILE: docs/detailed_docs/cli/filter.md
################################################################################
# CLI Feature Guide: Row Filtering & Slicing

[← Back to Master Reference](../../pytae.md)

Filter rows using pytae's ergonomic filter expressions (`-filter`), drop missing rows (`-dropna`), or slice rows (`-head`, `-tail`, `-arrange`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Pytae Filtering (`-filter`)](#pytae-filtering--filter)
  - [Exact Matching (`==`)](#exact-matching)
  - [Comparisons (`>`, `<`, `>=`, `<=`, `!=`)](#comparisons)
  - [Boolean Logic (`and`, `or`, and `(...)`)](#boolean-logic)
  - [Column-to-Column Comparisons (`col_a == col_b`)](#column-to-column-comparisons-col_a--col_b)
  - [Ranges & Intervals: Option 1 & Option 2 Dictionaries](#ranges--intervals)
  - [List Membership (`in` and `not in`)](#list-membership)
  - [Filtering Null & NaN Values (`is_null`, `is_not_null`, `is_nan`, `is_not_nan`) & Columns with Spaces](#filtering-null--nan-values-and-columns-with-spaces)
  - [Combining Multiple Conditions](#combining-multiple-conditions)
  - [Strict Syntax Enforcement & Diagnostic Errors](#strict-syntax-enforcement)
- [Slicing Extreme Rows](#slicing-extreme-rows)
- [Inline Data Assertions (`-assert`)](#inline-data-assertions--assert)
- [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Category | Key Syntax Highlights |
|---|---|---|
| `-filter CONDITIONS` | Row Filter | Strict equality `==`, boolean `and` / `or`, dict intervals `{'col': ('between', min, max)}` or `{'col': (('>=', min), ('<=', max))}`, list membership `col in ['a', 'b']`, bracketed spaces `[col name]` |
| `-dropna [COLS]` | Row Filter | Drops rows containing `NaN` (bare for all columns, or comma-separated subset) |
| `-head [LIMIT]`, `-tail [LIMIT]` | Row Slicing | Extract first/last $N$, percentage (`10%`), or with ties (`ties=true`), group-aware with `-by` |

---

## Pytae Filtering (`-filter`)

Pytae's `-filter` compiles expressions directly into Polars native engine filters, achieving high execution speeds with clean, readable syntax.

<a id="exact-matching"></a>
### Exact Matching (`==`)

String values inside `-filter` must be enclosed in single quotes `'value'`, and equality comparisons strictly require `==`:

```bash
pytae penguins.parquet -filter "species == 'Gentoo'" -head 3
```

> [!IMPORTANT]
> **Strict Equality and String Quoting Requirements**:
> - **Strict `==`**: Equality comparisons require `==`. Single `=` is reserved exclusively for column assignments in `-mutate`. Using `=` in `-filter` produces an immediate error guiding you to use `==`.
> - **Quoted String Literals**: String literals must always be quoted (e.g. `'Gentoo'`, `'9'`). If an unquoted literal or number is passed when filtering a string column (e.g. `species == Gentoo` or `id == 9` where `id` is a string column), `pytae` raises an explicit error guiding you to quote the string. This prevents silent type coercion and avoids unexpected lexicographical comparison bugs.
>
> **Shell Quoting Rule (Single Quotes Inside Double Quotes)**:
> In bash, zsh, or PowerShell, wrap the `-filter` argument in outer double quotes and use **single quotes** for string literals:
> ```bash
> pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30']"
> ```
> *Avoid nesting unescaped double quotes* like `-filter "currency=="CAD""` — the shell will strip the inner double quotes before `pytae` receives the argument, causing `pytae` to treat `CAD` as an unknown column name!

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             46.1 |            13.2 |                 211 |          4500 | Female |
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male   |
| Gentoo    | Biscoe   |             48.7 |            14.1 |                 210 |          4450 | Female |

<a id="comparisons"></a>
### Comparisons (`>`, `<`, `>=`, `<=`, `!=`)

Standard mathematical comparison operators are supported:

```bash
pytae penguins.parquet -filter "body_mass_g > 5500" -select "species,island,body_mass_g" -head 3
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5550 |

<a id="boolean-logic"></a>
### Boolean Logic (`and`, `or`, and `(...)`)

Filter expressions support full boolean logic with `and`, `or`, and parentheses `(...)` for nested grouping:

```bash
# Conjunction with 'and'
pytae penguins.parquet -filter "species == 'Gentoo' and body_mass_g > 5500" -select "species,body_mass_g" -head 3

# Disjunction with 'or'
pytae penguins.parquet -filter "island == 'Dream' or island == 'Torgersen'" -select "species,island" -head 3

# Grouping and precedence with nested parentheses:
pytae penguins.parquet -filter "(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000" -head 3
```

> [!NOTE]
> Following Python's *"one and only one obvious way"*, `pytae` strictly uses `and` and `or`. Bitwise `&` and `|` are disallowed, and commas `,` are strictly punctuation for function arguments and lists, not boolean operators.

<a id="column-to-column-comparisons-col_a--col_b"></a>
### Column-to-Column Comparisons (`col_a == col_b`)

You can compare two columns directly against each other (e.g. reconciling IDs, detecting limit breaches) in both Python and CLI using bare column names:

```bash
# In Python API
df.filter("tranche_id == deal_id")
df.filter("amount > limit")

# In CLI (bare column names on both sides)
pytae loans.parquet -filter "tranche_id == deal_id"
pytae loans.parquet -filter "amount > limit"
```

> [!NOTE]
> In `pytae`, unquoted identifiers on the right-hand side of a comparison resolve to the corresponding DataFrame column. If the name is not found in the DataFrame schema, `pytae` raises an explicit error with a fuzzy-match suggestion and a reminder to quote string literals, preventing silent zero-row matches.

<a id="ranges--intervals"></a>
### Ranges & Intervals: Option 1 & Option 2 Dictionaries

Mathematical bracket strings like `[3000, 3200]` have been dropped to eliminate list ambiguity. In modern `pytae`, range and interval queries are expressed through dictionary options or boolean string expressions:

#### Option 1: Native Polars `between`
Pass a dictionary specifying `('between', min, max)` for high-speed inclusive bounds:

```bash
pytae penguins.parquet -filter "{'body_mass_g': ('between', 3000, 3200)}" -select "species,body_mass_g" -head 3
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          3200 |
| Adelie    |          3200 |
| Adelie    |          3000 |

#### Option 2: Multi-Condition Tuples `(('op1', val1), ('op2', val2))`
Pass a dictionary containing a tuple of `(operator, value)` pairs to apply multiple conditions on the same column:

```bash
pytae penguins.parquet -filter "{'body_mass_g': (('>=', 3000), ('<=', 3200))}" -select "species,body_mass_g" -head 3
```

#### String Expression Range
You can also write ranges directly in filter strings using `and`:

```bash
pytae penguins.parquet -filter "body_mass_g >= 3000 and body_mass_g <= 3200" -select "species,body_mass_g" -head 3
```

<a id="list-membership"></a>
### List Membership (`in` and `not in`)

Match against a set of candidate values using `in` or `not in`:

```bash
# Inclusive candidate set
pytae penguins.parquet -filter "species in ['Chinstrap', 'Gentoo']" -select "species,island" -head 3

# Exclusion
pytae penguins.parquet -filter "species not in ['Adelie']" -select "species,island" -head 3
```

**Output:**

| species   | island   |
|:----------|:---------|
| Chinstrap | Dream    |
| Chinstrap | Dream    |
| Chinstrap | Dream    |

<a id="filtering-null--nan-values-and-columns-with-spaces"></a>
### Filtering Null & NaN Values (`is_null()`, `is_not_null()`, `is_nan()`, `is_not_nan()`) & Columns with Spaces

In pure Polars, missing values (`null`) and floating-point non-finite values (`NaN`) follow a strict, universal method-token standard across both expressions and dictionaries:
- **`null` checks**: Use `.is_null()` or `.is_not_null()`.
  - In string expressions: `"sex.is_null()"` or `"sex.is_not_null()"`
  - In dictionaries: `"{sex: is_null()}"` or `"{sex: is_not_null()}"`
  - *(Note: Parentheses are strictly required; bare words like `{sex: is_null}` and `None` like `{sex: None}` are disallowed)*
- **`NaN` checks**: Use `.is_nan()` or `.is_not_nan()`.
  - In string expressions: `"score.is_nan()"` or `"score.is_not_nan()"`
  - In dictionaries: `"{score: is_nan()}"` or `"{score: is_not_nan()}"`
  - *(Note: Parentheses are strictly required; bare words like `{score: is_nan}` and `nan` like `{score: nan}` are disallowed)*
- For columns whose names contain spaces or special punctuation, enclose the column name in brackets `[col name]`.

```bash
# 1. Bracket method notation for non-null values
pytae penguins.parquet -rename "bill_length_mm:[bill length mm]" -filter "[bill length mm].is_not_null()" -select "species,[bill length mm]" -head 3

# 2. String expression for null values
pytae penguins.parquet -filter "sex.is_null()" -select "species,sex" -head 3

# 3. Dictionary filter with canonical 'is_null()' method token
pytae penguins.parquet -filter "{sex: is_null()}" -select "species,sex" -head 3
pytae penguins.parquet -filter "{sex: is_not_null()}" -select "species,sex" -head 3

# 4. Floating-point NaN filtering via expression and dictionary
pytae measurements.parquet -filter "score.is_nan()"
pytae measurements.parquet -filter "{score: is_nan()}"
pytae measurements.parquet -filter "{score: is_not_nan()}"
```

**Output:**

| species   |   bill length mm |
|:----------|-----------------:|
| Adelie    |             39.1 |
| Adelie    |             39.5 |
| Adelie    |             40.3 |

<a id="combining-multiple-conditions"></a>
### Combining Multiple Conditions

Combine multiple conditions with `and`:

```bash
pytae penguins.parquet \
  -filter "species == 'Gentoo' and body_mass_g > 5500 and island == 'Biscoe'" \
  -select "species,body_mass_g,sex" \
  -head 3
```

**Output:**

| species   |   body_mass_g | sex   |
|:----------|--------------:|:------|
| Gentoo    |          5700 | Male  |
| Gentoo    |          5700 | Male  |
| Gentoo    |          5550 | Male  |

<a id="strict-syntax-enforcement"></a>
### Strict Syntax Enforcement & Diagnostic Errors

`pytae` strictly validates filter expressions to prevent subtle bugs and provide immediate clarity:

1. **Single `=` is rejected**:
   ```bash
   pytae penguins.parquet -filter "species = 'Gentoo'"
   # Error: invalid filter condition 'species = 'Gentoo'': use '==' for equality comparisons (e.g. species == 'Gentoo'). Single '=' is for assignment (-mutate), not comparison (-filter).
   ```
2. **Comma `,` as a boolean operator is rejected**:
   ```bash
   pytae penguins.parquet -filter "species == 'Gentoo', body_mass_g > 5000"
   # Error: invalid filter condition 'species == 'Gentoo', body_mass_g > 5000': comma ',' is not supported as a boolean operator. Use 'and' instead.
   ```
3. **Bitwise `&` and `|` are rejected**:
   ```bash
   pytae penguins.parquet -filter "species == 'Gentoo' & body_mass_g > 5000"
   # Error: invalid filter condition '...': '&' is not supported in filter. Use 'and' instead.
   ```
4. **Bracket interval notation `[min, max]` is rejected**:
   ```bash
   pytae penguins.parquet -filter "body_mass_g = [3000, 3200]"
   # Error: filter(): interval notation '[3000, 3200]' is not supported. Use 'and' (e.g. body_mass_g >= 3000 and body_mass_g <= 3200), or dict syntax 'body_mass_g: ("between", 3000, 3200)'.
   ```

---

## Slicing Extreme Rows

Extract top or bottom rows ordered by a specific column by composing `-arrange` with group-aware `-head` or `-tail`. For complete details and syntax, see the [Row Slicing Guide](head_tail.md).

### Top N Rows Overall

```bash
pytae penguins.parquet -arrange "body_mass_g desc" -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows per Group (`-by`)

When combined with `-by`, `-head` and `-tail` extract rows within each unique group:

```bash
pytae penguins.parquet -by species -arrange body_mass_g -head 1 -select "species,body_mass_g"
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          2850 |
| Chinstrap |          2700 |
| Gentoo    |          3950 |

---

## Inline Data Assertions (`-assert`)

While `-filter` silently keeps only matching rows, `-assert` enforces data quality and schema invariants at any point in the pipeline. If all rows satisfy the assertion conditions, the pipeline continues uninterrupted; if any condition fails, execution halts immediately with an informative error displaying the number of failing rows and sample violations.

```bash
# Validate ranges and non-null constraints:
pytae penguins.parquet -assert "body_mass_g > 0 and species.is_not_null()"

# Chain assertions between transformations:
pytae raw_events.parquet \
  -filter "status == 'SUCCESS'" \
  -assert "user_id.is_not_null() and amount >= 0" \
  -mutate "tax = amount * 0.08" \
  -assert "tax >= 0" \
  -save processed_events.parquet
```

### Python API (`df.assert_()` / `pt.assert_()`)

```python
import pytae as pt

df = pt.read_parquet("penguins.parquet")

# Method chaining:
validated = (
    df
    .filter("body_mass_g > 3000")
    .assert_("species in ['Adelie', 'Gentoo', 'Chinstrap']")
    .mutate("mass_kg = body_mass_g / 1000")
    .assert_("mass_kg > 3.0")
)

# Functional API:
pt.assert_(df, "bill_length_mm > 0", "sex.is_not_null()")

# Accessor API:
df.pt.assert_("body_mass_g > 0")
```

---

## Dropping Missing Values (`-dropna`)

Drop rows with missing values (`NaN`). Can be run bare or scoped to a comma-separated column list:

```bash
# Drop rows with NaN in any column
pytae penguins.parquet -dropna -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

```bash
# Drop rows with NaN in specific column(s)
pytae penguins.parquet -dropna "body_mass_g,sex" -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

> [!NOTE]
> For scoped aggregations and pivot tables, pass `dropna=true` inside the operation's spec (e.g., `-agg "a=mean,dropna=true"` or `-pivot "r=species,c=sex,dropna=true"`).

---

## Quoting Best Practices

In terminal shells (bash, zsh):
- Enclose the entire spec in outer double quotes: `-filter "..."`.
- Enclose string literals in inner single quotes: `'Gentoo'`, `'9'`. Unquoted strings or numbers against string columns will raise an explicit `TypeError`.
- Numeric literals should remain unquoted: `body_mass_g > 3500`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40` or `-arrange "[bill length mm] desc" -head 3`.

################################################################################
# FILE: docs/detailed_docs/cli/head_tail.md
################################################################################
# CLI Feature Guide: Row Slicing (`-head` & `-tail`)

[← Back to Master Reference](../../pytae.md)

Extract first, last, or extreme rows with full group awareness via `-by`, proportion limits (`10%`), and boundary tie handling (`ties=true`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Basic Slicing](#basic-slicing)
- [Proportion Slicing (`10%` / `0.1`)](#proportion-slicing-10--01)
- [Extreme Value Slicing](#extreme-value-slicing)
- [Group-Aware Slicing (`-by`)](#group-aware-slicing--by)
- [Boundary Ties (`ties=true`)](#boundary-ties-tiestrue)
- [Retirement of Legacy `-pick`](#retirement-of-legacy--pick)

---

## Overview & Quick Reference

| Flag | Description | Examples |
|---|---|---|
| `-head [LIMIT]` | Extract first $N$ rows, percentage, or proportion | `-head 5`, `-head 10%`, `-head 0.1`, `-head "3, ties=true"` |
| `-tail [LIMIT]` | Extract last $N$ rows, percentage, or proportion | `-tail 5`, `-tail 10%`, `-tail 0.1`, `-tail "3, ties=true"` |
| `-by COLS` | Partition rows into groups before slicing | `-by species -head 2`, `-by species -arrange "mass desc" -head 1` |

When `-head` or `-tail` is passed without an explicit limit, it defaults to 5 rows. Slicing preserves column order, resets the row index, and cleanly ungroups.

---

## Basic Slicing

Extract the first or last $N$ rows of the table:

```bash
# First 3 rows
pytae penguins.parquet -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Adelie    | Torgersen|          3750 |
| Adelie    | Torgersen|          3800 |
| Adelie    | Torgersen|          3250 |

```bash
# Last 3 rows
pytae penguins.parquet -tail 3 -select "species,island,body_mass_g"
```

---

## Proportion Slicing (`10%` / `0.1`)

Slice a percentage or fraction of rows by passing `%` or a float:

```bash
# First 5% of rows
pytae penguins.parquet -head 5% -shape
```

**Output:**
```
(17, 7)
```

Both percentages (`-head 10%`) and floating-point fractions (`-head 0.1`) are accepted.

---

## Extreme Value Slicing

In accordance with Pytae's *"One and Only One Obvious Way"*, extreme row selection (top/bottom $N$ by column) is achieved by composing `-arrange` with `-head` or `-tail`:

### Top N Rows Overall

```bash
# Top 3 heaviest penguins overall
pytae penguins.parquet -arrange "body_mass_g desc" -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows Overall

```bash
# Lightest 3 penguins overall
pytae penguins.parquet -arrange body_mass_g -head 3 -select "species,island,body_mass_g"
```

*(Alternatively: `pytae penguins.parquet -arrange "body_mass_g desc" -tail 3`)*

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Chinstrap | Dream    |          2700 |
| Adelie    | Biscoe   |          2850 |
| Adelie    | Dream    |          2850 |

---

## Group-Aware Slicing (`-by`)

When combined with `-by`, `-head` and `-tail` extract rows **within each unique group**:

### Heaviest Penguin per Species

```bash
# Top 1 heaviest penguin for each species
pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 1 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Adelie    | Biscoe   |          4775 |
| Chinstrap | Dream    |          4800 |
| Gentoo    | Biscoe   |          6300 |

### Lightest 2 Penguins per Island

```bash
pytae penguins.parquet -by island -arrange body_mass_g -head 2 -select "island,species,body_mass_g"
```

**Output:**

| island    | species   |   body_mass_g |
|:----------|:----------|--------------:|
| Biscoe    | Adelie    |          2850 |
| Biscoe    | Adelie    |          2850 |
| Dream     | Chinstrap |          2700 |
| Dream     | Adelie    |          2900 |
| Torgersen | Adelie    |          2900 |
| Torgersen | Adelie    |          3050 |

### Top 10% per Group

```bash
pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 10% -select "species,island,body_mass_g"
```

### Top N per Group in Chained Pipelines (Sequential `-by`)

In Pytae CLI, `-by` operates with **single-shot zero-pollution scoping**: each `-by` applies strictly to the verb that follows, then resets. You can seamlessly chain aggregation, sorting, and group-aware slicing in a single command:

```bash
# Top 2 species by average body mass for each island
pytae penguins.parquet \
  -by island,species -agg "avg_mass=mean(body_mass_g)" \
  -arrange "island, avg_mass desc" \
  -by island -head 2
```

**Output:**

| island    | species   |   avg_mass |
|:----------|:----------|-----------:|
| Biscoe    | Gentoo    |    5076.02 |
| Biscoe    | Adelie    |    3709.66 |
| Dream     | Chinstrap |    3733.09 |
| Dream     | Adelie    |    3688.39 |
| Torgersen | Adelie    |    3706.37 |

---

## Boundary Ties (`ties=true`)

When multiple rows share the exact value at the $N$-th boundary rank, pass `ties=true` to include all tied rows:

```bash
# Include ties at the rank boundary
pytae penguins.parquet -arrange "body_mass_g desc" -head "3, ties=true" -select "species,island,body_mass_g"
```

---

## Retirement of Legacy `-pick`

The niche verb `-pick` has been removed. In Pytae:
- Selecting top records is simply `-arrange "col desc" -head N`.
- Selecting bottom records is `-arrange col -head N` (or `-arrange "col desc" -tail N`).
- Grouped extreme selection is `-by group -arrange "col desc" -head N`.

Calling `-pick` raises an immediate, helpful redirect error guiding users to compose `-arrange` and `-head`/`-tail`.

################################################################################
# FILE: docs/detailed_docs/cli/inspect.md
################################################################################
# CLI Feature Guide: Inspection & Metadata

[← Back to Master Reference](../../pytae.md)

Inspect file dimensions, structure, sample rows, statistical distributions, and low-level storage metadata without writing boilerplate Python code.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Zero-Scan Parquet Metadata (`-meta`)](#zero-scan-parquet-metadata--meta)
- [Viewing Rows (`-head`, `-tail`, `-sample`)](#viewing-rows--head--tail--sample)
- [In-Line ASCII Visualizations (`-freq`, `-hist`)](#in-line-ascii-visualizations--freq--hist)
- [Dataset Dimensions (`-shape`)](#dataset-dimensions--shape)
- [Column Names & Ordering (`-cols`)](#column-names--ordering--cols)
- [Data Types & Null Counts (`-dtype`, `-nulls`)](#data-types--null-counts--dtype--nulls)
- [Statistical Summaries (`-describe`)](#statistical-summaries--describe)
- [Terminal Paging (`-pager`)](#terminal-paging--pager)
- [Display Modifiers (`-round`)](#display-modifiers--round)
- [Chaining & Terminal Operation Rules](#chaining--terminal-operation-rules)

---

## Overview & Rules

Inspection flags let you understand a dataset's layout and content instantly from the terminal.

| Flag | Description | Terminal Op? |
|---|---|---|
| `-head [N]` | Print the first N rows (default: 5) | No (returns DataFrame) |
| `-tail [N]` | Print the last N rows (default: 5) | No (returns DataFrame) |
| `-sample [N]` | Print N randomly sampled rows (default: 5) | No (returns DataFrame) |
| `-seed N` | Random seed for `-sample` reproducibility | Modifier for `-sample` |
| `-frac P` | Sample a fraction of rows (e.g. `0.1` for 10%) | Modifier for `-sample` |
| `-freq COL` | Terminal ASCII frequency distribution bar chart | **Yes** (terminal) |
| `-hist COL[:BINS]` | Terminal ASCII numeric histogram with bin intervals | **Yes** (terminal) |
| `-shape` | Print `(rows, cols)` tuple | **Yes** (terminal) |
| `-cols [ORDER]` | Print column names (optional `asc`/`desc` sorts names) | **Yes** (terminal) |
| `-dtype [ORDER]` | Print data types per column | **Yes** (terminal) |
| `-nulls [ORDER]` | Print count of missing / NaN values per column | **Yes** (terminal) |
| `-meta` | Zero-scan Parquet metadata (row groups, compression, schema) | **Yes** (terminal) |
| `-glimpse` | Transposed column overview with dtypes and inline sample values | **Yes** (terminal) |
| `-describe` | Statistical summary (count, mean, std, quartiles) | No (returns DataFrame) |
| `-pager` | Pipe long outputs through system pager (`$PAGER` or `less`) | Display flag |
| `-round N` | Round numeric columns to N decimal places | Display flag |

> [!NOTE]
> **Zero-cost header reading**: For formats with file-level headers (`.parquet`, `.sas7bdat`), `-shape`, `-cols`, `-dtype`, and `-head` read strictly from the metadata without loading the entire dataset into memory.

---

## Zero-Scan Parquet Metadata (`-meta`)

Inspect Parquet file internals in sub-milliseconds without scanning table data. Displays file size, Parquet format version, row groups count, column compression codecs, compression ratio, and schema.

```bash
pytae penguins.parquet -meta
```

**Output:**
```text
File: penguins.parquet
File size: 7.8 KB
Format: Parquet (version 2.6)
Rows: 344
Columns: 7
Row groups: 1
Compression: SNAPPY
Uncompressed data size: 5.0 KB
Space saving: -57.6%

Schema:
  #    Column             Type
  ---- -----------------  --------------------
  0    species            large_string
  1    island             large_string
  2    bill_length_mm     double
  3    bill_depth_mm      double
  4    flipper_length_mm  double
  5    body_mass_g        double
  6    sex                large_string
```

Copy metadata summary to clipboard:
```bash
pytae penguins.parquet -meta -o clip
```

---

## Viewing Rows (`-head`, `-tail`, `-sample`)

### First N rows (`-head`)

```bash
pytae penguins.parquet -head 3
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

### Last N rows (`-tail`)

```bash
pytae penguins.parquet -tail 3
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             50.4 |            15.7 |                 222 |          5750 | Male   |
| Gentoo    | Biscoe   |             45.2 |            14.8 |                 212 |          5200 | Female |
| Gentoo    | Biscoe   |             49.9 |            16.1 |                 213 |          5400 | Male   |

### Random rows with reproducible seed (`-sample`)

```bash
pytae penguins.parquet -sample 3 -seed 42
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Chinstrap | Dream    |             50.9 |            19.1 |                 196 |          3550 | Male   |
| Chinstrap | Dream    |             45.2 |            17.8 |                 198 |          3950 | Female |
| Gentoo    | Biscoe   |             46.5 |            13.5 |                 210 |          4550 | Female |

### Sample a percentage (`-frac`)

```bash
# Sample 1% of the dataset and check row count
pytae penguins.parquet -sample -frac 0.01 -shape
```

**Output:**
```text
(3, 7)
```

---

## In-Line ASCII Visualizations (`-freq`, `-hist`)

Inspect categorical distributions and numeric value distributions directly in the terminal without requiring a graphical display or web browser.

### Frequency Distribution Bars (`-freq COL`)

Prints an ASCII horizontal bar chart showing category counts and percentages:

```bash
pytae penguins.parquet -freq species
```

**Output:**
```text
species
Adelie     152 (44.2%)  ████████████████████████████████████████
Gentoo     124 (36.0%)  ████████████████████████████████
Chinstrap   68 (19.8%)  █████████████████
```

### Numeric Histogram (`-hist COL[:BINS]`)

Computes bin intervals for numeric columns and renders a terminal histogram (defaults to 10 bins; specify `:BINS` to adjust):

```bash
pytae penguins.parquet -hist body_mass_g:8
```

**Output:**
```text
body_mass_g (8 bins)
[2700.0, 3150.0)    64 (18.7%)  ████████████████
[3150.0, 3600.0)    71 (20.8%)  ██████████████████
[3600.0, 4050.0)    65 (19.0%)  ████████████████
[4050.0, 4500.0)    37 (10.8%)  █████████
[4500.0, 4950.0)    36 (10.5%)  █████████
[4950.0, 5400.0)    46 (13.5%)  ███████████
[5400.0, 5850.0)    19  (5.6%)  ████
[5850.0, 6300.0]     4  (1.2%)  █
```

---

## Dataset Dimensions (`-shape`)

Returns `(rows, cols)` tuple:

```bash
pytae penguins.parquet -shape
```

**Output:**
```text
(344, 7)
```

Chain after filtering to count matching rows:

```bash
pytae penguins.parquet -filter "species == 'Gentoo'" -shape
```

**Output:**
```text
(124, 7)
```

---

## Column Names & Ordering (`-cols`)

Print all column names in the order they appear in the file:

```bash
pytae penguins.parquet -cols
```

**Output:**
```text
species
island
bill_length_mm
bill_depth_mm
flipper_length_mm
body_mass_g
sex
```

Sort column names alphabetically with `asc` or `desc`:

```bash
pytae penguins.parquet -cols asc
```

**Output:**
```text
bill_depth_mm
bill_length_mm
body_mass_g
flipper_length_mm
island
sex
species
```

---

## Data Types & Null Counts (`-dtype`, `-nulls`)

### Column Data Types (`-dtype`)

```bash
pytae penguins.parquet -dtype
```

**Output:**

| Column | Dtype |
|:---|:---|
| species | str |
| island | str |
| bill_length_mm | float64 |
| bill_depth_mm | float64 |
| flipper_length_mm | float64 |
| body_mass_g | float64 |
| sex | str |

### Missing Value Counts (`-nulls`)

```bash
pytae penguins.parquet -nulls
```

**Output:**

| Column | Nulls |
|:---|---:|
| species | 0 |
| island | 0 |
| bill_length_mm | 2 |
| bill_depth_mm | 2 |
| flipper_length_mm | 2 |
| body_mass_g | 2 |
| sex | 11 |

Sort by column name descending:
```bash
pytae penguins.parquet -nulls desc
```

**Output:**

| Column | Nulls |
|:---|---:|
| species | 0 |
| sex | 11 |
| island | 0 |
| flipper_length_mm | 2 |
| body_mass_g | 2 |
| bill_length_mm | 2 |
| bill_depth_mm | 2 |

---

## Statistical Summaries (`-describe`)

### Five-Number Summary (`-describe`)

Computes count, mean, std, min, percentiles (25%, 50%, 75%), and max for numeric columns:

```bash
pytae penguins.parquet -describe -round 1
```

**Output:**

| Stat | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g |
|:---|---:|---:|---:|---:|
| count | 342.0 | 342.0 | 342.0 | 342.0 |
| mean | 43.9 | 17.2 | 200.9 | 4201.8 |
| std | 5.5 | 2.0 | 14.1 | 802.0 |
| min | 32.1 | 13.1 | 172.0 | 2700.0 |
| 25% | 39.2 | 15.6 | 190.0 | 3550.0 |
| 50% | 44.4 | 17.3 | 197.0 | 4050.0 |
| 75% | 48.5 | 18.7 | 213.0 | 4750.0 |
| max | 59.6 | 21.5 | 231.0 | 6300.0 |

Because `-describe` returns a DataFrame, it can be filtered, rounded, or exported:
```bash
pytae penguins.parquet -describe -round 2 -o summary.csv
```

### Transposed Summary (`-glimpse`)

Inspired by `dplyr::glimpse()` and Polars, `-glimpse` provides an immediate, transposed view of all columns, displaying row count, column count, dtypes, and an inline preview of first values:

```bash
pytae penguins.parquet -glimpse
```

**Output:**
```text
Rows: 344
Columns: 7
$ species           <str>     'Adelie', 'Adelie', 'Adelie', 'Adelie', 'Adelie...
$ island            <str>     'Torgersen', 'Torgersen', 'Torgersen', 'Torgers...
$ bill_length_mm    <float64> 39.1, 39.5, 40.3, NA, 36.7, 39.3, 38.9, 39.2, 3...
$ bill_depth_mm     <float64> 18.7, 17.4, 18.0, NA, 19.3, 20.6, 17.8, 19.6, 1...
$ flipper_length_mm <float64> 181.0, 186.0, 195.0, NA, 193.0, 190.0, 181.0, 1...
$ body_mass_g       <float64> 3750.0, 3800.0, 3250.0, NA, 3450.0, 3650.0, 362...
$ sex               <str>     'Male', 'Female', 'Female', NA, 'Female', 'Male...
```

> [!TIP]
> Unlike `-head`, which wraps across screen lines when dealing with wide tables (20–100+ columns), `-glimpse` guarantees that every column and its data type fit neatly on one line. It is also available in Python via `df.glimpse()`.

---

## Terminal Paging (`-pager`)

When viewing wide tables or large statistical summaries in the terminal, `-pager` streams the output into your system's pager (`$PAGER` or `less`), allowing keyboard navigation (`j`/`k`, `/` search, `q` to quit):

```bash
pytae wide_dataset.parquet -describe -pager
pytae data.parquet -head 100 -pager
```

---

## Display Modifiers (`-round`)

### Rounding Decimals (`-round`)

Rounds all floating-point numbers across the printed output or clipboard:

```bash
pytae penguins.parquet -agg body_mass_g=mean -round 2
```

**Output:**

| body_mass_g |
|---:|
| 4201.75 |

---

## Chaining & Terminal Operation Rules

Operations whose output is a scalar, list, or text report cannot have downstream DataFrame operations chained after them.

```bash
# Allowed: -shape or -meta can only be followed by -o clip
pytae penguins.parquet -shape -o clip
pytae penguins.parquet -meta -o clip

# Disallowed: Cannot chain DataFrame verbs off -shape
pytae penguins.parquet -shape -head 3
# Error: -shape does not return a DataFrame/Series, so no flag may follow it
```

################################################################################
# FILE: docs/detailed_docs/cli/join.md
################################################################################
# CLI Feature Guide: Relational Joins & Stacking (`-join` & `-concat`)

Join multiple datasets or append rows across tables directly from the command line using `-file`, `-join`, and `-concat`, powered natively by Polars' multithreaded SIMD execution engine.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Multi-File Declaration (`-file`)](#multi-file-declaration--file)
- [Relational Joins (`-join`)](#relational-joins--join)
  - [Join Strategies (`how=`)](#join-strategies-how)
  - [Differing Key Names](#differing-key-names)
  - [Multi-Column Join Keys](#multi-column-join-keys)
  - [Cardinality Validation](#cardinality-validation)
  - [Chaining Multiple Joins with `data`](#chaining-multiple-joins-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Downstream Verbs After Joins](#downstream-verbs-after-joins)

---

## Overview & Rules

While standard `pytae` commands process a single positional dataset, multi-table operations use `-file` to declare named input aliases:
- Aliases are semicolon-separated: `PATH=ALIAS; PATH=ALIAS`.
- Pipelines begin with `-join`, `-concat`, or `-sql`.
- Subsequent flags (`-filter`, `-mutate`, `-select`, `-by`, `-agg`, `-o`) operate on the combined result.

```bash
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -head 5
```

---

## Multi-File Declaration (`-file`)

Declare inputs using `PATH=ALIAS` separated by semicolons `;`:

```bash
# Two files
pytae -file "orders.parquet=o; customers.csv=c" ...

# Three files (different formats supported)
pytae -file "sales.parquet=s; stores.csv=st; targets.jsonl=t" ...
```

---

## Relational Joins (`-join`)

Syntax:
```bash
-join "left=LEFT_ALIAS, right=RIGHT_ALIAS, on=KEYS, how=STRATEGY"
```

### Join Strategies (`how=`)

| Strategy | Flag Syntax | Description |
|---|---|---|
| **Inner Join** *(default)* | `how=inner` | Keeps rows where keys match in both datasets |
| **Left Join** | `how=left` | Preserves all left rows; fills unmatched right cells with `null` |
| **Right Join** | `how=right` | Preserves all right rows; fills unmatched left cells with `null` |
| **Full Outer Join** | `how=full` or `how=outer` | Keeps all rows from both datasets |
| **Semi Join** | `how=semi` | Filters left rows that have a match in right (right columns excluded) |
| **Anti Join** | `how=anti` | Keeps left rows with **no** match in right (orphan/discrepancy detection) |
| **Cross Join** | `how=cross` | Full Cartesian product ($N \times M$ rows, omit `on=`) |

```bash
# Left outer join
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -head 10

# Anti join: find customers who have NEVER placed an order
pytae -file "customers.csv=c; orders.parquet=o" \
  -join "left=c, right=o, on=customer_id, how=anti" \
  -cols id,name,signup_date
```

---

### Differing Key Names

When join keys have different names across datasets, use the colon syntax `on="left_key:right_key"`:

```bash
# Join orders.client_id with customers.id
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=client_id:id, how=inner" \
  -head 5
```

---

### Multi-Column Join Keys

Separate composite keys with commas or plus signs:

```bash
pytae -file "sales.parquet=s; inventory.parquet=i" \
  -join "left=s, right=i, on=store_id:store_id, sku:sku, how=left" \
  -head 5
```

---

### Cardinality Validation

Catch accidental row multiplication or duplicate keys before they corrupt aggregations using `validate=`:
- `validate=1:1`: Checks that keys are unique in both left and right datasets.
- `validate=1:m`: Checks that keys are unique in the left dataset.
- `validate=m:1`: Checks that keys are unique in the right dataset.
- `validate=m:m`: Default, allows many-to-many matches.

```bash
pytae -file "orders.parquet=o; users.csv=u" \
  -join "left=o, right=u, on=user_id:id, how=inner, validate=m:1" \
  -head 5
```
*(If `users.csv` contains duplicate IDs, `pytae` immediately aborts with a descriptive error).*

---

### Chaining Multiple Joins with `data`

Chain 3 or more datasets by referencing the running pipeline result `data`:

```bash
pytae -file "orders.parquet=o; customers.csv=c; products.parquet=p" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -join "left=data, right=p, on=product_id, how=left" \
  -select order_id, customer_name, product_name, price, quantity \
  -head 10
```

---

## Row-Wise Stacking (`-concat`)

Stack multiple files sharing identical schemas into a single view:

```bash
pytae -file "q1.parquet=q1; q2.parquet=q2; q3.parquet=q3; q4.parquet=q4" \
  -concat "q1, q2, q3, q4" \
  -by quarter \
  -agg "total_revenue = amount:sum, order_count = count" \
  -o annual_summary.csv
```

---

## Downstream Verbs After Joins

Once joined or stacked, all standard `pytae` verbs apply seamlessly:

```bash
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=inner" \
  -filter "region == 'West' and amount > 100" \
  -mutate "tax = amount * 0.0825, total = amount + tax" \
  -by customer_name \
  -agg "spent = total:sum, orders = count" \
  -arrange "spent desc" \
  -head 10 \
  -o top_west_customers.parquet
```

################################################################################
# FILE: docs/detailed_docs/cli/mask.md
################################################################################
# CLI Feature Guide: Data Masking, Encryption & Tokenization (`-mask`, `-unmask`)

Anonymize, redact, encrypt, or tokenize sensitive PII columns across one-way irreversible and two-way reversible privacy pipelines.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [One-Way Masking](#one-way-masking)
  - [Cryptographic Hashing (`col=hash` / `col=sha256`)](#cryptographic-hashing-colhash--colsha256)
  - [Salted Hashing (`-salt`)](#salted-hashing--salt)
  - [String Redaction (`col=redact`)](#string-redaction-colredact)
- [Reversible Privacy Option 1: Key-Based Authenticated Encryption (`-key`)](#reversible-privacy-option-1-key-based-authenticated-encryption--key)
  - [Encrypting with `-mask "col=encrypt" -key "..."`](#encrypting-with--mask-colencrypt--key-)
  - [Decrypting with `-unmask "col" -key "..."`](#decrypting-with--unmask-col--key-)
- [Reversible Privacy Option 2: Pseudonym Tokenization with Persistent Vault (`-vault`)](#reversible-privacy-option-2-pseudonym-tokenization-with-persistent-vault--vault)
  - [Tokenizing with `-mask "col=tokenize" -vault "..."`](#tokenizing-with--mask-coltokenize--vault-)
  - [De-tokenizing with `-unmask "col" -vault "..."`](#de-tokenizing-with--unmask-col--vault-)
- [Mixed Multi-Column Masking Pipelines](#mixed-multi-column-masking-pipelines)

---

## Overview & Quick Reference

| Flag | Argument | Description |
|---|---|---|
| `-mask` | `"col=method, ..."` | Mask specified columns using `hash`, `sha256`, `redact`, `encrypt`, or `tokenize` |
| `-unmask` | `"col1, col2, ..."` | Revert encrypted or tokenized columns back to original values |
| `-key` | `"secret_password"` | Secret key for authenticated symmetric encryption & decryption |
| `-salt` | `"custom_salt"` | Salt appended to values prior to SHA-256 hashing (prevents rainbow table attacks) |
| `-vault` | `"path/to/vault.parquet"` | File path to persistent tokenization vault (supports `.parquet`, `.csv`, `.ndjson`, `.json`) |

---

## One-Way Masking

One-way masking transformations are irreversible by design. They prevent unauthorized recovery of raw values even if the transformed dataset is shared externally.

### Cryptographic Hashing (`col=hash` / `col=sha256`)

Computes the standard SHA-256 hex digest of non-null values. Null values remain intact.

```bash
# Mask email and user_id using SHA-256
pytae users.csv -mask "email=hash, user_id=sha256"
```

### Salted Hashing (`-salt`)

Appends a secret salt string before hashing, thwarting precomputed rainbow table and dictionary lookup attacks:

```bash
# SHA-256 hash with an organizational salt
pytae users.csv -mask "email=hash" -salt "prod_salt_2026_x89f"
```

### String Redaction (`col=redact`)

Replaces all non-null values in the target column with asterisks (`***`).

```bash
# Redact SSN and phone numbers completely
pytae customers.parquet -mask "ssn=redact, phone=redact"
```

---

## Reversible Privacy Option 1: Key-Based Authenticated Encryption (`-key`)

Key-based encryption performs authenticated symmetric stream encryption (HMAC-SHA256 CTR) with random per-cell initialization vectors (IVs) and cryptographic HMAC integrity verification.

- **Zero External Dependencies**: Operates natively using the Python standard library.
- **Tamper-Resistant**: If ciphertext is modified or the wrong key is supplied during `-unmask`, decryption raises an error rather than emitting corrupted garbage bytes.

### Encrypting with `-mask "col=encrypt" -key "..."`

```bash
# Encrypt SSN and notes columns with a strong secret key
pytae sensitive.csv -mask "ssn=encrypt, notes=encrypt" -key "TopSecretPassphrase42" -o secure.parquet
```

### Decrypting with `-unmask "col" -key "..."`

```bash
# Decrypt the encrypted columns back to plain text
pytae secure.parquet -unmask "ssn, notes" -key "TopSecretPassphrase42" -head 5
```

---

## Reversible Privacy Option 2: Pseudonym Tokenization with Persistent Vault (`-vault`)

Tokenization replaces sensitive entities with clean, format-preserving pseudonym tokens (e.g., `user_0001`, `user_0002`).

- **Preserves Entity Relationships**: Identical values are mapped to identical tokens, preserving frequency counts, group distributions, and join keys across multiple tables.
- **Type-Aware Vault**: The vault persists original column data types (`Int64`, `Float64`, `String`, etc.), so `-unmask` automatically restores the original column back to its native data type.
- **Incremental & Persistent**: Appending new batches against an existing vault reuses existing tokens and assigns subsequent incrementing tokens to novel values.

### Tokenizing with `-mask "col=tokenize" -vault "..."`

```bash
# Tokenize user IDs and persist mapping to user_vault.parquet
pytae transactions.parquet -mask "user_id=tokenize" -vault "user_vault.parquet" -o public_transactions.parquet
```

### De-tokenizing with `-unmask "col" -vault "..."`

```bash
# De-tokenize the anonymized dataset back to original identifiers using the vault
pytae public_transactions.parquet -unmask "user_id" -vault "user_vault.parquet"
```

---

## Mixed Multi-Column Masking Pipelines

Multiple masking strategies can be combined in a single `-mask` command:

```bash
# Hash email, encrypt SSN, and tokenize user name simultaneously
pytae internal_records.csv \
  -mask "email=hash, ssn=encrypt, user_name=tokenize" \
  -salt "audit_salt" \
  -key "SuperSecretKey99" \
  -vault "names_vault.parquet" \
  -o sanitized.parquet
```

################################################################################
# FILE: docs/detailed_docs/cli/multi_file.md
################################################################################
# CLI Feature Guide: Multi-File Pipelines

[← Back to Master Reference](../../pytae.md)

Load, join, stack, and query multiple disparate datasets in a unified pipeline using `-file`, `-join`, `-concat`, and cross-file `-sql`.

---

## Contents

- [Overview & Architecture](#overview--architecture)
- [Loading Named Inputs (`-file`)](#loading-named-inputs--file)
- [Joining Datasets (`-join`)](#joining-datasets--join)
  - [Shared Join Keys](#shared-join-keys)
  - [Different Join Keys (`left:right`)](#different-join-keys-leftright)
  - [Join Types (`how=inner|left|right|outer`)](#join-types-howinnerleftrightouter)
  - [Validating Joins (`validate=one_to_one`)](#validating-joins-validateone_to_one)
  - [Folding Multiple Files with `data`](#folding-multiple-files-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Cross-File SQL Queries (`-sql`)](#cross-file-sql-queries--sql)
- [Exporting Joined Results](#exporting-joined-results)

---

## Overview & Architecture

While standard `pytae` operations process a single positional file path, `-file` switches the CLI into multi-file mode:
- `-file` replaces the positional path entirely.
- The pipeline must begin with either `-join`, `-concat`, or `-sql`.
- Subsequent steps (`-filter`, `-select`, `-mutate`, `-agg`, `-o`) operate on the combined result.

---

## Loading Named Inputs (`-file`)

Declare two or more input files separated by semicolons `;`. Each entry maps a file path to an alias (`PATH=ALIAS`) and can include format overrides (like `-dlim` or `-encoding`):

```bash
pytae -file "emp.parquet=emp; dept.csv=dept,dlim=',' ; sales.txt=sales,dlim='|'" ...
```

---

## Joining Datasets (`-join`)

Merges two frames (or folds in the running pipeline result `data`):

| Parameter | Required? | Meaning |
|---|---|---|
| `left=`, `right=` | **Yes** | A `-file` alias, or the keyword `data` for the running pipeline view |
| `on=` | **Yes** | Shared key column(s), or `left_col:right_col` mapping |
| `how=` | No (default: `inner`) | `inner`, `left`, `right`, `outer`, `cross` |
| `validate=` | No | Join integrity: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many` |

### Shared Join Keys

```bash
pytae -file "emp.parquet=emp; dept.csv=dept" \
  -join "left=emp,right=dept,on=id" \
  -head 3
```

**Output:**

|   id | name    | dept        |   salary |
|-----:|:--------|:------------|---------:|
|    1 | Alice   | Engineering |    95000 |
|    2 | Bob     | Marketing   |    75000 |
|    3 | Charlie | Sales       |    82000 |

### Different Join Keys (`left:right`)

When key column names differ between datasets, map them using `:`:

```bash
pytae -file "customers.parquet=c; orders.csv=o" \
  -join "left=c,right=o,on='customer_id:cust_id',how=left" \
  -head 5
```

### Join Types (`how=inner|left|right|outer`)

```bash
# Left outer join
pytae -file "a.csv=a; b.csv=b" -join "left=a,right=b,on=id,how=left"
```

**Output:**

| id | val_a | val_b |
|---:|:---|---:|
| 1 | x | 10.0 |
| 2 | y | 20.0 |
| 3 | z | NaN |

### Validating Joins (`validate=one_to_one`)

Protect data integrity by failing immediately if relationships violate cardinality expectations:

```bash
pytae -file "a.csv=a; b.csv=b" -join "left=a,right=b,on=id,validate=one_to_one"
```

### Folding Multiple Files with `data`

Chain multiple `-join` flags in sequence. After the first join, use `data` to refer to the running pipeline result:

```bash
pytae -file "users.csv=u; orders.csv=o; payments.parquet=p" \
  -join "left=u,right=o,on=user_id" \
  -join "left=data,right=p,on=order_id" \
  -head 5
```

---

## Row-Wise Stacking (`-concat`)

Concatenates multiple datasets with matching structures into one unified table (equivalent to Pandas `pd.concat(ignore_index=True)`):

```bash
# Stack three monthly batches
pytae -file "jan.parquet=m1; feb.parquet=m2; mar.parquet=m3" \
  -concat "frames='m1,m2,m3'" \
  -shape
```

---

## Cross-File SQL Queries (`-sql`)

Instead of `-join`, you can start a `-file` pipeline with `-sql`. Every alias in `-file` is registered directly as an in-memory Polars SQL table:

```bash
pytae -file "customers.csv=c; orders.parquet=o" \
  -sql "
    select
      c.name,
      count(o.order_id) as total_orders,
      coalesce(sum(o.amount), 0) as total_spent
    from c
    left join o on c.customer_id = o.customer_id
    group by c.name
    order by total_spent desc
  "
```

**Output:**

| name | total_orders | total_spent |
|:---|---:|---:|
| Alice | 2 | 400.0 |
| Bob | 1 | 300.0 |
| Charlie | 0 | 0.0 |

---

## Exporting Joined Results

In `-file` mode, there is no single source path to infer an in-place output name. Therefore, exporting requires an explicit destination path via `-o`:

```bash
pytae -file "a.parquet=a; b.csv=b" \
  -join "left=a,right=b,on=id" \
  -o joined_output.parquet
```

> [!NOTE]
> - Exporting from a multi-file pipeline requires an explicit target file name (e.g. `-o out.parquet`). In-place format conversion (`-o csv`) cannot infer an output name without a single positional source file.
> - Glob-pattern batch conversion (`pytae 'data/*.parquet' -o csv`) is a separate single-file batch operation and cannot be combined with `-file`.

################################################################################
# FILE: docs/detailed_docs/cli/mutate.md
################################################################################
# CLI Feature Guide: Mutating & Computing Columns

[← Back to Master Reference](../../pytae.md)

Compute new columns or overwrite existing columns with mathematical formulas, ratios, boolean indicators, and Pandas expressions using `-mutate`.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Basic Arithmetic & Unit Conversion](#basic-arithmetic--unit-conversion)
- [Defining Multiple Columns](#defining-multiple-columns)
- [Multi-Column Transforms](#multi-column-transforms)
- [Boolean Indicators & Flags](#boolean-indicators--flags)
- [Conditional Logic with `if_else`](#conditional-logic-with-if_else)
- [Multi-Tiered Branching with `case_when`](#multi-tiered-branching-with-case_when)
- [Value Recoding with `map()`](#value-recoding-with-map)
- [Inline Type Casting (`int(_)`, `float(_)`, `str(_)`)](#inline-type-casting)
- [Window Functions (`first`, `last`, `shift`, `cumsum`)](#window-functions)
- [String Methods & Null Checks](#string-methods--null-checks)
- [Handling Column Names With Spaces](#handling-column-names-with-spaces)
- [Grouped Mutations (`-by` + `-mutate`)](#grouped-mutations--by--mutate)
- [Loading Specs From a File (`@specs.txt`)](#loading-specs-from-a-file-specstxt)
- [Quoting Syntax Rules](#quoting-syntax-rules)

---

## Overview & Rules

The `-mutate` flag evaluates mathematical, logical, and window expressions using Polars' multithreaded SIMD vector engine.

Syntax:
```bash
pytae data.parquet -mutate "new_col = expression"
```

Key Rules:
1. Column names inside the expression must remain **unquoted** so they resolve as variables: `mass_kg = body_mass_g / 1000`.
2. Wrap column names containing spaces in brackets: `[bmi] = [body mass g] / ([bill length mm] ** 2)`.
3. Separate multiple new column definitions with commas: `"col1 = a + b, col2 = a * 2"`.
4. Transform multiple columns at once using `(col1, col2) = expr` with `_` as the current column placeholder.
5. In string expressions, use natural English `or` and `and` without defensive parentheses.

---

## Basic Arithmetic & Unit Conversion

Convert penguin body mass from grams to kilograms:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000" \
  -select "species,body_mass_g,mass_kg" \
  -head 3
```

**Output:**

| species   |   body_mass_g |   mass_kg |
|:----------|--------------:|----------:|
| Adelie    |          3750 |      3.75 |
| Adelie    |          3800 |      3.8  |
| Adelie    |          3250 |      3.25 |

---

## Defining Multiple Columns

Define multiple computed fields in a single `-mutate` invocation:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -select "species,mass_kg,bill_ratio" \
  -round 2 \
  -head 3
```

**Output:**

| species   |   mass_kg |   bill_ratio |
|:----------|----------:|-------------:|
| Adelie    |      3.75 |         2.09 |
| Adelie    |      3.8  |         2.27 |
| Adelie    |      3.25 |         2.24 |

---

## Multi-Column Transforms

Apply the same formula across multiple columns simultaneously using parentheses `(...)` on the left-hand side and `_` as the placeholder for each matched column (the `pytae` equivalent of R `dplyr::across()`):

```bash
# Convert multiple bill columns in-place from mm to cm
pytae penguins.parquet \
  -mutate "(bill_length_mm, bill_depth_mm) = _ / 10" \
  -select "species,bill_length_mm,bill_depth_mm" \
  -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             3.91 |            1.87 |
| Adelie    |             3.95 |            1.74 |
| Adelie    |             4.03 |            1.8  |

### Creating New Columns with a Suffix or Prefix

Attach a suffix after `)` or a prefix before `(` to create new columns instead of overwriting the originals:

```bash
# Creates bill_length_mm_cm and bill_depth_mm_cm
pytae penguins.parquet \
  -mutate "(bill_length_mm, bill_depth_mm)_cm = _ / 10" \
  -select "bill_length_mm,bill_length_mm_cm,bill_depth_mm,bill_depth_mm_cm" \
  -head 3
```

**Output:**

|   bill_length_mm |   bill_length_mm_cm |   bill_depth_mm |   bill_depth_mm_cm |
|-----------------:|--------------------:|----------------:|-------------------:|
|             39.1 |                3.91 |            18.7 |               1.87 |
|             39.5 |                3.95 |            17.4 |               1.74 |
|             40.3 |                4.03 |            18   |               1.8  |

### Using `select()` Predicates Inside `(...)`

Any [`select`](select.md) criteria (`startswith=`, `endswith=`, `contains=`, `regex=`, `dtype=numeric`, or slices `start:end`) can be used inside `(...)`:

```bash
# Scale all columns starting with 'bill_'
pytae penguins.parquet \
  -mutate "(startswith=bill_) = _ / 10" \
  -select "species,bill_length_mm,bill_depth_mm" \
  -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             3.91 |            1.87 |
| Adelie    |             3.95 |            1.74 |
| Adelie    |             4.03 |            1.8  |

```bash
# Group-wise z-score standardization across all numeric columns
pytae penguins.parquet \
  -by species \
  -mutate "(dtype=numeric) = (_ - mean(_)) / std(_)" \
  -round 2 \
  -head 3
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             0.12 |            0.29 |               -0.99 |          0.11 | Male   |
| Adelie    | Torgersen |             0.27 |           -0.78 |               -0.19 |          0.22 | Female |
| Adelie    | Torgersen |             0.57 |           -0.28 |                1.25 |         -0.98 | Female |

---

## Boolean Indicators & Flags

Create binary flag columns by evaluating boolean comparisons:

```bash
pytae penguins.parquet \
  -mutate "is_heavy = body_mass_g > 4000" \
  -select "species,body_mass_g,is_heavy" \
  -head 3
```

**Output:**

| species   |   body_mass_g | is_heavy   |
|:----------|--------------:|:-----------|
| Adelie    |          3750 | False      |
| Adelie    |          3800 | False      |
| Adelie    |          3250 | False      |

---

<a id="conditional-logic-with-if_else"></a>
## Conditional Logic with `if_else`

Use `if_else(condition, true_val, false_val)` to perform vectorized binary branching.

### Example 1: Assigning Category Labels

Inside the outer double quotes `"-mutate \"...\""`, use single quotes `'...'` for string literals:

```bash
pytae tips.parquet \
  -mutate "generous = if_else(tip > 3.0, 'Yes', 'No')" \
  -select "total_bill,tip,generous" \
  -head 5
```

**Output:**

|   total_bill |   tip | generous   |
|-------------:|------:|:-----------|
|        16.99 |  1.01 | No         |
|        10.34 |  1.66 | No         |
|        21.01 |  3.5  | Yes        |
|        23.68 |  3.31 | Yes        |
|        24.59 |  3.61 | Yes        |

### Example 2: Fallback to an Existing Column or Floor Value

Pass column names (unquoted) or numeric scalars for either branch:

```bash
# Set a tip floor at 2.00, preserving the actual tip if higher
pytae tips.parquet \
  -mutate "adj_tip = if_else(tip < 2.0, 2.0, tip)" \
  -select "total_bill,tip,adj_tip" \
  -head 5
```

**Output:**

|   total_bill |   tip |   adj_tip |
|-------------:|------:|----------:|
|        16.99 |  1.01 |      2    |
|        10.34 |  1.66 |      2    |
|        21.01 |  3.5  |      3.5  |
|        23.68 |  3.31 |      3.31 |
|        24.59 |  3.61 |      3.61 |

### Example 3: Compound Conditions with `and` / `or`

Combine multiple conditions naturally using `and`, `or`, or `&`, `|`:

```bash
pytae tips.parquet \
  -mutate "high_spender = if_else(total_bill > 20 and tip > 3.0, 'High', 'Standard')" \
  -select "total_bill,tip,high_spender" \
  -head 5
```

**Output:**

|   total_bill |   tip | high_spender   |
|-------------:|------:|:---------------|
|        16.99 |  1.01 | Standard       |
|        10.34 |  1.66 | Standard       |
|        21.01 |  3.5  | High           |
|        23.68 |  3.31 | High           |
|        24.59 |  3.61 | High           |

---

<a id="multi-tiered-branching-with-case_when"></a>
## Multi-Tiered Branching with `case_when`

For multiple conditions evaluated in priority order, use `case_when((cond1, val1), (cond2, val2), default=fallback)`:

```bash
pytae tips.parquet \
  -mutate "tier = case_when((total_bill >= 25, 'High'), (total_bill >= 15, 'Medium'), default='Low')" \
  -select "total_bill,tier" \
  -head 6
```

**Output:**

|   total_bill | tier   |
|-------------:|:-------|
|        16.99 | Medium |
|        10.34 | Low    |
|        21.01 | Medium |
|        23.68 | Medium |
|        24.59 | Medium |
|        25.29 | High   |

---

<a id="value-recoding-with-map"></a>
## Value Recoding with `map()`

Recode categorical values via a dictionary lookup executed vectorially in the Polars engine:

```bash
# Two-argument: recode mapped values, preserve unmapped rows intact
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})" -head 5

# Three-argument with literal fallback: replace unmapped rows with 'Other'
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD'}, 'Other')" -head 5

# Three-argument with column fallback: pull replacement from another column
pytae deals.parquet -mutate "party = map(deal_type, {'Direct': 'DIR'}, broker_code)" -head 5
```

---

<a id="inline-type-casting"></a>
## Inline Type Casting (`int(_)`, `float(_)`, `str(_)`)

Cast column types directly inside `-mutate` using standard constructor functions:

```bash
# Convert individual columns
pytae data.csv -mutate "id = str(id), score = int(score), val = float(val)" -head 5

# Multi-column batch casting with across syntax
pytae data.csv -mutate "(col1, col2, col3) = int(_)" -head 5
```

---

<a id="window-functions"></a>
## Window Functions (`first`, `last`, `shift`, `cumsum`)

When combined with `-by`, window functions compute group-partitioned statistics and drifts:

### 1. Group Baselines & Boundaries (`first`, `last`)
```bash
pytae stocks.parquet \
  -by ticker \
  -mutate "baseline = first(price), drift = price - first(price), final = last(price)" \
  -head 5
```

### 2. Time-Series Shifts, Differences, & Growth (`shift`, `lag`, `lead`)
```bash
pytae stocks.parquet \
  -by ticker \
  -mutate "prev = shift(price, 1), diff = price - shift(price, 1), ret = price / shift(price, 1) - 1" \
  -head 5
```

### 3. Cumulative Running Statistics (`cumsum`, `cummax`, `cummin`)
```bash
pytae sales.parquet \
  -by region \
  -mutate "running_total = amount.cumsum(), peak = amount.cummax()" \
  -head 5
```

---

<a id="string-methods--null-checks"></a>
## String Methods & Null Checks

Vectorized string transforms and missing value predicates execute directly in `-mutate`:
- **String Matching**: `.str.contains('pat')`, `.str.starts_with('pre')`, `.str.ends_with('suf')`
- **String Transformations**: `.str.upper()`, `.str.lower()`, `.str.strip()`, `.str.len()`
- **Null Checks**: `.is_null()`, `.is_not_null()`, `fillna(col, default)`

```bash
pytae penguins.parquet \
  -mutate "species_upper = species.str.upper(), is_gen = species.str.starts_with('Gen'), has_sex = sex.is_not_null()" \
  -head 5
```

---

## Handling Column Names With Spaces

If column names have spaces or hyphens, wrap them in square brackets:

```bash
pytae dataset.csv -mutate "[total weight] = [body mass g] + [extra weight]"
```

**Output:**

| body mass g | extra weight | total weight |
|---:|---:|---:|
| 3000 | 500 | 3500 |
| 4000 | 200 | 4200 |
| 5000 | 300 | 5300 |

---

<a id="grouped-mutations--by--mutate"></a>
## Grouped Mutations (`-by` + `-mutate`)

Compute window transforms and group-level statistics (mean, sum, min, max, median, std, var, row count) broadcast back to every row without collapsing the dataset.

Combine `-by` with `-mutate`:

```bash
# Calculate average tip per day, difference from average, and group sample size
pytae tips.parquet \
  -select "day,total_bill,tip" \
  -by day \
  -mutate "avg_tip = mean(tip), diff = tip - avg_tip, cnt = count()" \
  -head 5 \
  -round 2
```

**Output:**

| day   |   total_bill |   tip |   avg_tip |   diff |   cnt |
|:------|-------------:|------:|----------:|-------:|------:|
| Sun   |        16.99 |  1.01 |      3.26 |  -2.25 |    76 |
| Sun   |        10.34 |  1.66 |      3.26 |  -1.6  |    76 |
| Sun   |        21.01 |  3.5  |      3.26 |   0.24 |    76 |
| Sun   |        23.68 |  3.31 |      3.26 |   0.05 |    76 |
| Sun   |        24.59 |  3.61 |      3.26 |   0.35 |    76 |

### Injected Aggregation Helpers

Within grouped `-mutate` expressions, the following aggregations evaluate per group:
- `mean(col)`, `sum(col)`, `median(col)`, `min(col)`, `max(col)`, `std(col)`, `var(col)`
- `count()`: Group row count (sample size)

### Multi-Column Grouping and Spaced Columns

Pass multiple grouping columns comma-separated, and use square brackets `[col]` for columns with spaces:

```bash
pytae tips.parquet \
  -select "day,time,total_bill,tip" \
  -rename "total_bill:[total bill]" \
  -by "day,time" \
  -mutate "[avg bill] = mean([total bill]), diff = [total bill] - [avg bill]" \
  -head 5 \
  -round 2
```

**Output:**

| day   | time   |   total bill |   tip |   avg bill |   diff |
|:------|:-------|-------------:|------:|-----------:|-------:|
| Sun   | Dinner |        16.99 |  1.01 |      21.41 |  -4.42 |
| Sun   | Dinner |        10.34 |  1.66 |      21.41 | -11.07 |
| Sun   | Dinner |        21.01 |  3.5  |      21.41 |  -0.4  |
| Sun   | Dinner |        23.68 |  3.31 |      21.41 |   2.27 |
| Sun   | Dinner |        24.59 |  3.61 |      21.41 |   3.18 |

### Missing Groups with `-dropna`

By default, rows containing `NA` in grouping columns are treated as their own distinct group so that no data is silently discarded. Chain `-dropna <col>` to exclude missing groups prior to calculation:

```bash
# Drop rows with NaN in grouping column prior to calculation
pytae penguins.parquet -dropna sex -by sex -mutate "avg_mass = mean(body_mass_g)" -select "sex,body_mass_g,avg_mass" -head 3 -round 1
```

**Output:**

| sex | body_mass_g | avg_mass |
|:---|---:|---:|
| Male | 3750.0 | 4545.7 |
| Female | 3800.0 | 3862.3 |
| Female | 3250.0 | 3862.3 |

---

## Loading Specs From a File (`@specs.txt`)

For complex pipelines with many engineered features, store expressions in an external text file:

```text
# features.txt
mass_kg = body_mass_g / 1000
bill_ratio = bill_length_mm / bill_depth_mm
flipper_to_mass = flipper_length_mm / mass_kg
```

Run via:
```bash
pytae penguins.parquet -mutate @features.txt -select "species,mass_kg,bill_ratio,flipper_to_mass" -head 5
```

**Output:**

| species   |   mass_kg |   bill_ratio |   flipper_to_mass |
|:----------|----------:|-------------:|------------------:|
| Adelie    |      3.75 |         2.09 |             48.27 |
| Adelie    |      3.8  |         2.27 |             48.95 |
| Adelie    |      3.25 |         2.24 |             60    |
| Adelie    |    nan    |       nan    |            nan    |
| Adelie    |      3.45 |         1.9  |             55.94 |

---

## Quoting Syntax Rules

In shell environments:
- Enclose the entire argument in double quotes: `-mutate "..."`.
- Inside the expression, use single quotes `'...'` for string literals:
  - Example: `-mutate "status = 'active'"`
  - Standard inner single quotes `'...'` define string literals, matching standard SQL.
- Do NOT quote column names:
  - Correct: `mass_kg = body_mass_g / 1000`
  - Incorrect: `mass_kg = 'body_mass_g' / 1000`

################################################################################
# FILE: docs/detailed_docs/cli/other_utilities.md
################################################################################
# CLI Feature Guide: Other Utilities & Miscellaneous Commands

[← Back to Master Reference](../../pytae.md)

Essential utilities, convenience flags, inspection shortcuts, cleaning helpers, multi-file workflows, I/O modifiers, and formatting options that complement core analytical verbs.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Inspection & Summary Flags](#inspection--summary-flags)
  - [Zero-Scan Parquet Metadata (`-meta`)](#zero-scan-parquet-metadata--meta)
  - [Rows, Shape & Overview (`-head`, `-tail`, `-sample`, `-shape`, `-glimpse`, `-describe`)](#rows-shape--overview--head--tail--sample--shape--glimpse--describe)
  - [Column Names, Data Types & Missing Counts (`-cols`, `-dtype`, `-nulls`)](#column-names-data-types--missing-counts--cols--dtype--nulls)
  - [Distribution & Frequency Analysis (`-freq`, `-hist`)](#distribution--frequency-analysis--freq--hist)
  - [Dataset & Schema Comparison (`-diff`)](#dataset--schema-comparison--diff)
- [Data Cleaning & Header Standardization](#data-cleaning--header-standardization)
  - [Header Cleaning (`-clean_columns`)](#header-cleaning--clean_columns)
  - [Missing Value Imputation (`-fillna`)](#missing-value-imputation--fillna)
  - [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
  - [Renaming Columns (`-rename`)](#renaming-columns--rename)
- [Multi-File Pipelines & Operations](#multi-file-pipelines--operations)
  - [Named Inputs (`-file`)](#named-inputs--file)
  - [Multi-File Joins (`-join`)](#multi-file-joins--join)
  - [Row Stacking (`-concat`)](#row-stacking--concat)
- [Input / Output & Pipeline Modifiers](#input--output--pipeline-modifiers)
  - [Reading Row Caps (`-nrows`)](#reading-row-caps--nrows)
  - [Delimiters & Encodings (`-dlim`, `-encoding`)](#delimiters--encodings--dlim--encoding)
  - [Exporting & Directory Routing (`-o`, `-out_dir`, `-fmt`)](#exporting--directory-routing--o--out_dir--fmt)
  - [Clipboard Export (`-o clip`)](#clipboard-export--o-clip)
  - [Execution Progress (`-progress`)](#execution-progress--progress)
- [Formatting & Display Modifiers](#formatting--display-modifiers)
  - [Rounding Decimals (`-round`)](#rounding-decimals--round)
  - [Interactive Paging (`-pager`)](#interactive-paging--pager)
- [Version & Help Diagnostics](#version--help-diagnostics)

---

## Overview & Quick Reference

| Flag | Category | Syntax / Value | Description |
|---|---|---|---|
| `-head [N]` | Inspection | Integer (default: `5`) | Displays first N rows |
| `-tail [N]` | Inspection | Integer (default: `5`) | Displays last N rows |
| `-sample [N]` | Inspection | Integer (default: `5`) | Displays N randomly sampled rows |
| `-seed N` | Inspection | Integer | Random seed for `-sample` reproducibility |
| `-frac P` | Inspection | Float `0 < P <= 1` | Sample fraction of rows instead of count |
| `-shape` | Inspection | Terminal flag | Prints dataset dimensions `(rows, cols)` |
| `-cols [ORDER]` | Inspection | Optional `asc` or `desc` | Prints column names (file order, or sorted) |
| `-dtype [ORDER]` | Inspection | Optional `asc` or `desc` | Prints column data types |
| `-nulls [ORDER]` | Inspection | Optional `asc` or `desc` | Prints null / NaN count per column |
| `-describe` | Inspection | Flag | Computes summary statistics (count, mean, std, min, max, quartiles) |
| `-glimpse` | Inspection | Flag | Transposed column overview with dtypes and sample values |
| `-meta` | Inspection | Flag | Instant Parquet metadata (row groups, compression, schema) |
| `-diff PATH` | Inspection | File path | Compares schemas, shapes, column drift, and cell values against another dataset |
| `-freq COL` | Inspection | Column name | Renders horizontal ASCII frequency bars with percentages |
| `-hist COL[:BINS]` | Inspection | `col` or `col:bins` | Renders in-terminal ASCII distribution histogram |
| `-clean_columns SPEC` | Cleaning | `strip,fill=_,case=lower,...` | Normalizes messy column header names |
| `-fillna [VAL]` | Cleaning | Scalar or `col:val,...` | Imputes missing values (`null` and `NaN`) |
| `-dropna [COLS]` | Cleaning | Optional comma-separated list | Drops rows containing NaN (across all columns or specified subset) |
| `-rename SPEC` | Cleaning | `old:new,...` | Explicitly renames column headers |
| `-file SPEC` | Multi-File | `path=alias;...` | Loads multiple input files into named aliases |
| `-join SPEC` | Multi-File | `left=a,right=b,on=k,...` | Joins datasets on keys with join validation |
| `-concat SPEC` | Multi-File | `a,b` or `how=outer` | Stacks multiple datasets row-wise |
| `-nrows N` | Input I/O | Integer | Caps rows loaded from disk during read |
| `-dlim STR` | Input I/O | Character (`","`, `"\t"`, `"|"`) | Delimiter for CSV / text files |
| `-encoding ENC` | Input I/O | Encoding name (`utf-8`, `latin1`) | Character encoding for text files |
| `-fmt FORMAT` | Input I/O | `csv`, `parquet`, `jsonl`, `txt` | Format override when reading STDIN or extensionless files |
| `-o TARGET` | Output I/O | File path, format, or `clip` | Exports result or copies to clipboard |
| `-out_dir DIR` | Output I/O | Directory path | Destination directory for exported files |
| `-progress [N]` | Diagnostics | Optional row frequency | Streaming row count progress during read/write |
| `-round N` | Formatting | Integer decimals | Rounds floating-point numbers to N places |
| `-pager` | Output | Flag | Pipes terminal output through interactive system pager (`less`) |
| `-version` | Meta | Flag | Displays pytae version information and exits |
| `-h` / `-help` | Meta | Flag | Displays usage help |

---

## Inspection & Summary Flags

### Zero-Scan Parquet Metadata (`-meta`)
Reads metadata footers in sub-milliseconds without scanning table data:
```bash
pytae transactions.parquet -meta
```

### Rows, Shape & Overview (`-head`, `-tail`, `-sample`, `-shape`, `-glimpse`, `-describe`)
```bash
# Peek at initial or final records
pytae penguins.parquet -head 3
pytae penguins.parquet -tail 3

# Reproducible random sampling
pytae penguins.parquet -sample 5 -seed 42
pytae penguins.parquet -sample -frac 0.05 -seed 42

# Dimensions, schema, and statistical summaries
pytae penguins.parquet -shape
pytae penguins.parquet -glimpse
pytae penguins.parquet -describe
```

### Column Names, Data Types & Missing Counts (`-cols`, `-dtype`, `-nulls`)
```bash
# Column names in file order or sorted
pytae penguins.parquet -cols
pytae penguins.parquet -cols desc

# Column dtypes
pytae penguins.parquet -dtype

# Null value diagnostics per column
pytae penguins.parquet -nulls desc
```

### Distribution & Frequency Analysis (`-freq`, `-hist`)
```bash
# Categorical frequency breakdown with percentage bars
pytae penguins.parquet -freq species

# Numeric distribution histogram directly in terminal
pytae penguins.parquet -hist body_mass_g
pytae penguins.parquet -hist body_mass_g:12
```

### Dataset & Schema Comparison (`-diff`)
Validates schema drift, shape deltas, added/removed columns, and value mismatches between two files:
```bash
pytae raw_v1.parquet -diff raw_v2.parquet
```

---

## Data Cleaning & Header Standardization

### Header Cleaning (`-clean_columns`)
Standardizes headers in order: `strip` -> `strip_special` -> `squeeze` -> `fill` -> `case` -> `dedupe`:
```bash
pytae messy.csv -clean_columns "strip,strip_special,fill=_,case=lower" -head 3
```

### Missing Value Imputation (`-fillna`)
Imputes missing values (`null` and `NaN`) across all columns or specific targets:
```bash
# Impute all numeric missing values with 0
pytae penguins.parquet -fillna 0 -head 5

# Impute specific columns with replacement value
pytae penguins.parquet -fillna "val='Unknown', cols='sex'" -head 5
```

### Dropping Missing Values (`-dropna`)
```bash
# Drop rows with ANY missing value across all columns
pytae penguins.parquet -dropna

# Drop rows missing specific column values
pytae penguins.parquet -dropna "sex,body_mass_g"
```

### Renaming Columns (`-rename`)
```bash
pytae penguins.parquet -rename "body_mass_g:mass,flipper_length_mm:flipper" -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper | mass | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

---

## Multi-File Pipelines & Operations

### Named Inputs (`-file`)
Loads multiple files simultaneously into named aliases:
```bash
pytae -file "emp.parquet=emp; dept.csv=dept" -join "left=emp,right=dept,on=dept_id" -head 5
```

### Multi-File Joins (`-join`)
Performs joins with optional relationship validation:
```bash
pytae -file "sales.parquet=s; stores.parquet=st" \
  -join "left=s,right=st,on=store_id,how=left,validate=many_to_one" \
  -head 5
```

### Row Stacking (`-concat`)
Stacks two or more datasets vertically:
```bash
pytae -file "q1.parquet=a; q2.parquet=b; q3.parquet=c" -concat "a,b,c" -shape
```

---

## Input / Output & Pipeline Modifiers

### Reading Row Caps (`-nrows`)
Stops reading at disk level after N rows (saving RAM and CPU on huge files):
```bash
pytae huge_log.csv -nrows 1000 -shape
```

### Delimiters & Encodings (`-dlim`, `-encoding`)
```bash
pytae records.dat -dlim "|" -shape
pytae legacy.txt -dlim "\t" -encoding latin1 -head 5
```

### Exporting & Directory Routing (`-o`, `-out_dir`, `-fmt`)
```bash
# Convert to Parquet
pytae input.csv -o output.parquet

# Convert and save in specific folder
pytae input.csv -o parquet -out_dir clean_data/

# Specify input format when reading from STDIN
cat data.jsonl | pytae - -fmt jsonl -shape
```

### Clipboard Export (`-o clip`)
Copies intermediate or final pipeline table to the OS clipboard as clean TSV:
```bash
pytae penguins.parquet -by species -agg "mean=body_mass_g:mean" -o clip
```

### Execution Progress (`-progress`)
Displays streaming row status during reading or exporting large datasets:
```bash
pytae huge_events.csv -progress -o events.parquet
```

---

## Formatting & Display Modifiers

### Rounding Decimals (`-round`)
Rounds all numeric columns to N decimals on display:
```bash
pytae penguins.parquet -by species -agg mean -round 2
```

### Interactive Paging (`-pager`)
Pipes output through the terminal pager (`less` / `$PAGER`) to browse wide tables or large summaries:
```bash
pytae penguins.parquet -describe -pager
```

---

## Version & Help Diagnostics

```bash
# Display installed pytae version
pytae -version

# Full command-line flag documentation
pytae -help

# Keyword-focused help with syntax and copy-pasteable examples
pytae -help agg
pytae -help filter
pytae -help mutate
pytae -help select
pytae -help pivot
pytae -help sql
pytae -help reshape
pytae -help arrange
pytae -help head
pytae -help distinct
```

################################################################################
# FILE: docs/detailed_docs/cli/pivot.md
################################################################################
# CLI Feature Guide: 2D Pivot Tables (`-pivot`)

[← Back to Master Reference](../../pytae.md)

`-pivot` provides an Excel-style 2D pivot table engine with universal `r, c, v, a` vocabulary:
- **Rows (`r=`)**: Row dimension(s) (*optional*).
- **Cols (`c=`)**: Column dimension(s) to spread as headers (*optional*).
- **Values (`v=`)**: Measure / metric column(s) to aggregate (*optional*; defaults to row count `n` when omitted).
- **Aggregation (`a=`)**: Summary function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`; default: `sum`).
- **Missing Categories (`dropna=`)**: Retain `NaN` keys when `false` (default: `false`).
- **Empty Intersections (`f_v=`)**: Fill missing grid cells (e.g. `f_v=0`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Excel-Style Pivot Layouts](#excel-style-pivot-layouts)
  - [1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)](#1-2d-grid-with-rows--columns-r-c-v)
  - [2. Frequency Tables & Count Matrices (v= Omitted)](#2-frequency-tables--count-matrices-v-omitted)
  - [3. Vertical Summary Table (`r=`, `v=`)](#3-vertical-summary-table-r-v)
  - [4. Horizontal Summary Table (`c=`, `v=`)](#4-horizontal-summary-table-c-v)
  - [5. Grand Total Summary (`v=`)](#5-grand-total-summary-v)
- [Hierarchical Grouping with Multiple Rows (`r=Region,Store`)](#hierarchical-grouping-with-multiple-rows-rregionstore)
- [Multi-Metric Reporting (`v=Sales,Profit`)](#multi-metric-reporting-vsalesprofit)
- [Filling Empty Intersections (`f_v=0`)](#filling-empty-intersections-f_v0)
- [Guarantees & Differences from `-wide`](#guarantees--differences-from--wide)

---

## Overview & Quick Reference

| Parameter | Meaning | Default | Example |
|---|---|---|---|
| `r` | Row dimension(s) | *None (optional)* | `r=Region` or `r=Region,Store` |
| `c` | Column header dimension(s) | *None (optional)* | `c=Year` or `c=Year,Quarter` |
| `v` | Metric column(s) to aggregate | *Optional (defaults to row counts)* | `v=Sales` or `v=Sales,Profit` |
| `a` | Aggregation function | `sum` | `a=mean`, `a=sum`, `a=count` |
| `dropna` | Drop NA categories | `false` | `dropna=false` (keeps NA groups) |
| `f_v` | Fill for empty cells | `None` (`0` for counts) | `f_v=0` |

---

## Excel-Style Pivot Layouts

Just like dragging fields into Rows and Columns in Excel, `r` and `c` are completely optional:

### 1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean" \
  -round 1
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |   3709.7 |       nan   |     5076 |
| Dream     |   3688.4 |      3733.1 |      nan |
| Torgersen |   3706.4 |       nan   |      nan |

### 2. Frequency Tables & Count Matrices (v= Omitted)

Just like in Excel where omitting a measure counts records, omitting `v=` in `-pivot` automatically computes row counts (`n`), returns clean integer columns (`int64`), and defaults unobserved intersections to `0`:

#### 2D Contingency Table (Cross-Tabulation):
```bash
# Omit v to produce a 2D cross-tabulation count matrix
pytae penguins.parquet -pivot "r=island,c=species"
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |       44 |           0 |      124 |
| Dream     |       56 |          68 |        0 |
| Torgersen |       52 |           0 |        0 |

#### 1D Frequency Breakdown:
```bash
# Omit c and v to produce a 1D frequency breakdown with column 'n'
pytae penguins.parquet -pivot "r=island,sex"
```

**Output:**

| island    | sex    |   n |
|:----------|:-------|----:|
| Biscoe    | Female |  80 |
| Biscoe    | Male   |  83 |
| Biscoe    | nan    |   5 |
| Dream     | Female |  61 |
| Dream     | Male   |  62 |
| Dream     | nan    |   1 |
| Torgersen | Female |  24 |
| Torgersen | Male   |  23 |
| Torgersen | nan    |   5 |

### 3. Vertical Summary Table (`r=`, `v=`)

Omit `c=` to summarize values strictly by row groups (like Excel with only Rows and Values):

```bash
pytae sales.parquet -pivot "r=Region,v=Sales,a=sum"
```

**Output:**

| Region   |   Sales |
|:---------|--------:|
| East     |    4500 |
| West     |    3350 |

### 4. Horizontal Summary Table (`c=`, `v=`)

Omit `r=` to summarize values horizontally across column headers:

```bash
pytae sales.parquet -pivot "c=Year,v=Sales,a=sum"
```

**Output:**

|   2022 |   2023 |   2024 |
|-------:|-------:|-------:|
|   2100 |   2600 |   3150 |

### 5. Grand Total Summary (`v=`)

Omit both `r=` and `c=` for a single-row grand aggregation:

```bash
pytae sales.parquet -pivot "v=Sales,a=sum"
```

**Output:**
```text
 Sales
7850.0
```

---

## Hierarchical Grouping with Multiple Rows (`r=Region,Store`)

Pass comma-separated columns to `r=` to group across multiple levels:

```bash
pytae sales.parquet -pivot "r=Region,Store,c=Year,v=Sales,a=sum"
```

**Output:**

| Region   | Store   |   2023 |   2024 |
|:---------|:--------|-------:|-------:|
| Store    | A       |    700 |    850 |
| Store    | B       |    800 |    950 |
| Store    | C       |    900 |   1100 |

Both `Region` and `Store` appear as clean leading columns without any MultiIndex row complexity.

---

## Multi-Metric Reporting (`v=Sales,Profit`)

Report multiple measures simultaneously across dimensions:

```bash
pytae sales.parquet -pivot "r=Region,c=Year,v=Sales,Profit,a=sum"
```

**Output:**

| Region   |   Profit_2023 |   Profit_2024 |   Sales_2023 |   Sales_2024 |
|:---------|--------------:|--------------:|-------------:|-------------:|
| East     |            90 |           120 |          700 |          850 |
| West     |           110 |           150 |          900 |         1100 |

Column names are automatically flattened into intuitive strings (`Metric_Col`), completely avoiding Pandas MultiIndex tuples.

---

## Filling Empty Intersections (`f_v=0`)

When a category combination has no records, replace the missing cell with a scalar:

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean,f_v=0" \
  -round 1
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |   3709.7 |         0   |   5076   |
| Dream     |   3688.4 |      3733.1 |      0   |
| Torgersen |   3706.4 |         0   |      0   |

---

## Guarantees & Differences from `-wide`

| Feature | `-pivot` (Analytical Reporting) | `-wide` (Pure Reshaping) |
|---|---|---|
| **Purpose** | Multi-dimensional summarization | Format conversion (spread tall to wide) |
| **Silent Aggregation** | **Expected** via `a` (default: `sum`) | **None** (1:1 structural bijection) |
| **Column Selection** | **Automatic**: only touches `r`, `c`, and `v` | Keeps all other columns as row IDs |
| **Index** | Always flat `RangeIndex(0, 1, 2, ...)` | Flat `RangeIndex` |
| **Subtotals & Totals** | None (preserves relational types & chaining) | None |

################################################################################
# FILE: docs/detailed_docs/cli/read_write.md
################################################################################
# CLI Feature Guide: File I/O, Export, & Compression

[← Back to Master Reference](../../pytae.md)

Export pipeline results, batch-convert datasets, route outputs to dedicated directories (`-out_dir`), stream large files with progress bars (`-progress`), and read/write gzip-compressed and JSON Lines formats.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Supported Formats Matrix](#supported-formats-matrix)
- [Reading from STDIN and Pipes](#reading-from-stdin-and-pipes)
- [Export Destinations (`-o`)](#export-destinations--o)
  - [Explicit File Path](#explicit-file-path)
  - [In-Place Format Shorthands](#in-place-format-shorthands)
  - [System Clipboard (`clip`)](#system-clipboard-clip)
- [Target Output Directory (`-out_dir`)](#target-output-directory--out_dir)
  - [Benefits of `-out_dir` over Explicit Paths](#benefits-of--out_dir-over-explicit-paths)
- [Transparent Compression (`.gz`)](#transparent-compression-gz)
- [JSON Lines Format (`.jsonl`, `.ndjson`)](#json-lines-format-jsonl-ndjson)
- [Delimiters & Encodings (`-dlim`, `-encoding`)](#delimiters--encodings--dlim--encoding)
- [Robust Mixed-Type Parquet Export](#robust-mixed-type-parquet-export)
- [Streaming Progress Bars (`-progress [N]`)](#streaming-progress-bars--progress-n)
- [Batch Conversions with Globbing](#batch-conversions-with-globbing)

---

## Overview & Quick Reference

| Flag | Description | Example |
|---|---|---|
| `-o TARGET` | Output destination (file path, format shorthand, or `clip`) | `-o clean.parquet`, `-o csv`, `-o clip` |
| `-out_dir DIR` | Target directory for exported files (requires `-o`) | `-o parquet -out_dir exports/` |
| `-fmt FORMAT` | Input format override when reading from STDIN (`-`) or extensionless files | `-fmt jsonl`, `-fmt csv` |
| `-progress [N]` | Display streaming row progress (default: 200,000 rows/chunk) | `-progress`, `-progress 50000` |
| `-dlim CHAR` | Text field delimiter (`.csv`, `.txt`, `.dat`) | `-dlim "\|"`, `-dlim "\t"` |
| `-encoding ENC` | Text encoding (SAS default `utf-8`, dat default `latin-1`) | `-encoding latin-1` |

---

## Supported Formats Matrix

| Format | Extension | Read | Write | Notes |
|---|---|---|---|---|
| **Parquet** | `.parquet`, `.pq` | ✓ | ✓ | Fast columnar binary format with embedded schema and snappy compression |
| **CSV** | `.csv` | ✓ | ✓ | Standard comma-delimited tabular text |
| **Delimited Text** | `.txt` | ✓ | ✓ | Defaults to tab-delimited (`\t`); customizable via `-dlim` |
| **Pipe-Delimited Data** | `.dat` | ✓ | ✓ | Defaults to pipe-delimited (`\|`) and `latin-1` encoding |
| **JSON Lines** | `.jsonl`, `.ndjson` | ✓ | ✓ | Line-delimited JSON records, streamed in chunks |
| **Compressed Gzip** | `.csv.gz`, `.txt.gz`, `.dat.gz`, `.jsonl.gz` | ✓ | ✓ | Transparent on-the-fly streaming compression and decompression |
| **SAS Dataset** | `.sas7bdat` | ✓ | — | SAS binary dataset format (read-only; export to Parquet or CSV) |

---

## Reading from STDIN and Pipes

`pytae` can read tabular streams directly from standard input (STDIN). With **auto-pipe detection**, you can pipe directly into `pytae` without typing an explicit `-`:

```bash
# Direct pipe (no dash needed!)
cat penguins.csv | pytae -head 5
curl -s https://example.com/events.csv | pytae -by event_type -count

# Explicit dash also fully supported
cat penguins.csv | pytae - -head 5
curl -s https://example.com/events.jsonl | pytae - -fmt jsonl -by event_type -count
```

When reading from STDIN, `pytae` automatically inspects the first chunk to sniff the format (`csv` vs `jsonl`). You can explicitly specify or force the input format using `-fmt`:
- `-fmt csv`
- `-fmt jsonl` / `-fmt ndjson`
- `-fmt txt` / `-fmt tsv`
- `-fmt parquet`

---

## Export Destinations (`-o`)

### Explicit File Path

Write directly to an explicit target filename:

```bash
# Save subset to Parquet
pytae penguins.parquet -select "species,body_mass_g" -o subset.parquet

# Convert SAS7BDAT to Parquet
pytae sales.sas7bdat -o sales.parquet
```

**Output:**
```text
Wrote 344 rows to subset.parquet
```

### In-Place Format Shorthands

Specify just a format name (`csv`, `parquet`, `txt`, `dat`, `jsonl`, `csv.gz`, `jsonl.gz`) to export alongside the source file with its extension changed:

```bash
pytae penguins.parquet -o csv
```

**Output:**
```text
Wrote 344 rows to penguins.csv
```

### System Clipboard (`clip`)

#### Exporting to Clipboard (`-o clip`)
Copies the output table or report directly to the system clipboard (suppressing stdout printing):

```bash
pytae penguins.parquet -head 5 -o clip
```

#### Ingesting from Clipboard (`pytae clip`)
Directly read and analyze tabular data copied to your system clipboard (e.g. from Excel, web tables, or Slack) without creating a temporary file:

```bash
# Copy a table in your browser/Excel, then immediately query it:
pytae clip -head 5
pytae clip -filter "sales > 100" -by region -agg "total = sales:sum"
```

---

## Target Output Directory (`-out_dir`)

Direct converted files into a specific folder. Pytae automatically creates the target folder if it does not exist:

```bash
# Export single file to target folder
pytae penguins.parquet -o csv -out_dir processed/

# Batch conversion with output directory
pytae raw_data.csv -o parquet -out_dir parquet_lake/
```

**Output:**
```text
Wrote 344 rows to processed/penguins.csv
```

> [!NOTE]
> When running batch exports into `-out_dir`, pytae validates and prevents destination filename collisions across different source folders.

### Benefits of `-out_dir` over Explicit Paths

While providing a full target path directly in `-o` (e.g., `pytae raw.csv -o parquet_lake/raw.parquet`) works well for single files, pairing a format shorthand with `-out_dir` (e.g., `pytae raw.csv -o parquet -out_dir parquet_lake/`) provides substantial advantages:

1. **Mandatory for Batch Conversions & Globs**:
   When converting multiple files at once, specifying an explicit filename in `-o` fails because all incoming datasets would attempt to overwrite the exact same destination file. Using `-out_dir` automatically preserves each file's stem name across the batch:
   ```bash
   # Converts raw/jan.csv -> parquet_lake/jan.parquet, raw/feb.csv -> parquet_lake/feb.parquet, etc.
   pytae "raw/*.csv" -o parquet -out_dir parquet_lake/
   ```

2. **Eliminates Shell Boilerplate in Pipelines**:
   In automated scripts or CI/CD pipelines where input filenames are dynamic variables (`$INPUT_FILE`), you do not need shell manipulation (`basename`, parameter expansion `${f%.*}`) to compute the new path:
   ```bash
   # Without -out_dir: verbose and fragile shell manipulation
   pytae "$INPUT_FILE" -o "parquet_lake/$(basename "${INPUT_FILE%.*}").parquet"

   # With -out_dir: clean and declarative
   pytae "$INPUT_FILE" -o parquet -out_dir parquet_lake/
   ```

3. **Compound Extension & Compression Awareness**:
   Pytae understands multi-part extensions like `.csv.gz` or `.jsonl.gz`. Using `-o parquet -out_dir parquet_lake/` cleanly strips both the `.gz` and `.csv` extensions, generating `parquet_lake/data.parquet` rather than `parquet_lake/data.csv.parquet`.

4. **Automatic Directory Creation & Collision Guarding**:
   Target directories specified in `-out_dir` are automatically created (`mkdir -p`) if they do not already exist. Pytae also verifies that batch inputs from different source directories sharing the same filename do not silently overwrite one another.

#### Summary Comparison

| Capability | Explicit Path (`-o path/name.ext`) | Directory Routing (`-o <format> -out_dir <dir>`) |
|---|---|---|
| **Single known destination** | `pytae raw.csv -o lake/clean.parquet` | `pytae raw.csv -o parquet -out_dir lake/` |
| **Batch / Glob conversions** | ❌ Fails (destination collision error) | `pytae "raw/*.csv" -o parquet -out_dir lake/` |
| **Shell scripts & variables** | Requires `basename` / `${f%.*}` manipulation | Declarative: `pytae "$FILE" -o parquet -out_dir lake/` |
| **Compressed source (`.csv.gz`)** | Manual stem cleanup required | Auto-strips compound extension to `.parquet` |
| **Destination directory** | Auto-creates parent folder | Auto-creates directory tree (`mkdir -p`) |


---

## Transparent Compression (`.gz`)

Read and write gzip-compressed tabular files directly without decompressing intermediate files onto disk:

```bash
# Compress CSV to gzip
pytae large.csv -o large.csv.gz

# Ingest compressed CSV and convert directly to Parquet
pytae large.csv.gz -o parquet

# Export Parquet to compressed JSON Lines
pytae events.parquet -o events.jsonl.gz
```

---

## JSON Lines Format (`.jsonl`, `.ndjson`)

Full chunked streaming support for newline-delimited JSON records:

```bash
# Inspect JSON Lines structure
pytae web_traffic.jsonl -shape -cols

# Convert JSON Lines to Parquet
pytae web_traffic.jsonl -o parquet
```

---

## Delimiters & Encodings (`-dlim`, `-encoding`)

### Delimiter (`-dlim`)

Override field separators for delimited text files:

```bash
# Read semicolon-delimited CSV and convert to Parquet
pytae european_data.csv -dlim ";" -o european_data.parquet

# Export with custom delimiter
pytae data.parquet -dlim "|" -o pipe_separated.txt
```

### Encoding (`-encoding`)

Handle non-UTF-8 character encodings:

```bash
pytae legacy_data.sas7bdat -encoding latin-1 -o modern.parquet
```

---

## Robust Mixed-Type Parquet Export

When converting messy datasets (such as CSV or SAS tables containing mixed strings, integers, and floats within an `object` column) to Parquet, PyArrow typically raises an `ArrowInvalid` conversion error:
```text
pyarrow.lib.ArrowInvalid: Could not convert '0828' with type str: tried to convert to double
```

`pytae` automatically intercepts `ArrowInvalid` during Parquet writes, safely converts the problematic mixed columns to clean strings with a clear `UserWarning`, and completes the export without crashing.

---

## Streaming Progress Bars (`-progress [N]`)

When converting large files with millions of rows, `-progress` shows real-time progress and processes data in memory-efficient chunks:

```bash
# Default chunk size (200,000 rows per chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress

# Custom chunk size (50,000 rows per chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress 50000
```

**Output:**
```text
writing... 1200000/5000000 rows (24%)
```

---

## Batch Conversions with Globbing

Convert dozens or hundreds of files at once using shell globbing:

```bash
# Convert all CSV files to Parquet in-place
pytae data/*.csv -o parquet

# Batch convert all Parquet files to compressed CSV in an exports directory
pytae data/*.parquet -o csv.gz -out_dir exports/
```

**Output:**
```text
== data/file1.parquet ==
Wrote 100000 rows to exports/file1.csv.gz
== data/file2.parquet ==
Wrote 150000 rows to exports/file2.csv.gz
```

################################################################################
# FILE: docs/detailed_docs/cli/reshape.md
################################################################################
# CLI Feature Guide: Reshaping (Pure 1-to-1: `-long` & `-wide`)

[← Back to Master Reference](../../pytae.md)

Pure structural 1-to-1 reshaping between long and wide formats without aggregation.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Unpivoting Wide to Long (`-long`)](#unpivoting-wide-to-long--long)
- [Pivoting Long to Wide (`-wide`)](#pivoting-long-to-wide--wide)
  - [1. Pure 1-to-1 Unmelting](#1-pure-1-to-1-unmelting)
  - [2. Explicit Row Index (`r=`)](#2-explicit-row-index-r)
  - [3. Round-Trip Reshaping (`-long` → `-wide`)](#3-round-trip-reshaping--long---wide)
- [Unnesting List & Array Columns (`-explode`)](#unnesting-list--array-columns--explode)
- [When to Use `-pivot` Instead of `-wide`](#when-to-use--pivot-instead-of--wide)

---

## Overview & Quick Reference

`-long` and `-wide` are designed as a **strictly complementary, 1-to-1 reshaping pair**:

| Flag | Description | Key Parameters |
|---|---|---|
| `-long [SPEC]` | Melt numeric columns into rows | `r=` or `id_vars=` (fixed rows), `c=` (metric header), `v=` (value header), `cols=` (optional melt subset) |
| `-wide [SPEC]` | Pure 1-to-1 reshape: spread long rows into headers | `r=` (row index), `c=` (header source), `v=` (values) |

> [!IMPORTANT]
> **`-wide` is strictly for 1-to-1 reshaping without aggregation.** If your data has multiple rows per key combination and requires mathematical summarization (`mean`, `sum`, `count`/`n`), use **[`-pivot`](pivot.md)**.
> For row deduplication, see **[`-distinct`](distinct.md)**; for sorting rows, see **[`-arrange`](arrange.md)**.

---

## Unpivoting Wide to Long (`-long`)

Melts all numeric columns into row-wise key-value pairs (`variable` and `value`), keeping non-numeric identifier columns intact:

```bash
pytae penguins.parquet \
  -select "species,bill_length_mm,bill_depth_mm" \
  -long \
  -head 4
```

**Output:**

| species   | variable       |   value |
|:----------|:---------------|--------:|
| Adelie    | bill_length_mm |    39.1 |
| Adelie    | bill_length_mm |    39.5 |
| Adelie    | bill_length_mm |    40.3 |
| Adelie    | bill_length_mm |   nan   |

Using the unified `rcva` grammar with `r=`, `c=`, and `v=`:
```bash
pytae penguins.parquet -long "r=species,c=metric,v=measurement" -head 4
```

**Output:**

| species   | island    | sex    | metric         |   measurement |
|:----------|:----------|:-------|:---------------|--------------:|
| Adelie    | Torgersen | Male   | bill_length_mm |          39.1 |
| Adelie    | Torgersen | Female | bill_length_mm |          39.5 |
| Adelie    | Torgersen | Female | bill_length_mm |          40.3 |
| Adelie    | Torgersen | nan    | bill_length_mm |         nan   |

---

## Pivoting Long to Wide (`-wide`)

`-wide` performs pure structural un-melting (inverse of `-long`), pivoting values from column `c=` into separate column headers using values from `v=`.

### 1. Pure 1-to-1 Unmelting

Given a long dataset with unique row keys (such as `flights.parquet` with unique `year` + `month` pairs):

```bash
pytae flights.parquet -wide "c=month,v=passengers" -head 3
```

**Output:**

|   year |   Jan |   Feb |   Mar |   Apr |   May |   Jun |   Jul |   Aug |   Sep |   Oct |   Nov |   Dec |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   1949 |   112 |   118 |   132 |   129 |   121 |   135 |   148 |   148 |   136 |   119 |   104 |   118 |
|   1950 |   115 |   126 |   141 |   135 |   125 |   149 |   170 |   170 |   158 |   133 |   114 |   140 |
|   1951 |   145 |   150 |   178 |   163 |   172 |   178 |   199 |   199 |   184 |   162 |   146 |   166 |

### 2. Explicit Row Index (`r=`)

By default, all columns other than `c` and `v` serve as row identifiers. Use `r=` to declare specific row index columns explicitly:

```bash
pytae flights.parquet -wide "r=year,c=month,v=passengers" -head 3
```

**Output:**

|   year |   Jan |   Feb |   Mar |   Apr |   May |   Jun |   Jul |   Aug |   Sep |   Oct |   Nov |   Dec |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   1949 |   112 |   118 |   132 |   129 |   121 |   135 |   148 |   148 |   136 |   119 |   104 |   118 |
|   1950 |   115 |   126 |   141 |   135 |   125 |   149 |   170 |   170 |   158 |   133 |   114 |   140 |
|   1951 |   145 |   150 |   178 |   163 |   172 |   178 |   199 |   199 |   184 |   162 |   146 |   166 |

### 3. Round-Trip Reshaping (`-long` → `-wide`)

Because `-long` and `-wide` are strict 1-to-1 bijections, you can melt and immediately un-melt back to the original tabular structure:

```bash
pytae items.parquet \
  -long "c=variable,v=value" \
  -wide "c=variable,v=value"
```

**Output:**

| id | val1 | val2 |
|:---|---:|---:|
| row1 | 10.0 | 100.0 |
| row2 | 20.0 | 200.0 |
| row3 | 30.0 | 300.0 |

---

## Unnesting List & Array Columns (`-explode`)

When tables contain list, array, or iterable values in cells (such as tags, items, or JSON arrays), `-explode` flattens them into individual rows, duplicating non-exploded column values across each element.

```bash
# Unnest a single list/array column:
pytae events.parquet -explode tags

# Unnest multiple list columns simultaneously:
pytae orders.parquet -explode "items,quantities"
```

### Python API (`df.explode()` / `pt.explode()`)

```python
import pytae as pt

df = pt.read_parquet("events.parquet")

# Unnest via verb function:
flat = pt.explode(df, "tags")

# Or via DataFrame method chaining:
flat = df.explode("items", "quantities")

# Or via pandas accessor:
flat = df.pt.explode("tags")
```

---

## When to Use `-pivot` Instead of `-wide`

| Scenario | Use `-wide` | Use `-pivot` |
|---|:---:|:---:|
| **Unique key-value pairs (1:1 un-melting)** | ✅ Yes | Optional |
| **Duplicate key-value combinations** | ❌ Raises error | ✅ Yes (aggregates) |
| **Mathematical summaries (`sum`, `mean`, etc.)** | ❌ Not supported | ✅ Yes (`a=sum`, `a=mean`) |
| **Two-way frequency counts (`a=count`)** | ❌ Not supported | ✅ Yes (`a=count`) |
| **Fill empty cells (`f_v=0`)** | ❌ (leaves `NaN`) | ✅ Yes (`f_v=0`) |

If duplicate keys are passed to `-wide`, `pytae` stops immediately and directs you to `-pivot`:

```text
pytae: error: wide() encountered duplicate entries for index [...] and column '...'. wide() is strictly for 1-to-1 reshaping without aggregation. Use pt.pivot() / -pivot to summarize or aggregate duplicate entries.
```

👉 See the complete **[2D Pivot Tables Guide](pivot.md)** for all multi-dimensional aggregation patterns.

################################################################################
# FILE: docs/detailed_docs/cli/select.md
################################################################################
# CLI Feature Guide: Column Selection

[← Back to Master Reference](../../pytae.md)

Select, filter, reorder, and exclude columns using names, negative prefixes, ranges, pattern matching, or data types with `-select`.

---

## Contents

- [Overview](#overview)
- [Selecting Explicit Columns](#selecting-explicit-columns)
- [Negative Selection & Exclusion (`!col`, `!start:end`)](#negative-selection--exclusion)
- [Slice Notation (`start:end`)](#slice-notation-startend)
- [Pattern Matching (`contains=`, `startswith=`, `endswith=`, `regex=`)](#pattern-matching)
- [Data Type Filtering (`dtype=`, `exclude_dtype=`)](#data-type-filtering)
- [Chaining `-select` in Pipelines](#chaining--select-in-pipelines)

---

## Overview

`-select` provides unified column management across the entire CLI pipeline, matching the Python library's `pt.select()` verb.

| Capability | Syntax / Flag | Example |
|---|---|---|
| Explicit names | `col1,col2` | `-select "species,island,body_mass_g"` |
| Negative selection | `!col` | `-select "!species"` or `-select "!sex,!year"` |
| Negative slices | `!start:end` | `-select "!bill_length_mm:flipper_length_mm"` |
| Column slice | `start:end` | `-select "bill_length_mm:body_mass_g"` |
| Substring / prefix / suffix | `contains=`, `startswith=`, `endswith=` | `-select "contains=bill"` |
| Regular expression | `regex=PATTERN` | `-select "regex=^bill_.*mm$"` |
| Data type filter | `dtype=numeric` / `exclude_dtype=category` | `-select "dtype=numeric"` |

---

## Selecting Explicit Columns

List column names separated by commas. The output DataFrame columns are ordered exactly as listed in the `-select` argument:

```bash
pytae penguins.parquet -select "species,island,body_mass_g" -head 3
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Adelie    | Torgersen |          3750 |
| Adelie    | Torgersen |          3800 |
| Adelie    | Torgersen |          3250 |

Reorder columns on the fly:
```bash
pytae penguins.parquet -select "body_mass_g,species" -head 3
```

**Output:**

|   body_mass_g | species   |
|--------------:|:----------|
|          3750 | Adelie    |
|          3800 | Adelie    |
|          3250 | Adelie    |

---

<a id="negative-selection--exclusion"></a>
## Negative Selection & Exclusion (`!col`, `!start:end`)

You can exclude specific columns, combinations, or slices directly within `-select`. Remaining columns preserve their original relative order.

### Negated Column Names (`!col`)

Prefix a column name with `!` to exclude it. Using `!` avoids any collision with CLI command flags and cleanly reserves `-col` exclusively for descending sort in `-arrange`:

```bash
pytae penguins.parquet -select "!species" -head 3
```

**Output:**

| island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

Multiple negated columns can be combined in quotes:
```bash
pytae penguins.parquet -select "!species, !island, !sex" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

### Negated Slices (`!start:end`)

Exclude a contiguous range of columns:
```bash
pytae penguins.parquet -select "!bill_length_mm:flipper_length_mm" -head 3
```

**Output:**

| species   | island    |   body_mass_g | sex    |
|:----------|:----------|--------------:|:-------|
| Adelie    | Torgersen |          3750 | Male   |
| Adelie    | Torgersen |          3800 | Female |
| Adelie    | Torgersen |          3250 | Female |

---

## Slice Notation (`start:end`)

Select a contiguous range of columns from `start` up to and including `end` (using pandas column position order):

```bash
pytae penguins.parquet -select "bill_length_mm:body_mass_g" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

---

## Pattern Matching

Match column names dynamically without typing every name:

| Token | Description | Example |
|---|---|---|
| `contains=TEXT` | Column names containing `TEXT` | `contains=bill` |
| `startswith=PREFIX` | Column names starting with `PREFIX` | `startswith=bill_` |
| `endswith=SUFFIX` | Column names ending with `SUFFIX` | `endswith=_mm` |
| `regex=PATTERN` | Column names matching regular expression | `regex=^bill_.*mm$` |

### Example: Contains

```bash
pytae penguins.parquet -select "contains=bill" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |
|-----------------:|----------------:|
|             39.1 |            18.7 |
|             39.5 |            17.4 |
|             40.3 |            18   |

### Combining names with pattern tokens

```bash
pytae penguins.parquet -select "species,contains=bill" -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             39.1 |            18.7 |
| Adelie    |             39.5 |            17.4 |
| Adelie    |             40.3 |            18   |

---

## Data Type Filtering

Select or exclude columns by data type:

| Token | Description |
|---|---|
| `dtype=numeric` | Numeric columns (`int64`, `float64`, etc.) |
| `dtype=object` / `dtype=str` | String or object columns |
| `dtype=datetime` | Datetime / timestamp columns |
| `exclude_dtype=category` | Exclude categorical columns |

### Example: Numeric Only

```bash
pytae penguins.parquet -select "dtype=numeric" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

---

## Chaining `-select` in Pipelines

`-select` can be repeated across intermediate pipeline steps (e.g. after `-mutate` or `-agg`), or chained sequentially to filter then subtract:

```bash
# Select numeric columns, then subtract bill_depth_mm
pytae penguins.parquet -select "dtype=numeric" -select "-bill_depth_mm" -head 3
```

**Output:**

|   bill_length_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|--------------------:|--------------:|
|             39.1 |                 181 |          3750 |
|             39.5 |                 186 |          3800 |
|             40.3 |                 195 |          3250 |

```bash
# Narrowing output columns after an aggregation
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = body_mass_g:mean, total = count" \
  -select "species,avg_mass"
```

**Output:**

| species   |   avg_mass |
|:----------|-----------:|
| Adelie    |    3700.66 |
| Chinstrap |    3733.09 |
| Gentoo    |    5076.02 |

################################################################################
# FILE: docs/detailed_docs/cli/sql.md
################################################################################
# CLI Feature Guide: SQL Engine

[← Back to Master Reference](../../pytae.md)

Execute full analytical SQL queries directly against tabular files and in-memory pipeline views via Polars SQLContext using `-sql`.

---

## Contents

- [Overview & Architecture](#overview--architecture)
- [Basic Queries Against Table `data`](#basic-queries-against-table-data)
- [Aggregations & Grouping](#aggregations--grouping)
- [Window Functions](#window-functions)
- [Common Table Expressions (CTEs)](#common-table-expressions-ctes)
- [Columns With Spaces & Identifier Quoting](#columns-with-spaces--identifier-quoting)
- [Reading SQL From File (`@query.sql`)](#reading-sql-from-file-querysql)
- [Multi-File SQL Joins](#multi-file-sql-joins)

---

## Overview & Architecture

Pytae integrates the native Polars SQL engine (`SQLContext`) to provide zero-copy, vectorized SQL execution directly against your data without external dependencies:
- In single-file pipelines, the current dataset view is queryable as table **`data`**.
- In multi-file mode (`-file`), each file alias (e.g. `df1`, `df2`) is queryable directly by name.
- SQL can be inserted at any point in the pipeline and chained with other pytae flags.

---

## Basic Queries Against Table `data`

Filter and select columns with standard SQL syntax:

```bash
pytae penguins.parquet -sql "select species, island, body_mass_g from data where body_mass_g > 5500" -head 3
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5550 |

---

## Aggregations & Grouping

Perform group aggregations, aliases, and ordering:

```bash
pytae penguins.parquet \
  -sql "select species, count(*) as count, round(avg(body_mass_g), 1) as avg_mass from data group by species order by avg_mass desc"
```

**Output:**

| species   |   count |   avg_mass |
|:----------|--------:|-----------:|
| Gentoo    |     124 |     5076   |
| Chinstrap |      68 |     3733.1 |
| Adelie    |     152 |     3700.7 |

---

## Window Functions

Run analytical window functions such as `ROW_NUMBER()`, `RANK()`, or running totals:

```bash
# Top 2 heaviest penguins per species
pytae penguins.parquet \
  -sql "select species, body_mass_g, row_number() over (partition by species order by body_mass_g desc) as rnk from data where body_mass_g is not null" \
  -filter "rnk <= 2"
```

**Output:**

| species   |   body_mass_g |   rnk |
|:----------|--------------:|------:|
| Adelie    |          4775 |     1 |
| Adelie    |          4725 |     2 |
| Chinstrap |          4800 |     1 |
| Chinstrap |          4550 |     2 |
| Gentoo    |          6300 |     1 |
| Gentoo    |          6050 |     2 |

---

## Common Table Expressions (CTEs)

Complex multi-step queries with `WITH` clauses work seamlessly:

```bash
pytae penguins.parquet -sql "
  with summary as (
    select species, avg(body_mass_g) as avg_mass
    from data
    where body_mass_g is not null
    group by species
  )
  select * from summary order by avg_mass desc
"
```

**Output:**

| species   |   avg_mass |
|:----------|-----------:|
| Gentoo    |    5076.02 |
| Chinstrap |    3733.09 |
| Adelie    |    3700.66 |

---

## Columns With Spaces & Identifier Quoting

Standard SQL quoting applies:
- Column names with spaces must be escaped with escaped double quotes `\"col a\"` or brackets `[col a]`.
- String literals must use single quotes `'val'`.

```bash
pytae data.parquet -sql "select \"body mass g\", \"bill length mm\" from data where species = 'Adelie'"
```

---

## Reading SQL From File (`@query.sql`)

For long or reusable queries, place the SQL query in a `.sql` file:

```sql
-- analysis.sql
SELECT
    species,
    island,
    COUNT(*) AS total_penguins,
    ROUND(AVG(body_mass_g), 2) AS mean_weight
FROM data
WHERE sex IS NOT NULL
GROUP BY species, island
ORDER BY mean_weight DESC;
```

Execute via:
```bash
pytae penguins.parquet -sql @analysis.sql
```

**Output:**

| species | island | total_penguins | mean_weight |
|:---|:---|---:|---:|
| Gentoo | Biscoe | 119 | 5092.44 |
| Chinstrap | Dream | 68 | 3733.09 |
| Adelie | Biscoe | 44 | 3709.66 |
| Adelie | Torgersen | 47 | 3708.51 |
| Adelie | Dream | 55 | 3701.36 |

---

## Multi-File SQL Joins

In `-file` mode, combine disparate datasets using standard SQL `JOIN`:

```bash
pytae -file "customers.csv=c; orders.parquet=o" \
  -sql "select c.customer_id, c.name, count(o.order_id) as num_orders, sum(o.amount) as total_spent from c left join o on c.customer_id = o.customer_id group by c.customer_id, c.name order by c.customer_id"
```

**Output:**

| customer_id | name | num_orders | total_spent |
|---:|:---|---:|---:|
| 1 | Alice | 2 | 400.0 |
| 2 | Bob | 1 | 300.0 |
| 3 | Charlie | 0 | NaN |

################################################################################
# NOTEBOOK: docs/detailed_docs/library/agg.ipynb
################################################################################
# Notebook: agg.ipynb

# `agg` — Reference

`agg` aggregates numeric columns with grouping inherited from standalone `pt.by()` (or computes a whole-table summary when no grouping is set).

### Primary Calling Paradigms

1. **Explicit Aliasing (`alias = "col:operation"`) — Recommended**:
   Every output column is explicitly declared as a keyword argument. No columns are created on the fly with unexpected suffixes.
   ```python
   df.by("species").agg(
       n="count",
       avg_bill="bill_length_mm:mean",
       total_mass="body_mass_g:sum",
       max_mass="body_mass_g:max",
   )
   ```

2. **1-to-1 Column Preservation (`col = "operation"`)**:
   Keep the original column name unchanged when performing a single aggregation on that column:
   ```python
   df.by("species").agg(
       n="count",
       bill_length_mm="mean",
       body_mass_g="sum",
   )
   ```

3. **Mixing Both Paradigms**:
   Combine preserved column names and explicit aliases seamlessly in a single `.agg()` call:
   ```python
   tips.by("smoker", "time").agg(
       cnt="count",
       total_bill="mean",       # preserved 1-to-1 column name
       avg_tip="tip:mean",      # explicit alias
       max_tip="tip:max",       # explicit alias
   )
   ```

4. **Columns with Spaces (String Specifications)**:
   Bracket spaced columns matching the CLI `-agg` flag:
   ```python
   df.by("species").agg("[avg bill] = [total bill]:mean, cnt = count")
   ```

5. **Table-Wide Uniform Aggregations**:
   Aggregate all numeric columns uniformly across groups:
   ```python
   df.by("species").agg(a=["mean", "count"])
   ```

6. **Whole-Table Summary**:
   Omit `.by(...)` to compute grand totals across the entire table:
   ```python
   df.agg(n="count", avg_bill="bill_length_mm:mean")
   ```

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
```

## Explicit Aliasing (`alias = "col:operation"`) — Recommended

Every output column name is explicitly declared on the left side of `=`. No columns are created on the fly, eliminating any guessing or magical suffixes.

```python
# Explicit aliases: every output column is named directly (no on-the-fly column creation)
(penguins
 .by('species')
 .agg(
     n='count',
     bill_length_mm='mean',
     mass_sum='body_mass_g:sum',
     mass_mean='body_mass_g:mean',
 )
)
```
Output:
```text
shape: (3, 5)
┌───────────┬─────┬────────────────┬──────────┬─────────────┐
│ species   ┆ n   ┆ bill_length_mm ┆ mass_sum ┆ mass_mean   │
│ ---       ┆ --- ┆ ---            ┆ ---      ┆ ---         │
│ str       ┆ i64 ┆ f64            ┆ f64      ┆ f64         │
╞═══════════╪═════╪════════════════╪══════════╪═════════════╡
│ Adelie    ┆ 152 ┆ 38.791391      ┆ 558800.0 ┆ 3700.662252 │
│ Chinstrap ┆ 68  ┆ 48.833824      ┆ 253850.0 ┆ 3733.088235 │
│ Gentoo    ┆ 124 ┆ 47.504878      ┆ 624350.0 ┆ 5076.01626  │
└───────────┴─────┴────────────────┴──────────┴─────────────┘
```

## Mixing Preserved Column Names & Explicit Aliases

You can cleanly combine 1-to-1 preserved column names (`col='operation'`) and explicit aliases (`alias='col:operation'`) in the same `.agg()` call. Output column order strictly follows parameter order.

```python
# Place count first (n at front), then preserved columns and explicit aliases:
# - cnt='count': row count
# - total_bill='mean': 1-to-1 preserved column name (mean of total_bill kept as total_bill)
# - avg_tip='tip:mean', max_tip='tip:max': explicit aliases (no columns created on the fly)
(
    tips
    .select('smoker', 'time', 'total_bill', 'tip')
    .by('smoker', 'time')
    .agg(
        cnt='count',
        total_bill='mean',
        avg_tip='tip:mean',
        max_tip='tip:max',
    )
)
```
Output:
```text
shape: (4, 6)
┌────────┬────────┬─────┬────────────┬──────────┬─────────┐
│ smoker ┆ time   ┆ cnt ┆ total_bill ┆ avg_tip  ┆ max_tip │
│ ---    ┆ ---    ┆ --- ┆ ---        ┆ ---      ┆ ---     │
│ cat    ┆ cat    ┆ i64 ┆ f64        ┆ f64      ┆ f64     │
╞════════╪════════╪═════╪════════════╪══════════╪═════════╡
│ No     ┆ Dinner ┆ 106 ┆ 20.09566   ┆ 3.126887 ┆ 9.0     │
│ No     ┆ Lunch  ┆ 45  ┆ 17.050889  ┆ 2.673778 ┆ 6.7     │
│ Yes    ┆ Dinner ┆ 70  ┆ 21.859429  ┆ 3.066    ┆ 10.0    │
│ Yes    ┆ Lunch  ┆ 23  ┆ 17.39913   ┆ 2.834348 ┆ 5.0     │
└────────┴────────┴─────┴────────────┴──────────┴─────────┘
```

```python
# You can name the count column anything you like as a keyword argument
# Here maddy='count' creates a column called 'maddy' that holds the group count
(
    penguins
    .select('species', 'island', 'body_mass_g')
    .by('species')
    .agg(maddy='count', body_mass_g='sum')
)
```
Output:
```text
shape: (3, 3)
┌───────────┬───────┬─────────────┐
│ species   ┆ maddy ┆ body_mass_g │
│ ---       ┆ ---   ┆ ---         │
│ str       ┆ i64   ┆ f64         │
╞═══════════╪═══════╪═════════════╡
│ Adelie    ┆ 152   ┆ 558800.0    │
│ Chinstrap ┆ 68    ┆ 253850.0    │
│ Gentoo    ┆ 124   ┆ 624350.0    │
└───────────┴───────┴─────────────┘
```

```python
# Multiple count columns as keyword arguments — each count gets its own name
(
    penguins
    .select('species', 'island', 'body_mass_g')
    .by('species')
    .agg(count='count', countv2='count', body_mass_g='mean')
)
```
Output:
```text
shape: (3, 4)
┌───────────┬───────┬─────────┬─────────────┐
│ species   ┆ count ┆ countv2 ┆ body_mass_g │
│ ---       ┆ ---   ┆ ---     ┆ ---         │
│ str       ┆ i64   ┆ i64     ┆ f64         │
╞═══════════╪═══════╪═════════╪═════════════╡
│ Adelie    ┆ 152   ┆ 152     ┆ 3700.662252 │
│ Chinstrap ┆ 68    ┆ 68      ┆ 3733.088235 │
│ Gentoo    ┆ 124   ┆ 124     ┆ 5076.01626  │
└───────────┴───────┴─────────┴─────────────┘
```

## Table-Wide Uniform Aggregations (`a=...`)

When you want to apply a single aggregation function across **all** numeric columns uniformly without declaring each column individually, pass `a="mean"` (or `a=["mean", "count"]`). Numeric column names are strictly preserved 1-to-1 without mangling or magic suffixes, and `count` adds the canonical tally column `n`.

> [!NOTE]
> **Zero Columns Created On The Fly**: To ensure column names are never invented behind your back (no `col_mean` or `col_sum`), applying multiple metric operations to columns requires explicit output aliases via **Paradigm 2** (e.g. `avg_mass="body_mass_g:mean", max_mass="body_mass_g:max"`). Attempting to apply multiple metric functions without aliases raises an immediate `ValueError`.

```python
# Single metric across all numeric columns + count: names preserved 1-to-1
(
    penguins
    .select("species", "island", "bill_length_mm", "body_mass_g")
    .by("species", "island")
    .agg(a=["mean", "count"])
)
```
Output:
```text
shape: (5, 5)
┌───────────┬───────────┬─────┬────────────────┬─────────────┐
│ species   ┆ island    ┆ n   ┆ bill_length_mm ┆ body_mass_g │
│ ---       ┆ ---       ┆ --- ┆ ---            ┆ ---         │
│ str       ┆ str       ┆ i64 ┆ f64            ┆ f64         │
╞═══════════╪═══════════╪═════╪════════════════╪═════════════╡
│ Adelie    ┆ Biscoe    ┆ 44  ┆ 38.975         ┆ 3709.659091 │
│ Adelie    ┆ Dream     ┆ 56  ┆ 38.501786      ┆ 3688.392857 │
│ Adelie    ┆ Torgersen ┆ 52  ┆ 38.95098       ┆ 3706.372549 │
│ Chinstrap ┆ Dream     ┆ 68  ┆ 48.833824      ┆ 3733.088235 │
│ Gentoo    ┆ Biscoe    ┆ 124 ┆ 47.504878      ┆ 5076.01626  │
└───────────┴───────────┴─────┴────────────────┴─────────────┘
```

```python
# Multiple metrics require explicit aliases (Paradigm 2) so column names are never created on the fly
(
    penguins
    .by("species")
    .agg(
        n="count",
        avg_mass="body_mass_g:mean",
        max_mass="body_mass_g:max",
        sum_bill="bill_length_mm:sum",
    )
)
```
Output:
```text
shape: (3, 5)
┌───────────┬─────┬─────────────┬──────────┬──────────┐
│ species   ┆ n   ┆ avg_mass    ┆ max_mass ┆ sum_bill │
│ ---       ┆ --- ┆ ---         ┆ ---      ┆ ---      │
│ str       ┆ i64 ┆ f64         ┆ f64      ┆ f64      │
╞═══════════╪═════╪═════════════╪══════════╪══════════╡
│ Adelie    ┆ 152 ┆ 3700.662252 ┆ 4775.0   ┆ 5857.5   │
│ Chinstrap ┆ 68  ┆ 3733.088235 ┆ 4800.0   ┆ 3320.7   │
│ Gentoo    ┆ 124 ┆ 5076.01626  ┆ 6300.0   ┆ 5843.1   │
└───────────┴─────┴─────────────┴──────────┴──────────┘
```

```python
# Single metric median across all numeric columns + count (preserved 1-to-1)
(
    penguins
    .select("species", "bill_length_mm", "body_mass_g")
    .by("species")
    .agg(a=["median", "count"])
)
```
Output:
```text
shape: (3, 4)
┌───────────┬─────┬────────────────┬─────────────┐
│ species   ┆ n   ┆ bill_length_mm ┆ body_mass_g │
│ ---       ┆ --- ┆ ---            ┆ ---         │
│ str       ┆ i64 ┆ f64            ┆ f64         │
╞═══════════╪═════╪════════════════╪═════════════╡
│ Adelie    ┆ 152 ┆ 38.8           ┆ 3700.0      │
│ Chinstrap ┆ 68  ┆ 49.55          ┆ 3700.0      │
│ Gentoo    ┆ 124 ┆ 47.3           ┆ 5000.0      │
└───────────┴─────┴────────────────┴─────────────┘
```

## Handling Missing Group Keys (`dropna`)

```python
# Default dropna=False keeps missing grouping keys in their own group (no silent data loss)
(penguins
 .select('species', 'sex', 'bill_length_mm', 'body_mass_g')
 .by('species', 'sex')
 .agg(a=['mean', 'count'])
)
```
Output:
```text
shape: (8, 5)
┌───────────┬────────┬─────┬────────────────┬─────────────┐
│ species   ┆ sex    ┆ n   ┆ bill_length_mm ┆ body_mass_g │
│ ---       ┆ ---    ┆ --- ┆ ---            ┆ ---         │
│ str       ┆ str    ┆ i64 ┆ f64            ┆ f64         │
╞═══════════╪════════╪═════╪════════════════╪═════════════╡
│ Adelie    ┆ Female ┆ 73  ┆ 37.257534      ┆ 3368.835616 │
│ Adelie    ┆ Male   ┆ 73  ┆ 40.390411      ┆ 4043.493151 │
│ Adelie    ┆ null   ┆ 6   ┆ 37.84          ┆ 3540.0      │
│ Chinstrap ┆ Female ┆ 34  ┆ 46.573529      ┆ 3527.205882 │
│ Chinstrap ┆ Male   ┆ 34  ┆ 51.094118      ┆ 3938.970588 │
│ Gentoo    ┆ Female ┆ 58  ┆ 45.563793      ┆ 4679.741379 │
│ Gentoo    ┆ Male   ┆ 61  ┆ 49.47377       ┆ 5484.836066 │
│ Gentoo    ┆ null   ┆ 5   ┆ 45.625         ┆ 4587.5      │
└───────────┴────────┴─────┴────────────────┴─────────────┘
```

```python
# Pass dropna=True to exclude groups with NaN keys
(penguins
 .select('species', 'sex', 'bill_length_mm', 'body_mass_g')
 .by('species', 'sex')
 .agg(a=['mean', 'count'], dropna=True)
)
```
Output:
```text
shape: (6, 5)
┌───────────┬────────┬─────┬────────────────┬─────────────┐
│ species   ┆ sex    ┆ n   ┆ bill_length_mm ┆ body_mass_g │
│ ---       ┆ ---    ┆ --- ┆ ---            ┆ ---         │
│ str       ┆ str    ┆ i64 ┆ f64            ┆ f64         │
╞═══════════╪════════╪═════╪════════════════╪═════════════╡
│ Adelie    ┆ Female ┆ 73  ┆ 37.257534      ┆ 3368.835616 │
│ Adelie    ┆ Male   ┆ 73  ┆ 40.390411      ┆ 4043.493151 │
│ Chinstrap ┆ Female ┆ 34  ┆ 46.573529      ┆ 3527.205882 │
│ Chinstrap ┆ Male   ┆ 34  ┆ 51.094118      ┆ 3938.970588 │
│ Gentoo    ┆ Female ┆ 58  ┆ 45.563793      ┆ 4679.741379 │
│ Gentoo    ┆ Male   ┆ 61  ┆ 49.47377       ┆ 5484.836066 │
└───────────┴────────┴─────┴────────────────┴─────────────┘
```

## `n`-only Aggregation — Count With No Numeric Columns Needed

```python
# Count only — useful for frequency tables on categorical columns
(penguins
 .select(exclude_dtype='number')
 .by('species', 'island')
 .agg(a='count')
)
```
Output:
```text
shape: (5, 3)
┌───────────┬───────────┬─────┐
│ species   ┆ island    ┆ n   │
│ ---       ┆ ---       ┆ --- │
│ str       ┆ str       ┆ i64 │
╞═══════════╪═══════════╪═════╡
│ Adelie    ┆ Biscoe    ┆ 44  │
│ Adelie    ┆ Dream     ┆ 56  │
│ Adelie    ┆ Torgersen ┆ 52  │
│ Chinstrap ┆ Dream     ┆ 68  │
│ Gentoo    ┆ Biscoe    ┆ 124 │
└───────────┴───────────┴─────┘
```

## Pipeline Chaining: Filter -> Select -> Aggregation -> Arrange

Because `pytae` operations return native `DataFrame` objects, you can chain verbs seamlessly end-to-end:

```python
(
    penguins
    .filter('body_mass_g > 3000')
    .select('species', 'sex', 'body_mass_g')
    .by('species', 'sex')
    .agg(
        cnt='count',
        avg_mass='body_mass_g:mean',
        max_mass='body_mass_g:max',
    )
    .arrange('avg_mass desc')
)
```
Output:
```text
shape: (8, 5)
┌───────────┬────────┬─────┬─────────────┬──────────┐
│ species   ┆ sex    ┆ cnt ┆ avg_mass    ┆ max_mass │
│ ---       ┆ ---    ┆ --- ┆ ---         ┆ ---      │
│ str       ┆ str    ┆ i64 ┆ f64         ┆ f64      │
╞═══════════╪════════╪═════╪═════════════╪══════════╡
│ Gentoo    ┆ Male   ┆ 61  ┆ 5484.836066 ┆ 6300.0   │
│ Gentoo    ┆ Female ┆ 58  ┆ 4679.741379 ┆ 5200.0   │
│ Gentoo    ┆ null   ┆ 4   ┆ 4587.5      ┆ 4875.0   │
│ Adelie    ┆ Male   ┆ 73  ┆ 4043.493151 ┆ 4775.0   │
│ Chinstrap ┆ Male   ┆ 34  ┆ 3938.970588 ┆ 4800.0   │
│ Adelie    ┆ null   ┆ 4   ┆ 3681.25     ┆ 4250.0   │
│ Chinstrap ┆ Female ┆ 32  ┆ 3572.65625  ┆ 4150.0   │
│ Adelie    ┆ Female ┆ 65  ┆ 3424.615385 ┆ 3900.0   │
└───────────┴────────┴─────┴─────────────┴──────────┘
```

## Columns with Spaces & String Specifications

When column names have spaces, passing them as keyword arguments (`[total bill]='mean'`) is forbidden by Python syntax.

`agg` solves this by accepting **string mapping specifications** (matching the CLI `-agg` flag), where column names with spaces are enclosed in square brackets `[col]`. No dictionary unpacking `**{...}` is required:

```python
# Create DataFrame with spaced column names
tips_spaced = tips.rename(columns={'total_bill': 'total bill'})

# Single string mapping with bracketed spaced columns
(
    tips_spaced
    .by('smoker')
    .agg("tip = mean, [total bill] = mean, n = count")
)
```
Output:
```text
shape: (2, 4)
┌────────┬──────────┬────────────┬─────┐
│ smoker ┆ tip      ┆ total bill ┆ n   │
│ ---    ┆ ---      ┆ ---        ┆ --- │
│ cat    ┆ f64      ┆ f64        ┆ i64 │
╞════════╪══════════╪════════════╪═════╡
│ No     ┆ 2.991854 ┆ 19.188278  ┆ 151 │
│ Yes    ┆ 3.00871  ┆ 20.756344  ┆ 93  │
└────────┴──────────┴────────────┴─────┘
```

```python
# Multiple positional string specifications
(
    tips_spaced
    .by('smoker')
    .agg("tip = mean", "[total bill] = mean", "n = count")
)
```
Output:
```text
shape: (2, 4)
┌────────┬──────────┬────────────┬─────┐
│ smoker ┆ tip      ┆ total bill ┆ n   │
│ ---    ┆ ---      ┆ ---        ┆ --- │
│ cat    ┆ f64      ┆ f64        ┆ i64 │
╞════════╪══════════╪════════════╪═════╡
│ No     ┆ 2.991854 ┆ 19.188278  ┆ 151 │
│ Yes    ┆ 3.00871  ┆ 20.756344  ┆ 93  │
└────────┴──────────┴────────────┴─────┘
```

```python
# Custom output names and bracketed source column
(
    tips_spaced
    .by('smoker')
    .agg("[avg bill] = [total bill]:mean, [total tip] = tip:sum, [table count] = count")
)
```
Output:
```text
shape: (2, 4)
┌────────┬───────────┬───────────┬─────────────┐
│ smoker ┆ avg bill  ┆ total tip ┆ table count │
│ ---    ┆ ---       ┆ ---       ┆ ---         │
│ cat    ┆ f64       ┆ f64       ┆ i64         │
╞════════╪═══════════╪═══════════╪═════════════╡
│ No     ┆ 19.188278 ┆ 451.77    ┆ 151         │
│ Yes    ┆ 20.756344 ┆ 279.81    ┆ 93          │
└────────┴───────────┴───────────┴─────────────┘
```

```python
# Complete pipeline: filter -> select -> agg with bracketed spaced columns across every verb
(
    tips
    .rename(columns={'total_bill': 'total bill'})
    .filter("[total bill] > 10 and day in [\x27Sat\x27, \x27Sun\x27] and time == \x27Dinner\x27 and size >= 2")
    .select('smoker', 'tip', '[total bill]')
    .by('smoker')
    .agg("tip = mean, [total bill] = mean, n = count")
)
```
Output:
```text
shape: (2, 4)
┌────────┬──────────┬────────────┬─────┐
│ smoker ┆ tip      ┆ total bill ┆ n   │
│ ---    ┆ ---      ┆ ---        ┆ --- │
│ cat    ┆ f64      ┆ f64        ┆ i64 │
╞════════╪══════════╪════════════╪═════╡
│ No     ┆ 3.225464 ┆ 20.705876  ┆ 97  │
│ Yes    ┆ 3.087719 ┆ 23.232281  ┆ 57  │
└────────┴──────────┴────────────┴─────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/arrange.ipynb
################################################################################
# Notebook: arrange.ipynb

# `arrange` — Row Sorting & Ordering

`arrange` orders DataFrame rows by one or more columns with full support for descending orders (`desc`), global `ascending=` overrides, and bracket notation for columns with spaces (`[col name]`).

In line with *"there should be one-- and preferably only one --obvious way to do it"*, descending sort is explicitly declared using `desc` (e.g. `"col desc"`).

| Method | Key Params | Purpose |
|---|---|---|
| `.arrange(*cols, ascending=None, na_last=True)` | `*cols`, `ascending`, `na_last` | Sort rows ascending / descending |

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
```

## 1. `arrange()` — Basic Sorting

By default, `.arrange()` sorts in ascending order.

```python
# Sort ascending by body mass
(
    penguins
    .arrange("body_mass_g")
    .select("species", "island", "body_mass_g")
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌───────────┬────────┬─────────────┐
│ species   ┆ island ┆ body_mass_g │
│ ---       ┆ ---    ┆ ---         │
│ str       ┆ str    ┆ f64         │
╞═══════════╪════════╪═════════════╡
│ Chinstrap ┆ Dream  ┆ 2700.0      │
│ Adelie    ┆ Biscoe ┆ 2850.0      │
│ Adelie    ┆ Biscoe ┆ 2850.0      │
│ Adelie    ┆ Biscoe ┆ 2900.0      │
│ Adelie    ┆ Dream  ┆ 2900.0      │
└───────────┴────────┴─────────────┘
```

## 2. Descending Order: `desc`

In line with *"one and only one obvious way"*, specify descending order explicitly by appending `desc` (or `descending`) to the column name.

```python
# Using explicit 'desc'
(
    penguins
    .arrange("body_mass_g desc")
    .select("species", "island", "body_mass_g")
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────┬─────────────┐
│ species ┆ island ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---         │
│ str     ┆ str    ┆ f64         │
╞═════════╪════════╪═════════════╡
│ Gentoo  ┆ Biscoe ┆ 6300.0      │
│ Gentoo  ┆ Biscoe ┆ 6050.0      │
│ Gentoo  ┆ Biscoe ┆ 6000.0      │
│ Gentoo  ┆ Biscoe ┆ 6000.0      │
│ Gentoo  ┆ Biscoe ┆ 5950.0      │
└─────────┴────────┴─────────────┘
```

## 3. Multi-Column Sorting

Pass multiple column specifications either as separate arguments or as a comma-separated string.

```python
# Multi-column: species ascending, body_mass_g descending
(
    penguins
    .arrange("species", "body_mass_g desc")
    .select("species", "island", "body_mass_g")
    .head(6)
)
```
Output:
```text
shape: (6, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Biscoe    ┆ 4775.0      │
│ Adelie  ┆ Biscoe    ┆ 4725.0      │
│ Adelie  ┆ Torgersen ┆ 4700.0      │
│ Adelie  ┆ Torgersen ┆ 4675.0      │
│ Adelie  ┆ Dream     ┆ 4650.0      │
│ Adelie  ┆ Dream     ┆ 4600.0      │
└─────────┴───────────┴─────────────┘
```

```python
# Comma-separated string
(
    penguins
    .arrange("species, body_mass_g desc")
    .select("species", "island", "body_mass_g")
    .head(6)
)
```
Output:
```text
shape: (6, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Biscoe    ┆ 4775.0      │
│ Adelie  ┆ Biscoe    ┆ 4725.0      │
│ Adelie  ┆ Torgersen ┆ 4700.0      │
│ Adelie  ┆ Torgersen ┆ 4675.0      │
│ Adelie  ┆ Dream     ┆ 4650.0      │
│ Adelie  ┆ Dream     ┆ 4600.0      │
└─────────┴───────────┴─────────────┘
```

## 4. Column Names with Spaces (`[col name]`)

Columns with spaces are cleanly referenced using square brackets `[col name]`.

```python
# Rename column to include spaces
spaced_penguins = penguins.rename(columns={"bill_length_mm": "bill length mm"})

# Sort by bracketed column name descending
(
    spaced_penguins
    .arrange("[bill length mm] desc")
    .select("species", "[bill length mm]")
    .head(5)
)
```
Output:
```text
shape: (5, 2)
┌───────────┬────────────────┐
│ species   ┆ bill length mm │
│ ---       ┆ ---            │
│ str       ┆ f64            │
╞═══════════╪════════════════╡
│ Gentoo    ┆ 59.6           │
│ Chinstrap ┆ 58.0           │
│ Gentoo    ┆ 55.9           │
│ Chinstrap ┆ 55.8           │
│ Gentoo    ┆ 55.1           │
└───────────┴────────────────┘
```

## 5. Functional Style (`pt.arrange`)

Available as standalone functional verb `pt.arrange(df, ...)`:

```python
# Functional arrange
top_tips = pt.arrange(tips, "tip desc")
top_tips[["total_bill", "tip", "day"]].head(4)
```
Output:
```text
shape: (4, 3)
┌────────────┬──────┬─────┐
│ total_bill ┆ tip  ┆ day │
│ ---        ┆ ---  ┆ --- │
│ f64        ┆ f64  ┆ cat │
╞════════════╪══════╪═════╡
│ 50.81      ┆ 10.0 ┆ Sat │
│ 48.33      ┆ 9.0  ┆ Sat │
│ 39.42      ┆ 7.58 ┆ Sat │
│ 48.27      ┆ 6.73 ┆ Sat │
└────────────┴──────┴─────┘
```

## 6. Design Principle: Rejecting `-` Shorthand

Prefixing columns with `-` (e.g. `arrange("-col")`) is intentionally not supported because it violates *"one and only one obvious way"* and creates ambiguity with hyphenated column names or negation expressions. Pytae strictly enforces explicit `desc`:

```python
# Leading '-' raises a clear ValueError pointing to 'col desc'
try:
    penguins.arrange("-body_mass_g")
except ValueError as err:
    print(f"Error caught as expected: {err}")
```
Output:
```text
Error caught as expected: arrange(): leading '-' is not supported. In line with 'one and only one obvious way', use 'body_mass_g desc' instead (e.g. arrange('body_mass_g desc')).
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/distinct.ipynb
################################################################################
# Notebook: distinct.ipynb

# Distinct Rows — Removing Duplicate Rows

Remove duplicate records across the intermediate DataFrame with full control over column subsets.

`pytae` provides both direct method chaining `df.distinct(*cols, keep='first')` and the functional verb `pt.distinct(df, *cols)`. In the CLI, the equivalent flag is `-distinct` (or `-distinct COLS`).

| Operation | Pytae Method Chain | CLI Equivalent |
|---|---|---|
| All Columns | `df.distinct()` | `-distinct` |
| Specific Columns | `df.distinct('col1', 'col2')` | `-distinct "col1,col2"` |
| Keep Last / None | `df.distinct(keep='last')` | N/A |

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt
import pandas as pd

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
```

## 1. Deduplicating Across All Columns (`.distinct()`)

Eliminate identical rows across all selected columns. The index is automatically reset:

```python
# Keep only unique species and island pairs
(
    penguins
    .select("species", "island")
    .distinct()
)
```
Output:
```text
shape: (5, 2)
┌───────────┬───────────┐
│ species   ┆ island    │
│ ---       ┆ ---       │
│ str       ┆ str       │
╞═══════════╪═══════════╡
│ Adelie    ┆ Torgersen │
│ Adelie    ┆ Biscoe    │
│ Adelie    ┆ Dream     │
│ Chinstrap ┆ Dream     │
│ Gentoo    ┆ Biscoe    │
└───────────┴───────────┘
```

## 2. Deduplicating by Specific Identifier Columns

Pass column names to restrict duplicate checks to specific identifiers, keeping the first matching record for all other columns:

```python
# Keep the first recorded penguin for each unique species and island combination
(
    penguins
    .select("species", "island", "body_mass_g", "sex")
    .distinct("species", "island")
)
```
Output:
```text
shape: (5, 4)
┌───────────┬───────────┬─────────────┬────────┐
│ species   ┆ island    ┆ body_mass_g ┆ sex    │
│ ---       ┆ ---       ┆ ---         ┆ ---    │
│ str       ┆ str       ┆ f64         ┆ str    │
╞═══════════╪═══════════╪═════════════╪════════╡
│ Adelie    ┆ Torgersen ┆ 3750.0      ┆ Male   │
│ Adelie    ┆ Biscoe    ┆ 3400.0      ┆ Female │
│ Adelie    ┆ Dream     ┆ 3250.0      ┆ Female │
│ Chinstrap ┆ Dream     ┆ 3500.0      ┆ Female │
│ Gentoo    ┆ Biscoe    ┆ 4500.0      ┆ Female │
└───────────┴───────────┴─────────────┴────────┘
```

## 3. Chaining in Pipelines

`df.distinct()` flows seamlessly inside multi-step pipelines in fluent method chains:

```python
# Filter heavy penguins -> select columns -> deduplicate -> arrange
(
    penguins
    .filter("body_mass_g > 4000")
    .select("species", "island")
    .distinct()
    .arrange("species", "island")
)
```
Output:
```text
shape: (5, 2)
┌───────────┬───────────┐
│ species   ┆ island    │
│ ---       ┆ ---       │
│ str       ┆ str       │
╞═══════════╪═══════════╡
│ Adelie    ┆ Biscoe    │
│ Adelie    ┆ Dream     │
│ Adelie    ┆ Torgersen │
│ Chinstrap ┆ Dream     │
│ Gentoo    ┆ Biscoe    │
└───────────┴───────────┘
```

## 4. Keeping the Last Record (`keep='last'`)

Optionally retain the last occurrence instead of the first:

```python
# Retain the last record for each day and time
(
    tips
    .select("day", "time", "total_bill", "tip")
    .distinct("day", "time", keep="last")
)
```
Output:
```text
shape: (6, 4)
┌──────┬────────┬────────────┬──────┐
│ day  ┆ time   ┆ total_bill ┆ tip  │
│ ---  ┆ ---    ┆ ---        ┆ ---  │
│ cat  ┆ cat    ┆ f64        ┆ f64  │
╞══════╪════════╪════════════╪══════╡
│ Fri  ┆ Dinner ┆ 15.38      ┆ 3.0  │
│ Sun  ┆ Dinner ┆ 15.69      ┆ 1.5  │
│ Thur ┆ Lunch  ┆ 16.47      ┆ 3.23 │
│ Fri  ┆ Lunch  ┆ 10.09      ┆ 2.0  │
│ Sat  ┆ Dinner ┆ 17.82      ┆ 1.75 │
│ Thur ┆ Dinner ┆ 18.78      ┆ 3.0  │
└──────┴────────┴────────────┴──────┘
```

## 5. Functional Style (`pt.distinct`)

Available as a standalone function:

```python
# Functional deduplication
pt.distinct(penguins[["species", "island"]])
```
Output:
```text
shape: (5, 2)
┌───────────┬───────────┐
│ species   ┆ island    │
│ ---       ┆ ---       │
│ str       ┆ str       │
╞═══════════╪═══════════╡
│ Adelie    ┆ Torgersen │
│ Adelie    ┆ Biscoe    │
│ Adelie    ┆ Dream     │
│ Chinstrap ┆ Dream     │
│ Gentoo    ┆ Biscoe    │
└───────────┴───────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/filter.ipynb
################################################################################
# Notebook: filter.ipynb

# `filter` — Comprehensive Reference

`filter` filters a DataFrame using intuitive CLI-style string expressions or programmatic dictionaries.

Under the hood, `filter` compiles conditions into high-performance Polars expressions evaluated directly in native C++/Rust memory.

### Calling Styles

`filter` supports two clean, unambiguous calling styles:

- **String expressions** (matches CLI `-filter` syntax; handles spaces directly):
  `df.filter("[bill length mm] > 40 and species == 'Adelie'")`
- **Dictionaries** (ideal for dynamic programmatic keys and Option 1 / Option 2 ranges):
  `df.filter({"bill length mm": "> 40", "species": "Adelie"})`
  `df.filter({"body_mass_g": ("between", 3500, 4000)})`
  `df.filter({"body_mass_g": ((">=", 3500), ("<=", 4000))})`
- **Top-level library verb**:
  `pt.filter(df, "species == 'Adelie' and body_mass_g > 5000")`

> [!IMPORTANT]
> **Why `pytae` Strictly Enforces `==` and Disallows Kwargs**:
> In Python syntax, keyword arguments like `df.filter(species="Adelie")` force the use of a single `=`. In `pytae`, single `=` is reserved exclusively for column assignments in `-mutate`. To prevent subtle bugs and ensure **"one and only one obvious way"**, `filter()` strictly requires `==` and raises an immediate `TypeError` if keyword arguments are passed.

---

### Comprehensive Reference Table

| Category | Example Syntax | Meaning / Target |
|---|---|---|
| **Equality** | `"species == 'Adelie'"` or `{"species": "Adelie"}` | Exact equality match (`==` strictly enforced; single `=` raises error) |
| **Inequality** | `"species != 'Adelie'"` or `{"species": ("!=", "Adelie")}` | Inequality match |
| **Relational Operators** | `"body_mass_g > 5000"` or `{"body_mass_g": (">", 5000)}` | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| **Set Membership** | `"species in ['Adelie', 'Gentoo']"` or `{"species": ['Adelie', 'Gentoo']}` | In candidate set / list |
| **Exclusion** | `"sex not in ['Male']"` or `{"sex": ("not in", ['Male'])}` | Not in candidate set |
| **Boolean AND** | `"species == 'Gentoo' and body_mass_g > 4500"` | Logical conjunction (comma `,` and bitwise `&` disallowed) |
| **Boolean OR** | `"island == 'Dream' or island == 'Torgersen'"` | Logical disjunction (bitwise `\|` disallowed) |
| **Grouping / Precedence** | `"(species == 'Adelie' or species == 'Chinstrap') and mass > 4000"` | Arbitrary nested boolean logic with parentheses |
| **Range Option 1 (`between`)** | `{"body_mass_g": ("between", 3500, 4000)}` | Inclusive range (`min <= x <= max`) via Polars `.is_between()` |
| **Range Option 2 (operator tuples)** | `{"body_mass_g": ((">=", 3500), ("<=", 4000))}` | Multiple conditions on same column via clean `(op, val)` pairs |
| **String Range Expression** | `"body_mass_g >= 3500 and body_mass_g <= 4000"` | Explicit boolean bounds in string expression |
| **Columns with Spaces** | `"[bill length mm] > 40"` or `{"bill length mm": (">", 40)}` | Spaced column syntax (brackets in strings, plain keys in dicts) |
| **String Prefixes/Suffixes** | `{"species": ("startswith", "Ad")}` or `{"species": ("endswith", "strap")}` | String prefix / suffix search |
| **Multiple Prefixes/Suffixes** | `{"species": ("startswith", ["Ad", "Ge"])}` | Matches any prefix / suffix in sequence |
| **String Substring / Regex** | `{"species": ("contains", "adel")}` or `{"species": ("regex", r"oo")}` | Substring match or regex search |
| **Null & NaN Checks** | `"sex.is_not_null()"`, `{"sex": "is_null()"}`, `"score.is_nan()"`, `{"score": "is_nan()"}` | Missing data (`null`) and IEEE 754 float NaNs (`NaN`) via universal method tokens (expressions & dicts) |
| **Column-to-Column** | `"exposure > limit"` or `"tranche_id == deal_id"` | Compare two columns using bare column names |
| **Variable Injection** | `"exposure > @threshold and tranche == col(@target_col)"` | External scalar (`@var`) and column (`col(@var)`) references |

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
print("Loaded sample datasets:", list(pt.sample_data.keys()))
```
Output:
```text
Loaded sample datasets: ['anagrams', 'anscombe', 'attention', 'brain_networks', 'car_crashes', 'diamonds', 'dots', 'dowjones', 'exercise', 'flights', 'fmri', 'geyser', 'glue', 'healthexp', 'iris', 'mpg', 'penguins', 'planets', 'seaice', 'taxis', 'tips', 'titanic']
```

## 1. Primary Calling Styles: String Expressions and Dictionaries

`filter()` accepts conditions as string expressions matching the CLI `-filter` syntax, or plain dictionaries for programmatic filters. Both direct method chaining (`df.filter(...)`) and the top-level library verb (`pt.filter(df, ...)`) are supported.

```python
# 1. String expressions — clean, readable, matches pytae CLI -filter syntax
# Uses '==' for equality and 'and' for logical conjunction
(
    penguins
    .filter("species == 'Adelie' and island == 'Dream'")
    .head(5)
)
```
Output:
```text
shape: (5, 7)
┌─────────┬────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---    ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str    ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Dream  ┆ 39.5           ┆ 16.7          ┆ 178.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Dream  ┆ 37.2           ┆ 18.1          ┆ 178.0             ┆ 3900.0      ┆ Male   │
│ Adelie  ┆ Dream  ┆ 39.5           ┆ 17.8          ┆ 188.0             ┆ 3300.0      ┆ Female │
│ Adelie  ┆ Dream  ┆ 40.9           ┆ 18.9          ┆ 184.0             ┆ 3900.0      ┆ Male   │
│ Adelie  ┆ Dream  ┆ 36.4           ┆ 17.0          ┆ 195.0             ┆ 3325.0      ┆ Female │
└─────────┴────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# 2. Plain dictionaries — ideal for programmatic pipelines or dynamic key mapping
(
    penguins
    .filter({"species": "Adelie", "island": "Dream"})
    .head(5)
)
```
Output:
```text
shape: (5, 7)
┌─────────┬────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---    ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str    ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Dream  ┆ 39.5           ┆ 16.7          ┆ 178.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Dream  ┆ 37.2           ┆ 18.1          ┆ 178.0             ┆ 3900.0      ┆ Male   │
│ Adelie  ┆ Dream  ┆ 39.5           ┆ 17.8          ┆ 188.0             ┆ 3300.0      ┆ Female │
│ Adelie  ┆ Dream  ┆ 40.9           ┆ 18.9          ┆ 184.0             ┆ 3900.0      ┆ Male   │
│ Adelie  ┆ Dream  ┆ 36.4           ┆ 17.0          ┆ 195.0             ┆ 3325.0      ┆ Female │
└─────────┴────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# 3. Composing multiple conditions — either chained or passed as multiple positional arguments
(
    penguins
    .filter("body_mass_g > 4000", "island == 'Biscoe'")
    .head(5)
)
```
Output:
```text
shape: (5, 7)
┌─────────┬────────┬────────────────┬───────────────┬───────────────────┬─────────────┬──────┐
│ species ┆ island ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex  │
│ ---     ┆ ---    ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---  │
│ str     ┆ str    ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str  │
╞═════════╪════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪══════╡
│ Adelie  ┆ Biscoe ┆ 40.1           ┆ 18.9          ┆ 188.0             ┆ 4300.0      ┆ Male │
│ Adelie  ┆ Biscoe ┆ 42.0           ┆ 19.5          ┆ 200.0             ┆ 4050.0      ┆ Male │
│ Adelie  ┆ Biscoe ┆ 41.3           ┆ 21.1          ┆ 195.0             ┆ 4400.0      ┆ Male │
│ Adelie  ┆ Biscoe ┆ 41.1           ┆ 18.2          ┆ 192.0             ┆ 4050.0      ┆ Male │
│ Adelie  ┆ Biscoe ┆ 41.1           ┆ 19.1          ┆ 188.0             ┆ 4100.0      ┆ Male │
└─────────┴────────┴────────────────┴───────────────┴───────────────────┴─────────────┴──────┘
```

```python
# 4. Top-level function pt.filter(df, ...) — works identically to DataFrame method
pt.filter(penguins, "species == 'Gentoo' and body_mass_g > 5000").head(5)
```
Output:
```text
shape: (5, 7)
┌─────────┬────────┬────────────────┬───────────────┬───────────────────┬─────────────┬──────┐
│ species ┆ island ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex  │
│ ---     ┆ ---    ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---  │
│ str     ┆ str    ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str  │
╞═════════╪════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪══════╡
│ Gentoo  ┆ Biscoe ┆ 50.0           ┆ 16.3          ┆ 230.0             ┆ 5700.0      ┆ Male │
│ Gentoo  ┆ Biscoe ┆ 50.0           ┆ 15.2          ┆ 218.0             ┆ 5700.0      ┆ Male │
│ Gentoo  ┆ Biscoe ┆ 47.6           ┆ 14.5          ┆ 215.0             ┆ 5400.0      ┆ Male │
│ Gentoo  ┆ Biscoe ┆ 46.7           ┆ 15.3          ┆ 219.0             ┆ 5200.0      ┆ Male │
│ Gentoo  ┆ Biscoe ┆ 46.8           ┆ 15.4          ┆ 215.0             ┆ 5150.0      ┆ Male │
└─────────┴────────┴────────────────┴───────────────┴───────────────────┴─────────────┴──────┘
```

## 2. Relational Comparisons (`==`, `!=`, `<`, `>`, `<=`, `>=`)

Comparison filters can be written directly in string expressions or as operator tuples inside dictionaries:
- String expressions: `"body_mass_g > 5000"`, `"species == 'Gentoo'"`
- Dictionary with operator tuples: `{"body_mass_g": (">", 5000)}`, `{"island": ("!=", "Dream")}`

> [!IMPORTANT]
> **Strict Equality Enforcement**: In `pytae`, equality comparisons in filter strings strictly require `==`. Single `=` is reserved exclusively for column assignments in `-mutate`. Using single `=` in filter expressions raises an immediate diagnostic error.

```python
# Numeric comparisons via string expressions
(
    penguins
    .filter("body_mass_g > 5000 and flipper_length_mm >= 220")
    .select('species', 'island', 'body_mass_g', 'flipper_length_mm')
    .head(5)
)
```
Output:
```text
shape: (5, 4)
┌─────────┬────────┬─────────────┬───────────────────┐
│ species ┆ island ┆ body_mass_g ┆ flipper_length_mm │
│ ---     ┆ ---    ┆ ---         ┆ ---               │
│ str     ┆ str    ┆ f64         ┆ f64               │
╞═════════╪════════╪═════════════╪═══════════════════╡
│ Gentoo  ┆ Biscoe ┆ 5700.0      ┆ 230.0             │
│ Gentoo  ┆ Biscoe ┆ 6300.0      ┆ 221.0             │
│ Gentoo  ┆ Biscoe ┆ 5350.0      ┆ 222.0             │
│ Gentoo  ┆ Biscoe ┆ 5550.0      ┆ 220.0             │
│ Gentoo  ┆ Biscoe ┆ 5250.0      ┆ 222.0             │
└─────────┴────────┴─────────────┴───────────────────┘
```

```python
# Dictionary with operator tuples: (op, value)
(
    penguins
    .filter({"body_mass_g": (">", 5500), "island": ("!=", "Dream")})
    .select('species', 'island', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────┬─────────────┐
│ species ┆ island ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---         │
│ str     ┆ str    ┆ f64         │
╞═════════╪════════╪═════════════╡
│ Gentoo  ┆ Biscoe ┆ 5700.0      │
│ Gentoo  ┆ Biscoe ┆ 5700.0      │
│ Gentoo  ┆ Biscoe ┆ 5550.0      │
│ Gentoo  ┆ Biscoe ┆ 5850.0      │
│ Gentoo  ┆ Biscoe ┆ 5850.0      │
└─────────┴────────┴─────────────┘
```

```python
# Multiple comparisons in string expressions
(
    penguins
    .filter("body_mass_g <= 3000 and bill_length_mm < 37")
    .select('species', 'island', 'bill_length_mm', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (4, 4)
┌─────────┬────────┬────────────────┬─────────────┐
│ species ┆ island ┆ bill_length_mm ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---            ┆ ---         │
│ str     ┆ str    ┆ f64            ┆ f64         │
╞═════════╪════════╪════════════════╪═════════════╡
│ Adelie  ┆ Biscoe ┆ 34.5           ┆ 2900.0      │
│ Adelie  ┆ Biscoe ┆ 36.5           ┆ 2850.0      │
│ Adelie  ┆ Biscoe ┆ 36.4           ┆ 2850.0      │
│ Adelie  ┆ Dream  ┆ 33.1           ┆ 2900.0      │
└─────────┴────────┴────────────────┴─────────────┘
```

## 3. Set Membership (`in` and `not in`)

To match against a list of candidate values:
- Use SQL/Python-style `in` or `not in` in string expressions: `"species in ['Adelie', 'Chinstrap']"`
- Pass a candidate list or exclusion tuple in a dictionary: `{"species": ['Adelie', 'Chinstrap']}`, `{"sex": ("not in", ['Male'])}`

```python
# Set membership via string expression
(
    penguins
    .filter("species in ['Adelie', 'Chinstrap'] and island in ['Dream', 'Biscoe']")
    .by('species', 'island')
    .agg("n = count, mean_mass = body_mass_g:mean")
)
```
Output:
```text
shape: (3, 4)
┌───────────┬────────┬─────┬─────────────┐
│ species   ┆ island ┆ n   ┆ mean_mass   │
│ ---       ┆ ---    ┆ --- ┆ ---         │
│ str       ┆ str    ┆ i64 ┆ f64         │
╞═══════════╪════════╪═════╪═════════════╡
│ Adelie    ┆ Biscoe ┆ 44  ┆ 3709.659091 │
│ Adelie    ┆ Dream  ┆ 56  ┆ 3688.392857 │
│ Chinstrap ┆ Dream  ┆ 68  ┆ 3733.088235 │
└───────────┴────────┴─────┴─────────────┘
```

```python
# 'in' and 'not in' inside string expressions
(
    penguins
    .filter("species in ['Adelie', 'Gentoo'] and island not in ['Torgersen']")
    .by('species', 'island')
    .agg("n = count")
)
```
Output:
```text
shape: (3, 3)
┌─────────┬────────┬─────┐
│ species ┆ island ┆ n   │
│ ---     ┆ ---    ┆ --- │
│ str     ┆ str    ┆ i64 │
╞═════════╪════════╪═════╡
│ Adelie  ┆ Biscoe ┆ 44  │
│ Adelie  ┆ Dream  ┆ 56  │
│ Gentoo  ┆ Biscoe ┆ 124 │
└─────────┴────────┴─────┘
```

```python
# Membership and exclusion using dictionary syntax
(
    penguins
    .filter({
        "species": ("not in", ['Gentoo']),
        "island": ['Dream', 'Torgersen'],
    })
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬────────┬─────────────┐
│ species ┆ island    ┆ sex    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---    ┆ ---         │
│ str     ┆ str       ┆ str    ┆ f64         │
╞═════════╪═══════════╪════════╪═════════════╡
│ Adelie  ┆ Torgersen ┆ Male   ┆ 3750.0      │
│ Adelie  ┆ Torgersen ┆ Female ┆ 3800.0      │
│ Adelie  ┆ Torgersen ┆ Female ┆ 3250.0      │
│ Adelie  ┆ Torgersen ┆ null   ┆ null        │
│ Adelie  ┆ Torgersen ┆ Female ┆ 3450.0      │
└─────────┴───────────┴────────┴─────────────┘
```

## 4. Boolean Logic: `and`, `or`, and Parentheses `(...)`

`pytae` supports rich boolean expressions in filter strings with:
- `and` for logical conjunction
- `or` for logical disjunction
- Arbitrary nesting with parentheses `(...)` for explicit precedence control

> [!NOTE]
> Following the Zen of Python (*"There should be one-- and preferably only one --obvious way to do it"*), `pytae` strictly uses `and` and `or`. Bitwise `&` and `|` are disallowed, and commas `,` are strictly punctuation for function arguments and lists, not boolean operators.

```python
# Logical conjunction with 'and'
(
    penguins
    .filter("species == 'Gentoo' and body_mass_g > 5500 and sex == 'Female'")
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (0, 4)
┌─────────┬────────┬─────┬─────────────┐
│ species ┆ island ┆ sex ┆ body_mass_g │
│ ---     ┆ ---    ┆ --- ┆ ---         │
│ str     ┆ str    ┆ str ┆ f64         │
╞═════════╪════════╪═════╪═════════════╡
└─────────┴────────┴─────┴─────────────┘
```

```python
# Logical disjunction with 'or'
(
    penguins
    .filter("island == 'Dream' or island == 'Torgersen'")
    .by('island')
    .agg("n = count")
)
```
Output:
```text
shape: (2, 2)
┌───────────┬─────┐
│ island    ┆ n   │
│ ---       ┆ --- │
│ str       ┆ i64 │
╞═══════════╪═════╡
│ Dream     ┆ 124 │
│ Torgersen ┆ 52  │
└───────────┴─────┘
```

```python
# Combining 'or' and 'and' with parentheses for precedence:
# Keep Adelie or Chinstrap penguins that weigh over 4000g:
(
    penguins
    .filter("(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000")
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(6)
)
```
Output:
```text
shape: (6, 4)
┌─────────┬───────────┬──────┬─────────────┐
│ species ┆ island    ┆ sex  ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---  ┆ ---         │
│ str     ┆ str       ┆ str  ┆ f64         │
╞═════════╪═══════════╪══════╪═════════════╡
│ Adelie  ┆ Torgersen ┆ Male ┆ 4675.0      │
│ Adelie  ┆ Torgersen ┆ null ┆ 4250.0      │
│ Adelie  ┆ Torgersen ┆ Male ┆ 4400.0      │
│ Adelie  ┆ Torgersen ┆ Male ┆ 4500.0      │
│ Adelie  ┆ Torgersen ┆ Male ┆ 4200.0      │
│ Adelie  ┆ Dream     ┆ Male ┆ 4150.0      │
└─────────┴───────────┴──────┴─────────────┘
```

```python
# Complex nested logic:
# (Gentoo on Biscoe) OR (Adelie on Dream), with body mass >= 3500
(
    penguins
    .filter("((species == 'Gentoo' and island == 'Biscoe') or (species == 'Adelie' and island == 'Dream')) and body_mass_g >= 3500")
    .by('species', 'island')
    .agg("n = count, mean_mass = body_mass_g:mean")
)
```
Output:
```text
shape: (2, 4)
┌─────────┬────────┬─────┬─────────────┐
│ species ┆ island ┆ n   ┆ mean_mass   │
│ ---     ┆ ---    ┆ --- ┆ ---         │
│ str     ┆ str    ┆ i64 ┆ f64         │
╞═════════╪════════╪═════╪═════════════╡
│ Adelie  ┆ Dream  ┆ 33  ┆ 3984.090909 │
│ Gentoo  ┆ Biscoe ┆ 123 ┆ 5076.01626  │
└─────────┴────────┴─────┴─────────────┘
```

## 5. Range & Interval Filtering: Option 1 and Option 2

Previous versions of data tools frequently used mathematical interval strings like `'[3000, 4000]'` or `'(3000, 4000)'`. In modern `pytae`, string bracket notation was dropped to eliminate ambiguity with Python list literals and ensure unambiguous typing.

Instead, `pytae` provides two clean, powerful options for range filtering:

### Option 1: `("between", min, max)`
Pass `("between", min, max)` inside a dictionary to map directly to Polars' highly optimized native `.is_between(lower, upper)` method:
```python
df.filter({"body_mass_g": ("between", 3000, 4000)})
```

### Option 2: Multi-condition Operator Tuples `(('op1', val1), ('op2', val2))`
Pass a tuple of clean `(operator, value)` pairs inside a dictionary to apply multiple conditions on the same column without string-mashed syntax:
```python
# Inclusive bounds:
df.filter({"body_mass_g": ((">=", 3000), ("<=", 4000))})

# Exclusive or asymmetric bounds:
df.filter({"body_mass_g": ((">", 3000), ("<", 4500))})
df.filter({"bill_length_mm": ((">", 40), ("<", 45))})
```

### String Expressions with `and`
You can also write ranges naturally in filter strings:
```python
df.filter("body_mass_g >= 3000 and body_mass_g <= 4000")
```

```python
# Option 1: ("between", min, max) — inclusive range via dictionary
display(
    penguins
    .filter({"body_mass_g": ("between", 3500, 3800)})
    .select('species', 'island', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Torgersen ┆ 3750.0      │
│ Adelie  ┆ Torgersen ┆ 3800.0      │
│ Adelie  ┆ Torgersen ┆ 3650.0      │
│ Adelie  ┆ Torgersen ┆ 3625.0      │
│ Adelie  ┆ Torgersen ┆ 3700.0      │
└─────────┴───────────┴─────────────┘
```

```python
# Option 2: Multi-condition operator tuples (('op', val), ...)
# Clean separation of operators and values; perfect for exclusive or asymmetric bounds:
(
    penguins
    .filter({
        "bill_length_mm": ((">", 40), ("<", 45)),
        "body_mass_g": ((">=", 3500), ("<=", 4000)),
    })
    .select('species', 'bill_length_mm', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────────────┬─────────────┐
│ species ┆ bill_length_mm ┆ body_mass_g │
│ ---     ┆ ---            ┆ ---         │
│ str     ┆ f64            ┆ f64         │
╞═════════╪════════════════╪═════════════╡
│ Adelie  ┆ 40.6           ┆ 3550.0      │
│ Adelie  ┆ 40.5           ┆ 3950.0      │
│ Adelie  ┆ 40.9           ┆ 3900.0      │
│ Adelie  ┆ 42.2           ┆ 3550.0      │
│ Adelie  ┆ 40.8           ┆ 3900.0      │
└─────────┴────────────────┴─────────────┘
```

```python
# Standard string expression range using 'and'
(
    penguins
    .filter("body_mass_g >= 3500 and body_mass_g <= 4000 and bill_depth_mm > 18")
    .select('species', 'bill_depth_mm', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬───────────────┬─────────────┐
│ species ┆ bill_depth_mm ┆ body_mass_g │
│ ---     ┆ ---           ┆ ---         │
│ str     ┆ f64           ┆ f64         │
╞═════════╪═══════════════╪═════════════╡
│ Adelie  ┆ 18.7          ┆ 3750.0      │
│ Adelie  ┆ 20.6          ┆ 3650.0      │
│ Adelie  ┆ 21.2          ┆ 3800.0      │
│ Adelie  ┆ 18.7          ┆ 3600.0      │
│ Adelie  ┆ 19.2          ┆ 3800.0      │
└─────────┴───────────────┴─────────────┘
```

## 6. Columns with Spaces & Bracket Notation `[col]`

When column names contain spaces or special punctuation (such as `bill length mm` or `counterparty_class_(irb)`):
- In **string expressions**, wrap the column name in square brackets: `[bill length mm] > 40`
- In **dictionaries**, use the column name directly as the key without any brackets: `{"bill length mm": "> 40"}`

```python
# Create a DataFrame with spaces in column names
penguins_spaces = penguins.rename(columns={
    'bill_length_mm': 'bill length mm',
    'body_mass_g': 'body mass g',
})
print("Columns with spaces:", penguins_spaces.columns.tolist()[:4])
```
Output:
```text
Columns with spaces: ['species', 'island', 'bill length mm', 'bill_depth_mm']
```

```python
# Filtering spaced columns using bracket notation in string expressions:
(
    penguins_spaces
    .filter("[bill length mm] > 45 and [body mass g] > 4000")
    .select('species', '[bill length mm]', '[body mass g]')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌───────────┬────────────────┬─────────────┐
│ species   ┆ bill length mm ┆ body mass g │
│ ---       ┆ ---            ┆ ---         │
│ str       ┆ f64            ┆ f64         │
╞═══════════╪════════════════╪═════════════╡
│ Adelie    ┆ 46.0           ┆ 4200.0      │
│ Adelie    ┆ 45.8           ┆ 4150.0      │
│ Adelie    ┆ 45.6           ┆ 4600.0      │
│ Chinstrap ┆ 46.0           ┆ 4150.0      │
│ Chinstrap ┆ 52.0           ┆ 4050.0      │
└───────────┴────────────────┴─────────────┘
```

```python
# Filtering spaced columns using plain dictionaries (Option 1 & Option 2 supported!):
(
    penguins_spaces
    .filter({
        "bill length mm": (">", 45),
        "body mass g": ("between", 4000, 5000),
    })
    .select('species', '[bill length mm]', '[body mass g]')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌───────────┬────────────────┬─────────────┐
│ species   ┆ bill length mm ┆ body mass g │
│ ---       ┆ ---            ┆ ---         │
│ str       ┆ f64            ┆ f64         │
╞═══════════╪════════════════╪═════════════╡
│ Adelie    ┆ 46.0           ┆ 4200.0      │
│ Adelie    ┆ 45.8           ┆ 4150.0      │
│ Adelie    ┆ 45.6           ┆ 4600.0      │
│ Chinstrap ┆ 46.0           ┆ 4150.0      │
│ Chinstrap ┆ 52.0           ┆ 4050.0      │
└───────────┴────────────────┴─────────────┘
```

## 7. String Matching (`startswith`, `endswith`, `contains`, `regex`)

For text/string columns, `pytae` provides high-speed pattern matching inside dictionaries:
- `{"col": ('startswith', prefix)}`: Matches string prefix
- `{"col": ('startswith', [prefix1, prefix2, ...])}`: Matches any of several prefixes
- `{"col": ('endswith', suffix)}` / `{"col": ('endswith', [suffix1, suffix2, ...])}`: Matches suffixes
- `{"col": ('contains', substr)}`: Substring search
- `{"col": ('regex', pattern)}`: Regular expression pattern search

```python
# Prefix and suffix matches via dictionary
(
    penguins
    .filter({
        "species": ('startswith', 'Ad'),
        "island": ('endswith', 'e'),
    })
    .select('species', 'island', 'body_mass_g')
    .head(5)
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────┬─────────────┐
│ species ┆ island ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---         │
│ str     ┆ str    ┆ f64         │
╞═════════╪════════╪═════════════╡
│ Adelie  ┆ Biscoe ┆ 3400.0      │
│ Adelie  ┆ Biscoe ┆ 3600.0      │
│ Adelie  ┆ Biscoe ┆ 3800.0      │
│ Adelie  ┆ Biscoe ┆ 3950.0      │
│ Adelie  ┆ Biscoe ┆ 3800.0      │
└─────────┴────────┴─────────────┘
```

```python
# Multiple prefixes: matches species starting with 'Ad' OR 'Ge'
(
    penguins
    .filter({"species": ('startswith', ['Ad', 'Ge'])})
    .by('species')
    .agg("n = count")
)
```
Output:
```text
shape: (2, 2)
┌─────────┬─────┐
│ species ┆ n   │
│ ---     ┆ --- │
│ str     ┆ i64 │
╞═════════╪═════╡
│ Adelie  ┆ 152 │
│ Gentoo  ┆ 124 │
└─────────┴─────┘
```

```python
# Regex pattern matching (e.g. repeated 'o')
(
    penguins
    .filter({"species": ('regex', r'oo')})
    .by('species')
    .agg("n = count")
)
```
Output:
```text
shape: (1, 2)
┌─────────┬─────┐
│ species ┆ n   │
│ ---     ┆ --- │
│ str     ┆ i64 │
╞═════════╪═════╡
│ Gentoo  ┆ 124 │
└─────────┴─────┘
```

## 8. Missing and Null Checks (`is_null()`, `is_not_null()`, `is_nan()`, `is_not_nan()`)

In Pytae and pure Polars, missing data (`null`) and floating-point non-finite values (`NaN`) follow a unified **method-token standard** across both **string expressions** and **dictionaries**:

- **Missing values (`null`)**: Represent absent / unrecorded values across any data type (string, numeric, date). Handled via `.is_null()` and `.is_not_null()`.
- **Floating-point non-finites (`NaN`)**: Represent IEEE 754 arithmetic results on float columns (`f32`, `f64`). Handled via `.is_nan()` and `.is_not_nan()`. Polars strictly separates `null` from `NaN`.

The exact same method names—`is_null()`, `is_not_null()`, `is_nan()`, and `is_not_nan()`—are used consistently everywhere.

```python
# 1. Missing data checks via string expressions (non-dict):
print("--- Missing sex using string expression (sex.is_null()) ---")
display(
    penguins
    .filter("sex.is_null()")
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Known sex using string expression (sex.is_not_null()) ---")
display(
    penguins
    .filter("sex.is_not_null()")
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Spaced column using bracket expression ([bill length mm].is_not_null()) ---")
display(
    penguins_spaces
    .filter("[bill length mm].is_not_null()")
    .select('species', 'island', '[bill length mm]', 'sex')
    .head(5)
)
```
Output:
```text
--- Missing sex using string expression (sex.is_null()) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬─────────────┬──────┐
│ species ┆ island    ┆ body_mass_g ┆ sex  │
│ ---     ┆ ---       ┆ ---         ┆ ---  │
│ str     ┆ str       ┆ f64         ┆ str  │
╞═════════╪═══════════╪═════════════╪══════╡
│ Adelie  ┆ Torgersen ┆ null        ┆ null │
│ Adelie  ┆ Torgersen ┆ 3475.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 4250.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 3300.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 3700.0      ┆ null │
└─────────┴───────────┴─────────────┴──────┘
```
Output:
```text
--- Known sex using string expression (sex.is_not_null()) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬─────────────┬────────┐
│ species ┆ island    ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64         ┆ str    │
╞═════════╪═══════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3450.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3650.0      ┆ Male   │
└─────────┴───────────┴─────────────┴────────┘
```
Output:
```text
--- Spaced column using bracket expression ([bill length mm].is_not_null()) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬────────────────┬────────┐
│ species ┆ island    ┆ bill length mm ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ str    │
╞═════════╪═══════════╪════════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 39.3           ┆ Male   │
└─────────┴───────────┴────────────────┴────────┘
```

```python
# 2. Missing data checks via dictionaries:
print("--- Missing sex using dictionary ({'sex': 'is_null()'}) ---")
display(
    penguins
    .filter({"sex": "is_null()"})
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Known sex using dictionary ({'sex': 'is_not_null()'}) ---")
display(
    penguins
    .filter({"sex": "is_not_null()"})
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Spaced column using dictionary ({'bill length mm': 'is_not_null()'}) ---")
display(
    penguins_spaces
    .filter({"bill length mm": "is_not_null()"})
    .select('species', 'island', '[bill length mm]', 'sex')
    .head(5)
)
```
Output:
```text
--- Missing sex using dictionary ({'sex': 'is_null()'}) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬─────────────┬──────┐
│ species ┆ island    ┆ body_mass_g ┆ sex  │
│ ---     ┆ ---       ┆ ---         ┆ ---  │
│ str     ┆ str       ┆ f64         ┆ str  │
╞═════════╪═══════════╪═════════════╪══════╡
│ Adelie  ┆ Torgersen ┆ null        ┆ null │
│ Adelie  ┆ Torgersen ┆ 3475.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 4250.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 3300.0      ┆ null │
│ Adelie  ┆ Torgersen ┆ 3700.0      ┆ null │
└─────────┴───────────┴─────────────┴──────┘
```
Output:
```text
--- Known sex using dictionary ({'sex': 'is_not_null()'}) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬─────────────┬────────┐
│ species ┆ island    ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64         ┆ str    │
╞═════════╪═══════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3450.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3650.0      ┆ Male   │
└─────────┴───────────┴─────────────┴────────┘
```
Output:
```text
--- Spaced column using dictionary ({'bill length mm': 'is_not_null()'}) ---
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬────────────────┬────────┐
│ species ┆ island    ┆ bill length mm ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ str    │
╞═════════╪═══════════╪════════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ Female │
│ Adelie  ┆ Torgersen ┆ 39.3           ┆ Male   │
└─────────┴───────────┴────────────────┴────────┘
```

```python
# 3. Floating-point NaN checks via string expressions and dictionaries:
df_measurements = pt.DataFrame({
    "sample_id": ["S1", "S2", "S3", "S4"],
    "score": [98.5, float("nan"), None, 76.2],
})

print("--- Original DataFrame (has both float NaN and missing null) ---")
display(df_measurements)

print("\n--- Non-dict string expression: score.is_nan() ---")
display(df_measurements.filter("score.is_nan()"))

print("\n--- Dictionary expression: {'score': 'is_nan()'} ---")
display(df_measurements.filter({"score": "is_nan()"}))

print("\n--- Dictionary expression: {'score': 'is_not_nan()'} ---")
display(df_measurements.filter({"score": "is_not_nan()"}))
```
Output:
```text
--- Original DataFrame (has both float NaN and missing null) ---
```
Output:
```text
shape: (4, 2)
┌───────────┬───────┐
│ sample_id ┆ score │
│ ---       ┆ ---   │
│ str       ┆ f64   │
╞═══════════╪═══════╡
│ S1        ┆ 98.5  │
│ S2        ┆ NaN   │
│ S3        ┆ null  │
│ S4        ┆ 76.2  │
└───────────┴───────┘
```
Output:
```text
--- Non-dict string expression: score.is_nan() ---
```
Output:
```text
shape: (1, 2)
┌───────────┬───────┐
│ sample_id ┆ score │
│ ---       ┆ ---   │
│ str       ┆ f64   │
╞═══════════╪═══════╡
│ S2        ┆ NaN   │
└───────────┴───────┘
```
Output:
```text
--- Dictionary expression: {'score': 'is_nan()'} ---
```
Output:
```text
shape: (1, 2)
┌───────────┬───────┐
│ sample_id ┆ score │
│ ---       ┆ ---   │
│ str       ┆ f64   │
╞═══════════╪═══════╡
│ S2        ┆ NaN   │
└───────────┴───────┘
```
Output:
```text
--- Dictionary expression: {'score': 'is_not_nan()'} ---
```
Output:
```text
shape: (2, 2)
┌───────────┬───────┐
│ sample_id ┆ score │
│ ---       ┆ ---   │
│ str       ┆ f64   │
╞═══════════╪═══════╡
│ S1        ┆ 98.5  │
│ S4        ┆ 76.2  │
└───────────┴───────┘
```

```python
# 4. Combining null/NaN checks and dynamic query building:
print("--- Combining in string expression ---")
display(
    penguins
    .filter("sex.is_not_null() and body_mass_g > 4500")
    .select('species', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Combining in dictionary ---")
display(
    penguins
    .filter({"sex": "is_not_null()", "species": "Gentoo"})
    .select('species', 'body_mass_g', 'sex')
    .head(5)
)

print("\n--- Dynamic programmatic query construction ---")
criteria = {"island": "Biscoe", "species": "Gentoo"}
criteria["sex"] = "is_not_null()"
display(
    penguins
    .filter(criteria)
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)
```
Output:
```text
--- Combining in string expression ---
```
Output:
```text
shape: (5, 3)
┌─────────┬─────────────┬──────┐
│ species ┆ body_mass_g ┆ sex  │
│ ---     ┆ ---         ┆ ---  │
│ str     ┆ f64         ┆ str  │
╞═════════╪═════════════╪══════╡
│ Adelie  ┆ 4675.0      ┆ Male │
│ Adelie  ┆ 4650.0      ┆ Male │
│ Adelie  ┆ 4600.0      ┆ Male │
│ Adelie  ┆ 4700.0      ┆ Male │
│ Adelie  ┆ 4725.0      ┆ Male │
└─────────┴─────────────┴──────┘
```
Output:
```text
--- Combining in dictionary ---
```
Output:
```text
shape: (5, 3)
┌─────────┬─────────────┬────────┐
│ species ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---         ┆ ---    │
│ str     ┆ f64         ┆ str    │
╞═════════╪═════════════╪════════╡
│ Gentoo  ┆ 4500.0      ┆ Female │
│ Gentoo  ┆ 5700.0      ┆ Male   │
│ Gentoo  ┆ 4450.0      ┆ Female │
│ Gentoo  ┆ 5700.0      ┆ Male   │
│ Gentoo  ┆ 5400.0      ┆ Male   │
└─────────┴─────────────┴────────┘
```
Output:
```text
--- Dynamic programmatic query construction ---
```
Output:
```text
shape: (5, 4)
┌─────────┬────────┬─────────────┬────────┐
│ species ┆ island ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---    ┆ ---         ┆ ---    │
│ str     ┆ str    ┆ f64         ┆ str    │
╞═════════╪════════╪═════════════╪════════╡
│ Gentoo  ┆ Biscoe ┆ 4500.0      ┆ Female │
│ Gentoo  ┆ Biscoe ┆ 5700.0      ┆ Male   │
│ Gentoo  ┆ Biscoe ┆ 4450.0      ┆ Female │
│ Gentoo  ┆ Biscoe ┆ 5700.0      ┆ Male   │
│ Gentoo  ┆ Biscoe ┆ 5400.0      ┆ Male   │
└─────────┴────────┴─────────────┴────────┘
```

## 9. Column-to-Column Comparisons

You can compare two DataFrame columns directly against each other (e.g., detecting limit breaches or verifying ID reconciliations) in both Python and CLI using bare column names without any `col()` wrapper:

```python
# Comparing two columns directly using bare column names
df_risk = pt.DataFrame({
    "exposure": [120, 250, 80, 410],
    "limit": [100, 200, 150, 400],
    "tranche_id": ["T1", "T2", "T3", "T4"],
    "deal_id": ["T1", "D2", "T3", "D4"],
})

print("--- Breaches (exposure > limit) ---")
display(df_risk.filter("exposure > limit"))

print("\n--- Reconciled (tranche_id == deal_id) ---")
display(df_risk.filter("tranche_id == deal_id"))
```
Output:
```text
--- Breaches (exposure > limit) ---
```
Output:
```text
shape: (3, 4)
┌──────────┬───────┬────────────┬─────────┐
│ exposure ┆ limit ┆ tranche_id ┆ deal_id │
│ ---      ┆ ---   ┆ ---        ┆ ---     │
│ i64      ┆ i64   ┆ str        ┆ str     │
╞══════════╪═══════╪════════════╪═════════╡
│ 120      ┆ 100   ┆ T1         ┆ T1      │
│ 250      ┆ 200   ┆ T2         ┆ D2      │
│ 410      ┆ 400   ┆ T4         ┆ D4      │
└──────────┴───────┴────────────┴─────────┘
```
Output:
```text
--- Reconciled (tranche_id == deal_id) ---
```
Output:
```text
shape: (2, 4)
┌──────────┬───────┬────────────┬─────────┐
│ exposure ┆ limit ┆ tranche_id ┆ deal_id │
│ ---      ┆ ---   ┆ ---        ┆ ---     │
│ i64      ┆ i64   ┆ str        ┆ str     │
╞══════════╪═══════╪════════════╪═════════╡
│ 120      ┆ 100   ┆ T1         ┆ T1      │
│ 80       ┆ 150   ┆ T3         ┆ T3      │
└──────────┴───────┴────────────┴─────────┘
```

## 10. External Variable Injection (`@var` and `col(@var)`)

You can inject external local variables into filter expressions:
- `@var`: Injects a scalar threshold or comparison literal
- `col(@var)`: Injects a dynamic column name from a Python variable

```python
# Inject scalar threshold and dynamic column target
threshold = 100
target_col = "deal_id"

display(df_risk.filter("exposure > @threshold and tranche_id == col(@target_col)"))
```
Output:
```text
shape: (1, 4)
┌──────────┬───────┬────────────┬─────────┐
│ exposure ┆ limit ┆ tranche_id ┆ deal_id │
│ ---      ┆ ---   ┆ ---        ┆ ---     │
│ i64      ┆ i64   ┆ str        ┆ str     │
╞══════════╪═══════╪════════════╪═════════╡
│ 120      ┆ 100   ┆ T1         ┆ T1      │
└──────────┴───────┴────────────┴─────────┘
```

## 11. Strict Error Handling & Diagnostic Feedback

`pytae` is intentionally designed with helpful, unambiguous error messages that guide you to the right syntax rather than silently failing or doing unexpected things.

```python
# 1. Keyword arguments are strictly rejected (forces '==' and prevents '=' confusion)
try:
    penguins.filter(species="Gentoo")
except TypeError as err:
    print("Caught expected TypeError:\n", err)
```
Output:
```text
Caught expected TypeError:
 filter(): keyword arguments are not supported (received ['species']). Equality comparisons strictly require '==' to avoid '=' assignment ambiguity. Use a string expression (e.g. df.filter("species == 'Gentoo'")) or a dictionary (e.g. df.filter({'species': 'Gentoo'}))
```

```python
# 2. Single '=' in strings is strictly disallowed (reserved for mutate)
try:
    penguins.filter("species = 'Gentoo'")
except ValueError as err:
    print("Caught expected ValueError:\n", err)
```
Output:
```text
Caught expected ValueError:
 invalid filter condition 'species = 'Gentoo'': use '==' for equality comparisons (e.g. species == 'Gentoo'). Single '=' is for assignment (-mutate), not comparison (-filter).
```

```python
# 3. Comma ',' is disallowed as a boolean operator (use 'and')
try:
    penguins.filter("species == 'Gentoo', body_mass_g > 5000")
except ValueError as err:
    print("Caught expected ValueError:\n", err)
```
Output:
```text
Caught expected ValueError:
 invalid filter condition 'species == 'Gentoo', body_mass_g > 5000': comma ',' is not supported as a boolean operator. Use 'and' instead (e.g. species == 'Gentoo' and body_mass_g > 5000).
```

```python
# 4. Bitwise '&' and '|' are disallowed (use 'and' / 'or')
try:
    penguins.filter("species == 'Gentoo' & body_mass_g > 5000")
except ValueError as err:
    print("Caught expected ValueError:\n", err)
```
Output:
```text
Caught expected ValueError:
 invalid filter condition 'species == 'Gentoo' & body_mass_g > 5000': '&' is not supported in filter. Use 'and' instead.
```

```python
# 5. Legacy interval strings '[3000, 4000]' are disallowed
try:
    penguins.filter("body_mass_g = [3000, 4000]")
except ValueError as err:
    print("Caught expected ValueError:\n", err)
```
Output:
```text
Caught expected ValueError:
 invalid filter condition 'body_mass_g = [3000, 4000]': use '==' for equality comparisons (e.g. body_mass_g == [3000, 4000]). Single '=' is for assignment (-mutate), not comparison (-filter).
```

```python
# 6. String column type safety: unquoted int against string column raises TypeError
df_str = pt.DataFrame({"id": ["1", "9", "10"], "val": [100, 200, 300]})

try:
    df_str.filter("id == 9")
except TypeError as err:
    print("Caught expected TypeError:\n", err)
```
Output:
```text
Caught expected TypeError:
 filter(): column 'id' has String type, but received int 9. String values must be enclosed in quotes (e.g. id = '9').
```

```python
# 7. Typo suggestion on misspelled column names
try:
    penguins.filter("speceis == 'Adelie'")
except (KeyError, Exception) as err:
    print("Caught expected error:\n", err)
```
Output:
```text
Caught expected error:
 unable to find column "speceis"; valid columns: ["species", "island", "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "sex"]

Did you mean "species"?
```

## 12. Real-World Analytical Pipelines

Filter works seamlessly as the entry point or intermediate step in pytae pipelines combining filtering, grouping, aggregation, reshaping, and sorting.

```python
# Tips dataset: weekend dinner parties of 2+ spending > $15
(
    tips
    .filter("day in ['Sat', 'Sun'] and time == 'Dinner' and size >= 2 and total_bill > 15")
    .by('smoker')
    .agg("mean_tip = tip:mean, mean_bill = total_bill:mean, total_diners = size:sum, n_tables = count")
    .arrange("mean_tip desc")
)
```
Output:
```text
shape: (2, 5)
┌────────┬──────────┬───────────┬──────────────┬──────────┐
│ smoker ┆ mean_tip ┆ mean_bill ┆ total_diners ┆ n_tables │
│ ---    ┆ ---      ┆ ---       ┆ ---          ┆ ---      │
│ cat    ┆ f64      ┆ f64       ┆ i64          ┆ i64      │
╞════════╪══════════╪═══════════╪══════════════╪══════════╡
│ No     ┆ 3.521081 ┆ 23.257297 ┆ 225          ┆ 74       │
│ Yes    ┆ 3.384889 ┆ 26.112    ┆ 122          ┆ 45       │
└────────┴──────────┴───────────┴──────────────┴──────────┘
```

```python
# Titanic dataset: survival rate of passengers in 1st/2nd class by sex
(
    titanic
    .filter("pclass in [1, 2] and age.is_not_null()")
    .filter({"age": ("between", 18, 60)})
    .by('pclass', 'sex')
    .agg("survival_rate = survived:mean, n_passengers = count")
    .arrange("pclass, sex")
)
```
Output:
```text
shape: (4, 4)
┌────────┬────────┬───────────────┬──────────────┐
│ pclass ┆ sex    ┆ survival_rate ┆ n_passengers │
│ ---    ┆ ---    ┆ ---           ┆ ---          │
│ i64    ┆ str    ┆ f64           ┆ i64          │
╞════════╪════════╪═══════════════╪══════════════╡
│ 1      ┆ female ┆ 0.973333      ┆ 75           │
│ 1      ┆ male   ┆ 0.411765      ┆ 85           │
│ 2      ┆ female ┆ 0.903226      ┆ 62           │
│ 2      ┆ male   ┆ 0.058824      ┆ 85           │
└────────┴────────┴───────────────┴──────────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/head_tail.ipynb
################################################################################
# Notebook: head_tail.ipynb

# Group-Aware & Extreme Row Slicing (`head` & `tail`)

[← Back to Master Reference](../../pytae.md)

`head()` and `tail()` select the first or last $N$ rows (or proportion of rows via `prop=`), with boundary tie-breaking (`with_ties=True`) and complete group awareness via `pt.by()`.

In accordance with Pytae's *"One and Only One Obvious Way"*, extreme row selection is achieved by composing `arrange()` with `head()` or `tail()`, eliminating the need for niche specialized verbs like `pick`:

| Method | Key Parameters | Purpose |
|---|---|---|
| `df.head(n=5, prop=None, with_ties=False)` | `n`, `prop`, `with_ties` | First $N$ rows (or fraction) |
| `df.tail(n=5, prop=None, with_ties=False)` | `n`, `prop`, `with_ties` | Last $N$ rows (or fraction) |
| `df.arrange(...).head(n)` | — | Extreme top rows overall |
| `df.arrange(...).tail(n)` | — | Extreme bottom rows overall |
| `df.by(...).arrange(...).head(n)` | `*cols` | Extreme rows partitioned per group |

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
```

## 1. Composing `arrange()` with `head()` — Top N Records

Retrieve rows with the highest values by sorting descending and slicing the head.

```python
# Top 3 heaviest penguins overall
(
    penguins
    .arrange("body_mass_g desc")
    .head(3)
    .select("species", "island", "body_mass_g")
)
```
Output:
```text
shape: (3, 3)
┌─────────┬────────┬─────────────┐
│ species ┆ island ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---         │
│ str     ┆ str    ┆ f64         │
╞═════════╪════════╪═════════════╡
│ Gentoo  ┆ Biscoe ┆ 6300.0      │
│ Gentoo  ┆ Biscoe ┆ 6050.0      │
│ Gentoo  ┆ Biscoe ┆ 6000.0      │
└─────────┴────────┴─────────────┘
```

## 2. Composing `arrange()` with `head()` or `tail()` — Bottom N Records

Retrieve rows with the lowest values by sorting ascending or taking the tail.

```python
# 3 lightest penguins overall
(
    penguins
    .arrange("body_mass_g")
    .head(3)
    .select("species", "island", "body_mass_g")
)
```
Output:
```text
shape: (3, 3)
┌───────────┬────────┬─────────────┐
│ species   ┆ island ┆ body_mass_g │
│ ---       ┆ ---    ┆ ---         │
│ str       ┆ str    ┆ f64         │
╞═══════════╪════════╪═════════════╡
│ Chinstrap ┆ Dream  ┆ 2700.0      │
│ Adelie    ┆ Biscoe ┆ 2850.0      │
│ Adelie    ┆ Biscoe ┆ 2850.0      │
└───────────┴────────┴─────────────┘
```

## 3. Group-Aware Slicing (`df.by()`)

When preceded by `.by(...)`, `head()` and `tail()` extract rows **per group**, returning a clean, ungrouped DataFrame.

```python
# Heaviest penguin for each species
(
    penguins
    .by("species")
    .arrange("body_mass_g desc")
    .head(1)
    .select("species", "island", "body_mass_g")
)
```
Output:
```text
shape: (3, 3)
┌───────────┬────────┬─────────────┐
│ species   ┆ island ┆ body_mass_g │
│ ---       ┆ ---    ┆ ---         │
│ str       ┆ str    ┆ f64         │
╞═══════════╪════════╪═════════════╡
│ Adelie    ┆ Biscoe ┆ 4775.0      │
│ Chinstrap ┆ Dream  ┆ 4800.0      │
│ Gentoo    ┆ Biscoe ┆ 6300.0      │
└───────────┴────────┴─────────────┘
```

```python
# Lightest 2 penguins per island
(
    penguins
    .by("island")
    .arrange("body_mass_g")
    .head(2)
    .select("island", "species", "body_mass_g")
)
```
Output:
```text
shape: (6, 3)
┌───────────┬───────────┬─────────────┐
│ island    ┆ species   ┆ body_mass_g │
│ ---       ┆ ---       ┆ ---         │
│ str       ┆ str       ┆ f64         │
╞═══════════╪═══════════╪═════════════╡
│ Biscoe    ┆ Adelie    ┆ 2850.0      │
│ Biscoe    ┆ Adelie    ┆ 2850.0      │
│ Dream     ┆ Chinstrap ┆ 2700.0      │
│ Dream     ┆ Adelie    ┆ 2900.0      │
│ Torgersen ┆ Adelie    ┆ 2900.0      │
│ Torgersen ┆ Adelie    ┆ 3050.0      │
└───────────┴───────────┴─────────────┘
```

## 4. Proportion Slicing with `prop=`

Select a fraction of rows (e.g. `prop=0.1` or `n="10%"`) overall or within each group.

```python
# Top 10% heaviest penguins per species
(
    penguins
    .by("species")
    .arrange("body_mass_g desc")
    .head(prop=0.1)
    .select("species", "island", "body_mass_g")
)
```
Output:
```text
shape: (33, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Biscoe    ┆ 4775.0      │
│ Adelie  ┆ Biscoe    ┆ 4725.0      │
│ Adelie  ┆ Torgersen ┆ 4700.0      │
│ Adelie  ┆ Torgersen ┆ 4675.0      │
│ Adelie  ┆ Dream     ┆ 4650.0      │
│ …       ┆ …         ┆ …           │
│ Gentoo  ┆ Biscoe    ┆ 5850.0      │
│ Gentoo  ┆ Biscoe    ┆ 5850.0      │
│ Gentoo  ┆ Biscoe    ┆ 5800.0      │
│ Gentoo  ┆ Biscoe    ┆ 5800.0      │
│ Gentoo  ┆ Biscoe    ┆ 5750.0      │
└─────────┴───────────┴─────────────┘
```

## 5. Boundary Ties (`with_ties=True`)

When multiple rows share the same value at the rank cutoff, pass `with_ties=True` to include all tied rows.

```python
# Top 3 with boundary ties included
(
    penguins
    .arrange("body_mass_g desc")
    .head(3, with_ties=True)
    .select("species", "island", "body_mass_g")
)
```
Output:
```text
shape: (4, 3)
┌─────────┬────────┬─────────────┐
│ species ┆ island ┆ body_mass_g │
│ ---     ┆ ---    ┆ ---         │
│ str     ┆ str    ┆ f64         │
╞═════════╪════════╪═════════════╡
│ Gentoo  ┆ Biscoe ┆ 6300.0      │
│ Gentoo  ┆ Biscoe ┆ 6050.0      │
│ Gentoo  ┆ Biscoe ┆ 6000.0      │
│ Gentoo  ┆ Biscoe ┆ 6000.0      │
└─────────┴────────┴─────────────┘
```

## 6. Functional Style (`pt.head` & `pt.tail`)

`pt.head(df, ...)` and `pt.tail(df, ...)` are also available as standalone functional verbs:

```python
# Functional top bill overall
pt.head(pt.arrange(tips, "total_bill desc"), 1)[["day", "total_bill", "tip"]]
```
Output:
```text
shape: (1, 3)
┌─────┬────────────┬──────┐
│ day ┆ total_bill ┆ tip  │
│ --- ┆ ---        ┆ ---  │
│ cat ┆ f64        ┆ f64  │
╞═════╪════════════╪══════╡
│ Sat ┆ 50.81      ┆ 10.0 │
└─────┴────────────┴──────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/join.ipynb
################################################################################
# Notebook: join.ipynb

# Relational Joins & Dataset Stacking (`join` & `concat`)

`pytae` provides high-performance relational joins and dataset concatenation powered natively by Polars' SIMD vector core.
- **Symmetrical Strategy Support**: `how='inner'`, `'left'`, `'right'`, `'full'`, `'semi'`, `'anti'`, `'cross'`
- **Colon Key Shorthand**: `on='client_id:id'` directly maps differing column keys without typing separate `left_on` / `right_on`
- **Cardinality Validation**: `validate='1:1'`, `'1:m'`, `'m:1'` verifies key uniqueness to prevent silent row explosion
- **Row Stacking**: `pt.concat([df1, df2])` and `df1.concat(df2)` for appending matching datasets
- **Lazy Execution Pushdown**: Preserves query pushdowns when joining lazy scans (`pt.scan_parquet`)

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt
import polars as pl
```

```python
# Sample datasets for joining
orders = pt.DataFrame({
    "order_id": [101, 102, 103, 104, 105],
    "customer_id": [1, 2, 1, 3, 99],  # customer 99 does not exist in customers
    "amount": [250.0, 120.0, 310.0, 85.0, 400.0],
    "item": ["Laptop", "Mouse", "Monitor", "Keyboard", "Desk"]
})

customers = pt.DataFrame({
    "customer_id": [1, 2, 3, 4],  # customer 4 has no orders
    "name": ["Alice", "Bob", "Charlie", "Diana"],
    "region": ["West", "East", "West", "South"]
})

print("Orders:")
display(orders)
print("Customers:")
display(customers)
```
Output:
```text
Orders:
```
Output:
```text
shape: (5, 4)
┌──────────┬─────────────┬────────┬──────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     │
│ ---      ┆ ---         ┆ ---    ┆ ---      │
│ i64      ┆ i64         ┆ f64    ┆ str      │
╞══════════╪═════════════╪════════╪══════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard │
│ 105      ┆ 99          ┆ 400.0  ┆ Desk     │
└──────────┴─────────────┴────────┴──────────┘
```
Output:
```text
Customers:
```
Output:
```text
shape: (4, 3)
┌─────────────┬─────────┬────────┐
│ customer_id ┆ name    ┆ region │
│ ---         ┆ ---     ┆ ---    │
│ i64         ┆ str     ┆ str    │
╞═════════════╪═════════╪════════╡
│ 1           ┆ Alice   ┆ West   │
│ 2           ┆ Bob     ┆ East   │
│ 3           ┆ Charlie ┆ West   │
│ 4           ┆ Diana   ┆ South  │
└─────────────┴─────────┴────────┘
```

## 1. Inner Join (`how='inner'`)
Keeps only rows with matching keys in both datasets:

```python
orders.join(customers, on="customer_id", how="inner")
```
Output:
```text
shape: (4, 6)
┌──────────┬─────────────┬────────┬──────────┬─────────┬────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     ┆ name    ┆ region │
│ ---      ┆ ---         ┆ ---    ┆ ---      ┆ ---     ┆ ---    │
│ i64      ┆ i64         ┆ f64    ┆ str      ┆ str     ┆ str    │
╞══════════╪═════════════╪════════╪══════════╪═════════╪════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   ┆ Alice   ┆ West   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    ┆ Bob     ┆ East   │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  ┆ Alice   ┆ West   │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard ┆ Charlie ┆ West   │
└──────────┴─────────────┴────────┴──────────┴─────────┴────────┘
```

## 2. Left Outer Join (`how='left'`)
Preserves all orders; unmatched customers (e.g. customer 99) receive `null`:

```python
orders.join(customers, on="customer_id", how="left")
```
Output:
```text
shape: (5, 6)
┌──────────┬─────────────┬────────┬──────────┬─────────┬────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     ┆ name    ┆ region │
│ ---      ┆ ---         ┆ ---    ┆ ---      ┆ ---     ┆ ---    │
│ i64      ┆ i64         ┆ f64    ┆ str      ┆ str     ┆ str    │
╞══════════╪═════════════╪════════╪══════════╪═════════╪════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   ┆ Alice   ┆ West   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    ┆ Bob     ┆ East   │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  ┆ Alice   ┆ West   │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard ┆ Charlie ┆ West   │
│ 105      ┆ 99          ┆ 400.0  ┆ Desk     ┆ null    ┆ null   │
└──────────┴─────────────┴────────┴──────────┴─────────┴────────┘
```

## 3. Semi Join (`how='semi'`) & Anti Join (`how='anti'`)
- **Semi Join**: Filters rows in the left dataset that have a matching key in the right table (without appending right columns).
- **Anti Join**: Identifies orphan records in the left dataset that have **no** match in the right table.

```python
# Semi join: orders placed by known customers
orders.join(customers, on="customer_id", how="semi")
```
Output:
```text
shape: (4, 4)
┌──────────┬─────────────┬────────┬──────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     │
│ ---      ┆ ---         ┆ ---    ┆ ---      │
│ i64      ┆ i64         ┆ f64    ┆ str      │
╞══════════╪═════════════╪════════╪══════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard │
└──────────┴─────────────┴────────┴──────────┘
```

```python
# Anti join: customers who have NEVER placed an order
customers.join(orders, on="customer_id", how="anti")
```
Output:
```text
shape: (1, 3)
┌─────────────┬───────┬────────┐
│ customer_id ┆ name  ┆ region │
│ ---         ┆ ---   ┆ ---    │
│ i64         ┆ str   ┆ str    │
╞═════════════╪═══════╪════════╡
│ 4           ┆ Diana ┆ South  │
└─────────────┴───────┴────────┘
```

## 4. Differing Key Names (Colon Shorthand `left_key:right_key`)

When keys have different names, use `on="left_key:right_key"` instead of separate `left_on` and `right_on`:

```python
users = pt.DataFrame({
    "uid": [1, 2, 3],
    "email": ["alice@work.com", "bob@work.com", "charlie@work.com"]
})

# Join orders.customer_id with users.uid
orders.join(users, on="customer_id:uid", how="inner")
```
Output:
```text
shape: (4, 6)
┌──────────┬─────────────┬────────┬──────────┬─────┬──────────────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     ┆ uid ┆ email            │
│ ---      ┆ ---         ┆ ---    ┆ ---      ┆ --- ┆ ---              │
│ i64      ┆ i64         ┆ f64    ┆ str      ┆ i64 ┆ str              │
╞══════════╪═════════════╪════════╪══════════╪═════╪══════════════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   ┆ 1   ┆ alice@work.com   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    ┆ 2   ┆ bob@work.com     │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  ┆ 1   ┆ alice@work.com   │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard ┆ 3   ┆ charlie@work.com │
└──────────┴─────────────┴────────┴──────────┴─────┴──────────────────┘
```

## 5. Join Cardinality Validation (`validate=`)

Guard against silent duplication by validating key relationships:
- `validate="1:1"`: Keys must be unique in both left and right frames.
- `validate="m:1"`: Keys must be unique in the right frame.
- `validate="1:m"`: Keys must be unique in the left frame.

```python
# Validate m:1 (many orders per unique customer)
orders.join(customers, on="customer_id", how="inner", validate="m:1")
```
Output:
```text
shape: (4, 6)
┌──────────┬─────────────┬────────┬──────────┬─────────┬────────┐
│ order_id ┆ customer_id ┆ amount ┆ item     ┆ name    ┆ region │
│ ---      ┆ ---         ┆ ---    ┆ ---      ┆ ---     ┆ ---    │
│ i64      ┆ i64         ┆ f64    ┆ str      ┆ str     ┆ str    │
╞══════════╪═════════════╪════════╪══════════╪═════════╪════════╡
│ 101      ┆ 1           ┆ 250.0  ┆ Laptop   ┆ Alice   ┆ West   │
│ 102      ┆ 2           ┆ 120.0  ┆ Mouse    ┆ Bob     ┆ East   │
│ 103      ┆ 1           ┆ 310.0  ┆ Monitor  ┆ Alice   ┆ West   │
│ 104      ┆ 3           ┆ 85.0   ┆ Keyboard ┆ Charlie ┆ West   │
└──────────┴─────────────┴────────┴──────────┴─────────┴────────┘
```

## 6. Dataset Stacking (`pt.concat` & `df.concat`)

Stack multiple datasets sharing common schemas into a single unified table:

```python
sales_q1 = pt.DataFrame({"quarter": ["Q1", "Q1"], "revenue": [1000, 1500]})
sales_q2 = pt.DataFrame({"quarter": ["Q2", "Q2"], "revenue": [1200, 1800]})

# Functional concat
total_sales = pt.concat([sales_q1, sales_q2])
display(total_sales)

# Method chaining equivalent
display(sales_q1.concat(sales_q2))
```
Output:
```text
shape: (4, 2)
┌─────────┬─────────┐
│ quarter ┆ revenue │
│ ---     ┆ ---     │
│ str     ┆ i64     │
╞═════════╪═════════╡
│ Q1      ┆ 1000    │
│ Q1      ┆ 1500    │
│ Q2      ┆ 1200    │
│ Q2      ┆ 1800    │
└─────────┴─────────┘
```
Output:
```text
shape: (4, 2)
┌─────────┬─────────┐
│ quarter ┆ revenue │
│ ---     ┆ ---     │
│ str     ┆ i64     │
╞═════════╪═════════╡
│ Q1      ┆ 1000    │
│ Q1      ┆ 1500    │
│ Q2      ┆ 1200    │
│ Q2      ┆ 1800    │
└─────────┴─────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/mutate.ipynb
################################################################################
# Notebook: mutate.ipynb

# `mutate` — Reference
`mutate` creates or overwrites columns using clean keyword argument syntax (`col="expr"` or `col=callable`). Each entry is evaluated in order via pandas `eval()` — a plain formula per column, or a lambda when needed.
### Calling Styles
1. **Keyword arguments** (most Pythonic): `.mutate(bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")`
2. **Dictionary unpacking** (for new column names with spaces): `.mutate(**{"body mass kg": "body_mass_g / 1000"})`
3. **External file specification**: `.mutate("@features.txt")`
---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import numpy as np
import pytae as pt

penguins = pt.sample_data['penguins']
```

## A single derived column

```python
# Body mass index style ratio — clean assignment formula via kwargs
(
    penguins
    .mutate(bmi='body_mass_g / bill_length_mm ** 2')
    .select('species', 'body_mass_g', 'bill_length_mm', 'bmi')
    .sample(10)
)
```
Output:
```text
shape: (10, 4)
┌─────────┬─────────────┬────────────────┬──────────┐
│ species ┆ body_mass_g ┆ bill_length_mm ┆ bmi      │
│ ---     ┆ ---         ┆ ---            ┆ ---      │
│ str     ┆ f64         ┆ f64            ┆ f64      │
╞═════════╪═════════════╪════════════════╪══════════╡
│ Adelie  ┆ 2850.0      ┆ 36.4           ┆ 2.151008 │
│ Adelie  ┆ 4275.0      ┆ 42.2           ┆ 2.400553 │
│ Adelie  ┆ 3475.0      ┆ 40.6           ┆ 2.108156 │
│ Adelie  ┆ 3050.0      ┆ 32.1           ┆ 2.959987 │
│ Adelie  ┆ 3725.0      ┆ 40.7           ┆ 2.248731 │
│ Adelie  ┆ 3700.0      ┆ 36.0           ┆ 2.854938 │
│ Gentoo  ┆ 4700.0      ┆ 45.8           ┆ 2.240613 │
│ Gentoo  ┆ 5200.0      ┆ 50.8           ┆ 2.015004 │
│ Gentoo  ┆ 4700.0      ┆ 41.7           ┆ 2.702874 │
│ Gentoo  ┆ 4875.0      ┆ 44.5           ┆ 2.46181  │
└─────────┴─────────────┴────────────────┴──────────┘
```

```python
# Column names inside the expression must stay unquoted — quoting one turns it into
# a string literal, which will break arithmetic
try:
    penguins.mutate(bmi="'body_mass_g' / 'bill_length_mm' ** 2")
except TypeError as exc:
    print(f"TypeError (as expected): {exc}")
```
Output:
```text
TypeError (as expected): division with 'String' datatypes is not allowed
```

## Multiple entries in one call, and chaining a later entry off an earlier one
Entries are applied left to right, so a later expression can reference a column derived earlier in the *same* `mutate()` call.

```python
# Two independent derived columns in one call via kwargs
(
    penguins
    .mutate(heavy='body_mass_g > 4000', mass_kg='body_mass_g / 1000')
    .select('species', 'body_mass_g', 'mass_kg', 'heavy')
    .sample(10)
)
```
Output:
```text
shape: (10, 4)
┌───────────┬─────────────┬─────────┬───────┐
│ species   ┆ body_mass_g ┆ mass_kg ┆ heavy │
│ ---       ┆ ---         ┆ ---     ┆ ---   │
│ str       ┆ f64         ┆ f64     ┆ bool  │
╞═══════════╪═════════════╪═════════╪═══════╡
│ Adelie    ┆ 2900.0      ┆ 2.9     ┆ false │
│ Adelie    ┆ 3800.0      ┆ 3.8     ┆ false │
│ Adelie    ┆ 3950.0      ┆ 3.95    ┆ false │
│ Adelie    ┆ 4100.0      ┆ 4.1     ┆ true  │
│ Chinstrap ┆ 4050.0      ┆ 4.05    ┆ true  │
│ Chinstrap ┆ 3525.0      ┆ 3.525   ┆ false │
│ Gentoo    ┆ 4200.0      ┆ 4.2     ┆ true  │
│ Gentoo    ┆ 4900.0      ┆ 4.9     ┆ true  │
│ Gentoo    ┆ 5650.0      ┆ 5.65    ┆ true  │
│ Gentoo    ┆ 5950.0      ┆ 5.95    ┆ true  │
└───────────┴─────────────┴─────────┴───────┘
```

```python
# mass_lb references mass_kg, derived by the keyword just before it
(
    penguins
    .mutate(mass_kg='body_mass_g / 1000', mass_lb='mass_kg * 2.20462')
    .select('species', 'body_mass_g', 'mass_kg', 'mass_lb')
    .sample(10)
)
```
Output:
```text
shape: (10, 4)
┌───────────┬─────────────┬─────────┬───────────┐
│ species   ┆ body_mass_g ┆ mass_kg ┆ mass_lb   │
│ ---       ┆ ---         ┆ ---     ┆ ---       │
│ str       ┆ f64         ┆ f64     ┆ f64       │
╞═══════════╪═════════════╪═════════╪═══════════╡
│ Adelie    ┆ 4150.0      ┆ 4.15    ┆ 9.149173  │
│ Adelie    ┆ 3600.0      ┆ 3.6     ┆ 7.936632  │
│ Adelie    ┆ 3600.0      ┆ 3.6     ┆ 7.936632  │
│ Adelie    ┆ 3900.0      ┆ 3.9     ┆ 8.598018  │
│ Adelie    ┆ 3450.0      ┆ 3.45    ┆ 7.605939  │
│ Chinstrap ┆ 4050.0      ┆ 4.05    ┆ 8.928711  │
│ Chinstrap ┆ 4100.0      ┆ 4.1     ┆ 9.038942  │
│ Gentoo    ┆ 4650.0      ┆ 4.65    ┆ 10.251483 │
│ Gentoo    ┆ 4400.0      ┆ 4.4     ┆ 9.700328  │
│ Gentoo    ┆ 4850.0      ┆ 4.85    ┆ 10.692407 │
└───────────┴─────────────┴─────────┴───────────┘
```

## String comparisons and local variables
String literals *inside* the expression (e.g. `'Adelie'`) need real quotes — column names stay bare. A variable from the calling scope can be referenced with an `@` prefix, same as pandas' own `eval()`/`query()`.

```python
# String comparisons inside the expression formula
(
    penguins
    .mutate(is_adelie="species == 'Adelie'")
    .select('species', 'is_adelie')
    .sample(10)
)
```
Output:
```text
shape: (10, 2)
┌───────────┬───────────┐
│ species   ┆ is_adelie │
│ ---       ┆ ---       │
│ str       ┆ bool      │
╞═══════════╪═══════════╡
│ Adelie    ┆ true      │
│ Adelie    ┆ true      │
│ Adelie    ┆ true      │
│ Adelie    ┆ true      │
│ Adelie    ┆ true      │
│ Chinstrap ┆ false     │
│ Chinstrap ┆ false     │
│ Chinstrap ┆ false     │
│ Gentoo    ┆ false     │
│ Gentoo    ┆ false     │
└───────────┴───────────┘
```

```python
# @-prefixed names resolve against the scope that called mutate(), not the module
# — works identically whether calling pt.mutate() or chaining .mutate()
threshold = 4000

(
    penguins
    .mutate(heavy='body_mass_g >= @threshold')
    .select('species', 'body_mass_g', 'heavy')
    .sample(10)
)
```
Output:
```text
shape: (10, 3)
┌─────────┬─────────────┬───────┐
│ species ┆ body_mass_g ┆ heavy │
│ ---     ┆ ---         ┆ ---   │
│ str     ┆ f64         ┆ bool  │
╞═════════╪═════════════╪═══════╡
│ Adelie  ┆ 3200.0      ┆ false │
│ Adelie  ┆ 4100.0      ┆ true  │
│ Adelie  ┆ 4250.0      ┆ true  │
│ Adelie  ┆ 3475.0      ┆ false │
│ Gentoo  ┆ 4750.0      ┆ true  │
│ Gentoo  ┆ 5300.0      ┆ true  │
│ Gentoo  ┆ 4400.0      ┆ true  │
│ Gentoo  ┆ 5650.0      ┆ true  │
│ Gentoo  ┆ 5950.0      ┆ true  │
│ Gentoo  ┆ 5500.0      ┆ true  │
└─────────┴─────────────┴───────┘
```

## Overwriting an existing column

```python
# mutate() can overwrite a column in place, e.g. converting units
(
    penguins
    .mutate(body_mass_g='body_mass_g / 1000')
    .select('species', 'body_mass_g')
    .sample(10)
)
```
Output:
```text
shape: (10, 2)
┌───────────┬─────────────┐
│ species   ┆ body_mass_g │
│ ---       ┆ ---         │
│ str       ┆ f64         │
╞═══════════╪═════════════╡
│ Adelie    ┆ 4.5         │
│ Adelie    ┆ 3.15        │
│ Adelie    ┆ 4.65        │
│ Adelie    ┆ 4.1         │
│ Adelie    ┆ 3.9         │
│ Adelie    ┆ 4.0         │
│ Chinstrap ┆ 3.725       │
│ Chinstrap ┆ 4.05        │
│ Gentoo    ┆ 5.1         │
│ Gentoo    ┆ 6.05        │
└───────────┴─────────────┘
```

## Column names with spaces — bracket syntax
Use square brackets `[col name]` to reference column names containing spaces without shell or syntax hazards (backticks are also supported):

```python
import pandas as pd
spaced = pt.DataFrame({'body mass g': [3750, 4200], 'bill length mm': [39.1, 46.5]})

# Square brackets protect column names that contain spaces
spaced.mutate(bmi="[body mass g] / [bill length mm] ** 2")
```
Output:
```text
shape: (2, 3)
┌─────────────┬────────────────┬──────────┐
│ body mass g ┆ bill length mm ┆ bmi      │
│ ---         ┆ ---            ┆ ---      │
│ i64         ┆ f64            ┆ f64      │
╞═════════════╪════════════════╪══════════╡
│ 3750        ┆ 39.1           ┆ 2.452888 │
│ 4200        ┆ 46.5           ┆ 1.942421 │
└─────────────┴────────────────┴──────────┘
```

## Real-world pipeline: mutate → filter → select
`mutate()` chains like any other pytae method — filter on a column you just derived with `filter()`.

```python
(
    penguins
    .mutate(bmi='body_mass_g / bill_length_mm ** 2')
    .filter("bmi > 2")
    .select('species', 'island', 'body_mass_g', 'bill_length_mm', 'bmi')
    .sample(10)
)
```
Output:
```text
shape: (10, 5)
┌─────────┬───────────┬─────────────┬────────────────┬──────────┐
│ species ┆ island    ┆ body_mass_g ┆ bill_length_mm ┆ bmi      │
│ ---     ┆ ---       ┆ ---         ┆ ---            ┆ ---      │
│ str     ┆ str       ┆ f64         ┆ f64            ┆ f64      │
╞═════════╪═══════════╪═════════════╪════════════════╪══════════╡
│ Adelie  ┆ Biscoe    ┆ 3950.0      ┆ 40.5           ┆ 2.408169 │
│ Adelie  ┆ Biscoe    ┆ 4050.0      ┆ 42.0           ┆ 2.295918 │
│ Adelie  ┆ Biscoe    ┆ 3350.0      ┆ 35.5           ┆ 2.658203 │
│ Adelie  ┆ Torgersen ┆ 3550.0      ┆ 39.6           ┆ 2.2638   │
│ Adelie  ┆ Dream     ┆ 4475.0      ┆ 37.5           ┆ 3.182222 │
│ Gentoo  ┆ Biscoe    ┆ 5700.0      ┆ 50.0           ┆ 2.28     │
│ Gentoo  ┆ Biscoe    ┆ 5050.0      ┆ 46.3           ┆ 2.355751 │
│ Gentoo  ┆ Biscoe    ┆ 5650.0      ┆ 47.8           ┆ 2.472821 │
│ Gentoo  ┆ Biscoe    ┆ 5550.0      ┆ 50.5           ┆ 2.176257 │
│ Gentoo  ┆ Biscoe    ┆ 5000.0      ┆ 46.4           ┆ 2.322384 │
└─────────┴───────────┴─────────────┴────────────────┴──────────┘
```

## Conditional column creation — `if_else()`, `case_when()`, `map()`
Plain `eval()` has no ternary/`where()` support, so `mutate()` provides three dplyr-style helpers as ordinary function calls, evaluated via `np.where()`/`np.select()`/`Series.map()`: `if_else(condition, true_value, false_value)`, `case_when((cond1, val1), (cond2, val2), ..., default)`, and `map(column, {key: value, ...}, default)`. A trailing bare argument to `case_when` is the catch-all default (like SQL ELSE). Because they are ordinary calls, they compose and chain with each other and with any pandas method. String outcomes need quotes; conditions are vectorized — prefer `and`/`or`/`not` (the bitwise `&`/`|`/`~` also work).

```python
# if_else(condition, true_value, false_value) — like dplyr's if_else()
# true_value and false_value can be scalars or column names; conditions are vectorized
(
    penguins
    .mutate(weight_class="if_else(body_mass_g > 4000, 'heavy', 'light')")
    .select('species', 'body_mass_g', 'weight_class')
    .sample(10)
)
```
Output:
```text
shape: (10, 3)
┌───────────┬─────────────┬──────────────┐
│ species   ┆ body_mass_g ┆ weight_class │
│ ---       ┆ ---         ┆ ---          │
│ str       ┆ f64         ┆ str          │
╞═══════════╪═════════════╪══════════════╡
│ Adelie    ┆ null        ┆ light        │
│ Adelie    ┆ 3900.0      ┆ light        │
│ Adelie    ┆ 3350.0      ┆ light        │
│ Adelie    ┆ 3700.0      ┆ light        │
│ Chinstrap ┆ 3775.0      ┆ light        │
│ Chinstrap ┆ 4550.0      ┆ heavy        │
│ Gentoo    ┆ 5200.0      ┆ heavy        │
│ Gentoo    ┆ 5450.0      ┆ heavy        │
│ Gentoo    ┆ 5600.0      ┆ heavy        │
│ Gentoo    ┆ null        ┆ light        │
└───────────┴─────────────┴──────────────┘
```

```python
# case_when supports tuples or flat pairs with default=
(
    penguins
    .mutate(
        size_class="case_when(body_mass_g >= 4500, 'large', body_mass_g >= 3500, 'medium', default='small')"
    )
    .select('species', 'body_mass_g', 'size_class')
    .sample(10)
)
```
Output:
```text
shape: (10, 3)
┌───────────┬─────────────┬────────────┐
│ species   ┆ body_mass_g ┆ size_class │
│ ---       ┆ ---         ┆ ---        │
│ str       ┆ f64         ┆ str        │
╞═══════════╪═════════════╪════════════╡
│ Adelie    ┆ 3750.0      ┆ medium     │
│ Adelie    ┆ 4450.0      ┆ medium     │
│ Adelie    ┆ 3450.0      ┆ small      │
│ Chinstrap ┆ 3725.0      ┆ medium     │
│ Chinstrap ┆ 2900.0      ┆ small      │
│ Chinstrap ┆ 3400.0      ┆ small      │
│ Chinstrap ┆ 4000.0      ┆ medium     │
│ Gentoo    ┆ 5650.0      ┆ large      │
│ Gentoo    ┆ 4350.0      ┆ medium     │
│ Gentoo    ┆ 5000.0      ┆ large      │
└───────────┴─────────────┴────────────┘
```

```python
# map(column, {key: value, ...}, default) — recode a column through a dictionary lookup
# unmapped keys become default if given, else NaN
(
    penguins
    .mutate(
        island_code="map(island, {'Torgersen': 'TOR', 'Biscoe': 'BIS'}, 'OTH')"
    )
    .select('species', 'island', 'island_code')
    .sample(10)
)
```
Output:
```text
shape: (10, 3)
┌───────────┬───────────┬─────────────┐
│ species   ┆ island    ┆ island_code │
│ ---       ┆ ---       ┆ ---         │
│ str       ┆ str       ┆ str         │
╞═══════════╪═══════════╪═════════════╡
│ Adelie    ┆ Torgersen ┆ TOR         │
│ Adelie    ┆ Biscoe    ┆ BIS         │
│ Adelie    ┆ Dream     ┆ OTH         │
│ Adelie    ┆ Dream     ┆ OTH         │
│ Adelie    ┆ Biscoe    ┆ BIS         │
│ Chinstrap ┆ Dream     ┆ OTH         │
│ Chinstrap ┆ Dream     ┆ OTH         │
│ Gentoo    ┆ Biscoe    ┆ BIS         │
│ Gentoo    ┆ Biscoe    ┆ BIS         │
│ Gentoo    ┆ Biscoe    ┆ BIS         │
└───────────┴───────────┴─────────────┘
```

## First non-null resolution — `coalesce()`

`coalesce(col1, col2, ..., default)` evaluates candidates left-to-right and returns the first non-null value per row, like SQL `COALESCE()` or `dplyr::coalesce()`:

```python
contacts = pt.DataFrame({
    'mobile': [None, '555-1234', None],
    'home': ['555-5678', None, None],
    'work': [None, None, '555-9012'],
})

contacts.mutate(preferred_contact="coalesce(mobile, home, work, 'N/A')")
```
Output:
```text
shape: (3, 4)
┌──────────┬──────────┬──────────┬───────────────────┐
│ mobile   ┆ home     ┆ work     ┆ preferred_contact │
│ ---      ┆ ---      ┆ ---      ┆ ---               │
│ str      ┆ str      ┆ str      ┆ str               │
╞══════════╪══════════╪══════════╪═══════════════════╡
│ null     ┆ 555-5678 ┆ null     ┆ 555-5678          │
│ 555-1234 ┆ null     ┆ null     ┆ 555-1234          │
│ null     ┆ null     ┆ 555-9012 ┆ 555-9012          │
└──────────┴──────────┴──────────┴───────────────────┘
```

## Combining expressions and callables in kwargs

`mutate()` cleanly mixes expression strings and python callables (e.g. lambdas) in keyword arguments:

```python
(
    penguins
    .mutate(
        bmi='body_mass_g / bill_length_mm ** 2',
        mass_kg='body_mass_g / 1000',
        is_heavy=lambda df: df['body_mass_g'] > 4000,
    )
    .select('species', 'bmi', 'mass_kg', 'is_heavy')
    .head(5)
)
```
Output:
```text
shape: (5, 4)
┌─────────┬──────────┬─────────┬──────────┐
│ species ┆ bmi      ┆ mass_kg ┆ is_heavy │
│ ---     ┆ ---      ┆ ---     ┆ ---      │
│ str     ┆ f64      ┆ f64     ┆ bool     │
╞═════════╪══════════╪═════════╪══════════╡
│ Adelie  ┆ 2.452888 ┆ 3.75    ┆ false    │
│ Adelie  ┆ 2.435507 ┆ 3.8     ┆ false    │
│ Adelie  ┆ 2.001121 ┆ 3.25    ┆ false    │
│ Adelie  ┆ null     ┆ null    ┆ null     │
│ Adelie  ┆ 2.561456 ┆ 3.45    ┆ false    │
└─────────┴──────────┴─────────┴──────────┘
```

### Row-wise custom logic with Python's built-in `map()`
When custom logic requires multi-column `if/elif/else` branching or arbitrary Python functions expecting row values, wrap the scalar function in Python's built-in `map()` inside a callable `lambda d: map(func, d['a'], d['b'])`.

For dictionary value recoding, use vectorized formula `map(col, mapping)` instead.

```python
def classify_penguin(species, mass_kg, island):
    if mass_kg is None or np.isnan(mass_kg):
        return "Incomplete Data"
    if species == "Gentoo" and mass_kg > 5.0:
        return "Giant Gentoo"
    elif island == "Torgersen" and mass_kg > 3.7:
        return "Prime Torgersen"
    else:
        return "Standard"

(
    penguins
    .mutate(
        mass_kg="body_mass_g / 1000",
        category=lambda d: map(classify_penguin, d["species"], d["mass_kg"], d["island"]),
    )
    .select("species", "island", "body_mass_g", "mass_kg", "category")
    .head(6)
)
```
Output:
```text
shape: (6, 5)
┌─────────┬───────────┬─────────────┬─────────┬─────────────────┐
│ species ┆ island    ┆ body_mass_g ┆ mass_kg ┆ category        │
│ ---     ┆ ---       ┆ ---         ┆ ---     ┆ ---             │
│ str     ┆ str       ┆ f64         ┆ f64     ┆ str             │
╞═════════╪═══════════╪═════════════╪═════════╪═════════════════╡
│ Adelie  ┆ Torgersen ┆ 3750.0      ┆ 3.75    ┆ Prime Torgersen │
│ Adelie  ┆ Torgersen ┆ 3800.0      ┆ 3.8     ┆ Prime Torgersen │
│ Adelie  ┆ Torgersen ┆ 3250.0      ┆ 3.25    ┆ Standard        │
│ Adelie  ┆ Torgersen ┆ null        ┆ null    ┆ Incomplete Data │
│ Adelie  ┆ Torgersen ┆ 3450.0      ┆ 3.45    ┆ Standard        │
│ Adelie  ┆ Torgersen ┆ 3650.0      ┆ 3.65    ┆ Standard        │
└─────────┴───────────┴─────────────┴─────────┴─────────────────┘
```

## Loading specs from an external file — `@specs.txt`
For complex feature engineering or shared pipelines across Python and the CLI, specs can be loaded from an external file. The file supports multiline expressions, `#` comments, empty lines, and column chaining (where later formulas reference columns defined earlier in the same file).
### File content of `penguin_features.txt`:
```text
# Engineering features for penguins
mass_kg = body_mass_g / 1000
# Convert kg to lbs (references mass_kg computed above)
mass_lb = mass_kg * 2.20462
```

```python
# Write a small demo spec file with comments and assignment '=' syntax
spec_content = """# Engineering features for penguins
mass_kg = body_mass_g / 1000

# Convert kg to lbs
mass_lb = mass_kg * 2.20462
"""
with open("penguin_features.txt", "w") as f:
    f.write(spec_content)

# Load directly using @filename
result = penguins.mutate("@penguin_features.txt")
out = (
    result
    .select("species", "mass_kg", "mass_lb")
    .sample(5)
)

# Clean up demo file
import os
os.remove("penguin_features.txt")

out
```
Output:
```text
shape: (5, 3)
┌───────────┬─────────┬───────────┐
│ species   ┆ mass_kg ┆ mass_lb   │
│ ---       ┆ ---     ┆ ---       │
│ str       ┆ f64     ┆ f64       │
╞═══════════╪═════════╪═══════════╡
│ Adelie    ┆ 4.4     ┆ 9.700328  │
│ Adelie    ┆ 2.975   ┆ 6.558744  │
│ Adelie    ┆ 3.9     ┆ 8.598018  │
│ Chinstrap ┆ 4.8     ┆ 10.582176 │
│ Chinstrap ┆ 3.8     ┆ 8.377556  │
└───────────┴─────────┴───────────┘
```

## Columns with spaces — SQL-style brackets `[col]`

SQL-style square brackets `[col a]` are supported alongside backticks, avoiding shell backtick substitution hazards:

```python
spaced.mutate(ratio='[body mass g] / [bill length mm]')
```
Output:
```text
shape: (2, 3)
┌─────────────┬────────────────┬───────────┐
│ body mass g ┆ bill length mm ┆ ratio     │
│ ---         ┆ ---            ┆ ---       │
│ i64         ┆ f64            ┆ f64       │
╞═════════════╪════════════════╪═══════════╡
│ 3750        ┆ 39.1           ┆ 95.907928 │
│ 4200        ┆ 46.5           ┆ 90.322581 │
└─────────────┴────────────────┴───────────┘
```

## Creating new columns with spaces — string expressions `[col] = ...`

You can create columns with spaces directly using string assignment expressions with brackets `[new col] = ...` with zero dictionary unpacking.

(Dictionary unpacking `**{'col name': ...}` is also supported for kwargs).

```python
# Create a new column with spaces using bracket string expression (no dict unpacking!)
(
    spaced
    .mutate("[body mass ratio] = [body mass g] / [bill length mm]")
    .select('[body mass g]', '[body mass ratio]')
    .head()
)
```
Output:
```text
shape: (2, 2)
┌─────────────┬─────────────────┐
│ body mass g ┆ body mass ratio │
│ ---         ┆ ---             │
│ i64         ┆ f64             │
╞═════════════╪═════════════════╡
│ 3750        ┆ 95.907928       │
│ 4200        ┆ 90.322581       │
└─────────────┴─────────────────┘
```

```python
# Define multiple new columns with spaces at once via string expressions
(
    penguins
    .mutate(
        "[body mass kg] = body_mass_g / 1000",
        "[bill ratio] = bill_length_mm / bill_depth_mm",
    )
    .select('species', '[body mass kg]', '[bill ratio]')
    .head()
)
```
Output:
```text
shape: (5, 3)
┌─────────┬──────────────┬────────────┐
│ species ┆ body mass kg ┆ bill ratio │
│ ---     ┆ ---          ┆ ---        │
│ str     ┆ f64          ┆ f64        │
╞═════════╪══════════════╪════════════╡
│ Adelie  ┆ 3.75         ┆ 2.090909   │
│ Adelie  ┆ 3.8          ┆ 2.270115   │
│ Adelie  ┆ 3.25         ┆ 2.238889   │
│ Adelie  ┆ null         ┆ null       │
│ Adelie  ┆ 3.45         ┆ 1.901554   │
└─────────┴──────────────┴────────────┘
```

Note: When loading specs from an external file (`@specs.txt`) or via the CLI (`-mutate`), names with spaces can be written directly on the left-hand side of `=` without dictionary unpacking:

```text
# inside an external spec file or CLI flag:
my bmi = [body mass g] / [bill length mm] ** 2
```

## Grouped mutations — `df.by(...).mutate(...)`

Unlike `pt.agg()` which collapses rows ($N \to K$), `df.by(...).mutate(...)` evaluates window calculations and group-level summaries and broadcasts them back to every row ($N \to N$).

Supported features:
- **Injected aggregation functions**: `mean(x)`, `sum(x)`, `median(x)`, `min(x)`, `max(x)`, `std(x)`, `var(x)`
- **Group row count**: `count()` (canonical window counting function)
- **Sequential expressions**: Later expressions within the same `mutate` call can immediately reference earlier group-derived columns (e.g. `diff = tip - avg_tip`)
- **Arbitrary output column names**: Name target columns cleanly without hardcoded prefixes
- **Multi-column grouping**: `.by('species', 'island')`
- **Spaced column names**: `[total bill]`
- **Missing group handling**: `dropna=False` retains NA groups

```python
# Compute group average tip, deviation from group average, and group sample size
tips = pt.sample("tips")
(
    tips
    .select("day", "time", "total_bill", "tip")
    .by("day")
    .mutate("avg_tip = mean(tip), diff = tip - avg_tip, group_size = count()")
    .head(6)
)
```
Output:
```text
shape: (6, 7)
┌─────┬────────┬────────────┬──────┬──────────┬───────────┬────────────┐
│ day ┆ time   ┆ total_bill ┆ tip  ┆ avg_tip  ┆ diff      ┆ group_size │
│ --- ┆ ---    ┆ ---        ┆ ---  ┆ ---      ┆ ---       ┆ ---        │
│ cat ┆ cat    ┆ f64        ┆ f64  ┆ f64      ┆ f64       ┆ u32        │
╞═════╪════════╪════════════╪══════╪══════════╪═══════════╪════════════╡
│ Sun ┆ Dinner ┆ 16.99      ┆ 1.01 ┆ 3.255132 ┆ -2.245132 ┆ 76         │
│ Sun ┆ Dinner ┆ 10.34      ┆ 1.66 ┆ 3.255132 ┆ -1.595132 ┆ 76         │
│ Sun ┆ Dinner ┆ 21.01      ┆ 3.5  ┆ 3.255132 ┆ 0.244868  ┆ 76         │
│ Sun ┆ Dinner ┆ 23.68      ┆ 3.31 ┆ 3.255132 ┆ 0.054868  ┆ 76         │
│ Sun ┆ Dinner ┆ 24.59      ┆ 3.61 ┆ 3.255132 ┆ 0.354868  ┆ 76         │
│ Sun ┆ Dinner ┆ 25.29      ┆ 4.71 ┆ 3.255132 ┆ 1.454868  ┆ 76         │
└─────┴────────┴────────────┴──────┴──────────┴───────────┴────────────┘
```

```python
# Multi-column grouping with spaced columns
(
    tips
    .rename(columns={"total_bill": "total bill"})
    .select("day", "time", "total bill", "tip")
    .by("day", "time")
    .mutate("[avg bill] = mean([total bill]), [bill diff] = [total bill] - [avg bill], count = count()")
    .head(6)
)
```
Output:
```text
shape: (6, 7)
┌─────┬────────┬────────────┬──────┬──────────┬───────────┬───────┐
│ day ┆ time   ┆ total bill ┆ tip  ┆ avg bill ┆ bill diff ┆ count │
│ --- ┆ ---    ┆ ---        ┆ ---  ┆ ---      ┆ ---       ┆ ---   │
│ cat ┆ cat    ┆ f64        ┆ f64  ┆ f64      ┆ f64       ┆ u32   │
╞═════╪════════╪════════════╪══════╪══════════╪═══════════╪═══════╡
│ Sun ┆ Dinner ┆ 16.99      ┆ 1.01 ┆ 21.41    ┆ -4.42     ┆ 76    │
│ Sun ┆ Dinner ┆ 10.34      ┆ 1.66 ┆ 21.41    ┆ -11.07    ┆ 76    │
│ Sun ┆ Dinner ┆ 21.01      ┆ 3.5  ┆ 21.41    ┆ -0.4      ┆ 76    │
│ Sun ┆ Dinner ┆ 23.68      ┆ 3.31 ┆ 21.41    ┆ 2.27      ┆ 76    │
│ Sun ┆ Dinner ┆ 24.59      ┆ 3.61 ┆ 21.41    ┆ 3.18      ┆ 76    │
│ Sun ┆ Dinner ┆ 25.29      ┆ 4.71 ┆ 21.41    ┆ 3.88      ┆ 76    │
└─────┴────────┴────────────┴──────┴──────────┴───────────┴───────┘
```

```python
# De-meaning and z-score calculation per group
(
    penguins
    .select("species", "body_mass_g")
    .by("species")
    .mutate(
        "mean_mass = mean(body_mass_g), std_mass = std(body_mass_g), z_score = (body_mass_g - mean_mass) / std_mass"
    )
    .head(6)
)
```
Output:
```text
shape: (6, 5)
┌─────────┬─────────────┬─────────────┬────────────┬───────────┐
│ species ┆ body_mass_g ┆ mean_mass   ┆ std_mass   ┆ z_score   │
│ ---     ┆ ---         ┆ ---         ┆ ---        ┆ ---       │
│ str     ┆ f64         ┆ f64         ┆ f64        ┆ f64       │
╞═════════╪═════════════╪═════════════╪════════════╪═══════════╡
│ Adelie  ┆ 3750.0      ┆ 3700.662252 ┆ 458.566126 ┆ 0.107591  │
│ Adelie  ┆ 3800.0      ┆ 3700.662252 ┆ 458.566126 ┆ 0.216627  │
│ Adelie  ┆ 3250.0      ┆ 3700.662252 ┆ 458.566126 ┆ -0.982764 │
│ Adelie  ┆ null        ┆ 3700.662252 ┆ 458.566126 ┆ null      │
│ Adelie  ┆ 3450.0      ┆ 3700.662252 ┆ 458.566126 ┆ -0.546622 │
│ Adelie  ┆ 3650.0      ┆ 3700.662252 ┆ 458.566126 ┆ -0.11048  │
└─────────┴─────────────┴─────────────┴────────────┴───────────┘
```

### Grouped vs. Overall Window Calculations (Single-Shot Grouping)

In Pytae, `.by()` establishes a single-shot, ephemeral grouping context consumed immediately by the next operation. Once `mutate()` finishes, the returned DataFrame is automatically flat and ungrouped! You can freely chain from a grouped mutation directly into an overall calculation without ever needing `ungroup()`.

```python
# Comparing species-level mean to overall dataset mean in a single pipeline
(
    penguins
    .select("species", "body_mass_g")
    .by("species")
    .mutate("species_mean = mean(body_mass_g)")
    .mutate("overall_mean = mean(body_mass_g)")
    .mutate("species_vs_overall = species_mean - overall_mean")
    .head(6)
)
```
Output:
```text
shape: (6, 5)
┌─────────┬─────────────┬──────────────┬──────────────┬────────────────────┐
│ species ┆ body_mass_g ┆ species_mean ┆ overall_mean ┆ species_vs_overall │
│ ---     ┆ ---         ┆ ---          ┆ ---          ┆ ---                │
│ str     ┆ f64         ┆ f64          ┆ f64          ┆ f64                │
╞═════════╪═════════════╪══════════════╪══════════════╪════════════════════╡
│ Adelie  ┆ 3750.0      ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
│ Adelie  ┆ 3800.0      ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
│ Adelie  ┆ 3250.0      ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
│ Adelie  ┆ null        ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
│ Adelie  ┆ 3450.0      ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
│ Adelie  ┆ 3650.0      ┆ 3700.662252  ┆ 4201.754386  ┆ -501.092134        │
└─────────┴─────────────┴──────────────┴──────────────┴────────────────────┘
```

### Handling missing grouping values with `dropna`

By default, `dropna=False` computes group statistics across `NA` rows as their own distinct group (no silent data loss). Pass `dropna=True` to exclude rows with `NA` in grouping columns from calculations, filling `NaN` in mutated columns while preserving total row count and index alignment:

```python
sample_data = pt.DataFrame({
    "grp": ["A", "A", None, "B", None],
    "val": [10.0, 20.0, 100.0, 30.0, 200.0]
})

# dropna=False (default): NA rows form a distinct group
print("dropna=False (default):")
print(
    sample_data
    .by("grp")
    .mutate("avg = mean(val), sz = count()", dropna=False)
)

# dropna=True: NA groups receive NaN
print("\ndropna=True:")
print(
    sample_data
    .by("grp")
    .mutate("avg = mean(val), sz = count()", dropna=True)
)
```
Output:
```text
dropna=False (default):
shape: (5, 4)
┌──────┬───────┬───────┬─────┐
│ grp  ┆ val   ┆ avg   ┆ sz  │
│ ---  ┆ ---   ┆ ---   ┆ --- │
│ str  ┆ f64   ┆ f64   ┆ u32 │
╞══════╪═══════╪═══════╪═════╡
│ A    ┆ 10.0  ┆ 15.0  ┆ 2   │
│ A    ┆ 20.0  ┆ 15.0  ┆ 2   │
│ null ┆ 100.0 ┆ 150.0 ┆ 2   │
│ B    ┆ 30.0  ┆ 30.0  ┆ 1   │
│ null ┆ 200.0 ┆ 150.0 ┆ 2   │
└──────┴───────┴───────┴─────┘

dropna=True:
shape: (5, 4)
┌──────┬───────┬──────┬──────┐
│ grp  ┆ val   ┆ avg  ┆ sz   │
│ ---  ┆ ---   ┆ ---  ┆ ---  │
│ str  ┆ f64   ┆ f64  ┆ u32  │
╞══════╪═══════╪══════╪══════╡
│ A    ┆ 10.0  ┆ 15.0 ┆ 2    │
│ A    ┆ 20.0  ┆ 15.0 ┆ 2    │
│ null ┆ 100.0 ┆ null ┆ null │
│ B    ┆ 30.0  ┆ 30.0 ┆ 1    │
│ null ┆ 200.0 ┆ null ┆ null │
└──────┴───────┴──────┴──────┘
```

## Comprehensive end-to-end recipe: combining all `mutate` capabilities

This master example combines all core features in a single fluent pipeline:
1. **Normal mutate**: Standard arithmetic derivation (`bill_ratio`, `mass_kg`).
2. **Sequential column referencing**: Using a freshly created column (`mass_kg`) inside subsequent expressions (`bmi`, `above_target`, `size_label`) within the *same* `mutate()` call.
3. **Binary conditional (`if_else`)**: Conditional branching into `'Heavy'` / `'Standard'`.
4. **Multi-condition tiers (`case_when`)**: Multi-tier categorization with ordered tuples and a fallback `default`.
5. **Null fallback (`coalesce`)**: Resolving the first non-null value across columns or supplying a fallback for missing data.
6. **Dictionary mapping (`map`)**: Category recoding through a dictionary lookup with fallback handling.
7. **Local variables (`@var`)**: Referencing caller-scope Python variables directly using the `@` prefix.
8. **Columns with spaces (`[col]`)**: Defining spaced columns via dict unpacking and referencing them with brackets `[mass lbs]`.
9. **Grouped window transforms (`pt.by()`)**: Computing group-level aggregations (`mean(mass_kg)`), relative offsets (`mass_diff`), and group sizes (`n`) without collapsing rows.
10. **Lambda callables**: Custom function inspecting the accumulated DataFrame with all prior mutations already attached.

```python
import numpy as np
import pytae as pt

penguins = pt.sample("penguins")

# 7. Local Python variable from caller scope (referenced with @ prefix)
target_threshold = 4.2

master_df = (
    penguins
    .by("species")
    .mutate(
        # 1. Normal mutate: standard arithmetic derivation
        bill_ratio="bill_length_mm / bill_depth_mm",
        mass_kg="body_mass_g / 1000",
        
        # 3. Referencing newly created col (mass_kg) in the same mutate call
        bmi="mass_kg / ((flipper_length_mm / 1000) ** 2)",
        
        # 7a. Local variable reference (@target_threshold) from caller scope
        above_target="mass_kg > @target_threshold",
        
        # 4. if_else: binary conditional logic
        size_label="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')",
        
        # 5. case_when: multi-condition tiered categorization
        weight_tier="case_when((mass_kg >= 5.0, 'XL'), (mass_kg >= 4.0, 'Large'), (mass_kg >= 3.0, 'Medium'), default='Small')",
        
        # 6. coalesce: prioritize sex, fall back to 'Undetermined' when null (row 3 has sex=NaN)
        effective_sex="coalesce(sex, 'Undetermined')",
        
        # 7b. map(): category dictionary lookup with default fallback
        species_code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE', 'Chinstrap': 'CH'}, 'OTHER')",
        
        # 7c. Spaced column creation via dict unpacking & bracket referencing
        **{"mass lbs": "mass_kg * 2.20462"},
        heavy_lbs="[mass lbs] > 9.5",
        
        # 9. Grouped window transforms via standalone pt.by() without collapsing rows
        species_avg_mass="mean(mass_kg)",
        mass_diff="mass_kg - species_avg_mass",
        group_size="count()",
        
        # 2. lambda: custom callable inspecting the accumulated DataFrame
        is_large=lambda df: (df["mass_kg"] > 4.0) & (df["bill_ratio"] > 2.5),
        # analysis='species', #if we don't use pt.lit, it will just assign value of speciec column
        # analysis='species2', #it will throw error because there is not 'species2 column'
        analysis="'species'", 
        
    )
)

cols_to_show = [
    "species", "species_code", "mass_kg", "species_avg_mass", "mass_diff",
    "group_size", "bmi", "size_label", "weight_tier", "effective_sex", 
    "above_target", "heavy_lbs", "is_large","analysis"
]
master_df[cols_to_show].head(8)
```
Output:
```text
shape: (8, 14)
┌─────────┬─────────────┬─────────┬─────────────┬───┬────────────┬───────────┬──────────┬──────────┐
│ species ┆ species_cod ┆ mass_kg ┆ species_avg ┆ … ┆ above_targ ┆ heavy_lbs ┆ is_large ┆ analysis │
│ ---     ┆ e           ┆ ---     ┆ _mass       ┆   ┆ et         ┆ ---       ┆ ---      ┆ ---      │
│ str     ┆ ---         ┆ f64     ┆ ---         ┆   ┆ ---        ┆ bool      ┆ bool     ┆ str      │
│         ┆ str         ┆         ┆ f64         ┆   ┆ bool       ┆           ┆          ┆          │
╞═════════╪═════════════╪═════════╪═════════════╪═══╪════════════╪═══════════╪══════════╪══════════╡
│ Adelie  ┆ AD          ┆ 3.75    ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 3.8     ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 3.25    ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ null    ┆ 3.700662    ┆ … ┆ null       ┆ null      ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 3.45    ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 3.65    ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 3.625   ┆ 3.700662    ┆ … ┆ false      ┆ false     ┆ false    ┆ species  │
│ Adelie  ┆ AD          ┆ 4.675   ┆ 3.700662    ┆ … ┆ true       ┆ true      ┆ false    ┆ species  │
└─────────┴─────────────┴─────────┴─────────────┴───┴────────────┴───────────┴──────────┴──────────┘
```

## Assigning Literal Constants with `quoted string literals (e.g. status="'active'")`
In `mutate()`, all string arguments are evaluated as **formulas and column expressions**, never as raw string literals:
- If you write `status="active"`, pytae searches for a column named `active`. Because no such column exists, it raises `KeyError: name 'active' is not defined`.
- Worse, if a column named `original` happens to exist, writing `source="original"` will silently copy that column instead of assigning the word `"original"`.

To assign a standalone literal constant value directly as a keyword argument without awkward nested quotes (`status="'active'"`), wrap it in `quoted string literals (e.g. status="'active'")`:
- `.mutate(status=pt.lit("active"), source=pt.lit("original"))`

> **When is `quoted string literals (e.g. status="'active'")` NOT needed?**
> 1. **Inside conditional helpers (`if_else`, `case_when`, `coalesce`)**: `quoted string literals (e.g. status="'active'")` is **completely irrelevant here**. Inside formula expressions, standard inner single quotes `'...'` already distinguish string literals from column references:
>    ```python
>    df.mutate(size="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')")
>    ```
> 2. **In the CLI**: `quoted string literals (e.g. status="'active'")` is **never needed in the CLI**. In terminal commands, standard inner single quotes are always used:
>    ```bash
>    pytae data.parquet -mutate "status = 'active'"
>    ```

```python
import pandas as pd
import pytae as pt

# Sample dataframe containing a column named 'original'
df = pt.DataFrame({'original': [100, 200], 'val': [1, 2]})

# 1. Unquoted string matching an existing column -> copies that column!
print("Copied column 'original':\n", df.mutate(source='original'))

# 2. With pt.lit(): assigns literal string constants cleanly and safely
print("\nWith pt.lit():\n", df.mutate(source="'original'", status="'active'"))
```
Output:
```text
Copied column 'original':
 shape: (2, 3)
┌──────────┬─────┬────────┐
│ original ┆ val ┆ source │
│ ---      ┆ --- ┆ ---    │
│ i64      ┆ i64 ┆ i64    │
╞══════════╪═════╪════════╡
│ 100      ┆ 1   ┆ 100    │
│ 200      ┆ 2   ┆ 200    │
└──────────┴─────┴────────┘

With pt.lit():
 shape: (2, 4)
┌──────────┬─────┬──────────┬────────┐
│ original ┆ val ┆ source   ┆ status │
│ ---      ┆ --- ┆ ---      ┆ ---    │
│ i64      ┆ i64 ┆ str      ┆ str    │
╞══════════╪═════╪══════════╪════════╡
│ 100      ┆ 1   ┆ original ┆ active │
│ 200      ┆ 2   ┆ original ┆ active │
└──────────┴─────┴──────────┴────────┘
```

## Conditional Branching: `if_else` & `case_when`

Pytae provides vectorized conditional branching directly inside formula strings:
- `if_else(condition, if_true, if_false)`: Binary branching. Supports literals or picking between columns!
- `case_when((cond1, val1), (cond2, val2), default)`: Multi-tier priority branching.

```python
# 1. Binary if_else returning literal categories
df_cond = penguins.mutate(size="if_else(body_mass_g > 4000, 'Heavy', 'Normal')")
df_cond.select("species", "body_mass_g", "size").head(5)
```
Output:
```text
shape: (5, 3)
┌─────────┬─────────────┬────────┐
│ species ┆ body_mass_g ┆ size   │
│ ---     ┆ ---         ┆ ---    │
│ str     ┆ f64         ┆ str    │
╞═════════╪═════════════╪════════╡
│ Adelie  ┆ 3750.0      ┆ Normal │
│ Adelie  ┆ 3800.0      ┆ Normal │
│ Adelie  ┆ 3250.0      ┆ Normal │
│ Adelie  ┆ null        ┆ Normal │
│ Adelie  ┆ 3450.0      ┆ Normal │
└─────────┴─────────────┴────────┘
```

```python
# 2. Dynamic column selection in if_else
# If island is 'Biscoe', select flipper_length_mm, otherwise bill_length_mm
df_col_select = penguins.mutate(metric="if_else(island == 'Biscoe', flipper_length_mm, bill_length_mm)")
df_col_select.select("species", "island", "flipper_length_mm", "bill_length_mm", "metric").head(5)
```
Output:
```text
shape: (5, 5)
┌─────────┬───────────┬───────────────────┬────────────────┬────────┐
│ species ┆ island    ┆ flipper_length_mm ┆ bill_length_mm ┆ metric │
│ ---     ┆ ---       ┆ ---               ┆ ---            ┆ ---    │
│ str     ┆ str       ┆ f64               ┆ f64            ┆ f64    │
╞═════════╪═══════════╪═══════════════════╪════════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 181.0             ┆ 39.1           ┆ 39.1   │
│ Adelie  ┆ Torgersen ┆ 186.0             ┆ 39.5           ┆ 39.5   │
│ Adelie  ┆ Torgersen ┆ 195.0             ┆ 40.3           ┆ 40.3   │
│ Adelie  ┆ Torgersen ┆ null              ┆ null           ┆ null   │
│ Adelie  ┆ Torgersen ┆ 193.0             ┆ 36.7           ┆ 36.7   │
└─────────┴───────────┴───────────────────┴────────────────┴────────┘
```

```python
# 3. Multi-tier branching with case_when
df_tier = penguins.mutate(
    tier="""
    case_when(
        (body_mass_g > 5000, 'Super-Heavy'),
        (body_mass_g > 3500, 'Medium'),
        'Light'
    )
    """
)
df_tier.select("species", "body_mass_g", "tier").head(6)
```
Output:
```text
shape: (6, 3)
┌─────────┬─────────────┬────────┐
│ species ┆ body_mass_g ┆ tier   │
│ ---     ┆ ---         ┆ ---    │
│ str     ┆ f64         ┆ str    │
╞═════════╪═════════════╪════════╡
│ Adelie  ┆ 3750.0      ┆ Medium │
│ Adelie  ┆ 3800.0      ┆ Medium │
│ Adelie  ┆ 3250.0      ┆ Light  │
│ Adelie  ┆ null        ┆ Light  │
│ Adelie  ┆ 3450.0      ┆ Light  │
│ Adelie  ┆ 3650.0      ┆ Medium │
└─────────┴─────────────┴────────┘
```

## Referencing External Python Variables (`@var`)

Prefix local Python variables with `@` to inject them directly into formula expressions without f-strings or manual escaping.
Unquoted identifiers without `@` always resolve to DataFrame column names, preventing silent shadowing bugs.

```python
cutoff = 4500.0
target_island = "Dream"

penguins.mutate(
    is_target_heavy="if_else(body_mass_g >= @cutoff and island == @target_island, 'Yes', 'No')"
).filter("is_target_heavy == 'Yes'").select("species", "island", "body_mass_g", "is_target_heavy").head(5)
```
Output:
```text
shape: (5, 4)
┌───────────┬────────┬─────────────┬─────────────────┐
│ species   ┆ island ┆ body_mass_g ┆ is_target_heavy │
│ ---       ┆ ---    ┆ ---         ┆ ---             │
│ str       ┆ str    ┆ f64         ┆ str             │
╞═══════════╪════════╪═════════════╪═════════════════╡
│ Adelie    ┆ Dream  ┆ 4650.0      ┆ Yes             │
│ Adelie    ┆ Dream  ┆ 4600.0      ┆ Yes             │
│ Chinstrap ┆ Dream  ┆ 4550.0      ┆ Yes             │
│ Chinstrap ┆ Dream  ┆ 4800.0      ┆ Yes             │
│ Chinstrap ┆ Dream  ┆ 4500.0      ┆ Yes             │
└───────────┴────────┴─────────────┴─────────────────┘
```

## Vectorized Value Recoding: `map(col, mapping[, fallback])`

Recode categorical values using dictionary lookups executed natively in the Polars engine with **Zero Data Loss by default**.

```python
# Two-argument: recodes mapped values, preserves unmapped rows intact
penguins.mutate(
    species_code="map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})"
).select("species", "species_code").distinct().head(5)
```
Output:
```text
shape: (3, 2)
┌───────────┬──────────────┐
│ species   ┆ species_code │
│ ---       ┆ ---          │
│ str       ┆ str          │
╞═══════════╪══════════════╡
│ Adelie    ┆ AD           │
│ Chinstrap ┆ Chinstrap    │
│ Gentoo    ┆ GEN          │
└───────────┴──────────────┘
```

```python
# Three-argument with literal fallback: unmapped rows become 'Other'
penguins.mutate(
    species_code="map(species, {'Adelie': 'AD'}, 'Other')"
).select("species", "species_code").distinct().head(5)
```
Output:
```text
shape: (3, 2)
┌───────────┬──────────────┐
│ species   ┆ species_code │
│ ---       ┆ ---          │
│ str       ┆ str          │
╞═══════════╪══════════════╡
│ Adelie    ┆ AD           │
│ Chinstrap ┆ Other        │
│ Gentoo    ┆ Other        │
└───────────┴──────────────┘
```

## Inline Type Casting: `int(_)`, `float(_)`, `str(_)`, `bool(_)`

Cast column types directly in formula expressions using standard Python constructors:

```python
# Cast year to int, mass to string
df_types = penguins.mutate(
    mass_str="str(body_mass_g)"
)
print("mass_str dtype:", df_types.schema["mass_str"])
```
Output:
```text
mass_str dtype: String
```

## Grouped Window Functions: `first`, `last`, `shift`, `cumsum`

Compute group-partitioned window metrics and baselines without collapsing table rows:

```python
# Compute species mean, deviation, and first/last group baselines
penguins.by("species").mutate(
    species_mean="mean(body_mass_g)",
    mass_dev="body_mass_g - mean(body_mass_g)",
    first_mass="first(body_mass_g)",
    last_mass="last(body_mass_g)"
).select("species", "body_mass_g", "species_mean", "mass_dev", "first_mass").head(6)
```
Output:
```text
shape: (6, 5)
┌─────────┬─────────────┬──────────────┬─────────────┬────────────┐
│ species ┆ body_mass_g ┆ species_mean ┆ mass_dev    ┆ first_mass │
│ ---     ┆ ---         ┆ ---          ┆ ---         ┆ ---        │
│ str     ┆ f64         ┆ f64          ┆ f64         ┆ f64        │
╞═════════╪═════════════╪══════════════╪═════════════╪════════════╡
│ Adelie  ┆ 3750.0      ┆ 3700.662252  ┆ 49.337748   ┆ 3750.0     │
│ Adelie  ┆ 3800.0      ┆ 3700.662252  ┆ 99.337748   ┆ 3750.0     │
│ Adelie  ┆ 3250.0      ┆ 3700.662252  ┆ -450.662252 ┆ 3750.0     │
│ Adelie  ┆ null        ┆ 3700.662252  ┆ null        ┆ 3750.0     │
│ Adelie  ┆ 3450.0      ┆ 3700.662252  ┆ -250.662252 ┆ 3750.0     │
│ Adelie  ┆ 3650.0      ┆ 3700.662252  ┆ -50.662252  ┆ 3750.0     │
└─────────┴─────────────┴──────────────┴─────────────┴────────────┘
```

## Dynamic Column Resolution via `col(@var)`

When writing dynamic functions or reusable pipeline steps, you can pass column names through local variables using `col(@var)` or `col('name')` rather than formatting strings:

```python
target_measure = "body_mass_g"
penguins.mutate(
    normalized_measure="col(@target_measure) / 1000.0"
).select("species", "body_mass_g", "normalized_measure").head(4)
```
Output:
```text
shape: (4, 3)
┌─────────┬─────────────┬────────────────────┐
│ species ┆ body_mass_g ┆ normalized_measure │
│ ---     ┆ ---         ┆ ---                │
│ str     ┆ f64         ┆ f64                │
╞═════════╪═════════════╪════════════════════╡
│ Adelie  ┆ 3750.0      ┆ 3.75               │
│ Adelie  ┆ 3800.0      ┆ 3.8                │
│ Adelie  ┆ 3250.0      ┆ 3.25               │
│ Adelie  ┆ null        ┆ null               │
└─────────┴─────────────┴────────────────────┘
```

## Boolean Safety in `map()` and Type Compatibility Guards

When mapping values to booleans, `map()` strictly preserves the boolean dtype (`pl.Boolean`), preventing silent string coercion into truthy `'false'` strings:

```python
df_credit = pt.DataFrame({"rating": ["2B", "3C", "4D"]})
res_bool = df_credit.mutate(
    is_investment_grade="map(rating, {'2B': True, '3C': False}, default=False)"
)
print(res_bool)
print(res_bool.dtypes)
```
Output:
```text
shape: (3, 2)
┌────────┬─────────────────────┐
│ rating ┆ is_investment_grade │
│ ---    ┆ ---                 │
│ str    ┆ bool                │
╞════════╪═════════════════════╡
│ 2B     ┆ true                │
│ 3C     ┆ false               │
│ 4D     ┆ false               │
└────────┴─────────────────────┘
[String, Boolean]
```

### Strict Type Guards Against Mixing Incompatible Types

Mixing booleans with strings or numeric types in `map()` raises an explicit `TypeError` rather than corrupting types:

```python
try:
    df_credit.mutate(out="map(rating, {'2B': 'Senior'}, default=False)")
except TypeError as e:
    print(e)
```
Output:
```text
map() cannot mix non-boolean mapping values with boolean default False. Polars requires homogeneous column dtypes; coercing booleans to strings would evaluate 'false' as truthy in Python.
```

## Unbracketed Column Names with Special Characters

Columns containing parentheses, hyphens, or special characters (common in regulatory reporting like IRBA/LGD) work seamlessly even without brackets:

```python
df_irba = pt.DataFrame({
    "irba_unsecured_lgd_(1g00)": [0.25, 0.45, 0.70],
    "post_crm_lgd_(2a)": [0.20, 0.50, 0.60],
})
df_irba.mutate(
    delta="irba_unsecured_lgd_(1g00) - post_crm_lgd_(2a)",
    is_high_risk="irba_unsecured_lgd_(1g00) > 0.40",
)
```
Output:
```text
shape: (3, 4)
┌───────────────────────────┬───────────────────┬───────┬──────────────┐
│ irba_unsecured_lgd_(1g00) ┆ post_crm_lgd_(2a) ┆ delta ┆ is_high_risk │
│ ---                       ┆ ---               ┆ ---   ┆ ---          │
│ f64                       ┆ f64               ┆ f64   ┆ bool         │
╞═══════════════════════════╪═══════════════════╪═══════╪══════════════╡
│ 0.25                      ┆ 0.2               ┆ 0.05  ┆ false        │
│ 0.45                      ┆ 0.5               ┆ -0.05 ┆ true         │
│ 0.7                       ┆ 0.6               ┆ 0.1   ┆ true         │
└───────────────────────────┴───────────────────┴───────┴──────────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/other_utilities.ipynb
################################################################################
# Notebook: other_utilities.ipynb

# `other_utilities` — Data Cleaning, Profiling & Helper Reference

Pytae provides a cohesive suite of data cleaning, profiling, inspection, and export utilities designed to complement core analytical verbs:

| Utility | Key Parameters | Primary Purpose |
|---|---|---|
| `.dropna()` | `*cols`, `subset=`, `how='all'|'any'`, `drop_nans=True` | Drops missing values with **Zero Data Loss by default** |
| `.fillna()` | `value`, `*cols`, `subset=`, `nans=True` | Imputes missing values (scalars, dicts, column-specific) |
| `.clean_columns()` | `strip=`, `strip_special=`, `squeeze=`, `fill=`, `case=`, `dedupe=` | Normalizes messy spreadsheet column headers |
| `.rename()` | `*args`, `columns=`, `**kwargs` | Renames columns via string specs (`old:new`), dicts, or kwargs |
| `.cols()` | `ascending=True|False|None` | Returns sorted or original file order column names |
| `.glimpse()` | `width=None` | Non-destructive transposed column overview |
| `.freq()` | `col`, `dropna=False` | In-terminal / notebook ASCII categorical frequency bars |
| `.hist()` | `col`, `bins=10` | In-terminal / notebook ASCII numeric distribution histogram |
| `.diff()` | `other`, `tol=0.0`, `rtol=0.0` | Detailed schema, shape, drift, and cell comparison report |
| `.to_clip()` | *(none)* | Copies clean TSV table directly to the system clipboard |

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
```

## 1. `dropna()` — Zero Data Loss by Default

In standard pandas, calling `.dropna()` without arguments defaults to `how='any'`, silently dropping every row that is missing even a single optional column.

**Pytae's Zero Data Loss Philosophy:**
- **Bare `.dropna()`**: Drops **only completely empty rows** (rows where all columns are null, `how='all'`).
- **Targeted columns**: Pass specific column names to drop rows where any of *those* columns are missing.
- **`drop_nans=True` (default)**: Drops both Arrow `null` and IEEE 754 float `NaN` (`float("nan")`). Pass `drop_nans=False` to drop only Arrow nulls.

```python
# Construct a dataset with partial nulls and a completely empty row
sample_df = pt.DataFrame({
    "species": ["Adelie", "Gentoo", None, None],
    "island": ["Dream", "Biscoe", "Torgersen", None],
    "body_mass_g": [3700.0, None, 4200.0, None],
})

# Bare dropna() drops ONLY the completely blank row (row 3); partial nulls are preserved!
sample_df.dropna()
```
Output:
```text
shape: (3, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Dream     ┆ 3700.0      │
│ Gentoo  ┆ Biscoe    ┆ null        │
│ null    ┆ Torgersen ┆ 4200.0      │
└─────────┴───────────┴─────────────┘
```

```python
# Drop rows where specific columns are missing (e.g. body_mass_g or sex)
penguins.dropna("body_mass_g", "sex").head(5)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 39.3           ┆ 20.6          ┆ 190.0             ┆ 3650.0      ┆ Male   │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Works with subset= or bracket notation for columns with spaces
penguins_spaced = penguins.rename(columns={"body_mass_g": "body mass g"})
penguins_spaced.dropna("[body mass g]", subset=["sex"]).head(5)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body mass g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 39.3           ┆ 20.6          ┆ 190.0             ┆ 3650.0      ┆ Male   │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# how='all' with columns: drops only when BOTH specified columns are missing
print("Original rows:", len(sample_df))
print("Drop when ANY of (species, body_mass_g) is null:", len(sample_df.dropna("species", "body_mass_g", how="any")))
print("Drop when BOTH of (species, body_mass_g) are null:", len(sample_df.dropna("species", "body_mass_g", how="all")))
```
Output:
```text
Original rows: 4
Drop when ANY of (species, body_mass_g) is null: 1
Drop when BOTH of (species, body_mass_g) are null: 3
```

```python
# dropna() chains seamlessly with other verbs and grouped operations
(
    penguins
    .by("species")
    .dropna("sex")
    .select("species", "island", "body_mass_g", "sex")
    .head(5)
)
```
Output:
```text
shape: (5, 4)
┌─────────┬───────────┬─────────────┬────────┐
│ species ┆ island    ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64         ┆ str    │
╞═════════╪═══════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3450.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 3650.0      ┆ Male   │
└─────────┴───────────┴─────────────┴────────┘
```

## 2. `fillna()` — Missing Value Imputation

`.fillna()` provides flexible missing value imputation:
- **Default `nans=True`**: Imputes both Arrow `null` and floating-point `NaN` values.
- **Type-safe scalar fill**: Automatically casts to compatible column dtypes (e.g. numeric 0 fills numeric columns without corrupting string columns).
- **Per-column dictionaries**: Target specific columns with tailored replacement values.
- **Column-specific scoping**: Fill specific columns via positional arguments or `subset=`.

```python
# Fill numeric columns with 0.0 (non-numeric columns remain untouched)
penguins.fillna(0.0).head(5)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 0.0            ┆ 0.0           ┆ 0.0               ┆ 0.0         ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Target specific columns with tailored replacement values
(
    penguins
    .fillna({
        "bill_length_mm": 0.0,
        "sex": "Unknown",
        "body_mass_g": 3000.0,
    })
    .head(5)
)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬─────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex     │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---     │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str     │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪═════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male    │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female  │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female  │
│ Adelie  ┆ Torgersen ┆ 0.0            ┆ null          ┆ null              ┆ 3000.0      ┆ Unknown │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female  │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴─────────┘
```

```python
# Target only specific columns using positional arguments or subset=
# Here, bill_length_mm is filled, while other null columns remain intact
penguins.fillna(0.0, "bill_length_mm").head(5)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 0.0            ┆ null          ┆ null              ┆ null        ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Demonstrate granular null vs NaN imputation using the nans= parameter
nan_df = pt.DataFrame({
    "val": [1.0, float("nan"), None, 4.0],
})

print("Original:\n", nan_df)
print("fillna(0.0, nans=False) -> fills null only, leaves float NaN intact:\n", nan_df.fillna(0.0, nans=False))
print("fillna(0.0, nans=True)  -> fills both null and float NaN (default):\n", nan_df.fillna(0.0, nans=True))
```
Output:
```text
Original:
 shape: (4, 1)
┌──────┐
│ val  │
│ ---  │
│ f64  │
╞══════╡
│ 1.0  │
│ NaN  │
│ null │
│ 4.0  │
└──────┘
fillna(0.0, nans=False) -> fills null only, leaves float NaN intact:
 shape: (4, 1)
┌─────┐
│ val │
│ --- │
│ f64 │
╞═════╡
│ 1.0 │
│ NaN │
│ 0.0 │
│ 4.0 │
└─────┘
fillna(0.0, nans=True)  -> fills both null and float NaN (default):
 shape: (4, 1)
┌─────┐
│ val │
│ --- │
│ f64 │
╞═════╡
│ 1.0 │
│ 0.0 │
│ 0.0 │
│ 4.0 │
└─────┘
```

## 3. `clean_columns()` — Header Normalization

Spreadsheets and external data sources frequently contain inconsistent header names: leading/trailing spaces, repeated spaces, mixed casing, and special characters (`#`, `$`, `%`, parentheses).

`clean_columns()` cleans header names in a deterministic order:
1. `strip`: Trims leading and trailing whitespace.
2. `strip_special`: Strips non-alphanumeric symbols (e.g. `(g)`, `$`, `%`, `#`, `!`) while preserving the fill separator.
3. `squeeze`: Collapses runs of internal whitespace into a single space.
4. `fill`: Replaces whitespace characters with a delimiter (e.g. `'_'`).
5. `case`: Normalizes casing (`'lower'`, `'upper'`, or `'proper'`).
6. `dedupe`: Disambiguates duplicate column names resulting from cleaning (e.g. `revenue`, `revenue_1`).

```python
# Create a realistic messy headers DataFrame
messy = pt.DataFrame({
    "  Species  ": ["Adelie"],
    "Island   Name": ["Torgersen"],
    "Body Mass (g)": [3750],
    "Bill Length [mm]": [39.1],
    "Bill Length [cm]": [3.91],
})

print("Before cleaning:", list(messy.columns))

# Clean headers into standard snake_case with deduplication
cleaned = messy.clean_columns(
    strip=True,
    strip_special=True,
    squeeze=True,
    fill="_",
    case="lower",
    dedupe=True,
)

print("After cleaning: ", list(cleaned.columns))
cleaned
```
Output:
```text
Before cleaning: ['  Species  ', 'Island   Name', 'Body Mass (g)', 'Bill Length [mm]', 'Bill Length [cm]']
After cleaning:  ['species', 'island_name', 'body_mass_g', 'bill_length_mm', 'bill_length_cm']
```
Output:
```text
shape: (1, 5)
┌─────────┬─────────────┬─────────────┬────────────────┬────────────────┐
│ species ┆ island_name ┆ body_mass_g ┆ bill_length_mm ┆ bill_length_cm │
│ ---     ┆ ---         ┆ ---         ┆ ---            ┆ ---            │
│ str     ┆ str         ┆ i64         ┆ f64            ┆ f64            │
╞═════════╪═════════════╪═════════════╪════════════════╪════════════════╡
│ Adelie  ┆ Torgersen   ┆ 3750        ┆ 39.1           ┆ 3.91           │
└─────────┴─────────────┴─────────────┴────────────────┴────────────────┘
```

```python
# Case options: 'lower', 'upper', or 'proper' (Title Case)
print("Lower: ", penguins.clean_columns(case="lower").cols(ascending=None)[:4])
print("Upper: ", penguins.clean_columns(case="upper").cols(ascending=None)[:4])
print("Proper:", penguins.clean_columns(case="proper").cols(ascending=None)[:4])

# Collision handling with dedupe=True:
colliding_df = pt.DataFrame({"Sales (Q1)": [10], "Sales (Q2)": [20]})
# Without dedupe=True, stripping special chars would cause collision ('sales' vs 'sales')
print("Deduped:", colliding_df.clean_columns(strip_special=True, case="lower", dedupe=True).columns)
```
Output:
```text
Lower:  ['species', 'island', 'bill_length_mm', 'bill_depth_mm']
Upper:  ['SPECIES', 'ISLAND', 'BILL_LENGTH_MM', 'BILL_DEPTH_MM']
Proper: ['Species', 'Island', 'Bill_Length_Mm', 'Bill_Depth_Mm']
Deduped: ['sales q1', 'sales q2']
```

## 4. `rename()` — Explicit Column Renaming

`rename()` provides multiple ergonomic calling styles:
- **String syntax**: Matches the CLI `-rename "old:new"` syntax.
- **Bracket notation**: Renames columns with spaces cleanly.
- **Keyword arguments**: `df.rename(old=new)`.
- **Dictionary mapping**: `df.rename({"old": "new"})` or `df.rename(columns={"old": "new"})`.

```python
# String specification (matches CLI -rename)
penguins.rename("species:penguin_species, island:habitat").head(3)
```
Output:
```text
shape: (3, 7)
┌───────────────┬───────────┬───────────────┬───────────────┬───────────────┬─────────────┬────────┐
│ penguin_speci ┆ habitat   ┆ bill_length_m ┆ bill_depth_mm ┆ flipper_lengt ┆ body_mass_g ┆ sex    │
│ es            ┆ ---       ┆ m             ┆ ---           ┆ h_mm          ┆ ---         ┆ ---    │
│ ---           ┆ str       ┆ ---           ┆ f64           ┆ ---           ┆ f64         ┆ str    │
│ str           ┆           ┆ f64           ┆               ┆ f64           ┆             ┆        │
╞═══════════════╪═══════════╪═══════════════╪═══════════════╪═══════════════╪═════════════╪════════╡
│ Adelie        ┆ Torgersen ┆ 39.1          ┆ 18.7          ┆ 181.0         ┆ 3750.0      ┆ Male   │
│ Adelie        ┆ Torgersen ┆ 39.5          ┆ 17.4          ┆ 186.0         ┆ 3800.0      ┆ Female │
│ Adelie        ┆ Torgersen ┆ 40.3          ┆ 18.0          ┆ 195.0         ┆ 3250.0      ┆ Female │
└───────────────┴───────────┴───────────────┴───────────────┴───────────────┴─────────────┴────────┘
```

```python
# Bracket notation for spaced columns
spaced_df = penguins.rename(columns={"bill_length_mm": "bill length mm", "body_mass_g": "body mass g"})

# Rename spaced columns to clean snake_case
spaced_df.rename("[bill length mm]:bill_len, [body mass g]:mass_g").head(3)
```
Output:
```text
shape: (3, 7)
┌─────────┬───────────┬──────────┬───────────────┬───────────────────┬────────┬────────┐
│ species ┆ island    ┆ bill_len ┆ bill_depth_mm ┆ flipper_length_mm ┆ mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---      ┆ ---           ┆ ---               ┆ ---    ┆ ---    │
│ str     ┆ str       ┆ f64      ┆ f64           ┆ f64               ┆ f64    ┆ str    │
╞═════════╪═══════════╪══════════╪═══════════════╪═══════════════════╪════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1     ┆ 18.7          ┆ 181.0             ┆ 3750.0 ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5     ┆ 17.4          ┆ 186.0             ┆ 3800.0 ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3     ┆ 18.0          ┆ 195.0             ┆ 3250.0 ┆ Female │
└─────────┴───────────┴──────────┴───────────────┴───────────────────┴────────┴────────┘
```

## 5. `cols()` — Column Discovery & Introspection

`cols()` returns a list of column names:
- **`ascending=True` (default)**: Alphabetical ascending order (convenient for wide datasets).
- **`ascending=False`**: Alphabetical descending order.
- **`ascending=None`**: Preserves original DataFrame / file order.

```python
print("Alphabetical ascending (default):\n", penguins.cols())
print("\nAlphabetical descending:\n", penguins.cols(ascending=False))
print("\nOriginal file / DataFrame order:\n", penguins.cols(ascending=None))
```
Output:
```text
Alphabetical ascending (default):
 ['bill_depth_mm', 'bill_length_mm', 'body_mass_g', 'flipper_length_mm', 'island', 'sex', 'species']

Alphabetical descending:
 ['species', 'sex', 'island', 'flipper_length_mm', 'body_mass_g', 'bill_length_mm', 'bill_depth_mm']

Original file / DataFrame order:
 ['species', 'island', 'bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g', 'sex']
```

## 6. `glimpse()` — Transposed Column Overview

Inspired by R/dplyr and Polars, `.glimpse()` prints a compact, transposed view:
- Summarizes row count, column count, and in-memory footprint.
- Lists every column name alongside its dtype and inline sample values.
- Non-destructive: returns `self` for easy mid-pipeline inspection.

```python
# Direct glimpse overview
penguins.glimpse()
```
Output:
```text
Rows: 344
Columns: 7
$ species           <String>  'Adelie', 'Adelie', 'Adelie', 'Adelie', 'Adelie...
$ island            <String>  'Torgersen', 'Torgersen', 'Torgersen', 'Torgers...
$ bill_length_mm    <Float64> 39.1, 39.5, 40.3, NA, 36.7, 39.3, 38.9, 39.2, 3...
$ bill_depth_mm     <Float64> 18.7, 17.4, 18.0, NA, 19.3, 20.6, 17.8, 19.6, 1...
$ flipper_length_mm <Float64> 181.0, 186.0, 195.0, NA, 193.0, 190.0, 181.0, 1...
$ body_mass_g       <Float64> 3750.0, 3800.0, 3250.0, NA, 3450.0, 3650.0, 362...
$ sex               <String>  'Male', 'Female', 'Female', NA, 'Female', 'Male...
```
Output:
```text
shape: (344, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
│ …       ┆ …         ┆ …              ┆ …             ┆ …                 ┆ …           ┆ …      │
│ Gentoo  ┆ Biscoe    ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
│ Gentoo  ┆ Biscoe    ┆ 46.8           ┆ 14.3          ┆ 215.0             ┆ 4850.0      ┆ Female │
│ Gentoo  ┆ Biscoe    ┆ 50.4           ┆ 15.7          ┆ 222.0             ┆ 5750.0      ┆ Male   │
│ Gentoo  ┆ Biscoe    ┆ 45.2           ┆ 14.8          ┆ 212.0             ┆ 5200.0      ┆ Female │
│ Gentoo  ┆ Biscoe    ┆ 49.9           ┆ 16.1          ┆ 213.0             ┆ 5400.0      ┆ Male   │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Non-destructive: glimpse mid-pipeline then continue chaining
(
    penguins
    .filter("body_mass_g > 4000")
    .glimpse()
    .select("species", "island", "body_mass_g")
    .head(3)
)
```
Output:
```text
Rows: 172
Columns: 7
$ species           <String>  'Adelie', 'Adelie', 'Adelie', 'Adelie', 'Adelie...
$ island            <String>  'Torgersen', 'Torgersen', 'Torgersen', 'Torgers...
$ bill_length_mm    <Float64> 39.2, 42.0, 34.6, 42.5, 46.0, 39.2, 39.8, 44.1...
$ bill_depth_mm     <Float64> 19.6, 20.2, 21.1, 20.7, 21.5, 21.1, 19.1, 19.7...
$ flipper_length_mm <Float64> 195.0, 190.0, 198.0, 197.0, 194.0, 196.0, 184.0...
$ body_mass_g       <Float64> 4675.0, 4250.0, 4400.0, 4500.0, 4200.0, 4150.0...
$ sex               <String>  'Male', NA, 'Male', 'Male', 'Male', 'Male', 'Ma...
```
Output:
```text
shape: (3, 3)
┌─────────┬───────────┬─────────────┐
│ species ┆ island    ┆ body_mass_g │
│ ---     ┆ ---       ┆ ---         │
│ str     ┆ str       ┆ f64         │
╞═════════╪═══════════╪═════════════╡
│ Adelie  ┆ Torgersen ┆ 4675.0      │
│ Adelie  ┆ Torgersen ┆ 4250.0      │
│ Adelie  ┆ Torgersen ┆ 4400.0      │
└─────────┴───────────┴─────────────┘
```

## 7. Visual Profiling in Notebooks: `freq()` & `hist()`

Pytae provides in-terminal and notebook ASCII distribution profiling:
- **`freq(col)`**: Computes frequency counts and rendered percentage bars for categorical columns.
- **`hist(col, bins=10)`**: Computes binned numeric distribution intervals with ASCII histogram bars.

```python
# Categorical frequency distribution with ASCII proportional bars
penguins.freq("species")
```
Output:
```text
shape: (3, 3)
┌───────────┬───────┬──────────────────────────────┐
│ species   ┆ Count ┆ Distribution                 │
│ ---       ┆ ---   ┆ ---                          │
│ str       ┆ i64   ┆ str                          │
╞═══════════╪═══════╪══════════════════════════════╡
│ Adelie    ┆ 152   ┆ ████████████████████ (44.2%) │
│ Gentoo    ┆ 124   ┆ ████████████████ (36.0%)     │
│ Chinstrap ┆ 68    ┆ █████████ (19.8%)            │
└───────────┴───────┴──────────────────────────────┘
```

```python
# Numeric distribution histogram with ASCII bars and percentages
penguins.hist("body_mass_g", bins=6)
```
Output:
```text
shape: (6, 3)
┌──────────────┬───────┬──────────────────────────────┐
│ Range        ┆ Count ┆ Distribution                 │
│ ---          ┆ ---   ┆ ---                          │
│ str          ┆ i64   ┆ str                          │
╞══════════════╪═══════╪══════════════════════════════╡
│ [2700, 3300] ┆ 34    ┆ ██████ (9.9%)                │
│ [3300, 3900] ┆ 110   ┆ ████████████████████ (32.2%) │
│ [3900, 4500] ┆ 80    ┆ ███████████████ (23.4%)      │
│ [4500, 5100] ┆ 60    ┆ ███████████ (17.5%)          │
│ [5100, 5700] ┆ 41    ┆ ███████ (12.0%)              │
│ [5700, 6300] ┆ 17    ┆ ███ (5.0%)                   │
└──────────────┴───────┴──────────────────────────────┘
```

## 8. `diff()` — Dataset & Schema Comparison

Compare two DataFrames or dataset files to detect schema drift, shape discrepancies, and cell value mismatches with optional floating-point tolerance (`tol=`, `rtol=`):

```python
df1 = penguins.head(5)
df2 = penguins.head(5).mutate("body_mass_g = body_mass_g + 0.005")

# Exact diff detects cell mismatches
print(df1.diff(df2))

# Comparison with floating-point tolerance tol=0.01 ignores sub-threshold drift
print(df1.diff(df2, tol=0.01))
```
Output:
```text
Comparing:
  Left (source):  <left> (5 rows, 7 cols)
  Right (target): <right> (5 rows, 7 cols)

Shape:
  Rows: 5 vs 5 (+0)
  Cols: 7 vs 7 (+0)

Columns:
  Common (7):        species, island, bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, sex

Schema Drift:
  None (all common columns have matching dtypes)

Values:
  Mismatches found in 4 cells across common columns:
    * body_mass_g: 4 cell(s) differ (max diff: 0.005)
Comparing:
  Left (source):  <left> (5 rows, 7 cols)
  Right (target): <right> (5 rows, 7 cols)

Shape:
  Rows: 5 vs 5 (+0)
  Cols: 7 vs 7 (+0)

Columns:
  Common (7):        species, island, bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, sex

Schema Drift:
  None (all common columns have matching dtypes)

Values:
  Tolerance: threshold/atol=0.01 (for numeric columns)
  Identical: all cell values match within tolerance.
```

## 9. `to_clip()` — Zero-Friction Clipboard Export

`df.to_clip()` copies the DataFrame to the system clipboard as tab-separated values (TSV) without index. You can immediately paste it (`Cmd+V` / `Ctrl+V`) into Excel, Google Sheets, or any spreadsheet editor.

```python
# Copy aggregated summary table to clipboard
(
    penguins
    .by("species")
    .agg(
        cnt="count",
        avg_mass="body_mass_g:mean",
        max_mass="body_mass_g:max",
    )
).to_clip()

print("Summary table copied to clipboard! Paste directly into Excel or Google Sheets.")
```
Output:
```text
Summary table copied to clipboard! Paste directly into Excel or Google Sheets.
```

## 10. `mask()` & `unmask()` — Sensitive Data Masking, Encryption & Tokenization

Protect sensitive PII columns across one-way irreversible and two-way reversible privacy pipelines:
- **One-Way Hashing**: Cryptographic SHA-256 (`hash` or `sha256`) with optional `salt`.
- **Redaction**: Replaces non-null values with asterisks (`***`).
- **Option 1 (Key Encryption)**: Authenticated HMAC-SHA256 CTR stream encryption (`encrypt`) and decryption (`unmask(..., key=...)`).
- **Option 2 (Tokenization with Vault)**: Consistent pseudonym tokenization (`tokenize`) maintaining relationships, join keys, and dtypes via a persistent vault (`vault="..."`).

```python
# Create sample sensitive data
customers = pt.DataFrame({
    "user_id": [101, 102, 103, 101],
    "email": ["alice@corp.com", "bob@corp.com", "carol@corp.com", "alice@corp.com"],
    "ssn": ["111-22-3333", "222-33-4444", "333-44-5555", "111-22-3333"],
    "notes": ["VIP member", "Standard tier", "New account", "Repeat order"],
})

# 1. One-way hash email with salt & redact notes
masked = customers.mask({"email": "hash", "notes": "redact"}, salt="audit_salt")
print("Masked:")
print(masked)

# 2. Reversible encryption with secret key
encrypted = customers.mask({"ssn": "encrypt"}, key="SecretPass123")
decrypted = encrypted.unmask(["ssn"], key="SecretPass123")
assert decrypted["ssn"].to_list() == customers["ssn"].to_list()
print("Decryption successful!")

# 3. Reversible tokenization with persistent vault
import tempfile
from pathlib import Path
vault_file = Path(tempfile.mkdtemp()) / "user_vault.parquet"
tokenized = customers.mask({"user_id": "tokenize"}, vault=vault_file)
print("Tokens:", tokenized["user_id"].to_list())
restored = tokenized.unmask(["user_id"], vault=vault_file)
assert restored["user_id"].to_list() == customers["user_id"].to_list()
print("De-tokenization restored original types & values!")
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/pivot.ipynb
################################################################################
# Notebook: pivot.ipynb

# `pt.pivot` / `df.pivot` — Excel-Style 2D Pivot Tables

`pt.pivot()` summarizes and aggregates tabular data across dimensions using the intuitive **RCVA** grammar:
- **`r`** (Rows): Row grouping dimensions (*optional*)
- **`c`** (Cols): Column header dimensions (*optional*)
- **`v`** (Values): Value / measure column(s) to aggregate (**required**)
- **`a`** (Aggregation): Aggregation function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`; default: `sum`)

### Core Guarantees:
1. **Always Flat 1D Output**: Never produces MultiIndex rows or tuples in column headers. Column names are joined with `_` (e.g. `Sales_2023`).
2. **Always Clean Reset Index**: Returns a standard `RangeIndex(0, 1, 2, ...)` every time.
3. **Automatic Subsetting**: Only references `r`, `c`, and `v`—no need to pre-select columns.
4. **No Silent Data Loss**: `dropna=False` by default, retaining missing categories.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")
flights = pt.sample("flights")
penguins.head()
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

## 1. Classic 2D Contingency Grid (`r=`, `c=`, `v=`)

Summarize average body mass across islands (rows) and species (columns):

```python
penguins.pivot(r="island", c="species", v="body_mass_g", a="mean")
```
Output:
```text
shape: (3, 4)
┌───────────┬─────────────┬─────────────┬────────────┐
│ island    ┆ Adelie      ┆ Chinstrap   ┆ Gentoo     │
│ ---       ┆ ---         ┆ ---         ┆ ---        │
│ str       ┆ f64         ┆ f64         ┆ f64        │
╞═══════════╪═════════════╪═════════════╪════════════╡
│ Biscoe    ┆ 3709.659091 ┆ null        ┆ 5076.01626 │
│ Dream     ┆ 3688.392857 ┆ 3733.088235 ┆ null       │
│ Torgersen ┆ 3706.372549 ┆ null        ┆ null       │
└───────────┴─────────────┴─────────────┴────────────┘
```

## 2. Frequency Matrix via Row Counts ()

Count occurrences across dimensions (the direct successor to cross-tabulation):

```python
penguins.pivot(r="island", c="species", a="count")
```
Output:
```text
shape: (3, 4)
┌───────────┬────────┬───────────┬────────┐
│ island    ┆ Adelie ┆ Chinstrap ┆ Gentoo │
│ ---       ┆ ---    ┆ ---       ┆ ---    │
│ str       ┆ i64    ┆ i64       ┆ i64    │
╞═══════════╪════════╪═══════════╪════════╡
│ Biscoe    ┆ 44     ┆ 0         ┆ 124    │
│ Dream     ┆ 56     ┆ 68        ┆ 0      │
│ Torgersen ┆ 52     ┆ 0         ┆ 0      │
└───────────┴────────┴───────────┴────────┘
```

## 3. Flexible Excel Layouts: Optional Rows or Columns

Just like dragging fields in Excel, `r` and `c` are completely optional.

```python
# Omit c: vertical summary table by row group
penguins.pivot(r="species", v="body_mass_g", a="mean")
```
Output:
```text
shape: (3, 2)
┌───────────┬─────────────┐
│ species   ┆ body_mass_g │
│ ---       ┆ ---         │
│ str       ┆ f64         │
╞═══════════╪═════════════╡
│ Adelie    ┆ 3700.662252 │
│ Chinstrap ┆ 3733.088235 │
│ Gentoo    ┆ 5076.01626  │
└───────────┴─────────────┘
```

```python
# Omit r: horizontal summary table across column headers
penguins.pivot(c="species", v="body_mass_g", a="mean")
```
Output:
```text
shape: (1, 3)
┌─────────────┬─────────────┬────────────┐
│ Adelie      ┆ Chinstrap   ┆ Gentoo     │
│ ---         ┆ ---         ┆ ---        │
│ f64         ┆ f64         ┆ f64        │
╞═════════════╪═════════════╪════════════╡
│ 3700.662252 ┆ 3733.088235 ┆ 5076.01626 │
└─────────────┴─────────────┴────────────┘
```

```python
# Omit both r and c: grand scalar aggregation across the dataset
penguins.pivot(v="body_mass_g", a="mean")
```
Output:
```text
shape: (1, 1)
┌─────────────┐
│ body_mass_g │
│ ---         │
│ f64         │
╞═════════════╡
│ 4201.754386 │
└─────────────┘
```

## 4. Multi-Level Dimensions & Multi-Metric Reporting

Pass a list of columns to `r`, `c`, or `v`:

```python
# Hierarchical rows + multiple metric values
penguins.pivot(
    r=["island", "sex"],
    c="species",
    v=["body_mass_g", "flipper_length_mm"],
    a="mean",
    f_v=0
)
```
Output:
```text
shape: (12, 8)
┌───────────┬────────┬────────────┬────────────┬────────────┬────────────┬────────────┬────────────┐
│ island    ┆ sex    ┆ body_mass_ ┆ body_mass_ ┆ body_mass_ ┆ flipper_le ┆ flipper_le ┆ flipper_le │
│ ---       ┆ ---    ┆ g_Adelie   ┆ g_Chinstra ┆ g_Gentoo   ┆ ngth_mm_Ad ┆ ngth_mm_Ch ┆ ngth_mm_Ge │
│ str       ┆ str    ┆ ---        ┆ p          ┆ ---        ┆ elie       ┆ instrap    ┆ ntoo       │
│           ┆        ┆ f64        ┆ ---        ┆ f64        ┆ ---        ┆ ---        ┆ ---        │
│           ┆        ┆            ┆ f64        ┆            ┆ f64        ┆ f64        ┆ f64        │
╞═══════════╪════════╪════════════╪════════════╪════════════╪════════════╪════════════╪════════════╡
│ Biscoe    ┆ null   ┆ null       ┆ null       ┆ null       ┆ 0.0        ┆ 0.0        ┆ 215.75     │
│ Biscoe    ┆ null   ┆ 0.0        ┆ 0.0        ┆ 4587.5     ┆ null       ┆ null       ┆ null       │
│ Biscoe    ┆ Female ┆ 3369.31818 ┆ 0.0        ┆ 4679.74137 ┆ 187.181818 ┆ 0.0        ┆ 212.706897 │
│           ┆        ┆ 2          ┆            ┆ 9          ┆            ┆            ┆            │
│ Biscoe    ┆ Male   ┆ 4050.0     ┆ 0.0        ┆ 5484.83606 ┆ 190.409091 ┆ 0.0        ┆ 221.540984 │
│           ┆        ┆            ┆            ┆ 6          ┆            ┆            ┆            │
│ Dream     ┆ null   ┆ null       ┆ null       ┆ null       ┆ 179.0      ┆ 0.0        ┆ 0.0        │
│ …         ┆ …      ┆ …          ┆ …          ┆ …          ┆ …          ┆ …          ┆ …          │
│ Dream     ┆ Male   ┆ 4045.53571 ┆ 3938.97058 ┆ 0.0        ┆ 191.928571 ┆ 199.911765 ┆ 0.0        │
│           ┆        ┆ 4          ┆ 8          ┆            ┆            ┆            ┆            │
│ Torgersen ┆ null   ┆ null       ┆ null       ┆ null       ┆ 187.25     ┆ 0.0        ┆ 0.0        │
│ Torgersen ┆ null   ┆ 3681.25    ┆ 0.0        ┆ 0.0        ┆ null       ┆ null       ┆ null       │
│ Torgersen ┆ Female ┆ 3395.83333 ┆ 0.0        ┆ 0.0        ┆ 188.291667 ┆ 0.0        ┆ 0.0        │
│           ┆        ┆ 3          ┆            ┆            ┆            ┆            ┆            │
│ Torgersen ┆ Male   ┆ 4034.78260 ┆ 0.0        ┆ 0.0        ┆ 194.913043 ┆ 0.0        ┆ 0.0        │
│           ┆        ┆ 9          ┆            ┆            ┆            ┆            ┆            │
└───────────┴────────┴────────────┴────────────┴────────────┴────────────┴────────────┴────────────┘
```

## 5. Seamless Method Chaining & Plotting

Because `pt.pivot` always returns a clean, rectangular DataFrame with a flat RangeIndex, you can immediately chain into further transformations or `.plot()`:

```python
piv = penguins.pivot(r="island", c="species", v="body_mass_g", a="mean", f_v=0)
# Clean flat columns and standard index ready for downstream manipulation:
print("Columns:", list(piv.columns))
print("Index:", list(piv.index))
piv
```
Output:
```text
Columns: ['island', 'Adelie', 'Chinstrap', 'Gentoo']
Index: [0, 1, 2]
```
Output:
```text
shape: (3, 4)
┌───────────┬─────────────┬─────────────┬────────────┐
│ island    ┆ Adelie      ┆ Chinstrap   ┆ Gentoo     │
│ ---       ┆ ---         ┆ ---         ┆ ---        │
│ str       ┆ f64         ┆ f64         ┆ f64        │
╞═══════════╪═════════════╪═════════════╪════════════╡
│ Biscoe    ┆ 3709.659091 ┆ 0.0         ┆ 5076.01626 │
│ Dream     ┆ 3688.392857 ┆ 3733.088235 ┆ 0.0        │
│ Torgersen ┆ 3706.372549 ┆ 0.0         ┆ 0.0        │
└───────────┴─────────────┴─────────────┴────────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/read_write.ipynb
################################################################################
# Notebook: read_write.ipynb

# Data Ingestion, Streaming & Sinks (`read_*`, `scan_*`, `write_*`)

`pytae` provides fast, dedicated readers and writers powered by Polars' multithreaded I/O core, complete with automatic compression handling, schema inference, and lazy query optimization.

- **Eager Readers**: `pt.read_parquet()`, `pt.read_csv()`, `pt.read_txt()`, `pt.read_jsonl()`, `pt.read_sas()`
- **Lazy Scanners**: `pt.scan_parquet()`, `pt.scan_csv()` for out-of-core streaming and query pushdowns
- **Writers**: `df.write_parquet()`, `df.write_csv()`, `df.write_jsonl()`
- **Sample Datasets**: Instant access to `penguins`, `diamonds`, `tips`, `flights`, `titanic` via `pt.sample()`

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt
import tempfile
from pathlib import Path
```

## 1. Built-in Sample Datasets (`pt.sample`)
Load sample datasets directly without downloading external files:

```python
penguins = pt.sample("penguins")
display(penguins.head(4))
print("Available sample datasets:", list(pt.sample_data.keys()))
```
Output:
```text
shape: (4, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```
Output:
```text
Available sample datasets: ['anagrams', 'anscombe', 'attention', 'brain_networks', 'car_crashes', 'diamonds', 'dots', 'dowjones', 'exercise', 'flights', 'fmri', 'geyser', 'glue', 'healthexp', 'iris', 'mpg', 'penguins', 'planets', 'seaice', 'taxis', 'tips', 'titanic']
```

## 2. Writing & Reading Parquet and CSV Files
Parquet provides columnar compression, fast reads, and preserved data types:

```python
with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)
    pq_file = tmp_path / "penguins.parquet"
    csv_file = tmp_path / "penguins.csv"
    
    # Write to Parquet and CSV
    penguins.write_parquet(pq_file)
    penguins.write_csv(csv_file)
    
    # Read back eagerly
    df_pq = pt.read_parquet(pq_file)
    df_csv = pt.read_csv(csv_file)
    
    print(f"Parquet shape: {df_pq.shape}, CSV shape: {df_csv.shape}")
    display(df_pq.head(3))
```
Output:
```text
Parquet shape: (344, 7), CSV shape: (344, 7)
```
Output:
```text
shape: (3, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

## 3. Lazy Scanning & Query Pushdowns (`pt.scan_parquet`)
`pt.scan_parquet()` returns a lazy DataFrame (`pl.LazyFrame`). Filters and column selections push down directly into the Parquet reader:
Rows that do not match the filter are skipped in row groups before ever touching RAM!

```python
with tempfile.TemporaryDirectory() as tmp_dir:
    pq_file = Path(tmp_dir) / "data.parquet"
    penguins.write_parquet(pq_file)
    
    # Scan lazily
    lazy_df = pt.scan_parquet(pq_file)
    print("Is lazy frame:", lazy_df.is_lazy)
    
    # Build query plan: filter & select
    query = (
        lazy_df
        .filter("body_mass_g > 4500 and island == 'Biscoe'")
        .select("species", "body_mass_g")
    )
    
    # Collect query results into eager DataFrame
    eager_res = query.collect()
    print("Collected shape:", eager_res.shape)
    display(eager_res.head(5))
```
Output:
```text
Is lazy frame: True
Collected shape: (109, 2)
```
Output:
```text
shape: (5, 2)
┌─────────┬─────────────┐
│ species ┆ body_mass_g │
│ ---     ┆ ---         │
│ str     ┆ f64         │
╞═════════╪═════════════╡
│ Adelie  ┆ 4725.0      │
│ Adelie  ┆ 4775.0      │
│ Adelie  ┆ 4600.0      │
│ Gentoo  ┆ 5700.0      │
│ Gentoo  ┆ 5700.0      │
└─────────┴─────────────┘
```

## 4. Clipboard Operations
Quickly copy and paste data directly between Python and spreadsheets:

```python
# df.to_clipboard() copies tab-delimited records to the OS clipboard
small_df = penguins.select("species", "body_mass_g").head(3)
# small_df.to_clipboard()  # Copies to OS clipboard
display(small_df)
```
Output:
```text
shape: (3, 2)
┌─────────┬─────────────┐
│ species ┆ body_mass_g │
│ ---     ┆ ---         │
│ str     ┆ f64         │
╞═════════╪═════════════╡
│ Adelie  ┆ 3750.0      │
│ Adelie  ┆ 3800.0      │
│ Adelie  ┆ 3250.0      │
└─────────┴─────────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/reshape.ipynb
################################################################################
# Notebook: reshape.ipynb

# `long` / `wide` — Pure 1-to-1 Reshaping

`long` melts numeric columns to rows. `wide` spreads a column's values into headers.

| Method | Key params | Purpose |
|---|---|---|
| `.long(c='variable', v='value', id_vars=None)` | `c`, `v`, `id_vars` | wide → long (melt) |
| `.wide(c='variable', v='value', r=None)` | `c`, `v`, `index` (or `r`) | long → wide (pure 1:1 unmelt) |

They are designed to work together as a **strictly complementary 1-to-1 reshaping pair**.

> **Note on Aggregation:**
> `wide()` is strictly for 1-to-1 structural reshaping without aggregation. If your data contains duplicate row/column keys and requires summarization (`mean`, `sum`, `count`/`n`), use [**`pt.pivot`**](pivot.ipynb).

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")
flights = pt.sample("flights")
healthexp = pt.sample("healthexp")

flights.head()
```
Output:
```text
shape: (5, 3)
┌──────┬───────┬────────────┐
│ year ┆ month ┆ passengers │
│ ---  ┆ ---   ┆ ---        │
│ i64  ┆ cat   ┆ i64        │
╞══════╪═══════╪════════════╡
│ 1949 ┆ Jan   ┆ 112        │
│ 1949 ┆ Feb   ┆ 118        │
│ 1949 ┆ Mar   ┆ 132        │
│ 1949 ┆ Apr   ┆ 129        │
│ 1949 ┆ May   ┆ 121        │
└──────┴───────┴────────────┘
```

## 1. `long` — Melt Columns to Rows

Melts all numeric columns to rows by default, preserving non-numeric columns as row identifiers:

```python
# Melt numeric columns into (variable, value) pairs
(
    penguins
    .select("species", "bill_length_mm", "bill_depth_mm")
    .long()
    .head()
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────────────┬───────┐
│ species ┆ variable       ┆ value │
│ ---     ┆ ---            ┆ ---   │
│ str     ┆ str            ┆ f64   │
╞═════════╪════════════════╪═══════╡
│ Adelie  ┆ bill_length_mm ┆ 39.1  │
│ Adelie  ┆ bill_length_mm ┆ 39.5  │
│ Adelie  ┆ bill_length_mm ┆ 40.3  │
│ Adelie  ┆ bill_length_mm ┆ null  │
│ Adelie  ┆ bill_length_mm ┆ 36.7  │
└─────────┴────────────────┴───────┘
```

```python
# Customize target column names for variable and value
(
    flights.long(c="metric", v="value")
    .head()
)
```
Output:
```text
shape: (5, 3)
┌───────┬────────┬───────┐
│ month ┆ metric ┆ value │
│ ---   ┆ ---    ┆ ---   │
│ cat   ┆ str    ┆ i64   │
╞═══════╪════════╪═══════╡
│ Jan   ┆ year   ┆ 1949  │
│ Feb   ┆ year   ┆ 1949  │
│ Mar   ┆ year   ┆ 1949  │
│ Apr   ┆ year   ┆ 1949  │
│ May   ┆ year   ┆ 1949  │
└───────┴────────┴───────┘
```

```python
# Explicit id_vars: specify which columns remain fixed
(
    healthexp.long(id_vars=["Year", "Country"], c="Metric", v="Amount")
    .head()
)
```
Output:
```text
shape: (5, 4)
┌──────┬───────────────┬──────────────┬─────────┐
│ Year ┆ Country       ┆ Metric       ┆ Amount  │
│ ---  ┆ ---           ┆ ---          ┆ ---     │
│ i64  ┆ str           ┆ str          ┆ f64     │
╞══════╪═══════════════╪══════════════╪═════════╡
│ 1970 ┆ Germany       ┆ Spending_USD ┆ 252.311 │
│ 1970 ┆ France        ┆ Spending_USD ┆ 192.143 │
│ 1970 ┆ Great Britain ┆ Spending_USD ┆ 123.993 │
│ 1970 ┆ Japan         ┆ Spending_USD ┆ 150.437 │
│ 1970 ┆ USA           ┆ Spending_USD ┆ 326.961 │
└──────┴───────────────┴──────────────┴─────────┘
```

## 2. `wide` — Pure 1-to-1 Unmelting

Pivots categorical values in column `c` into column headers, pulling cell values from `v`. Every `(index, c)` combination must be unique.

```python
# flights has exactly one row per year + month: perfect 1-to-1 unmelt
flights_wide = flights.wide(c="month", v="passengers")
flights_wide.head()
```
Output:
```text
shape: (5, 13)
┌──────┬─────┬─────┬─────┬───┬─────┬─────┬─────┬─────┐
│ year ┆ Apr ┆ Aug ┆ Dec ┆ … ┆ May ┆ Nov ┆ Oct ┆ Sep │
│ ---  ┆ --- ┆ --- ┆ --- ┆   ┆ --- ┆ --- ┆ --- ┆ --- │
│ i64  ┆ i64 ┆ i64 ┆ i64 ┆   ┆ i64 ┆ i64 ┆ i64 ┆ i64 │
╞══════╪═════╪═════╪═════╪═══╪═════╪═════╪═════╪═════╡
│ 1949 ┆ 129 ┆ 148 ┆ 118 ┆ … ┆ 121 ┆ 104 ┆ 119 ┆ 136 │
│ 1950 ┆ 135 ┆ 170 ┆ 140 ┆ … ┆ 125 ┆ 114 ┆ 133 ┆ 158 │
│ 1951 ┆ 163 ┆ 199 ┆ 166 ┆ … ┆ 172 ┆ 146 ┆ 162 ┆ 184 │
│ 1952 ┆ 181 ┆ 242 ┆ 194 ┆ … ┆ 183 ┆ 172 ┆ 191 ┆ 209 │
│ 1953 ┆ 235 ┆ 272 ┆ 201 ┆ … ┆ 229 ┆ 180 ┆ 211 ┆ 237 │
└──────┴─────┴─────┴─────┴───┴─────┴─────┴─────┴─────┘
```

```python
# Explicit index parameter (r= / index=)
demo_long = pt.DataFrame({
    "id": [1, 2, 3],
    "quarter": ["Q1", "Q2", "Q3"],
    "sales": [100, 200, 300]
})
demo_long.wide(r="id", c="quarter", v="sales")
```
Output:
```text
shape: (3, 4)
┌─────┬──────┬──────┬──────┐
│ id  ┆ Q1   ┆ Q2   ┆ Q3   │
│ --- ┆ ---  ┆ ---  ┆ ---  │
│ i64 ┆ i64  ┆ i64  ┆ i64  │
╞═════╪══════╪══════╪══════╡
│ 1   ┆ 100  ┆ null ┆ null │
│ 2   ┆ null ┆ 200  ┆ null │
│ 3   ┆ null ┆ null ┆ 300  │
└─────┴──────┴──────┴──────┘
```

## 3. Strict 1-to-1 Reshaping Guarantees

If your DataFrame contains duplicate index/column pairs, `wide()` refuses to silently aggregate and raises a clear error directing you to `pt.pivot()`:

```python
# penguins has multiple individuals per (island, species), so wide() halts:
try:
    penguins.wide(r="island", c="species", v="body_mass_g")
except ValueError as e:
    print("Error caught successfully:")
    print(e)
```
Output:
```text
Error caught successfully:
wide() encountered duplicate entries for row 'r' ['island'] and column 'species'. wide() is strictly for 1-to-1 reshaping without aggregation. Use pt.pivot() / -pivot to summarize or aggregate duplicate entries.
```

To summarize duplicate keys across dimensions, use [`pt.pivot`](pivot.ipynb) instead:

```python
# Proper aggregation with pt.pivot:
penguins.pivot(r="island", c="species", v="body_mass_g", a="mean")
```
Output:
```text
shape: (3, 4)
┌───────────┬─────────────┬─────────────┬────────────┐
│ island    ┆ Adelie      ┆ Chinstrap   ┆ Gentoo     │
│ ---       ┆ ---         ┆ ---         ┆ ---        │
│ str       ┆ f64         ┆ f64         ┆ f64        │
╞═══════════╪═════════════╪═════════════╪════════════╡
│ Biscoe    ┆ 3709.659091 ┆ null        ┆ 5076.01626 │
│ Dream     ┆ 3688.392857 ┆ 3733.088235 ┆ null       │
│ Torgersen ┆ 3706.372549 ┆ null        ┆ null       │
└───────────┴─────────────┴─────────────┴────────────┘
```

## 4. Round-Trip Reshaping (`long` ↔ `wide`)

Because `long` and `wide` are strict bijections, a DataFrame can be unpivoted to long format and seamlessly restored to its original structure:

```python
# Start with wide flights
wide_orig = flights.wide(c="month", v="passengers")

# 1. Melt to long
long_form = wide_orig.long(c="month", v="passengers", id_vars=["year"])

# 2. Reshape back to wide
wide_restored = long_form.wide(r="year", c="month", v="passengers")

# 3. Verify exact match (aligning column order)
pd.testing.assert_frame_equal(wide_orig[wide_restored.columns], wide_restored)
print("Round-trip verified: wide_orig matches wide_restored perfectly!")
wide_restored.head()
```
Output:
```text
Round-trip verified: wide_orig matches wide_restored perfectly!
```
Output:
```text
shape: (5, 13)
┌──────┬─────┬─────┬─────┬───┬─────┬─────┬─────┬─────┐
│ year ┆ Apr ┆ Aug ┆ Dec ┆ … ┆ May ┆ Nov ┆ Oct ┆ Sep │
│ ---  ┆ --- ┆ --- ┆ --- ┆   ┆ --- ┆ --- ┆ --- ┆ --- │
│ i64  ┆ i64 ┆ i64 ┆ i64 ┆   ┆ i64 ┆ i64 ┆ i64 ┆ i64 │
╞══════╪═════╪═════╪═════╪═══╪═════╪═════╪═════╪═════╡
│ 1949 ┆ 129 ┆ 148 ┆ 118 ┆ … ┆ 121 ┆ 104 ┆ 119 ┆ 136 │
│ 1950 ┆ 135 ┆ 170 ┆ 140 ┆ … ┆ 125 ┆ 114 ┆ 133 ┆ 158 │
│ 1951 ┆ 163 ┆ 199 ┆ 166 ┆ … ┆ 172 ┆ 146 ┆ 162 ┆ 184 │
│ 1952 ┆ 181 ┆ 242 ┆ 194 ┆ … ┆ 183 ┆ 172 ┆ 191 ┆ 209 │
│ 1953 ┆ 235 ┆ 272 ┆ 201 ┆ … ┆ 229 ┆ 180 ┆ 211 ┆ 237 │
└──────┴─────┴─────┴─────┴───┴─────┴─────┴─────┴─────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/select.ipynb
################################################################################
# Notebook: select.ipynb

# `select` — Reference

`select` picks columns by name, slice, dtype, or substring. Negative names (`'!col'`) and negative slices (`'!start:end'`) drop columns while preserving relative order. Regex is the `regex=` keyword — a positional string that is not an exact name is an error, not a silent regex. `everything()` pulls in "the rest" after pinning specific columns first.

| Argument type | Example | Selects |
|---|---|---|
| List | `['a','b']` | exact named columns |
| String (name) | `'species'` | exact column |
| Negative string | `'!species'`, `'!island'` | exclude named column |
| Negative slice | `'!bill_length_mm:body_mass_g'` | exclude contiguous range |
| String (slice) | `'bill_length_mm:body_mass_g'` | contiguous range |
| `everything()` | after explicit cols | remaining columns |
| callable | `lambda c: c.startswith('b')` | columns passing test |
| `regex=` | `regex='mm$'` | names matching regex |
| `dtype=` | `dtype='numeric'` | by dtype |
| `exclude_dtype=` | `exclude_dtype='number'` | excluding dtype |
| `contains=` | `contains='mm'` | substring in name |
| `startswith=` | `startswith='bill'` | name prefix |
| `endswith=` | `endswith='mm'` | name suffix |

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
titanic = pt.sample_data['titanic']
tips = pt.sample_data['tips']

penguins.cols(ascending=None)  # see column order
```
Output:
```text
['species',
 'island',
 'bill_length_mm',
 'bill_depth_mm',
 'flipper_length_mm',
 'body_mass_g',
 'sex']
```

## Names, `contains`, and `regex`
Criteria are a union (OR). Prefer `contains=` for substrings and `regex=` for patterns. Multiple values in a list are also OR.

```python
# All columns that contain 'bill' OR 'mass', plus species
(penguins
 .select('species', contains=['bill', 'mass'])
 .head()
)
```
Output:
```text
shape: (5, 4)
┌─────────┬────────────────┬───────────────┬─────────────┐
│ species ┆ bill_length_mm ┆ bill_depth_mm ┆ body_mass_g │
│ ---     ┆ ---            ┆ ---           ┆ ---         │
│ str     ┆ f64            ┆ f64           ┆ f64         │
╞═════════╪════════════════╪═══════════════╪═════════════╡
│ Adelie  ┆ 39.1           ┆ 18.7          ┆ 3750.0      │
│ Adelie  ┆ 39.5           ┆ 17.4          ┆ 3800.0      │
│ Adelie  ┆ 40.3           ┆ 18.0          ┆ 3250.0      │
│ Adelie  ┆ null           ┆ null          ┆ null        │
│ Adelie  ┆ 36.7           ┆ 19.3          ┆ 3450.0      │
└─────────┴────────────────┴───────────────┴─────────────┘
```

```python
# Column order rule: explicit list preserves YOUR order; contains/regex follow original DataFrame order
# island, sex, species are listed explicitly so they come first in that exact order,
# then contains='mm' adds remaining mm-cols in original df order
(penguins
 .select('island', 'sex', 'species', contains='mm')
 .head()
)
```
Output:
```text
shape: (5, 6)
┌───────────┬────────┬─────────┬────────────────┬───────────────┬───────────────────┐
│ island    ┆ sex    ┆ species ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm │
│ ---       ┆ ---    ┆ ---     ┆ ---            ┆ ---           ┆ ---               │
│ str       ┆ str    ┆ str     ┆ f64            ┆ f64           ┆ f64               │
╞═══════════╪════════╪═════════╪════════════════╪═══════════════╪═══════════════════╡
│ Torgersen ┆ Male   ┆ Adelie  ┆ 39.1           ┆ 18.7          ┆ 181.0             │
│ Torgersen ┆ Female ┆ Adelie  ┆ 39.5           ┆ 17.4          ┆ 186.0             │
│ Torgersen ┆ Female ┆ Adelie  ┆ 40.3           ┆ 18.0          ┆ 195.0             │
│ Torgersen ┆ null   ┆ Adelie  ┆ null           ┆ null          ┆ null              │
│ Torgersen ┆ Female ┆ Adelie  ┆ 36.7           ┆ 19.3          ┆ 193.0             │
└───────────┴────────┴─────────┴────────────────┴───────────────┴───────────────────┘
```

```python
# Columns ending in 'mm' — anchored regex
(penguins
 .select(regex='mm$')
 .head()
)
```
Output:
```text
shape: (5, 3)
┌────────────────┬───────────────┬───────────────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm │
│ ---            ┆ ---           ┆ ---               │
│ f64            ┆ f64           ┆ f64               │
╞════════════════╪═══════════════╪═══════════════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             │
│ 39.5           ┆ 17.4          ┆ 186.0             │
│ 40.3           ┆ 18.0          ┆ 195.0             │
│ null           ┆ null          ┆ null              │
│ 36.7           ┆ 19.3          ┆ 193.0             │
└────────────────┴───────────────┴───────────────────┘
```

```python
# Combining contains= with a slice in one call (union)
# contains='mm' picks the mm-cols; 'island:body_mass_g' slice picks everything between those two cols
(penguins
 .select('island:body_mass_g', contains='mm')
 .head()
)
```
Output:
```text
shape: (5, 5)
┌───────────┬────────────────┬───────────────┬───────────────────┬─────────────┐
│ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         │
│ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         │
╞═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╡
│ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      │
│ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      │
│ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      │
│ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        │
│ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      │
└───────────┴────────────────┴───────────────┴───────────────────┴─────────────┘
```

## Slice notation — contiguous column range
`'start_col:end_col'` selects all columns from start to end (inclusive), in DataFrame order.

```python
# Select from 'bill_length_mm' through 'body_mass_g' (all measurement cols)
(penguins
 .select('bill_length_mm:body_mass_g')
 .head()
)
```
Output:
```text
shape: (5, 4)
┌────────────────┬───────────────┬───────────────────┬─────────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---            ┆ ---           ┆ ---               ┆ ---         │
│ f64            ┆ f64           ┆ f64               ┆ f64         │
╞════════════════╪═══════════════╪═══════════════════╪═════════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      │
│ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      │
│ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      │
│ null           ┆ null          ┆ null              ┆ null        │
│ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      │
└────────────────┴───────────────┴───────────────────┴─────────────┘
```

```python
# Advanced regex: columns containing 'mm' but NOT 'flipper'
# this is regex for selecting all columns containing 'mm' but not 'flipper'.
# just because it can be done, does not mean it should be done.
# use more readable ways like list comprehension — this will ensure your co-workers
# don't stab you in the middle of the night
(penguins
 .select(regex=r'^(?=.*mm)(?!.*flipper).*')  # regex sorcery
 .head()
)

# More readable alternative:
cols_with_mm_not_flipper = [c for c in penguins.columns if 'mm' in c and 'flipper' not in c]
(
    penguins
    .select(cols_with_mm_not_flipper)
    .head()
)
```
Output:
```text
shape: (5, 2)
┌────────────────┬───────────────┐
│ bill_length_mm ┆ bill_depth_mm │
│ ---            ┆ ---           │
│ f64            ┆ f64           │
╞════════════════╪═══════════════╡
│ 39.1           ┆ 18.7          │
│ 39.5           ┆ 17.4          │
│ 40.3           ┆ 18.0          │
│ null           ┆ null          │
│ 36.7           ┆ 19.3          │
└────────────────┴───────────────┘
```

## `everything()` — pin key columns first, then the rest
Use `everything()` to move specific columns to the front without dropping any.

```python
# Move 'body_mass_g' and 'species' to front, keep all other columns after
(penguins
 .select('body_mass_g', 'species', pt.everything())
 .head()
)
```
Output:
```text
shape: (5, 7)
┌─────────────┬─────────┬───────────┬────────────────┬───────────────┬───────────────────┬────────┐
│ body_mass_g ┆ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ sex    │
│ ---         ┆ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---    │
│ f64         ┆ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ str    │
╞═════════════╪═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪════════╡
│ 3750.0      ┆ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ Male   │
│ 3800.0      ┆ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ Female │
│ 3250.0      ┆ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ Female │
│ null        ┆ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null   │
│ 3450.0      ┆ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ Female │
└─────────────┴─────────┴───────────┴────────────────┴───────────────┴───────────────────┴────────┘
```

## Callable — select columns with a function

```python
# Lambda: columns whose name has more than 6 characters
(penguins
 .select(lambda c: len(c) > 6)
 .head()
)
```
Output:
```text
shape: (5, 5)
┌─────────┬────────────────┬───────────────┬───────────────────┬─────────────┐
│ species ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---     ┆ ---            ┆ ---           ┆ ---               ┆ ---         │
│ str     ┆ f64            ┆ f64           ┆ f64               ┆ f64         │
╞═════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╡
│ Adelie  ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      │
│ Adelie  ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      │
│ Adelie  ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      │
│ Adelie  ┆ null           ┆ null          ┆ null              ┆ null        │
│ Adelie  ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      │
└─────────┴────────────────┴───────────────┴───────────────────┴─────────────┘
```

## `dtype`, `exclude_dtype`, `contains`, `startswith`, `endswith`, `regex`

```python
# All numeric columns only
(penguins
 .select(dtype='numeric')
 .head()
)
```
Output:
```text
shape: (5, 4)
┌────────────────┬───────────────┬───────────────────┬─────────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---            ┆ ---           ┆ ---               ┆ ---         │
│ f64            ┆ f64           ┆ f64               ┆ f64         │
╞════════════════╪═══════════════╪═══════════════════╪═════════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      │
│ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      │
│ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      │
│ null           ┆ null          ┆ null              ┆ null        │
│ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      │
└────────────────┴───────────────┴───────────────────┴─────────────┘
```

```python
# Drop numeric columns — keep only categorical/string columns
(penguins
 .select(exclude_dtype='number')
 .head()
)
```
Output:
```text
shape: (5, 3)
┌─────────┬───────────┬────────┐
│ species ┆ island    ┆ sex    │
│ ---     ┆ ---       ┆ ---    │
│ str     ┆ str       ┆ str    │
╞═════════╪═══════════╪════════╡
│ Adelie  ┆ Torgersen ┆ Male   │
│ Adelie  ┆ Torgersen ┆ Female │
│ Adelie  ┆ Torgersen ┆ Female │
│ Adelie  ┆ Torgersen ┆ null   │
│ Adelie  ┆ Torgersen ┆ Female │
└─────────┴───────────┴────────┘
```

```python
# exclude_dtype also accepts a list — exclude multiple dtype families at once
(penguins
 .select(exclude_dtype=['datetime', 'object'])
 .head()
)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Titanic: columns starting with 'p' or 'a', plus all numeric; behaviour here is | and not &
(titanic
 .select(startswith=['p', 'a'], dtype='numeric')
 .head()
)
```
Output:
```text
shape: (5, 9)
┌──────────┬────────┬──────┬───────┬───┬─────────┬────────────┬───────┬───────┐
│ survived ┆ pclass ┆ age  ┆ sibsp ┆ … ┆ fare    ┆ adult_male ┆ alive ┆ alone │
│ ---      ┆ ---    ┆ ---  ┆ ---   ┆   ┆ ---     ┆ ---        ┆ ---   ┆ ---   │
│ i64      ┆ i64    ┆ f64  ┆ i64   ┆   ┆ f64     ┆ bool       ┆ str   ┆ bool  │
╞══════════╪════════╪══════╪═══════╪═══╪═════════╪════════════╪═══════╪═══════╡
│ 0        ┆ 3      ┆ 22.0 ┆ 1     ┆ … ┆ 7.25    ┆ true       ┆ no    ┆ false │
│ 1        ┆ 1      ┆ 38.0 ┆ 1     ┆ … ┆ 71.2833 ┆ false      ┆ yes   ┆ false │
│ 1        ┆ 3      ┆ 26.0 ┆ 0     ┆ … ┆ 7.925   ┆ false      ┆ yes   ┆ true  │
│ 1        ┆ 1      ┆ 35.0 ┆ 1     ┆ … ┆ 53.1    ┆ false      ┆ yes   ┆ false │
│ 0        ┆ 3      ┆ 35.0 ┆ 0     ┆ … ┆ 8.05    ┆ true       ┆ no    ┆ true  │
└──────────┴────────┴──────┴───────┴───┴─────────┴────────────┴───────┴───────┘
```

```python
# endswith — select columns whose name ends with a given suffix
(penguins
 .select(endswith='mm')  # same result as .select(regex='mm$') but more readable
 .head()
)
```
Output:
```text
shape: (5, 3)
┌────────────────┬───────────────┬───────────────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm │
│ ---            ┆ ---           ┆ ---               │
│ f64            ┆ f64           ┆ f64               │
╞════════════════╪═══════════════╪═══════════════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             │
│ 39.5           ┆ 17.4          ┆ 186.0             │
│ 40.3           ┆ 18.0          ┆ 195.0             │
│ null           ┆ null          ┆ null              │
│ 36.7           ┆ 19.3          ┆ 193.0             │
└────────────────┴───────────────┴───────────────────┘
```

```python
# Columns containing 'bill' or 'flipper' in name, used in a full chain ;  behaviour here is | and not &
(
    penguins
    .filter("species in [\x27Adelie\x27, \x27Gentoo\x27]")
    .select('species', 'island', contains=['bill', 'flipper'])
    .by('species', 'island')
    .agg(a=['mean', 'count'])
)
```
Output:
```text
shape: (4, 6)
┌─────────┬───────────┬─────┬────────────────┬───────────────┬───────────────────┐
│ species ┆ island    ┆ n   ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm │
│ ---     ┆ ---       ┆ --- ┆ ---            ┆ ---           ┆ ---               │
│ str     ┆ str       ┆ i64 ┆ f64            ┆ f64           ┆ f64               │
╞═════════╪═══════════╪═════╪════════════════╪═══════════════╪═══════════════════╡
│ Adelie  ┆ Biscoe    ┆ 44  ┆ 38.975         ┆ 18.370455     ┆ 188.795455        │
│ Adelie  ┆ Dream     ┆ 56  ┆ 38.501786      ┆ 18.251786     ┆ 189.732143        │
│ Adelie  ┆ Torgersen ┆ 52  ┆ 38.95098       ┆ 18.429412     ┆ 191.196078        │
│ Gentoo  ┆ Biscoe    ┆ 124 ┆ 47.504878      ┆ 14.982114     ┆ 217.186992        │
└─────────┴───────────┴─────┴────────────────┴───────────────┴───────────────────┘
```

## Negative selection & exclusion — `!col`, negative slices

Drop or exclude columns by prefixing names with `!` (or `-` / `~`) or passing a negative slice (`'!start:end'`). Remaining columns preserve their original relative DataFrame order without needing a separate drop function.

```python
# Drop single column by negating with '!'
(
    penguins.select('!species')
    .head(3)
)
```
Output:
```text
shape: (3, 6)
┌───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
└───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Drop multiple columns
(
    penguins.select('!species', '!island', '!sex')
    .head(3)
)
```
Output:
```text
shape: (3, 4)
┌────────────────┬───────────────┬───────────────────┬─────────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---            ┆ ---           ┆ ---               ┆ ---         │
│ f64            ┆ f64           ┆ f64               ┆ f64         │
╞════════════════╪═══════════════╪═══════════════════╪═════════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      │
│ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      │
│ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      │
└────────────────┴───────────────┴───────────────────┴─────────────┘
```

```python
# Exclude a contiguous slice of columns
(
    penguins.select('!bill_length_mm:body_mass_g')
    .head(3)
)
```
Output:
```text
shape: (3, 3)
┌─────────┬───────────┬────────┐
│ species ┆ island    ┆ sex    │
│ ---     ┆ ---       ┆ ---    │
│ str     ┆ str       ┆ str    │
╞═════════╪═══════════╪════════╡
│ Adelie  ┆ Torgersen ┆ Male   │
│ Adelie  ┆ Torgersen ┆ Female │
│ Adelie  ┆ Torgersen ┆ Female │
└─────────┴───────────┴────────┘
```

```python
# Exclude multiple columns with positional negation
(
    penguins.select('!species', '!island')
    .head(3)
)
```
Output:
```text
shape: (3, 5)
┌────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
└────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

```python
# Combine positive selection with negative exclusion in a chain
(penguins
 .select(dtype='numeric')
 .select('!bill_depth_mm')
 .head(3)
)
```
Output:
```text
shape: (3, 3)
┌────────────────┬───────────────────┬─────────────┐
│ bill_length_mm ┆ flipper_length_mm ┆ body_mass_g │
│ ---            ┆ ---               ┆ ---         │
│ f64            ┆ f64               ┆ f64         │
╞════════════════╪═══════════════════╪═════════════╡
│ 39.1           ┆ 181.0             ┆ 3750.0      │
│ 39.5           ┆ 186.0             ┆ 3800.0      │
│ 40.3           ┆ 195.0             ┆ 3250.0      │
└────────────────┴───────────────────┴─────────────┘
```

## Columns with spaces — bracket notation `[col]`

Square brackets `[col name]` allow selecting and manipulating columns with spaces without quoting ambiguity, supporting individual names, comma lists, ranges, and exclusions:

```python
# Select columns with spaces using bracket notation
penguins_spaced = penguins.rename(columns={'bill_length_mm': 'bill length mm', 'body_mass_g': 'body mass g'})
(
    penguins_spaced.select('species', '[bill length mm]', '[body mass g]')
    .head()
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────────────┬─────────────┐
│ species ┆ bill length mm ┆ body mass g │
│ ---     ┆ ---            ┆ ---         │
│ str     ┆ f64            ┆ f64         │
╞═════════╪════════════════╪═════════════╡
│ Adelie  ┆ 39.1           ┆ 3750.0      │
│ Adelie  ┆ 39.5           ┆ 3800.0      │
│ Adelie  ┆ 40.3           ┆ 3250.0      │
│ Adelie  ┆ null           ┆ null        │
│ Adelie  ┆ 36.7           ┆ 3450.0      │
└─────────┴────────────────┴─────────────┘
```

```python
# Comma-separated string with bracketed space columns
(
    penguins_spaced.select('species, [bill length mm], [body mass g]')
    .head()
)
```
Output:
```text
shape: (5, 3)
┌─────────┬────────────────┬─────────────┐
│ species ┆ bill length mm ┆ body mass g │
│ ---     ┆ ---            ┆ ---         │
│ str     ┆ f64            ┆ f64         │
╞═════════╪════════════════╪═════════════╡
│ Adelie  ┆ 39.1           ┆ 3750.0      │
│ Adelie  ┆ 39.5           ┆ 3800.0      │
│ Adelie  ┆ 40.3           ┆ 3250.0      │
│ Adelie  ┆ null           ┆ null        │
│ Adelie  ┆ 36.7           ┆ 3450.0      │
└─────────┴────────────────┴─────────────┘
```

```python
# Drop a spaced column using negative bracket syntax ![col]
(
    penguins_spaced.select('species', '[bill length mm]', '![bill length mm]')
    .head()
)
```
Output:
```text
shape: (5, 1)
┌─────────┐
│ species │
│ ---     │
│ str     │
╞═════════╡
│ Adelie  │
│ Adelie  │
│ Adelie  │
│ Adelie  │
│ Adelie  │
└─────────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/library/sql.ipynb
################################################################################
# Notebook: sql.ipynb

# `sql` — Reference

Execute full ANSI SQL queries directly against DataFrames via Polars' native `SQLContext` engine. The current frame is registered as table **`data`** (and alias **`self`**). Zero external dependencies required—powered 100% by the built-in multithreaded Polars Rust engine.

| Call style | Meaning |
|---|---|
| `pt.sql(df, query)` | Function form; the passed frame is queryable as table `data` (or `self`) |
| `df.sql(query)` | Direct DataFrame method; seamlessly chains with other `pt` methods |
| `df.sql('@query.sql')` | Load and execute SQL query directly from an external `.sql` file |

The names `data` and `self` are reserved for the current frame.
Column names with spaces can use standard SQL double quotes (`"bill length mm"`), square brackets (`[bill length mm]`), or backticks (`` `bill length mm` ``).

---

```python
import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pandas as pd
import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
```

## Function form — current frame is table `data`

```python
# The passed DataFrame is registered as the table `data`
pt.sql(
    penguins,
    'select species, avg(body_mass_g) as avg_mass, count(*) as n '
    'from data group by species order by species'
)
```
Output:
```text
shape: (3, 3)
┌───────────┬─────────────┬─────┐
│ species   ┆ avg_mass    ┆ n   │
│ ---       ┆ ---         ┆ --- │
│ str       ┆ f64         ┆ i64 │
╞═══════════╪═════════════╪═════╡
│ Adelie    ┆ 3700.662252 ┆ 152 │
│ Chinstrap ┆ 3733.088235 ┆ 68  │
│ Gentoo    ┆ 5076.01626  ┆ 124 │
└───────────┴─────────────┴─────┘
```

## DataFrame Method — `df.sql(...)`

Same query engine, but chains naturally off any DataFrame.

```python
# `data` inside the query refers to the frame the accessor is called on
(
    penguins
    .sql("select * from data where species = 'Adelie'")
    .head()
)
```
Output:
```text
shape: (5, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ f64               ┆ f64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Adelie  ┆ Torgersen ┆ 39.1           ┆ 18.7          ┆ 181.0             ┆ 3750.0      ┆ Male   │
│ Adelie  ┆ Torgersen ┆ 39.5           ┆ 17.4          ┆ 186.0             ┆ 3800.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ 40.3           ┆ 18.0          ┆ 195.0             ┆ 3250.0      ┆ Female │
│ Adelie  ┆ Torgersen ┆ null           ┆ null          ┆ null              ┆ null        ┆ null   │
│ Adelie  ┆ Torgersen ┆ 36.7           ┆ 19.3          ┆ 193.0             ┆ 3450.0      ┆ Female │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘
```

## Spaced column names — double quotes, brackets `[col]`, or backticks

SQL standard uses double quotes for identifiers with spaces. `pytae` also accepts SQL-style square brackets `[col a]` and backticks (both automatically converted to standard SQL double quotes before querying):

```python
spaced = pt.DataFrame({'col a': [1, 20, 3], 'col b': ['x', 'y', 'z']})

# Double quotes, brackets, and backticks all work
pt.sql(spaced, 'select [col a], `col b` from data where [col a] > 2')
```
Output:
```text
shape: (2, 2)
┌───────┬───────┐
│ col a ┆ col b │
│ ---   ┆ ---   │
│ i64   ┆ str   │
╞═══════╪═══════╡
│ 20    ┆ y     │
│ 3     ┆ z     │
└───────┴───────┘
```

## Extra frames — joins across DataFrames

Pass additional DataFrames as keyword arguments; each becomes a table of that name.

## Chaining — mix SQL with pandas and other `pt` methods

```python
# SQL to aggregate, then a plain pandas method, then another pt accessor call
(
    tips
    .sql('select day, time, sum(total_bill) as bill, sum(tip) as tip from data group by day, time')
    .sort_values('bill', ascending=False)
    .mutate(tip_pct='tip / bill * 100')
)
```
Output:
```text
shape: (6, 5)
┌──────┬────────┬─────────┬────────┬───────────┐
│ day  ┆ time   ┆ bill    ┆ tip    ┆ tip_pct   │
│ ---  ┆ ---    ┆ ---     ┆ ---    ┆ ---       │
│ cat  ┆ cat    ┆ f64     ┆ f64    ┆ f64       │
╞══════╪════════╪═════════╪════════╪═══════════╡
│ Sat  ┆ Dinner ┆ 1778.4  ┆ 260.4  ┆ 14.642375 │
│ Sun  ┆ Dinner ┆ 1627.16 ┆ 247.39 ┆ 15.203791 │
│ Thur ┆ Lunch  ┆ 1077.55 ┆ 168.83 ┆ 15.66795  │
│ Fri  ┆ Dinner ┆ 235.96  ┆ 35.28  ┆ 14.951687 │
│ Fri  ┆ Lunch  ┆ 89.92   ┆ 16.68  ┆ 18.549822 │
│ Thur ┆ Dinner ┆ 18.78   ┆ 3.0    ┆ 15.974441 │
└──────┴────────┴─────────┴────────┴───────────┘
```

## Loading queries from an external file — `@query.txt`

Just like the CLI (`pytae data.parquet -sql @query.txt`), you can pass `@path.txt` to execute SQL queries directly from a file:

```python
with open('query_demo.txt', 'w') as f:
    f.write('select species, avg(body_mass_g) as avg_mass from data group by species order by avg_mass desc')

out = penguins.sql('@query_demo.txt')
if os.path.exists('query_demo.txt'):
    os.remove('query_demo.txt')
out
```
Output:
```text
shape: (3, 2)
┌───────────┬─────────────┐
│ species   ┆ avg_mass    │
│ ---       ┆ ---         │
│ str       ┆ f64         │
╞═══════════╪═════════════╡
│ Gentoo    ┆ 5076.01626  │
│ Chinstrap ┆ 3733.088235 │
│ Adelie    ┆ 3700.662252 │
└───────────┴─────────────┘
```

## Analytical SQL: Window Functions and Common Table Expressions (CTEs)

Polars SQLContext natively supports full analytical ANSI SQL features including window functions, partitioning, ranking, and common table expressions (CTEs):

```python
query = """
WITH ranked AS (
    SELECT species, island, body_mass_g,
           RANK() OVER (PARTITION BY species ORDER BY body_mass_g DESC) as rank
    FROM data
    WHERE body_mass_g IS NOT NULL
)
SELECT * FROM ranked WHERE rank <= 2
"""
penguins.sql(query)
```
Output:
```text
shape: (6, 4)
┌───────────┬────────┬─────────────┬──────┐
│ species   ┆ island ┆ body_mass_g ┆ rank │
│ ---       ┆ ---    ┆ ---         ┆ ---  │
│ str       ┆ str    ┆ f64         ┆ i64  │
╞═══════════╪════════╪═════════════╪══════╡
│ Adelie    ┆ Biscoe ┆ 4725.0      ┆ 2    │
│ Adelie    ┆ Biscoe ┆ 4775.0      ┆ 1    │
│ Chinstrap ┆ Dream  ┆ 4550.0      ┆ 2    │
│ Chinstrap ┆ Dream  ┆ 4800.0      ┆ 1    │
│ Gentoo    ┆ Biscoe ┆ 6300.0      ┆ 1    │
│ Gentoo    ┆ Biscoe ┆ 6050.0      ┆ 2    │
└───────────┴────────┴─────────────┴──────┘
```

################################################################################
# NOTEBOOK: docs/detailed_docs/plotting/plotting.ipynb
################################################################################
# Notebook: plotting.ipynb

# pytae Visualization with `Plotter` & `pt.plot`

`Plotter` is `pytae`'s method-chainable visualization engine built on top of Matplotlib and `pandas.plot()`. It eliminates visualization boilerplate by providing:
- **Single Subplot by Default**: Omit `mosaic` for single charts where `on=` is optional
- **Subplots Without Mosaic**: Use standard `nrows` and `ncols` (e.g. `pt.Plotter(df, nrows=1, ncols=2)`)
- **Direct Accessor & Functional Chaining**: `df.plot(...)` and `pt.plot(df, ...)`
- **Direct Pipeline Plotting**: Designed to work cleanly with `pt.agg()` and `pt.pivot()`, with built-in `palette=`
- **True Distribution Semantics**: Unaggregated `box` plots alongside `kde` and `hist`
- **Secondary Y-Axis Overlays**: Effortless dual axes via `on="A^"` syntax
- **Multi-Panel Mosaic Dashboards**: Arbitrary subplot grids using ASCII string diagrams
- **Automated Grid Faceting**: Small multiples via `pt.Plotter.facet(...)` with shared axis scales
- **Jupyter Auto-Display**: Direct inline rendering via `_repr_png_()` without requiring `p.fig`

```python
import numpy as np
import pandas as pd
import pytae as pt

# Pre-load sample datasets for all cells
tips = pt.sample("tips")
penguins = pt.sample("penguins")
diamonds = pt.sample("diamonds")
titanic = pt.sample("titanic")
```

## 1. Single Subplots & The Three Entry Points (Default: No Mosaic Needed)

When `mosaic` is omitted, `Plotter` automatically creates a **single subplot** (axis `"A"`), and specifying `on="A"` is completely optional.

`pytae` provides three interchangeable entry points depending on your workflow:
1. **DataFrame Method (`df.plot(...)` & `.finalize()`)**: Plugs directly into pandas / pytae transformation chains with fluent chaining throughout.
2. **Functional Style (`pt.plot(df, ...)` & `pt.finalize()`)**: Concise standalone functions for procedural workflows.
3. **Class Constructor (`pt.Plotter(df)`)**: Object-oriented single-subplot initialization with `.finalize()`.

```python
tips = pt.sample("tips")

# 1.1 DataFrame Accessor: single subplot without mosaic, chained directly from wrangling
(
    tips
    .filter("total_bill > 10")
    .by("day", "sex")
    .agg(total_bill="mean")
    .plot(
        kind="bar",
        x="day",
        y="total_bill",
        by="sex",
        palette="tab10",
        title="Average Bill by Day and Sex"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x110ecda90>
```

```python
penguins = pt.sample("penguins")

# 1.2 Functional Style: pt.plot(...) paired with pt.finalize()
p = pt.plot(
    penguins,
    kind="scatter",
    x="bill_length_mm",
    y="bill_depth_mm",
    by="species",
    palette="Set2",
    title="Penguin Bill Dimensions by Species"
)
pt.finalize(p)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bd25a90>
```

```python
# 1.3 Class Constructor: pt.Plotter(df) on a single subplot (no mosaic needed)
p = pt.Plotter(tips.by("day").agg(total_bill="mean"), figsize=(8, 4.5))
(
    p
    .plot(kind="line", x="day", y="total_bill", marker="o", color="crimson", title="Mean Bill Trend")
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bdff250>
```

## 2. Plot Kinds & Distribution Semantics

`pytae` supports a complete collection of plot kinds:
- **Aggregated / Categorical**: `bar`, `barh`, `line`, `pie`
- **Distributions**: `box` (unaggregated), `hist`, `kde` / `density`
- **Relationships**: `scatter`, `hexbin`
- **2D Matrices**: `heatmap`

```python
# 2.1 Grouped horizontal bar chart with custom aggregation
(
    tips
    .pivot(r="day", c="time", v="tip", a="mean")
    .plot(
        kind="barh",
        x="day",
        palette="tab10",
        title="Mean Tip by Day and Dining Time"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bd3eb10>
```

```python
# 2.2 Pre-aggregated pie chart with formatted percentages
(
    tips
    .by("day")
    .agg(total_bill="sum")
    .plot(
        kind="pie",
        y="total_bill",
        by="day",
        autopct="%1.1f%%",
        palette="Pastel1",
        title="Total Revenue Share by Day"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bd3e650>
```

```python
diamonds = pt.sample("diamonds").sample(1000, random_state=42)

# 2.3 Hexbin density plot for dense continuous distributions
(
    diamonds
    .plot(
        kind="hexbin",
        x="carat",
        y="price",
        gridsize=25,
        cmap="viridis",
        title="Diamond Carat vs Price (Hexbin Density)"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x10fd90710>
```

```python
# 2.4 Unaggregated Box Plot: shows real distribution quartiles across categories
(
    diamonds
    .plot(
        kind="box",
        x="cut",
        y="price",
        title="Diamond Price Distribution by Cut"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bb8f240>
```

```python
titanic = pt.sample("titanic")

# 2.5 Overlapping histograms split by group (accepts x= or column=)
(
    titanic
    .plot(
        kind="hist",
        x="age",
        by="alive",
        bins=25,
        alpha=0.6,
        palette="tab10",
        title="Age Distribution by Survival Status"
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x110e3b460>
```

```python
# 2.6 2D Heatmap: correlation matrix with numeric cell text annotations
corr = penguins.select_dtypes("number").corr()

pt.plot(
    corr,
    kind="heatmap",
    annot=True,
    fmt=".2f",
    cmap="coolwarm",
    title="Penguin Numeric Feature Correlation"
).finalize()
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf65450>
```

## 3. Subplots & Multi-Panel Dashboards (With & Without Mosaic)

You can build subplots in two ways:
1. **Without Mosaic**: Using familiar `nrows` and `ncols` (e.g. `pt.Plotter(df, nrows=1, ncols=2)`), automatically assigning panels `'A'`, `'B'`, etc.
2. **With Mosaic**: Using ASCII diagrams (`mosaic="""AB\nCD"""`) for arbitrary grid layouts.

Additionally, append `^` to an axis identifier (e.g. `on="A^"`) to overlay an independent secondary Y-axis sharing the same X-axis.

```python
# 3.1 Subplots WITHOUT Mosaic: use standard nrows and ncols
p_sub = pt.Plotter(nrows=1, ncols=2, figsize=(11, 4.5))
(
    p_sub
    .data(tips.by("day").agg(total_bill="mean"))
    .plot(on="A", kind="bar", x="day", y="total_bill", palette="tab10", title="Mean Bill by Day")
    .data(tips)
    .plot(on="B", kind="scatter", x="total_bill", y="tip", c="day", cmap="viridis", title="Bill vs Tip")
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf66350>
```

```python
# 3.2 Dual-axis overlay: average bill (bar) vs average tip (line on A^)
k = pt.Plotter(figsize=(9, 5))
(
    k
    .data(tips.by("day").agg(total_bill="mean"))
    .plot(on="A", kind="bar", x="day", y="total_bill", legend=False, title="Average Bill (Bars) vs Average Tip (Line)")
    .data(tips.by("day").agg(tip="mean"))
    .plot(on="A^", kind="line", x="day", y="tip", color="crimson", marker="o", linewidth=2.5)
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.15), ncols=2)
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf65050>
```

```python
# 3.3 Multi-Panel Mosaic Dashboard using ASCII layout
mosaic = """
AB
CD
"""

p = pt.Plotter(mosaic=mosaic, figsize=(14, 9))
(
    p
    .data(titanic.by("pclass").agg(survived="mean"))
    .plot(on="A", kind="bar", x="pclass", y="survived", palette="Set1", title="Survival Rate by Class")
    .data(titanic.by("sex").agg(survived="mean"))
    .plot(on="B", kind="bar", x="sex", y="survived", palette="tab10", title="Survival Rate by Sex")
    .data(titanic)
    .plot(on="C", kind="hist", x="age", by="alive", bins=20, alpha=0.6, palette="Set2", title="Age Distribution by Survival")
    .plot(on="D", kind="kde", x="fare", by="class", title="Fare Density by Class")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.05), ncols=4)
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf66950>
```

```python
# 3.4 Multi-Dataset Dashboard: mix different DataFrames across panels
mosaic_multi = """
AAB
AAC
"""

p_multi = pt.Plotter(mosaic=mosaic_multi, figsize=(13, 7))
(
    p_multi
    # Panel A: Penguins scatter
    .data(penguins)
    .plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="tab10", title="Penguin Bill Dimensions")
    # Panel B: Tips bar chart
    .data(tips.by("day").agg(total_bill="mean"))
    .plot(on="B", kind="bar", x="day", y="total_bill", color="#2a9d8f", title="Mean Bill by Day")
    # Panel C: Titanic survival rate
    .data(titanic.by("pclass").agg(survived="mean"))
    .plot(on="C", kind="bar", x="pclass", y="survived", color="#e76f51", title="Survival Rate by Class")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.05), ncols=3)
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11c7c0750>
```

## 4. Grid Faceting / Small Multiples (Auto-Faceting with `by` & `ncols`)

Split a dataset across an automated grid of subplots for each distinct level of a categorical column.

`pytae` automatically recognizes faceting whenever `by=` and `ncols=` are passed to **`pt.plot(...)`**, **`df.plot(...)`**, or **`pt.Plotter(...)`**—no need to remember a separate `pt.Plotter.facet` class method! (The explicit `pt.Plotter.facet` is still fully supported as an alias). Leftover grid cells are automatically kept clean.

```python
# 4.1 Auto-Faceting with pt.plot(by="species", ncols=3): automatic small multiples grid
pt.plot(
    penguins,
    by="species",
    ncols=3,
    x="bill_length_mm",
    y="bill_depth_mm",
    kind="scatter",
    sharex=True,
    sharey=True,
    figsize=(12, 4),
    title="Bill Dimensions by Species"
).finalize()
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf65650>
```

```python
# 4.2 Fluent Accessor Auto-Faceting: df.plot(by="cut", ncols=3)
(
    diamonds
    .plot(
        by="cut",
        ncols=2,
        x="price",
        kind="hist",
        bins=30,
        figsize=(12, 6),
        titles=True,
        sharex=True
    )
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bf66150>
```

## 5. End-to-End Pipelines: Mixing pandas, pytae, and Multi-Panel Mosaics

Because `pytae` methods return standard pandas DataFrames, you can freely mix standard pandas operations (`.dropna()`, `.rename()`, `.sort_values()`) with `pytae` verbs (`.mutate()`, `.filter()`, `.select()`) in a single chained pipeline that ends directly in a multi-panel mosaic dashboard.

```python
# 5.1 Continuous Accessor Chain: pandas + pytae + mosaic dashboard
wrangle_penguins = (
    penguins
    # 1. pandas: Drop missing measurements
    .dropna(subset=["bill_length_mm", "bill_depth_mm", "body_mass_g"])
    # 2. pytae: Feature engineering (compute ratio and scaled mass)
    .mutate(bill_ratio="bill_length_mm / bill_depth_mm", mass_kg="body_mass_g / 1000")
    # 3. pytae: Expressive filter
    .filter("mass_kg > 3.0")
    # 4. pandas: Sort observations
    .sort_values("body_mass_g", ascending=False)
)

(
    pt.Plotter(
        mosaic="""
        AB
        CD
        """,
        figsize=(13, 9)
    )
    .data(wrangle_penguins)
    .plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="Set1", title="Bill Dimensions")
    .plot(on="B", kind="box", x="species", y="body_mass_g", title="Body Mass Distribution")
    .data(wrangle_penguins.by("species").agg(bill_ratio="mean"))
    .plot(on="C", kind="bar", x="species", y="bill_ratio", palette="tab10", title="Mean Bill Ratio")
    .data(wrangle_penguins)
    .plot(on="D", kind="kde", x="body_mass_g", by="species", title="Body Mass Density")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.05), ncols=3)
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bad2350>
```

```python
# 5.2 Functional Style: wrangle with mixed verbs, then pass to pt.plot(mosaic=...)
cleaned_diamonds = (
    diamonds
    .rename(columns={"table": "table_pct"})
    .select("cut", "color", "price", "carat")
    .mutate(price_per_carat="price / carat")
    .filter("price_per_carat > 1500")
)

(
    pt.Plotter(
        mosaic="""
        AA
        BC
        """,
        figsize=(12, 8)
    )
    .data(cleaned_diamonds.by("cut", "color").agg(price_per_carat="mean"))
    .plot(on="A", kind="bar", x="cut", y="price_per_carat", by="color", palette="tab10", title="Mean Price/Carat by Cut & Color")
    .data(cleaned_diamonds)
    .plot(on="B", kind="box", x="cut", y="price_per_carat", title="Price/Carat Distribution")
    .plot(on="C", kind="scatter", x="carat", y="price", by="cut", palette="Set2", title="Carat vs Price")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.05), ncols=4)
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11bad1a50>
```

## 6. Advanced Controls & Customization (`_CONTROL_KWARGS`)

`pytae` provides dedicated control kwargs that drive `Plotter` behavior directly and are handled before delegating to Matplotlib:

| Control Kwarg | Type / Values | Purpose |
|---|---|---|
| `on` | `str` (`"A"`, `"B"`, `"A^"`) | Routes plot to a specific mosaic panel or secondary axis |
| `print_data` | `bool` | Prints the plotted DataFrame to stdout |
| `clip_data` | `bool` | Copies the plotted DataFrame to system clipboard |
| `secondary_y` | `bool` | Routes to secondary Y-axis (equivalent to `on="A^"`) |
| `xlabel` | `str` | Custom X-axis label override |
| `ylabel` | `str` | Custom Y-axis label override |
| `palette` | `str` (e.g. `"tab10"`, `"Set2"`) | Built-in colormap for discrete categories |
| `annot` | `bool` | Annotates heatmap cells with numeric values (see 2.6) |
| `fmt` | `str` (e.g. `".2f"`, `".1f"`) | Format string specifier for heatmap annotations (see 2.6) |

> **Design Principle:** In line with *"One and only one obvious way"*, `Plotter` does not perform implicit aggregation. Aggregate or summarize first using `df.agg(...)` or `df.pivot(...)` before plotting.

```python
# 6.1 Control Kwargs: print_data, clip_data, xlabel, and ylabel
p = (
    tips
    .by("day", "sex")
    .agg(total_bill="mean")
    .plot(
        kind="bar",
        x="day",
        y="total_bill",
        by="sex",
        palette="tab10",
        xlabel="Day of Week",
        ylabel="Average Total Bill ($)",
        title="Average Bill by Day and Sex",
        print_data=True,  # Prints the exact plotted DataFrame sent to Matplotlib
        clip_data=True    # Copies the plotted DataFrame to system clipboard for pasting
    )
    .finalize()
)

# You can also retrieve the plotted DataFrame anytime via p.get_data("A")
print("\nRetrieved via p.get_data('A'):")
print(p.get_data("A"))
```
Output:
```text
day     Female       Male
0   Fri  14.145556  19.857000
1   Sat  19.680357  20.802542
2   Sun  19.872222  21.887241
3  Thur  16.715312  18.714667

Retrieved via p.get_data('A'):
    day     Female       Male
0   Fri  14.145556  19.857000
1   Sat  19.680357  20.802542
2   Sun  19.872222  21.887241
3  Thur  16.715312  18.714667
```

```python
# 6.2 Control Kwarg: secondary_y=True for automatic secondary Y-axis routing
k = pt.Plotter(figsize=(9, 5))
(
    k
    .data(tips.by("day").agg(total_bill="mean"))
    .plot(on="A", kind="bar", x="day", y="total_bill", legend=False,
          xlabel="Day of Week", ylabel="Mean Total Bill ($)", title="Average Bill (Bars) vs Tip (Line)")
    .data(tips.by("day").agg(tip="mean"))
    .plot(kind="line", x="day", y="tip", secondary_y=True,
          color="crimson", marker="o", linewidth=2.5, ylabel="Mean Tip ($)")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.15), ncols=2)
)
k.fig
```
Output:
```text
<Figure size 900x500 with 2 Axes>
```

```python
# 6.3 Plotting Pre-Aggregated / Direct Data (No Extra Flags Needed)
pre_aggregated = pt.DataFrame({
    "quarter": ["Q1", "Q2", "Q3", "Q4"],
    "revenue": [120, 150, 180, 210]
})

(
    pre_aggregated
    .plot(kind="bar", x="quarter", y="revenue", color="#457b9d", title="Quarterly Revenue")
    .finalize()
)
```
Output:
```text
<pytae.plotting.Plotter at 0x11c7c0850>
```

```python
# 6.4 Direct Matplotlib Styling (axd, fig) and Figure Export
k = pt.Plotter(tips, figsize=(8, 4.5))
(
    k
    .plot(kind="scatter", x="total_bill", y="tip", c="total_bill", cmap="viridis", title="Tips vs Bill with Custom Annotation")
)

# Access raw Matplotlib Axes directly before finalization
k.axd["A"].axhline(3.0, color="red", linestyle="--", linewidth=1.5, label=r"Target Tip (\$3)")
k.axd["A"].grid(True, linestyle=":", alpha=0.5)

# Finalize the figure (export anytime via: k.save("chart.png", dpi=150))
k.finalize()
k.fig
```
Output:
```text
<Figure size 800x450 with 2 Axes>
```

```python
# 6.5 Post-Plot Manipulation: Iterating over Subplots in a for loop via p.axd
p = pt.Plotter(nrows=1, ncols=2, figsize=(11, 4.5))
(
    p
    .data(tips.by("day").agg(total_bill="mean"))
    .plot(on="A", kind="bar", x="day", y="total_bill", palette="tab10", title="Mean Bill by Day")
    .data(tips)
    .plot(on="B", kind="scatter", x="total_bill", y="tip", c="day", cmap="viridis", title="Bill vs Tip")
    .finalize()
)

# Loop over all subplots via p.axd for fine-grained Matplotlib controls
for key, ax in p.axd.items():
    # 1. Add subtle custom grid lines
    ax.grid(True, linestyle=":", alpha=0.6)
    # 2. Add panel badge to title
    ax.set_title(f"[{key}] {ax.get_title()}", fontsize=11, fontweight="bold", pad=8)
    # 3. Fine-tune tick label font sizes
    ax.tick_params(axis="both", labelsize=9)

# Specific override on panel B
p.axd["B"].axhline(3.0, color="crimson", linestyle="--", linewidth=1.2, label=r"Tip Ref (\$3)")
p.axd["B"].legend(loc="upper left", frameon=True, fontsize=8)

p.fig
```
Output:
```text
<Figure size 1100x450 with 3 Axes>
```

```python
# 6.6 Introspect which kwargs are unsupported vs pytae controls (_CONTROL_KWARGS)
for plot_kind in ["scatter", "bar", "box", "hist"]:
    info = pt.Plotter.supported_kwargs(plot_kind)
    print(f"kind='{plot_kind}': unsupported={info['unsupported']}, controls={info['pytae_controls']}")
```
Output:
```text
kind='scatter': unsupported=['dropna'], controls=['annot', 'clip_data', 'fmt', 'on', 'palette', 'print_data', 'secondary_y', 'xlabel', 'ylabel']
kind='bar': unsupported=[], controls=['annot', 'by', 'clip_data', 'dropna', 'fmt', 'on', 'palette', 'print_data', 'secondary_y', 'xlabel', 'y', 'ylabel']
kind='box': unsupported=['dropna'], controls=['annot', 'by', 'clip_data', 'column', 'fmt', 'on', 'palette', 'print_data', 'secondary_y', 'x', 'xlabel', 'y', 'ylabel']
kind='hist': unsupported=[], controls=['annot', 'by', 'clip_data', 'column', 'dropna', 'fmt', 'on', 'palette', 'print_data', 'secondary_y', 'x', 'xlabel', 'y', 'ylabel']
```

================================================================================
9. MASTER DOCUMENTATION & ARCHITECTURE GUIDE (docs/pytae.md)
================================================================================

################################################################################
# FILE: docs/pytae.md
################################################################################
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
│                           │ by, agg, distinct, head, tail, wide, long, pivot, join.     │
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
│ 5. ZERO DATA LOSS         │ Non-destructive safe defaults: bare dropna() drops only   │
│                           │ 100% blank rows; agg/pivot retain NA groups.               │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 6. SINGLE-SHOT GROUPING   │ df.by(*cols) scopes only the immediate next verb and auto- │
│                           │ ungroups. Sticky groups are eliminated; ungroup is dead.   │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 7. 100% POLARS SIMD CORE  │ Multithreaded Rust SIMD vector execution under the hood,   │
│                           │ bypassing Python GIL bottlenecks with zero overhead.      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Naming Rationale: Why `filter`, `distinct`, `by`, `arrange`, `agg`, `long`/`wide`?

Pytae carefully chooses concise, intention-revealing names that eliminate ambiguity, prevent keyword collisions, and adhere strictly to *"One and Only One Obvious Way"*:

### 1. `filter` instead of `query` or `qry`
- **Why `filter`?** `filter` is the canonical, intuitive verb across modern data science (R `dplyr`, SQL `FILTER`, Polars, Apache Spark). Calling it `filter` provides immediate familiarity and zero surprise.
- **Why not `df.query()`?** Pandas' native `df.query()` is string-only and passes expressions to `numexpr`, which chokes on Python functions and spaced columns. In contrast, `df.filter()` supports:
  - **Bare Callables & Lambdas**: `df.filter(lambda d: d['mass'] > 4000)` with full Python expressions and functions.
  - **Mathematical Intervals**: `df.filter(mass="[3000, 4500]")` or `df.filter(pct="(0, 100)")`.
  - **Set Membership & Operators**: lists `cat=['A', 'B']`, tuples `species=('startswith', ['Ad', 'Ge'])`.
  - **Bracketed Spaced Columns**: `df.filter("[bill length mm] > 40")` without ugly backtick escaping.
  - **Keyword & Dictionary Syntax**: `df.filter(status="active")` or `{"col": "> 5"}`.
- **CLI Alignment**: The CLI uses `-filter "expr"`. The legacy `-qry` has been deprecated in favor of canonical `-filter`.

### 2. `distinct` instead of `dedupe`, `unique`, or `drop_duplicates`
- **Why `distinct`?** `distinct` is the universally recognized keyword in SQL (`SELECT DISTINCT`) and dplyr (`distinct()`). It clearly describes returning unique, deduplicated rows.
- **Why not `unique`?** In Pandas, `.unique()` is a Series method returning a 1D NumPy array of scalar values, not a DataFrame. Using `unique` would conflate scalar distinct values with full-table row deduplication.
- **CLI Alignment**: The CLI uses `-distinct "species,island"`, with optional `keep=first|last|none` control.

### 3. `by` for Single-Shot Scoped Grouping (Why `ungroup` is Obsolete)
- **Why `by` over `groupby`?** In Pandas, `.groupby()` creates a lazy `DataFrameGroupBy` object that breaks standard DataFrame method chaining and forces multi-level index outputs upon aggregation.
- In R's `dplyr`, `group_by()` produces a sticky grouped data frame that persists across operations unless the user manually chains `%>% ungroup()`.
- **In Pytae, grouping is strictly single-shot and auto-clearing**:
  - `df.by(*cols)` sets an active grouping context for the *immediate next verb*.
  - `.mutate()` executes window calculations partitioned by group, consumes the grouping, and immediately returns a clean, ungrouped `DataFrame`.
  - `.head()` / `.tail()` slices rows (including extreme values after `.arrange()`) per group and returns an ungrouped `DataFrame`.
  - `.agg()` collapses per group and returns an ungrouped `DataFrame`.
  - Because grouping is never sticky, subsequent operations naturally evaluate at the whole-table scope without needing an `ungroup()` verb.
- **Fluent Re-Grouping**: You can seamlessly transition between group scopes and overall table scopes in one chain:
  ```python
  (
      df
      .by("region").mutate(reg_avg="mean(sales)")
      .mutate(overall_avg="mean(sales)")
      .by("product").mutate(prod_avg="mean(sales)")
  )
  ```
- **Strict `*args` Only**: `df.by("species", "island")` requires clean positional `*args`. Nested lists (`df.by(["species"])`) and `df.by(None)` are strictly rejected with clear error guidance.
- **Precedence**: If a second `.by()` is called before being consumed, it cleanly overwrites the previous grouping context.

### 4. `arrange` instead of `sort` or `sort_by`
- **Why not `sort`?** Python's built-in list has `.sort()`, and Pandas previously had `.sort()` (deprecated in favor of `.sort_values()`). In CLI flags, `-sort` is ambiguous (does it sort rows, columns, or files?).
- **Why not `sort_by`?** `arrange` is the canonical Tidyverse verb for row ordering. It cleanly conveys ordering rows without implying whether an index or values are being sorted. It supports explicit ascending/descending declarations (`col desc`), multi-column ordering, and bracketed column names `[col name] desc`. Prefixing columns with `-` is intentionally rejected to prevent ambiguity with hyphenated column names or negative numbers.

### 5. `agg` instead of `summarise` or `summarize`
- **Why not `summarise`?** In Python, `summarise` vs `summarize` introduces spelling ambiguity (British vs American English). Having both violates *"One and Only One Obvious Way"*.
- **Why `agg`?** `agg` is universally recognized in Pandas (`.agg()`). By elevating `agg` (`df.agg()` and CLI `-agg`), Pytae eliminates spelling confusion while providing declarative named aggregations (`avg_mass="body_mass_g:mean"`, `total="count"`).

### 6. `long` and `wide` instead of `melt`, `stack`, `unstack`, `pivot_wider`
- Pytae uses strictly complementary, intuitive English opposites:
  - **`long()`**: Turns wide tables into tall records using the unified `rcva` grammar (`r=` or `id_vars=`, `c=`, `v=`).
  - **`wide()`**: Pure 1-to-1 structural unmelting without aggregation (`r=`, `c=`, `v=`).
  - **`pivot()`**: 2D cross-tabulation aggregation matrices (`r=`, `c=`, `v=`, `a=`).
- All three verbs produce pure, flat 1D column headers with zero MultiIndex traps.

### 7. `count` for Fast Tallying & Intention-Revealing Aggregations
- **Why `count`?** Counting occurrences of categories or combinations of factors is the single most common exploratory data analysis operation. In Pandas, users are forced to choose between `.value_counts()` (which returns a 1D Series with index labels, breaking fluent chaining) or `.groupby('col').size().reset_index(name='n')`.
- **First-Class Verb**: Pytae introduces a dedicated `count()` verb across both Python (`df.count("species")`, `df.by("species").count()`) and the CLI (`-count species`, `-by species -count`).
- **Intuitive Defaults**: `count()` automatically sorts descending by count (`sort=True`) with output column `name="n"`. Pass `sort=False` to preserve original encounter order, or `name="total"` to rename the tally.
- **Natural Grammar in `agg()`**: Inside `agg()`, `count` (or `count()`) is the canonical counting function (`total_penguins="count"`, `avg_mass="body_mass_g:mean"`). In `avg_mass="body_mass_g:mean"`, `mean` is the function; therefore, `total_penguins="count"` makes `count` the consistent, intention-revealing function name, eliminating the awkward `n="n"` parameter tautology while preserving `"n"` as an alias for backward compatibility.

### 8. Visualization: "Compute in Polars, Visualize in Pandas"
- **Why Pandas for plotting?** Polars delivers unmatched multithreaded SIMD vector speed for data ingestion, filtering, and aggregation. However, the Pandas and Matplotlib ecosystem remains the most mature, flexible, and feature-rich visualization standard in Python.
- **Zero-Friction Bridge**: Calling `.plot()` automatically converts the prepared dataset to Pandas (`.to_pandas()`) and delegates directly to `pandas.DataFrame.plot`. Users get 100% compatibility with all standard plot kinds (`bar`, `barh`, `line`, `area`, `scatter`, `hexbin`, `heatmap`, `hist`, `box`, `kde`, `density`, `pie`), Matplotlib colormaps, secondary axes (`^`), and subplot mosaics without writing conversion boilerplate.
- **Clean Separation of Concerns**: Aggregation belongs in Polars (`.by().agg()`); visualization belongs in Pandas (`.plot()`). Pytae strictly prohibits implicit in-plot aggregation, keeping your pipelines predictable and high-performance.
- 👉 **Interactive Plotting Notebook**: [detailed_docs/plotting/plotting.ipynb](detailed_docs/plotting/plotting.ipynb)

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
        .agg(total_rev="sum(sales)", n="count")       -agg "total_rev = sum(sales), n = count"
        .arrange("total_rev desc")                    -arrange "total_rev desc"
                      │                                       │
                      ▼                                       ▼
              In-Memory Result                          Stdout / Export
           Clean, flat DataFrame                      Table view, -o lake/
```

---

## Lazy Evaluation & Background Execution: The High-Performance Engine

One of Pytae's most powerful capabilities is its native, transparent support for **Lazy Evaluation** backed by Polars' query optimizer and streaming execution engine.

In traditional tools like Pandas, operations are strictly eager: reading a 50 GB CSV or Parquet file attempts to allocate 150+ GB of memory upfront, frequently resulting in fatal out-of-memory (`OOM`) crashes. In Pytae, switching from eager exploration to out-of-core, high-throughput production data pipelines requires changing a single function call: `pt.read_*` $\rightarrow$ `pt.scan_*`.

```
               EAGER EXECUTION (pt.read_*)                 LAZY EXECUTION (pt.scan_*)
             ┌─────────────────────────────┐             ┌─────────────────────────────┐
             │   pt.read_parquet("file")   │             │   pt.scan_parquet("file")   │
             └──────────────┬──────────────┘             └──────────────┬──────────────┘
                            │ Reads entire file                         │ Builds unexecuted
                            ▼ into memory                               ▼ logical plan
             ┌─────────────────────────────┐             ┌─────────────────────────────┐
             │      pytae.DataFrame        │             │      pytae.DataFrame        │
             │   (in-memory pl.DataFrame)  │             │    (lazy pl.LazyFrame)      │
             └──────────────┬──────────────┘             └──────────────┬──────────────┘
                            │ Immediate execution                       │ Chained verbs build
                            ▼ per verb                                  ▼ query graph
             ┌─────────────────────────────┐             ┌─────────────────────────────┐
             │ .filter().mutate().agg()    │             │ .filter().mutate().agg()    │
             └──────────────┬──────────────┘             └──────────────┬──────────────┘
                            │                                           │
                            ▼                                           ▼ Rust Query Optimizer:
                     Eager In-Memory                             • Predicate Pushdown (filter)
                         Result                                  • Projection Pushdown (select)
                                                                 • Parallel Multithreaded SIMD
                                                                        │
                                                                        ▼
                                                         Automatic Background .collect()
                                                         or Explicit df.collect()
```

### 1. Eager vs. Lazy: Two Modes, One Identical Grammar

Every single verb in Pytae operates identically whether the underlying data is an eager `pl.DataFrame` or a lazy `pl.LazyFrame`:

```python
import pytae as pt

# 1. Eager: Immediately loads file into RAM
eager_df = pt.read_parquet("transactions.parquet")
print(eager_df.is_lazy)  # False

# 2. Lazy: Scans metadata only; zero rows loaded into RAM
lazy_df = pt.scan_parquet("transactions.parquet")
print(lazy_df.is_lazy)   # True

# Converting between modes
lazy_from_eager = eager_df.lazy()     # Convert eager -> lazy
eager_from_lazy = lazy_df.collect()   # Explicitly materialize lazy -> eager
```

### 2. The Optimizer: Predicate & Projection Pushdown

When running on a lazy DataFrame, Pytae defers execution until results are required. Polars' underlying Rust optimizer analyzes the entire computational graph and applies physical query optimizations:

1. **Predicate Pushdown (Filter Pushdown)**:
   - When you write `.filter("status == 'completed' & amount > 100")`, Pytae does not read all rows and filter in Python.
   - It pushes the filter criteria directly down into the file reader. For Parquet files, entire row groups are skipped at the disk level using Parquet block metadata and statistics, reading only matching rows into memory.
2. **Projection Pushdown (Column Selection)**:
   - When you write `.select("customer_id", "total_spend")`, Pytae reads **only those two columns** from storage. The remaining 50+ columns in the file are never touched, dramatically reducing disk I/O and memory bandwidth.
3. **Slice / Limit Pushdown**:
   - Calling `.head(10)` or `.arrange("sales desc").head(5)` avoids scanning the remainder of the file once the threshold is satisfied.

#### Inspecting the Execution Plan with `df.explain()`
You can inspect the exact physical and logical optimizations performed by Pytae using `.explain()`:

```python
plan = (
    pt.scan_parquet("sales.parquet")
    .filter("region == 'East' & sales > 500")
    .mutate(tax="sales * 0.08")
    .select("order_id", "sales", "tax")
    .explain()
)
print(plan)
```
```text
FAST_PROJECT: [order_id, sales, tax]
  SELECT [col("order_id"), col("sales"), col("sales") * 0.08 AS "tax"]
    FILTER: [(col("region") == "East") & (col("sales") > 500)]
      PARQUET SCAN sales.parquet
        PROJECT 2/18 COLUMNS: [order_id, sales, region]
        PREDICATE: [(col("region") == "East") & (col("sales") > 500)]
```

### 3. Automatic Background `collect()`: Zero-Friction Materialization

In many data frameworks (like Spark or pure Polars), forgetting to call `.collect()` leads to type mismatches, missing methods, or runtime crashes. **Pytae eliminates this friction with intelligent background collection**:

- **Direct-to-Disk Streaming Sinks**:
  - Calling `df.to_parquet("output.parquet")` or `df.to_csv("output.csv")` on a lazy DataFrame does not require an explicit `.collect()` call. Pytae triggers streaming execution directly into the output file, keeping memory usage constant even for terabyte-scale datasets.
- **Smart Shape & Count Queries**:
  - In Pandas, checking `len(df)` loads the entire table into memory.
  - In Pytae, calling `len(lazy_df)` or `lazy_df.shape` executes a lightweight `select(pl.len()).collect().item()` query in the background, returning row and column counts in milliseconds without loading data records into RAM.
- **Non-Destructive Inspection (`glimpse`, `freq`, `hist`)**:
  - Calling `lazy_df.glimpse()` automatically pushes a `.limit(25)` scan in the background, allowing you to preview schemas and sample rows of multi-gigabyte datasets without materializing them into memory.
- **CLI Streaming & Auto-TTY Collection**:
  - The `pytae` command-line tool automatically builds a lazy query plan across input flags (`-filter`, `-mutate`, `-by`, `-agg`, `-arrange`) and executes it in background Rust code right at the terminal output boundary.

---

## Ecosystem Comparisons & Migration Guides

Pytae was designed to synthesize the best strengths of the modern data engineering landscape while eliminating historical baggage, index traps, and syntax fragmentation.

### High-Level Ecosystem Comparison Matrix

| Capability / Paradigm | Pandas | dplyr (R) | SAS | Pytae |
|:---|:---|:---|:---|:---|
| **Core Philosophy** | Multiple competing ways per task | Functional pipelines (`%>%`, `\|>`) | Procedural `DATA` step + PROCs | **One and Only One Obvious Way** |
| **Execution Engine** | Single-threaded Python & NumPy | C++ (cpp11) / R interpreter | Procedural row-by-row PDV loop | **Multithreaded Rust SIMD (Polars)** |
| **Out-of-Core / Lazy Execution** | No native lazy engine (OOM on big files) | Limited (requires external `dbplyr`) | Sequential disk streaming | **Native `scan_*` with query pushdowns** |
| **Index Traps & MultiIndex** | Constant `.reset_index()` & nested tuples | Not applicable (R data frame) | Not applicable | **Pure flat 1D columns; zero MultiIndex** |
| **Grouping Scope** | Lazy `DataFrameGroupBy` object | "Sticky" `group_by()` (requires `ungroup`) | `BY` statement (requires prior `PROC SORT`) | **Single-shot `by()` (auto-clearing)** |
| **Missing Data Retention** | `dropna=True` *(Drops missing groups!)* | Preserves `NA` groups by default | Drops missing groups unless `MISSING` | **`dropna=False` by default (Zero Data Loss)** |
| **Row-Dropping Default** | Bare `dropna()` drops if *any* col is NA | `tidyr::drop_na()` requires explicit cols | Custom `IF` filter | **Bare `dropna()` drops only 100% blank rows** |
| **Missing Value Sorting** | Nulls sorted at end (or start) | NAs sorted at end | **Missing `.` sorted as $< -\infty$ *(Bug trap!)* ** | **Safe Polars sorting (`nulls_last`)** |
| **Relational Joins** | `pd.merge()` / `df.join()` | `left_join()`, `inner_join()` | `MERGE` *(Fatal abort if unsorted on disk!)* | **`df.join()` (Instant in-memory hash join)** |
| **Reshaping Model** | `melt()`, `pivot()`, `pivot_table()` | `pivot_longer()`, `pivot_wider()` | `PROC TRANSPOSE` (`_NAME_`, `COL1`) | **Symmetric `long()`, `wide()`, `pivot()`** |
| **CLI / Shell Parity** | None (requires writing `.py` script) | None (requires `Rscript -e '...'`) | Batch `sas -sysin` (produces `.log`/`.lst`) | **100% grammar parity (`pytae -verb`)** |

---

### Dedicated Deep Dive Guides

For exhaustive syntax mappings, feature-by-feature Rosetta stones, and migration walkthroughs, see the dedicated guides:

- **[Pytae vs. Pandas Deep Dive & Rosetta Stone](comparison_to_pandas.md)**:
  - Eliminating the `MultiIndex` nightmare and index management overhead.
  - Avoiding Pandas silent data loss traps (`dropna=True` in groupby).
  - Performance benchmarks: single-threaded Python GIL vs. native Polars Rust SIMD.
  - Complete 14-task syntax translation table and end-to-end pipeline comparison.

- **[Pytae vs. dplyr (R / Tidyverse) Deep Dive & Rosetta Stone](comparison_to_dplyr.md)**:
  - Bringing Tidyverse elegance to Python without Non-Standard Evaluation (NSE) quoting headaches.
  - Why `ungroup()` is obsolete: comparing dplyr's sticky grouping with Pytae's single-shot auto-clearing `df.by()`.
  - Multi-column transformations: `across()` vs. Pytae's concise `(a, b)_cm = _ * 10`.
  - Full Tidyverse-to-Pytae Rosetta stone and Unix CLI parity.

- **[Pytae vs. SAS Deep Dive & Migration Guide](comparison_to_sas.md)**:
  - Transitioning from the procedural Program Data Vector (PDV) to modern vectorized SIMD execution.
  - The dangerous SAS missing value trap (numeric `.` sorting below negative infinity).
  - Eliminating the mandatory pre-sorting requirement of SAS `MERGE ... BY ...`.
  - Clinical trial analysis walkthrough (SDTM `VSL` & `DM`) and native `.sas7bdat` file ingestion.

---

## Detailed Documentation Directory

All comprehensive guides, API signatures, CLI flags, walkthroughs, and edge cases are documented under **`docs/`**:
- **`docs/cli_cheatsheet.md`**: [**The Definitive CLI Cheat Sheet & Cookbook**](cli_cheatsheet.md) — 12 curated sections of one-liner recipes and Unix shell workflows.
- **`detailed_docs/cli/`**: Comprehensive Command Line Markdown guides (`.md`)
- **`detailed_docs/library/`**: Interactive, fully executed Jupyter Notebooks (`.ipynb`)

| Category | Python Library (Notebook) | CLI Guide (Markdown) | Key Capabilities & Verbs |
|:---|:---|:---|:---|
| **Data I/O** | **[read_write.ipynb](detailed_docs/library/read_write.ipynb)** | **[read_write.md](detailed_docs/cli/read_write.md)** | `pt.read_*`, `pt.scan_*`, `write_*`, `-o`, `-out_dir`, `-fmt`, `-progress`, STDIN, clipboard |
| **Derivations** | **[mutate.ipynb](detailed_docs/library/mutate.ipynb)** | **[mutate.md](detailed_docs/cli/mutate.md)** | `mutate`, formulas, sequential assignments, `if_else`, `case_when`, `map`, `shift`, `@var` |
| **Row Filtering** | **[filter.ipynb](detailed_docs/library/filter.ipynb)** | **[filter.md](detailed_docs/cli/filter.md)** | `filter`, `assert_` (data assertions), intervals `[10, 20]`, set membership `in`, `or`/`and`, string methods, callables |
| **Columns** | **[select.ipynb](detailed_docs/library/select.ipynb)** | **[select.md](detailed_docs/cli/select.md)** | `select`, drop with `!`, regex/patterns, inline rename, `pt.everything` |
| **Sorting** | **[arrange.ipynb](detailed_docs/library/arrange.ipynb)** | **[arrange.md](detailed_docs/cli/arrange.md)** | `arrange`, ascending, descending `col desc`, multi-column ordering, null positioning |
| **Aggregation** | **[agg.ipynb](detailed_docs/library/agg.ipynb)** | **[agg.md](detailed_docs/cli/agg.md)** | `by`, `agg`, `n`, `mean`, `sum`, `std`, `median`, `min`, `max`, `dropna=False` Zero Data Loss |
| **Cross-Tab** | **[pivot.ipynb](detailed_docs/library/pivot.ipynb)** | **[pivot.md](detailed_docs/cli/pivot.md)** | `pivot`, `r=`, `c=`, `v=`, `a=`, `f_v=`, flat 1D columns (no MultiIndex traps) |
| **Deduplication** | **[distinct.ipynb](detailed_docs/library/distinct.ipynb)** | **[distinct.md](detailed_docs/cli/distinct.md)** | `distinct`, whole-table deduplication, subset uniqueness, `keep='first'\|'last'\|'none'` |
| **Slicing** | **[head_tail.ipynb](detailed_docs/library/head_tail.ipynb)** | **[head_tail.md](detailed_docs/cli/head_tail.md)** | `arrange` + `head`/`tail`, group-aware with `by`, percentage `prop=`, ties `with_ties=` |
| **Reshaping** | **[reshape.ipynb](detailed_docs/library/reshape.ipynb)** | **[reshape.md](detailed_docs/cli/reshape.md)** | `long` (unpivoting), `wide` (1:1 pivoting), and `explode` (unnesting list/array columns) |
| **Relational Joins**| **[join.ipynb](detailed_docs/library/join.ipynb)** | **[join.md](detailed_docs/cli/join.md)** | `df.join`, `pt.join`, `pt.concat`, inner/left/right/full/semi/anti/cross, colon keys, `validate` |
| **Masking & Privacy**| **[other_utilities.ipynb](detailed_docs/library/other_utilities.ipynb)** | **[mask.md](detailed_docs/cli/mask.md)** | `mask`, `unmask`, `-mask`, `-unmask`, SHA-256 hash, salt, redact, key encryption, vault tokenization |
| **Interactive REPL**| — | **[repl.md](repl.md)** | `pytae -i`, `pytae <file> -i`, state history, `history -cli`, `history -py`, `undo`, `redo`, `reset`, `checkpoint`, `restore`, `rm *`, `clear` |
| **Utilities** | **[other_utilities.ipynb](detailed_docs/library/other_utilities.ipynb)** | **[clean_replace.md](detailed_docs/cli/clean_replace.md)**<br>**[diff.md](detailed_docs/cli/diff.md)** | `fillna`, `dropna`, `clean_columns`, `diff` (key-aware with `on=`, `tol=`), `glimpse`, `cols`, `to_clip` |
| **Inspection** | **[other_utilities.ipynb](detailed_docs/library/other_utilities.ipynb)** | **[inspect.md](detailed_docs/cli/inspect.md)** | `-cols`, `-dtype`, `-shape`, `-nulls`, `-head`, `-tail`, `-glimpse`, `-summary`, `-freq`, `-hist`, `-bar`, `-scatter`, `-corr` |
| **Multi-File** | **[join.ipynb](detailed_docs/library/join.ipynb)** | **[multi_file.md](detailed_docs/cli/multi_file.md)** | `-file` pipelines, multi-file globbing (`*.parquet`), multi-table joining, batch inputs, pipes, Unix redirection |
| **SQL Engine** | **[sql.ipynb](detailed_docs/library/sql.ipynb)** | **[sql.md](detailed_docs/cli/sql.md)** | `df.sql()`, `pt.sql()`, `-sql` native Polars SQL engine (SQLContext) on data and files |
| **Plotting** | **[plotting.ipynb](detailed_docs/plotting/plotting.ipynb)** | **[cli_plots.md](detailed_docs/cli/cli_plots.md)** | `df.plot()`, `-plot`, `-finalize`, terminal `-bar`, `-scatter`, `-corr`, headless figures |
| **Doc Search & MCP** | — | — | `pytae doc <query>`, `pt.doc()`, `pytae mcp` stdio JSON-RPC 2.0 server for Copilot/Cursor |
| **Comparisons** | **[vs. Pandas](comparison_to_pandas.md)**<br>**[vs. dplyr](comparison_to_dplyr.md)**<br>**[vs. SAS](comparison_to_sas.md)** | — | Pytae vs. Pandas vs. dplyr vs. SAS, naming rationale, "one and only one obvious way" |
| **Benchmarks** | **[benchmarks.ipynb](benchmarks/benchmarks.ipynb)** | **[run_benchmarks.py](benchmarks/run_benchmarks.py)**<br>**[README](benchmarks/README.md)** | Reproducible 5M-row speed benchmarks: Pytae vs. Pandas/dplyr/SAS, timings & plots |

---

## 30-Second Quickstart

### In Python:
```python
import pytae as pt

# Eager read or lazy scan
penguins = pt.read_parquet("penguins.parquet")

report = (
    penguins.filter("body_mass_g > 3500 & sex.is_not_null()")
    .mutate(
        body_mass_kg="body_mass_g / 1000",
        bill_ratio="bill_length_mm / bill_depth_mm",
        status="'verified'"
    )
    .by("species", "island")
    .agg(
        n="count",
        avg_mass_kg="body_mass_kg:mean",
        max_ratio="bill_ratio:max"
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
  -filter "body_mass_g > 3500 and sex.is_not_null()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm, status = 'verified'" \
  -by species,island \
  -agg "n = count, avg_mass_kg = body_mass_kg:mean, max_ratio = bill_ratio:max" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

================================================================================
CLI CHEATSHEET & COOKBOOK (docs/cli_cheatsheet.md)
================================================================================

################################################################################
# FILE: docs/cli_cheatsheet.md
################################################################################
# Pytae CLI Cheat Sheet & Cookbook

The definitive quick-reference guide and recipe cookbook for the `pytae` Unix command-line tool.

---

## 1. ⚡ Quick File Inspection & Metadata

Inspect Parquet, CSV, TSV, JSONL, and SAS7BDAT datasets with zero startup overhead:

```bash
# Print row and column dimensions (zero-cost on Parquet)
pytae data.parquet -shape

# Preview the first or last 5 rows (custom limit optional)
pytae data.parquet -head
pytae data.parquet -head 10
pytae data.parquet -tail 5

# View column names in file order, or sorted alphabetically
pytae data.parquet -cols
pytae data.parquet -cols asc

# View column data types
pytae data.parquet -dtype

# View null count and missingness per column
pytae data.parquet -nulls
pytae data.parquet -nulls desc

# Transposed overview of columns, dtypes, and sample values
pytae data.parquet -glimpse

# Statistical summary (count, mean, std, min, percentiles, max)
pytae data.parquet -describe

# Inspect low-level Parquet metadata (row groups, compression, statistics)
pytae data.parquet -meta

# Random sampling (reproducible with -seed)
pytae data.parquet -sample 10 -seed 42
pytae data.parquet -sample -frac 0.05
```

---

## 2. 🔍 Row Filtering & Slicing (`-filter`)

Filter rows cleanly using operator expressions, ranges, set membership, or column comparisons:

```bash
# Exact match (strict '==' enforced; string values must be quoted with single quotes inside double quotes)
pytae data.parquet -filter "species == 'Gentoo'"
pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30', '2026-08-31']"

# Numeric comparison operators (>, <, >=, <=, !=) and boolean logic (and, or, parens)
pytae data.parquet -filter "body_mass_g > 5000"
pytae data.parquet -filter "body_mass_g >= 3500 and flipper_length_mm < 210"
pytae data.parquet -filter "(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000"

# Column-to-column comparison (reconcile IDs, detect limit breaches)
pytae loans.parquet -filter "exposure > limit"
pytae loans.parquet -filter "tranche_id == deal_id"

# Ranges & Intervals (Option 1 native between or Option 2 multi-condition tuple dicts)
pytae data.parquet -filter "{'body_mass_g': ('between', 3000, 3500)}"
pytae data.parquet -filter "{'body_mass_g': (('>=', 3000), ('<=', 3500))}"
pytae data.parquet -filter "body_mass_g >= 3000 and body_mass_g <= 3500"

# List set membership (in, not in)
pytae data.parquet -filter "species in ['Adelie', 'Chinstrap']"
pytae data.parquet -filter "species not in ['Gentoo']"

# Null and NaN checks (universal 'is_null()' / 'is_nan()' in expressions and dicts)
pytae data.parquet -filter "sex.is_not_null()"
pytae data.parquet -filter "sex.is_null()"
pytae data.parquet -filter "{'sex': 'is_null()'}"
pytae data.parquet -filter "score.is_nan()"
pytae data.parquet -filter "score.is_not_nan()"
pytae data.parquet -filter "{score: is_nan()}"

# Columns with parentheses or spaces
pytae data.parquet -filter "counterparty_class_(irb) == 'Sovereigns'"
pytae data.parquet -filter "[counterparty class (irb)].is_not_null()"

# Inline assertions (validates all rows satisfy conditions; fails fast on violation)
pytae data.parquet -assert "body_mass_g > 0 and id.is_not_null()"
pytae orders.parquet -assert "order_id.is_not_null() and amount >= 0" -o valid.parquet

# Drop rows containing missing values
pytae data.parquet -dropna
pytae data.parquet -dropna "body_mass_g,sex"
```

---

## 3. 🛠 Feature Engineering & Mutation (`-mutate`)

Derive and overwrite columns using vectorized Polars SIMD expressions:

```bash
# Basic arithmetic formulas
pytae data.parquet -mutate "mass_kg = body_mass_g / 1000.0"

# Sequential assignments (later columns reference earlier ones)
pytae data.parquet -mutate "mass_kg = body_mass_g / 1000.0, mass_lbs = mass_kg * 2.20462"

# Conditional branching: if_else(condition, true_val, false_val)
pytae data.parquet -mutate "size = if_else(body_mass_g > 4000, 'Large', 'Small')"

# Multi-condition branching: case_when
pytae data.parquet -mutate "tier = case_when(body_mass_g > 5000, 'Heavy', body_mass_g > 3500, 'Medium', default='Light')"

# Categorical mapping & recoding: map(col, {dict}, default=...)
# (Strict boolean safety: mapping booleans preserves Boolean dtype)
pytae data.parquet -mutate "is_heavy = map(species, {'Gentoo': True}, default=False)"
pytae data.parquet -mutate "region = map(island, {'Biscoe': 'South', 'Dream': 'North'}, default='Other')"

# String functions: .str.lower(), .str.upper(), .str.slice(), .str.replace()
pytae data.parquet -mutate "species_lower = species.str.lower()"

# Unbracketed special-character columns (parentheses, hyphens)
pytae data.parquet -mutate "diff = irba_unsecured_lgd_(1g00) - post_crm_lgd_(2a)"

# Dynamic column referencing via col()
pytae data.parquet -mutate "target_copy = col('body_mass_g') * 1.5"
```

---

## 4. 🎯 Column Selection & Renaming (`-select`, `-rename`)

Select, reorder, and drop columns with flexible pattern matching:

```bash
# Explicit column selection and reordering
pytae data.parquet -select "species,island,body_mass_g"

# Drop columns using exclamation mark negation (!col)
pytae data.parquet -select "!sex,!year"

# Pattern and prefix matching
pytae data.parquet -select "startswith=bill_"
pytae data.parquet -select "endswith=_mm"
pytae data.parquet -select "contains=length"

# Select by data type
pytae data.parquet -select "dtype=float"
pytae data.parquet -select "exclude_dtype=string"

# Rename columns (old_name:new_name)
pytae data.parquet -rename "body_mass_g:weight_g,bill_length_mm:beak_len"

# Automated header cleaning (strip whitespace, snake_case, deduplicate)
pytae messy.csv -clean_columns "strip,fill=_,case=lower,dedupe"
```

---

## 5. 📊 In-Terminal Visualizations

Generate instant ASCII/Unicode charts directly in your terminal:

```bash
# Frequency table of a categorical column
pytae data.parquet -freq species

# In-terminal frequency bar chart
pytae data.parquet -freq species -bar

# In-terminal distribution histogram (custom bins optional)
pytae data.parquet -hist body_mass_g
pytae data.parquet -hist body_mass_g:20

# In-terminal scatter plot
pytae data.parquet -scatter "bill_length_mm,bill_depth_mm"

# Correlation matrix
pytae data.parquet -corr

# Generate publication-quality Matplotlib figures headlessly
pytae data.parquet -by species -agg "avg_mass=body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass" -finalize "save=chart.png"
```

---

## 6. 📈 Aggregation & Grouping (`-by`, `-agg`)

Perform blazing-fast grouped calculations:

```bash
# Group-by count
pytae data.parquet -by species -count

# Multiple aggregations per group
pytae data.parquet -by species -agg "avg_mass=body_mass_g:mean, max_flipper=flipper_length_mm:max, total=count"

# Multi-column grouping
pytae data.parquet -by "species,island" -agg "mean_mass=body_mass_g:mean"

# Deduplicate rows across key columns
pytae data.parquet -distinct "species,island"

# Sort rows by multiple columns with directions
pytae data.parquet -arrange "species asc, body_mass_g desc"

# Sequential -by with single-shot zero-pollution scoping (each -by scopes the next verb, then resets)
pytae sales.parquet -by region -mutate "regional_mean=mean(sales)" -mutate "global_mean=mean(sales)" -by dept -mutate "dept_mean=mean(sales)"

# Top N per group in a single CLI command (e.g. top 2 species by avg body mass for each island)
pytae penguins.parquet -by island,species -agg "avg_mass=mean(body_mass_g)" -arrange "island, avg_mass desc" -by island -head 2
```

---

## 7. 🔄 Reshaping & Pivoting (`-long`, `-wide`, `-pivot`)

Reshape tables without writing complex code:

```bash
# Melt wide table into long form (unpivot): r (id rows), c (header name), v (values)
pytae data.parquet -long "r=species,island, c=metric, v=value"

# Reshape long table back to wide (1-to-1 un-melt): r, c, v
pytae long.parquet -wide "r=species, c=metric, v=value"

# 2D Pivot table with aggregation: r (rows), c (columns), v (values), a (aggregation)
pytae data.parquet -pivot "r=species, c=island, v=body_mass_g, a=mean"

# Explode / unnest list-like or array columns into multiple rows (one element per row)
pytae events.parquet -explode tags
pytae orders.parquet -explode "items,quantities"
```

---

## 8. 🔗 Multi-File Relational Operations (`-file`, `-join`, `-sql`)

Combine multiple datasets without touching Python:

```bash
# Inner, left, right, or outer joins
pytae -file "orders.parquet=ord; customers.csv=cust" \
  -join "left=ord, right=cust, on=customer_id, how=left" \
  -head 10

# Stack datasets vertically (concat / union)
pytae -file "q1.parquet=a; q2.parquet=b; q3.parquet=c" \
  -concat "frames=a,b,c" -shape

# Run analytical ANSI SQL across files
pytae -file "sales.parquet=s; stores.csv=st" \
  -sql "SELECT st.region, SUM(s.amount) as total FROM s JOIN st ON s.store_id = st.id GROUP BY 1 ORDER BY 2 DESC"

# Load globbed multi-file partitions into -file
pytae -file "parts/*.parquet=all_parts; stores.csv=st" \
  -join "left=all_parts, right=st, on=store_id, how=left"
```

---

## 9. 💾 Format Conversions & Sinks (`-o`)

Convert effortlessly between `.parquet`, `.csv`, `.tsv`, `.dat`, `.jsonl`, and `.sas7bdat`:

```bash
# Convert SAS7BDAT to snappy compressed Parquet
pytae legacy.sas7bdat -o clean.parquet

# Convert Parquet to CSV
pytae data.parquet -o export.csv

# Batch convert all CSV files in a directory to Parquet
pytae "raw/*.csv" -o parquet -out_dir "clean/"

# Specify delimiter or encoding
pytae data.txt -dlim "\t" -encoding latin-1 -o data.parquet

# Copy filtered results directly to system clipboard
pytae data.parquet -filter "species == 'Gentoo'" -head 10 -o clip
```

---

## 10. 🧪 Drift & Difference Detection (`-diff`)

Compare two datasets for schema, row count, null count, and numerical cell drift:

```bash
# Compare schema and values between two files
pytae baseline.parquet -diff current.parquet

# Tolerance threshold for floating-point calculations (absolute & relative)
pytae baseline.parquet -diff current.parquet -tol 1e-4

# Key-aware row alignment (reconcile by primary/composite keys, detect added/removed keys & cell diffs)
pytae baseline.parquet -diff "current.parquet,on=id,tol=1e-4"
pytae baseline.parquet -diff "current.parquet,on=id:cust_id,tol=0.01"

# Compare with custom delimiter or encoding
pytae left.csv -diff right.csv -dlim "," -tol 0.001
```

---

## 11. 🚰 Unix Shell Piping

Integrate seamlessly into standard Unix command-line pipelines:

```bash
# Pipe raw CSV data from standard input (use '-' as path)
cat raw_stream.csv | pytae - -fmt csv -shape

# Pipe through grep, awk, or less
pytae data.parquet -filter "body_mass_g > 4000" | grep "Biscoe" | less

# Shell output redirection
pytae data.parquet -select "species,body_mass_g" -arrange "body_mass_g desc" > top_penguins.txt

# Inspect compressed archives directly
pytae archive.csv.gz -shape -head 5
```

---

## 12. 🎭 Sensitive Data Masking, Encryption & Tokenization (`-mask`, `-unmask`)

Secure, redact, encrypt, or tokenize sensitive PII columns across one-way and reversible workflows:

```bash
# 1. One-way Cryptographic SHA-256 Hashing
pytae users.csv -mask "email=hash, user_id=sha256"

# One-way Hashing with Custom Salt
pytae users.csv -mask "email=hash" -salt "company_secret_salt_2026"

# 2. Character & String Redaction (replaces with '***')
pytae users.csv -mask "ssn=redact, credit_card=redact"

# 3. Option 1: Reversible Authenticated Encryption (-key)
# Encrypt sensitive columns using authenticated AES/HMAC stream encryption
pytae users.csv -mask "ssn=encrypt, notes=encrypt" -key "MyStrongSecretPassphrase" -o secure.parquet

# Reversible Decryption with -unmask and -key
pytae secure.parquet -unmask "ssn, notes" -key "MyStrongSecretPassphrase"

# 4. Option 2: Reversible Pseudonym Tokenization with Persistent Vault (-vault)
# Maps unique values to consistent pseudonym tokens (e.g., user_0001) while preserving joins
pytae users.csv -mask "user=tokenize" -vault "user_vault.parquet" -o anonymized.parquet

# De-tokenize back to original values using the vault
pytae anonymized.parquet -unmask "user" -vault "user_vault.parquet"

# Mixed Multi-Column Strategy
pytae customers.csv -mask "email=hash, ssn=encrypt, name=tokenize" -key "SecretKey" -vault "names.parquet" -o clean.parquet
```

---

## 13. 💬 Interactive REPL Shell (`-i`)

Stateful interactive data manipulation environment with in-memory execution and undo/redo history:

```bash
# Launch interactive REPL with a dataset pre-loaded
pytae data.parquet -i

# Launch empty REPL workbench
pytae -i

# Pre-filter dataset and drop directly into interactive REPL
pytae data.parquet -filter "sales > 100" -i

# Resume or launch a named persistent session (default ~/.pytae/sessions/<name>)
pytae -session analysis

# Custom session storage directory (overrides default location)
export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/pytae_sessions"
pytae -session analysis

# List all saved persistent sessions on disk
pytae -sessions

# Inside the REPL prompt:
# 1. State Management & Undo
undo                 # Revert last transformation
redo                 # Re-apply last undone transformation
reset                # Revert to latest checkpoint (or initial dataset if none)
reset initial        # Revert strictly to initial dataset read (bypassing checkpoints)
history              # Show history of applied steps and checkpoint milestone banners
history -cli         # Export session transformations as reproducible one-line CLI command
history -py          # Export session transformations as runnable Python script (import pytae as pt...)
checkpoint v1        # Save disk-backed snapshot (Arrow IPC, 0 RAM overhead, resets undo baseline)
rm checkpoint v1     # Delete a saved checkpoint from disk (or rm checkpoint *)
restore v1           # Restore workbench to snapshot (RAM strictly from v1, purges post-v1 tables)
session              # Display active session name, disk path, and saved checkpoints
session save v_done  # Save current session checkpoints under named directory
session load my_lab  # Switch to persistent session and boot from its latest checkpoint
sessions             # List all saved persistent sessions on disk
rm session my_lab    # Delete a saved persistent session from disk
rm df                # Remove active table from memory and free RAM (or rm df1 / rm *)
clear                # Clear the terminal screen
status               # Show active dataset shape, columns, and memory

# 2. Pipeline Execution & Inspection (RAM-speed with zero file re-reads)
pytae> -filter "species == 'Gentoo'"
pytae> -mutate "mass_kg = body_mass_g / 1000.0"
pytae> -by species -agg "mean_kg=mass_kg:mean, n=count"
pytae> -select "species,island,mass_kg"
pytae> -arrange "mass_kg desc"
pytae> -cols asc                                             # Column names sorted alphabetically
pytae> -cols | grep mass                                     # Pipe command output to shell utility

# 3. Direct Query Engines & Export
pytae> -sql "SELECT species, AVG(body_mass_g) FROM df GROUP BY 1"
pytae> py df.shape
pytae> -o clean.parquet
pytae> -o clip                                               # Copy active table to system clipboard
# Up / Down arrow keys recall persistent command history (~/.pytae_history)
```

---

## 13. 📖 Documentation Search & MCP Server (`doc`, `mcp`)

Search documentation, CLI flags, Python API verbs, and syntax rules instantly from your terminal or AI coding assistant:

```bash
# Search by keyword or verb
pytae doc explode
pytae doc assert
pytae doc "diff on key"

# Search by concept or natural language (BM25 full-text ranking)
pytae doc "flatten list"
pytae doc "schema drift"
pytae doc "grouped percentiles"

# Launch Model Context Protocol (MCP) server for Copilot, Cursor, or VS Code
pytae mcp
```

---

👉 **For Python Library Reference**: See [docs/pytae.md](pytae.md) or import directly via `import pytae as pt`.

================================================================================
INTERACTIVE REPL SHELL GUIDE (docs/repl.md)
================================================================================

################################################################################
# FILE: docs/repl.md
################################################################################
# CLI Feature Guide: Interactive REPL Shell (`-i`)

Stateful, iterative in-memory data manipulation and exploratory data analysis without repeatedly reloading datasets from disk.

---

## Contents

- [Overview and Why Use REPL](#overview-and-why-use-repl)
- [Two Core Operation Modes](#two-core-operation-modes)
- [Launching the REPL](#launching-the-repl)
- [Mode 1: Single-Table Exploration Deep-Dive](#mode-1-single-table-exploration-deep-dive)
  - [In-Memory Pipeline Transformations](#in-memory-pipeline-transformations)
  - [Non-Destructive Inspection & Column Sorting](#non-destructive-inspection--column-sorting)
  - [Session State, Reset Hierarchy, and Rollback](#session-state-reset-hierarchy-and-rollback)
  - [Checkpoints and Snapshots](#checkpoints-and-snapshots-disk-backed--memory-isolated)
  - [Persistent REPL Sessions](#persistent-repl-sessions-session--s--sessions)
- [Mode 2: Multi-Table Workbench Deep-Dive](#mode-2-multi-table-workbench-deep-dive)
  - [Ingesting Datasets](#ingesting-datasets)
  - [Listing Loaded Tables](#listing-loaded-tables)
  - [Removing Tables (`rm <table_name>`)](#removing-in-memory-tables-rm-table_name)
  - [Subject-First Execution](#subject-first-execution)
  - [Multi-Table Joins](#multi-table-joins)
  - [Assigning Pipeline and Join Results](#assigning-pipeline-and-join-results)
  - [ANSI SQL Across Loaded Tables](#ansi-sql-across-loaded-tables)
  - [Fluent Python Queries](#fluent-python-queries)
- [Piping Output to Shell Tools (`|`)](#piping-output-to-shell-tools-)
- [Command History & Arrow Key Navigation](#command-history--arrow-key-navigation)
- [Saving and Exporting](#saving-and-exporting)
- [Complete REPL Command Reference](#complete-repl-command-reference)

---

## Overview and Why Use REPL

In standard one-shot CLI usage, executing multiple queries on a 1 GB file requires re-reading and re-parsing the file from disk on every single command:

```bash
# Standard CLI: reads and parses sales.parquet 3 separate times
pytae sales.parquet -shape
pytae sales.parquet -filter "amount > 100" -head 5
pytae sales.parquet -by region -agg "total=amount:sum"
```

The **Pytae REPL** loads your dataset into memory **once**. All subsequent filters, aggregations, feature mutations, and SQL queries execute in RAM at multithreaded Polars speed. Because Polars tables are immutable Arrow buffers under the hood, rolling back a mistake with `undo` or `reset` is an instantaneous $O(1)$ pointer reassignment.

---

## Two Core Operation Modes

The Pytae REPL is engineered around two distinct data analysis scenarios with zero syntax bloat:

| Feature | Mode 1: Single-Table Exploration | Mode 2: Multi-Table Workbench |
|---|---|---|
| **Invocation** | `pytae penguins.parquet -i` | `pytae -i` |
| **Primary Workflow** | Rapid, iterative analysis of a single file | Multi-table joins, comparative analysis, SQL |
| **Command Syntax** | `-filter "..."`, `-head 5`, `-o clean.parquet` | `df1 -filter "..."`, `df2 -head 5`, `df1 -join df2` |
| **Dataset Prefix** | Omitted (unambiguous, only 1 table exists) | Explicit subject-first (`df1`, `df2`, `df3`) |
| **State Cursor** | Bound to the loaded file | Stateless workbench (subject specifies the table) |

---

## Launching the REPL

You can launch the REPL from the command line in multiple ways:

```bash
# 1. Mode 1: Pre-load a single dataset into the interactive shell
pytae penguins.parquet -i

# 2. Mode 2: Launch an empty REPL workbench (load datasets via df1 = orders.parquet)
pytae -i

# 3. Pre-filter a dataset and drop directly into the interactive REPL
pytae penguins.parquet -filter "body_mass_g > 4000" -i

# 4. Resume or start a named persistent session
pytae -session analysis

# 5. List all saved persistent sessions from the command line
pytae -sessions
```

Upon launching, the interactive prompt displays the current file name and live table shape (or session name if active):
```text
pytae [penguins.parquet: 344x7]> 
pytae:analysis [orders.parquet: 10000x4]> 
```

---

## Mode 1: Single-Table Exploration Deep-Dive

When launched with a single input file (`pytae penguins.parquet -i`), the REPL enters **Single-Table Exploration Mode**. Because only one dataset exists in memory, all operations execute directly on the active table without needing any table prefix.

### In-Memory Pipeline Transformations

Any standard Pytae CLI flag sequence can be typed directly into the prompt. Transformations execute on the in-memory Arrow table, output a concise status confirmation, and update the table state:

```text
pytae [penguins.parquet: 344x7]> -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"
-> penguins.parquet: 188 rows x 7 cols

pytae [penguins.parquet: 188x7]> -mutate "mass_kg = body_mass_g / 1000, is_heavy = mass_kg > 4.5"
-> penguins.parquet: 188 rows x 9 cols

pytae [penguins.parquet: 188x9]> -select "species,island,mass_kg"
-> penguins.parquet: 188 rows x 3 cols

pytae [penguins.parquet: 188x3]> -head 3
┌─────────┬───────────┬─────────┐
│ species ┆ island    ┆ mass_kg │
│ ---     ┆ ---       ┆ ---     │
│ str     ┆ str       ┆ f64     │
╞═════════╪═══════════╪═════════╡
│ Adelie  ┆ Torgersen ┆ 3.75    │
│ Adelie  ┆ Biscoe    ┆ 3.8     │
│ Adelie  ┆ Dream     ┆ 3.9     │
└─────────┴───────────┴─────────┘
```

> [!NOTE]
> **1:1 CLI Syntax Parity**: Pipeline verbs and inspection flags always start with a leading hyphen (e.g. `-filter`, `-mutate`, `-select`, `-arrange`, `-join`, `-head`, `-shape`, `-cols`), maintaining exact parity with standard CLI usage. If a bare verb is entered (e.g. `filter "..."` or `shape`), Pytae catches it and provides a helpful reminder.

> [!TIP]
> **Clean Terminal (Model 2)**: Pipeline transformations and table switching output concise shape confirmations (e.g. `-> penguins.parquet: 188 rows x 7 cols` or `df1: 344 rows x 7 cols`) without dumping full tables. To view rows, explicitly run `-head` or `-tail`.

### Non-Destructive Inspection & Column Sorting

Inspection commands display metadata or previews **without** truncating or mutating your dataset:

```text
# Non-destructive previews (does NOT truncate active rows)
pytae> -head 10
pytae> -tail 5

# Dimensions
pytae> -shape
(344, 7)

# Column names in file order
pytae> -cols
species
island
bill_length_mm
...

# Column names sorted alphabetically (asc) or descending (desc)
pytae> -cols asc
bill_depth_mm
bill_length_mm
body_mass_g
flipper_length_mm
island
sex
species

# Column name pattern filtering
pytae> -cols mass
body_mass_g

# Column types & missing values (also supports asc / desc sorting)
pytae> -dtype
pytae> -dtype asc
pytae> -nulls
pytae> -glimpse
pytae> -describe
```

### Session State, Reset Hierarchy, and Rollback

* **`reset`**: Reverts the session to the **latest saved checkpoint**. If no checkpoints exist in the session, it falls back to the original dataset state as loaded from disk. Bare `reset` resets **all tables** across the workbench. Active RAM is strictly isolated, post-checkpoint tables are purged, undo/redo history is cleared, and garbage collection runs immediately:
  ```text
  pytae [df1, df2, df3]> reset
  Restored checkpoint 'maddy' (2 tables: df1, df2; active: df2).
  ```
* **`reset <table_name>`**: Resets **only the specified table** (e.g., `reset df1`) to its state in the latest checkpoint (or initial file read if no checkpoint exists), leaving all other tables completely untouched:
  ```text
  pytae [df1, df2]> reset df1
  Reset table 'df1' to latest checkpoint 'v1'.
  ```
* **`reset <table_name> initial`**: Strictly reverts the specified table back to its initial file read state without touching any other tables in the session:
  ```text
  pytae [df1, df2]> reset df1 initial
  Reset table 'df1' to initial state (344 rows x 7 cols).
  ```
* **`reset initial`**: Strictly reverts **all tables** across the entire session back to the initial dataset read state, even when intermediate checkpoints exist:
  ```text
  pytae [df1, df2]> reset initial
  Restored initial dataset. Active shape: (344, 7)
  ```
  > [!NOTE]
  > Unrecognized table names are rejected:
  > `pytae: table 'orig' not found. Available: df1, df2`

* **`undo` & `redo`**: Step backward and forward through your transformation stack:
  ```text
  pytae> undo
  Undid: -filter "body_mass_g > 4000". Active shape: (344, 7)

  pytae> redo
  Redid: -filter "body_mass_g > 4000". Active shape: (168, 7)
  ```
* **`history`**: View the full audit log of applied pipeline transformations alongside checkpoint milestones:
  ```text
  pytae> history
  Pipeline History:
     1: -filter "species == 'Adelie'"
    *checkpoint: v1*
     2: -mutate "mass_kg = body_mass_g / 1000.0"
     3: reset (to checkpoint 'v1')
  ```
  Checkpoint milestones appear unnumbered as distinct banners (`  *checkpoint: <name>*`), while executable transformation steps are numbered sequentially without skipping.

### Checkpoints and Snapshots (Disk-Backed & Memory-Isolated)

Checkpoints in Pytae are **session-wide, persisted to disk (Arrow IPC), and consume 0 MB of active RAM**.

Key Architectural Guarantees:
1. **Disk Storage (Arrow IPC)**: Tables are serialized to session storage via Polars Arrow IPC (`.ipc`). Saved checkpoints do not duplicate memory or pin RAM.
2. **Undo Baseline Reset**: Creating a checkpoint (`checkpoint <name>`) establishes a clean milestone. The undo/redo stacks are cleared, immediately releasing intermediate transformation memory from RAM via garbage collection. Any *subsequent* transformations push to a fresh undo stack, so you can freely experiment and `undo` back to your checkpoint milestone.
3. **Strict Memory Isolation on `restore`**: Running `restore <name>` completely purges any post-checkpoint tables (e.g. `df3`, temporary joins) from memory, resets the undo stack, triggers `gc.collect()`, and loads strictly the checkpoint tables. Active RAM is guaranteed to match the checkpoint state only.
4. **Decoupled `rm`**: Running `rm <table_name>` reclaims RAM immediately. Checkpoints on disk remain completely safe and independent.

```text
# Save a named checkpoint across the entire workbench session (persisted to disk, undo reset)
pytae [df1, df2]> checkpoint maddy
Saved checkpoint 'maddy' (2 tables: df1, df2).

# Create experimental tables or run mutations
pytae [df1, df2]> df3 = df1 -filter "amount > 100"
pytae [df1, df2, df3]> df2 -filter "status == 'active'"

# List all saved checkpoints and their constituent tables
pytae [df1, df2, df3]> checkpoints
Saved Checkpoints:
  - maddy          : df1 (344x7), df2 (244x7) [active: df2]

# Delete a single saved checkpoint (frees disk files)
pytae [df1, df2, df3]> rm checkpoint maddy
Removed checkpoint 'maddy'.

# Or alternatively
pytae [df1, df2, df3]> checkpoint rm maddy

# Clear all saved checkpoints
pytae [df1, df2, df3]> rm checkpoint *
Cleared all saved checkpoints.

# Restore the entire workbench back to the checkpoint (RAM strictly isolated, post-checkpoint tables dropped)
pytae [df1, df2, df3]> restore maddy
Restored checkpoint 'maddy' (2 tables: df1, df2; active: df2).
pytae [df1, df2]> 
```

### Persistent REPL Sessions (`-session`, `-s`, `-sessions`)

Pytae provides full support for **named, persistent REPL sessions** that can be closed and resumed at any time across terminal sessions.

#### 1. Core Architectural Rules

1. **Only Checkpoints are Persisted**: In a persistent session, only frozen checkpoints (`checkpoint <name>`) and their Arrow IPC tables are saved to disk. Any scratch/uncheckpointed tables, temporary joins, or ad-hoc column mutations in RAM are dropped on REPL exit.
2. **Clean Boot from Latest Checkpoint**: Upon booting or resuming a session (`pytae -session <name>`), the session loads strictly from its latest checkpoint. Active memory is clean, with 0 MB of scratch memory leaked from previous sessions.
3. **Session Location**: Sessions are stored under `~/.pytae/sessions/<name>/` by default (containing session metadata and `.ipc` checkpoint tables). You can override this base directory to any custom folder, external SSD, or project path by setting the `PYTAE_SESSIONS_DIR` environment variable.

> [!TIP]
> **Customizing Session Storage Location (`PYTAE_SESSIONS_DIR`)**:
> - **In Shell (Bash / Zsh)**:
>   ```bash
>   # Override for a single session:
>   PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/my_sessions" pytae -session analysis
>
>   # Or export permanently in ~/.zshrc or ~/.bashrc:
>   export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/my_sessions"
>   ```
> - **In Python**:
>   ```python
>   import os
>   os.environ["PYTAE_SESSIONS_DIR"] = "/path/to/custom_sessions"
>   import pytae as pt
>   pt.repl(session="analysis")
>   ```
> - **Verifying Location**: Type `session` inside the REPL prompt at any time to verify the exact active directory on disk:
>   ```text
>   pytae:analysis [df1: 344x7]> session
>   Active session: 'analysis' (2 checkpoints; location: /Volumes/ExternalSSD/my_sessions/analysis)
>   ```


#### 2. CLI Interface

```bash
# Launch or resume a named persistent session
pytae -session analysis

# Start a persistent session with an initial dataset pre-loaded
pytae penguins.parquet -session penguins_lab

# List all saved persistent sessions on disk
pytae -sessions
```

Listing sessions displays checkpoint counts, total disk size, and last modified timestamps:
```text
$ pytae -sessions
Saved Sessions:
  - penguins_lab     : 2 checkpoints (0.05 MB) [last modified: 2026-10-26 22:15]
  - sales_q3         : 3 checkpoints (4.12 MB) [last modified: 2026-10-26 21:40]
```

#### 3. In-REPL Session Commands

Within any active REPL shell, you can manage sessions without quitting:

```text
# Check current session status and disk directory
pytae:penguins_lab [df1]> session
Active session: 'penguins_lab' (/Users/username/.pytae/sessions/penguins_lab)
Saved checkpoints: v1, v2 (latest: v2)

# Save or promote current anonymous session to a named persistent session
pytae [df1, df2]> session save analysis_final
Saved session 'analysis_final' (/Users/username/.pytae/sessions/analysis_final).

# Load/switch to an existing persistent session (loads latest checkpoint)
pytae [df1]> session load sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v3' (2 tables: df1, df2).

# List all saved sessions from inside the REPL
pytae> sessions
Saved Sessions:
  - penguins_lab     : 2 checkpoints (0.05 MB)
  - sales_q3         : 3 checkpoints (4.12 MB)

# Remove a persistent session from disk
pytae> rm session sales_q3
Removed session 'sales_q3' from disk.
```

When a persistent session is active, the prompt dynamically includes the session name:
```text
pytae:analysis [df1: 344x7]> 
```

---

## Mode 2: Multi-Table Workbench Deep-Dive

When launched with `pytae -i`, the REPL enters **Multi-Table Workbench Mode**. You can load several datasets into memory simultaneously and manipulate them using clean, stateless **subject-first commands (`df -cmd`)**.

### Ingesting Datasets

Load files into named variables using standard assignment syntax or the `load` command. In addition to file paths, you can pass inline reader options matching the CLI (`-encoding`, `-dlim`, `-nrows`):

```text
$ pytae -i
================================================================================
                         PYTAE INTERACTIVE REPL                                 
================================================================================
Type 'help' for REPL commands, 'reset' to revert to original, or 'exit' to quit.
No initial dataset loaded. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table.

# 1. Load an existing file from disk
pytae> df1 = orders.parquet
Loaded orders.parquet as 'df1' (10,000 rows x 4 cols).

# 2. Ingest CSV with specific encoding, custom delimiter, and row limit
pytae [df1: 10,000x4]> df2 = raw_data.csv -encoding latin1 -dlim ";" -nrows 5000
Loaded raw_data.csv as 'df2' (5,000 rows x 8 cols) [encoding=latin1, sep=;, nrows=5000].

# 3. Or load using the load command with alias and options
pytae [df1, df2]> load sales.csv as df3 -dlim "\t"
Loaded sales.csv as 'df3' (1,200 rows x 6 cols) [sep=	].

# 4. Multi-file globbing and directory scanning
pytae [df1, df2, df3]> load "parts/*.parquet" as df4
Loaded 12 files matching 'parts/*.parquet' as 'df4' (120,000 rows x 8 cols).

# 5. Or explicitly load a bundled sample dataset via sample:<name>
pytae [df1, df2, df3, df4]> df5 = sample:penguins
Loaded penguins.parquet as 'df5' (344 rows x 7 cols).

pytae [df1, df2, df3, df4]>
```

> [!NOTE]
> File assignments are strict and predictable: `df = filename.parquet` requires an actual file on disk. Bundled sample datasets are only loaded when explicitly prefixed with `sample:<name>` (e.g. `df = sample:penguins`). There is no fuzzy matching or automatic fallback for non-existent files.

Notice how the prompt dynamically updates to show all datasets currently in memory: `pytae [df1, df2]> `.

### Listing Loaded Tables

Inspect all loaded tables and their dimensions anytime:

```text
pytae [df1, df2]> tables
Tables in memory:
   df1         : 10,000 rows x 4 cols (orders.parquet)
   df2         : 1,500 rows x 3 cols (customers.parquet)
```

### Removing In-Memory Tables (`rm <table_name>` / `rm df`)

Remove datasets from memory when they are no longer needed. Pytae flexibly resolves table targets by explicit variable name, filename stem, or the universal alias `df` (which targets the currently active dataset):

```text
# Remove by universal alias (targets active dataset):
pytae [penguins.parquet: 344x8]> rm df
Removed table 'penguins.parquet'. No tables remain loaded.
pytae>

# Remove by filename stem:
pytae [orders.parquet, customers.parquet]> rm orders
Removed table 'orders.parquet'. Switched active dataset to 'customers.parquet'.

# Remove all loaded tables at once:
pytae [df1, df2]> rm *
Removed all 2 loaded tables. No tables remain loaded.
```

> [!TIP]
> **Immediate Memory Release (`rm`)**: `rm <name>` and `rm *` immediately drop tables from memory and perform garbage collection with zero disk overhead. Table removal is non-undoable to ensure multi-gigabyte datasets are instantly purged without filling disk space with redundant serialization dumps. If you want a recovery snapshot before dropping tables, save a checkpoint first (`checkpoint <name>`), which can be restored anytime with `restore <name>` or `reset`. Additionally, transformation undo history is bounded to a sliding window of 10 steps to prevent long pipelines from accumulating memory.

### Subject-First Execution

Instead of modal "switching" between tables, **every operation explicitly states its target dataset**. This eliminates ambiguity and mirrors the Pytae CLI 1:1:

```text
# Non-destructive inspection of specific tables
pytae [df1, df2]> df1 -head 3
pytae [df1, df2]> df2 -head 3
pytae [df1, df2]> df1 -shape
(10,000, 4)
pytae [df1, df2]> df2 -cols

# Apply in-place transformations to a specific table
pytae [df1, df2]> df1 -filter "amount > 100"
pytae [df1, df2]> df1 -shape
(3,450, 4)

# Export a specific table directly
pytae [df1, df2]> df1 -o clean_orders.parquet
```

> [!TIP]
> **Quick Dimensions**: Typing a bare table name (e.g. `df1`) switches to it and prints its dimensions (`df1: 10,000 rows x 4 cols`) without dumping any table rows. To inspect rows, run `df1 -head 5` or `-head 5`.

### Multi-Table Joins

Join datasets using standard Pytae `-join` syntax directly in the REPL:

```text
# Join df2 into df1 on a shared customer_id key
pytae [df1, df2]> df1 -join df2 on=customer_id

# Differing column names and explicit join type
pytae [df1, df2]> df1 -join df2 on=cust_id:id how=left

# Join and export directly in one step
pytae [df1, df2]> df1 -join df2 on=cust_id -o merged.parquet
```

Supported join types: `how=left`, `how=inner`, `how=outer`, `how=semi`, `how=anti`.

### Assigning Pipeline and Join Results

Create new named tables from transformations, joins, or ANSI SQL queries:

```text
# 1. Pipeline assignment from another table (df1 remains untouched)
pytae [df1, df2]> df_filtered = df1 -filter "amount > 150"

# 2. Join assignment
pytae [df1, df2]> df3 = df1 -join df2 on=cust_id

# 3. ANSI SQL assignment across loaded tables
pytae [df1, df2, df3]> df4 = -sql "SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id"
Created 'df4' (10,000 rows x 3 cols).
```

### ANSI SQL Across Loaded Tables

Every loaded table (`df1`, `df2`, `df3`, etc.) and saved checkpoint is automatically registered in Polars SQLContext:

```text
pytae [df1, df2]> -sql "SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id"
-> df1: 10,000 rows x 3 cols

pytae [df1, df2]> -head 2
┌──────────┬─────────────┬────────┐
│ order_id ┆ name        ┆ amount │
│ ---      ┆ ---         ┆ ---    │
│ i64      ┆ str         ┆ f64    │
╞══════════╪═════════════╪════════╡
│ 1001     ┆ Alice Smith ┆ 149.50 │
│ 1002     ┆ Bob Jones   ┆ 89.00  │
└──────────┴─────────────┴────────┘
```

### Fluent Python Queries

Evaluate Python expressions directly against your loaded tables:

```text
pytae [df1, df2]> py df1.join(df2, on="cust_id", how="left")
```

---

## Piping Output to Shell Tools (`|`)

You can pipe any REPL command output directly to standard Unix shell utilities (such as `grep`, `awk`, `head`, `wc`, or `less`) using the pipe operator `|`:

```text
# Search column names with grep
pytae [penguins.parquet: 344x7]> -cols | grep mass
body_mass_g

# Search sorted columns on a targeted table
pytae [df1, df2]> df1 -cols asc | grep bill
bill_depth_mm
bill_length_mm

# Count preview rows with wc
pytae [penguins.parquet: 344x7]> -head 50 | wc -l
54
```

> [!NOTE]
> Pipe symbols inside quotes or brackets (such as `-select "regex=bill|body"` or python expressions) are safely evaluated as expression logic rather than shell pipes.

---

## Command History & Arrow Key Navigation

The REPL automatically preserves command history across sessions:
- **`~/.pytae_history`**: History is persistently saved to your home directory (up to 1,000 commands).
- **Up / Down Arrow Keys**: Press <kbd>↑</kbd> and <kbd>↓</kbd> to cycle backward and forward through prior commands. Supported on Unix/macOS (`libedit`, GNU `readline`), Windows Terminal, and PowerShell.
- **Git Bash on Windows**: When launching Pytae in standard Git Bash (MinTTY), run with `winpty pytae -i` (or inside Windows Terminal) for full interactive line editing. If run without `winpty`, pressing <kbd>↑</kbd> and Enter automatically recalls and executes prior commands from history.
- **`history`**: Displays a numbered log of pipeline transformation steps applied during the current session.
- **`history -cli`**: Generates and prints an exact, reproducible one-shot CLI command string reconstructing the entire interactive session from scratch.
- **`history -py`**: Generates and prints a complete, runnable Python script using `import pytae as pt` and DataFrame method chaining.

---

## Saving and Exporting

Export your active dataset to disk or the system clipboard using the standard `-o` flag:

```text
# Export to Parquet, CSV, or NDJSON
pytae> -o clean_penguins.parquet
pytae> -o output.csv
pytae> -o output.ndjson

# Copy directly to system clipboard
pytae> -o clip
```

---

## Complete REPL Command Reference

| Command | Syntax | Description | Mutates Active Table? |
|---|---|---|---|
| **`help`** | `help` | Display formatted help manual | No |
| **`clear`** | `clear` | Clear the terminal screen | No |
| **`status`** | `status` | Show active dataset name, shape, memory, undo stack depth | No |
| **`reset`** | `reset` | Revert all tables across workbench to latest checkpoint (or initial dataset read if no checkpoints exist) | **Yes** (clears undo) |
| **`reset <table_name>`** | `reset <table_name>` | Revert only the specified table to latest checkpoint (or initial read) without affecting other tables | **Yes** (clears undo) |
| **`reset <table_name> initial`** | `reset <table_name> initial` | Revert only the specified table strictly to initial read without affecting other tables | **Yes** (clears undo) |
| **`reset initial`** | `reset initial` | Revert all tables strictly to initial dataset read (bypassing checkpoints) | **Yes** (clears undo) |
| **`undo`** | `undo` | Revert the last applied transformation step | **Yes** (undoable) |
| **`redo`** | `redo` | Re-apply the last undone transformation step | **Yes** (undoable) |
| **`history`** | `history`, `history -cli`, `history -py` | List numbered transformation steps, or export history as CLI command (`-cli`) or Python script (`-py`) | No |
| **`checkpoint`** | `checkpoint <name>` | Save snapshot of entire workbench (all tables in session) | No |
| **`rm checkpoint`** | `rm checkpoint <name>`, `rm checkpoint *` | Delete a saved checkpoint (or all checkpoints) | No |
| **`restore`** | `restore <name>` | Restore entire workbench to named checkpoint | **Yes** (undoable) |
| **`checkpoints`**| `checkpoints` | List all saved checkpoints and their constituent tables | No |
| **`session`** | `session` | Display active session name, disk path, and checkpoints | No |
| **`session save`**| `session save <name>` | Save or promote session to persistent storage under `<name>` | No |
| **`session load`**| `session load <name>` | Switch to persistent session and restore its latest checkpoint | **Yes** (undoable) |
| **`sessions`** | `sessions` | List all persistent sessions saved on disk | No |
| **`rm session`**| `rm session <name>` | Remove a named persistent session directory from disk | No |
| **`rm`** | `rm <table_name>`, `rm df`, `rm *` | Remove table or active dataset from memory (releases RAM immediately) | No (use `checkpoint` for snapshots) |
| **`gc` / `free`** | `gc`, `free` | Force garbage collection and return unmapped memory pages to OS | No |
| **`<var> = <file>`** | `df1 = orders.parquet [-encoding <enc>] [-dlim <char>] [-nrows <N>]` | Ingest dataset into a named table with reader options | **Yes** |
| **`load`** | `load <file> [as <alias>] [-encoding <enc>] [-dlim <char>] [-nrows <N>]` | Load dataset with alias and reader options | **Yes** |
| **`tables`** | `tables` | List all loaded tables in memory | No |
| **`<name> -<cmd>`** | `df1 -head 5`, `df2 -shape`, `df1 -cols asc` | Run command directly on named table (subject-first) | Depends on command |
| **`<name>`** | `df1` | Switch to table and display dimensions (`rows x cols`) | **Yes** (switches active) |
| **`-join`** | `-join <target> on=<key> [how=...] [-o <path>]` | Join table or file into active dataset | **Yes** (undoable) |
| **`-o`** | `-o <path>`, `-o clip` | Export active dataset to Parquet/CSV or clipboard | No |
| **`-sql`** | `-sql "<query>"` | Run ANSI SQL against active table or named tables | **Yes** (undoable) |
| **`py`** | `py <expr>` | Evaluate Python expression on `df` / `pldf` | No |
| **`<cmd> \| <sh>`** | `-cols \| grep bill`, `-head 50 \| wc -l` | Pipe command output to external shell tool | No |
| **`-head`** | `-head [N]` | Non-destructive preview of top $N$ rows (default 5) | No |
| **`-tail`** | `-tail [N]` | Non-destructive preview of bottom $N$ rows (default 5) | No |
| **`-shape`** | `-shape` | Display row and column counts | No |
| **`-cols`** | `-cols [asc\|desc\|pattern]` | List column names (file order, or asc/desc sorted, or filtered) | No |
| **`-dtype`** | `-dtype [asc\|desc]` | Display column data types (optional alphabetical sort) | No |
| **`-nulls`** | `-nulls [asc\|desc]` | Display missing value counts (optional alphabetical sort) | No |
| **`-glimpse`** | `-glimpse` | Display transposed schema and sample values | No |
| **`-describe`**| `-describe` | Display statistical summary of numeric columns | No |
| **`exit`** | `exit` | Exit the REPL session | — |

================================================================================
10. ECOSYSTEM COMPARISONS & MIGRATION GUIDES (Pandas, dplyr, SAS)
================================================================================

################################################################################
# FILE: docs/comparison_to_pandas.md
################################################################################
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
penguins.by("sex").count()
# or: penguins.by("sex").agg(total="count")
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
# PYTAE: Zero-Data-Loss safety semantics (bare dropna drops only 100% blank rows)
df.dropna()                       # Drops only 100% blank rows
df.dropna("customer_id", "email") # Drops rows missing required keys (how='any')
```

---

## 3. Grouping Semantics: Lazy `DataFrameGroupBy` vs. Single-Shot `by()`

### The Pandas Trap
In Pandas, `.groupby()` returns a lazy intermediate `DataFrameGroupBy` object. This object splits the API: some methods work on it, others do not. You cannot chain regular DataFrame methods without aggregating first or invoking complex `.apply()` functions that cause severe performance degradation.

### The Pytae Solution
In Pytae, grouping is **single-shot, non-destructive, and auto-clearing**:
- `df.by(*cols)` sets a transient grouping context for the *immediate next verb* (`mutate`, `agg`, `head`, `tail`).
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

## 4. Performance & Speed Benchmarks: Native Polars SIMD vs. Single-Threaded Pandas

Pandas executes operations primarily in the Python interpreter and single-threaded NumPy routines, bounded by the Python Global Interpreter Lock (GIL). In contrast, Pytae is powered by the multithreaded Rust engine of **Polars**, utilizing AVX-512 / AVX2 / NEON hardware vector instructions across all available CPU cores with contiguous Apache Arrow columnar memory layouts.

### Architecture Comparison
| Dimension | Pandas | Pytae |
|:---|:---|:---|
| **Underlying Architecture** | Python interpreter + C/NumPy arrays | 100% Native Rust + Apache Arrow |
| **Multithreading** | Single-threaded; blocked by Python GIL | Automatically parallelized across all CPU cores |
| **Vectorization** | Limited NumPy SIMD | Full AVX-512 / AVX2 / NEON vector pipelines |
| **Memory Model** | High overhead (object pointers, frequent copies) | Minimal overhead (Arrow chunked memory, string cache) |
| **Lazy Execution** | No native query optimizer | `pt.scan_parquet()` query planning & pushdowns |

### Reproducible Speed Benchmarks (5,000,000 Rows)
*Environment: Apple Silicon M-series (macOS), Python 3.13, 5,000,000 rows across 5 columns (categorical strings, float measurements, integer weights).*

| Benchmark Task (5 Million Rows) | Pandas 2.2 Execution | Pytae (Eager) | Pytae (Lazy Pushdown) | Pytae Advantage |
|:---|:---|:---|:---|:---|
| **End-to-End Pipeline**<br>*(Parquet Read $\to$ Filter $\to$ Mutate $\to$ GroupBy Agg $\to$ Arrange)* | `0.587s` | `0.205s` | **`0.042s`** | **14.1x faster** (Lazy)<br>**2.9x faster** (Eager) |
| **Multi-Column Sorting (`arrange`)**<br>*(5M rows, 2 columns: string asc, numeric desc)* | `2.981s` | **`0.730s`** | N/A | **4.1x faster** |
| **Grouped Aggregation (`by` + `agg`)**<br>*(5M rows, 15 groups, 3 metrics: `n`, `mean`, `max`)* | `0.258s` | **`0.131s`** | N/A | **2.0x faster** |
| **Relational Join (`join`)**<br>*(1,000,000 rows $\times$ 1,000,000 rows, integer key inner join)* | `0.133s` | **`0.052s`** | N/A | **2.6x faster** |
| **Analytical SQL Query (`sql`)**<br>*(5M rows, Filter + Group By + Aggregations via SQL)* | External engine required | **`0.021s`** | N/A | **Sub-25ms instant** |

### Why Pytae Outperforms Pandas
1. **True Multithreading without GIL**: While Pandas processes row loops and `apply()` sequentially on a single core, Pytae chunks operations across all hardware threads without locking.
2. **Predicate & Projection Pushdown**: In `pt.scan_parquet()`, Pytae reads only the requested columns and filters rows directly inside the Parquet storage reader before materializing buffers into memory.
3. **Zero Intermediate Memory Duplication**: Pandas frequently requires `.copy()` to avoid `SettingWithCopyWarning`, multiplying memory footprint. Pytae utilizes copy-on-write and Arrow buffer slicing.

> [!TIP]
> **Reproducibility**: Complete, self-contained benchmark scripts and interactive notebooks are available in **[`docs/benchmarks/`](benchmarks/README.md)** (executable CLI script: [`run_benchmarks.py`](benchmarks/run_benchmarks.py), interactive notebook: [`benchmarks.ipynb`](benchmarks/benchmarks.ipynb)).

---

## 5. Feature-by-Feature Rosetta Stone: Pytae vs. Pandas

### 1. Row Filtering
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Boolean Mask** | `df[df['sales'] > 100]` | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `df[(df['a'] > 1) & (df['b'] == 'E')]` | `df.filter("a > 1 and b == 'E'")` | `-filter "a > 1 and b == 'E'"` |
| **Interval / Range** | `df[df['x'].between(10, 20)]` | `df.filter(x=("between", 10, 20))` | `-filter "{'x': ('between', 10, 20)}"` |
| **Set Membership** | `df[df['cat'].isin(['A', 'B'])]` | `df.filter(cat=['A', 'B'])` | `-filter "cat in ['A', 'B']"` |
| **Spaced Columns** | `df[df['gross sales'] > 50]` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **String Prefix** | `df[df['name'].str.startswith('A')]` | `df.filter(name=('startswith', 'A'))` | `-filter "name.startswith('A')"` |
| **Null Row Check** | `df[df['col'].notna()]` | `df.filter("col.is_not_null()")` | `-filter "col.is_not_null()"` |
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
| **Drop Columns** | `df.drop(columns=['c', 'd'])` | `df.select("!c", "!d")` | `-select "!c,!d"` |
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

### 5. Grouped Aggregation & Counting (`count`, `by` + `agg`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Count Frequencies** | `df['g'].value_counts().reset_index()` | `df.count("g")` | `-count g` |
| **Group Row Count** | `df.groupby('g').size().reset_index(name='n')` | `df.by("g").count()` | `-by g -count` |
| **Group & Summarize** | `df.groupby('g')['x'].mean().reset_index()` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Summary with Count** | `df.groupby('g').agg(n=('x','size'), m=('x','mean')).reset_index()` | `df.by("g").agg(total="count", m="x:mean")` | `-by g -agg "total=count,m=x:mean"` |
| **Multiple Metrics** | `df.groupby('g').agg(m=('x','mean'), s=('x','sum')).reset_index()` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Keep NA Groups** | `df.groupby('g', dropna=False).mean().reset_index()` | Default behavior (`dropna=False`) | Default behavior |
| **Whole-Table Summary**| `df.agg({'x': 'mean'}).to_frame().T` | `df.agg(m="x:mean", n="count")` | `-agg "m=x:mean,n=count"` |

### 6. Slicing Extreme Records (`arrange` + `head` / `tail`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `df.nlargest(5, 'sales')` | `df.arrange("sales desc").head(5)` | `-arrange "sales desc" -head 5` |
| **Bottom N Records** | `df.nsmallest(5, 'sales')` | `df.arrange("sales").head(5)` | `-arrange sales -head 5` |
| **Top Percentage** | `df.nlargest(int(len(df)*0.1), 'sales')` | `df.arrange("sales desc").head(prop=0.1)` | `-arrange "sales desc" -head 10%` |
| **Top N per Group** | `df.groupby('g').apply(lambda d: d.nlargest(3, 'x')).reset_index(drop=True)` | `df.by("g").arrange("x desc").head(3)` | `-by g -arrange "x desc" -head 3` |

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

### 11. Missing Data Architecture & Cleaning (`dropna`, `fillna`, `clean_columns`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Safe Blank Row Dropping** | `df.dropna(how='all')` *(Defaults to dangerous `how='any'`)* | `df.dropna()` *(Defaults to safe `how='all'`)* | `-dropna` |
| **Targeted Key Dropping** | `df.dropna(subset=['id', 'email'])` | `df.dropna("id", "email")` | `-dropna id,email` |
| **Dual Null & NaN Imputation**| `df.fillna(0)` *(Fails on nullable types)*| `df.fillna(0, nans=True)` | `-fillna 0` |
| **Column-Specific Imputation**| `df.fillna({'a': 0, 'b': 'N/A'})` | `df.fillna({'a': 0, 'b': 'N/A'})` | `-fillna "a=0,b='N/A'"` |
| **Deterministic Column Cleaning**| Third-party `janitor` / `skimpy` | `df.clean_columns()` *(Deterministic 6-stage)* | `-clean_columns` |
| **Preserve NA Groups in Agg** | `df.groupby('g', dropna=False).agg(...)` | Default behavior (`dropna=False`) | Default behavior |

### 12. Embedded ANSI SQL Engine (`sql`)
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **SQL Query on DataFrame** | Requires external `duckdb` or `sqldf` | `df.sql("SELECT species, avg(body_mass_g) FROM self GROUP BY species")` | N/A |
| **SQL Query on Disk File** | Requires importing `duckdb` in script | `pt.sql("SELECT * FROM 'data.parquet' WHERE sales > 100")` | `-sql "SELECT * FROM file.parquet WHERE sales > 100"` |

### 13. Grouped Window Calculations & Lag/Lead
| Task | Pandas | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Group Mean Window** | `df['m'] = df.groupby('g')['x'].transform('mean')` | `df.by("g").mutate(m="mean(x)")` | `-by g -mutate "m = mean(x)"` |
| **Within-Group Percentage** | `df['pct'] = df['x'] / df.groupby('g')['x'].transform('sum')` | `df.by("g").mutate(pct="x / sum(x)")` | `-by g -mutate "pct = x / sum(x)"` |
| **Within-Group Rank** | `df.groupby('g')['x'].rank()` | `df.by("g").mutate(r="rank(x)")` | `-by g -mutate "r = rank(x)"` |
| **Grouped Shift / Lag** | `df.groupby('g')['x'].shift(1)` | `df.by("g").mutate(prev="shift(x, 1)")` | `-by g -mutate "prev = shift(x, 1)"` |
| **Grouped Cumulative Sum** | `df.groupby('g')['x'].cumsum()` | `df.by("g").mutate(cum="cum_sum(x)")` | `-by g -mutate "cum = cum_sum(x)"` |

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
    .filter("body_mass_g > 3500 & sex.is_not_null()")
    .mutate(body_mass_kg="body_mass_g / 1000", bill_ratio="bill_length_mm / bill_depth_mm")
    .by("species", "island")
    .agg(n="count", avg_mass_kg="body_mass_kg:mean", max_ratio="bill_ratio:max")
    .arrange("avg_mass_kg desc")
    .to_parquet("summary.parquet")
)
```

### In Pytae (Unix CLI Pipeline):
```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500 and sex.is_not_null()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -by species,island \
  -agg "n = count, avg_mass_kg = body_mass_kg:mean, max_ratio = bill_ratio:max" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

Notice the stark contrast: Pytae eliminates intermediate variables, eliminates `.copy()`, eliminates `.reset_index()`, eliminates `index=False`, and translates 1:1 into a single high-performance terminal command.


################################################################################
# FILE: docs/comparison_to_dplyr.md
################################################################################
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
- `df.by(*cols)` establishes a grouping context for the *immediate next verb* (`mutate`, `agg`, `head`, `tail`).
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
| **Multiple Conditions** | `filter(df, a > 1, b == "E")` | `df.filter("a > 1 and b == 'E'")` | `-filter "a > 1 and b == 'E'"` |
| **Interval / Range** | `filter(df, between(x, 10, 20))` | `df.filter(x=("between", 10, 20))` | `-filter "{'x': ('between', 10, 20)}"` |
| **Set Membership** | `filter(df, cat %in% c("A", "B"))` | `df.filter(cat=['A', 'B'])` | `-filter "cat in ['A', 'B']"` |
| **Spaced Columns** | `filter(df, \`gross sales\` > 50)` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **Prefix Match** | `filter(df, str_starts(name, "A"))`| `df.filter(name=('startswith', 'A'))`| `-filter "name.startswith('A')"` |
| **Null Row Check** | `filter(df, !is.na(col))` | `df.filter("col.is_not_null()")` | `-filter "col.is_not_null()"` |

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
| **Drop Columns** | `select(df, -c, -d)` | `df.select("!c", "!d")` | `-select "!c,!d"` |
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

### 5. Grouped Summaries & Counting (`count`, `by` + `agg`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Count Frequencies** | `count(df, g, sort = TRUE)` | `df.count("g")` | `-count g` |
| **Group Row Count** | `df %>% group_by(g) %>% count()` | `df.by("g").count()` | `-by g -count` |
| **Group Summary** | `df %>% group_by(g) %>% summarise(m = mean(x)) %>% ungroup()` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Summary with Count** | `summarise(df, total = n(), m = mean(x))` | `df.by("g").agg(total="count", m="x:mean")` | `-by g -agg "total=count,m=x:mean"` |
| **Multiple Metrics** | `summarise(df, m = mean(x), s = sum(x))` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Whole-Table Summary**| `summarise(df, m = mean(x))` | `df.agg(m="x:mean", n="count")` | `-agg "m=x:mean,n=count"` |

### 6. Slicing Top / Bottom Records (`arrange` + `head` / `tail`)
| Task | dplyr (R) | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `slice_max(df, sales, n = 5)` | `df.arrange("sales desc").head(5)` | `-arrange "sales desc" -head 5` |
| **Bottom N Records** | `slice_min(df, sales, n = 5)` | `df.arrange("sales").head(5)` | `-arrange sales -head 5` |
| **Top Proportion** | `slice_max(df, sales, prop = 0.1)` | `df.arrange("sales desc").head(prop=0.1)` | `-arrange "sales desc" -head 10%` |
| **Top N per Group** | `df %>% group_by(g) %>% slice_max(x, n = 3) %>% ungroup()` | `df.by("g").arrange("x desc").head(3)` | `-by g -arrange "x desc" -head 3` |

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
| **Column Name Cleaning** | `janitor::clean_names(df)` | `df.clean_columns()` *(Deterministic 6-stage)* | `-clean_columns` |
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
| **Grouped Cumulative Sum** | `df %>% group_by(g) %>% mutate(cum = cumsum(x)) %>% ungroup()` | `df.by("g").mutate(cum="x.cumsum()")` | `-by g -mutate "cum = x.cumsum()"` |

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
    .filter("body_mass_g > 3500 & sex.is_not_null()")
    .mutate(body_mass_kg="body_mass_g / 1000", bill_ratio="bill_length_mm / bill_depth_mm")
    .by("species", "island")
    .agg(n="count", avg_mass_kg="body_mass_kg:mean", max_ratio="bill_ratio:max")
    .arrange("avg_mass_kg desc")
    .to_parquet("summary.parquet")
)
```

### In Pytae (Unix CLI Pipeline):
```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500 and sex.is_not_null()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -by species,island \
  -agg "n = count, avg_mass_kg = body_mass_kg:mean, max_ratio = bill_ratio:max" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

Pytae provides everything Tidyverse users love about `dplyr`—fluent method chaining, declarative verbs, and clean data thinking—while granting massive SIMD vector performance and Unix command-line superpowers.


################################################################################
# FILE: docs/comparison_to_sas.md
################################################################################
# Pytae vs. SAS — Deep Dive & Migration Guide

[← Back to Master Reference](pytae.md) | [Comparison with Pandas](comparison_to_pandas.md) | [Comparison with dplyr](comparison_to_dplyr.md)

For over four decades, **SAS (Statistical Analysis System)** has been the foundational analytical engine in regulated enterprise environments: clinical trials, biostatistics, pharmaceutical submissions (CDISC SDTM / ADaM), banking risk models (Basel / CECL / CCAR), insurance actuarial analysis, and government statistics.

As organizations modernize their tech stacks and migrate toward Python and cloud-native architectures, SAS developers, biostatisticians, and risk analysts often encounter steep friction with standard Python tools like Pandas. Pandas introduces foreign index abstractions, fragile chaining, and multi-syntax confusion.

`pytae` provides a natural, high-performance bridge for SAS professionals:
1. **Familiar Tabular Intuition**: Pure, flat 2D data tables without index complexity.
2. **"One and Only One Obvious Way"**: Eliminates syntax fragmentation by providing exactly one clear verb per task.
3. **Massive Multithreaded Vector Speed**: Replaces slow, iterative row-by-row `DATA` step processing with 100% native Rust/Polars SIMD vectorization.
4. **Native `.sas7bdat` Ingestion**: Read legacy SAS datasets directly without needing SAS installed.

---

## Key Architectural Differences: Pytae vs. SAS

```
┌───────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
│ Architectural Dimension       │ SAS (Base SAS, STAT, ETS)        │ Pytae (Python Library & CLI)     │
├───────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
│ Core Execution Paradigm       │ Row-by-row Program Data Vector   │ Multithreaded SIMD Vector Core   │
│ Syntax Architecture           │ Split: DATA step vs PROC SQL/PROCs│ Single, unified grammar          │
│ In-Memory Data Structure      │ SAS Dataset (.sas7bdat) on disk  │ Apache Arrow / Polars DataFrame  │
│ Missing Value Internal Rep    │ Numeric '.' is smaller than -Inf │ Strict null / IEEE-754 NaN       │
│ Relational Merge Prerequisite │ All inputs MUST be sorted on disk│ In-memory hash join (no sort)    │
│ State Tracking (Lags/Sums)    │ Manual RETAIN, FIRST., LAST.     │ Declarative window expressions   │
│ Grouping Mechanism            │ BY statement (requires sort)     │ Single-shot by() (auto-clearing) │
│ Reshaping                     │ PROC TRANSPOSE (_NAME_, COL1)    │ Unified wide(), long(), pivot()  │
│ Interactive Execution         │ Batch (.sas -> .log / .lst)      │ Interactive Python REPL & CLI    │
└───────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
```

---

## 1. The Core Paradigm Shift: SAS Program Data Vector vs. Pytae Vector SIMD

### The SAS Execution Model
In SAS, the `DATA` step is an explicit, procedural row-by-row loop:
1. SAS initializes the **Program Data Vector (PDV)** in memory.
2. It reads one observation from disk into the PDV.
3. It executes the statements in the `DATA` step sequentially.
4. At the `RUN;` statement, it outputs the PDV to disk and loops back to step 2 until the end of the file (`EOF`).

While intuitive for sequential accounting logic, the PDV model creates significant overhead:
- It relies heavily on temporary disk scratch space (`WORK` library).
- Window calculations require manual state maintenance using `RETAIN` statements and automatic variables (`_N_`, `_ERROR_`).
- Operations cannot parallelize across CPU cores because rows are processed sequentially.

### The Pytae Vector Execution Model
Pytae executes operations on **entire column vectors simultaneously**:
- Processing is powered by native Rust/Polars multithreaded SIMD kernels.
- Operations automatically saturate all available CPU cores.
- Data resides in contiguous Apache Arrow memory buffers with zero Python GIL lockup.

---

## 2. The Dangerous SAS Missing Value Trap vs. Pytae Safe Nulls

### The SAS Negative Infinity Trap
In SAS, numeric missing values (`.`, `.A` through `.Z`) are stored internally as special double-precision values that are **smaller than negative infinity** ($-\infty$):

$$\text{Missing } (.) < -999{,}999{,}999 < 0 < \text{Positive Numbers}$$

This architectural choice causes catastrophic logic errors when filtering or deriving variables:

```sas
/* DANGEROUS SAS LOGIC BUG */
DATA pediatric_check;
  SET clinical_patients;
  IF age < 18 THEN pediatric = 1; /* BUG! */
  ELSE pediatric = 0;
RUN;
```

> [!CAUTION]
> If a patient's `age` is missing (`.`), SAS evaluates `age < 18` as **TRUE** because `.` is smaller than 18! Consequently, patients with unrecorded ages are misclassified as pediatric patients.
>
> SAS programmers are forced to write defensive, verbose conditions everywhere:
> `IF NOT MISSING(age) AND age < 18 THEN pediatric = 1;`

### The Pytae Safe Null Model
In Pytae, missing values adhere to strict three-valued logic and IEEE-754 semantics:
- A comparison with missing (`null` or `NaN`) always evaluates to missing / false.
- Filtering `df.filter("age < 18")` **never** includes null or NaN records.
- Null checks are explicit and readable: `df.filter("age.is_not_null()")` or `df.filter("age.is_null()")`.

---

## 3. Merge Requirements: SAS Pre-Sorting vs. Pytae Instant Hash Joins

### The SAS Sort Requirement
In SAS, merging two datasets using the `MERGE` statement in a `DATA` step strictly requires that **both datasets be physically sorted on disk by the merge keys**:

```sas
/* MANDATORY SAS PRE-SORTING */
PROC SORT DATA=work.demographics;
  BY patient_id;
RUN;

PROC SORT DATA=work.vitals;
  BY patient_id;
RUN;

DATA work.merged;
  MERGE work.demographics (IN=in_demo) work.vitals (IN=in_vit);
  BY patient_id;
  IF in_demo; /* Left join */
RUN;
```

If either dataset is not sorted, SAS halts execution with a fatal runtime error:
`ERROR: BY variables are not properly sorted on data set WORK.DEMOGRAPHICS.`

### The Pytae Instant Hash Join
Pytae uses in-memory hash joins:
- Datasets **never** need to be pre-sorted.
- Keys with different column names are linked with a simple colon (`on="patient_id:subjid"`).
- Join cardinality is validated automatically if desired:

```python
# PYTAE: Zero pre-sorting required
demographics.join(vitals, on="patient_id", how="left", validate="1:m")
```

---

## 4. Group Statefulness: SAS `RETAIN` and `FIRST.`/`LAST.` vs. Pytae Declarative Windows

### The SAS Multi-Step Ceremony
In SAS, computing running totals, cumulative maximums, or group percentages requires:
1. Running `PROC SORT` by the grouping variable.
2. Creating a `DATA` step with a `BY` statement.
3. Explicitly declaring `RETAIN` variables.
4. Writing conditional logic checking `IF FIRST.group THEN ...`:

```sas
/* SAS: Cumulative sales by region */
PROC SORT DATA=sales;
  BY region;
RUN;

DATA sales_running;
  SET sales;
  BY region;
  RETAIN cum_sales;
  IF FIRST.region THEN cum_sales = 0;
  cum_sales = cum_sales + amount;
RUN;
```

### The Pytae Single-Line Declarative Vector
In Pytae, grouped calculations are written as clear, declarative expressions without state management:

```python
# PYTAE: One obvious declarative line
sales.by("region").mutate(cum_sales="amount.cumsum()")
```

---

## 5. Reshaping: `PROC TRANSPOSE` vs. `wide`, `long`, `pivot`

### The SAS `PROC TRANSPOSE` Complexity
In SAS, transposing long data into wide data (or vice versa) is notoriously cryptic:
```sas
PROC TRANSPOSE DATA=vitals OUT=vitals_wide (DROP=_NAME_);
  BY patient_id visit;
  ID test_code;
  VAR test_result;
RUN;
```
`PROC TRANSPOSE` produces arbitrary automatic column names (`_NAME_`, `COL1`, `COL2`) that require post-processing `RENAME=` clauses and macro workarounds.

### The Pytae Reshaping Suite
Pytae provides three intuitive, dedicated verbs with zero column name artifacts:
1. **`df.long(id_vars=..., cols=...)`**: Melts wide columns into tall records.
2. **`df.wide(r=..., c=..., v=...)`**: Pure 1-to-1 structural unmelting without aggregation.
3. **`df.pivot(r=..., c=..., v=..., a=...)`**: Generates 2D cross-tabulation aggregation matrices.

---

## 6. Performance & Speed Benchmarks: Base SAS Disk Spooling & PROC SORT vs. Pytae Vector SIMD

In traditional SAS architectures, analytical execution speed is severely throttled by two primary bottlenecks:
1. **Single-Threaded Program Data Vector (PDV)**: Sequential row-by-row iteration in the `DATA` step cannot leverage modern multi-core CPU architectures.
2. **Mandatory Disk Spooling & Sort Steps**: `PROC SORT` and `MERGE ... BY ...` repeatedly write temporary datasets to the `WORK` scratch library on physical disk, incurring massive I/O serialization penalties.

Pytae completely eliminates these bottlenecks by executing in-memory on **Apache Arrow columnar buffers** powered by **Polars Rust SIMD vector parallelism**.

### Comparative Benchmark: SAS vs. Pytae (5,000,000 Records)
*Environment: 5,000,000 observations, clinical trial simulation data (demographics, labs, vital signs).*

| Operation / Pipeline Stage | Base SAS Execution Model | Pytae Execution | Pytae Speedup Advantage |
|:---|:---|:---|:---|
| **End-to-End Pipeline**<br>*(File Read $\to$ Filter $\to$ Derive $\to$ Group Summary $\to$ Sort)* | **`6.50s – 12.00s`**<br>*(Sequential PDV read + PROC MEANS + PROC SORT + disk write)* | **`0.205s`** (Eager)<br>**`0.042s`** (Lazy) | **30x to 150x faster**<br>*(Zero disk spooling)* |
| **Sorting 5M Observations**<br>*(PROC SORT by Category, Value DESC)* | **`5.80s – 9.50s`**<br>*(Writes scratch files to WORK library on disk)* | **`0.730s`**<br>*(In-memory multithreaded radix sort)* | **8x to 13x faster** |
| **Relational Join / Merge**<br>*(1,000,000 obs $\times$ 1,000,000 obs)* | **`3.50s – 6.00s`**<br>*(Requires 2x PROC SORT + DATA step MERGE)* | **`0.052s`**<br>*(Instant in-memory hash join; NO pre-sort!)* | **70x to 110x faster** |
| **Grouped Summary Statistics**<br>*(PROC MEANS / PROC SUMMARY on 5M rows)* | **`1.80s – 3.20s`**<br>*(Single-threaded aggregation step)* | **`0.131s`**<br>*(Multithreaded vector SIMD aggregation)* | **14x to 24x faster** |
| **Ingestion of `.sas7bdat` Files**<br>*(Direct binary SAS dataset read into memory)* | Native SAS engine | **Instant zero-copy Arrow**<br>*(No SAS license required)* | **Direct modern analytics** |

### Why Migration to Pytae Accelerates Clinical & Financial Pipelines
- **No Mandatory Pre-Sorting**: SAS pipelines spend up to 60% of their total wall-clock runtime executing `PROC SORT` simply to satisfy the prerequisite of `MERGE ... BY ...` or `BY` group processing. Pytae hash joins and group contexts require **zero pre-sorting**.
- **Zero Disk Thrashing**: SAS pipelines create dozens of intermediate datasets in `WORK` (`work.temp1`, `work.temp2`), generating heavy disk I/O. Pytae operations stream purely in high-speed RAM and Arrow buffers.
- **Hardware Saturated Concurrency**: While a SAS `DATA` step utilizes only 1 CPU core at 100%, Pytae saturates all 8, 16, or 64 cores simultaneously.

> [!TIP]
> **Reproducibility**: Complete, self-contained benchmark scripts and interactive notebooks are available in **[`docs/benchmarks/`](benchmarks/README.md)** (executable CLI script: [`run_benchmarks.py`](benchmarks/run_benchmarks.py), interactive notebook: [`benchmarks.ipynb`](benchmarks/benchmarks.ipynb)).

---

## 7. Feature-by-Feature Rosetta Stone: Pytae vs. SAS

### 1. Data Ingestion & I/O
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Read SAS Dataset** | `SET libref.dataset;` | `pt.DataFrame(pd.read_sas("dataset.sas7bdat"))` | `pytae dataset.sas7bdat` |
| **Read CSV** | `PROC IMPORT DATAFILE='...' DBMS=CSV;` | `pt.read_csv("file.csv")` | `pytae file.csv` |
| **Read Parquet** | SAS Viya CAS Parquet engine | `pt.read_parquet("file.parquet")` | `pytae file.parquet` |
| **Write Parquet** | Viya CAS Save | `df.to_parquet("file.parquet")` | `-o file.parquet` |
| **Write CSV** | `PROC EXPORT DATAFILE='...' DBMS=CSV;` | `df.to_csv("file.csv")` | `-o file.csv` |
| **Clipboard Export** | Custom DDE / ODS script | `df.to_clip()` | `-o clip` |

### 2. Row Filtering
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Filter** | `WHERE sales > 100;` (or `IF sales > 100;`) | `df.filter("sales > 100")` | `-filter "sales > 100"` |
| **Multiple Conditions** | `WHERE a > 1 AND b = 'East';` | `df.filter("a > 1 and b == 'East'")` | `-filter "a > 1 and b == 'East'"` |
| **Mathematical Range** | `WHERE 10 <= x <= 20;` | `df.filter(x=("between", 10, 20))` | `-filter "{'x': ('between', 10, 20)}"` |
| **Set Membership** | `WHERE cat IN ('A', 'B');` | `df.filter(cat=['A', 'B'])` | `-filter "cat in ['A', 'B']"` |
| **Spaced Column Name** | `WHERE 'gross sales'n > 50;` | `df.filter("[gross sales] > 50")` | `-filter "[gross sales] > 50"` |
| **String Prefix Match**| `WHERE name LIKE 'A%';` | `df.filter(name=('startswith', 'A'))` | `-filter "name.startswith('A')"` |
| **Non-Missing Check** | `WHERE col IS NOT MISSING;` | `df.filter("col.is_not_null()")` | `-filter "col.is_not_null()"` |

### 3. Column Derivations & Feature Engineering (`mutate`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Simple Math** | `y = a / b;` | `df.mutate(y="a / b")` | `-mutate "y = a / b"` |
| **Sequential Calculations**| `a = 1; b = a * 2;` | `df.mutate(a="1", b="a * 2")` | `-mutate "a=1, b=a*2"` |
| **Conditional (If/Else)** | `IF x > 0 THEN f='pos'; ELSE f='neg';` | `df.mutate(f="if_else(x > 0, 'pos', 'neg')")` | `-mutate "f=if_else(x>0,'pos','neg')"` |
| **Multi-Branch (Case)** | `SELECT; WHEN(c1) f=v1; OTHERWISE f=v3; END;` | `df.mutate(f="case_when(c1, v1, c2, v2, v3)")` | `-mutate "f=case_when(c1,v1,v3)"` |
| **Format / Value Recoding**| `PROC FORMAT; ... PUT(x, fmt.);` | `df.mutate(x="map(x, {'A': 1, 'B': 2})")` | `-mutate "x=map(x, {'A':1})"` |
| **Lag / Previous Row** | `prev = LAG(x);` | `df.mutate(prev="shift(x, 1)")` | `-mutate "prev = shift(x, 1)"` |
| **Multi-Column Transform**| `ARRAY cols(*) a b; DO i=1 TO 2; ...` | `df.mutate("(a, b) = _ * 10")` | `-mutate "(a, b) = _ * 10"` |
| **Multi-Column + Suffix** | Macro loop generating variable assignments | `df.mutate("(a, b)_cm = _ * 10")` | `-mutate "(a, b)_cm = _ * 10"` |

### 4. Column Selection & Renaming (`select`, `rename`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Keep Columns** | `KEEP a b;` (or `SET in (KEEP=a b);`) | `df.select("a", "b")` | `-select "a,b"` |
| **Drop Columns** | `DROP c d;` (or `SET in (DROP=c d);`) | `df.select("!c", "!d")` | `-select "!c,!d"` |
| **Rename Variables** | `RENAME old=new;` | `df.rename("old:new")` | `-rename "old:new"` |
| **Inline Select & Rename**| `SET in (KEEP=a RENAME=(a=b));` | `df.select("a:b")` | `-select "a:b"` |

### 5. Row Sorting (`arrange`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Ascending Sort** | `PROC SORT; BY sales; RUN;` | `df.arrange("sales")` | `-arrange sales` |
| **Descending Sort** | `PROC SORT; BY DESCENDING sales; RUN;` | `df.arrange("sales desc")` | `-arrange "sales desc"` |
| **Multi-Column Sort** | `PROC SORT; BY a DESCENDING b; RUN;` | `df.arrange("a", "b desc")` | `-arrange "a, b desc"` |

### 6. Grouped Summaries & Counting (`count`, `by` + `agg`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Frequency Count** | `PROC FREQ; TABLES g; RUN;` | `df.count("g")` | `-count g` |
| **Group Mean** | `PROC MEANS NWAY NOPRINT; CLASS g; VAR x; OUTPUT OUT=out MEAN=m; RUN;` | `df.by("g").agg(m="x:mean")` | `-by g -agg m=x:mean` |
| **Observation Count** | `OUTPUT OUT=out N=n;` | `df.by("g").agg(total="count")` | `-by g -agg total=count` |
| **Multiple Metrics** | `OUTPUT OUT=out MEAN=m SUM=s MIN=mn MAX=mx;` | `df.by("g").agg(m="x:mean", s="x:sum")` | `-by g -agg "m=x:mean,s=x:sum"` |
| **Preserve Missing Groups**| `PROC MEANS MISSING;` *(Defaults to dropping!)*| Default behavior (`dropna=False`) | Default behavior |

### 7. Deduplication (`distinct`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Deduplicate Table** | `PROC SORT NODUPRECS; BY _ALL_; RUN;` | `df.distinct()` | `-distinct` |
| **Deduplicate by Keys** | `PROC SORT NODUPKEY; BY a b; RUN;` | `df.distinct("a", "b")` | `-distinct "a,b"` |

### 8. Extreme Record Slicing (`arrange` + `head` / `tail`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Top N Records** | `PROC SORT; BY DESCENDING x; DATA out; SET in; IF _N_ <= 5; RUN;` | `df.arrange("x desc").head(5)` | `-arrange "x desc" -head 5` |
| **Bottom N Records** | `PROC SORT; BY x; DATA out; SET in; IF _N_ <= 5; RUN;` | `df.arrange("x").head(5)` | `-arrange x -head 5` |
| **Top N per Group** | `PROC SORT; BY g DESCENDING x; DATA out; SET in; BY g; IF FIRST.g; RUN;` | `df.by("g").arrange("x desc").head(1)` | `-by g -arrange "x desc" -head 1` |

### 9. Reshaping & Pivoting (`wide`, `long`, `pivot`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Wide to Long (Unpivot)**| `PROC TRANSPOSE DATA=in OUT=out; BY id; VAR x y; RUN;` | `df.long(id_vars="id", cols=["x", "y"])` | `-long "id_vars=id, cols='x,y'"` |
| **Long to Wide (Spread)** | `PROC TRANSPOSE DATA=in OUT=out; BY id; ID metric; VAR val; RUN;` | `df.wide(r="id", c="metric", v="val")` | `-wide "r=id, c=metric, v=val"` |
| **2D Pivot Matrix** | `PROC TABULATE` or `PROC TRANSPOSE` after `PROC MEANS` | `df.pivot(r="r", c="c", v="v", a="mean")` | `-pivot "r=r, c=c, v=v, a=mean"` |

### 10. Relational Joins (`join`, `concat`)
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Inner Join** | `MERGE a (IN=in_a) b (IN=in_b); BY id; IF in_a AND in_b;` *(Requires prior sort!)* | `df1.join(df2, on="id", how="inner")` | `-join "f2.parquet,on=id"` |
| **Left Join** | `MERGE a (IN=in_a) b (IN=in_b); BY id; IF in_a;` *(Requires prior sort!)* | `df1.join(df2, on="id", how="left")` | `-join "f2.parquet,on=id,how=left"` |
| **Different Key Names** | `RENAME=(cust_id=id)` inside `MERGE` statement | `df1.join(df2, on="id:cust_id")` | `-join "f2.parquet,on=id:cust_id"` |
| **Vertical Stack (Concat)**| `DATA out; SET a b; RUN;` | `pt.concat([df1, df2], how="vertical")` | N/A |

### 11. Inspection, Profiling & Validation
| Task | SAS | Pytae (Python) | Pytae CLI |
|:---|:---|:---|:---|
| **Dataset Metadata** | `PROC CONTENTS DATA=in; RUN;` | `df.glimpse()` | `-glimpse` |
| **Frequency Table** | `PROC FREQ; TABLES col; RUN;` | `df.freq("col")` *(With ASCII bars)* | `-freq col` |
| **Dataset Comparison** | `PROC COMPARE BASE=a COMPARE=b CRITERION=0.01; RUN;` | `df.diff(df2, tol=0.01)` | `pytae a.parquet -diff b.parquet,tol=0.01` |
| **ANSI SQL Engine** | `PROC SQL; SELECT ... FROM in; QUIT;` | `df.sql("SELECT ... FROM self")` | `-sql "SELECT ... FROM file.parquet"` |

---

## 8. End-to-End Migration Example: Clinical Vital Signs Summary

### The Clinical Analysis Task:
In a clinical trial analysis:
1. Ingest clinical vital signs data.
2. Filter for baseline records (`VISIT = 'Baseline'`) with valid pulse measurements.
3. Compute pulse pressure ($Systolic - Diastolic$).
4. Categorize subjects into hypertensive tiers.
5. Group by treatment arm (`TRTP`) and sex.
6. Summarize subject count, mean systolic, and mean pulse pressure.
7. Sort by mean systolic pressure descending.

### In SAS:
```sas
/* 1. Sort vitals by keys for merging */
PROC SORT DATA=sdtm.vsl;
  BY USUBJID;
RUN;

PROC SORT DATA=sdtm.dm;
  BY USUBJID;
RUN;

/* 2. Merge demographics and filter baseline records */
DATA work.baseline_vitals;
  MERGE sdtm.vsl (IN=in_v) sdtm.dm (IN=in_d);
  BY USUBJID;
  WHERE in_v AND in_d AND VISIT = 'Baseline' AND NOT MISSING(SYSBP) AND NOT MISSING(DIABP);

  /* 3. Derive Pulse Pressure */
  pulse_pressure = SYSBP - DIABP;

  /* 4. Categorize Hypertensive Tier */
  IF SYSBP >= 140 OR DIABP >= 90 THEN htn_tier = 'Stage 2';
  ELSE IF SYSBP >= 130 OR DIABP >= 80 THEN htn_tier = 'Stage 1';
  ELSE htn_tier = 'Normal';
RUN;

/* 5 & 6. Grouped Summary Statistics */
PROC MEANS DATA=work.baseline_vitals NWAY NOPRINT MISSING;
  CLASS TRTP SEX;
  VAR SYSBP pulse_pressure;
  OUTPUT OUT=work.summary (DROP=_TYPE_ _FREQ_)
    N(SYSBP)=n_subjects
    MEAN(SYSBP)=mean_sysbp
    MEAN(pulse_pressure)=mean_pp;
RUN;

/* 7. Sort final summary */
PROC SORT DATA=work.summary;
  BY DESCENDING mean_sysbp;
RUN;
```

### In Pytae (Python Library):
```python
import pandas as pd
import pytae as pt

# Ingest directly from SAS datasets or Parquet
vsl = pt.DataFrame(pd.read_sas("vsl.sas7bdat"))
dm = pt.DataFrame(pd.read_sas("dm.sas7bdat"))

summary = (
    vsl.filter("VISIT == 'Baseline' & SYSBP.is_not_null() & DIABP.is_not_null()")
    .join(dm, on="USUBJID", how="inner")
    .mutate(
        pulse_pressure="SYSBP - DIABP",
        htn_tier="case_when("
            "SYSBP >= 140 | DIABP >= 90, 'Stage 2', "
            "SYSBP >= 130 | DIABP >= 80, 'Stage 1', "
            "'Normal'"
        ")"
    )
    .by("TRTP", "SEX")
    .agg(
        n_subjects="count",
        mean_sysbp="SYSBP:mean",
        mean_pp="pulse_pressure:mean"
    )
    .arrange("mean_sysbp desc")
)

# Export clean result to Parquet or CSV
summary.to_parquet("summary.parquet")
```

### In Pytae (Unix CLI Pipeline):
```bash
pytae vsl.sas7bdat \
  -filter "VISIT == 'Baseline' and SYSBP.is_not_null() and DIABP.is_not_null()" \
  -join "dm.sas7bdat,on=USUBJID,how=inner" \
  -mutate "pulse_pressure = SYSBP - DIABP, htn_tier = case_when(SYSBP >= 140 | DIABP >= 90, 'Stage 2', SYSBP >= 130 | DIABP >= 80, 'Stage 1', 'Normal')" \
  -by TRTP,SEX \
  -agg "n_subjects = count, mean_sysbp = mean(SYSBP), mean_pp = mean(pulse_pressure)" \
  -arrange "mean_sysbp desc" \
  -o summary.parquet
```

### Why SAS Teams Migrate to Pytae
- **No Disk Sorting Overhead**: Pytae's in-memory hash joins replace multi-step `PROC SORT` runs.
- **Zero Syntax Splitting**: No cognitive switching between `DATA` steps and `PROC SQL`.
- **Elimination of Missing Value Logic Bugs**: Pytae's safe null handling prevents accidental inclusion of missing values in comparisons.
- **Modern Cloud Execution**: Runs natively in Linux containers, cloud Lambdas, Airflow DAGs, and interactive Jupyter environments.


================================================================================
11. BUILD & CONFIGURATION (pyproject.toml)
================================================================================

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pytae"
version = "3.12.8"
description = "Fast, ergonomic pandas tools and zero-code CLI for tabular data manipulation and plotting"
authors = [{ name = "Madhukar Kumar Jha", email = "madhukar.k.jha@gmail.com" }]
readme = "readme.md"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.0",
    "pyarrow>=15.0.0",
    "polars>=1.0.0",
    "pyreadline3>=3.4.0; sys_platform == 'win32'",
]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]

[project.optional-dependencies]
plot = ["matplotlib", "scipy"]
sql = []
dev = ["pytest>=8.0.0", "matplotlib", "scipy", "ruff>=0.8", "mypy>=1.13"]
notebooks = ["nbclient", "nbformat", "ipykernel", "scipy"]

[project.scripts]
pytae = "pytae.cli:main"

[project.urls]
"Homepage" = "https://github.com/maddytae/pytae"
"Bug Tracker" = "https://github.com/maddytae/pytae/issues"
"Documentation" = "https://github.com/maddytae/pytae/blob/master/docs/pytae.md"
"Detailed Docs" = "https://github.com/maddytae/pytae/tree/master/docs/detailed_docs"
"Cheat Sheet" = "https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md"
"Changelog" = "https://github.com/maddytae/pytae/blob/master/changelog.md"

[tool.hatch.build.targets.wheel.force-include]
"reference" = "pytae/reference"

[tool.ruff]
target-version = "py311"
line-length = 120
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = [
    "E501",  # line length — CLI specs and docs strings are long on purpose
    "E731",  # clip_action = lambda ... in the CLI pipeline
]

[tool.ruff.lint.per-file-ignores]
"src/pytae/__init__.py" = ["F401"]  # re-exports
"tests/*" = ["E402"]  # sys.path insert before pytae import
"tests/test_mutate.py" = ["E402", "F841"]  # @locals are used via pandas eval
"src/pytae/plotting.py" = ["E741", "F841"]
"docs/detailed_docs/*" = ["E402", "F401", "E401", "E701", "I001"]
"docs/detailed_docs/**" = ["E402", "F401", "E401", "E701", "I001"]

[tool.mypy]
python_version = "3.12"
files = ["src/pytae"]
ignore_missing_imports = true
check_untyped_defs = true
warn_unused_ignores = true
pretty = true
# plotting is matplotlib-heavy; typed incrementally with the rest of the library
exclude = ["src/pytae/plotting.py"]

[[tool.mypy.overrides]]
module = ["pytae.*"]
ignore_errors = true