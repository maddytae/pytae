# CLI Feature Guide: Interactive REPL Shell (`-i`)

Stateful, iterative in-memory data manipulation and exploratory data analysis without repeatedly reloading datasets from disk.

---

## Contents

- [Overview and Why Use REPL](#overview-and-why-use-repl)
- [Architecture & Guarantees](#architecture--guarantees)
- [Launching the REPL](#launching-the-repl)
- [Ingesting Datasets](#ingesting-datasets)
  - [Variable Assignment (`df = file.parquet`)](#variable-assignment-df--fileparquet)
  - [Reader Options (`-encoding`, `-dlim`, `-nrows`)](#reader-options--encoding--dlim--nrows)
  - [The `load` Command](#the-load-command)
  - [Glob Ingestion](#glob-ingestion)
  - [Sample Datasets (`sample:<name>`)](#sample-datasets-samplename)
- [Multi-Table Workbench Operations](#multi-table-workbench-operations)
  - [Listing Tables (`status table`)](#listing-tables-status-table-status-table--v)
  - [Switching Active Tables (`use <name>`)](#switching-active-tables-use-name)
  - [Renaming Tables (`rename <old> <new>`)](#renaming-tables-rename-old-new)
  - [Subject-First Execution (`<tbl> -<cmd>`)](#subject-first-execution-tbl--cmd)
  - [Multi-Table Joins (`-join`)](#multi-table-joins--join)
  - [Assigning Results (`<var> = <tbl> -<pipeline>`)](#assigning-results-var--tbl--pipeline)
- [In-Memory Pipeline Transformations](#in-memory-pipeline-transformations)
  - [Full CLI Pipeline Verbs](#full-cli-pipeline-verbs)
  - [Assignment vs. Bare Exploration Semantics](#assignment-vs-bare-exploration-semantics)
- [Non-Destructive Data Inspection](#non-destructive-data-inspection)
  - [Previews (`-head`, `-tail`, `-sample`)](#previews--head--tail--sample)
  - [Metadata (`-shape`, `-cols`, `-schema`, `-dtype`, `-nulls`)](#metadata--shape--cols--schema--dtype--nulls)
  - [Summaries (`-glimpse`, `-describe`, `-freq`)](#summaries--glimpse--describe--freq)
  - [Comparing Datasets (`-diff <tbl1> <tbl2>`)](#comparing-datasets--diff-tbl1-tbl2)
- [SQL & Python Interop](#sql--python-interop)
  - [ANSI SQL across Tables (`-sql`)](#ansi-sql-across-tables--sql)
  - [Explicit Table Names in SQL](#explicit-table-names-in-sql)
  - [SQL Variable Assignment (`df3 = -sql "..."`)](#sql-variable-assignment-df3---sql-)
  - [Fluent Python Execution (`py <expr>`)](#fluent-python-execution-py-expr)
- [Multi-Line Input & Continuation](#multi-line-input--continuation)
  - [Pipeline Line Continuation (`\`)](#pipeline-line-continuation-)
  - [Multi-Line SQL Queries](#multi-line-sql-queries)
  - [Multi-Line Variables & Data Structures](#multi-line-variables--data-structures)
  - [Bare `py` Python Block Mode](#bare-py-python-block-mode)
  - [Aborting Multi-Line Buffers (`Ctrl+C`)](#aborting-multi-line-buffers-ctrlc)
- [Session Variables & Parameters (`@var`)](#session-variables--parameters-var)
  - [Defining Variables (`<name> = <literal>`)](#defining-variables-name--literal)
  - [Supported Types & Safety Guarantees](#supported-types--safety-guarantees)
  - [Inspection & Key Traversal (`@var`, `@var.key`, `@var[idx]`)](#inspection--key-traversal-var-varkey-varidx)
  - [Using Variables in Pipelines (`-filter`, `-mutate`, `-sql`)](#using-variables-in-pipelines--filter--mutate--sql)
  - [Inspecting and Removing Variables (`status var`, `rm var`)](#inspecting-and-removing-variables-status-var-rm-var)
  - [Checkpoint & Session Persistence (`vars.json`)](#checkpoint--session-persistence-varsjson)
  - [Namespace Isolation & Collision Prevention](#namespace-isolation--collision-prevention)
- [Tab Autocompletion & Navigation](#tab-autocompletion--navigation)
- [Memory Management](#memory-management)
  - [Removing Tables (`rm table <name>`, `rm table *`)](#removing-tables-rm-table-name-rm-table-)
  - [Immediate Memory Deallocation & OS Trimming](#immediate-memory-deallocation--os-trimming)
  - [Diagnostics & Inspection (`status`, `status table`, `status session`)](#diagnostics--inspection-status-status-table-status-session)
- [State Navigation & History](#state-navigation--history)
  - [Reset Hierarchy (`reset`, `reset <tbl>`, `reset initial`)](#reset-hierarchy-reset-reset-tbl-reset-initial)
  - [In-REPL History Audit Log (`history`)](#in-repl-history-audit-log-history)
- [Checkpoints (Disk-Backed & RAM-Isolated)](#checkpoints-disk-backed--ram-isolated)
  - [Saving Checkpoints (`checkpoint <name>`)](#saving-checkpoints-checkpoint-name)
  - [Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)](#listing--deleting-checkpoints-status-checkpoint-rm-checkpoint)
  - [Restoring Entire Workbench (`restore <name>`)](#restoring-entire-workbench-restore-name)
  - [Reloading After `rm *` via `restore <name>`](#reloading-after-rm--via-restore-name)
- [Persistent REPL Sessions](#persistent-repl-sessions)
  - [Unified Path-First Session Architecture](#unified-path-first-session-architecture)
  - [Inspecting & Managing Sessions (`status session`, `sessions`)](#inspecting--managing-sessions-status-session-sessions)
- [REPL Configuration (`set`)](#repl-configuration-set)
  - [Querying Settings (`set`, `set <key>`)](#querying-settings-set-set-key)
  - [Starting a Session (`set new_session = <name|path>`)](#starting-a-session-set-new_session--namepath)
  - [Loading a Session (`set load_session = <name|path>`)](#loading-a-session-set-load_session--namepath)
  - [Saving / Relocating a Session (`set save_session = <name|path>`)](#saving--relocating-a-session-set-save_session--namepath)
  - [Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`)](#checkpoint-storage-format-set-checkpoint_format--parquetipc)
  - [Replay Script Auto-Save (`set save_code = <path>`)](#replay-script-auto-save-set-save_code--path)
  - [Combining Multiple Settings on One Line](#combining-multiple-settings-on-one-line)
- [Session Export & Replay Scripts](#session-export--replay-scripts)
  - [Exit-Time Export (`exit -s [path]`)](#exit-time-export-exit--s-path)
  - [Automatic Replay Script Filtering (`_is_replayable_entry`)](#automatic-replay-script-filtering-_is_replayable_entry)
  - [Path Canonicalization & Windows UNC Resolution](#path-canonicalization--windows-unc-resolution)
  - [Batch Replay Execution (`pytae -i < script.txt`)](#batch-replay-execution-pytae--i--scripttxt)
- [Shell Integration (`|`)](#shell-integration-)
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

The **Pytae REPL (`pytae -i`)** loads your dataset into memory **once**. All subsequent filters, aggregations, feature mutations, and SQL queries execute in RAM at multithreaded Polars speed. Because exploratory pipelines execute non-destructively by default, rolling back a mutated state with `reset` or named checkpoints is instantaneous.

---

## Architecture & Guarantees

1. **Zero Ambiguity (`pytae -i`)**: Interactive sessions are started cleanly with `pytae -i`. Datasets are loaded explicitly inside the REPL (e.g. `df = sales.parquet`), ensuring session history files are completely self-contained and reproducible.
2. **Subject-First Multi-Table Workbench**: Load multiple tables into named variables (`df1`, `df2`, `orders`). Run operations with clear subject prefixes (`df1 -head 5`, `df1 -join df2 on=id`) or switch the active cursor.
3. **Strict Memory Isolation**: Checkpoints are serialized to disk (`.ipc` or `.parquet`). They consume **0 MB of RAM**. Restoring a checkpoint or removing tables immediately frees memory back to the operating system.
4. **Interactive vs. Script Decoupling**: Exploratory previews (bare `-head`, `-pivot`, `-describe`) and checkpoints are kept in the live `history` audit log, but are cleanly omitted when saving batch replay scripts. Intermediate table removals (`rm df1`, `rm *`) are preserved in replay scripts to ensure batch pipelines run with minimal memory footprints.

---

## Launching the REPL

Launch the REPL cleanly from the command line:

```bash
# Launch interactive REPL workbench
pytae -i
```

> [!NOTE]
> `pytae -i` is the dedicated entrypoint for the interactive workbench. Datasets are loaded explicitly inside the REPL with `df = file.parquet`, and persistent project sessions are configured inside via `set session_name = <name>`. This guarantees that exported session history files contain the full ingestion command and run anywhere.

Upon launching, load a dataset to begin exploring:
```text
pytae> df = penguins.parquet
Loaded penguins.parquet as 'df' (344 rows x 7 cols).
pytae [df: 344x7]> 
```

---

## Ingesting Datasets

### Variable Assignment (`df = file.parquet`)
Load datasets directly into named table variables using standard assignment:

```text
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (100,000 rows x 6 cols).
pytae [orders: 100,000x6]> 
```

### Reader Options (`-opts`, `-encoding`, `-dlim`, `-nrows`)
Pass inline format parameters or full reader options directly during assignment:

```text
# Specify Latin-1 encoding, custom semicolon delimiter, and load only the first 5,000 rows
pytae> raw = export.csv -encoding latin1 -dlim ";" -nrows 5000
Loaded export.csv as 'raw' (5,000 rows x 12 cols) [encoding=latin1, sep=;, nrows=5000].

# Load Excel workbooks with default (first) sheet
pytae> sales = sales_2024.xlsx
Loaded sales_2024.xlsx as 'sales' (3,500 rows x 8 cols).

# Specify target sheet name directly inside -opts
pytae> feb = sales_2024.xlsx -opts "sheet=Feb"
Loaded 'feb' from sales_2024.xlsx (3,500 rows x 8 cols).

# Pass multiple reader kwargs using -opts (e.g. sheet, skiprows, header, usecols)
pytae> notes = sales_2024.xlsx -opts "sheet=CustomNotes, skiprows=2, header=0"
Loaded 'notes' from sales_2024.xlsx (1,200 rows x 5 cols).
```
> [!NOTE]
> - Sheet names must strictly be specified via `-opts "sheet=..."`. Colon sheet syntax (`file.xlsx:Sheet`) is not supported to ensure path integrity and eliminate ambiguity.
> - In the REPL, reader options (`-opts`) apply strictly to the specific assignment command on that line. Options do not persist across future assignments, ensuring clean, predictable data loading.

### The `load` Command
Alternatively, use the `load` keyword with optional aliases:

```text
pytae> load customers.csv as cust -dlim ","
Loaded customers.csv as 'cust' (15,000 rows x 5 cols) [sep=,].
```

### Glob Ingestion
Ingest multiple partition files matching a glob pattern into a single unified table:

```text
pytae> load "sales_2025/part_*.parquet" as sales_2025
Loaded 12 files matching 'sales_2025/part_*.parquet' as 'sales_2025' (1,200,000 rows x 8 cols).
```

### Sample Datasets (`sample:<name>`)
Quickly load bundled demo datasets using the explicit `sample:` prefix:

```text
pytae> df = sample:penguins
Loaded penguins.parquet as 'df' (344 rows x 7 cols).

pytae> iris = sample:iris
Loaded iris.parquet as 'iris' (150 rows x 5 cols).
```
Available bundled samples: `penguins`, `iris`, `tips`, `titanic`, `diamonds`, `flights`, `planets`.

---

## Multi-Table Workbench Operations

### Listing Tables (`status table`, `status table -v`)
View active dataset details and all loaded tables in memory, their shapes, and source files:

```text
pytae [orders, cust]> status table
Table          : orders (orders.parquet) [active]
Shape          : 100,000 rows x 6 columns
Table memory   : ~14.20 MB
Status         : active

Loaded Tables (2):
 * orders      : 100,000 rows x 6 cols (orders.parquet) [active]
   cust        : 15,000 rows x 5 cols (customers.csv)
```

Use `status table -v` to inspect column lists and per-table memory footprint:
```text
pytae [orders, cust]> status table -v
Loaded Tables (2):
 * orders      : 100,000 rows x 6 cols (~14.20 MB) (orders.parquet) [active]
       Columns (6): order_id, customer_id, order_date, amount, status, items
   cust        : 15,000 rows x 5 cols (~1.12 MB) (customers.csv)
       Columns (5): customer_id, name, email, signup_date, country
Total Tables: ~15.32 MB | Process RAM: ~128.5 MB
```

> [!NOTE]
> Bare `tables` is disabled in favor of the singular `status table` command.

### Switching Active Tables (`use <name>`)
Switch the active cursor to another table using `use <name>` (e.g. `use orders`, `use df`, `use cust`):

```text
# Switch active dataset to cust
pytae [orders, cust]> use cust
Switched active dataset to 'cust'. Active shape: (15,000, 5)

# Inspect a table's dimensions without switching active cursor:
pytae [orders, cust]> orders
orders: 100,000 rows x 6 cols (tip: 'use orders' to switch active dataset)
```

> [!NOTE]
> Bare table names (like `orders` or `df`) display table dimensions without altering the active table cursor. To switch the active table, explicitly use `use <name>`.

### Renaming Tables (`rename <old> <new>`)
Rename an in-memory dataset via instant $O(1)$ zero-copy pointer reassignment:

```text
# Rename table df1 to customers
pytae [df1, orders]> rename df1 customers
Renamed table 'df1' to 'customers'.
pytae [customers, orders]>
```
All references in the multi-table workbench, table source tracking, and active cursor update instantaneously without copying underlying Arrow memory buffers.

### Subject-First Execution (`<tbl> -<cmd>`)
Execute commands on non-active tables without switching cursors:

```text
# Inspect cust without switching active table away from orders
pytae [orders, cust]> cust -head 3
pytae [orders, cust]> cust -shape
(15,000, 5)

# Transform cust directly
pytae [orders, cust]> cust -filter "country == 'US'"
-> cust: 9,200 rows x 5 cols
```

### Multi-Table Joins (`-join`)
Join loaded tables on shared key columns:

```text
# Left join cust into orders on customer_id
pytae [orders, cust]> orders -join cust on=customer_id how=left

# Join with different column names on left and right
pytae [orders, cust]> orders -join cust on=cust_id:id how=inner

# Join and export directly to file in one step
pytae [orders, cust]> orders -join cust on=customer_id -o merged.parquet
```
Supported join types: `how=left`, `how=inner`, `how=outer`, `how=semi`, `how=anti`, `how=cross`.

### Assigning Results (`<var> = <tbl> -<pipeline>`)
Create new tables from transformations or joins without modifying the original:

```text
# Create a derived table (orders remains untouched)
pytae [orders, cust]> big_orders = orders -filter "total > 500"
Created 'big_orders' (12,400 rows x 6 cols).

# Assign join result to a new table
pytae [orders, cust, big_orders]> enriched = orders -join cust on=customer_id
Created 'enriched' (100,000 rows x 10 cols).
```

---

## In-Memory Pipeline Transformations

### Full CLI Pipeline Verbs
All standard Pytae CLI transformation flags operate natively in the REPL with 1:1 syntax parity:

```text
# 1. Filter rows
pytae [df: 344x7]> -filter "species == 'Gentoo' and body_mass_g > 4000"
-> df: 124 rows x 7 cols

# 2. Add or mutate columns
pytae [df: 124x7]> -mutate "mass_kg = body_mass_g / 1000.0, heavy = mass_kg > 4.5"
-> df: 124 rows x 9 cols

# 3. Project or exclude columns
pytae [df: 124x9]> -select "species,island,mass_kg,!heavy"
-> df: 124 rows x 3 cols

# 4. Sort rows
pytae [df: 124x3]> -arrange "mass_kg desc"

# 5. Grouped aggregation
pytae [df: 124x3]> -by island -agg "avg_mass=mass_kg:mean, count=count"
-> df: 1 rows x 3 cols
```

### Assignment vs. Bare Exploration Semantics
Pytae draws a clean distinction between **bare exploratory previews** and **state mutations**:

- **Bare preview (`-pivot ...`, `-filter ...`)**: If executed without variable assignment (`df = ...`) or output redirection (`-o ...`), preview commands like `-pivot` display the formatted table in your terminal for immediate inspection **without altering the shape of the underlying table**.
- **Explicit assignment (`df = df -pivot ...` or `summary = df -pivot ...`)**: Mutates the table in memory and registers a state change in history.
- **Why this matters**: Bare exploratory previews are kept in your interactive terminal history, but are automatically excluded from saved replay scripts (`exit -s`) so automated batch scripts only contain true state changes.

---

## Non-Destructive Data Inspection

Non-destructive inspection flags display schema, dimensions, or previews without altering or truncating active tables in memory:

### Previews (`-head`, `-tail`, `-sample`)
```text
pytae> -head 5           # Preview first 5 rows
pytae> -tail 5           # Preview last 5 rows
pytae> -sample 10        # Preview 10 random sample rows
```

### Metadata (`-shape`, `-cols`, `-schema`, `-dtype`, `-nulls`)
```text
pytae> -shape            # Print (rows, cols)
(344, 7)

pytae> -cols             # Column names in file order
pytae> -cols asc         # Sorted alphabetically ascending
pytae> -cols desc        # Sorted alphabetically descending
pytae> -cols mass        # Filter column names by substring

pytae> -schema           # Full structured breakdown (types, nulls, cardinality)
pytae> -dtype            # Column data types (supports -dtype asc)
pytae> -nulls            # Missing value counts per column
```

### Summaries (`-glimpse`, `-describe`, `-freq`)
```text
pytae> -glimpse          # Transposed schema with sample values (matches dplyr::glimpse)
pytae> -describe         # Descriptive statistics (mean, std, min, max, quartiles)
pytae> -freq species     # Frequency distribution table for column
```

### Comparing Datasets (`-diff <tbl1> <tbl2>`)
Compare two in-memory tables, compare the active dataset against another table, or compare against a saved checkpoint with optional key alignment (`on=...`) and numeric tolerance (`-tol ...`). In alignment with Pytae's CLI standard where all dataset verbs use a leading hyphen, `-diff` requires a single hyphen (bare `diff` is rejected with educational guidance):

```text
# Compare active table against orders_backup
pytae [orders]> -diff orders_backup

# Explicitly compare two loaded tables
pytae> -diff df1 df2

# Align rows by primary key before comparing values (reports added/removed keys & mismatched cells)
pytae> -diff df1 df2 on=customer_id

# Target a specific table as left operand
pytae> df1 -diff df2 on=customer_id

# Composite multi-column keys and numeric tolerance
pytae> -diff df1 df2 on="store_id, product_id" -tol 0.001

# Compare active table against a saved checkpoint
pytae [df: 344x7]> -diff snap1 on=id

# Embedded spec syntax (identical to CLI)
pytae> -diff df1 "df2,on=customer_id"
```

---

## SQL & Python Interop

### ANSI SQL across Tables (`-sql`)
All loaded tables and saved checkpoints are registered in Polars SQLContext. You can query across tables using full ANSI SQL:

```text
pytae [orders, cust]> -sql "SELECT orders.order_id, cust.name, orders.total FROM orders JOIN cust ON orders.cust_id = cust.id WHERE orders.total > 200"
shape: (1,240, 3)
┌──────────┬─────────────┬────────┐
│ order_id ┆ name        ┆ total  │
│ ---      ┆ ---         ┆ ---    │
│ i64      ┆ str         ┆ f64    │
╞══════════╪═════════════╪════════╡
│ 1001     ┆ Jane Doe    ┆ 245.50 │
│ 1004     ┆ John Smith  ┆ 512.00 │
└──────────┴─────────────┴────────┘
```

### Explicit Table Names in SQL
In the REPL, every dataset in memory is registered in Polars SQLContext under its exact user-assigned variable name (e.g. `df`, `df2`, `orders`, `cust`), alongside saved checkpoints. No synthetic aliases (`this`, `self`, `data`) are registered, guaranteeing pure ANSI SQL and eliminating variable shadowing:

```text
# Query loaded tables directly by their variable names
pytae [orders, cust]> -sql "SELECT orders.order_id, cust.name FROM orders JOIN cust ON orders.cust_id = cust.id"

# Self-contained single-table queries
pytae [customers]> -sql "SELECT country, COUNT(*) as n FROM customers GROUP BY country"
```

### SQL Variable Assignment (`df3 = -sql "..."`)
Assign SQL query results directly to new or existing tables:

```text
pytae [orders, cust]> high_value = -sql "SELECT * FROM orders WHERE total > 1000"
Created 'high_value' from SQL query (520 rows x 6 cols).
```

### Fluent Python Execution (`py <expr>`)
Evaluate Polars Python expressions directly against the workbench:

```text
pytae [df: 344x7]> py pldf.group_by("species").len()
shape: (3, 2)
┌───────────┬─────┐
│ species   ┆ len │
│ ---       ┆ --- │
│ str       ┆ u32 │
╞═══════════╪═════╡
│ Adelie    ┆ 152 │
│ Gentoo    ┆ 124 │
│ Chinstrap ┆ 68  │
└───────────┴─────┘
```

---

## Multi-Line Input & Continuation

The REPL supports multi-line inputs across pipelines, SQL queries, session variables, and bare Python blocks. When input is incomplete, the prompt switches to a clean `... ` continuation prompt:

### Pipeline Line Continuation (`\`)
Long analytical pipelines can be split across multiple lines using a trailing backslash `\`:

```text
pytae [df: 344x7]> df = -filter "species == 'Gentoo'" \
...   -mutate "kg = body_mass_g / 1000.0" \
...   -select "species, island, kg" \
...   -arrange "kg desc"
Updated 'df' (124 rows x 3 cols).
```

### Multi-Line SQL Queries
Complex ANSI SQL queries can span multiple lines using unclosed double or single quotes:

```text
pytae [df: 344x7]> -sql "
...   SELECT
...     species,
...     island,
...     AVG(body_mass_g) AS avg_mass,
...     COUNT(*) AS n
...   FROM df
...   GROUP BY species, island
...   ORDER BY avg_mass DESC
... "
```
This syntax also works for SQL table assignment (`summary = -sql "..."`).

### Multi-Line Variables & Data Structures
Dictionaries and lists can be authored across multiple lines using unclosed brackets or braces:

```text
pytae> cfg = {
...   "min_mass": 3200,
...   "island": "Biscoe",
...   "species": ["Gentoo", "Adelie"]
... }
Assigned variable @cfg = {'min_mass': 3200, 'island': 'Biscoe', 'species': ['Gentoo', 'Adelie']}
```

### Bare `py` Python Block Mode
Entering bare `py` initiates Python block mode. You can write multi-line Python code, loops, functions, and statements, terminating the block with an empty line (pressing Enter on an empty line):

```text
pytae [df: 344x7]> py
... for species, sub_df in pldf.group_by("species"):
...     print(f"Species: {species[0]} has {len(sub_df)} records")
... 
Species: Adelie has 152 records
Species: Gentoo has 124 records
Species: Chinstrap has 68 records
```
Any standard outputs (`print(...)`) are captured and displayed directly in the REPL.

### Aborting Multi-Line Buffers (`Ctrl+C`)
Pressing `Ctrl+C` while in a multi-line continuation prompt immediately cancels the current input buffer, prints `^C`, and returns to the active single-line REPL prompt (`pytae> `) without executing any partial code.

---

## Session Variables & Parameters (`@var`)

The Pytae REPL provides lightweight session parameters and variables without Python runtime overhead or fragile object pickling. You can define constants, threshold limits, lists, and configuration dictionaries, reference them cleanly inside `-filter`, `-mutate`, and `-sql` expressions using the `@` prefix, and have them automatically saved and restored with checkpoints.

### Defining Variables (`<name> = <literal>`)

Assign JSON-serializable primitives (`int`, `float`, `str`, `bool`, `list`, `dict`, `None`) directly in the REPL:

```text
# Scalar numbers and strings
pytae> min_mass = 3500
Set @min_mass = 3500

pytae> label = "Gentoo"
Set @label = 'Gentoo'

pytae> factor = 1.25
Set @factor = 1.25

# Lists and collections
pytae> target_species = ['Gentoo', 'Adelie']
Set @target_species = ['Gentoo', 'Adelie']

# Dictionaries and nested configs
pytae> cfg = {'min_mass': 3200, 'island': 'Biscoe', 'limits': {'depth': 15.0}}
Set @cfg = {'min_mass': 3200, 'island': 'Biscoe', 'limits': {'depth': 15.0}}
```

### Supported Types & Safety Guarantees

Variables are strictly restricted to JSON-serializable primitives:
- **Primitives**: `int`, `float`, `str`, `bool`, `None`
- **Sequences**: `list` (tuples are converted to lists)
- **Mappings**: `dict` (keys must be strings)

Arbitrary Python class instances, lambda functions, and unpicklable objects are disallowed. This guarantees 100% portability, fast disk I/O, and zero dependency on Python pickle.

### Inspection & Key Traversal (`@var`, `@var.key`, `@var[idx]`)

Type any variable prefixed with `@` to inspect its current value and data type without mutating workbench state. Nested dictionary keys and list indices can be accessed using standard dot (`.`) or bracket (`[]`) notation:

```text
pytae> @min_mass
@min_mass = 3500 (int)

pytae> @target_species[0]
@target_species[0] = 'Gentoo' (str)

pytae> @cfg.min_mass
@cfg.min_mass = 3200 (int)

pytae> @cfg['island']
@cfg['island'] = 'Biscoe' (str)

pytae> @cfg.limits.depth
@cfg.limits.depth = 15.0 (float)
```

If an undefined variable or key is referenced, Pytae prints an informative error:
```text
pytae> @unknown
pytae: variable '@unknown' is not defined. Use 'status var' to view defined variables.
```

### Using Variables in Pipelines (`-filter`, `-mutate`, `-sql`)

Use `@var` in pipeline expressions across filters, mutations, and SQL queries:

```text
# Scalar threshold filter
pytae [df: 344x7]> df = -filter "body_mass_g > @min_mass"

# List membership filter
pytae [df: 344x7]> df = -filter "species in @target_species"

# Dictionary lookup / nested config filter
pytae [df: 344x7]> df = -filter "body_mass_g > @cfg.min_mass and island == @cfg['island']"

# Feature mutation using scalar parameter
pytae [df: 344x7]> df = -mutate "kg = body_mass_g / @factor"

# ANSI SQL query with parameterized variables
pytae [df: 344x7]> -sql "SELECT species, AVG(body_mass_g) as avg_mass FROM df WHERE body_mass_g > @min_mass GROUP BY 1"
```

### Inspecting and Removing Variables (`status var`, `rm var`)

#### Listing Variables (`status var`)
```text
pytae> status var
Session Variables (3):
  * @min_mass         : 3500 (int)
  * @target_species   : ['Gentoo', 'Adelie'] (list)
  * @cfg              : {'min_mass': 3200, 'island': 'Biscoe'} (dict)
```

Use `status var -v` for verbose metadata including the raw formatted JSON output:
```text
pytae> status var -v
Session Variables (3):
  * @min_mass         : 3500 (int)
  * @target_species   : ['Gentoo', 'Adelie'] (list)
  * @cfg              : {'min_mass': 3200, 'island': 'Biscoe'} (dict)

Raw JSON:
{
  "min_mass": 3500,
  "target_species": [
    "Gentoo",
    "Adelie"
  ],
  "cfg": {
    "min_mass": 3200,
    "island": "Biscoe"
  }
}
```

Inspect an individual variable in detail with `status var <name>`:
```text
pytae> status var cfg
Variable '@cfg':
  Type  : dict
  Length: 2
  Value :
{
  "min_mass": 3200,
  "island": "Biscoe"
}
```

#### Deleting Variables (`rm var <name>`, `rm var *`)
```text
# Delete a specific variable
pytae> rm var min_mass
Removed variable '@min_mass'.

# Delete all session variables at once
pytae> rm var *
Removed all session variables (2 removed).
```

### Checkpoint & Session Persistence (`vars.json`)

Session variables are fully integrated into Pytae's checkpoint and persistent session architecture:
1. When you run `checkpoint <name>`, Pytae creates `vars.json` alongside the dataset snapshots in the checkpoint directory and records variable counts in `meta.json`.
2. When you run `restore <name>`, Pytae clears current session variables and restores the exact variable snapshot from `vars.json`.
3. Persistent session storage (`set new_session = <name>`, `set save_session = <name>`) preserves `vars.json` so your configuration dictionaries and parameter thresholds persist across terminal restarts.

```text
pytae [df]> min_mass = 4500
Set @min_mass = 4500

pytae [df]> checkpoint baseline
Saved checkpoint 'baseline' (1 tables: df, 1 variables: @min_mass).

pytae [df]> rm var *
Removed all session variables (1 removed).

pytae [df]> restore baseline
Restored checkpoint 'baseline' (1 tables: df; active: df, 1 variables: @min_mass).

pytae [df]> @min_mass
@min_mass = 4500 (int)
```

### Namespace Isolation & Collision Prevention

To guarantee predictable execution and prevent confusing state collisions:
1. **Reserved Command Protection**: Variable names cannot match built-in verbs or REPL commands (`filter`, `select`, `mutate`, `status`, `checkpoint`, `restore`, etc.).
2. **Table / Variable Collision Prevention**:
   - Assigning a variable with the name of an existing table produces an explicit error:
     `pytae: '<name>' is already an active table; cannot assign as a variable. Use 'rm table <name>' first.`
   - Assigning a table or loading a dataset with the name of an existing variable produces an explicit error:
     `pytae: '<name>' is already a session variable; cannot assign as a table. Use 'rm var <name>' first.`
   - Renaming a table to match an existing variable is similarly rejected.

### Removing Tables (`rm table <name>`, `rm table *`)
Purge tables from memory when they are no longer needed:

```text
# Remove specific table by variable name
pytae [df1, df2]> rm table df1
Removed table 'df1'. Switched active dataset to 'df2'.

# Remove all loaded tables at once
pytae [orders, cust, big_orders]> rm table *
Removed all 3 loaded tables. No tables remain loaded.
```

> [!NOTE]
> Explicit category syntax (`rm table <name>`, `rm table *`, `rm checkpoint <name>`, or `rm checkpoint *`) is required. Categorical consistency eliminates ambiguity between in-memory tables and on-disk checkpoints. Deleting persistent sessions is managed directly via standard OS file operations (e.g. `rm -rf ./<name>`).

### Immediate Memory Deallocation & OS Trimming
Unlike standard Python shells that retain memory pages in process heaps:
1. **Zero Lingering References**: Running `rm table <name>` or `rm table *` purges the table from `self.tables`, `self.orig_tables`, and `self.initial_tables`.
2. **OS Memory Trimming**: Pytae automatically triggers [`_release_memory()`](file:///Users/maddy/Documents/my_repos/pytae/src/pytae/repl.py#L92-L131), which calls `gc.collect()` and instructs the OS memory manager to reclaim freed pages:
   - **macOS**: Resident pages trimmed and measured live via `mach_task_basic_info`.
   - **Windows**: `SetProcessWorkingSetSize(-1, -1)` and `K32EmptyWorkingSet` trim unused working set pages back to the Windows kernel.
   - **Linux**: `libc.malloc_trim(0)` flushes unmapped heap arenas back to the OS.

### Diagnostics & Inspection (`status`, `status table`, `status session`)
Pytae unifies system diagnostics under the `status` command family:

Running bare `status` lists the available inspection categories:
```text
pytae> status
pytae: please specify a status category to inspect:
  - status session [path] [-v] : Inspect active session or a session on disk
  - status table [name] [-v]   : Inspect active table schema or loaded table inventory
  - status checkpoint [name]   : Inspect saved checkpoints or checkpoint details
  - status var [name] [-v]     : Inspect session variables, parameters and constants
```

Inspect active table dimensions, memory footprint, and process status:
```text
pytae [df: 344x7]> status table
Table          : df (penguins.parquet) [active]
Shape          : 344 rows x 7 columns
Table memory   : ~0.02 MB
Status         : active
```

Use `status table -v` (or `status table <name> -v`) to expand the column schema and data types:
```text
pytae [df: 344x7]> status table -v
Table          : df (penguins.parquet) [active]
Shape          : 344 rows x 7 columns
Table memory   : ~0.02 MB
Status         : active
Columns (7):
  species             : String
  island              : String
  bill_length_mm      : Float64
  bill_depth_mm       : Float64
  flipper_length_mm   : Float64
  body_mass_g         : Float64
  sex                 : String
```

Inspect the active session state, disk storage path, and environment with `status session`:
```text
pytae:my_lab [df: 344x7]> status session
=== REPL Session Status ===
Session Name  : my_lab (storage: ./my_lab)
Active Table  : df
Loaded Tables : 1 tables loaded
Checkpoints   : 2 saved
Process RAM   : ~129.2 MB (PID 7158)
------------------------------------------------------------
(Tip: Use 'status table [name]' for table details, 'status checkpoint [name]' for checkpoints)
```

Use `status session -v` for verbose diagnostics including session flight recorder path and active settings:
```text
pytae:my_lab [df: 344x7]> status session -v
=== REPL Session Status ===
Session Name  : my_lab (storage: ./my_lab)
Active Table  : df
Loaded Tables : 1 tables loaded
Checkpoints   : 2 saved
Session Logs  : ~/.pytae/history/history_2026_11_03_18_00_29.txt
Settings      : checkpoint_format=ipc, save_code=off, max_rows=10, max_cols=None, float_precision=None
Process RAM   : ~129.4 MB (PID 7158)
------------------------------------------------------------
```

---

## State Navigation & History

### Reset Hierarchy (`reset`, `reset <tbl>`, `reset initial`)
* **`reset`**: Reverts all tables in the workbench to the **latest saved checkpoint**. If no checkpoints exist, reverts to the initial file read state.
* **`reset <table_name>`**: Reverts **only the specified table** to the latest checkpoint (or initial read), leaving all other loaded tables untouched.
* **`reset <table_name> initial`**: Reverts **only the specified table** strictly to its initial file read state, bypassing checkpoints.
* **`reset initial`**: Strictly reverts **all tables** across the entire workbench back to their initial file read state, bypassing all intermediate checkpoints.

### In-REPL History Audit Log (`history`)
Inspect every command executed in the session as a clean, numbered list:

```text
pytae [df: 344x7]> history
Session History:
   1: df = penguins.parquet
   2: checkpoint v1
   3: -filter "species == 'Adelie'"
   4: rm df

pytae [df: 344x7]> history 3     # Show only the last 3 commands
```

---

## Checkpoints (Disk-Backed & RAM-Isolated)

### Saving Checkpoints (`checkpoint <name>`)
Save a complete snapshot of the entire workbench to disk:

```text
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust).
```
- **Zero RAM Overhead**: Tables are written to disk storage (`.ipc` or `.parquet`). Checkpoints consume **0 MB of active RAM**.
- **Default Storage Location (Ephemeral Mode)**:
  When running `pytae -i` without binding to a named session, checkpoints are written to an isolated, secure OS temporary folder (e.g. `/tmp/pytae_cp_xxxxxx/` or `$TMPDIR/pytae_cp_xxxxxx/` on macOS/Linux, `%TEMP%\pytae_cp_xxxxxx\` on Windows).
  - **Automatic Cleanup**: When you exit or close the REPL, the temporary checkpoint folder is automatically purged from disk, leaving zero lingering files on your machine.
  - **Inspect Location**: Run `status checkpoint -v` anytime to inspect the exact temporary directory path and on-disk byte sizes.
- **Mid-Session Promotion**:
  If you start in ephemeral mode, save several checkpoints, and decide you want to keep them permanently, simply bind a session name:
  ```text
  pytae> set new_session = my_permanent_project
  ```
  Pytae immediately promotes all existing temporary checkpoints into `./my_permanent_project/` (or your target path) while keeping all in-memory tables loaded.
- **Milestone Established**: Creating a checkpoint frees intermediate memory while establishing a safe restore point.

### Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)
```text
# List all checkpoints and their constituent tables
pytae> status checkpoint
Saved Checkpoints (2):
  - baseline       : orders (100,000x6), cust (15,000x5) [active: cust]
  - cleaned        : orders (82,000x6) [active: orders] [parquet]

# Detailed snapshot file listing
pytae> status checkpoint -v

# Delete a single checkpoint from disk
pytae> rm checkpoint cleaned
Removed checkpoint 'cleaned'.

# Delete all checkpoints
pytae> rm checkpoint *
Cleared all saved checkpoints.
```

### Restoring Entire Workbench (`restore <name>`)
Restore the workbench to any saved checkpoint milestone:

```text
pytae [orders, cust, scratch_df]> restore baseline
Restored checkpoint 'baseline' (2 tables: orders, cust; active: cust).
```
*All post-checkpoint scratch tables (`scratch_df`) are automatically dropped and garbage collected. Active RAM strictly matches the checkpoint state.*

### Reloading After `rm *` via `restore <name>`
Because checkpoints live on **disk**, running `rm *` clears active RAM but leaves all checkpoints completely safe!

```text
pytae [df1, df2]> checkpoint abc
Saved checkpoint 'abc' (2 tables: df1, df2).

pytae [df1, df2]> rm *
Removed all 2 loaded tables. No tables remain loaded.
pytae> 

# Restore entire workbench from checkpoint:
pytae> restore abc
Restored checkpoint 'abc' (2 tables: df1, df2; active: df1).
```

> [!NOTE]
> Checkpoints are state milestones and are restored strictly via `restore <name>` (or `reset`). Variable assignment (`df = abc`) is reserved exclusively for file paths, table copies, and query results. Trying to assign a checkpoint directly (`df = abc`) is rejected with a helpful suggestion to use `restore abc`.
>
> For configuring whether checkpoints are stored as fast uncompressed Arrow IPC or compressed Parquet, see [Checkpoint Storage Format (`set checkpoint_format`)](#checkpoint-storage-format-set-checkpoint_format--parquetipc).

---

## Persistent REPL Sessions

Persistent sessions allow you to save your workbench checkpoints to disk and resume your analysis across terminal restarts or system reboots.

### Unified Path-First Session Architecture

Pytae sessions are 100% path-first and self-contained:
- **Project-Local by Default**: A named session created in your terminal lives right inside the current working directory (`./<session_name>/`) or at any explicit relative/absolute filesystem path you specify (e.g. `/Volumes/ExternalSSD/my_lab`).
- **Standard Session Manifest**:
  - `session.json`: JSON manifest storing session metadata (`name`, `created_at`, `updated_at`, `checkpoint_format`, `checkpoints`).
  - `checkpoints/`: Directory containing IPC/Parquet snapshot subdirectories and frozen table states.
  - `.pytae_session`: Marker file ensuring the directory is recognized as an active Pytae session.
- **Home Directory Support Files (`~/.pytae/`)**:
  - `~/.pytae/code/`: Default home for generated replayable pipeline scripts.
  - `~/.pytae/history/`: Flight recorder logging interactive keystrokes and queries.

### Inspecting & Managing Sessions (`status session`, `sessions`)

```text
# Inspect active session name, disk path, checkpoints, and RAM
pytae:my_project [df1]> status session
=== REPL Session Status ===
Session Name  : my_project (storage: ./my_project)
Active Table  : df1
Loaded Tables : 1 tables loaded
Checkpoints   : 2 saved
Process RAM   : ~129.5 MB (PID 95089)

# Verbose session status (includes log file path and active configuration)
pytae:my_project [df1]> status session -v

# Inspect an external session directory on disk without loading it into memory
pytae> status session ./other_project -v

# List persistent sessions in current working directory (or search path)
pytae> sessions
Sessions Directory: /Users/username/my_analysis

Saved Sessions (2 found):
  - my_project
    Path:        /Users/username/my_analysis/my_project
    Status:      Ready
  - sales_q3
    Path:        /Volumes/ExternalSSD/sales_q3
    Status:      [Offline / Unreachable]

# From the command line outside the REPL
$ pytae -i                      # Start REPL (inside run: set load_session = ./my_project)
$ pytae -sessions              # List sessions in current working directory
$ pytae -sessions -v           # Verbose breakdown of checkpoints and formats
$ pytae -sessions /Volumes/ExternalSSD/sessions  # Scan target path for sessions

# Remove a persistent session using standard OS file commands
$ rm -rf ./old_project
```

---

## REPL Configuration (`set`)

The `set` command is the central control hub for inspecting and configuring your interactive session workbench. Settings can be queried bare, set individually, or combined together on a single line.

### Querying Settings (`set`, `set <key>`)

Running `set` with no arguments displays all current configuration values and available options:

```text
pytae> set
new_session       = (options: <name>, <path>) (e.g. set new_session = rwa_analysis)
load_session      = (options: <name>, <path>) (e.g. set load_session = rwa_analysis)
save_session      = none (options: <name>, <path>, move = true, overwrite = true)
checkpoint_format = ipc (options: ipc, parquet)
save_code         = none (options: <path>, none)
max_rows          = 10 (options: <int>, default)
max_cols          = all (options: <int>, all, default)
float_precision   = auto (options: <int>, auto, default)
comma             = off (options: on, off)
```

To query a single setting without modifying it, run `set <key>`:

```text
pytae> set checkpoint_format
checkpoint_format = ipc (options: ipc, parquet)

pytae> set save_code
save_code = none (options: <path>, none)
```

### Starting a Session (`set new_session = <name|path>`)

Start a new persistent session on disk. If tables are already loaded into the workbench, they remain active in memory while a fresh checkpoint history is established:

```text
# Start session in current working directory (./my_lab)
pytae [df: 344x7]> set new_session = my_lab
Started new session 'my_lab' at '/Users/username/my_analysis/my_lab' (1 tables active in workbench).
pytae:my_lab [df: 344x7]>

# Start session at a custom absolute or relative directory path
pytae> set new_session = /Volumes/ExternalSSD/rwa_analysis
Started new session 'rwa_analysis' at '/Volumes/ExternalSSD/rwa_analysis'.
pytae:rwa_analysis>
```

### Loading a Session (`set load_session = <name|path>`)

Switch directly to an existing persistent session from disk, automatically restoring its latest checkpoint:

```text
# Load session from current working directory
pytae> set load_session = sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v2'.
pytae:sales_q3 [sales_q3: 150,000x12]>

# Load session from an explicit path
pytae> set load_session = /Volumes/ExternalSSD/pytae_sessions/sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v2'.
```

### Saving / Relocating a Session (`set save_session = <name|path>`)

Snapshot or clone the current session checkpoints under a new name or directory:

```text
# Clone/snapshot session to a new name in current directory
pytae:my_lab> set save_session = my_lab_backup
Saved session 'my_lab' to '/Users/username/my_analysis/my_lab_backup'.

# Relocate (move) active session directory to new path
pytae:my_lab> set save_session = /Volumes/ExternalSSD/my_lab, move = true
Relocated session to '/Volumes/ExternalSSD/my_lab'.

# Safely replace an existing session directory with a clean slate
pytae:my_lab> set save_session = my_lab_backup, overwrite = true
Overwrote existing session 'my_lab_backup' at '/Users/username/my_analysis/my_lab_backup'.
```

> [!NOTE]
> If the destination session already exists at that path, Pytae requires `overwrite = true` (or `session save <name> -overwrite`) to prevent accidental destruction of existing session work. Overwriting completely clears stale ghost checkpoints from the destination. Saving within the current active session does not require `overwrite = true`.

### Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`, `convert = all`)

Control the on-disk serialization format used for session checkpoints:

- **`ipc` (Default)**: Uncompressed Arrow IPC streaming format (`.ipc`). Delivers maximum write and read speed for near-instant `checkpoint` and `restore` operations.
- **`parquet`**: Compressed columnar Parquet format (`.parquet`). Minimizes disk usage on storage-constrained environments, USB drives, or shared networks.

#### Future-Only by Default (Zero Latency)
By default, changing the checkpoint format applies instantly to all subsequent checkpoints without blocking or freezing the REPL:

```text
# Switch future checkpoints to compressed Parquet format
pytae> set checkpoint_format = parquet
Set checkpoint_format = parquet (new checkpoints will be saved as compressed Parquet).
Note: 2 existing checkpoint(s) remain in IPC format. Run 'set checkpoint_format = parquet, convert = all' to re-encode them.
```

*Pytae automatically detects formats during `restore`, allowing IPC and Parquet checkpoints to coexist and be used interchangeably within the same session.*

#### Re-Encoding Existing Checkpoints (`convert = all`)
To reclaim disk space immediately by converting all prior checkpoints in the active session:

```text
# Convert all existing checkpoints to Parquet and set future format
pytae> set checkpoint_format = parquet, convert = all
Converting 2 existing checkpoint(s) to parquet...
  - cp1: converted (320.0 MB -> 62.4 MB)
  - cp2: converted (320.0 MB -> 64.1 MB)
All 2 checkpoint(s) converted. Set checkpoint_format = parquet.

# Or convert existing checkpoints to the currently active format
pytae> set convert = all
```

### Replay Script Auto-Save (`set save_code = <path>`)

Designate a file path to automatically capture and write your session's replayable command script upon exit (also supported via alias `save_commands`):

```text
# Enable auto-save on exit
pytae> set save_code = pipeline.txt
Set save_code = 'pipeline.txt' (session commands will be auto-saved here on exit).

# Disable auto-save
pytae> set save_code = none
Disabled auto-saving commands on exit.
```

When you quit the REPL via `exit` or <kbd>Ctrl+D</kbd>, Pytae automatically writes the clean, executable pipeline script.

### Display Preferences (`set max_rows`, `max_cols`, `float_precision`, `comma`)

Customize how datasets and tables are formatted and displayed during interactive inspection (`-head`, `-tail`, `-sample`, `-describe`, `py <expr>`, and pipeline executions):

- **Row Truncation (`set max_rows = <int>|default`, alias: `rows`)**:
  Controls the maximum number of rows printed in table previews. Defaults to `10`.
  ```text
  pytae> set max_rows = 25
  Set max_rows = 25.

  pytae> set rows = default
  Set max_rows = 10 (default).
  ```

- **Column Truncation (`set max_cols = <int>|all|default`, alias: `cols`)**:
  Limits the maximum number of columns displayed in wide tables. Defaults to `all` (unconstrained).
  ```text
  pytae> set max_cols = 5
  Set max_cols = 5.

  pytae> set cols = all
  Set max_cols = all (show all columns).
  ```

- **Floating-Point Precision (`set float_precision = <int>|auto|default`, alias: `precision`)**:
  Sets the number of decimal digits rendered for floating-point numbers during terminal table display. Defaults to `auto`.
  ```text
  pytae> set float_precision = 2
  Set float_precision = 2.

  pytae> set precision = auto
  Set float_precision = auto (default precision).
  ```
  > [!NOTE]
  > `float_precision` is strictly a terminal display preference. It never modifies the underlying DataFrame in memory. Exports to file (`-o result.parquet`, `-o result.csv`) and clipboard (`-o clip`) always retain the full, unrounded IEEE 754 precision.

- **Thousands Comma Separator (`set comma = on|off`)**:
  Toggles comma grouping separators for large numeric values (both integers and floating-point numbers) during terminal table display. Defaults to `off`.
  ```text
  pytae> set comma = on
  Set comma = on (numeric values will be formatted with thousands comma separators for display).

  pytae> df -head 2
  shape: (2, 2)
  ┌───────────┬──────────────┐
  │ count     ┆ revenue      │
  │ ---       ┆ ---          │
  │ i64       ┆ f64          │
  ╞═══════════╪══════════════╡
  │ 1,234,567 ┆ 1,234.57     │
  │ 8,910     ┆ 9,876,543.21 │
  └───────────┴──────────────┘

  pytae> set comma = off
  Set comma = off.
  ```
  > [!NOTE]
  > `comma` formatting is strictly for visual display. Numerical columns remain typed `Int64` / `Float64` in memory. Copying via `-o clip` or exporting to file outputs raw unformatted numbers (`1234567`, not `"1,234,567"`), preserving calculation readiness in Excel, Google Sheets, and scripts.

### Combining Multiple Settings on One Line

Multiple settings can be chained in a single command using comma, semicolon, space, or repeated `set` syntax:

```text
# Start a named session in current directory and configure auto-save replay script
pytae> set new_session = my_lab, save_code = pipeline.txt

# Start a session at a specific path and set checkpoint compression
pytae> set new_session = /Volumes/Share/sessions/analytics, checkpoint_format = parquet

# Clone active session and relocate directory simultaneously
pytae> set save_session = /Volumes/ExternalSSD/my_lab, move = true

# Configure replay script destination and checkpoint compression together
pytae> set save_code = build.txt, checkpoint_format = parquet
```

---

## Session Export & Replay Scripts

Pytae provides a powerful workflow to turn interactive exploration into portable, automated pipeline scripts that run anywhere.

> [!TIP]
> To configure automatic replay script generation upfront before working, use [`set save_code = <path>`](#replay-script-auto-save-set-save_code--path).

### Exit-Time Export (`exit -s [path]`)

Save pure data transformation commands directly when exiting. Output paths always resolve to the **current working directory (`cwd`)**, and Pytae prints the full absolute path as an unambiguous reminder and clickable terminal link:

```text
# Save to default ./history.txt in the current working directory
pytae> exit -s
Session commands saved to /Users/maddy/my_analysis/history.txt.
Exiting pytae REPL.

# Save to custom script file in the current working directory
pytae> exit -s transform_orders.txt
Session commands saved to /Users/maddy/my_analysis/transform_orders.txt.
Exiting pytae REPL.
```

### Automatic Replay Script Filtering (`_is_replayable_entry`)
When exporting a replay script, Pytae automatically filters out noise:
- **Excluded**:
  - Checkpoint commands (`checkpoint <name>`, `restore <name>`) — checkpoints are interactive exploration tools; omitting them avoids redundant disk I/O during batch replay.
  - Bare exploratory inspection commands (`-head`, `-tail`, `-describe`, `-cols`, bare `-pivot`, and transient clipboard `-o clip` copies) that do not assign to a variable or export to a persistent file.
  - REPL UI controls and configuration (`tables`, `checkpoints`, `history`, `clear`, `set ...`) — display preferences, timing, and session bindings are never injected into replay scripts, keeping exported pipelines 100% pure and reproducible.
- **Included**:
  - File ingestion commands (`df = ...`, `load ...`).
  - Variable assignments (`orders_clean = orders -filter ...`).
  - Table removals (`rm df1`, `rm *`) to keep batch memory footprints low.
  - Persistent output file exports (`-o clean.parquet`, `-o report.csv`) — transient clipboard copies (`-o clip`) are strictly excluded to prevent failures in headless/CI batch execution.

### Path Canonicalization & Windows UNC Resolution
Replay scripts must be portable across directories:
1. **Absolute Paths**: Relative input paths (`df = ../data/orders.parquet`) are automatically canonicalized to absolute paths in the replay script.
2. **Windows Mapped Drives to UNC**: On Windows, mapped network drives (`Z:\shared\data.parquet`) are automatically resolved to universal UNC network paths (`\\server\share\data.parquet`) using Windows `WNetGetConnectionW`. The script can run on any machine with network access without requiring drive letter mappings.

### Batch Replay Execution (`pytae -i < script.txt`)
Replay your exported script non-interactively or in batch:

```bash
pytae -i < pipeline.txt
```
Pytae executes every transformation line by line, freeing memory on `rm`, and exporting your final outputs.

---

## Shell Integration (`|`)

Pipe any REPL output directly to standard Unix tools:

```text
# Filter column names with grep
pytae [df: 344x7]> -cols | grep mass
body_mass_g

# Search sorted columns on a specific table
pytae [orders, cust]> orders -cols asc | grep id
customer_id
order_id

# Count preview rows with wc
pytae [df: 344x7]> -head 50 | wc -l
54
```
*Note: Pipe characters inside quotes or brackets (e.g. `-filter "a | b"` or regexes) are correctly parsed as expression logic rather than shell pipes.*

---

## Tab Autocompletion & Navigation

The Pytae REPL provides context-aware autocompletion via standard `readline`:

- **Commands & Verbs**: Press `[Tab]` at an empty prompt to view top-level commands (`use`, `diff`, `rename`, `rm`, `set`, `checkpoint`, `restore`, etc.).
- **Flags**: Type `-` and press `[Tab]` to autocomplete CLI pipeline verbs (`-filter`, `-select`, `-mutate`, `-arrange`, `-pivot`, etc.).
- **Table & Checkpoint Names**: Autocompletes loaded tables after `use `, `rename `, `diff `, and `rm `, or checkpoints after `restore `.
- **Column Names**: Inside pipeline flags (`-select `, `-filter `, `-by `, `-arrange `), autocompletes column names of the active dataset or specified table prefix.
- **File Paths**: Autocompletes local filesystem files and directories after `load `, `-o `, or assignment (`df = `).
- **Settings**: Autocompletes configuration keys and options after `set ` (e.g. `set checkpoint_format = ` -> `ipc`, `parquet`, `arrow`).

---

## Complete REPL Command Reference

| Category | Command | Syntax Example | Description | Mutates State? |
|---|---|---|---|---|
| **Ingestion** | Assignment | `df1 = orders.parquet [-nrows 1000]` | Load file into named table variable | Yes |
| | `load` | `load sales.csv as df2 -dlim ";"` | Load file with alias and reader options | Yes |
| | Samples | `df = sample:penguins` | Load bundled sample dataset | Yes |
| **Tables** | `status table` | `status table [-v]` | List loaded tables, shapes, and sources | No |
| | Bare name | `df1` | Display table dimensions without switching cursor | No |
| | `use` | `use df1` | Switch active dataset | Yes (active) |
| | `rename` | `rename df1 customers` | Zero-copy $O(1)$ in-memory table rename | Yes |
| | Subject-first | `df1 -head 5`, `df2 -shape` | Execute command directly on named table | Depends |
| | `rm table` | `rm table df1`, `rm table orders`, `rm table *` | Remove table from memory (immediate OS trim) | Yes |
| **Transform** | `-filter` | `-filter "amount > 100"` | Filter rows by expression | Yes |
| | `-mutate` | `-mutate "tax = amount * 0.1"` | Add or modify columns | Yes |
| | `-select` | `-select "id,name,!notes"` | Column projection and exclusion | Yes |
| | `-arrange` | `-arrange "amount desc"` | Sort rows | Yes |
| | `-by -agg` | `-by cat -agg "total=amt:sum"` | Grouped aggregation | Yes |
| | `-join` | `df1 -join df2 on=cust_id` | Join tables | Yes |
| | Assignment | `df3 = df1 -filter "..."` | Assign pipeline result to new variable | Yes |
| **Inspection** | `-head` / `-tail` | `-head 10`, `-tail 5` | Non-destructive preview of rows | No |
| | `-sample` | `-sample 10` | Non-destructive random row preview | No |
| | `-shape` | `-shape` | Display (rows, columns) | No |
| | `-schema` | `-schema` | Detailed column breakdown and null counts | No |
| | `-cols` | `-cols [asc\|desc\|pattern]` | List column names (supports sorting/filter) | No |
| | `-dtype` / `-nulls` | `-dtype asc`, `-nulls` | Column types and missing value counts | No |
| | `-glimpse` | `-glimpse` | Transposed schema and preview values | No |
| | `-describe` | `-describe` | Statistical summary of numeric columns | No |
| | `-diff` | `-diff df1 df2 [on=id] [-tol 0.01]` | Compare two tables with optional key alignment | No |
| **SQL & Python** | `-sql` | `-sql "SELECT * FROM df1"` | Run ANSI SQL across loaded tables | Yes |
| | SQL Assign | `df4 = -sql "..."` | Create new table from SQL query | Yes |
| | `py` | `py pldf.columns` | Evaluate Python/Polars expression | No |
| **State & Navigation** | `reset` | `reset` | Revert workbench to latest checkpoint | Yes |
| | `reset <tbl>` | `reset df1` | Revert single table to latest checkpoint | Yes |
| | `reset initial` | `reset initial` | Revert workbench to initial file read state | Yes |
| | `history` | `history [N]` | Display numbered audit log of session commands | No |
| **Checkpoints** | `checkpoint` | `checkpoint <name>` | Save snapshot to disk (0 MB RAM) | No |
| | `restore` | `restore <name>` | Restore workbench to named checkpoint | Yes |
| | `status checkpoint` | `status checkpoint [-v]` | List all saved checkpoints on disk | No |
| | `rm checkpoint` | `rm checkpoint <name>`, `rm checkpoint *` | Delete checkpoint(s) from disk | No |
| | `set` | `set checkpoint_format = parquet` | Set format to `parquet` or `ipc` | No |
| **Sessions** | `status session` | `status session [-v]` | Display persistent session name and path | No |
| | `set new_session` | `set new_session = <name\|path>` | Start persistent session on disk | No |
| | `set load_session` | `set load_session = <name\|path>` | Switch session and restore latest checkpoint | Yes |
| | `set save_session` | `set save_session = <name\|path>` | Snapshot or relocate session directory | No |
| | `sessions` | `sessions` | List all persistent sessions on disk | No |
| **Settings** | `set` | `set` | Inspect all configuration settings | No |
| | `set save_code` | `set save_code = pipeline.txt` | Set target replay script path upfront | No |
| | `set checkpoint_format`| `set checkpoint_format = parquet` | Set format to `parquet` or `ipc` | No |
| **Export & Exit**| `-o` | `-o clean.parquet`, `-o clip` | Export dataset to file or clipboard | No |
| | `status` | `status` | Display inspection category options | No |
| | `status table` | `status table [name] [-v]` | Inspect active table shape, RAM, and schema | No |
| | `clear` | `clear` | Clear terminal screen | No |
| | `exit` | `exit [-s [path]]` | Exit REPL (optionally save replay script) | — |
| **Navigation** | `[Tab]` | `[Tab]` | Autocomplete commands, flags, tables, columns, paths | No |

---

## Frequently Asked Questions (FAQ)

### 1. `set`: Configuration & Session Lifecycle

#### Q: How do I move (relocate) an existing session to a new directory?
```text
pytae> set save_session = /Volumes/ExternalSSD/my_project, move = true
```
- **Relocation (`mv`)**: Moves the session directory to the target path.
- The old directory is unlinked to avoid duplicate ghost directories.

#### Q: How do I clone (snapshot) an existing session into a new session without touching the original?
```text
pytae> set save_session = ./client_run1
```
- Source session is preserved untouched.
- An independent clone `client_run1` is created with all checkpoints. Future checkpoints apply strictly to `client_run1`.

#### Q: Can I configure the session directory via an OS environment variable?
**Yes.** Set `PYTAE_SESSIONS_DIR` in your operating system environment:

```bash
# Set session base directory to an external drive or shared folder
export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/pytae_sessions"
pytae -i  # Inside REPL: set load_session = project_x
```
*(On Windows Command Prompt: `set PYTAE_SESSIONS_DIR=C:\pytae_sessions` | PowerShell: `$env:PYTAE_SESSIONS_DIR="C:\pytae_sessions"`)*

**Directory Precedence Order**:
1. **Explicit In-REPL Setting**: `set new_session = <path>` or `set load_session = <path>`.
2. **OS Environment Variable**: `PYTAE_SESSIONS_DIR` (used automatically if set).
3. **Default**: Current working directory `Path.cwd()` (used if neither is set).

#### Q: How do I automatically save my pipeline commands to a script upon exit?
```text
pytae> set save_code = pipeline.txt
```
- When you type `exit` or `quit`, Pytae automatically writes all pure pipeline transformations to `pipeline.txt`.
- You can chain this when starting your session in a single command:
  ```text
  pytae> set new_session = my_lab, save_code = pipeline.txt
  ```

---

### 2. Checkpoints & Memory Storage

#### Q: If I run `pytae -i` without setting a session, where are checkpoints stored?
- Checkpoints are **never stored in RAM** (they always consume 0 MB of active memory).
- By default in ephemeral mode, checkpoints are written to the OS temporary directory (`/tmp/pytae_cp_xxxxxx/` or `$TMPDIR` on macOS/Linux, `%TEMP%` on Windows).
- When you exit the REPL, the temporary folder is **automatically cleaned and deleted**.
- To keep your checkpoints permanently without restarting, simply promote the session mid-flight:
  ```text
  pytae> set new_session = my_permanent_project
  ```
  Pytae will immediately promote your existing checkpoints to `./my_permanent_project/` while keeping all tables active in memory.

---

### 3. `status`: Diagnostics & Inspection

#### Q: What is the difference between `status session` and `status table`?
- **`status session`**: Displays active session name, disk path, number of checkpoints, session logs, and process RAM. Add `-v` for configuration flags.
- **`status table`**: Displays the active dataset, dimensions, memory footprint, and active status. Add `-v` to show column schema and data types.

#### Q: Why are bare `tables`, `checkpoints`, and `vars` rejected?
In accordance with Pytae's *"One Obvious Way"* philosophy and strict singular category hierarchy:
- Inspection is unified under the `status` command family:
  - `status table` (or `status table -v` for loaded table inventory, columns, and RAM totals).
  - `status checkpoint` (or `status checkpoint -v` for saved checkpoints, disk bytes, and file paths).
  - `status table df1` (or `status table df1 -v` for schema).
  - `status var` (or `status var -v` for variables, parameters, and constants).
  - `status session` (or `status session -v` for logs and settings).

---

### 4. `rm`: Explicit Categorical Deletion

#### Q: Why does `rm` require `table` or `checkpoint`?
Bare `rm df1` or `rm *` is strictly rejected:
```text
pytae: 'rm df1' requires explicit category; use 'rm table df1'.
```
- **Explicit Grammar**: Prevents accidental namespace collisions (e.g. if a table is named `checkpoint`).
- **Syntax Symmetry**:
  - `rm table <name>` / `rm table *`: Frees in-memory tables and immediately trims OS memory.
  - `rm checkpoint <name>` / `rm checkpoint *`: Deletes saved snapshots from disk.

#### Q: Why can't I run `rm session` from inside the REPL?
Deleting persistent session directories from inside the running REPL was removed to prevent process corruption and accidental self-deletion. To delete saved sessions, use standard OS commands from your terminal:
```bash
rm -rf ./old_session
```
