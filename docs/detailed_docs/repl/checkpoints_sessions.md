# REPL Guide: In-Memory Workbench, Checkpoints & Configuration

[← Back to Master Reference](../../pytae.md)

This guide covers ephemeral IPC snapshotting (`checkpoint`), instant workbench recovery (`restore`), milestone diffing (`-diff <checkpoint>`), table switching (`switch`), session status inspection (`status session`), smart pipeline export on exit (`exit -s [pt|py|path]`), in-session export (`export script`), and user preferences (`set`, `set save`) in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [In-Memory Workbench Architecture](#in-memory-workbench-architecture)
- [Checkpoints & Ephemeral IPC Storage](#checkpoints--ephemeral-ipc-storage)
  - [Saving & Updating Checkpoints (`checkpoint <name>`)](#saving--updating-checkpoints-checkpoint-name)
  - [Restoring Workbench State (`restore [name]`)](#restoring-workbench-state-restore-name)
  - [Milestone Diffing Against Checkpoints (`-diff <checkpoint>`)](#milestone-diffing-against-checkpoints--diff-checkpoint)
  - [Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)](#listing--deleting-checkpoints-status-checkpoint-rm-checkpoint)
  - [Reverting to Disk Source (`reset`, `reset <tbl>`, `reset initial`)](#reverting-to-disk-source-reset)
- [Table Navigation (`switch <name>`)](#table-navigation-switch-name)
- [Session Status & Diagnostics (`status session`)](#session-status--diagnostics-status-session)
- [Exporting Reusable Pipelines](#exporting-reusable-pipelines)
  - [Smart Export on Exit (`exit -s`, `exit -s py`, `exit -s pt`)](#smart-export-on-exit-exit--s-exit--s-py-exit--s-pt)
  - [In-Session Script Export (`export script`)](#in-session-script-export-export-script)
- [Comprehensive Real-World Scenarios](#comprehensive-real-world-scenarios)
  - [Scenario 1: Feature Engineering with Milestone Diffing](#scenario-1-feature-engineering-with-milestone-diffing)
  - [Scenario 2: Multi-Table Join & Experimental Branching](#scenario-2-multi-table-join--experimental-branching)
  - [Scenario 3: One-Liner Pipeline Export to Python & Pytae Scripts](#scenario-3-one-liner-pipeline-export-to-python--pytae-scripts)
- [REPL Configuration (`set`, `set save`)](#repl-configuration-set-set-save)
  - [Querying Active Settings (`set`)](#querying-active-settings-set)
  - [Display Preferences (`max_rows`, `max_cols`, `float_precision`, `comma`)](#display-preferences)
  - [Persisting Settings to Disk (`set save`, `~/.pytae/config.json`)](#persisting-settings-to-disk-set-save-pytaeconfigjson)
  - [Retirement of Legacy Disk Sessions](#retirement-of-legacy-disk-sessions)

---

## In-Memory Workbench Architecture

The Pytae REPL operates as a pure **in-memory workbench**:
- **0 MB RAM Overhead for Checkpoints**: Checkpoints serialize frozen tables to an ephemeral process-bound temp directory (`/tmp/pytae_cp_xxxxxx/`) in Arrow IPC format and session variables in `<name>__vars.json`. They consume **0 MB of active RAM**.
- **Automatic Lifecycle Cleanup**: When exiting the session (`exit`, `Ctrl+D`, or process termination), the ephemeral temporary directory and all `.ipc` snapshots are completely wiped clean immediately.
- **Flight Recorder History**: All commands entered during a session are auto-logged to `~/.pytae/history/history_<timestamp>.txt`. Exiting an empty session immediately purges empty history files.
- **Multi-Table Workspace**: Load multiple datasets into named tables (`df1 = orders.parquet`, `df2 = sample:tips`), query them via fluent verbs or ANSI SQL (`-sql "SELECT * FROM df1 JOIN df2..."`), and switch between them with `switch <name>` (`use` deprecated).

---

## Checkpoints & Ephemeral IPC Storage

### Saving & Updating Checkpoints (`checkpoint <name>`)

Take an ephemeral snapshot of all active tables, original file references, session `@variables`, and pipeline state:

```text
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust; 2 variables: @tax_rate, @threshold).
```

When you re-save to an existing checkpoint name, Pytae automatically purges the old IPC files, writes the updated state, and clearly reports the overwrite:

```text
pytae [orders, cust]> checkpoint baseline
Updated checkpoint 'baseline' (2 tables: orders, cust; 2 variables: @tax_rate, @threshold).
```

### Restoring Workbench State (`restore [name]`)

Restoring removes modified tables from RAM and streams back the exact snapshot from the ephemeral IPC disk:

```text
# Revert to a specific named checkpoint
pytae [orders, cust, scratch_df]> restore baseline
Restored checkpoint 'baseline' (2 tables: orders, cust; active: cust).

# Revert to the most recent checkpoint (bare restore)
pytae [orders, cust]> restore
Restored checkpoint 'baseline' (2 tables: orders, cust).
```

*(Note: `revert` is supported as an exact synonym. The legacy verb `rollback` is deprecated and automatically routes to `restore` while displaying deprecation guidance).*

All post-checkpoint scratch tables and uncommitted mutations are automatically dropped.

### Milestone Diffing Against Checkpoints (`-diff <checkpoint>`)

You can compare the active in-memory table against its counterpart inside any saved checkpoint:

```text
pytae [t1]> t1 = -mutate "bonus = tip * 2"
pytae [t1]> -diff baseline
Comparing 't1' vs 'checkpoint:baseline':
Comparing:
  Left (source):  <left> (244 rows, 8 cols)
  Right (target): <right> (244 rows, 7 cols)

Shape:
  Rows: 244 vs 244 (+0)
  Cols: 8 vs 7 (+1)

Columns:
  + Added in left (1):   bonus
  Common (7):            total_bill, tip, sex, smoker, day, time, size

Schema Drift:
  None (all common columns have matching dtypes)

Values:
  Matching: all cell values in common columns match.
```

#### Comparing Specific Tables inside a Checkpoint (`<checkpoint>:<table_name>`)
If you have multiple tables loaded and wish to compare a specific table:
```text
pytae [t1, t2]> -diff baseline:t2
Comparing 't2' vs 'checkpoint:baseline:t2':
...
```

Or compare across two different checkpoints:
```text
pytae> -diff v1:t1 v2:t1
Comparing 'checkpoint:v1:t1' vs 'checkpoint:v2:t1':
...
```

### Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)

```text
# List all saved checkpoints, tables, and disk sizes
pytae> status checkpoint
Checkpoints (2 saved):
  - baseline       : 2 tables [active: cust], 2 vars [@tax_rate, @threshold] (42.1 KB disk, 0 MB RAM) [2026-11-07 12:00:00]
      - orders: 1,000 rows x 8 cols
      - cust: 500 rows x 4 cols
  - filtered       : 1 table [active: orders] (18.4 KB disk, 0 MB RAM) [2026-11-07 12:05:00]
      - orders: 742 rows x 8 cols

# Inspect metadata for a specific checkpoint
pytae> status checkpoint baseline
Checkpoint: baseline
Active Table : cust
Tables       : 2 tables (orders, cust)
Variables    : 2 defined [@tax_rate = 0.08, @threshold = 1000]
Created      : 2026-11-07 12:00:00
Storage      : ephemeral disk IPC (42.1 KB on disk, 0 MB RAM)

# Delete a single checkpoint
pytae> rm checkpoint filtered
Removed checkpoint 'filtered'.

# Purge all checkpoints
pytae> rm checkpoint *
Cleared all saved checkpoints.
```

### Reverting to Disk Source (`reset`)

To revert active tables back to their original state loaded from disk:

```text
# Revert to latest checkpoint (or initial state if no checkpoints exist)
pytae [orders]> reset
Reset active table 'orders' to latest checkpoint 'baseline'.

# Revert a single table strictly to its initial file read state (bypassing checkpoints)
pytae [orders, cust]> reset orders initial
Reset table 'orders' to initial state.

# Revert all tables across the workbench strictly to initial file read state
pytae [orders, cust]> reset initial
Reset all tables to initial state.
```

---

## Table Navigation (`switch <name>`)

In a multi-table session, use `switch <name>` to select the active dataset cursor:

```text
pytae [df1, df2]> switch df2
Switched active dataset to 'df2'. Active shape: (150, 5)

pytae [df1, df2*]> -head 3
shape: (3, 5)
...
```

> [!NOTE]
> The verb `use <table_name>` is **deprecated** in favor of `switch <table_name>`. While `use` still works for backward compatibility, it emits a recommendation to adopt `switch`.

---

## Session Status & Diagnostics (`status session`)

Inspect active in-memory tables, variable definitions, saved checkpoints, process RAM consumption, and history logs:

```text
pytae [orders, cust*]> status session
=== REPL Session Status ===
Active Table  : cust (500 rows x 4 cols, ~0.02 MB)
Loaded Tables : 2 tables [orders, cust*] (~0.12 MB in memory)
Variables     : 2 defined [@tax_rate, @threshold]
Checkpoints   : 2 saved (latest: baseline) [42.1 KB ephemeral disk, 0 MB RAM]
Process RAM   : ~148.2 MB (PID 64919)
------------------------------------------------------------
(Tip: Use 'status table [name]' for table details, 'status checkpoint [name]' for checkpoints, 'status var [name]' for variables)
```

In verbose mode (`status session -v`), each checkpoint lists its individual ephemeral disk footprint alongside its creation timestamp and table count:

```text
pytae [orders, cust*]> status session -v
=== REPL Session Status ===
Active Table  : cust (500 rows x 4 cols, ~0.02 MB)
Loaded Tables : 2 tables [orders, cust*] (~0.12 MB in memory)
  - orders   : 1,000 rows x 8 cols (~0.10 MB) (source: orders.parquet)
  - cust [active]: 500 rows x 4 cols (~0.02 MB) (source: customers.csv)
Variables     : 2 defined [@tax_rate, @threshold]
  * @tax_rate     : 0.08 (float)
  * @threshold    : 1000 (int)
Checkpoints   : 2 saved (latest: baseline) [42.1 KB ephemeral disk, 0 MB RAM]
  - baseline    : ephemeral IPC created 2026-11-07 12:00:00 (2 tables, 42.1 KB ephemeral disk, 0 MB RAM)
History Log   : ~/.pytae/history/history_20261107_120000.txt
Settings      : max_rows=10, max_cols=all, float_precision=auto
Process RAM   : ~148.2 MB (PID 64919)
```

---

## Exporting Reusable Pipelines

### Smart Export on Exit (`exit -s`, `exit -s py`, `exit -s pt`)

When finishing an exploration session, you can save your commands directly into a standalone, reproducible pipeline as you exit:

| Command | Output File | Description |
| :--- | :--- | :--- |
| **`exit -s`** | `./session.pt` in cwd | **Default**: Saves clean, pruned commands to an executable Pytae script. Run with `pytae session.pt`. |
| **`exit -s py`** | `./session.py` in cwd | Compiles the session into a standalone Polars/Pytae Python script. Run with `python session.py`. |
| **`exit -s pt`** | `./session.pt` in cwd | Explicit shortcut for `./session.pt`. |
| **`exit -s <custom_path>`** | `<custom_path>` | Saves to any custom path (e.g. `exit -s pipeline.py` or `exit -s etl.pt`). |

#### Automatic Branch Pruning
Both `exit -s` and `export script` automatically **prune rolled-back branches and undo paths**. If you tested a mutation, restored a checkpoint, and went down another path, only the final reproducible pipeline is exported!

### In-Session Script Export (`export script`)

You can also export your pipeline at any time during an active session without exiting:

```text
# Export to a Pytae script (replayable via `pytae pipeline.pt`)
pytae> export script pipeline.pt

# Export with relative file paths (portable across machines)
pytae> export script pipeline.pt -relative

# Export to a standalone Python script using Polars / Pytae DataFrame
pytae> export script pipeline.py
```

---

## Comprehensive Real-World Scenarios

### Scenario 1: Feature Engineering with Milestone Diffing

In this scenario, a data analyst loads a dataset, creates a baseline milestone, engineers experimental features, diffs against the milestone, and reverts unwanted changes.

```text
# 1. Ingest dataset
pytae> tips = sample:tips
Loaded tips.parquet as 'tips' (244 rows x 7 cols).

# 2. Freeze baseline state (0 MB RAM overhead)
pytae [tips]> checkpoint baseline
Saved checkpoint 'baseline' (244 rows x 7 cols).

# 3. Add experimental features
pytae [tips]> tips = -mutate "pct = (tip / total_bill) * 100", "is_high = tip > 5"
shape: (244, 9)
...

# 4. Compare active table vs baseline milestone
pytae [tips]> -diff baseline
Comparing 'tips' vs 'checkpoint:baseline':
Comparing:
  Left (source):  <left> (244 rows, 9 cols)
  Right (target): <right> (244 rows, 7 cols)

Shape:
  Rows: 244 vs 244 (+0)
  Cols: 9 vs 7 (+2)

Columns:
  + Added in left (2):   is_high, pct
  Common (7):            total_bill, tip, sex, smoker, day, time, size

Values:
  Matching: all cell values in common columns match.

# 5. Decide to discard experimental features and restore clean baseline
pytae [tips]> restore baseline
Restored checkpoint 'baseline' (244 rows x 7 cols).

pytae [tips]> -diff baseline
Values:
  Identical: all cell values match exactly.
```

---

### Scenario 2: Multi-Table Join & Experimental Branching

In this scenario, we load two tables, define parameters, filter, and join.

```text
# 1. Ingest two tables
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (10,000 rows x 6 cols).

pytae [orders]> cust = customers.csv
Loaded customers.csv as 'cust' (1,200 rows x 4 cols).

# 2. Define session variables
pytae [orders, cust]> @min_spend = 50.0

# 3. Checkpoint pre-join state
pytae [orders, cust]> checkpoint pre_join
Saved checkpoint 'pre_join' (2 tables: orders, cust; 1 variable: @min_spend).

# 4. Filter orders and join with customers
pytae [orders, cust]> switch orders
Switched active dataset to 'orders'. Active shape: (10,000, 6)

pytae [orders, cust*]> orders = -filter "amount >= @min_spend"
shape: (6,420, 6)

pytae [orders, cust*]> orders = -join cust on=customer_id
shape: (6,420, 9)

# 5. Inspect status telemetry
pytae [orders, cust*]> status session
=== REPL Session Status ===
Active Table  : orders (6,420 rows x 9 cols, ~0.45 MB)
Loaded Tables : 2 tables [orders*, cust] (~0.52 MB in memory)
Variables     : 1 defined [@min_spend]
Checkpoints   : 1 saved (latest: pre_join) [124.5 KB ephemeral disk, 0 MB RAM]
Process RAM   : ~165.2 MB (PID 48201)
------------------------------------------------------------

# 6. Update checkpoint with new milestone
pytae [orders, cust*]> checkpoint pre_join
Updated checkpoint 'pre_join' (2 tables: orders, cust; 1 variable: @min_spend).
```

---

### Scenario 3: One-Liner Pipeline Export to Python & Pytae Scripts

When you are satisfied with your exploratory analysis, exit cleanly while generating ready-to-run automation scripts:

#### Exporting to an Executable Pytae Script (`exit -s` or `exit -s pt`)
```text
pytae [orders, cust*]> exit -s
Session code saved to /Users/analyst/projects/session.pt.
Exiting pytae REPL.
```

Generated `session.pt`:
```pytae
# Pytae Script: session.pt
# Generated: 2026-11-07 17:25:00

orders = orders.parquet
cust = customers.csv
@min_spend = 50.0
orders = -filter "amount >= @min_spend"
orders = -join cust on=customer_id
```

Run directly in headless production via:
```bash
pytae session.pt
```

#### Exporting to Standalone Polars Python (`exit -s py`)
```text
pytae [orders, cust*]> exit -s py
Session code saved to /Users/analyst/projects/session.py.
Exiting pytae REPL.
```

Generated `session.py`:
```python
"""Auto-generated standalone Python pipeline script from pytae REPL session."""
# Generated: 2026-11-07 17:25:00

import pandas as pd
import polars as pl
import pytae as pt

orders = pt.read("orders.parquet")
cust = pt.read("customers.csv")
min_spend = 50.0

orders = orders.filter(pl.col("amount") >= min_spend)
orders = orders.join(cust, on="customer_id", how="inner")
```

Run directly with standard Python:
```bash
python session.py
```

---

## REPL Configuration (`set`, `set save`)

### Querying Active Settings (`set`)

Running `set` with no arguments displays active display preferences:

```text
pytae> set
max_rows        = 10 (options: <int>, default)
max_cols        = all (options: <int>, all, default)
float_precision = auto (options: <int>, auto, default)
comma           = off (options: on, off)
(Tip: Run 'set save' to persist settings across REPL sessions)
```

Query a specific key using `set <key>`:

```text
pytae> set max_rows
max_rows        = 10 (options: <int>, default)
```

### Display Preferences

- **Row Truncation (`set max_rows = <int>|default`, alias: `rows`)**: Controls rows displayed in previews. Defaults to `10`.
- **Column Truncation (`set max_cols = <int>|all|default`, alias: `cols`)**: Limits columns displayed in wide tables. Defaults to `all`.
- **Floating-Point Precision (`set float_precision = <int>|auto|default`, alias: `precision`)**: Sets decimal display places. Defaults to `auto`.
- **Thousands Comma Separator (`set comma = on|off`)**: Formats numbers with grouping commas (e.g. `1,234,567`). Numeric columns remain native integers/floats in memory and exports.

Multiple settings can be combined on one line:

```text
pytae> set max_rows = 25, comma = on, float_precision = 2
```

### Persisting Settings to Disk (`set save`, `~/.pytae/config.json`)

On first launch, Pytae automatically creates `~/.pytae/config.json` with default settings. To save active configuration settings across sessions:

```text
pytae> set save
Saved configuration to /Users/username/.pytae/config.json.
```

The JSON configuration file is loaded automatically on subsequent REPL launches:

```json
{
  "max_rows": 25,
  "max_cols": "all",
  "float_precision": 2,
  "comma": "on"
}
```

### Retirement of Legacy Disk Sessions

> [!NOTE]
> Legacy persistent disk sessions (`set new_session = ...`, `set load_session = ...`, `set save_session = ...`, `set checkpoint_format = ...`) have been retired.
> - Use ephemeral checkpoints (`checkpoint <name>`, `restore [name]`) for instant undo and branching (0 MB RAM).
> - Use `exit -s [pt|py|path]` or `export script <path.pt | path.py>` to persist, version-control, and share data pipelines.
> - Run exported scripts in batch mode via `pytae <script.pt>` or `python <script.py>`.
