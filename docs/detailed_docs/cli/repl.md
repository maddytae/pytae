# CLI Feature Guide: Interactive REPL Shell (`-i`)

Stateful, iterative in-memory data manipulation and exploratory data analysis without repeatedly reloading datasets from disk.

---

## Contents

- [Overview & Why Use REPL](#overview--why-use-repl)
- [Two Core Operation Modes](#two-core-operation-modes)
  - [Mode 1: Single-Table Exploration (`pytae <file> -i`)](#mode-1-single-table-exploration-pytae-file--i)
  - [Mode 2: Multi-Table Workbench (`pytae -i` with `df -cmd`)](#mode-2-multi-table-workbench-pytae--i-with-df--cmd)
- [Launching the REPL](#launching-the-repl)
- [Mode 1: Single-Table Exploration Deep-Dive](#mode-1-single-table-exploration-deep-dive)
  - [Direct Pipeline Transformations](#direct-pipeline-transformations)
  - [Non-Destructive Inspection (`head`, `shape`, `cols`, etc.)](#non-destructive-inspection-head-shape-cols-etc)
  - [Session State & Rollback (`reset`, `undo`, `redo`)](#session-state--rollback-reset-undo-redo)
  - [Checkpoints & Snapshots (`checkpoint`, `restore`)](#checkpoints--snapshots-checkpoint-restore)
- [Mode 2: Multi-Table Workbench Deep-Dive (`df -cmd`)](#mode-2-multi-table-workbench-deep-dive-df--cmd)
  - [Assigning Datasets (`df1 = orders.parquet`)](#assigning-datasets-df1--ordersparquet)
  - [Listing Loaded Tables (`tables`, `vars`)](#listing-loaded-tables-tables-vars)
  - [Subject-First Execution (`df1 -head 5`, `df2 -shape`)](#subject-first-execution-df1--head-5-df2--shape)
  - [Multi-Table Joins (`-join`)](#multi-table-joins--join)
  - [Assigning Pipeline & Join Results (`df3 = ...`)](#assigning-pipeline--join-results-df3--)
  - [ANSI SQL Across Loaded Tables (`sql`)](#ansi-sql-across-loaded-tables-sql)
  - [Fluent Python Queries (`py`)](#fluent-python-queries-py)
- [Saving & Exporting (`-o`)](#saving--exporting--o)
- [Complete REPL Command Reference](#complete-repl-command-reference)

---

## Overview & Why Use REPL

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
| **Command Syntax** | `-filter "..."`, `head 5`, `-o clean.parquet` | `df1 -filter "..."`, `df2 -head 5`, `df1 -join df2` |
| **Dataset Prefix** | Omitted (unambiguous, only 1 table exists) | Explicit subject-first (`df1`, `df2`, `df3`) |
| **State Cursor** | Bound to the loaded file | Stateless workbench (subject specifies the table) |

---

## Launching the REPL

You can launch the REPL from the command line in three ways:

```bash
# 1. Mode 1: Pre-load a single dataset into the interactive shell
pytae penguins.parquet -i

# 2. Mode 2: Launch an empty REPL workbench (load datasets via df1 = orders.parquet)
pytae -i

# 3. Pre-filter a dataset and drop directly into the interactive REPL
pytae penguins.parquet -filter "body_mass_g > 4000" -i
```

Upon launching, the interactive prompt displays the current file name and live table shape:
```text
pytae [penguins.parquet: 344x7]> 
```

---

## Mode 1: Single-Table Exploration Deep-Dive

When launched with a single input file (`pytae penguins.parquet -i`), the REPL enters **Single-Table Exploration Mode**. Because only one dataset exists in memory, all operations execute directly on the active table without needing any table prefix.

### 1. In-Memory Pipeline Transformations

Any standard Pytae CLI flag sequence can be typed directly into the prompt. Transformations execute on the in-memory Arrow table, output a concise status confirmation, and update the table state:

```text
pytae [penguins.parquet: 344x7]> -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"
-> penguins.parquet: 188 rows x 7 cols

pytae [penguins.parquet: 188x7]> -mutate "mass_kg = body_mass_g / 1000, is_heavy = mass_kg > 4.5"
-> penguins.parquet: 188 rows x 9 cols

pytae [penguins.parquet: 188x9]> -select "species,island,mass_kg"
-> penguins.parquet: 188 rows x 3 cols

pytae [penguins.parquet: 188x3]> head 3
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
> **1:1 CLI Syntax Parity**: Pipeline verbs always start with a leading hyphen (e.g. `-filter`, `-mutate`, `-select`, `-arrange`, `-join`), maintaining exact parity with standard CLI usage. If a bare verb is entered (e.g. `filter "..."`), Pytae catches it and provides a helpful reminder.

> [!TIP]
> **Clean Terminal (Model 2)**: Pipeline transformations and table switching output concise shape confirmations (e.g. `-> penguins.parquet: 188 rows x 7 cols` or `df1: 344 rows x 7 cols`) without dumping full tables. To view rows, explicitly run `head` or `tail`.

### 2. Non-Destructive Inspection (`head`, `shape`, `cols`, etc.)

Inspection commands display metadata or previews **without** truncating or mutating your dataset:

```text
# Non-destructive previews (does NOT truncate active rows)
pytae> head 10
pytae> tail 5

# Dimensions & columns
pytae> shape
(344, 7)

pytae> cols
species
island
bill_length_mm
...

# Column types & missing values
pytae> dtype
pytae> nulls
pytae> glimpse
pytae> describe
```

### 3. Session State & Rollback (`reset`, `undo`, `redo`)

* **`reset`**: Reverts the table back to the original dataset as loaded from disk:
  ```text
  pytae [penguins.parquet: 64x3]> reset
  Restored original dataset. Active shape: (344, 7)
  ```
* **`undo` & `redo`**: Step backward and forward through your transformation stack:
  ```text
  pytae> undo
  Undid: -filter "body_mass_g > 4000". Active shape: (344, 7)

  pytae> redo
  Redid: -filter "body_mass_g > 4000". Active shape: (168, 7)
  ```
* **`history`**: View the full log of applied pipeline steps:
  ```text
  pytae> history
  Pipeline History:
     1: -filter "body_mass_g > 4000"
     2: -mutate "mass_kg = body_mass_g / 1000.0"
  ```

### 4. Checkpoints & Snapshots (`checkpoint`, `restore`)

Save named checkpoints at key milestones before experimenting with exploratory transformations:

```text
# Save a named checkpoint
pytae> checkpoint baseline
Saved checkpoint 'baseline' (344 rows x 7 cols).

# Experiment with aggressive filtering
pytae> -filter "island == 'Dream' and sex == 'female'"
shape: (61, 7)

# Restore back to your saved checkpoint
pytae> restore baseline
Restored checkpoint 'baseline'. Active shape: (344, 7)

# List all saved checkpoints
pytae> checkpoints
Saved Checkpoints:
  - baseline       : 344 rows x 7 cols
```

*(Aliases: `cp` for `checkpoint`, `checkout` for `restore`, `cps` for `checkpoints`)*.

---

## Mode 2: Multi-Table Workbench Deep-Dive (`df -cmd`)

When launched with `pytae -i`, the REPL enters **Multi-Table Workbench Mode**. You can load several datasets into memory simultaneously and manipulate them using clean, stateless **subject-first commands (`df -cmd`)**.

### 1. Ingesting Datasets (`<var> = <file>`)

Load files into named variables using standard assignment syntax:

```text
$ pytae -i
================================================================================
                         PYTAE INTERACTIVE REPL                                 
================================================================================
Type 'help' for REPL commands, 'reset' to revert to original, or 'exit' to quit.
No initial dataset loaded. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table.

# 1. Load an existing file from disk (strict path check, no fuzzy fallback)
pytae> df1 = orders.parquet
Loaded orders.parquet as 'df1' (10,000 rows x 4 cols).

# 2. Or explicitly load a bundled sample dataset via sample:<name>
pytae [df1: 10,000x4]> df2 = sample:penguins
Loaded penguins.parquet as 'df2' (344 rows x 7 cols).

pytae [df1, df2]>
```

> [!NOTE]
> File assignments are strict and predictable: `df = filename.parquet` requires an actual file on disk. Bundled sample datasets are only loaded when explicitly prefixed with `sample:<name>` (e.g. `df = sample:penguins`). There is no fuzzy matching or automatic fallback for non-existent files.

Notice how the prompt dynamically updates to show all datasets currently in memory: `pytae [df1, df2]> `.

### 2. Listing Loaded Tables (`tables`, `vars`)

Inspect all loaded tables and their dimensions anytime:

```text
pytae [df1, df2]> tables
Tables in memory:
   df1         : 10,000 rows x 4 cols (orders.parquet)
   df2         : 1,500 rows x 3 cols (customers.parquet)
```

### 3. Subject-First Execution (`df1 -head 5`, `df2 -shape`)

Instead of modal "switching" between tables, **every operation explicitly states its target dataset**. This eliminates ambiguity and mirrors the Pytae CLI 1:1:

```text
# Non-destructive inspection of specific tables
pytae [df1, df2]> df1 -head 3
pytae [df1, df2]> df2 -head 3
pytae [df1, df2]> df1 shape
(10,000, 4)
pytae [df1, df2]> df2 cols

# Apply in-place transformations to a specific table
pytae [df1, df2]> df1 -filter "amount > 100"
pytae [df1, df2]> df1 shape
(3,450, 4)

# Export a specific table directly
pytae [df1, df2]> df1 -o clean_orders.parquet
```

> [!TIP]
> **Quick Dimensions**: Typing a bare table name (e.g. `df1`) switches to it and prints its dimensions (`df1: 10,000 rows x 4 cols`) without dumping any table rows. To inspect rows, run `df1 -head 5` or `head 5`.

### 4. Multi-Table Joins (`-join`)

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

### 5. Assigning Pipeline & Join Results (`df3 = ...`)

Create new named tables from transformations, joins, or ANSI SQL queries:

```text
# 1. Pipeline assignment from another table (df1 remains untouched)
pytae [df1, df2]> df_filtered = df1 -filter "amount > 150"

# 2. Join assignment
pytae [df1, df2]> df3 = df1 -join df2 on=cust_id

# 3. ANSI SQL assignment across loaded tables
pytae [df1, df2, df3]> df4 = sql SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id
```

### 6. ANSI SQL Across Loaded Tables (`sql`)

Every loaded table (`df1`, `df2`, `df3`, etc.) and saved checkpoint is automatically registered in Polars SQLContext:

```text
pytae [df1, df2]> sql SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id
shape: (10,000, 3)
┌──────────┬─────────────┬────────┐
│ order_id ┆ name        ┆ amount │
│ ---      ┆ ---         ┆ ---    │
│ i64      ┆ str         ┆ f64    │
╞══════════╪═════════════╪════════╡
│ 1001     ┆ Alice Smith ┆ 149.50 │
│ 1002     ┆ Bob Jones   ┆ 89.00  │
└──────────┴─────────────┴────────┘
```

### 7. Fluent Python Queries (`py`)

Evaluate Python expressions directly against your loaded tables:

```text
pytae [df1, df2]> py df1.join(df2, on="cust_id", how="left")
```

---

## Saving & Exporting (`-o`)

Export your active dataset to disk or the system clipboard using the standard `-o` / `--output` flag:

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
| **`help`** | `help`, `?` | Display formatted help manual | No |
| **`status`** | `status` | Show active dataset name, shape, memory, undo stack depth | No |
| **`reset`** | `reset` | Revert active table to original dataset from disk | **Yes** (undoable) |
| **`undo`** | `undo` | Revert the last applied transformation step | **Yes** (undoable) |
| **`redo`** | `redo` | Re-apply the last undone transformation step | **Yes** (undoable) |
| **`history`** | `history` | List numbered history of applied transformation steps | No |
| **`checkpoint`** | `checkpoint <name>`, `cp <name>` | Save current table state with a name | No |
| **`restore`** | `restore <name>`, `checkout <name>` | Restore active table to a named checkpoint | **Yes** (undoable) |
| **`checkpoints`**| `checkpoints`, `cps` | List all saved checkpoint names and shapes | No |
| **`<var> = <file>`** | `df1 = orders.parquet` | Load file as named table in memory | **Yes** |
| **`tables`** | `tables`, `vars` | List all loaded tables in memory | No |
| **`<name> <cmd>`** | `df1 -head 5`, `df2 -shape` | Run command directly on named table (subject-first) | Depends on command |
| **`<name>`** | `df1` | Switch to table and display dimensions (`rows x cols`) | **Yes** (switches active) |
| **`-join`** | `-join <target> on=<key> [how=...] [-o <path>]` | Join table or file into active dataset | **Yes** (undoable) |
| **`-o`** | `-o <path>`, `-o clip` | Export active dataset to Parquet/CSV or clipboard | No |
| **`sql`** | `sql <query>` | Run ANSI SQL against active table or named tables | **Yes** (undoable) |
| **`py`** | `py <expr>` | Evaluate Python expression on `df` / `pldf` | No |
| **`head`** | `head [N]` | Non-destructive preview of top $N$ rows (default 5) | No |
| **`tail`** | `tail [N]` | Non-destructive preview of bottom $N$ rows (default 5) | No |
| **`shape`** | `shape`, `-shape` | Display row and column counts | No |
| **`cols`** | `cols [asc]`, `-cols` | Display column names | No |
| **`dtype`** | `dtype`, `-dtype` | Display column data types | No |
| **`nulls`** | `nulls`, `-nulls` | Display missing value counts | No |
| **`glimpse`** | `glimpse`, `-glimpse` | Display transposed schema and sample values | No |
| **`describe`** | `describe`, `-describe` | Display statistical summary of numeric columns | No |
| **`exit`** | `exit`, `quit`, `q` | Exit the REPL session | — |

