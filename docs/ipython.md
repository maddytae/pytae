# Pytae IPython & Jupyter Workbench

Pytae's interactive workbench runs natively inside **IPython** and **Jupyter** (JupyterLab, VS Code Notebooks, Google Colab).

There is no separate shell to launch and no `%load_ext` command to remember — just import `pytae`:

```python
import pytae as pt
```

The moment `import pytae as pt` runs inside an active IPython or Jupyter session, Pytae silently registers:
- Workbench magics (`%pt` / `%%pt`, `%checkpoint`, `%restore`, `%status`, `%free`, `%set`, `%export`, `%exit -s`)
- Persistent display formatters for `pytae.DataFrame` (both terminal plain-text and Jupyter HTML)
- Context-aware Tab completion (CLI `-flags`, DataFrame names, column names, and checkpoint names)

*(Outside IPython — e.g., CLI commands or plain `python script.py` — IPython is never imported, so there is zero startup overhead. Set `PYTAE_NO_IPYTHON_EXT=1` if you ever want to import `pytae` inside IPython without registering magics.)*

---

## Quick Start

```python
import pytae as pt

# Load data with Python or %pt
df = pt.sample("penguins")
# or: df = %pt sales.parquet

# Save an ephemeral disk checkpoint (0 MB RAM)
%checkpoint raw

# Run any Pytae CLI pipeline in-process (immutable by default!)
heavy = %pt df -filter "body_mass_g > 4000" -arrange "body_mass_g desc"

# Inspect tracked tables, checkpoints, OS process RSS, and settings
%status

# Roll back DataFrame state strictly and reclaim RAM
%restore raw

# Delete a large DataFrame AND scrub hidden IPython Out/_ cache references
%free heavy

# Export clean, runnable .py or .ipynb (auto-prunes errors, rollbacks & previews)
%export analysis.py
```

---

## Magic Reference

### 1. `%pt` and `%%pt` — Full In-Process CLI Pipelines (Immutable)

`%pt` executes Pytae's full CLI grammar (`-filter`, `-mutate`, `-select`, `-by`, `-agg`, `-pivot`, `-long`, `-wide`, `-join`, `-concat`, `-outliers`, `-dups`, `-distinct`, `-mask`, `-freq`, `-hist`, `-bar`, `-scatter`, `-corr`, `-plot`, `-browse`, `-diff`, `-meta`, `-schema`, `-glimpse`, `-sql`, `-o`, etc.) **in-process** with zero subprocess overhead.

- **Immutable by default**: `%pt` never mutates an existing DataFrame in-place. Assign explicitly with `res = %pt ...` or `%%pt res`.
- **Works on RAM DataFrames, disk paths, and `clip`**: Pass a variable name (`df`), a file path (`sales.parquet`), `sample:penguins`, or `clip`.
- **Supports `@var` interpolation**: Reference Python scalars/lists in expressions (`cutoff = 4000; %pt df -filter "body_mass_g > @cutoff"`).

#### Line magic (`%pt`)
```python
# Explore without modifying `df`
%pt df -filter "species == 'Adelie'" -head 5

# Assign result to a new DataFrame
adelie = %pt df -filter "species == 'Adelie'" -mutate "mass_kg = body_mass_g / 1000"

# Load from disk + filter in one step
recent = %pt sales.parquet -filter "year == 2025" -select "id,region,amount"

# Terminal visualizations & exports
%pt df -hist body_mass_g
%pt df -freq island
%pt df -o out/penguins.parquet
%pt df -o clip

# SQL across all DataFrames in IPython's namespace
top = %pt -sql "SELECT island, COUNT(*) AS n, AVG(body_mass_g) AS avg_mass FROM df GROUP BY island"

# In-memory multi-table joins, concats, docs & TUI browser
joined = %pt orders -join "right=customers, on=cust_id, how=left"
%pt -doc "diff on key"
%pt df -browse
```

#### Cell magic (`%%pt` and `%%pt [var] -sql`)
Write readable multi-line pipelines without `\` continuations. Put an optional target variable name on the `%%pt` header line, or add `-sql` for full multi-line SQL across all live DataFrames (without colliding with `jupysql`'s `%%sql`):

```python
%%pt summary
df
-dropna "body_mass_g"
-filter "species != 'Gentoo'"
-by "species, island"
-agg "avg_mass = mean(body_mass_g), n = count()"
```

```sql
%%pt top_customers -sql
SELECT c.name, SUM(o.amount) AS total
FROM orders o
JOIN customers c ON o.cust_id = c.id
WHERE o.amount > @min_amt
GROUP BY c.name
ORDER BY total DESC
```
-arrange "avg_mass desc"
```

Multi-line SQL via `%%pt`:
```python
%%pt top_islands
-sql "
SELECT island, COUNT(*) AS n, AVG(body_mass_g) AS avg_mass
FROM df
GROUP BY island
ORDER BY avg_mass DESC
"
```

---

### 2. `%checkpoint` & `%restore` — Atomic Workbench Time-Machine

Checkpoints always capture the **entire workbench state** — every DataFrame (`pytae`, `polars`, `pandas`) spilled to fast Arrow IPC on disk (**0 MB RAM overhead**) plus all user data variables (scalars, lists, dicts, sets, `Path`, dates). Selective per-table checkpointing is intentionally disallowed so `%restore` is always atomic and consistent.

```python
%checkpoint raw                  # Snapshot entire workbench (all DataFrames + user variables)
%checkpoint list                 # List saved checkpoints & disk size
%checkpoint diff df raw          # Compare current `df` against checkpoint `raw`
%checkpoint rm raw               # Delete a checkpoint (or `*` for all)
```

**Strict Restore (`%restore`)**:
```python
%restore raw    # Restore checkpoint `raw`
%restore        # Restore the most recent checkpoint
```
`%restore` always performs a **strict restore** of workbench state:
1. Restores all snapshotted DataFrames (in their exact original Python types) and all snapshotted user variables.
2. Drops any DataFrames or user variables created *after* the checkpoint.
3. Scrubs stale references from IPython's `Out` / `_` cache and trims OS RSS.
4. Keeps your Python imports, functions, and classes intact.

---

### 3. `%status` — Workbench & Memory Overview

```python
%status                  # All tracked DataFrames (type, shape, RAM), checkpoints, OS RSS, settings
%status -v               # Include total DataFrame RAM
%status df               # Detailed shape, RAM, null counts, and columns for `df`
%status df -v            # Full column-by-column schema & null breakdown
%status checkpoint       # List all checkpoints
%status checkpoint raw   # Inspect tables inside checkpoint `raw`
```

---

### 4. `%free` — Delete DataFrames & Reclaim OS RAM

In IPython, plain `del df` often fails to free RAM because IPython's output cache (`Out[N]`, `_`, `_N`) still holds strong references to previously displayed DataFrames, and OS allocators retain freed pages.

`%free` deletes the variable(s), **scrubs all hidden references from `Out` / `_`**, runs `gc.collect()`, trims the OS working set, and reports the RSS change:

```python
%free big_df             # Delete `big_df`, scrub Out/_ cache, trim OS RSS
%free df1 df2            # Delete multiple DataFrames + reclaim RAM
%free *                  # Delete all tracked DataFrames + reclaim RAM
%free                    # Keep named variables; scrub stale Out/_ DataFrame refs + trim RAM
```

---

### 5. `%set` — Persistent Display Formatting

Configure DataFrame rendering for both terminal IPython (`text/plain`) and Jupyter (`text/html`):

```python
%set                                              # Show current settings
%set max_rows=20 max_cols=12                      # Update for current session
%set float_precision=2 comma=true                 # Format floats & thousands separators
%set save                                         # Persist permanently to ~/.pytae/config.json
%set reset                                        # Reset to defaults
```

---

### 6. `%export` & `%exit -s` — Clean Script / Notebook Export

Export your session history to a standalone `.py` script or `.ipynb` notebook:

```python
%export analysis.py      # Standalone runnable Python script
%export analysis.ipynb   # Valid Jupyter notebook (nbformat v4)
%exit -s analysis.py     # Export and exit IPython cleanly
%exit -s                 # Export to ./session.py and exit
```

What `%export` automatically cleans up:
- **Errored cells** (syntax errors, failed magics, raised exceptions)
- **Rolled-back cells** (everything executed between `%checkpoint` and `%restore`)
- **Duplicate & dead overwritten assignments** (e.g. consecutive duplicate cells or `x = ...` immediately overwritten without being read, while preserving `.to(...)` / `-o` side effects)
- **Workbench & inspection noise** (`%status`, `%checkpoint`, `%restore`, `%free`, `%set`, `%exit`, bare `df`, unassigned `df.head()`, unassigned `%pt df -head`)
- **Standalone Python rewrite** (for `.py`): converts `df = %pt sample:penguins` → `df = pt.sample('penguins')` and `res = %pt ...` → `res = pt.eval_cli(..., locals())` so `python analysis.py` runs out of the box.

#### CLI History: Inspect, Search, Export & Reload Past Sessions
Forgot to run `%export`, want to look up what you ran yesterday, or resume a past session? `pytae -history` reads `~/.ipython/profile_default/history.sqlite` directly:

```bash
pytae -history                           # List last 25 IPython sessions (ID, timestamp, cmds, preview)
pytae -history -n 50                     # List last 50 sessions
pytae -history 42                        # View raw cells of session #42
pytae -history ~1                        # View latest session (~2 for two ago)
pytae -history 42 -clean                 # Print cleaned/pruned Python to stdout
pytae -history -search "penguins"        # Search across all sessions
pytae -history 42 -o code.py             # Export session #42 to standalone Python
pytae -history ~1 -o nb.ipynb            # Export latest session to Jupyter notebook
pytae -history 42 -load                  # Replay cleaned session #42 into IPython (populates %history)
pytae code.py -load                      # Replay a .py script into IPython (populates %history)
pytae nb.ipynb -load                     # Replay a .ipynb notebook into IPython (populates %history)
pytae -history -db ~/alt/history.sqlite  # One-off history DB path override
pytae -history -set-db ~/alt/history.sqlite  # Persist custom history DB path in ~/.pytae/config.json
pytae -history -set-db reset             # Reset history DB path back to IPython default
```

> **Tip (`-load` vs. IPython's built-in `%run`):**
> - Use **`pytae analysis.py -load`** / **`pytae analysis.ipynb -load`** (or `pytae -history 42 -load`) when you want each cell replayed into `%history`, ↑ arrow, and `%export`.
> - Inside an already-running IPython session, use IPython's native **`%run -i analysis.py`** (or **`%run analysis.ipynb`**) to silently execute a script/notebook and load its variables/DataFrames into memory without adding its lines to `%history`.

---

## Themes & Syntax Highlighting in IPython

IPython + Pygments natively provides 49+ color themes and 24-bit true-color syntax highlighting:

```python
%colors gruvbox-dark     # Switch live (neutral, linux, lightbg, gruvbox-dark, nocolor)
```

To set a permanent theme in `~/.ipython/profile_default/ipython_config.py`:
```python
c = get_config()
c.TerminalInteractiveShell.true_color = True
c.InteractiveShell.colors = "linux"
c.TerminalInteractiveShell.highlighting_style = "dracula"  # monokai, nord, one-dark, etc.
```
