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
- [SQL & Python Interop](#sql--python-interop)
  - [ANSI SQL across Tables (`-sql`)](#ansi-sql-across-tables--sql)
  - [SQL Variable Assignment (`df3 = -sql "..."`)](#sql-variable-assignment-df3---sql-)
  - [Fluent Python Execution (`py <expr>`)](#fluent-python-execution-py-expr)
- [Memory Management & Garbage Collection](#memory-management--garbage-collection)
  - [Removing Tables (`rm <name>`, `rm df`, `rm *`)](#removing-tables-rm-name-rm-df-rm-)
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
  - [Reloading After `rm *` & Selective Checkpoint Assignment (`df = <cp>`)](#reloading-after-rm--selective-checkpoint-assignment-df--cp)
  - [Configuring Format (`set checkpoint_format = parquet|ipc`)](#configuring-format-set-checkpoint_format--parquetipc)
- [Persistent REPL Sessions](#persistent-repl-sessions)
  - [CLI Flags (`pytae -session <name>`, `pytae -sessions`)](#cli-flags-pytae--session-name-pytae--sessions)
  - [In-REPL Session Commands (`session`, `session save`, `session load`)](#in-repl-session-commands-session-session-save-session-load)
  - [Custom Directory (`PYTAE_SESSIONS_DIR`)](#custom-directory-pytae_sessions_dir)
- [Session Export & Replay Scripts](#session-export--replay-scripts)
  - [Upfront Auto-Save (`set save = <path>`)](#upfront-auto-save-set-save--path)
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

Launch the REPL from the command line:

```bash
# 1. Launch interactive REPL workbench
pytae -i

# 2. Resume or start a named persistent session
pytae -session analysis

# 3. List all saved persistent sessions from the command line
pytae -sessions
```

> [!NOTE]
> Passing positional files directly to `-i` (e.g. `pytae file.parquet -i`) is disallowed. Simply run `pytae -i`, then load your dataset with `df = file.parquet`. This guarantees that exported session history files contain the full ingestion command and run anywhere.

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

### Reader Options (`-encoding`, `-dlim`, `-nrows`)
Pass inline format parameters directly during assignment:

```text
# Specify Latin-1 encoding, custom semicolon delimiter, and load only the first 5,000 rows
pytae> raw = export.csv -encoding latin1 -dlim ";" -nrows 5000
Loaded export.csv as 'raw' (5,000 rows x 12 cols) [encoding=latin1, sep=;, nrows=5000].
```

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

### Removing Tables (`rm <name>`, `rm df`, `rm *`)
Purge tables from memory when they are no longer needed:

```text
# Remove specific table by variable name
pytae [df1, df2]> rm df1
Removed table 'df1'. Switched active dataset to 'df2'.

# Remove active dataset using universal alias 'df'
pytae [df2]> rm df
Removed table 'df2'. No tables remain loaded.

# Remove all loaded tables at once
pytae [orders, cust, big_orders]> rm *
Removed all 3 loaded tables. No tables remain loaded.
```

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

### Reloading After `rm *` & Selective Checkpoint Assignment (`df = <cp>`)
Because checkpoints live on **disk**, running `rm *` clears active RAM but leaves all checkpoints completely safe!

```text
pytae [df1, df2]> checkpoint abc
Saved checkpoint 'abc' (2 tables: df1, df2).

pytae [df1, df2]> rm *
Removed all 2 loaded tables. No tables remain loaded.
pytae> 
```

You can reload from `abc` in two ways:
1. **Restore entire workbench**:
   ```text
   pytae> restore abc
   Restored checkpoint 'abc' (2 tables: df1, df2; active: df1).
   ```
2. **Selective table assignment from checkpoint**:
   ```text
   # Load a single table from the checkpoint into a new variable name
   pytae> df = abc
   Assigned 'df' from 'abc' (344 rows x 7 cols).
   ```

### Configuring Format (`set checkpoint_format = parquet|ipc`)
By default, checkpoints are saved as uncompressed Arrow IPC (`.ipc`) for near-instant read/write speeds. You can configure your session to use compressed Parquet (`.parquet`) to minimize disk space:

```text
# Check current format
pytae> set
checkpoint_format = ipc (options: ipc, parquet)
save              = none (options: <path>, none)

# Set to compressed Parquet
pytae> set checkpoint_format = parquet
Set checkpoint_format = parquet (checkpoints will be saved as compressed Parquet).
```
*Pytae auto-detects file format on restore, so you can restore IPC and Parquet checkpoints interchangeably within the same session.*

---

## Persistent REPL Sessions

Persistent sessions allow you to save your workbench checkpoints to disk and resume your analysis across terminal restarts or system reboots.

### CLI Flags (`pytae -session <name>`, `pytae -sessions`)
```bash
# 1. Start or resume a named persistent session
pytae -session my_project

# 2. List all persistent sessions saved on disk
pytae -sessions
```

Listing sessions displays checkpoint counts, total disk size, and timestamps:
```text
$ pytae -sessions
Saved Sessions:
  - my_project       : 3 checkpoints (4.12 MB) [last modified: 2026-11-01 09:30]
  - model_eval       : 1 checkpoint  (0.85 MB) [last modified: 2026-10-30 14:15]
```

### In-REPL Session Commands (`session`, `session save`, `session load`)
```text
# Inspect active session name and directory
pytae:my_project [df1]> session
Active session: 'my_project' (/Users/username/.pytae/sessions/my_project)

# Promote an anonymous session to a persistent named session
pytae [df1, df2]> session save analysis_q4
Saved session 'analysis_q4' (/Users/username/.pytae/sessions/analysis_q4).

# Switch to a different persistent session (restores its latest checkpoint)
pytae [df1]> session load my_project
Switched to session 'my_project'. Restored latest checkpoint 'v2'.

# Remove a persistent session from disk
pytae> rm session old_project
Removed session 'old_project' from disk.
```

### Custom Directory (`PYTAE_SESSIONS_DIR`)
By default, persistent sessions are saved under `~/.pytae/sessions/`. Override this path to an external drive, network mount, or project directory by setting `PYTAE_SESSIONS_DIR`:

```bash
# In Bash/Zsh:
export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/pytae_sessions"
pytae -session project_x
```

---

## Session Export & Replay Scripts

Pytae provides a powerful workflow to turn interactive exploration into portable, automated pipeline scripts that run anywhere.

### Upfront Auto-Save (`set save = <path>`)
Configure where your session script should be saved upon exit:

```text
pytae> set save = pipeline.txt
Set save = 'pipeline.txt' (session commands will be auto-saved here on exit).
```
When you quit the REPL via `exit` or <kbd>Ctrl+D</kbd>, Pytae automatically generates the script.

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
  - REPL UI controls (`tables`, `checkpoints`, `history`, `clear`).
- **Included**:
  - File ingestion commands (`df = ...`, `load ...`).
  - Variable assignments (`orders_clean = orders -filter ...`).
  - Table removals (`rm df1`, `rm *`) to keep batch memory footprints low.
  - Output exports (`-o clean.parquet`, `-o clip`).
  - Session configuration (`set checkpoint_format = parquet`).

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

## Complete REPL Command Reference

| Category | Command | Syntax Example | Description | Mutates State? |
|---|---|---|---|---|
| **Ingestion** | Assignment | `df1 = orders.parquet [-nrows 1000]` | Load file into named table variable | Yes |
| | `load` | `load sales.csv as df2 -dlim ";"` | Load file with alias and reader options | Yes |
| | Samples | `df = sample:penguins` | Load bundled sample dataset | Yes |
| **Tables** | `tables` | `tables` | List loaded tables, shapes, and sources | No |
| | Bare name | `df1` | Switch active dataset and display shape | Yes (active) |
| | `use` | `use df1` | Switch active dataset | Yes (active) |
| | Subject-first | `df1 -head 5`, `df2 -shape` | Execute command directly on named table | Depends |
| | `rm` | `rm df1`, `rm df`, `rm *` | Remove table from memory (immediate OS trim) | Yes |
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
| **SQL & Python** | `-sql` | `-sql "SELECT * FROM df1"` | Run ANSI SQL across all loaded tables | Yes (undoable) |
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
| | Assign CP | `df = <cp_name>` | Assign table from checkpoint to variable | Yes |
| | `checkpoints` | `checkpoints` | List all saved checkpoints on disk | No |
| | `rm checkpoint` | `rm checkpoint <name>`, `rm checkpoint *` | Delete checkpoint(s) from disk | No |
| | `set` | `set checkpoint_format = parquet` | Set format to `parquet` or `ipc` | No |
| **Sessions** | `session` | `session` | Display persistent session name and path | No |
| | `session save` | `session save <name>` | Promote session to persistent disk storage | No |
| | `session load` | `session load <name>` | Switch session and restore latest checkpoint | Yes |
| | `sessions` | `sessions` | List all persistent sessions on disk | No |
| | `rm session` | `rm session <name>` | Delete a persistent session from disk | No |
| **Export & Exit**| `set save` | `set save = pipeline.txt` | Set target replay script path upfront | No |
| | `-o` | `-o clean.parquet`, `-o clip` | Export dataset to file or clipboard | No |
| | `status` | `status` | Display active dataset, RAM, undo depth | No |
| | `gc` | `gc` | Force garbage collection and OS memory trim | No |
| | `clear` | `clear` | Clear terminal screen | No |
| | `exit` | `exit [-s [path]]` | Exit REPL (optionally save replay script) | — |
