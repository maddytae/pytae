# REPL Guide: In-Memory Workbench, Checkpoints & Configuration

[← Back to Master Reference](../../pytae.md)

This guide covers in-memory snapshotting (`checkpoint`), instant workbench recovery (`rollback`), session status inspection, pipeline script export (`export script`), and configuration (`set`, `set save`) in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [In-Memory Workbench Architecture](#in-memory-workbench-architecture)
- [Checkpoints & Rollbacks](#checkpoints--rollbacks)
  - [Saving In-Memory Checkpoints (`checkpoint <name>`)](#saving-in-memory-checkpoints-checkpoint-name)
  - [Restoring Workbench State (`rollback [name]`)](#restoring-workbench-state-rollback-name)
  - [Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)](#listing--deleting-checkpoints-status-checkpoint-rm-checkpoint)
  - [Reverting to Disk Source (`reset`)](#reverting-to-disk-source-reset)
- [Session Status & Diagnostics (`status session`)](#session-status--diagnostics-status-session)
- [Exporting Reusable Pipelines (`export script`)](#exporting-reusable-pipelines-export-script)
- [REPL Configuration (`set`, `set save`)](#repl-configuration-set-set-save)
  - [Querying Active Settings (`set`)](#querying-active-settings-set)
  - [Display Preferences (`max_rows`, `max_cols`, `float_precision`, `comma`)](#display-preferences)
  - [Persisting Settings to Disk (`set save`, `~/.pytae/config.json`)](#persisting-settings-to-disk-set-save-pytaeconfigjson)
  - [Retirement of Legacy Disk Sessions](#retirement-of-legacy-disk-sessions)

---

## In-Memory Workbench Architecture

The Pytae REPL operates as a pure **in-memory workbench**:
- **Zero Disk Footprint**: Interactive sessions run in RAM without generating persistent disk session directories.
- **Flight Recorder History**: All commands entered during a session are auto-logged to `~/.pytae/history/history_<timestamp>.txt`. Exiting an empty session immediately purges empty history files.
- **Multi-Table Workspace**: Load datasets into named tables (`df1 = orders.parquet`, `df2 = sample:tips`), query them via fluent verbs or ANSI SQL (`-sql "SELECT * FROM df1 JOIN df2..."`), and manage multiple frames concurrently.

---

## Checkpoints & Rollbacks

### Saving In-Memory Checkpoints (`checkpoint <name>`)

Take an in-memory snapshot of all active tables, variables, and pipeline state:

```text
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust).
```

Checkpoints freeze table states in memory via zero-copy / deep-copy semantics, allowing instant milestone recovery without writing to disk.

### Restoring Workbench State (`rollback [name]`)

Revert the workbench to any previously saved checkpoint:

```text
# Revert to specific checkpoint
pytae [orders, cust, scratch_df]> rollback baseline
Restored checkpoint 'baseline' (2 tables: orders, cust; active: cust).

# Revert to the most recent checkpoint
pytae [orders, cust]> rollback
Restored checkpoint 'baseline' (2 tables: orders, cust).
```

All post-checkpoint scratch tables and uncommitted mutations are automatically dropped.

### Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)

```text
# List all saved checkpoints
pytae> status checkpoint
Checkpoints (2 saved):
  - baseline : orders, cust (created 2026-11-07 12:00:00)
  - filtered : orders (created 2026-11-07 12:05:00)

# Delete a single checkpoint from memory
pytae> rm checkpoint filtered
Removed checkpoint 'filtered'.

# Purge all checkpoints
pytae> rm checkpoint *
Cleared all saved checkpoints.
```

### Reverting to Disk Source (`reset`)

To revert active tables back to their original state loaded from disk:

```text
pytae [orders]> reset
Reset active table 'orders' to initial state.
```

---

## Session Status & Diagnostics (`status session`)

Inspect active in-memory tables, variable definitions, saved checkpoints, process RAM consumption, and history logs:

```text
pytae [df1]> status session
=== REPL Session Status ===
Mode          : in-memory workbench
Active Table  : df1
Loaded Tables : 1 tables loaded [df1]
Variables     : 2 defined [@min_val, @factor]
Checkpoints   : 1 saved (latest: baseline)
Process RAM   : ~45.2 MB (PID 12345)
------------------------------------------------------------
(Tip: Use 'status table [name]' for table details, 'status checkpoint [name]' for checkpoints, 'status var [name]' for variables)

# Verbose session status (includes history log path and active configuration)
pytae [df1]> status session -v
```

---

## Exporting Reusable Pipelines (`export script`)

Export the executed, state-mutating pipeline to an executable Pytae script (`.pt`) or standalone Python script (`.py`):

```text
# Export to a Pytae script (replayable via `pytae pipeline.pt`)
pytae> export script pipeline.pt

# Export with relative file paths (portable across machines)
pytae> export script pipeline.pt -relative

# Export to a standalone Python script using Polars / Pytae DataFrame
pytae> export script pipeline.py
```

The exported script automatically prunes rolled-back command branches, filters pure inspections (e.g. `-head`, `-schema`), and produces 100% reproducible data pipelines.

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
> - Use in-memory checkpoints (`checkpoint <name>`, `rollback [name]`) for instant undo and branching.
> - Use `export script <path.pt | path.py>` to persist, version-control, and share data pipelines.
> - Run exported scripts in batch mode via `pytae <script.pt>` or `pytae -run <script.pt>`.
