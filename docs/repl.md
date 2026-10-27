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
pytae -session analysis   # or short alias: pytae -s analysis

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

* **`reset`**: Reverts the session to the **latest saved checkpoint**. If no checkpoints exist in the session, it falls back to the original dataset state as loaded from disk. Active RAM is strictly isolated, post-checkpoint tables are purged, undo/redo history is cleared, and garbage collection runs immediately:
  ```text
  pytae [df1, df2, df3]> reset
  Restored checkpoint 'maddy' (2 tables: df1, df2; active: df2).
  ```
* **`reset initial`**: Strictly reverts the entire session back to the initial dataset read state, even when intermediate checkpoints exist:
  ```text
  pytae [df1, df2]> reset initial
  Restored initial dataset state (1 table: df1). Active shape: (344, 7)
  ```
  > [!NOTE]
  > Unrecognized sub-arguments (such as `reset orig`) are rejected:
  > `pytae: 'reset orig' is not recognized; use 'reset' or 'reset initial'.`

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
3. **Session Location**: Sessions are stored under `~/.pytae/sessions/<name>/` (containing session metadata and `.ipc` checkpoint tables). You can override the base directory by setting the `PYTAE_SESSIONS_DIR` environment variable.

#### 2. CLI Interface

```bash
# Launch or resume a named persistent session
pytae -session analysis
pytae -s analysis

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

# 4. Or explicitly load a bundled sample dataset via sample:<name>
pytae [df1, df2, df3]> df4 = sample:penguins
Loaded penguins.parquet as 'df4' (344 rows x 7 cols).

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
| **`reset`** | `reset` | Revert to latest checkpoint (or initial dataset read if no checkpoints exist) | **Yes** (undoable) |
| **`reset initial`** | `reset initial` | Revert session strictly to initial dataset read (bypassing checkpoints) | **Yes** (undoable) |
| **`undo`** | `undo` | Revert the last applied transformation step | **Yes** (undoable) |
| **`redo`** | `redo` | Re-apply the last undone transformation step | **Yes** (undoable) |
| **`history`** | `history` | List numbered history of applied transformation steps and checkpoint banners | No |
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

