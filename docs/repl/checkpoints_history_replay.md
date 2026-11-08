# REPL Guide: Checkpoints, History Audit, Pipeline Export & Replay

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers saving in-memory snapshots (`checkpoint`), instant rollback (`restore`), milestone diffing (`-diff`), audit history logging (`history`), exporting clean reproducible pipelines (`export`, `exit -s`), post-hoc CLI conversion (`pytae -export`), and batch execution in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Checkpoints & Ephemeral IPC Storage](#checkpoints--ephemeral-ipc-storage)
  - [Saving & Updating Checkpoints (`checkpoint <name>`)](#saving--updating-checkpoints-checkpoint-name)
  - [Instant Workbench Recovery (`restore [name]`)](#instant-workbench-recovery-restore-name)
  - [Milestone Diffing Against Checkpoints (`-diff`)](#milestone-diffing-against-checkpoints--diff)
  - [Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)](#listing--deleting-checkpoints-status-checkpoint-rm-checkpoint)
  - [Reverting to Source (`reset`, `reset <tbl>`, `reset initial`)](#reverting-to-source-reset-reset-tbl-reset-initial)
- [Session History & Audit Logging](#session-history--audit-logging)
  - [In-REPL History Audit Log (`history`, `history <n>`)](#in-repl-history-audit-log-history-history-n)
  - [Automated Flight-Recorder Storage](#automated-flight-recorder-storage)
- [Reproducible Pipeline Export](#reproducible-pipeline-export)
  - [In-Session Export (`export <path> [-relative]`)](#in-session-export-export-path--relative)
  - [Smart Export on Exit (`exit -s [path] [-relative]`)](#smart-export-on-exit-exit--s-path--relative)
  - [Automatic Undo Branch Pruning](#automatic-undo-branch-pruning)
  - [Path Canonicalization & Windows UNC Resolution](#path-canonicalization--windows-unc-resolution)
- [Executing Exported Scripts: "One and Only One Obvious Way"](#executing-exported-scripts-one-and-only-one-obvious-way)
  - [Pytae Pipeline Scripts (`.pt`)](#pytae-pipeline-scripts-pt)
  - [Python Scripts (`.py`)](#python-scripts-py)
  - [Post-Hoc CLI Conversion (`pytae -export`)](#post-hoc-cli-conversion-pytae--export)
- [Comprehensive Real-World Scenarios](#comprehensive-real-world-scenarios)
  - [Scenario 1: Feature Engineering with Milestone Diffing & Rollback](#scenario-1-feature-engineering-with-milestone-diffing--rollback)
  - [Scenario 2: Multi-Table Branching & Production Pipeline Export](#scenario-2-multi-table-branching--production-pipeline-export)

---

## Checkpoints & Ephemeral IPC Storage

The Pytae REPL features a zero-overhead snapshotting system. When exploring hypotheses, you can freeze your workbench state at any time without consuming valuable RAM.

### Saving & Updating Checkpoints (`checkpoint <name>`)

Take an ephemeral snapshot of all active tables, original file references, session `@variables`, and pipeline state:

```text
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust; 2 variables: @tax_rate, @threshold).
```

- **0 MB RAM Overhead**: Tables are serialized to an ephemeral process-bound temp directory (`/tmp/pytae_cp_xxxxxx/`) in Arrow IPC format, consuming **0 MB of active process heap**.
- **Instant Overwrite**: Re-saving to an existing checkpoint name automatically replaces the previous snapshot and reports the update:

```text
pytae [orders, cust]> checkpoint baseline
Updated checkpoint 'baseline' (2 tables: orders, cust; 2 variables: @tax_rate, @threshold).
```

- **Automatic Lifecycle Cleanup**: When exiting the session (`exit`, `Ctrl+D`, or process termination), all ephemeral IPC files and temporary directories are wiped completely.

### Instant Workbench Recovery (`restore [name]`)

Restoring drops modified tables from RAM and streams back the exact snapshot from disk at microsecond speeds:

```text
# Revert to a specific named checkpoint
pytae [orders, cust, scratch_df]> restore baseline
Restored checkpoint 'baseline' (2 tables: orders, cust; active: cust).

# Revert to the most recent checkpoint (bare restore)
pytae [orders, cust]> restore
Restored checkpoint 'baseline' (2 tables: orders, cust).
```

All post-checkpoint scratch tables and uncommitted mutations are automatically dropped.

### Milestone Diffing Against Checkpoints (`-diff`)

Compare the active in-memory table against its frozen counterpart inside any checkpoint. Running bare `-diff` compares the active table against the **latest saved milestone**:

```text
pytae [t1*]> t1 = -mutate "bonus = tip * 2"

# 1. Bare -diff compares active table vs latest checkpoint
pytae [t1*]> -diff
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
```text
pytae [t1, t2]> -diff baseline:t2
Comparing 't2' vs 'checkpoint:baseline:t2':
...
```

#### Comparing Across Two Different Checkpoints
```text
pytae> -diff v1:t1 v2:t1
Comparing 'checkpoint:v1:t1' vs 'checkpoint:v2:t1':
...
```

### Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)

```text
# List all saved checkpoints, tables, and sizes
pytae> status checkpoint
Checkpoints (2 saved):
  - baseline       : 2 tables [active: cust], 2 vars [@tax_rate, @threshold] (42.1 KB disk, 0 MB RAM)
      - orders: 1,000 rows x 8 cols
      - cust: 500 rows x 4 cols
  - filtered       : 1 table [active: orders] (18.4 KB disk, 0 MB RAM)
      - orders: 742 rows x 8 cols

# Inspect metadata for a specific checkpoint
pytae> status checkpoint baseline
Checkpoint: baseline
Active Table : cust
Tables       : 2 tables (orders, cust)
Variables    : 2 defined [@tax_rate = 0.08, @threshold = 1000]
Storage      : ephemeral disk IPC (42.1 KB on disk, 0 MB RAM)

# Delete a single checkpoint
pytae> rm checkpoint filtered
Removed checkpoint 'filtered'.

# Purge all checkpoints
pytae> rm checkpoint *
Cleared all saved checkpoints.
```

### Reverting to Source (`reset`, `reset <tbl>`, `reset initial`)

Reset commands allow you to step back to baseline states:

* **`reset`**: Reverts active tables to the **latest saved checkpoint**. If no checkpoints exist, reverts to the initial file read state.
* **`reset <table_name>`**: Reverts **only the specified table** to the latest checkpoint (or initial read), leaving all other loaded tables untouched.
* **`reset <table_name> initial`**: Reverts **only the specified table** strictly to its initial file read state, bypassing all intermediate checkpoints.
* **`reset initial`**: Strictly reverts **all tables** across the entire workbench back to their initial file read state.

---

## Session History & Audit Logging

### In-REPL History Audit Log (`history`, `history <n>`)

Inspect commands executed during your session as a clean numbered list:

```text
pytae [df: 344x7]> history
Session History:
   1: df = penguins.parquet
   2: checkpoint v1
   3: -filter "species == 'Adelie'"
   4: df = -mutate "mass_kg = body_mass_g / 1000"

# View only the last 3 commands
pytae [df: 344x7]> history 3
```

### Automated Flight-Recorder Storage

Every interactive session automatically writes a chronological flight-recorder audit log to `~/.pytae/history/history_<timestamp>.txt`. If an interactive session is closed without running any commands or loading any tables, Pytae automatically purges the empty history file so your directory stays completely clean.

---

## Reproducible Pipeline Export

### In-Session Export (`export <path> [-relative]`)

Export your active pipeline at any time without exiting the REPL:

```text
# 1. Export as a native Pytae pipeline script (canonical)
pytae> export pipeline.pt

# 2. Export with portable relative file paths
pytae> export pipeline.pt -relative

# 3. Export as a standalone Python / Polars script
pytae> export pipeline.py
pytae> export pipeline.py -relative
```

### Smart Export on Exit (`exit -s [path] [-relative]`)

Save pure transformation steps into a standalone executable script as you exit:

| Command | Output File | Description |
|:---|:---|:---|
| **`exit -s`** | `./session.pt` in `cwd` | **Default**: Saves clean, pruned steps to a Pytae script. |
| **`exit -s py`** | `./session.py` in `cwd` | Compiles session into a standalone Python / Polars script. |
| **`exit -s pt`** | `./session.pt` in `cwd` | Explicit shortcut for `./session.pt`. |
| **`exit -s <path> [-relative]`** | `<path>` in `cwd` | Saves to custom path with optional relative dataset paths. |

### Automatic Undo Branch Pruning

Both `exit -s` and `export` automatically **prune rolled-back branches and discarded experiments**. If you test a filter, restore a checkpoint, and choose another path, only the active, final pipeline steps that produced your current tables are written to the exported script.

### Path Canonicalization & Windows UNC Resolution

When exporting scripts:
1. **Absolute Paths by Default**: Relative paths provided interactively (`df = ../data/orders.parquet`) are canonicalized to absolute paths so scripts can be executed safely from any working directory or cron scheduler.
2. **Portable Relative Paths with `-relative`**: When sharing scripts with colleagues or checking them into Git repositories alongside data folders, passing `-relative` preserves paths relative to the current working directory.
3. **Windows Mapped Drives to UNC**: On Windows, mapped network drives (`Z:\shared\data.parquet`) are automatically resolved to universal network paths (`\\server\share\data.parquet`) using Windows `WNetGetConnectionW`.

---

## Executing Exported Scripts: "One and Only One Obvious Way"

Pytae enforces clear boundaries between native Pytae scripts and standard Python scripts:

### Pytae Pipeline Scripts (`.pt`)

Native Pytae pipeline scripts contain zero-boilerplate assignments and flags (`orders = orders.parquet`, `-filter "amount > 100"`).

- **Headless Execution**:
  ```bash
  pytae pipeline.pt
  ```
  Runs to completion, executes exports, and exits `0`. Ideal for automated batch pipelines and CI/CD.

- **Interactive Preload**:
  ```bash
  pytae -i pipeline.pt
  ```
  Executes the script and leaves you directly inside the interactive REPL with all datasets loaded.

### Python Scripts (`.py`)

Python scripts exported via `export pipeline.py` or `exit -s py` contain standard Python code using `pytae` and `polars`.

- **Headless Execution**:
  ```bash
  python pipeline.py
  ```
- **Interactive Python**:
  ```bash
  python -i pipeline.py
  ```

> [!NOTE]
> Attempting to run Python scripts with `pytae script.py` or `pytae -i script.py` is actively intercepted with a friendly redirect:
> ```text
> pytae error: 'script.py' is a Python script; run with 'python script.py'.
> For native Pytae pipelines, use 'pytae <script.pt>'.
> ```

### Post-Hoc CLI Conversion (`pytae -export`)

If you closed a session without exporting, you can convert any recorded flight-recorder log (`~/.pytae/history/`) into a clean script post-hoc:

```bash
# Convert to native Pytae script
pytae -export ~/.pytae/history/history_20261108_000000.txt -o pipeline.pt

# Convert to standalone Python script
pytae -export ~/.pytae/history/history_20261108_000000.txt -o pipeline.py

# Convert with portable relative paths
pytae -export history.txt -o pipeline.pt -relative
```

---

## Comprehensive Real-World Scenarios

### Scenario 1: Feature Engineering with Milestone Diffing & Rollback

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

# 4. Compare active table vs baseline milestone
pytae [tips]> -diff baseline
Comparing 'tips' vs 'checkpoint:baseline':
Shape:
  Rows: 244 vs 244 (+0)
  Cols: 9 vs 7 (+2)
Columns:
  + Added in left (2):   is_high, pct
  Common (7):            total_bill, tip, sex, smoker, day, time, size

# 5. Decide to discard experimental features and restore clean baseline
pytae [tips]> restore baseline
Restored checkpoint 'baseline' (244 rows x 7 cols).

pytae [tips]> -diff baseline
Values:
  Identical: all cell values match exactly.
```

---

### Scenario 2: Multi-Table Branching & Production Pipeline Export

```text
# 1. Ingest tables and declare parameters
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (10,000 rows x 6 cols).

pytae [orders]> cust = customers.csv
Loaded customers.csv as 'cust' (1,200 rows x 4 cols).

pytae [orders, cust]> min_spend = 50.0
Set @min_spend = 50.0

# 2. Checkpoint pre-join milestone
pytae [orders, cust]> checkpoint pre_join
Saved checkpoint 'pre_join' (2 tables: orders, cust; 1 variable: @min_spend).

# 3. Filter orders and join with customers
pytae [orders, cust]> switch orders
pytae [orders, cust*]> orders = -filter "amount >= @min_spend"
pytae [orders, cust*]> orders = -join cust on=customer_id -o clean_orders.parquet
Exported 6,420 rows to clean_orders.parquet.

# 4. Export reproducible production pipeline on exit
pytae [orders, cust*]> exit -s
Session code saved to /Users/analyst/projects/session.pt.
Exiting pytae REPL.
```

Generated `session.pt`:
```pytae
# Pytae Script: session.pt
# Generated: 2026-11-08 00:20:00

orders = orders.parquet
cust = customers.csv
min_spend = 50.0
orders = -filter "amount >= @min_spend"
orders = -join cust on=customer_id -o clean_orders.parquet
```

Run in production:
```bash
pytae session.pt
```
