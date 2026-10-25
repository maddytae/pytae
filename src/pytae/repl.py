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
SESSION & STATE MANAGEMENT:
  undo                 : Revert the last transformation step
  redo                 : Re-apply the last undone transformation step
  reset                : Restore the original dataset as loaded from disk
  history              : Show numbered history of transformation steps
  status               : Display active dataset shape, columns, and memory
  checkpoint <name>    : Save current table state with a name (alias: cp)
  restore <name>       : Restore table to a saved checkpoint (alias: checkout)
  checkpoints          : List all saved checkpoints (alias: cps)
  load <path>          : Load a new file from disk into the REPL (alias: read)
  save <path>          : Export active table to Parquet/CSV or clipboard (alias: -o)
  exit / quit / q      : Exit the REPL session

INSPECTION (Non-destructive previews, active dataset is preserved):
  head [N]             : Preview first N rows (default 5, e.g. head 10)
  tail [N]             : Preview last N rows (default 5, e.g. tail 10)
  shape                : Print (rows, columns)
  cols [asc]           : Print column names (file order or alphabetical)
  dtype                : Print column data types
  nulls                : Print missing value counts per column
  glimpse              : Transposed overview of columns and sample values
  describe             : Statistical summary of numeric columns
  freq <col> [-bar]    : Frequency distribution table with optional ASCII bar

PIPELINE TRANSFORMATIONS (Updates active dataset with automatic undo):
  -filter <condition>  : Filter rows, e.g. -filter "species == 'Gentoo'"
  -mutate <expr>       : Create/modify columns, e.g. -mutate "mass_kg = body_mass_g / 1000"
  -select <cols>       : Column projection, e.g. -select "species,island,mass_kg"
  -arrange <specs>     : Sort rows, e.g. -arrange "mass_kg desc"
  -by <g> -agg <specs> : Grouped aggregation, e.g. -by species -agg "m=body_mass_g:mean, n=count"
  -distinct <cols>     : Deduplicate rows
  -dropna [cols]       : Drop missing values
  -fillna <specs>      : Impute missing values
  -mask / -unmask      : Mask, encrypt, or tokenize sensitive columns

QUERY & PYTHON EXPRESSIONS:
  sql <query>          : Run ANSI SQL on active table (alias: df or data)
                         e.g. sql SELECT species, AVG(body_mass_g) FROM df GROUP BY 1
  py <expr>            : Evaluate Python expression with 'df' (pytae) and 'pldf' (polars)
================================================================================\
"""

_INSPECTION_OPS = frozenset(
    (
        "shape",
        "-shape",
        "--shape",
        "cols",
        "-cols",
        "--cols",
        "dtype",
        "-dtype",
        "--dtype",
        "nulls",
        "-nulls",
        "--nulls",
        "describe",
        "-describe",
        "--describe",
        "glimpse",
        "-glimpse",
        "--glimpse",
        "meta",
        "-meta",
        "--meta",
        "freq",
        "-freq",
        "--freq",
        "hist",
        "-hist",
        "--hist",
        "bar",
        "-bar",
        "--bar",
        "scatter",
        "-scatter",
        "--scatter",
        "corr",
        "-corr",
        "--corr",
        "plot",
        "-plot",
        "--plot",
    )
)

_PREVIEW_OPS = frozenset(("head", "-head", "--head", "tail", "-tail", "--tail"))

_TRANSFORMATION_PREFIXES = (
    "-filter",
    "--filter",
    "-mutate",
    "--mutate",
    "-select",
    "--select",
    "-rename",
    "--rename",
    "-arrange",
    "--arrange",
    "-by",
    "--by",
    "-agg",
    "--agg",
    "-distinct",
    "--distinct",
    "-count",
    "--count",
    "-dropna",
    "--dropna",
    "-fillna",
    "--fillna",
    "-clean_columns",
    "--clean_columns",
    "-mask",
    "--mask",
    "-unmask",
    "--unmask",
    "-long",
    "--long",
    "-wide",
    "--wide",
    "-pivot",
    "--pivot",
    "-sample",
    "--sample",
    "-sql",
    "--sql",
)


class PytaeRepl:
    """Stateful interactive REPL environment for pytae."""

    def __init__(
        self,
        df: Any | None = None,
        path: Path | str | None = None,
        prompt: str = "pytae",
    ) -> None:
        self.prompt = prompt
        self.path: Path | None = Path(path) if path else None
        self.path_str = self.path.name if self.path else ("<memory>" if df is not None else None)

        self.orig_df: pl.DataFrame | None = None
        self.current_df: pl.DataFrame | None = None

        if df is not None:
            self._set_initial_df(df)
        elif self.path is not None:
            self._load_file(self.path)

        self.undo_stack: list[tuple[str, pl.DataFrame]] = []
        self.redo_stack: list[tuple[str, pl.DataFrame]] = []
        self.checkpoints: dict[str, pl.DataFrame] = {}
        self.history: list[str] = []

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
        p = Path(path)
        if not p.exists():
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
        if self.current_df is not None:
            name = self.path_str or "<dataframe>"
            return f"{self.prompt} [{name}: {self._get_shape_str()}]> "
        return f"{self.prompt}> "

    def execute_line(self, raw_line: str, output_fn: Callable[[str], None] = print) -> bool:
        """Execute one REPL input line. Returns False if REPL should terminate."""
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return True

        # Check for exit
        if line.lower() in ("exit", "quit", "q", ":q"):
            output_fn("Exiting pytae REPL.")
            return False

        # Help
        if line.lower() in ("help", "?", "-help", "--help"):
            output_fn(REPL_HELP)
            return True

        # Status
        if line.lower() == "status":
            self._cmd_status(output_fn)
            return True

        # Reset
        if line.lower() in ("reset", "-reset", "--reset"):
            self._cmd_reset(output_fn)
            return True

        # Undo
        if line.lower() in ("undo", "-undo", "--undo"):
            self._cmd_undo(output_fn)
            return True

        # Redo
        if line.lower() in ("redo", "-redo", "--redo"):
            self._cmd_redo(output_fn)
            return True

        # History
        if line.lower() in ("history", "-history", "--history"):
            self._cmd_history(output_fn)
            return True

        # Checkpoint / Restore
        tokens = shlex.split(line)
        first_lower = tokens[0].lower()

        if first_lower in ("checkpoint", "cp", "tag"):
            if len(tokens) < 2:
                output_fn("Usage: checkpoint <name> (e.g. checkpoint baseline)")
                return True
            self._cmd_checkpoint(tokens[1], output_fn)
            return True

        if first_lower in ("restore", "checkout"):
            if len(tokens) < 2:
                output_fn("Usage: restore <name> (e.g. restore baseline)")
                return True
            self._cmd_restore(tokens[1], output_fn)
            return True

        if first_lower in ("checkpoints", "cps", "tags"):
            self._cmd_list_checkpoints(output_fn)
            return True

        # Load / Read
        if first_lower in ("load", "read", "open"):
            if len(tokens) < 2:
                output_fn("Usage: load <path> (e.g. load penguins.parquet)")
                return True
            self._cmd_load(tokens[1], output_fn)
            return True

        # Save / Export / -o
        if first_lower in ("save", "export") or (first_lower in ("-o", "--output") and len(tokens) >= 2):
            target = tokens[1]
            self._cmd_save(target, output_fn)
            return True

        # SQL Query
        if first_lower == "sql":
            query = line[3:].strip()
            self._cmd_sql(query, output_fn)
            return True

        # Python Expression
        if first_lower == "py":
            expr = line[2:].strip()
            self._cmd_py(expr, output_fn)
            return True

        # Convenience shortcuts for non-destructive inspection without hyphens
        if first_lower == "shape":
            if self.current_df is not None:
                output_fn(f"({self.current_df.shape[0]}, {self.current_df.shape[1]})")
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower in ("cols", "columns"):
            if self.current_df is not None:
                output_fn("\n".join(self.current_df.columns))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower in ("dtype", "dtypes"):
            if self.current_df is not None:
                reader = DataFrameReader(self.current_df)
                output_fn(reader.dtypes().to_string())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "nulls":
            if self.current_df is not None:
                nulls_s = self.current_df.null_count().to_pandas().iloc[0]
                output_fn(nulls_s.to_string())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "glimpse":
            if self.current_df is not None:
                from pytae.dataframe import DataFrame as PytaeDataFrame

                output_fn(PytaeDataFrame(self.current_df).glimpse())
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "describe":
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.describe()))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "head":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.head(n)))
            else:
                output_fn("No dataset loaded.")
            return True

        if first_lower == "tail":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            if self.current_df is not None:
                output_fn(_format_table(self.current_df.tail(n)))
            else:
                output_fn("No dataset loaded.")
            return True

        # Otherwise, process as a pytae pipeline command
        self._cmd_pipeline(line, tokens, output_fn)
        return True

    def _cmd_status(self, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("No dataset loaded. Use 'load <path>' to load a table.")
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
        if self.orig_df is None:
            output_fn("pytae: no original dataset loaded to reset.")
            return
        self.undo_stack.append(("before reset", self.current_df.clone()))
        self.current_df = self.orig_df.clone()
        self.redo_stack.clear()
        self.history.append("reset")
        output_fn(f"Restored original dataset. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")

    def _cmd_undo(self, output_fn: Callable[[str], None]) -> None:
        if not self.undo_stack:
            output_fn("Nothing to undo.")
            return
        desc, prev_df = self.undo_stack.pop()
        self.redo_stack.append((desc, self.current_df.clone()))
        self.current_df = prev_df
        self.history.append(f"undo [{desc}]")
        output_fn(f"Undid: {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")

    def _cmd_redo(self, output_fn: Callable[[str], None]) -> None:
        if not self.redo_stack:
            output_fn("Nothing to redo.")
            return
        desc, next_df = self.redo_stack.pop()
        self.undo_stack.append((desc, self.current_df.clone()))
        self.current_df = next_df
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
        self.redo_stack.clear()
        self.history.append(f"restore {name}")
        output_fn(f"Restored checkpoint '{name}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")

    def _cmd_list_checkpoints(self, output_fn: Callable[[str], None]) -> None:
        if not self.checkpoints:
            output_fn("No checkpoints saved. Use 'checkpoint <name>' to save one.")
            return
        output_fn("Saved Checkpoints:")
        for name, cp_df in self.checkpoints.items():
            output_fn(f"  - {name:<15}: {cp_df.shape[0]:,} rows x {cp_df.shape[1]} cols")

    def _cmd_load(self, path_str: str, output_fn: Callable[[str], None]) -> None:
        p = Path(path_str)
        if not p.exists():
            output_fn(f"pytae: file not found: {p}")
            return
        try:
            self._load_file(p)
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.checkpoints.clear()
            self.history.clear()
            self.history.append(f"load {p.name}")
            output_fn(f"Loaded {p.name} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols).")
        except Exception as exc:
            output_fn(f"pytae: failed to load {p}: {exc}")

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
            output_fn("Usage: sql <query> (e.g. sql SELECT species, COUNT(*) FROM df GROUP BY 1)")
            return
        try:
            ctx = pl.SQLContext()
            ctx.register("df", self.current_df)
            ctx.register("data", self.current_df)
            if self.path and self.path.stem:
                ctx.register(self.path.stem, self.current_df)
            res = ctx.execute(query).collect()
            output_fn(_format_table(res))
            # Update state with SQL query result
            self.undo_stack.append((f"sql {query[:40]}...", self.current_df.clone()))
            self.current_df = res
            self.redo_stack.clear()
            self.history.append(f"sql {query}")
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
            res = eval(expr, {}, local_scope)
            if isinstance(res, (pl.DataFrame, PytaeDataFrame)):
                output_fn(_format_table(res))
            else:
                output_fn(repr(res))
        except Exception as exc:
            output_fn(f"pytae Python Error: {exc}")

    def _cmd_pipeline(self, line: str, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded. Use 'load <path>' to load a file first.")
            return

        # Auto-prefix bare verbs with hyphens if user omitted them (e.g. `filter "..."` -> `-filter "..."`)
        normalized_tokens: list[str] = []
        for i, tok in enumerate(tokens):
            bare_verb = f"-{tok}"
            if i == 0 and not tok.startswith("-") and bare_verb in _TRANSFORMATION_PREFIXES:
                normalized_tokens.append(bare_verb)
            elif not tok.startswith("-") and bare_verb in (
                "-filter",
                "-mutate",
                "-select",
                "-arrange",
                "-by",
                "-agg",
                "-head",
                "-tail",
            ):
                # If preceding token was not a flag expecting a value, treat as flag
                prev = normalized_tokens[-1] if normalized_tokens else ""
                if prev.startswith("-") and prev not in (
                    "-distinct",
                    "-dropna",
                    "-count",
                    "-shape",
                    "-cols",
                    "-dtype",
                    "-nulls",
                    "-glimpse",
                ):
                    normalized_tokens.append(tok)
                else:
                    normalized_tokens.append(bare_verb)
            else:
                normalized_tokens.append(tok)

        # Build pipeline execution argv
        exec_argv = ["<memory>"] + normalized_tokens

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
                    self.redo_stack.clear()
                    self.history.append(line)
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
            output_fn(f"Loaded: {self.path_str or '<dataframe>'} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)")
        else:
            output_fn("No initial dataset loaded. Use 'load <path>' to load a table.")
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
    prompt: str = "pytae",
) -> Any:
    """Launch the interactive Pytae REPL.

    Parameters
    ----------
    df : DataFrame | polars.DataFrame | pandas.DataFrame, optional
        Pre-load an in-memory DataFrame into the REPL.
    path : str | Path, optional
        Path to a dataset file (.parquet, .csv, .sas7bdat, etc.) to load.
    prompt : str, default 'pytae'
        Prompt prefix for the REPL prompt.

    Returns
    -------
    DataFrame | None
        The active DataFrame upon exiting the REPL.
    """
    runner = PytaeRepl(df=df, path=path, prompt=prompt)
    return runner.run()
