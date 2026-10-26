"""Interactive REPL (Read-Eval-Print Loop) for pytae with in-memory state and undo/redo.

Provides stateful, iterative data manipulation without repeatedly reloading datasets from disk.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import Any, Callable

import polars as pl

from pytae.cli_run import _format_table, _process_path
from pytae.readers import DataFrameReader, get_reader

try:
    import readline  # Enable arrow keys, line editing, and history in terminal
except ImportError:
    readline = None


REPL_BANNER = """\
================================================================================
                         PYTAE INTERACTIVE REPL                                 
================================================================================
Type 'help' for REPL commands, 'reset' to revert to original, or 'exit' to quit.
"""

REPL_HELP = """\
================================================================================
                             PYTAE REPL COMMANDS                                
================================================================================
MODE 1: SINGLE-TABLE EXPLORATION (pytae <file> -i):
  Commands apply directly to the loaded table without any prefix:
  -filter <condition>    : Filter rows, e.g. -filter "species == 'Gentoo'"
  -mutate <expr>         : Add/modify columns, e.g. -mutate "mass_kg = body_mass_g / 1000"
  -select <cols>         : Column projection, e.g. -select "species,island,mass_kg"
  -arrange <specs>       : Sort rows, e.g. -arrange "mass_kg desc"
  -by <g> -agg <specs>   : Grouped aggregation, e.g. -by species -agg "m=mass:mean, n=count"
  -distinct <cols>       : Deduplicate rows
  -dropna [cols]         : Drop missing values
  -fillna <specs>        : Impute missing values
  -head [N] / -tail [N]  : Non-destructive preview of top/bottom N rows (e.g. -head 10)
  -shape / -cols /-dtype : Non-destructive metadata inspection
  -o <path> / -o clip    : Export table to file (Parquet/CSV/NDJSON) or clipboard

MODE 2: MULTI-TABLE WORKBENCH (pytae -i):
  Load multiple datasets and operate with subject-first syntax (<tbl> -<cmd>):
  <var> = <path.parquet> : Ingest dataset into a named variable (e.g. df1 = orders.parquet)
  <tbl> -head [N]        : Preview specific table (e.g. df1 -head 5, df2 -head 3)
  <tbl> -shape / -cols   : Inspect table metadata (e.g. df1 -shape, df2 -cols)
  <tbl> -<pipeline>      : Run pipeline directly on table (e.g. df1 -filter "amount > 100")
  <tbl> -join <t2> on=<k>: Join tables (e.g. df1 -join df2 on=cust_id -o merged.parquet)
  <tbl> -o <path>        : Export specific table (e.g. df1 -o clean_orders.parquet)
  <var> = <tbl> -<pipe>  : Assign pipeline result to new variable (e.g. df3 = df1 -filter ...)
  <var> = <t1> -join <t2>: Assign join result (e.g. df3 = df1 -join df2 on=cust_id)
  <var> = -sql "<query>" : Create table from ANSI SQL across loaded tables
  tables                 : List all loaded datasets in memory
  use <name>             : Switch active dataset (or type bare table name e.g. df1)

STATE NAVIGATION (Undoable):
  undo                   : Revert the last transformation step
  redo                   : Re-apply the last undone transformation step
  reset                  : Restore original dataset state
  history                : Show numbered transformation log
  checkpoint <name>      : Save snapshot of current table state
  restore <name>         : Restore table to saved checkpoint
  checkpoints            : List saved checkpoints
  exit                   : Exit REPL

QUERY & PYTHON EXPRESSIONS:
  -sql "<query>"         : Run ANSI SQL on active table or across named tables
                           e.g. -sql "SELECT df1.*, df2.name FROM df1 JOIN df2 ON df1.id = df2.id"
  py <expr>              : Evaluate Python expression with 'df' (pytae) and 'pldf' (polars)
================================================================================\
"""

_DISALLOWED_ALIASES: dict[str, str] = {
    # Session controls hyphenated forms (must be bare words)
    "-help": "help",
    "--help": "help",
    "-exit": "exit",
    "--exit": "exit",
    "-status": "status",
    "--status": "status",
    "-reset": "reset",
    "--reset": "reset",
    "-undo": "undo",
    "--undo": "undo",
    "-redo": "redo",
    "--redo": "redo",
    "-history": "history",
    "--history": "history",
    "-tables": "tables",
    "--tables": "tables",
    "-checkpoint": "checkpoint",
    "--checkpoint": "checkpoint",
    "-checkpoints": "checkpoints",
    "--checkpoints": "checkpoints",
    "-restore": "restore",
    "--restore": "restore",
    "-use": "use",
    "--use": "use",
    "-load": "load",
    "--load": "load",
    # Double-hyphen data inspection forms
    "--shape": "-shape",
    "--cols": "-cols",
    "--dtype": "-dtype",
    "--nulls": "-nulls",
    "--glimpse": "-glimpse",
    "--describe": "-describe",
    "--head": "-head",
    "--tail": "-tail",
    # Double-hyphen pipeline flags
    "--filter": "-filter",
    "--mutate": "-mutate",
    "--select": "-select",
    "--arrange": "-arrange",
    "--by": "-by",
    "--agg": "-agg",
    "--distinct": "-distinct",
    "--count": "-count",
    "--sample": "-sample",
    "--seed": "-seed",
    "--frac": "-frac",
    "--fillna": "-fillna",
    "--dropna": "-dropna",
    "--clean_columns": "-clean_columns",
    "--mask": "-mask",
    "--unmask": "-unmask",
    "--long": "-long",
    "--wide": "-wide",
    "--pivot": "-pivot",
    "--rename": "-rename",
    "--join": "-join",
    "--concat": "-concat",
    "--sql": "-sql",
    "--output": "-o <path>",
    "-output": "-o <path>",
    "--out_dir": "-out_dir",
    "-out-dir": "-out_dir",
    "--out-dir": "-out_dir",
    "-od": "-out_dir",
    "--od": "-out_dir",
    "-limit": "-nrows",
    "--limit": "-nrows",
    "--nrows": "-nrows",
    "-tolerance": "-tol",
    "--tolerance": "-tol",
    "--tol": "-tol",
    # Synonym / legacy aliases
    "columns": "-cols",
    "-columns": "-cols",
    "--columns": "-cols",
    "dtypes": "-dtype",
    "-dtypes": "-dtype",
    "--dtypes": "-dtype",
    "vars": "tables",
    "datasets": "tables",
    "cp": "checkpoint",
    "-cp": "checkpoint",
    "--cp": "checkpoint",
    "cps": "checkpoints",
    "-cps": "checkpoints",
    "--cps": "checkpoints",
    "tag": "checkpoint",
    "tags": "checkpoints",
    "switch": "use",
    "-interactive": "-i",
    "--interactive": "-i",
    "-repl": "-i",
    "--repl": "-i",
    "-examples": "-cheatsheet",
    "--examples": "-cheatsheet",
    "checkout": "restore",
    "read": "load",
    "open": "load",
    "save": "-o <path>",
    "export": "-o <path>",
    "quit": "exit",
    "q": "exit",
    ":q": "exit",
    "?": "help",
}

_BARE_PIPELINE_VERBS = frozenset(
    (
        "filter",
        "mutate",
        "select",
        "rename",
        "arrange",
        "by",
        "agg",
        "distinct",
        "count",
        "dropna",
        "fillna",
        "clean_columns",
        "mask",
        "unmask",
        "long",
        "wide",
        "pivot",
        "sample",
        "join",
        "concat",
        "shape",
        "cols",
        "dtype",
        "nulls",
        "glimpse",
        "describe",
        "head",
        "tail",
        "sql",
    )
)


class PytaeRepl:
    """Stateful interactive REPL environment for pytae."""

    def __init__(
        self,
        df: Any | None = None,
        path: Path | str | None = None,
        paths: list[Path | str] | None = None,
        prompt: str = "pytae",
    ) -> None:
        self.prompt = prompt
        self.undo_stack: list[tuple[str, pl.DataFrame]] = []
        self.redo_stack: list[tuple[str, pl.DataFrame]] = []
        self.tables: dict[str, pl.DataFrame] = {}
        self.orig_tables: dict[str, pl.DataFrame] = {}
        self.checkpoints: dict[str, pl.DataFrame] = {}
        self.table_sources: dict[str, str] = {}
        self.history: list[str] = []

        self.path: Path | None = None
        self.path_str: str | None = None
        self.orig_df: pl.DataFrame | None = None
        self.current_df: pl.DataFrame | None = None

        if paths:
            for p_item in paths:
                raw_item = str(p_item)
                if "=" in raw_item and not raw_item.startswith("-"):
                    var_name, path_val = raw_item.split("=", 1)
                    var_name = var_name.strip()
                    path_val = path_val.strip()
                else:
                    path_val = raw_item
                    var_name = Path(path_val).stem
                p = Path(path_val).expanduser()
                if not p.exists():
                    from pytae import DATA_PATH

                    candidate = DATA_PATH / p.name
                    if not candidate.exists():
                        candidate = DATA_PATH / f"{p.stem}.parquet"
                    if candidate.exists():
                        p = candidate
                if p.exists():
                    try:
                        reader = get_reader(p)
                        t_df = reader.to_polars()
                        self.tables[var_name] = t_df
                        self.orig_tables[var_name] = t_df.clone()
                        self.table_sources[var_name] = p.name
                        self.current_df = t_df
                        self.orig_df = t_df.clone()
                        self.path_str = var_name
                    except Exception:
                        pass
        elif df is not None:
            self._set_initial_df(df)
            self.path = Path(path) if path else None
            self.path_str = self.path.name if self.path else "<memory>"
            initial_name = self.path_str or "df"
            self.tables[initial_name] = self.current_df
            self.orig_tables[initial_name] = self.current_df.clone()
            self.table_sources[initial_name] = str(self.path) if self.path else "<memory>"
        elif path is not None:
            self.path = Path(path)
            self._load_file(self.path)
            initial_name = self.path_str or self.path.stem or "df"
            self.tables[initial_name] = self.current_df
            self.orig_tables[initial_name] = self.current_df.clone()
            self.table_sources[initial_name] = self.path.name

    def _set_initial_df(self, df: Any) -> None:
        from pytae.dataframe import DataFrame as PytaeDataFrame

        if isinstance(df, PytaeDataFrame):
            df = df._df
        if not isinstance(df, pl.DataFrame):
            try:
                df = pl.from_pandas(df)
            except Exception:
                pass
        self.orig_df = df
        self.current_df = df

    def _load_file(self, path: Path | str) -> None:
        p = Path(path).expanduser()
        if str(p).startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = str(p)[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                raise FileNotFoundError(f"Unknown sample dataset '{sample_name}'. Available: {available}")
            p = sample_file
        elif not p.exists():
            from pytae import DATA_PATH

            candidate = DATA_PATH / p.name
            if not candidate.exists():
                candidate = DATA_PATH / f"{p.stem}.parquet"
            if candidate.exists():
                p = candidate
            else:
                raise FileNotFoundError(f"File not found: {p}")
        reader = get_reader(p)
        df = reader.to_polars()
        self.path = p
        self.path_str = p.name
        self.orig_df = df
        self.current_df = df

    def _get_shape_str(self) -> str:
        if self.current_df is None:
            return "no dataset"
        return f"{self.current_df.shape[0]:,}x{self.current_df.shape[1]}"

    def _build_prompt(self) -> str:
        if len(self.tables) > 1:
            table_names = ", ".join(self.tables.keys())
            return f"{self.prompt} [{table_names}]> "
        elif self.current_df is not None:
            name = self.path_str or "<dataframe>"
            return f"{self.prompt} [{name}: {self._get_shape_str()}]> "
        return f"{self.prompt}> "

    def execute_line(self, raw_line: str, output_fn: Callable[[str], None] = print) -> bool:
        """Execute one REPL input line. Returns False if REPL should terminate."""
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return True

        # Check for exit (strictly 'exit', not 'quit' or 'q')
        if line.lower() == "exit":
            output_fn("Exiting pytae REPL.")
            return False

        # Help (strictly 'help', not '?')
        if line.lower() == "help":
            output_fn(REPL_HELP)
            return True

        # Shell command execution: !<command> (e.g. !ls, !dir)
        if line.startswith("!"):
            shell_cmd = line[1:].strip()
            if not shell_cmd:
                output_fn("Usage: !<command> (e.g. !ls or !dir)")
                return True
            import subprocess

            try:
                res = subprocess.run(shell_cmd, shell=True, text=True, capture_output=True)
                if res.stdout:
                    output_fn(res.stdout.rstrip())
                if res.stderr:
                    output_fn(res.stderr.rstrip())
            except Exception as e:
                output_fn(f"Shell error: {e}")
            return True

        # Status
        if line.lower() == "status":
            self._cmd_status(output_fn)
            return True

        # Reset
        if line.lower() == "reset":
            self._cmd_reset(output_fn)
            return True

        # Undo
        if line.lower() == "undo":
            self._cmd_undo(output_fn)
            return True

        # Redo
        if line.lower() == "redo":
            self._cmd_redo(output_fn)
            return True

        # History
        if line.lower() == "history":
            self._cmd_history(output_fn)
            return True

        # Tokenize line
        tokens = shlex.split(line)
        first_lower = tokens[0].lower()

        # Reject disallowed aliases, legacy synonyms, or hyphenated inspection commands
        if first_lower in _DISALLOWED_ALIASES:
            canonical = _DISALLOWED_ALIASES[first_lower]
            output_fn(f"pytae: '{first_lower}' is not recognized; use '{canonical}'.")
            return True

        # Reject bare pipeline verbs and suggest hyphenated CLI flag
        if first_lower in _BARE_PIPELINE_VERBS:
            output_fn(f"pytae: bare '{first_lower}' is not recognized; use '-{first_lower}' (matching CLI syntax).")
            return True

        # Tables list
        if first_lower == "tables":
            self._cmd_list_tables(output_fn)
            return True

        # Switch active dataset (`use <name>`)
        if first_lower == "use":
            if len(tokens) >= 2:
                self._cmd_use(tokens[1], output_fn)
            else:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(f"Usage: use <table_name> (available: {avail})")
            return True

        # Variable Assignment: `df1 = orders.parquet` or `df3 = df1 -filter "..."` or `df3 = sql SELECT ...`
        if (
            "=" in line
            and not line.startswith("-")
            and not any(
                line.strip().startswith(p)
                for p in (
                    "filter",
                    "-filter",
                    "mutate",
                    "-mutate",
                    "select",
                    "-select",
                    "arrange",
                    "-arrange",
                    "by",
                    "-by",
                    "agg",
                    "-agg",
                    "sql",
                    "join",
                    "-join",
                )
            )
        ):
            left_part, right_part = line.split("=", 1)
            var_name = left_part.strip()
            if var_name.isidentifier():
                self._cmd_assign(var_name, right_part.strip(), output_fn)
                return True

        # Bare table name switches active dataset and shows shape only (Model 2: no table dump)
        if first_lower in self.tables and len(tokens) == 1:
            self.current_df = self.tables[first_lower]
            self.path_str = first_lower
            n_rows, n_cols = self.current_df.shape
            output_fn(f"{first_lower}: {n_rows:,} rows x {n_cols} cols")
            return True

        # Targeted table command (e.g. `df1 -filter ...` or `df2 head 5`)
        if first_lower in self.tables and len(tokens) > 1:
            self._cmd_targeted_pipeline(first_lower, line[len(tokens[0]) :].strip(), output_fn)
            return True

        # Bare checkpoint name hint
        if first_lower in self.checkpoints and len(tokens) == 1:
            output_fn(
                f"pytae: '{first_lower}' is a saved checkpoint. Use 'restore {first_lower}' to activate it, or 'checkpoints' to list all."
            )
            return True

        if first_lower == "checkpoint":
            if len(tokens) < 2:
                output_fn("Usage: checkpoint <name> (e.g. checkpoint baseline)")
                return True
            self._cmd_checkpoint(tokens[1], output_fn)
            return True

        if first_lower == "restore":
            if len(tokens) < 2:
                output_fn("Usage: restore <name> (e.g. restore baseline)")
                return True
            self._cmd_restore(tokens[1], output_fn)
            return True

        if first_lower == "checkpoints":
            self._cmd_list_checkpoints(output_fn)
            return True

        # Load file as table
        if first_lower == "load":
            if len(tokens) < 2:
                output_fn("Usage: load <path> [as <alias>] (e.g. load penguins.parquet as peng)")
                return True
            self._cmd_load(tokens, output_fn)
            return True

        # Join: -join (bare join is caught by _BARE_PIPELINE_VERBS above)
        if first_lower == "-join":
            self._cmd_join(tokens[1:], output_fn)
            return True

        # Save / Export: -o (reject -output / --output)
        if first_lower == "-o":
            if len(tokens) < 2:
                output_fn("Usage: -o <path.parquet|csv|ndjson|clip>")
                return True
            target = tokens[1]
            self._cmd_save(target, output_fn)
            return True
        elif first_lower.startswith("-o="):
            target = first_lower[3:].strip("\"'")
            self._cmd_save(target, output_fn)
            return True
        elif first_lower.startswith(("-output", "--output")):
            output_fn("pytae: '-output' is not recognized; use '-o <path>'.")
            return True

        # SQL Query: -sql "<query>"
        if first_lower in ("-sql", "--sql"):
            if first_lower == "--sql":
                output_fn("pytae: '--sql' uses double hyphens; pytae uses single hyphen '-sql'.")
                return True
            raw_query = line[4:].strip()
            query = raw_query.strip("\"'")
            self._cmd_sql(query, output_fn)
            return True

        # Python Expression
        if first_lower == "py":
            expr = line[2:].strip()
            self._cmd_py(expr, output_fn)
            return True

        # Non-destructive dataset inspection (-shape, -cols, -dtype, etc.)
        if first_lower == "-shape":
            if self.current_df is not None:
                output_fn(f"({self.current_df.shape[0]}, {self.current_df.shape[1]})")
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-cols":
            if self.current_df is not None:
                output_fn("\n".join(self.current_df.columns))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-dtype":
            if self.current_df is not None:
                reader = DataFrameReader(self.current_df)
                output_fn(reader.dtypes().to_string())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-nulls":
            if self.current_df is not None:
                nulls_s = self.current_df.null_count().to_pandas().iloc[0]
                output_fn(nulls_s.to_string())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-glimpse":
            if self.current_df is not None:
                from pytae.dataframe import DataFrame as PytaeDataFrame

                output_fn(PytaeDataFrame(self.current_df).glimpse())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-describe":
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.describe()))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-head":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.head(n), tbl_rows=max(n, 10)))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "-tail":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.tail(n), tbl_rows=max(n, 10)))
            else:
                output_fn("No dataset loaded.")
            return True

        # Otherwise, process as a pytae pipeline command
        self._cmd_pipeline(line, tokens, output_fn)
        return True

    def _cmd_status(self, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("No dataset loaded. Use '<var> = <path.parquet>' to load a table.")
            return
        n_rows, n_cols = self.current_df.shape
        mem_mb = self.current_df.estimated_size() / (1024 * 1024)
        output_fn(f"Active dataset: {self.path_str or '<memory>'}")
        output_fn(f"Shape         : {n_rows:,} rows x {n_cols} columns")
        output_fn(f"Memory        : ~{mem_mb:.2f} MB")
        output_fn(f"Undo steps    : {len(self.undo_stack)} available")
        output_fn(f"Checkpoints   : {len(self.checkpoints)} saved")
        output_fn(f"Columns ({n_cols}): {', '.join(self.current_df.columns[:10])}{'...' if n_cols > 10 else ''}")

    def _cmd_reset(self, output_fn: Callable[[str], None]) -> None:
        if self.path_str and self.path_str in self.orig_tables:
            orig = self.orig_tables[self.path_str]
        elif self.orig_df is not None:
            orig = self.orig_df
        else:
            output_fn("pytae: no original dataset loaded to reset.")
            return
        self.undo_stack.append(("before reset", self.current_df.clone()))
        self.current_df = orig.clone()
        if self.path_str and self.path_str in self.tables:
            self.tables[self.path_str] = self.current_df
        self.redo_stack.clear()
        self.history.append("reset")
        output_fn(
            f"Restored original dataset. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
        )

    def _cmd_undo(self, output_fn: Callable[[str], None]) -> None:
        if not self.undo_stack:
            output_fn("Nothing to undo.")
            return
        desc, prev_df = self.undo_stack.pop()
        self.redo_stack.append((desc, self.current_df.clone()))
        self.current_df = prev_df
        if self.path_str and self.path_str in self.tables:
            self.tables[self.path_str] = prev_df
        self.history.append(f"undo [{desc}]")
        output_fn(f"Undid: {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")

    def _cmd_redo(self, output_fn: Callable[[str], None]) -> None:
        if not self.redo_stack:
            output_fn("Nothing to redo.")
            return
        desc, next_df = self.redo_stack.pop()
        self.undo_stack.append((desc, self.current_df.clone()))
        self.current_df = next_df
        if self.path_str and self.path_str in self.tables:
            self.tables[self.path_str] = next_df
        self.history.append(f"redo [{desc}]")
        output_fn(f"Redid: {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")

    def _cmd_history(self, output_fn: Callable[[str], None]) -> None:
        if not self.history:
            output_fn("No transformations recorded in this session.")
            return
        output_fn("Pipeline History:")
        for idx, entry in enumerate(self.history, start=1):
            output_fn(f"  {idx:2d}: {entry}")

    def _cmd_checkpoint(self, name: str, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded to checkpoint.")
            return
        self.checkpoints[name] = self.current_df.clone()
        output_fn(f"Saved checkpoint '{name}' ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols).")

    def _cmd_restore(self, name: str, output_fn: Callable[[str], None]) -> None:
        if name not in self.checkpoints:
            avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
            output_fn(f"pytae: checkpoint '{name}' not found. Available checkpoints: {avail}")
            return
        self.undo_stack.append((f"before restore {name}", self.current_df.clone()))
        self.current_df = self.checkpoints[name].clone()
        if self.path_str and self.path_str in self.tables:
            self.tables[self.path_str] = self.current_df
        self.redo_stack.clear()
        self.history.append(f"restore {name}")
        output_fn(
            f"Restored checkpoint '{name}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
        )

    def _cmd_list_checkpoints(self, output_fn: Callable[[str], None]) -> None:
        if not self.checkpoints:
            output_fn("No checkpoints saved. Use 'checkpoint <name>' to save one.")
            return
        output_fn("Saved Checkpoints:")
        for name, cp_df in self.checkpoints.items():
            output_fn(f"  - {name:<15}: {cp_df.shape[0]:,} rows x {cp_df.shape[1]} cols")

    def _cmd_list_tables(self, output_fn: Callable[[str], None]) -> None:
        if not self.tables:
            output_fn(
                "No tables loaded in memory. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table."
            )
            return
        output_fn("Tables in memory:")
        for name, tbl_df in self.tables.items():
            source = self.table_sources.get(name, "")
            source_info = f" ({source})" if source else ""
            is_active = self.path_str == name or (self.current_df is not None and self.current_df is tbl_df)
            marker = " *" if is_active else "  "
            status = " [active]" if is_active else ""
            output_fn(f"{marker} {name:<12}: {tbl_df.shape[0]:,} rows x {tbl_df.shape[1]} cols{source_info}{status}")

    def _cmd_use(self, name: str, output_fn: Callable[[str], None]) -> None:
        if name not in self.tables:
            avail = ", ".join(self.tables.keys()) if self.tables else "none"
            output_fn(f"pytae: table '{name}' not found. Available tables: {avail}")
            return
        self.current_df = self.tables[name]
        self.path_str = name
        output_fn(
            f"Switched active dataset to '{name}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
        )

    def _cmd_assign(self, var_name: str, right_expr: str, output_fn: Callable[[str], None]) -> None:
        # 1. SQL query assignment: `df3 = -sql "<query>"`
        if right_expr.startswith(("-sql ", "-sql=")):
            query = right_expr[4:].lstrip(" =").strip().strip("\"'")
            try:
                ctx = pl.SQLContext()
                if self.current_df is not None:
                    ctx.register("df", self.current_df)
                    ctx.register("data", self.current_df)
                for tbl_name, tbl_df in self.tables.items():
                    ctx.register(tbl_name, tbl_df)
                for cp_name, cp_df in self.checkpoints.items():
                    if cp_name not in self.tables:
                        ctx.register(cp_name, cp_df)
                res = ctx.execute(query).collect()
                self.tables[var_name] = res
                self.table_sources[var_name] = f"sql: {query[:30]}"
                self.current_df = res
                self.path_str = var_name
                self.history.append(f'{var_name} = -sql "{query}"')
                output_fn(f"Created '{var_name}' from SQL query ({res.shape[0]:,} rows x {res.shape[1]} cols).")
                return
            except Exception as exc:
                output_fn(f"pytae SQL Error: {exc}")
                return

        if right_expr.lower().startswith("sql "):
            output_fn("pytae: bare 'sql' is not recognized; use '-sql \"<query>\"' (matching CLI syntax).")
            return

        # 2. File path assignment: `df1 = orders.parquet` or explicit sample URI: `df1 = sample:penguins`
        clean_path = right_expr.removeprefix("load ").strip("\"' ")
        p = Path(clean_path).expanduser()
        if clean_path.startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = clean_path[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                output_fn(f"pytae: unknown sample dataset '{sample_name}'. Available: {available}")
                return
            p = sample_file
        elif not p.exists():
            from pytae import DATA_PATH

            candidate = DATA_PATH / p.name
            if not candidate.exists():
                candidate = DATA_PATH / f"{p.stem}.parquet"
            if candidate.exists():
                p = candidate

        if p.exists():
            try:
                reader = get_reader(p)
                df = reader.to_polars()
                self.tables[var_name] = df
                self.orig_tables[var_name] = df.clone()
                self.table_sources[var_name] = p.name
                self.current_df = df
                self.orig_df = df.clone()
                self.path_str = var_name
                self.history.append(f"{var_name} = {clean_path}")
                output_fn(f"Loaded {p.name} as '{var_name}' ({df.shape[0]:,} rows x {df.shape[1]} cols).")
                return
            except Exception as exc:
                output_fn(f"pytae: failed to load {p}: {exc}")
                return

        # 3. Pipeline / Table assignment: `df3 = df1 -filter ...` or `df3 = df1 -join df2 ...` or `df3 = df1`
        right_tokens = shlex.split(right_expr)
        if right_tokens:
            first_tok = right_tokens[0]
            if first_tok in self.tables or first_tok in self.checkpoints:
                source_df = self.tables[first_tok] if first_tok in self.tables else self.checkpoints[first_tok]
                pipe_tokens = right_tokens[1:]
                pipe_line = right_expr[len(first_tok) :].strip()
                if not pipe_tokens:
                    # Simple copy: `df3 = df1`
                    self.tables[var_name] = source_df.clone()
                    self.table_sources[var_name] = f"copy of {first_tok}"
                    self.current_df = self.tables[var_name]
                    self.path_str = var_name
                    output_fn(
                        f"Assigned '{var_name}' from '{first_tok}' ({source_df.shape[0]:,} rows x {source_df.shape[1]} cols)."
                    )
                    return
                # Check for disallowed alias or bare verb in pipeline
                first_pipe = pipe_tokens[0].lower()
                if first_pipe in _DISALLOWED_ALIASES:
                    canonical = _DISALLOWED_ALIASES[first_pipe]
                    output_fn(f"pytae: '{first_pipe}' is not recognized; use '{canonical}'.")
                    return
                if first_pipe in _BARE_PIPELINE_VERBS:
                    output_fn(
                        f"pytae: bare '{first_pipe}' is not recognized; use '-{first_pipe}' (matching CLI syntax)."
                    )
                    return
                # Run pipeline or join on source_df
                self.current_df = source_df.clone()
                if first_pipe == "-join":
                    self._cmd_join(pipe_tokens[1:], output_fn)
                else:
                    self._cmd_pipeline(pipe_line, pipe_tokens, output_fn)
                res_df = self.current_df
                self.tables[var_name] = res_df
                self.table_sources[var_name] = f"{first_tok} {pipe_line[:20]}"
                self.current_df = res_df
                self.path_str = var_name
                self.history.append(f"{var_name} = {right_expr}")
                output_fn(f"Created '{var_name}' ({res_df.shape[0]:,} rows x {res_df.shape[1]} cols).")
                return

        output_fn(f"pytae: could not assign '{var_name}'. '{clean_path}' is not an existing file or table.")

    def _cmd_targeted_pipeline(self, table_name: str, sub_line: str, output_fn: Callable[[str], None]) -> None:
        target_df = self.tables[table_name]
        old_active = self.current_df
        old_path = self.path_str
        self.current_df = target_df
        self.path_str = table_name

        sub_tokens = shlex.split(sub_line)
        first_sub = sub_tokens[0].lower() if sub_tokens else ""

        if first_sub in _DISALLOWED_ALIASES:
            canonical = _DISALLOWED_ALIASES[first_sub]
            output_fn(f"pytae: '{first_sub}' is not recognized; use '{canonical}'.")
            self.current_df = old_active
            self.path_str = old_path
            return

        if first_sub in _BARE_PIPELINE_VERBS:
            output_fn(f"pytae: bare '{first_sub}' is not recognized; use '-{first_sub}' (matching CLI syntax).")
        elif first_sub == "-shape":
            output_fn(f"({target_df.shape[0]}, {target_df.shape[1]})")
        elif first_sub == "-cols":
            output_fn("\n".join(target_df.columns))
        elif first_sub == "-dtype":
            reader = DataFrameReader(target_df)
            output_fn(reader.dtypes().to_string())
        elif first_sub == "-nulls":
            output_fn(target_df.null_count().to_pandas().iloc[0].to_string())
        elif first_sub == "-glimpse":
            from pytae.dataframe import DataFrame as PytaeDataFrame

            output_fn(PytaeDataFrame(target_df).glimpse())
        elif first_sub == "-describe":
            output_fn(_format_table(target_df.describe()))
        elif first_sub == "-head":
            n = int(sub_tokens[1]) if len(sub_tokens) > 1 and sub_tokens[1].isdigit() else 5
            output_fn(_format_table(target_df.head(n), tbl_rows=max(n, 10)))
        elif first_sub == "-tail":
            n = int(sub_tokens[1]) if len(sub_tokens) > 1 and sub_tokens[1].isdigit() else 5
            output_fn(_format_table(target_df.tail(n), tbl_rows=max(n, 10)))
        elif first_sub == "-o":
            dest = sub_tokens[1] if len(sub_tokens) > 1 else "output.parquet"
            self._cmd_save(dest, output_fn)
        elif first_sub.startswith(("-output", "--output")):
            output_fn("pytae: '-output' is not recognized; use '-o <path>'.")
        elif first_sub == "-join":
            self._cmd_join(sub_tokens[1:], output_fn)
            self.tables[table_name] = self.current_df
        elif first_sub == "-sql":
            raw_query = sub_line[4:].strip()
            query = raw_query.strip("\"'")
            self._cmd_sql(query, output_fn)
            self.tables[table_name] = self.current_df
        else:
            self._cmd_pipeline(sub_line, sub_tokens, output_fn)
            self.tables[table_name] = self.current_df

        self.current_df = old_active
        self.path_str = old_path

    def _cmd_load(self, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        path_str = tokens[1].strip("\"' ")
        alias: str | None = None
        if len(tokens) >= 4 and tokens[2].lower() == "as":
            alias = tokens[3]

        p = Path(path_str).expanduser()
        if not path_str.startswith("sample:") and not p.exists():
            from pytae import DATA_PATH

            candidate = DATA_PATH / p.name
            if not candidate.exists():
                candidate = DATA_PATH / f"{p.stem}.parquet"
            if candidate.exists():
                p = candidate
            else:
                output_fn(f"pytae: file not found: {p}")
                return
        try:
            self._load_file(path_str if path_str.startswith("sample:") else p)
            self.undo_stack.clear()
            self.redo_stack.clear()
            target_alias = alias or self.path_str or p.stem or p.name
            self.tables[target_alias] = self.current_df.clone()
            self.orig_tables[target_alias] = self.current_df.clone()
            self.table_sources[target_alias] = p.name
            self.path_str = target_alias
            if alias:
                self.history.append(f"load {p.name} as {alias}")
                output_fn(
                    f"Loaded {p.name} as '{alias}' ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)."
                )
            else:
                self.history.append(f"load {p.name}")
                output_fn(f"Loaded {p.name} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols).")
        except Exception as exc:
            output_fn(f"pytae: failed to load {p}: {exc}")

    def _cmd_join(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded to join into. Load a dataset first with '<var> = <file.parquet>'.")
            return
        if not args:
            output_fn("Usage: -join <target> on=<key> [how=left|inner|outer|semi|anti] [-o <file>]")
            return

        # 1. Extract any output destination: `-o <dest>` (reject -output / --output)
        output_file: str | None = None
        filtered_args: list[str] = []
        i = 0
        while i < len(args):
            tok = args[i]
            if tok in ("--output", "-output") or tok.startswith(("--output=", "-output=")):
                output_fn(f"pytae: '{tok}' is not recognized; use '-o <path>'.")
                return
            if tok == "-o":
                if i + 1 < len(args):
                    output_file = args[i + 1]
                    i += 2
                    continue
            elif tok.startswith("-o="):
                output_file = tok[3:].strip("\"'")
                i += 1
                continue
            filtered_args.append(tok)
            i += 1

        # 2. Flatten any comma-separated argument string (e.g. `left=df1,right=df2,on=id`)
        parts: list[str] = []
        for arg in filtered_args:
            if "," in arg and "=" in arg:
                parts.extend([p.strip() for p in arg.split(",") if p.strip()])
            else:
                parts.append(arg)

        left_name: str | None = None
        right_name: str | None = None
        on_key: str | None = None
        how = "left"

        for part in parts:
            part_clean = part.strip("\"'")
            if part_clean.startswith("left="):
                left_name = part_clean[5:].strip("\"'")
            elif part_clean.startswith("right="):
                right_name = part_clean[6:].strip("\"'")
            elif part_clean.startswith("on="):
                on_key = part_clean[3:].strip("\"'")
            elif part_clean.startswith("how="):
                how = part_clean[4:].strip("\"'").lower()
            elif right_name is None and not part_clean.startswith("-") and "=" not in part_clean:
                right_name = part_clean
            elif on_key is None and not part_clean.startswith("-") and "=" not in part_clean and right_name is not None:
                on_key = part_clean

        if right_name is None:
            output_fn("pytae: -join requires a target table or file (e.g. -join df2 on=customer_id)")
            return

        if on_key is None:
            output_fn("pytae: -join requires 'on=<key>' (e.g. -join df2 on=customer_id or on=cust_id:id)")
            return

        # 3. Resolve left table
        if left_name is not None:
            if left_name in self.tables:
                left_df = self.tables[left_name]
            elif left_name in self.checkpoints:
                left_df = self.checkpoints[left_name]
            else:
                lp = Path(left_name).expanduser()
                if not lp.exists():
                    from pytae import DATA_PATH

                    candidate = DATA_PATH / lp.name
                    if not candidate.exists():
                        candidate = DATA_PATH / f"{lp.stem}.parquet"
                    if candidate.exists():
                        lp = candidate
                if lp.exists():
                    try:
                        left_df = get_reader(lp).to_polars()
                    except Exception as exc:
                        output_fn(f"pytae: failed to read left table '{left_name}': {exc}")
                        return
                else:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: left table '{left_name}' not found. Available: {avail}")
                    return
        else:
            left_df = self.current_df
            left_name = self.path_str or "active"

        # 4. Resolve right table
        if right_name in self.tables:
            right_df = self.tables[right_name]
        elif right_name in self.checkpoints:
            right_df = self.checkpoints[right_name]
        else:
            rp = Path(right_name).expanduser()
            if not rp.exists():
                from pytae import DATA_PATH

                candidate = DATA_PATH / rp.name
                if not candidate.exists():
                    candidate = DATA_PATH / f"{rp.stem}.parquet"
                if candidate.exists():
                    rp = candidate
            if rp.exists():
                try:
                    right_df = get_reader(rp).to_polars()
                except Exception as exc:
                    output_fn(f"pytae: failed to read right table '{right_name}': {exc}")
                    return
            else:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(
                    f"pytae: join target '{right_name}' not found. Must be a loaded table or existing file (available: {avail})"
                )
                return

        # 5. Column matching
        left_col = on_key
        right_col = on_key
        if ":" in on_key:
            left_col, right_col = on_key.split(":", 1)

        if left_col not in left_df.columns:
            output_fn(
                f"pytae: join key '{left_col}' not found in '{left_name}'. Available: {', '.join(left_df.columns)}"
            )
            return
        if right_col not in right_df.columns:
            output_fn(
                f"pytae: join key '{right_col}' not found in '{right_name}'. Available: {', '.join(right_df.columns)}"
            )
            return

        # 6. Execute join
        try:
            how_polars = "full" if how in ("outer", "full") else how
            joined = left_df.join(
                right_df,
                left_on=left_col,
                right_on=right_col,
                how=how_polars,  # type: ignore[arg-type]
            )
            self.undo_stack.append((f"-join {right_name} on={on_key} (how={how})", self.current_df.clone()))
            self.current_df = joined
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = joined
            self.redo_stack.clear()
            self.history.append(f"-join {right_name} on={on_key} how={how}")
            output_fn(
                f"Joined '{left_name}' with '{right_name}' on '{on_key}' (how={how}): {joined.shape[0]:,} rows x {joined.shape[1]} cols"
            )

            # 7. If -o was passed, export immediately
            if output_file is not None:
                self._cmd_save(output_file, output_fn)
        except Exception as exc:
            output_fn(f"pytae join error: {exc}")

    def _cmd_save(self, target: str, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded to save.")
            return
        if target.lower() in ("clip", "clipboard"):
            self.current_df.to_pandas().to_clipboard(index=False)
            output_fn(f"Copied {self.current_df.shape[0]:,} rows to system clipboard.")
            return
        out_path = Path(target)
        try:
            from pytae.readers import write_dataframe

            write_dataframe(self.current_df, out_path)
            output_fn(f"Saved {self.current_df.shape[0]:,} rows to {out_path}.")
        except Exception as exc:
            output_fn(f"pytae: failed to save to {out_path}: {exc}")

    def _cmd_sql(self, query: str, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded for SQL query.")
            return
        if not query:
            output_fn('Usage: -sql "<query>" (e.g. -sql "SELECT species, COUNT(*) FROM df GROUP BY 1")')
            return
        try:
            ctx = pl.SQLContext()
            ctx.register("df", self.current_df)
            ctx.register("data", self.current_df)
            if self.path and self.path.stem:
                ctx.register(self.path.stem, self.current_df)
            for tbl_name, tbl_df in self.tables.items():
                ctx.register(tbl_name, tbl_df)
            for cp_name, cp_df in self.checkpoints.items():
                if cp_name not in self.tables:
                    ctx.register(cp_name, cp_df)
            res = ctx.execute(query).collect()
            output_fn(f"-> {self.path_str or 'df'}: {res.shape[0]:,} rows x {res.shape[1]} cols")
            # Update state with SQL query result
            self.undo_stack.append((f'-sql "{query[:40]}..."', self.current_df.clone()))
            self.current_df = res
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = res
            self.redo_stack.clear()
            self.history.append(f'-sql "{query}"')
        except Exception as exc:
            output_fn(f"pytae SQL Error: {exc}")

    def _cmd_py(self, expr: str, output_fn: Callable[[str], None]) -> None:
        if not expr:
            output_fn("Usage: py <expression> (e.g. py df.columns or py pldf.shape)")
            return
        try:
            from pytae.dataframe import DataFrame as PytaeDataFrame

            local_scope = {
                "df": PytaeDataFrame(self.current_df) if self.current_df is not None else None,
                "pldf": self.current_df,
                "pl": pl,
            }
            for tbl_name, tbl_df in self.tables.items():
                local_scope[tbl_name] = PytaeDataFrame(tbl_df)
            for cp_name, cp_df in self.checkpoints.items():
                if cp_name not in local_scope:
                    local_scope[cp_name] = PytaeDataFrame(cp_df)
            res = eval(expr, {}, local_scope)
            if isinstance(res, (pl.DataFrame, PytaeDataFrame)):
                output_fn(_format_table(res))
            else:
                output_fn(repr(res))
        except Exception as exc:
            output_fn(f"pytae Python Error: {exc}")

    def _cmd_pipeline(self, line: str, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded. Load a dataset first with '<var> = <path.parquet>'.")
            return

        # Build pipeline execution argv directly without bare verb auto-prefixing
        exec_argv = ["<memory>"] + tokens

        from pytae.cli import (
            build_parser,
            parse_concat_arg,
            parse_filter,
            parse_join_arg,
            parse_rename,
            parse_select_spec,
        )

        parser = build_parser(exit_on_error=False)
        try:
            args, extras = parser.parse_known_args(exec_argv)
            if extras:
                first_extra = extras[0].lower().lstrip("-")
                if first_extra in _BARE_PIPELINE_VERBS:
                    output_fn(
                        f"pytae: bare '{extras[0]}' is not recognized; use '-{first_extra}' (matching CLI syntax)."
                    )
                else:
                    output_fn(f"pytae: unrecognized arguments: {' '.join(extras)}")
                return
        except argparse.ArgumentError as exc:
            output_fn(f"pytae: {exc}")
            return
        except SystemExit as exc:
            output_fn(f"pytae: {exc}")
            return

        rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
        select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
        filter_specs = [parse_filter(raw) for raw in (args.filter or [])]
        mutate_specs = list(args.mutate or [])
        sql_specs = list(args.sql or [])
        join_specs = [parse_join_arg(raw) for raw in (args.join or [])]
        concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]

        op_order = getattr(args, "op_order", [])

        # Determine if this command is purely an inspection or preview operation
        has_transformations = any(
            op
            in (
                "filter",
                "mutate",
                "select",
                "rename",
                "arrange",
                "by",
                "agg",
                "distinct",
                "count",
                "fillna",
                "dropna",
                "clean_columns",
                "mask",
                "unmask",
                "long",
                "wide",
                "pivot",
                "sample",
                "sql",
            )
            for op in op_order
        )

        args._memory_df = self.current_df
        args.in_repl = True
        args.output_fn = output_fn

        # Save snapshot for undo if it's a mutating transformation
        snapshot = self.current_df.clone() if has_transformations else None

        try:
            failed = _process_path(
                Path("<memory>"),
                args,
                parser,
                batch=True,
                show_all=not op_order,
                select_specs=select_specs,
                filter_specs=filter_specs,
                mutate_specs=mutate_specs,
                sql_specs=sql_specs,
                rename_specs=rename_specs,
                join_specs=join_specs,
                concat_specs=concat_specs,
            )
            if failed:
                output_fn("pytae: command failed with errors.")
                return

            if has_transformations:
                res_frame = getattr(args, "_result_frame", None)
                if res_frame is not None:
                    assert snapshot is not None
                    self.undo_stack.append((line, snapshot))
                    if isinstance(res_frame, pl.LazyFrame):
                        res_frame = res_frame.collect()
                    elif not isinstance(res_frame, pl.DataFrame):
                        res_frame = pl.from_pandas(res_frame)
                    self.current_df = res_frame
                    if self.path_str and self.path_str in self.tables:
                        self.tables[self.path_str] = res_frame
                    self.redo_stack.clear()
                    self.history.append(line)
                    explicit_inspect = any(
                        op
                        in (
                            "head",
                            "tail",
                            "describe",
                            "glimpse",
                            "freq",
                            "hist",
                            "bar",
                            "scatter",
                            "corr",
                            "plot",
                            "diff",
                            "shape",
                            "cols",
                            "dtype",
                            "nulls",
                        )
                        for op in op_order
                    )
                    if not explicit_inspect:
                        output_fn(
                            f"-> {self.path_str or 'df'}: {res_frame.shape[0]:,} rows x {res_frame.shape[1]} cols"
                        )
        except Exception as exc:
            output_fn(f"pytae error: {exc}")

    def run(
        self,
        input_fn: Callable[[str], str] | None = None,
        output_fn: Callable[[str], None] = print,
    ) -> Any:
        """Run the REPL interactive loop until user exits. Returns final active DataFrame."""
        output_fn(REPL_BANNER)
        if self.current_df is not None:
            output_fn(
                f"Loaded: {self.path_str or '<dataframe>'} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)"
            )
        else:
            output_fn(
                "No initial dataset loaded. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table."
            )
        output_fn("")

        def _get_input(prompt_text: str) -> str:
            if input_fn is not None:
                try:
                    return input_fn(prompt_text)
                except TypeError:
                    return input_fn()  # type: ignore[call-arg]
            return input(prompt_text)

        while True:
            prompt = self._build_prompt()
            try:
                line = _get_input(prompt)
            except KeyboardInterrupt:
                output_fn("\n(KeyboardInterrupt - command cancelled)")
                continue
            except EOFError:
                output_fn("\nExiting pytae REPL.")
                break

            should_continue = self.execute_line(line, output_fn=output_fn)
            if not should_continue:
                break

        return self.current_df


def repl(
    df: Any | None = None,
    path: Path | str | None = None,
    paths: list[Path | str] | None = None,
    prompt: str = "pytae",
) -> Any:
    """Launch the interactive Pytae REPL.

    Parameters
    ----------
    df : DataFrame | polars.DataFrame | pandas.DataFrame, optional
        Pre-load an in-memory DataFrame into the REPL.
    path : str | Path, optional
        Path to a dataset file (.parquet, .csv, .sas7bdat, etc.) to load.
    paths : list[str | Path], optional
        Multiple dataset paths to pre-load into the Multi-Table Workbench.
    prompt : str, default 'pytae'
        Prompt prefix for the REPL prompt.

    Returns
    -------
    DataFrame | None
        The active DataFrame upon exiting the REPL.
    """
    runner = PytaeRepl(df=df, path=path, paths=paths, prompt=prompt)
    return runner.run()
