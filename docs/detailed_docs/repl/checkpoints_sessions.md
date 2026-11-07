# REPL Guide: Checkpoints & Persistent Sessions

[← Back to Master Reference](../../pytae.md)

This guide covers disk-backed snapshotting (`checkpoint`), instant workbench recovery (`restore`), persistent project sessions, and interactive configuration (`set`) in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Checkpoints (Disk-Backed & RAM-Isolated)](#checkpoints-disk-backed--ram-isolated)
  - [Saving Checkpoints (`checkpoint <name>`)](#saving-checkpoints-checkpoint-name)
  - [Zero RAM Overhead Guarantee](#zero-ram-overhead-guarantee)
  - [Ephemeral Mode & Automatic Temp Cleanup](#ephemeral-mode--automatic-temp-cleanup)
  - [Mid-Session Project Promotion](#mid-session-project-promotion)
  - [Listing & Deleting Checkpoints (`status checkpoint`, `rm checkpoint`)](#listing--deleting-checkpoints-status-checkpoint-rm-checkpoint)
  - [Restoring Workbench State (`restore <name>`)](#restoring-workbench-state-restore-name)
  - [Reloading After `rm *` via `restore <name>`](#reloading-after-rm--via-restore-name)
- [Persistent REPL Sessions](#persistent-repl-sessions)
  - [Unified Path-First Session Architecture](#unified-path-first-session-architecture)
  - [Session Manifest Structure](#session-manifest-structure)
  - [Inspecting & Managing Sessions (`status session`, `sessions`)](#inspecting--managing-sessions-status-session-sessions)
  - [Environment Variable `PYTAE_SESSIONS_DIR`](#environment-variable-pytae_sessions_dir)
- [REPL Configuration (`set`)](#repl-configuration-set)
  - [Querying Settings (`set`, `set <key>`)](#querying-settings-set-set-key)
  - [Starting a Session (`set new_session = <name|path>`)](#starting-a-session-set-new_session--namepath)
  - [Loading a Session (`set load_session = <name|path>`)](#loading-a-session-set-load_session--namepath)
  - [Saving / Relocating a Session (`set save_session = <name|path>`)](#saving--relocating-a-session-set-save_session--namepath)
  - [Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`, `convert = all`)](#checkpoint-storage-format-set-checkpoint_format--parquetipc-convert--all)
  - [Replay Script Auto-Save (`set save_code = <path>`)](#replay-script-auto-save-set-save_code--path)
  - [Display Preferences (`max_rows`, `max_cols`, `float_precision`, `comma`)](#display-preferences-set-max_rows-max_cols-float_precision-comma)
  - [Combining Multiple Settings on One Line](#combining-multiple-settings-on-one-line)

---

## Checkpoints (Disk-Backed & RAM-Isolated)

### Saving Checkpoints (`checkpoint <name>`)

Save a complete snapshot of the entire workbench to disk:

```text
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust).
```

### Zero RAM Overhead Guarantee

Tables are written to disk storage (`.ipc` or `.parquet`). Checkpoints consume **0 MB of active RAM**. Creating a checkpoint frees intermediate memory while establishing a safe restore point.

### Ephemeral Mode & Automatic Temp Cleanup

When running `pytae -i` without binding to a named session, checkpoints are written to an isolated, secure OS temporary folder (e.g. `/tmp/pytae_cp_xxxxxx/` or `$TMPDIR/pytae_cp_xxxxxx/` on macOS/Linux, `%TEMP%\pytae_cp_xxxxxx\` on Windows).
- **Automatic Cleanup**: When you exit or close the REPL, the temporary checkpoint folder is automatically purged from disk, leaving zero lingering files on your machine.
- **Inspect Location**: Run `status checkpoint -v` anytime to inspect the exact temporary directory path and on-disk byte sizes.

### Mid-Session Project Promotion

If you start in ephemeral mode, save several checkpoints, and decide you want to keep them permanently, simply bind a session name:

```text
pytae> set new_session = my_permanent_project
```
Pytae immediately promotes all existing temporary checkpoints into `./my_permanent_project/` (or your target path) while keeping all in-memory tables loaded.

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

### Restoring Workbench State (`restore <name>`)

Restore the workbench to any saved checkpoint milestone:

```text
pytae [orders, cust, scratch_df]> restore baseline
Restored checkpoint 'baseline' (2 tables: orders, cust; active: cust).
```
All post-checkpoint scratch tables (`scratch_df`) are automatically dropped and garbage collected. Active RAM strictly matches the checkpoint state.

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
```

### Environment Variable `PYTAE_SESSIONS_DIR`

Configure default session directory search path:

```bash
export PYTAE_SESSIONS_DIR="/Volumes/ExternalSSD/pytae_sessions"
pytae -i
```

**Directory Precedence Order**:
1. Explicit In-REPL Setting: `set new_session = <path>` or `set load_session = <path>`.
2. OS Environment Variable: `PYTAE_SESSIONS_DIR`.
3. Default: Current working directory `Path.cwd()`.

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

Query an individual setting with `set <key>`:
```text
pytae> set checkpoint_format
checkpoint_format = ipc (options: ipc, parquet)
```

### Starting a Session (`set new_session = <name|path>`)

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

```text
# Load session from current working directory
pytae> set load_session = sales_q3
Switched to session 'sales_q3'. Restored latest checkpoint 'v2'.
pytae:sales_q3 [sales_q3: 150,000x12]>
```

### Saving / Relocating a Session (`set save_session = <name|path>`)

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

### Checkpoint Storage Format (`set checkpoint_format = parquet|ipc`, `convert = all`)

Control the on-disk serialization format used for session checkpoints:
- **`ipc` (Default)**: Uncompressed Arrow IPC streaming format (`.ipc`). Maximum write/read speed.
- **`parquet`**: Compressed columnar Parquet format (`.parquet`). Minimizes disk usage on storage-constrained environments or USB drives.

```text
# Set future format
pytae> set checkpoint_format = parquet

# Convert all existing checkpoints to Parquet and update future format
pytae> set checkpoint_format = parquet, convert = all
Converting 2 existing checkpoint(s) to parquet...
  - cp1: converted (320.0 MB -> 62.4 MB)
  - cp2: converted (320.0 MB -> 64.1 MB)
All 2 checkpoint(s) converted. Set checkpoint_format = parquet.
```

### Replay Script Auto-Save (`set save_code = <path>`)

Designate a file path to automatically capture and write your session's replayable command script upon exit (also supported via alias `save_commands`):

```text
pytae> set save_code = pipeline.txt
Set save_code = 'pipeline.txt' (session commands will be auto-saved here on exit).
```

### Display Preferences (`set max_rows`, `max_cols`, `float_precision`, `comma`)

- **Row Truncation (`set max_rows = <int>|default`, alias: `rows`)**: Controls rows printed in table previews. Defaults to `10`.
- **Column Truncation (`set max_cols = <int>|all|default`, alias: `cols`)**: Limits columns displayed in wide tables. Defaults to `all`.
- **Floating-Point Precision (`set float_precision = <int>|auto|default`, alias: `precision`)**: Sets decimal display places. Defaults to `auto`. (Does not affect unrounded IEEE 754 exports).
- **Thousands Comma Separator (`set comma = on|off`)**: Formats numbers with comma separators (e.g. `1,234,567`). Numeric columns remain native integers/floats in memory and exports.

### Combining Multiple Settings on One Line

```text
pytae> set new_session = my_lab, save_code = pipeline.txt
pytae> set new_session = /Volumes/Share/sessions/analytics, checkpoint_format = parquet
```
