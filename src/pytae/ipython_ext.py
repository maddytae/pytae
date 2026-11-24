"""IPython / Jupyter integration for Pytae (auto-activated on `import pytae as pt`).

Provides:
- `%pt` / `%%pt`: Full in-process, immutable Pytae CLI pipelines on RAM DataFrames & files
- `%checkpoint`: Ephemeral Arrow IPC snapshots on disk (save, list, rm, diff)
- `%restore`: Strict DataFrame rollback + IPython Out/_ cache scrub + OS RSS trim
- `%status`: Workbench inventory (tables, shapes, RAM, checkpoints, RSS, settings)
- `%set`: Persistent display formatting (max_rows, max_cols, float_precision, comma, save, reset)
- `%free`: Delete DataFrame(s) + scrub IPython Out/_ cache + OS RSS trim
- `%export`: Export clean `.py` or `.ipynb` from IPython history with rollback pruning
- `%exit [-s [path]]`: Standard IPython exit, optionally exporting session first
- Context-aware Tab completion & display formatter hooks
"""

from __future__ import annotations

import shlex
from typing import Any

import polars as pl
from IPython.core.magic import Magics, line_cell_magic, line_magic, magics_class

from pytae.workbench import Workbench, frame_columns, is_dataframe

_PT_CLI_FLAGS = sorted(
    [
        "-agg",
        "-alias",
        "-arrange",
        "-assert",
        "-bar",
        "-browse",
        "-by",
        "-cheatsheet",
        "-clean_columns",
        "-collect",
        "-cols",
        "-concat",
        "-corr",
        "-count",
        "-describe",
        "-diff",
        "-distinct",
        "-dlim",
        "-doc",
        "-dropna",
        "-dtype",
        "-dups",
        "-encoding",
        "-explain",
        "-explode",
        "-fillna",
        "-filter",
        "-fmt",
        "-freq",
        "-glimpse",
        "-head",
        "-hist",
        "-join",
        "-key",
        "-long",
        "-mask",
        "-meta",
        "-mutate",
        "-nrows",
        "-nulls",
        "-o",
        "-opts",
        "-out_dir",
        "-outliers",
        "-pivot",
        "-plot",
        "-rename",
        "-round",
        "-salt",
        "-sample",
        "-scatter",
        "-schema",
        "-seed",
        "-select",
        "-shape",
        "-sql",
        "-tail",
        "-time",
        "-tol",
        "-unmask",
        "-vault",
        "-wide",
    ]
)

_SET_KEYS = ["max_rows=", "max_cols=", "float_precision=", "comma=", "save", "reset"]


def _scrub_ipython_cache(shell: Any, target_ids: set[int] | None) -> int:
    """Remove references to specific object IDs (or all DataFrames if None) from IPython Out/_ cache."""
    if shell is None:
        return 0
    ns = shell.user_ns
    removed = 0

    def _matches(obj: Any) -> bool:
        if obj is None:
            return False
        if target_ids is None:
            return is_dataframe(obj)
        if id(obj) in target_ids:
            return True
        inner = getattr(obj, "_df", None)
        if inner is not None and id(inner) in target_ids:
            return True
        return False

    # Clear _, __, ___, _1, _2, ...
    for k in list(ns.keys()):
        if k in ("_", "__", "___") or (k.startswith("_") and k[1:].isdigit()):
            try:
                if _matches(ns[k]):
                    ns[k] = None
                    removed += 1
            except Exception:
                pass

    # Clear Out / _oh dict
    for dict_name in ("Out", "_oh"):
        out_dict = ns.get(dict_name)
        if isinstance(out_dict, dict):
            for idx in list(out_dict.keys()):
                try:
                    if _matches(out_dict[idx]):
                        del out_dict[idx]
                        removed += 1
                except Exception:
                    pass

    # Clear displayhook reference if present
    dh = getattr(shell, "displayhook", None)
    if dh is not None:
        for attr in ("_", "__", "___"):
            try:
                if _matches(getattr(dh, attr, None)):
                    setattr(dh, attr, None)
                    removed += 1
            except Exception:
                pass

    return removed


def _collect_session_history(shell: Any) -> list[tuple[int, str]]:
    """Return [(cell_index, raw_source), ...] for the current IPython session."""
    if shell is None:
        return []
    hm = getattr(shell, "history_manager", None)
    if hm is not None:
        raw_hist = getattr(hm, "input_hist_raw", None)
        if isinstance(raw_hist, list) and len(raw_hist) > 1:
            return [(idx, str(src)) for idx, src in enumerate(raw_hist) if idx > 0 and src]
    in_list = shell.user_ns.get("In")
    if isinstance(in_list, list):
        return [(idx, str(src)) for idx, src in enumerate(in_list) if idx > 0 and src]
    return []


@magics_class
class PytaeMagics(Magics):
    """IPython line and cell magics for the Pytae Workbench."""

    def __init__(self, shell: Any, workbench: Workbench | None = None) -> None:
        super().__init__(shell)
        self.wb = workbench or Workbench()

    def _user_ns(self) -> dict[str, Any]:
        assert self.shell is not None
        return self.shell.user_ns

    def _current_cell_index(self) -> int:
        hm = getattr(self.shell, "history_manager", None)
        if hm is not None:
            raw_hist = getattr(hm, "input_hist_raw", None)
            if isinstance(raw_hist, list) and len(raw_hist) > 1:
                return len(raw_hist) - 1
        return int(getattr(self.shell, "execution_count", 0) or 0)

    def _scrub_fn(self, target_ids: set[int] | None) -> int:
        return _scrub_ipython_cache(self.shell, target_ids)

    @line_cell_magic
    def pt(self, line: str = "", cell: str | None = None) -> Any:
        """Run a Pytae CLI pipeline in-process (immutable by default).

        Line usage:
            res = %pt df -filter "body_mass_g > 4000" -by island -agg mean
            df  = %pt sales.parquet -select "id,amount"

        Cell usage:
            %%pt summary
            df
            -filter "body_mass_g > 4000"
            -by island
            -agg mean
        """
        idx = self._current_cell_index()
        res = self.wb.run_pt(line, self._user_ns(), cell=cell, output_fn=print, cell_index=idx)
        if idx in self.wb.failed_cells:
            hm = getattr(self.shell, "history_manager", None)
            sess_id = int(getattr(hm, "session_number", 0) or 0)
            if sess_id > 0:
                self.wb.save_session_meta(sess_id)
        return res

    @line_magic
    def checkpoint(self, line: str = "") -> None:
        """Manage atomic workbench checkpoints (all DataFrames + user variables).

        Usage:
            %checkpoint <name>                 Save full workbench snapshot (0 MB RAM)
            %checkpoint list                   List saved checkpoints
            %checkpoint rm <name | *>          Delete a checkpoint (or all)
            %checkpoint diff <table> <cp_name> Compare table against checkpoint
        """
        raw = line.strip()
        if not raw or raw.lower() == "list":
            print(self.wb.list_checkpoints())
            return

        tokens = shlex.split(raw)
        sub = tokens[0].lower()
        if sub in ("rm", "drop", "delete"):
            if len(tokens) < 2:
                print("Usage: %checkpoint rm <name | *>")
                return
            print(self.wb.remove_checkpoint(tokens[1]))
            return
        if sub == "diff":
            if len(tokens) < 3:
                print("Usage: %checkpoint diff <table> <checkpoint_name>")
                return
            print(self.wb.diff_against_checkpoint(tokens[1], tokens[2], self._user_ns()))
            return

        if len(tokens) > 1:
            raise ValueError(
                "%checkpoint captures the entire workbench (all DataFrames and variables); "
                "selective arguments are not supported. Usage: %checkpoint <name>"
            )

        cp_name = tokens[0]
        msg = self.wb.checkpoint(
            cp_name,
            self._user_ns(),
            cell_index=self._current_cell_index(),
        )
        print(msg)

    @line_magic
    def restore(self, line: str = "") -> None:
        """Strictly restore DataFrame state to a saved checkpoint (or latest).

        Usage:
            %restore [checkpoint_name]
        """
        cp_name = line.strip() or None
        msg = self.wb.restore(
            cp_name,
            self._user_ns(),
            cell_index=self._current_cell_index(),
            cache_scrub_fn=self._scrub_fn,
        )
        hm = getattr(self.shell, "history_manager", None)
        sess_id = int(getattr(hm, "session_number", 0) or 0)
        if sess_id > 0:
            self.wb.save_session_meta(sess_id)
        print(msg)

    @line_magic
    def status(self, line: str = "") -> None:
        """Inspect tracked DataFrames, checkpoints, OS process RSS, and settings.

        Usage:
            %status [-v]
            %status <table_name> [-v]
            %status checkpoint [name]
        """
        tokens = shlex.split(line.strip()) if line.strip() else []
        verbose = False
        cleaned: list[str] = []
        for t in tokens:
            if t in ("-v", "--verbose"):
                verbose = True
            else:
                cleaned.append(t)
        target = " ".join(cleaned) if cleaned else None
        print(self.wb.status(self._user_ns(), target=target, verbose=verbose))

    @line_magic
    def set(self, line: str = "") -> None:
        """View or configure persistent Pytae display settings.

        Usage:
            %set
            %set max_rows=20 float_precision=2 comma=true
            %set save
            %set reset
        """
        print(self.wb.settings.apply_spec(line))

    @line_magic
    def free(self, line: str = "") -> None:
        """Delete DataFrame(s) and/or user variable(s), scrub IPython Out/_ cache, and trim OS RSS.

        Always preserves imported modules (`pt`, `pd`, etc.) and functions/classes.

        Usage:
            %free df1 [x ...]     Delete specific DataFrame(s) or variable(s)
            %free -df             Delete all DataFrames (keeps vars, imports, functions)
            %free -vars           Delete all user variables (keeps DataFrames, imports, functions)
            %free *               Delete all DataFrames AND user variables (keeps imports & functions)
            %free                 Scrub stale DataFrame refs in Out/_ and trim OS RAM
        """
        names = shlex.split(line.strip()) if line.strip() else []
        print(self.wb.free(names, self._user_ns(), cache_scrub_fn=self._scrub_fn))

    @line_magic
    def export(self, line: str = "") -> None:
        """Export session history to a clean `.py` or `.ipynb` with rollback pruning.

        Usage:
            %export analysis.py [-relative]
            %export analysis.ipynb [-relative]
        """
        raw = line.strip()
        if not raw:
            print("Usage: %export <path.py | path.ipynb> [-relative]")
            return
        tokens = shlex.split(raw)
        relative_paths = False
        dest: str | None = None
        for t in tokens:
            if t in ("-relative", "--relative"):
                relative_paths = True
            elif dest is None:
                dest = t
        if dest is None:
            print("Usage: %export <path.py | path.ipynb> [-relative]")
            return
        cells = _collect_session_history(self.shell)
        print(
            self.wb.export_session(
                dest,
                cells,
                exclude_cell_index=self._current_cell_index(),
                relative_paths=relative_paths,
            )
        )

    @line_magic
    def exit(self, line: str = "") -> None:
        """Exit IPython, optionally exporting session history first (`%exit -s [path] [-relative]`)."""
        tokens = shlex.split(line.strip()) if line.strip() else []
        if tokens and tokens[0] in ("-s", "--save"):
            relative_paths = False
            dest = "session.py"
            for t in tokens[1:]:
                if t in ("-relative", "--relative"):
                    relative_paths = True
                else:
                    dest = t
            cells = _collect_session_history(self.shell)
            print(
                self.wb.export_session(
                    dest,
                    cells,
                    exclude_cell_index=self._current_cell_index(),
                    relative_paths=relative_paths,
                )
            )

        # In terminal IPython call ask_exit(); in Jupyter kernels avoid killing the kernel unexpectedly
        shell_cls = type(self.shell).__name__
        if "ZMQ" in shell_cls:
            print("Note: In Jupyter, close or shut down the kernel from the UI.")
            return
        ask_exit = getattr(self.shell, "ask_exit", None)
        if callable(ask_exit):
            ask_exit()


# ---------------------------------------------------------------------------
# Display formatters & Tab completion
# ---------------------------------------------------------------------------


def _register_display_formatters(ipython: Any, wb: Workbench) -> None:
    from pytae.dataframe import DataFrame as PytaeDataFrame

    def _plain_formatter(df: PytaeDataFrame, p: Any, cycle: bool) -> None:
        if cycle:
            p.text("DataFrame(...)")
            return
        with pl.Config(**wb.settings.to_polars_config()):
            p.text(repr(df))

    def _html_formatter(df: PytaeDataFrame) -> str:
        with pl.Config(**wb.settings.to_polars_config()):
            return df._repr_html_()

    plain = ipython.display_formatter.formatters.get("text/plain")
    if plain is not None:
        plain.for_type(PytaeDataFrame, _plain_formatter)
    html = ipython.display_formatter.formatters.get("text/html")
    if html is not None:
        html.for_type(PytaeDataFrame, _html_formatter)


def _complete_pytae_magic(wb: Workbench, ipython: Any, event: Any) -> list[str]:
    """Context-aware Tab completion for `%pt`, `%checkpoint`, `%restore`, `%status`, `%free`, `%set`."""
    line: str = getattr(event, "line", "") or ""
    symbol: str = getattr(event, "symbol", "") or ""
    stripped = line.lstrip()
    parts = stripped.split()
    if not parts:
        return []
    magic = parts[0].lstrip("%").lower()
    ns = ipython.user_ns
    tables = wb.discover_tables(ns)
    table_names = sorted(tables.keys())
    cp_names = list(wb.checkpoint_order)

    if magic == "restore":
        return [c for c in cp_names if c.startswith(symbol)]

    if magic == "checkpoint":
        if len(parts) <= 2 and not line.endswith(" "):
            cands = ["list", "rm", "diff"] + cp_names
            return [c for c in cands if c.startswith(symbol)]
        if len(parts) >= 2 and parts[1].lower() in ("rm", "drop", "delete"):
            return [c for c in (cp_names + ["*"]) if c.startswith(symbol)]
        if len(parts) >= 2 and parts[1].lower() == "diff":
            if len(parts) == 2 or (len(parts) == 3 and not line.endswith(" ")):
                return [t for t in table_names if t.startswith(symbol)]
            return [c for c in cp_names if c.startswith(symbol)]
        return []

    if magic == "free":
        return [t for t in (table_names + ["-df", "-vars", "*"]) if t.startswith(symbol)]

    if magic == "status":
        cands = table_names + ["checkpoint", "checkpoints"] + cp_names + ["-v"]
        return [c for c in cands if c.startswith(symbol)]

    if magic == "set":
        return [k for k in _SET_KEYS if k.startswith(symbol)]

    if magic == "pt":
        if symbol.startswith("-"):
            return [f for f in _PT_CLI_FLAGS if f.startswith(symbol)]
        # If a known DataFrame is referenced earlier in the line, offer its column names too
        cols: list[str] = []
        for tok in parts[1:]:
            if tok in tables:
                try:
                    cols = frame_columns(tables[tok])
                except Exception:
                    cols = []
                break
        cands = table_names + cols + _PT_CLI_FLAGS
        return [c for c in dict.fromkeys(cands) if c.startswith(symbol)]

    return []


# ---------------------------------------------------------------------------
# Registration entry points (auto-invoked by `import pytae`)
# ---------------------------------------------------------------------------


def register_ipython_workbench(ipython: Any) -> None:
    """Register Pytae magics, display formatters, and Tab completers on `ipython`."""
    if hasattr(ipython, "_pytae_workbench"):
        return
    wb = Workbench(load_config=True)
    magics = PytaeMagics(ipython, workbench=wb)
    ipython.register_magics(magics)
    ipython._pytae_workbench = wb
    ipython._pytae_magics = magics

    _register_display_formatters(ipython, wb)

    def _on_post_run_cell(result: Any) -> None:
        if getattr(result, "error_before_exec", None) is not None or getattr(result, "error_in_exec", None) is not None:
            idx = magics._current_cell_index()
            if idx > 0:
                wb.failed_cells.add(idx)
                hm = getattr(ipython, "history_manager", None)
                sess_id = int(getattr(hm, "session_number", 0) or 0)
                if sess_id > 0:
                    wb.save_session_meta(sess_id)

    events = getattr(ipython, "events", None)
    if events is not None:
        try:
            events.register("post_run_cell", _on_post_run_cell)
            ipython._pytae_post_run_cb = _on_post_run_cell
        except Exception:
            pass

    def _completer(_self: Any, event: Any) -> list[str]:
        return _complete_pytae_magic(wb, ipython, event)

    for cmd in ("%pt", "%%pt", "%checkpoint", "%restore", "%status", "%free", "%set"):
        try:
            ipython.set_hook("complete_command", _completer, str_key=cmd)
        except Exception:
            pass


def unregister_ipython_workbench(ipython: Any) -> None:
    """Clean up Pytae workbench state from `ipython`."""
    cb = getattr(ipython, "_pytae_post_run_cb", None)
    events = getattr(ipython, "events", None)
    if cb is not None and events is not None:
        try:
            events.unregister("post_run_cell", cb)
        except Exception:
            pass
        delattr(ipython, "_pytae_post_run_cb")
    wb = getattr(ipython, "_pytae_workbench", None)
    if wb is not None:
        wb.cleanup()
        delattr(ipython, "_pytae_workbench")
    if hasattr(ipython, "_pytae_magics"):
        delattr(ipython, "_pytae_magics")
