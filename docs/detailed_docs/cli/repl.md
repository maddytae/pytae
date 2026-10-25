# CLI Feature Guide: Interactive REPL Shell (`-i`, `-repl`, `repl`)

Stateful, iterative in-memory data manipulation and exploratory data analysis without repeatedly reloading datasets from disk.

---

## Contents

- [Overview & Why Use REPL](#overview--why-use-repl)
- [Launching the REPL](#launching-the-repl)
- [Session State & Rollback (`reset`, `undo`, `redo`)](#session-state--rollback-reset-undo-redo)
- [Checkpoints & Snapshots (`checkpoint`, `restore`)](#checkpoints--snapshots-checkpoint-restore)
- [Multi-Table Workflow & Variable Assignment (`<var> = <file>`)](#multi-table-workflow--variable-assignment-var--file)
  - [Assigning Datasets (`df1 = orders.parquet`)](#assigning-datasets-df1--ordersparquet)
  - [Listing Loaded Tables (`tables`, `vars`)](#listing-loaded-tables-tables-vars)
  - [Switching the Active Table (`use df1`, bare `df2`)](#switching-the-active-table-use-df1-bare-df2)
  - [Targeted Commands on Specific Tables (`df1 -head 5`, `df2 shape`)](#targeted-commands-on-specific-tables-df1--head-5-df2-shape)
  - [Assigning Pipeline & SQL Results (`df3 = ...`)](#assigning-pipeline--sql-results-df3--)
- [In-Memory Pipeline Transformations](#in-memory-pipeline-transformations)
- [Non-Destructive Inspection (`head`, `shape`, `cols`, etc.)](#non-destructive-inspection-head-shape-cols-etc)
- [Multi-Table Joins & ANSI SQL (`-join`, `sql`)](#multi-table-joins--ansi-sql--join-sql)
  - [Option 1: Standard Pipeline `-join`](#option-1-standard-pipeline--join)
  - [Option 2: ANSI SQL Across Loaded Datasets (`sql`)](#option-2-ansi-sql-across-loaded-datasets-sql)
  - [Option 3: Fluent Python Joins (`py`)](#option-3-fluent-python-joins-py)
- [Saving & Exporting (`-o`)](#saving--exporting--o)
- [Python & Jupyter SDK Integration (`pt.repl()`, `df.repl()`)](#python--jupyter-sdk-integration-ptrepl-dfrepl)
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

## Launching the REPL

You can launch the REPL from the command line in three ways:

```bash
# 1. Pre-load a dataset into the interactive shell
pytae penguins.parquet -i

# 2. Launch an empty REPL prompt (load data later via 'load <file>')
pytae -i
pytae repl

# 3. Pre-filter a dataset and drop directly into the interactive REPL
pytae penguins.parquet -filter "body_mass_g > 4000" -i
```

Upon launching, the interactive prompt displays the current file name and live table shape:
```text
pytae [penguins.parquet: 344x7]> 
```

---

## Session State & Rollback (`reset`, `undo`, `redo`)

### 1. `reset`: Revert to Original Dataset
If you perform multiple transformations and realize you want to discard your changes, `reset` instantly rolls the table back to the original dataset as loaded from disk:

```text
pytae [penguins.parquet: 344x7]> -filter "species == 'Gentoo'"
shape: (124, 7)
...

pytae [penguins.parquet: 124x7]> reset
Restored original dataset. Active shape: (344, 7)

pytae [penguins.parquet: 344x7]> 
```

### 2. `undo` & `redo`: Step-by-Step History Navigation
Like `Ctrl+Z` in an editor, `undo` steps backward through your transformation stack, while `redo` re-applies undone steps:

```text
pytae [penguins.parquet: 344x7]> -filter "body_mass_g > 4000"
shape: (168, 7)

pytae [penguins.parquet: 168x7]> -mutate "mass_kg = body_mass_g / 1000.0"
shape: (168, 8)

pytae [penguins.parquet: 168x8]> undo
Undid: -mutate "mass_kg = body_mass_g / 1000.0". Active shape: (168, 7)

pytae [penguins.parquet: 168x7]> redo
Redid: -mutate "mass_kg = body_mass_g / 1000.0". Active shape: (168, 8)
```

### 3. `history`: Inspect Applied Pipeline Steps
```text
pytae [penguins.parquet: 168x8]> history
Pipeline History:
   1: -filter "body_mass_g > 4000"
   2: -mutate "mass_kg = body_mass_g / 1000.0"
```

---

## Checkpoints & Snapshots (`checkpoint`, `restore`)

You can save named state checkpoints at key milestones before experimenting with exploratory transformations:

```text
# Save a named checkpoint
pytae [penguins.parquet: 344x7]> checkpoint baseline
Saved checkpoint 'baseline' (344 rows x 7 cols).

# Experiment with aggressive filtering
pytae [penguins.parquet: 344x7]> -filter "island == 'Dream' and sex == 'female'"
shape: (61, 7)

# Restore back to your saved checkpoint
pytae [penguins.parquet: 61x7]> restore baseline
Restored checkpoint 'baseline'. Active shape: (344, 7)

# List all saved checkpoints
pytae [penguins.parquet: 344x7]> checkpoints
Saved Checkpoints:
  - baseline       : 344 rows x 7 cols
```

*(Aliases: `cp` for `checkpoint`, `checkout` for `restore`, `cps` for `checkpoints`)*.

---

## Multi-Table Workflow & Variable Assignment (`<var> = <file>`)

You can launch a clean REPL without any initial dataset via `pytae -i`, load multiple tables into named variables, and analyze or join them simultaneously.

### Assigning Datasets (`df1 = orders.parquet`)

```text
$ pytae -i
================================================================================
                         PYTAE INTERACTIVE REPL                                 
================================================================================
Type 'help' for REPL commands, 'reset' to revert to original, or 'exit' to quit.
No initial dataset loaded. Use 'load <path>' to load a table.

pytae> df1 = orders.parquet
Loaded orders.parquet as 'df1' (10,000 rows x 4 cols).

pytae [df1: 10,000x4]> df2 = customers.parquet
Loaded customers.parquet as 'df2' (1,500 rows x 3 cols).

pytae [df2: 1,500x3]>
```

### Listing Loaded Tables (`tables`, `vars`)

Use `tables` or `vars` to inspect every dataset currently held in memory. The active table is designated with an asterisk `*`:

```text
pytae [df2: 1,500x3]> tables
Tables in memory:
   df1         : 10,000 rows x 4 cols (orders.parquet)
 * df2         : 1,500 rows x 3 cols (customers.parquet) [active]
```

### Switching the Active Table (`use df1`, bare `df2`)

Switch your active working dataset with `use <name>` or by simply typing the table name:

```text
pytae [df2: 1,500x3]> use df1
Switched active dataset to 'df1'. Active shape: (10,000, 4)

pytae [df1: 10,000x4]> df2
Switched active dataset to 'df2'. Active shape: (1,500, 3)
shape: (5, 3)
...
```

### Targeted Commands on Specific Tables (`df1 -head 5`, `df2 shape`)

Execute inspections or transformations directly on a specific table without switching your active context:

```text
# Non-destructive inspection of df1 while df2 remains active
pytae [df2: 1,500x3]> df1 -head 3
pytae [df2: 1,500x3]> df1 shape
(10,000, 4)

# Apply a transformation directly to df1
pytae [df2: 1,500x3]> df1 -filter "amount > 100"
pytae [df2: 1,500x3]> df1 shape
(3,450, 4)
```

### Assigning Pipeline & SQL Results (`df3 = ...`)

Create new named tables from transformations, joins, or ANSI SQL queries:

```text
# 1. Pipeline assignment from another table
pytae> df_filtered = df1 -filter "amount > 150"

# 2. Join assignment
pytae> df3 = df1 join df2 on=customer_id

# 3. ANSI SQL assignment across loaded datasets
pytae> df4 = sql SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.customer_id = df2.id
```

---

## In-Memory Pipeline Transformations

Any standard Pytae CLI flag sequence can be typed directly into the prompt. Transformations execute on the in-memory Arrow table, print the resulting table, and update the active dataset:

```text
# Filter rows
pytae> -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"

# Feature engineering
pytae> -mutate "mass_kg = body_mass_g / 1000, is_heavy = mass_kg > 4.5"

# Column selection & drop
pytae> -select "species,island,mass_kg"
pytae> -select "!sex"

# Sort rows
pytae> -arrange "mass_kg desc"

# Grouped aggregation
pytae> -by species -agg "avg_mass=body_mass_g:mean, count=count"

# Sensitive data masking and encryption
pytae> -mask "email=hash, ssn=encrypt" -key "SecretKey123"
```

> [!TIP]
> **Bare-Verb Convenience**: Leading hyphens are optional for primary verbs. `filter "species == 'Gentoo'"` works identically to `-filter "species == 'Gentoo'"`.

---

## Non-Destructive Inspection (`head`, `shape`, `cols`, etc.)

Inspection commands display metadata or previews **without** truncating or mutating your active table:

```text
# Non-destructive head/tail previews (does NOT truncate active rows)
pytae> head 10
pytae> tail 5

# Dimensions & columns
pytae> shape
(344, 7)

pytae> cols
species
island
bill_length_mm
bill_depth_mm
flipper_length_mm
body_mass_g
sex

pytae> dtype
species               object
island                object
bill_length_mm       float64
...

# Missing values & statistical summary
pytae> nulls
pytae> glimpse
pytae> describe
```

---

## Multi-Table Joins & ANSI SQL (`-join`, `sql`)

The REPL provides three seamless ways to join datasets in memory using standard Pytae commands.

### Option 1: Standard Pipeline `-join`

Join another loaded table or disk file directly into your active dataset using Pytae's standard `-join` command:

```text
# With df1 active: left join df2 on customer_id
pytae [df1: 10,000x4]> -join df2 on=customer_id

# With differing column names (left_col:right_col) and join type
pytae [df1: 10,000x4]> -join df2 on=cust_id:id how=left

# Join and export directly in one step with standard -o
pytae [df1: 10,000x4]> -join df2 on=cust_id -o merged.parquet
```

Supported join types: `how=left`, `how=inner`, `how=outer`, `how=semi`, `how=anti`.

You can also use standard multi-file key-value syntax:
```text
pytae> -join "left=df1,right=df2,on=cust_id,how=inner" -o merged.parquet
```

### Option 2: ANSI SQL Across Loaded Datasets (`sql`)

Every loaded table (`df1`, `df2`, etc.) and saved checkpoint is automatically registered and queryable in `sql`:

```text
pytae> sql SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.id
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

You can assign the SQL result to a new named table:
```text
pytae> df3 = sql SELECT df1.order_id, df2.name FROM df1 JOIN df2 ON df1.cust_id = df2.id
```

### Option 3: Fluent Python Joins (`py`)

Use Pytae's fluent Python API directly on your loaded tables:

```text
pytae> py df1.join(df2, on="cust_id", how="left")
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

## Python & Jupyter SDK Integration (`pt.repl()`, `df.repl()`)

You can launch the Pytae REPL directly from Python scripts, IPython, or Jupyter:

```python
import pytae as pt
import pandas as pd

df = pt.read_parquet("sales.parquet")

# 1. Launch REPL off any Pytae DataFrame
cleaned_df = df.repl()

# 2. Or call via pandas .pt accessor
raw_df = pd.read_csv("raw.csv")
cleaned_df = raw_df.pt.repl()

# 3. Direct function call
pt.repl(df)
```

When you type `exit` in the REPL, the final transformed table is returned directly into your Python variable.

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
| **`tables`** | `tables`, `vars` | List all loaded tables in memory (`*` = active) | No |
| **`use`** | `use <name>`, `<name>` | Switch active dataset to specified table | **Yes** |
| **`<name> <cmd>`** | `df1 -head 5`, `df2 shape` | Run command directly on named table | Depends on command |
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

