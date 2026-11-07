# REPL Guide: Memory Management, History & Replay Scripts

[← Back to Master Reference](../../pytae.md)

This guide covers memory deallocation, OS page trimming, audit logs, session export (`exit -s`), batch replay pipelines, and Unix shell integration in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Memory Management](#memory-management)
  - [Removing Tables (`rm table <name>`, `rm table *`)](#removing-tables-rm-table-name-rm-table-)
  - [Immediate Memory Deallocation & OS Trimming](#immediate-memory-deallocation--os-trimming)
  - [Diagnostics & Inspection (`status`, `status table`, `status session`)](#diagnostics--inspection-status-status-table-status-session)
- [State Navigation & History](#state-navigation--history)
  - [Reset Hierarchy (`reset`, `reset <tbl>`, `reset initial`)](#reset-hierarchy-reset-reset-tbl-reset-initial)
  - [In-REPL History Audit Log (`history`)](#in-repl-history-audit-log-history)
  - [Persistent Arrow-Key History Navigation](#persistent-arrow-key-history-navigation)
- [Session Export & Replay Scripts](#session-export--replay-scripts)
  - [Exit-Time Export (`exit -s [path]`)](#exit-time-export-exit--s-path)
  - [Automatic Replay Script Filtering (`_is_replayable_entry`)](#automatic-replay-script-filtering-_is_replayable_entry)
  - [Path Canonicalization & Windows UNC Resolution](#path-canonicalization--windows-unc-resolution)
  - [Batch Replay Execution (`pytae -i < script.txt`)](#batch-replay-execution-pytae--i--scripttxt)
- [Shell Integration (`|`)](#shell-integration-)
- [Tab Autocompletion & Keybindings](#tab-autocompletion--keybindings)

---

## Memory Management

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
> Explicit category syntax (`rm table <name>`, `rm table *`, `rm checkpoint <name>`, or `rm checkpoint *`) is required. Categorical consistency eliminates ambiguity between in-memory tables and on-disk checkpoints.

### Immediate Memory Deallocation & OS Trimming

Unlike standard Python shells that retain memory pages in process heaps:
1. **Zero Lingering References**: Running `rm table <name>` or `rm table *` purges the table from `self.tables`, `self.orig_tables`, and `self.initial_tables`.
2. **OS Memory Trimming**: Pytae automatically triggers internal memory reclamation, calling `gc.collect()` and instructing the OS kernel to reclaim freed pages:
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

Inspect active session state, storage path, checkpoints, and RAM:
```text
pytae:my_lab [df: 344x7]> status session
=== REPL Session Status ===
Session Name  : my_lab (storage: ./my_lab)
Active Table  : df
Loaded Tables : 1 tables loaded
Checkpoints   : 2 saved
Process RAM   : ~129.2 MB (PID 7158)
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
   4: rm table df

pytae [df: 344x7]> history 3     # Show only the last 3 commands
```

### Persistent Arrow-Key History Navigation

The REPL maintains persistent readline history stored in `~/.pytae_history`. Use <kbd>↑</kbd> and <kbd>↓</kbd> arrow keys to recall previous commands. Multi-line commands containing `\` continuation are cleanly flattened into single lines in history for smooth arrow navigation.

---

## Session Export & Replay Scripts

Pytae provides a powerful workflow to turn interactive exploration into portable, automated pipeline scripts that run anywhere.

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
  - REPL UI controls and configuration (`tables`, `checkpoints`, `history`, `clear`, `set ...`) — display preferences, timing, and session bindings are never injected into replay scripts.
- **Included**:
  - File ingestion commands (`df = ...`, `load ...`).
  - Variable assignments (`orders_clean = orders -filter ...`).
  - Table removals (`rm table df1`, `rm table *`) to keep batch memory footprints low.
  - Persistent output file exports (`-o clean.parquet`, `-o report.csv`).

### Path Canonicalization & Windows UNC Resolution

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

## Tab Autocompletion & Keybindings

The Pytae REPL provides context-aware autocompletion via standard `readline`:

- **Commands & Verbs**: Press `[Tab]` at an empty prompt to view top-level commands (`switch`, `use`, `diff`, `rename`, `rm`, `set`, `checkpoint`, `restore`, `export`, etc.).
- **Flags**: Type `-` and press `[Tab]` to autocomplete CLI pipeline verbs (`-filter`, `-select`, `-mutate`, `-arrange`, `-pivot`, etc.).
- **Table & Checkpoint Names**: Autocompletes loaded tables after `switch `, `use `, `rename `, `diff `, and `rm table `, or checkpoints after `restore `.
- **Column Names**: Inside pipeline flags (`-select `, `-filter `, `-by `, `-arrange `), autocompletes column names of the active dataset or specified table prefix.
- **File Paths**: Autocompletes local filesystem files and directories after `load `, `-o `, or assignment (`df = `).
- **Settings**: Autocompletes configuration keys and options after `set ` (e.g. `set comma = ` -> `on`, `off`, or `set save`).
- **Keybindings**: <kbd>Ctrl+A</kbd> / <kbd>Home</kbd> jumps to the beginning of the line; <kbd>Ctrl+E</kbd> / <kbd>End</kbd> jumps to the end; <kbd>Ctrl+C</kbd> aborts multi-line continuation prompts.
