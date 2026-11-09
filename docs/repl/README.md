# Pytae Interactive REPL Workbench (`pytae -i`)

[← Back to Master Reference](../pytae.md)

The Pytae REPL is a high-performance in-memory exploratory workbench. Unlike traditional command-line tools that re-read gigabyte files from disk on every invocation, the Pytae REPL loads datasets into memory **once**, retains native multithreaded Polars Arrow memory buffers, and executes transformations, ANSI SQL, and Python logic at RAM speed.

---

## The 6 Pillars of the REPL Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PYTAE REPL ARCHITECTURAL PILLARS                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. IN-MEMORY WORKBENCH     │ Load multiple datasets once; transform and inspect at      │
│                            │ microsecond RAM speeds with zero repeated disk I/O.        │
├────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 2. NON-DESTRUCTIVE PREVIEWS│ Bare verbs (-head, -filter) display safe previews. State   │
│                            │ is modified only through explicit assignment (df = ...).   │
├────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 3. ZERO-RAM CHECKPOINTS    │ Snapshots (checkpoint <name>) serialize to ephemeral disk  │
│                            │ Arrow IPC. Instant rollback (restore) with 0 MB RAM cost.  │
├────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 4. EPHEMERAL SANDBOXING    │ Embedded Python (py) runs in an ephemeral scope with zero   │
│                            │ residual RAM footprint. Explicit .to_pytae() handoff.      │
├────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 5. REPRODUCIBLE SCRIPTS    │ Automatic flight recorder logs every step. Prunes undo paths│
│                            │ and exports clean .pt (Pytae) or .py (Python) pipelines.   │
├────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 6. OS PAGE DEALLOCATION    │ Deleting tables (rm table) immediately invokes kernel page │
│                            │ trimming (malloc_trim, Mach task, working set).            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 30-Second Quickstart

```bash
# Launch the interactive workbench
pytae -i
```

```text
# 1. Ingest datasets into named tables
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (100,000 rows x 6 cols).

pytae [orders: 100,000x6]> cust = customers.csv
Loaded customers.csv as 'cust' (15,000 rows x 5 cols).

# 2. Safe, non-destructive preview
pytae [orders, cust]> -filter "amount > 500" -head 3

# 3. Explicit state mutation
pytae [orders, cust]> orders = -filter "amount > 500" -mutate "tax = amount * 0.08"

# 4. Instant named snapshot (0 MB RAM overhead)
pytae [orders, cust]> checkpoint baseline
Saved checkpoint 'baseline' (2 tables: orders, cust).

# 5. Relational joins & ANSI SQL across tables
pytae [orders, cust]> enriched = orders -join cust on=customer_id how=left
pytae [orders, cust, enriched]> top_spenders = -sql "SELECT cust.name, sum(orders.amount) as total FROM orders JOIN cust ON orders.customer_id = cust.customer_id GROUP BY 1 ORDER BY total DESC LIMIT 5"

# 6. Milestone diffing & instant rollback
pytae> -diff baseline
pytae> restore baseline

# 7. Export reproducible pipeline and exit
pytae> export pipeline.pt -relative
pytae> exit -s
```

---

## Master Command Reference

| Category | Command | Syntax Example | Description |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Direct Assignment | `df = file.parquet` | Load dataset into named table. |
| | Reader Options | `df = file.csv -dlim "," -nrows 100` | Ingest with custom delimiter, encoding, or row limits. |
| | Excel Sheets | `df = sales.xlsx -opts "sheet=Q1"` | Specify sheet, header, or skiprows via `-opts`. |
| | Glob Ingestion | `sales = "parts/*.parquet"` | Ingest multi-file partitions into unified table. |
| | Bundled Samples | `tips = sample:tips` | Instant access to bundled sample datasets (`penguins`, `tips`, `iris`, etc.). |
| **Table Management** | Listing Tables | `status table` | Display active table details and memory footprint. |
| | Switching Cursor | `switch <name>` | Select active table cursor for bare commands. |
| | Zero-Copy Rename | `rename <old> <new>` | Instant $O(1)$ pointer reassignment. |
| | Subject-First Verbs| `<tbl> -<verb>` | Run verb directly on non-active table without switching. |
| | Deleting Tables | `rm table <name>`, `rm table *` | Purge tables and return memory pages to the OS kernel. |
| **Pipelines & Verbs** | Safe Preview | `-filter "..."`, `-head 5` | Non-destructive preview matching terminal CLI output. |
| | State Mutation | `df = -filter "..."` | Update table state via explicit assignment. |
| | Relational Joins | `-join <right> on=key how=left` | Relational join across loaded tables. |
| | Inspection | `-schema`, `-cols`, `-summary` | Instant schema, column list, or statistical glimpse. |
| **Advanced Query** | ANSI SQL | `-sql "SELECT ..."` | Native Polars SQLContext querying across active tables. |
| | Python Eval | `py <expr>` | Single-line Python expression evaluation. |
| | Python Block | `py:` ... `end` | Multi-line Python block with ephemeral RAM sandboxing. |
| | Register Table | `py: df.to_pytae('tbl')` | Register Python DataFrame back to Pytae workbench. |
| **Variables & Config** | Session Variable | `threshold = 1000` | Define typed session parameter referenced as `@threshold`. |
| | Variable Status | `status var` | List defined variables and values. |
| | Remove Variable | `rm var <name>`, `rm var *` | Purge session variable definitions. |
| | Display Settings | `set max_rows = 25` | Configure `max_rows`, `max_cols`, `float_precision`, `comma`. |
| | Persist Settings | `set save` | Save preferences to `~/.pytae/config.json`. |
| | Session Status | `status`, `status -v` | Complete session diagnostics (RAM, tables, variables, checkpoints). |
| **Checkpoints** | Save Snapshot | `checkpoint <name>` | Save state to ephemeral IPC disk (0 MB active RAM). |
| | Instant Restore | `restore [name]` | Revert workbench state to checkpoint. |
| | Milestone Diff | `-diff`, `-diff <cp>` | Compare active table against checkpoint state. |
| | Revert to Source | `reset`, `reset initial` | Revert to latest checkpoint or initial file read state. |
| | Checkpoint Status | `status checkpoint` | List saved checkpoints and disk usage. |
| | Remove Checkpoint | `rm checkpoint <name>` | Delete named checkpoint. |
| **Export & Replay** | In-Session Export | `export <path> [-relative]` | Export clean, reproducible pipeline (`.pt` or `.py`). |
| | Exit Export | `exit -s [path] [-relative]` | Export session pipeline on exit to `./session.pt`. |
| | History Audit Log | `history`, `history <n>` | Display numbered session command history. |
| | CLI Log Conversion | `pytae -export <hist> -o <out>`| Post-hoc conversion of history logs to `.pt` or `.py`. |
| | Headless Execution | `pytae pipeline.pt` | Run Pytae pipeline headlessly to completion. |
| | Interactive Preload| `pytae -i pipeline.pt` | Preload script into interactive REPL session. |

---

## Detailed Topic Manuals

Dive deeper into specific subsystems:

1. **[Workbench & Multi-Table Management](workbench_tables.md)**:
   Launching the shell, ingesting local/remote/sample files, reader options, managing multiple tables, zero-copy renaming, shell navigation, and keybindings.
2. **[In-Memory Pipelines & Data Inspection](pipelines_inspection.md)**:
   Exploration vs. mutation semantics, chaining CLI verbs at RAM speed, relational joins, and non-destructive inspection tools (`-head`, `-cols`, `-schema`, `-diff`).
3. **[SQL & Python Interop (Ephemeral Python Sandboxing)](sql_python_interop.md)**:
   Cross-table ANSI SQL queries, embedded Python evaluation, multi-line blocks, the ephemeral memory sandboxing architecture, and explicit `.to_pytae()` table conversion.
4. **[Session Variables & Configuration](variables_config.md)**:
   Defining session `@parameters`, nested configuration traversal, using variables in pipelines, display preferences (`set`), and persisting settings (`set save`).
5. **[Checkpoints, History Audit, Pipeline Export & Replay](checkpoints_history_replay.md)**:
   Ephemeral IPC snapshotting (`checkpoint`), zero-RAM storage, instant state rollback (`restore`), milestone schema/value diffing (`-diff`), flight recorder audit logs, clean script export (`export`, `exit -s`), automatic undo branch pruning, CLI history conversion (`pytae -export`), batch execution, and kernel memory page deallocation.
