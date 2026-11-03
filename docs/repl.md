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
  - [Listing Tables (`tables`)](#listing-tables-tables)
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
  - [Comparing Datasets (`diff <tbl1> <tbl2>`)](#comparing-datasets-diff-tbl1-tbl2)
- [SQL & Python Interop](#sql--python-interop)
  - [ANSI SQL across Tables (`-sql`)](#ansi-sql-across-tables--sql)
  - [Explicit Table Names in SQL](#explicit-table-names-in-sql)
  - [SQL Variable Assignment (`df3 = -sql "..."`)](#sql-variable-assignment-df3---sql-)
  - [Fluent Python Execution (`py <expr>`)](#fluent-python-execution-py-expr)
- [Tab Autocompletion & Navigation](#tab-autocompletion--navigation)
- [Memory Management & Garbage Collection](#memory-management--garbage-collection)
  - [Removing Tables (`rm <name>`, `rm *`)](#removing-tables-rm-name-rm-)
  - [Immediate Memory Deallocation & OS Trimming](#immediate-memory-deallocation--os-trimming)
  - [Manual GC & Memory Stats (`gc`, `status`)](#manual-gc--memory-stats-gc-status)
- [State Navigation & History](#state-navigation--history)
  - [Undo & Redo (`undo`, `redo`)](#undo--redo-undo-redo)
  - [Reset Hierarchy (`reset`, `reset <tbl>`, `reset initial`)](#reset-hierarchy-reset-reset-tbl-reset-initial)
  - [In-REPL History Audit Log (`history`)](#in-repl-history-audit-log-history)
- [Checkpoints (Disk-Backed & RAM-Isolated)](#checkpoints-disk-backed--ram-isolated)
  - [Saving Checkpoints (`checkpoint <name>`)](#saving-checkpoints-checkpoint-name)
  - [Listing & Deleting Checkpoints (`checkpoints`, `rm checkpoint`)](#listing--deleting-checkpoints-checkpoints-rm-checkpoint)
  - [Restoring Entire Workbench (`restore <name>`)](#restoring-entire-workbench-restore-name)
  - [Reloading After `rm *` via `restore <name>`](#reloading-after-rm--via-restore-name)
- [Persistent REPL Sessions](#persistent-repl-sessions)
  - [Overview & User Architecture (`~/.pytae/sessions/`)](#overview--user-architecture-pytaesessions)
  - [In-REPL Session Commands (`session`, `session save`, `session load`, `sessions`, `rm session`)](#in-repl-session-commands-session-session-save-session-load-sessions-rm-session)
- [REPL Configuration (`set`)](#repl-configuration-set)
  - [Querying Settings (`set`, `set <key>`)](#querying-settings-set-set-key)
  - [Session Persistence (`set session = <name>`, `set session = none`)](#session-persistence-set-session--name-set-session--none)
  - [Session Loading & Switching (`set load_session = <name>`)](#session-loading--switching-set-load_session--name)
  - [Session Storage & Relocation (`set sessions_dir = <path>`)](#session-storage--relocation-set-sessions_dir--path)
  - [Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`)](#checkpoint-storage-format-set-checkpoint_format--parquetipc)
  - [Replay Script Auto-Save (`set save_commands = <path>`)](#replay-script-auto-save-set-save_commands--path)
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

The **Pytae REPL (`pytae -i`)** loads your dataset into memory **once**. All subsequent filters, aggregations, feature mutations, and SQL queries execute in RAM at multithreaded Polars speed. Because Polars tables are immutable Arrow buffers under the hood, rolling back a mistake with `undo` or `reset` is an instantaneous $O(1)$ pointer reassignment.

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
> `pytae -i` is the dedicated entrypoint for the interactive workbench. Datasets are loaded explicitly inside the REPL with `df = file.parquet`, and persistent project sessions are configured inside via `set session = <name>`. This guarantees that exported session history files contain the full ingestion command and run anywhere.

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

### Listing Tables (`tables`)
View all active datasets in memory, their shapes, and source files:

```text
pytae [orders, cust]> tables
Tables in memory:
 * orders      : 100,000 rows x 6 cols (orders.parquet) [active]
   cust        : 15,000 rows x 5 cols (customers.csv)
```

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

### Comparing Datasets (`diff <tbl1> <tbl2>`)
Compare two in-memory tables, compare the active dataset against another table, or compare against a saved checkpoint:

```text
# Compare active table against orders_backup
pytae [orders]> diff orders_backup

# Explicitly compare two loaded tables
pytae> diff df1 df2

# Compare with numeric float tolerance
pytae> diff df1 df2 -tol 0.001

# Compare active table against a saved checkpoint
pytae [df: 344x7]> diff snap1
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

## Memory Management & Garbage Collection

### Removing Tables (`rm <name>`, `rm *`)
Purge tables from memory when they are no longer needed:

```text
# Remove specific table by variable name
pytae [df1, df2]> rm df1
Removed table 'df1'. Switched active dataset to 'df2'.

# Remove all loaded tables at once
pytae [orders, cust, big_orders]> rm *
Removed all 3 loaded tables. No tables remain loaded.
```

> [!NOTE]
> Explicit table names (or `rm *`) are required. Vague generic aliases like `rm df` are not used when removing tables to protect against accidental deletions of the wrong dataset.

### Immediate Memory Deallocation & OS Trimming
Unlike standard Python shells that retain memory pages in process heaps:
1. **Zero Lingering References**: Running `rm <name>` or `rm *` purges the table from `self.tables`, `self.orig_tables`, `self.initial_tables`, and clears the undo/redo stack snapshots.
2. **OS Memory Trimming**: Pytae automatically triggers [`_release_memory()`](file:///Users/maddy/Documents/my_repos/pytae/src/pytae/repl.py#L92-L131), which calls `gc.collect()` and instructs the OS memory manager to reclaim freed pages:
   - **macOS**: Resident pages trimmed and measured live via `mach_task_basic_info`.
   - **Windows**: `SetProcessWorkingSetSize(-1, -1)` and `K32EmptyWorkingSet` trim unused working set pages back to the Windows kernel.
   - **Linux**: `libc.malloc_trim(0)` flushes unmapped heap arenas back to the OS.

### Manual GC & Memory Stats (`gc`, `status`)
Inspect memory usage and run garbage collection anytime:

```text
pytae [df: 344x7]> status
Active dataset : df
Shape          : 344 rows x 7 cols
Table memory   : 0.02 MB
Process RAM    : ~129.5 MB
Undo steps     : 2 / 10

pytae [df: 344x7]> gc
Garbage collection complete. Process RAM: ~129.2 MB.
```

---

## State Navigation & History

### Undo & Redo (`undo`, `redo`)
Safely experiment with transformations. Undo and redo operate as $O(1)$ pointer swaps:

```text
pytae [df: 344x7]> -filter "species == 'Gentoo'"
-> df: 124 rows x 7 cols

pytae [df: 124x7]> undo
Undid: -filter "species == 'Gentoo'". Active shape: (344, 7)

pytae [df: 344x7]> redo
Redid: -filter "species == 'Gentoo'". Active shape: (124, 7)
```
*Note: The undo stack maintains a sliding window of 10 steps to prevent unbounded memory growth during long sessions.*

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
   4: undo [-filter "species == 'Adelie'"]
   5: rm df

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
- **Undo Baseline Established**: Creating a checkpoint clears the undo/redo stacks, freeing intermediate memory while establishing a safe restore point.

### Listing & Deleting Checkpoints (`checkpoints`, `rm checkpoint`)
```text
# List all checkpoints and their constituent tables
pytae> checkpoints
Saved Checkpoints:
  - baseline       : orders (100,000x6), cust (15,000x5) [active: cust]
  - cleaned        : orders (82,000x6) [active: orders] [parquet]

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

### Overview & User Architecture (`~/.pytae/sessions/`)

All user state in Pytae is structured under a unified `~/.pytae/` home root:
- `~/.pytae/sessions/<session_name>/`: Houses persistent session checkpoints (`checkpoints/`), metadata manifest (`session.json`), and table state.
- `~/.pytae/commands/`: Default home for generated replayable command scripts.
- `~/.pytae/history/`: Flight recorder logging all interactive keystrokes and queries.

### In-REPL Session Commands (`session`, `session save`, `session load`, `sessions`, `rm session`)

In addition to configuring sessions via `set`, Pytae provides dedicated top-level session commands:

```text
# Inspect active session name and filesystem location
pytae:my_project [df1]> session
Active session: 'my_project' (2 checkpoints; location: /Users/username/.pytae/sessions/my_project)

# Promote current workbench checkpoints to disk under a named session
pytae [df1, df2]> session save my_project
Session saved as 'my_project' (2 checkpoints saved).
pytae:my_project [df1, df2]>

# Switch to a different persistent session (restores its latest checkpoint)
pytae [df1]> session load sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v2'.

# List all persistent sessions saved on disk (includes location, size, and health status)
pytae> sessions
Sessions Directory: /Users/username/.pytae/sessions
Saved Sessions:
  - my_project       : Ready (2 checkpoints (cp1, cp2); 0.05 MB; /Users/username/.pytae/sessions/my_project)
  - sales_q3         : Ready (3 checkpoints (v1, v2, v3); 4.12 MB; /Users/username/.pytae/sessions/sales_q3)

# Remove a persistent session and its checkpoints from disk
pytae> rm session old_project
Removed session 'old_project' from disk.
```

> [!NOTE]
> Network shares or external drives listed in `sessions` that are temporarily disconnected or unreachable are safely presented as `[Offline / Unreachable]` without modifying or pruning records.

---

## REPL Configuration (`set`)

The `set` command is the central control hub for inspecting and configuring your interactive session workbench. Settings can be queried bare, set individually, or combined together on a single line.

### Querying Settings (`set`, `set <key>`)

Running `set` with no arguments displays all current configuration values and available options:

```text
pytae> set
session           = none (options: <name>, none)
checkpoint_format = ipc (options: ipc, parquet)
save_commands     = none (options: <path>, none)
sessions_dir      = /Users/username/.pytae/sessions (options: <path>, default)
```

To query a single setting without modifying it, run `set <key>`:

```text
pytae> set checkpoint_format
checkpoint_format = ipc (options: ipc, parquet)

pytae> set sessions_dir
sessions_dir = /Users/username/.pytae/sessions (options: <path>, default)
```

### Session Persistence (`set session = <name>`, `set session = none`)

Bind your current ephemeral workbench to a persistent named session on disk, or detach back to an ephemeral state:

- **Bind / Promote to Named Session**:
  Saves all current checkpoints and workbench tables to disk, updating your prompt to reflect the active session name:
  ```text
  pytae [df1, df2]> set session = my_project
  Session saved as 'my_project' (2 checkpoints saved).
  pytae:my_project [df1, df2]>
  ```
- **Detach / Revert to Ephemeral**:
  Pass `none` (or `off`, `false`, `0`) to detach from disk persistence while preserving loaded tables in memory:
  ```text
  pytae:my_project [df1, df2]> set session = none
  Detached persistent session 'my_project' (session reverted to ephemeral).
  pytae [df1, df2]>
  ```

### Session Loading & Switching (`set load_session = <name>`)

Switch directly to an existing persistent session from disk, automatically restoring its latest checkpoint:

```text
pytae> set load_session = sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v2'.
pytae:sales_q3 [sales_q3: 150,000x12]>
```

> [!NOTE]
> `set load_session` strictly expects a session name (e.g. `sales_q3`), never file paths with `/` or `\`. To switch session storage directories, see [Session Storage & Relocation](#session-storage--relocation-set-sessions_dir--path).

### Session Storage & Relocation (`set sessions_dir = <path>`)

Configure the base filesystem directory where persistent sessions and their checkpoints are stored.

- **Default Location**: `~/.pytae/sessions/`
- **Relocating Active Sessions (Full Migration Without Duplicates)**:
  When a session is active, running `set sessions_dir = <path>` immediately migrates all checkpoints, tables, and session metadata from the old directory to `<path>/<session_name>`. Once the data is verified in the new destination, Pytae automatically unlinks and removes the previous session directory, preventing duplicate or ghost copies:
  ```text
  pytae:my_project> set sessions_dir = /Volumes/ExternalSSD/pytae_sessions
  Relocated active session 'my_project' to '/Volumes/ExternalSSD/pytae_sessions/my_project' (2 checkpoints moved).
  ```
- **Reset to Default**:
  Pass `default` to restore the standard directory:
  ```text
  pytae> set sessions_dir = default
  Set sessions_dir = '/Users/username/.pytae/sessions'.
  ```
- **Ephemeral Protection**:
  Running `set sessions_dir = <path>` alone while in ephemeral mode is cleanly rejected to prevent orphaned directory pointers. Set `session = <name>` alongside `sessions_dir = <path>` to establish both together.
- **Environment Variable**:
  You can configure a global default across all CLI launches via `PYTAE_SESSIONS_DIR`:
  ```bash
  export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/pytae_sessions"
  pytae -session project_x
  ```

### Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`)

Control the on-disk serialization format used for session checkpoints:

- **`ipc` (Default)**: Uncompressed Arrow IPC streaming format (`.ipc`). Delivers maximum write and read speed for near-instant `checkpoint` and `restore` operations.
- **`parquet`**: Compressed columnar Parquet format (`.parquet`). Minimizes disk usage on storage-constrained environments or network drives.

```text
# Switch to compressed Parquet format
pytae> set checkpoint_format = parquet
Set checkpoint_format = parquet (checkpoints will be saved as compressed Parquet).

# Switch back to fast uncompressed Arrow IPC
pytae> set checkpoint_format = ipc
Set checkpoint_format = ipc (checkpoints will be saved as fast uncompressed Arrow IPC).
```

*Pytae auto-detects formats on restore, allowing IPC and Parquet checkpoints to be used interchangeably within the same session.*

### Replay Script Auto-Save (`set save_commands = <path>`)

Designate a file path to automatically capture and write your session's replayable command script upon exit:

```text
# Enable auto-save on exit
pytae> set save_commands = pipeline.txt
Set save_commands = 'pipeline.txt' (session commands will be auto-saved here on exit).

# Disable auto-save
pytae> set save_commands = none
Disabled auto-saving commands on exit.
```

When you quit the REPL via `exit` or <kbd>Ctrl+D</kbd>, Pytae automatically writes the clean, executable pipeline script.

### Combining Multiple Settings on One Line

Multiple settings can be chained in a single command using comma, semicolon, space, or repeated `set` syntax:

```text
# Bind a named session and relocate its storage directory simultaneously
pytae> set session = analytics, sessions_dir = /Volumes/Share/sessions

# Load an existing session and migrate it to a new location in one step
pytae> set load_session = sales_q3, sessions_dir = /Volumes/ExternalSSD/pytae_sessions

# Configure replay script destination and checkpoint compression together
pytae> set save_commands = build.txt, checkpoint_format = parquet
```

---

## Session Export & Replay Scripts

Pytae provides a powerful workflow to turn interactive exploration into portable, automated pipeline scripts that run anywhere.

> [!TIP]
> To configure automatic replay script generation upfront before working, use [`set save_commands = <path>`](#replay-script-auto-save-set-save_commands--path).

### Exit-Time Export (`exit -s [path]`)

Save the session history directly when exiting:

```text
# Save to default history.txt
pytae> exit -s

# Save to custom script file
pytae> exit -s transform_orders.txt
Session history saved to /Users/username/transform_orders.txt.
Exiting pytae REPL.
```

### Automatic Replay Script Filtering (`_is_replayable_entry`)
When exporting a replay script, Pytae automatically filters out noise:
- **Excluded**:
  - Checkpoint commands (`checkpoint <name>`, `restore <name>`) — checkpoints are interactive exploration tools; omitting them avoids redundant disk I/O during batch replay.
  - Bare exploratory inspection commands (`-head`, `-tail`, `-describe`, `-cols`, bare `-pivot`) that do not assign to a variable or export to a file.
  - REPL UI controls and configuration (`tables`, `checkpoints`, `history`, `clear`, `set ...`).
- **Included**:
  - File ingestion commands (`df = ...`, `load ...`).
  - Variable assignments (`orders_clean = orders -filter ...`).
  - Table removals (`rm df1`, `rm *`) to keep batch memory footprints low.
  - Output exports (`-o clean.parquet`, `-o clip`).

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
| **Tables** | `tables` | `tables` | List loaded tables, shapes, and sources | No |
| | Bare name | `df1` | Display table dimensions without switching cursor | No |
| | `use` | `use df1` | Switch active dataset | Yes (active) |
| | `rename` | `rename df1 customers` | Zero-copy $O(1)$ in-memory table rename | Yes |
| | Subject-first | `df1 -head 5`, `df2 -shape` | Execute command directly on named table | Depends |
| | `rm` | `rm df1`, `rm orders`, `rm *` | Remove table from memory (immediate OS trim) | Yes |
| **Transform** | `-filter` | `-filter "amount > 100"` | Filter rows by expression | Yes (undoable) |
| | `-mutate` | `-mutate "tax = amount * 0.1"` | Add or modify columns | Yes (undoable) |
| | `-select` | `-select "id,name,!notes"` | Column projection and exclusion | Yes (undoable) |
| | `-arrange` | `-arrange "amount desc"` | Sort rows | Yes (undoable) |
| | `-by -agg` | `-by cat -agg "total=amt:sum"` | Grouped aggregation | Yes (undoable) |
| | `-join` | `df1 -join df2 on=cust_id` | Join tables | Yes (undoable) |
| | Assignment | `df3 = df1 -filter "..."` | Assign pipeline result to new variable | Yes |
| **Inspection** | `-head` / `-tail` | `-head 10`, `-tail 5` | Non-destructive preview of rows | No |
| | `-sample` | `-sample 10` | Non-destructive random row preview | No |
| | `-shape` | `-shape` | Display (rows, columns) | No |
| | `-schema` | `-schema` | Detailed column breakdown and null counts | No |
| | `-cols` | `-cols [asc\|desc\|pattern]` | List column names (supports sorting/filter) | No |
| | `-dtype` / `-nulls` | `-dtype asc`, `-nulls` | Column types and missing value counts | No |
| | `-glimpse` | `-glimpse` | Transposed schema and preview values | No |
| | `-describe` | `-describe` | Statistical summary of numeric columns | No |
| | `diff` | `diff df1 df2 [-tol 0.01]` | Compare two tables or active table against target | No |
| **SQL & Python** | `-sql` | `-sql "SELECT * FROM df1"` | Run ANSI SQL across loaded tables | Yes (undoable) |
| | SQL Assign | `df4 = -sql "..."` | Create new table from SQL query | Yes |
| | `py` | `py pldf.columns` | Evaluate Python/Polars expression | No |
| **State & Undo** | `undo` | `undo` | Revert last transformation step (up to 10) | Yes (undoable) |
| | `redo` | `redo` | Re-apply last undone transformation step | Yes (undoable) |
| | `reset` | `reset` | Revert workbench to latest checkpoint | Yes |
| | `reset <tbl>` | `reset df1` | Revert single table to latest checkpoint | Yes |
| | `reset initial` | `reset initial` | Revert workbench to initial file read state | Yes |
| | `history` | `history [N]` | Display numbered audit log of session commands | No |
| **Checkpoints** | `checkpoint` | `checkpoint <name>` | Save snapshot to disk (0 MB RAM, clears undo) | No |
| | `restore` | `restore <name>` | Restore workbench to named checkpoint | Yes |
| | `checkpoints` | `checkpoints` | List all saved checkpoints on disk | No |
| | `rm checkpoint` | `rm checkpoint <name>`, `rm checkpoint *` | Delete checkpoint(s) from disk | No |
| | `set` | `set checkpoint_format = parquet` | Set format to `parquet` or `ipc` | No |
| **Sessions** | `session` | `session` | Display persistent session name and path | No |
| | `session save` | `session save <name>` | Promote session to persistent disk storage | No |
| | `session load` | `session load <name>` | Switch session and restore latest checkpoint | Yes |
| | `sessions` | `sessions` | List all persistent sessions on disk | No |
| | `rm session` | `rm session <name>` | Delete a persistent session from disk | No |
| **Settings** | `set` | `set` | Inspect all configuration settings | No |
| | `set session` | `set session = <name>` | Bind REPL to persistent session | No |
| | `set load_session` | `set load_session = <name>` | Switch session and restore latest checkpoint | Yes |
| | `set save_commands` | `set save_commands = pipeline.txt` | Set target replay script path upfront | No |
| | `set checkpoint_format`| `set checkpoint_format = parquet` | Set format to `parquet` or `ipc` | No |
| | `set sessions_dir` | `set sessions_dir = <path>` | Configure persistent sessions base directory | No |
| **Export & Exit**| `-o` | `-o clean.parquet`, `-o clip` | Export dataset to file or clipboard | No |
| | `status` | `status` | Display active dataset, RAM, undo depth | No |
| | `gc` | `gc` | Force garbage collection and OS memory trim | No |
| | `clear` | `clear` | Clear terminal screen | No |
| | `exit` | `exit [-s [path]]` | Exit REPL (optionally save replay script) | — |
| **Navigation** | `[Tab]` | `[Tab]` | Autocomplete commands, flags, tables, columns, paths | No |
