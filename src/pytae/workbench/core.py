"""Core stateful `Workbench` engine (checkpoints, strict restore, status, free, `%pt`, export)."""

from __future__ import annotations

import argparse
import ast
import atexit
import copy
import datetime
import json
import os
import re
import shlex
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from pytae.cli_run import NON_DF_TERMINAL_OPS, _format_bytes, _process_path
from pytae.workbench.export import (
    _build_notebook_json,
    _build_python_script,
    _infer_missing_imports,
    _is_skippable_cell,
    _prune_dead_and_duplicate_cells,
    _rewrite_cell_for_python,
    _substitute_ns_vars,
)
from pytae.workbench.settings import DisplaySettings
from pytae.workbench.system import (
    _IPYTHON_INTERNAL_RE,
    _dir_size_bytes,
    _is_pytae_df,
    frame_kind,
    frame_memory_bytes,
    frame_shape_str,
    from_polars_frame,
    get_process_rss_mb,
    get_session_meta_dir,
    is_dataframe,
    is_user_var,
    release_memory,
    to_polars_frame,
)

# ---------------------------------------------------------------------------
# Checkpoint metadata
# ---------------------------------------------------------------------------


@dataclass
class CheckpointTableEntry:
    name: str
    path: Path
    kind: str
    shape: str


@dataclass
class CheckpointRecord:
    name: str
    created_at: datetime.datetime
    cell_index: int
    tables: dict[str, CheckpointTableEntry] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    @property
    def disk_bytes(self) -> int:
        return _dir_size_bytes([entry.path for entry in self.tables.values()])


# ---------------------------------------------------------------------------
# Workbench engine
# ---------------------------------------------------------------------------

class Workbench:
    """Pure-Python stateful workbench for Pytae inside IPython / Jupyter."""

    def __init__(self, *, load_config: bool = True) -> None:
        self.settings = DisplaySettings()
        if load_config:
            self.settings.load()
        self.checkpoints: dict[str, CheckpointRecord] = {}
        self.checkpoint_order: list[str] = []
        self.restore_events: list[tuple[int, int]] = []
        self.failed_cells: set[int] = set()
        self._cp_dir: Path | None = None
        try:
            atexit.register(self.cleanup)
        except Exception:
            pass

    def _get_or_create_cp_dir(self) -> Path:
        if self._cp_dir is None or not self._cp_dir.exists():
            self._cp_dir = Path(tempfile.mkdtemp(prefix="pytae_cp_"))
        return self._cp_dir

    def cleanup(self) -> None:
        """Delete ephemeral checkpoint temp directory."""
        if self._cp_dir is not None and self._cp_dir.exists():
            shutil.rmtree(self._cp_dir, ignore_errors=True)
        self._cp_dir = None

    def __del__(self) -> None:
        try:
            self.cleanup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Table discovery
    # ------------------------------------------------------------------

    def discover_tables(self, ns: dict[str, Any]) -> dict[str, Any]:
        """Return user-defined DataFrames currently present in `ns`."""
        tables: dict[str, Any] = {}
        for k, v in ns.items():
            if not isinstance(k, str) or _IPYTHON_INTERNAL_RE.match(k):
                continue
            if is_dataframe(v):
                tables[k] = v
        return tables

    def discover_vars(self, ns: dict[str, Any]) -> dict[str, Any]:
        """Return user-defined scalar/collection variables currently present in `ns`."""
        user_vars: dict[str, Any] = {}
        for k, v in ns.items():
            if not isinstance(k, str) or _IPYTHON_INTERNAL_RE.match(k):
                continue
            if is_user_var(v):
                user_vars[k] = v
        return user_vars

    # ------------------------------------------------------------------
    # Checkpoints & strict restore (D11)
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        name: str,
        ns: dict[str, Any],
        *,
        cell_index: int = 0,
    ) -> str:
        """Save an atomic snapshot of the entire workbench (all DataFrames + user variables)."""
        cp_name = name.strip()
        if not cp_name:
            raise ValueError("Checkpoint name cannot be empty.")

        all_tables = self.discover_tables(ns)
        all_vars = self.discover_vars(ns)

        # Overwrite existing checkpoint cleanly if reusing name
        if cp_name in self.checkpoints:
            self._delete_checkpoint_files(self.checkpoints[cp_name])
            if cp_name in self.checkpoint_order:
                self.checkpoint_order.remove(cp_name)

        cp_dir = self._get_or_create_cp_dir()
        safe_cp = re.sub(r"[^A-Za-z0-9_.-]+", "_", cp_name)
        entries: dict[str, CheckpointTableEntry] = {}

        for tbl_name, obj in all_tables.items():
            kind = frame_kind(obj)
            raw = to_polars_frame(obj)
            eager = raw.collect() if isinstance(raw, pl.LazyFrame) else raw
            safe_tbl = re.sub(r"[^A-Za-z0-9_.-]+", "_", tbl_name)
            dest = cp_dir / f"{safe_cp}__{safe_tbl}.ipc"
            try:
                eager.write_ipc(dest)
            except Exception:
                dest = cp_dir / f"{safe_cp}__{safe_tbl}.parquet"
                eager.write_parquet(dest)
            entries[tbl_name] = CheckpointTableEntry(
                name=tbl_name,
                path=dest,
                kind=kind,
                shape=frame_shape_str(obj),
            )

        snap_vars: dict[str, Any] = {}
        for var_name, val in all_vars.items():
            try:
                snap_vars[var_name] = copy.deepcopy(val)
            except Exception:
                snap_vars[var_name] = val

        rec = CheckpointRecord(
            name=cp_name,
            created_at=datetime.datetime.now(),
            cell_index=cell_index,
            tables=entries,
            variables=snap_vars,
        )
        self.checkpoints[cp_name] = rec
        self.checkpoint_order.append(cp_name)

        tbl_part = (
            f"{len(entries)} table{'s' if len(entries) != 1 else ''}: {', '.join(entries.keys())}"
            if entries
            else "0 tables"
        )
        var_part = f", {len(snap_vars)} var{'s' if len(snap_vars) != 1 else ''}" if snap_vars else ""
        disk_part = f" | {_format_bytes(rec.disk_bytes)} on disk" if entries else ""
        return f"Checkpoint '{cp_name}' saved ({tbl_part}{var_part}{disk_part})."

    def _delete_checkpoint_files(self, rec: CheckpointRecord) -> None:
        for entry in rec.tables.values():
            try:
                if entry.path.exists():
                    entry.path.unlink()
            except OSError:
                pass

    def _read_checkpoint_entry(self, entry: CheckpointTableEntry) -> pl.DataFrame:
        if entry.path.suffix in (".parquet", ".pq"):
            return pl.read_parquet(entry.path)
        return pl.read_ipc(entry.path)

    def restore(
        self,
        name: str | None,
        ns: dict[str, Any],
        *,
        cell_index: int = 0,
        cache_scrub_fn: Callable[[set[int] | None], int] | None = None,
    ) -> str:
        """Strictly restore DataFrame state in `ns` to checkpoint `name` (or latest).

        Drops any DataFrame variables created after the checkpoint, restores all
        snapshotted DataFrames in their original Python types, scrubs IPython's
        output cache references to dropped/replaced DataFrames, and trims OS RSS.
        """
        if not self.checkpoint_order:
            raise KeyError("No checkpoints saved in this session.")

        target_name = name.strip() if name else self.checkpoint_order[-1]
        if target_name not in self.checkpoints:
            avail = ", ".join(self.checkpoint_order)
            raise KeyError(f"Checkpoint '{target_name}' not found. Available: {avail}")

        rec = self.checkpoints[target_name]
        rss_before = get_process_rss_mb()

        current_tables = self.discover_tables(ns)
        stale_ids: set[int] = set()
        dropped_names: list[str] = []

        # Strict restore: collect ids of current DataFrames to scrub, drop extras
        for tbl_name, obj in current_tables.items():
            stale_ids.add(id(obj))
            if _is_pytae_df(obj):
                stale_ids.add(id(obj._df))
            if tbl_name not in rec.tables:
                ns.pop(tbl_name, None)
                dropped_names.append(tbl_name)
        current_tables.clear()
        del current_tables
        obj = None  # release loop variable reference before GC

        # Restore snapshotted DataFrames
        restored_parts: list[str] = []
        for tbl_name, entry in rec.tables.items():
            pl_df = self._read_checkpoint_entry(entry)
            ns[tbl_name] = from_polars_frame(pl_df, entry.kind)
            restored_parts.append(f"{tbl_name} ({entry.shape})")

        # Strict restore of user data variables: drop vars created after checkpoint, restore snapshotted values
        current_vars = self.discover_vars(ns)
        for var_name in list(current_vars.keys()):
            if var_name not in rec.variables:
                ns.pop(var_name, None)
                dropped_names.append(var_name)
        current_vars.clear()
        del current_vars

        for var_name, val in rec.variables.items():
            try:
                ns[var_name] = copy.deepcopy(val)
            except Exception:
                ns[var_name] = val

        if cache_scrub_fn is not None and stale_ids:
            cache_scrub_fn(stale_ids)

        release_memory()
        rss_after = get_process_rss_mb()

        if cell_index > 0:
            self.restore_events.append((rec.cell_index, cell_index))

        msg = f"Restored checkpoint '{target_name}'"
        if restored_parts:
            msg += f" ({', '.join(restored_parts)})"
        else:
            msg += " (0 tables)"
        if dropped_names:
            msg += f" | dropped: {', '.join(sorted(dropped_names))}"
        if rss_before is not None and rss_after is not None:
            msg += f" | RSS: {rss_before:.1f} -> {rss_after:.1f} MB"
        return msg

    def list_checkpoints(self) -> str:
        if not self.checkpoint_order:
            return "No checkpoints saved."
        lines = [f"{'Name':<18} {'Tables':<32} {'Created':<10} {'Disk':>10}"]
        lines.append("-" * 74)
        for cp_name in self.checkpoint_order:
            rec = self.checkpoints[cp_name]
            tbls = ", ".join(rec.tables.keys()) or "(none)"
            if len(tbls) > 30:
                tbls = tbls[:27] + "..."
            ts = rec.created_at.strftime("%H:%M:%S")
            disk = _format_bytes(rec.disk_bytes)
            lines.append(f"{cp_name:<18} {tbls:<32} {ts:<10} {disk:>10}")
        return "\n".join(lines)

    def remove_checkpoint(self, name: str) -> str:
        target = name.strip()
        if target == "*":
            count = len(self.checkpoints)
            for rec in self.checkpoints.values():
                self._delete_checkpoint_files(rec)
            self.checkpoints.clear()
            self.checkpoint_order.clear()
            return f"Removed all {count} checkpoint(s)."
        if target not in self.checkpoints:
            raise KeyError(f"Checkpoint '{target}' not found.")
        rec = self.checkpoints.pop(target)
        self._delete_checkpoint_files(rec)
        if target in self.checkpoint_order:
            self.checkpoint_order.remove(target)
        return f"Removed checkpoint '{target}'."

    def diff_against_checkpoint(
        self,
        table_name: str,
        cp_name: str,
        ns: dict[str, Any],
        *,
        on: str | None = None,
    ) -> str:
        """Compare an in-memory DataFrame against its snapshot in a checkpoint."""
        tables = self.discover_tables(ns)
        if table_name not in tables:
            raise KeyError(f"Table '{table_name}' not found in namespace.")
        if cp_name not in self.checkpoints:
            raise KeyError(f"Checkpoint '{cp_name}' not found.")
        rec = self.checkpoints[cp_name]
        if table_name not in rec.tables:
            raise KeyError(f"Table '{table_name}' was not saved in checkpoint '{cp_name}'.")

        cp_pl = self._read_checkpoint_entry(rec.tables[table_name])
        cur_raw = to_polars_frame(tables[table_name])
        cur_pl = cur_raw.collect() if isinstance(cur_raw, pl.LazyFrame) else cur_raw

        lines = [f"Diff: '{table_name}' (current) vs checkpoint '{cp_name}'"]
        lines.append(f"  Rows:    {cp_pl.height:,} -> {cur_pl.height:,} ({cur_pl.height - cp_pl.height:+,})")
        cp_cols = list(cp_pl.columns)
        cur_cols = list(cur_pl.columns)
        added = [c for c in cur_cols if c not in cp_cols]
        removed = [c for c in cp_cols if c not in cur_cols]
        common = [c for c in cur_cols if c in cp_cols]
        dtype_changes = [
            f"{c} ({cp_pl.schema[c]} -> {cur_pl.schema[c]})"
            for c in common
            if cp_pl.schema[c] != cur_pl.schema[c]
        ]
        if added:
            lines.append(f"  Added:   {', '.join(added)}")
        if removed:
            lines.append(f"  Removed: {', '.join(removed)}")
        if dtype_changes:
            lines.append(f"  Dtypes:  {', '.join(dtype_changes)}")
        if not added and not removed and not dtype_changes:
            if cp_pl.height == cur_pl.height and cp_pl.equals(cur_pl):
                lines.append("  Data:    Identical")
            else:
                lines.append("  Schema:  Identical (values differ)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Free / OS memory reclaim
    # ------------------------------------------------------------------

    def free(
        self,
        names: list[str],
        ns: dict[str, Any],
        *,
        cache_scrub_fn: Callable[[set[int] | None], int] | None = None,
    ) -> str:
        """Delete target DataFrame(s), scrub IPython Out/_ cache, and trim OS RSS."""
        rss_before = get_process_rss_mb()

        if not names:
            scrubbed = cache_scrub_fn(None) if cache_scrub_fn is not None else 0
            release_memory()
            rss_after = get_process_rss_mb()
            rss_part = (
                f" | RSS: {rss_before:.1f} -> {rss_after:.1f} MB"
                if rss_before is not None and rss_after is not None
                else ""
            )
            return f"Reclaimed memory (scrubbed {scrubbed} cached ref(s)){rss_part}."

        targets: list[str] = []
        seen_targets: set[str] = set()

        def _add_targets(keys: list[str]) -> None:
            for k in keys:
                if k not in seen_targets:
                    seen_targets.add(k)
                    targets.append(k)

        for tok in names:
            low = tok.lower()
            if tok == "*":
                _add_targets(list(self.discover_tables(ns).keys()))
                _add_targets(list(self.discover_vars(ns).keys()))
            elif low in ("-df", "--df", "-dfs", "--dfs"):
                _add_targets(list(self.discover_tables(ns).keys()))
            elif low in ("-vars", "--vars", "-var", "--var"):
                _add_targets(list(self.discover_vars(ns).keys()))
            else:
                _add_targets([tok])

        freed_names: list[str] = []
        freed_bytes = 0
        target_ids: set[int] = set()
        missing: list[str] = []

        for t in targets:
            if t not in ns:
                missing.append(t)
                continue
            obj = ns.pop(t)
            target_ids.add(id(obj))
            if _is_pytae_df(obj):
                target_ids.add(id(obj._df))
            if is_dataframe(obj):
                sz = frame_memory_bytes(obj)
                if sz is not None:
                    freed_bytes += sz
            freed_names.append(t)
            del obj

        scrubbed = cache_scrub_fn(target_ids) if (cache_scrub_fn is not None and target_ids) else 0
        release_memory()
        rss_after = get_process_rss_mb()

        parts: list[str] = []
        if freed_names:
            sz_str = f" ({_format_bytes(freed_bytes)})" if freed_bytes > 0 else ""
            parts.append(f"Freed {', '.join(freed_names)}{sz_str}")
        if scrubbed:
            parts.append(f"scrubbed {scrubbed} Out/_ ref(s)")
        if rss_before is not None and rss_after is not None:
            parts.append(f"RSS: {rss_before:.1f} -> {rss_after:.1f} MB")
        if missing:
            parts.append(f"not found: {', '.join(missing)}")
        return " | ".join(parts) if parts else "Nothing to free."

    # ------------------------------------------------------------------
    # Status inspection
    # ------------------------------------------------------------------

    def status(self, ns: dict[str, Any], target: str | None = None, *, verbose: bool = False) -> str:
        """Render workbench status, single table details, or checkpoint details."""
        tables = self.discover_tables(ns)
        t = (target or "").strip()

        if t.lower() in ("checkpoint", "checkpoints"):
            return self.list_checkpoints()
        if t.lower().startswith("checkpoint "):
            cp_name = t.split(None, 1)[1].strip()
            if cp_name not in self.checkpoints:
                raise KeyError(f"Checkpoint '{cp_name}' not found.")
            rec = self.checkpoints[cp_name]
            lines = [
                f"Checkpoint: {rec.name} (created {rec.created_at.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"{_format_bytes(rec.disk_bytes)} on disk)"
            ]
            for tbl_name, entry in rec.tables.items():
                lines.append(f"  - {tbl_name} [{entry.kind}]: {entry.shape}")
            return "\n".join(lines)

        if t and t in tables:
            return self._format_single_table_status(t, tables[t], verbose=verbose)
        if t and t in self.checkpoints:
            rec = self.checkpoints[t]
            lines = [f"Checkpoint: {rec.name} ({_format_bytes(rec.disk_bytes)} on disk)"]
            for tbl_name, entry in rec.tables.items():
                lines.append(f"  - {tbl_name} [{entry.kind}]: {entry.shape}")
            return "\n".join(lines)
        if t:
            raise KeyError(f"No table or checkpoint named '{t}'.")

        # Full workbench summary
        lines = ["Pytae Workbench Status", "-" * 60]
        if tables:
            lines.append(f"Tables ({len(tables)}):")
            lines.append(f"  {'Name':<18} {'Type':<12} {'Shape':<16} {'RAM':>10}")
            total_ram = 0
            for tbl_name, obj in tables.items():
                kind = frame_kind(obj)
                shape = frame_shape_str(obj)
                sz = frame_memory_bytes(obj)
                if sz is not None:
                    total_ram += sz
                ram_str = _format_bytes(sz) if sz is not None else "lazy"
                lines.append(f"  {tbl_name:<18} {kind:<12} {shape:<16} {ram_str:>10}")
            if verbose:
                lines.append(f"  Total DataFrame RAM: {_format_bytes(total_ram)}")
        else:
            lines.append("Tables (0):       (none)")

        if self.checkpoint_order:
            cp_summary = ", ".join(
                f"{n} ({len(self.checkpoints[n].tables)}t, {_format_bytes(self.checkpoints[n].disk_bytes)})"
                for n in self.checkpoint_order
            )
            lines.append(f"Checkpoints ({len(self.checkpoint_order)}):  {cp_summary}")
        else:
            lines.append("Checkpoints (0):  (none)")

        rss = get_process_rss_mb()
        if rss is not None:
            lines.append(f"Process RSS:      {rss:.1f} MB")
        lines.append(f"Settings:         {self.settings.format_inline()}")
        return "\n".join(lines)

    def _format_single_table_status(self, name: str, obj: Any, *, verbose: bool = False) -> str:
        kind = frame_kind(obj)
        shape = frame_shape_str(obj)
        sz = frame_memory_bytes(obj)
        ram_str = _format_bytes(sz) if sz is not None else "lazy"
        lines = [f"Table: {name} [{kind}] ({shape}, {ram_str})"]
        raw = to_polars_frame(obj)
        if isinstance(raw, pl.LazyFrame):
            schema = raw.collect_schema()
            lines.append(f"Columns ({len(schema)}): {', '.join(schema.names())}")
            return "\n".join(lines)
        null_counts = {c: int(raw[c].null_count()) for c in raw.columns}
        non_zero = {c: n for c, n in null_counts.items() if n > 0}
        if non_zero:
            null_str = ", ".join(f"{c} ({n:,})" for c, n in non_zero.items())
            lines.append(f"Nulls: {null_str}")
        else:
            lines.append("Nulls: 0")
        if verbose:
            lines.append("Schema:")
            for c, dt in raw.schema.items():
                lines.append(f"  {c:<24} {str(dt):<16} nulls={null_counts[c]:,}")
        else:
            cols_preview = ", ".join(f"{c}:{raw.schema[c]}" for c in raw.columns[:12])
            if len(raw.columns) > 12:
                cols_preview += f", ... (+{len(raw.columns) - 12} more)"
            lines.append(f"Columns: {cols_preview}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # In-process immutable CLI pipeline (`%pt` / `%%pt`)
    # ------------------------------------------------------------------

    def run_pt(
        self,
        line: str,
        ns: dict[str, Any],
        *,
        cell: str | None = None,
        output_fn: Callable[[str], None] = print,
        cell_index: int = 0,
    ) -> Any:
        """Execute a full Pytae CLI pipeline in-process, immutably.

        Supports:
        - Line magic: `res = %pt df -filter "x > 5" -by g -agg mean`
        - Disk read:  `df = %pt sales.parquet -filter "year == 2025"`
        - Cell magic: `%%pt [target_var]\\n df\\n -filter ...`
        - Multi-table `-join` / `-concat` / `-sql` / `-diff` referencing `ns` DataFrames or disk paths
        - `@var` interpolation from scalar/list/dict variables in `ns`
        """
        from pytae.cli import (
            _normalize_cli_args,
            build_parser,
            parse_concat_arg,
            parse_filter,
            parse_join_arg,
            parse_rename,
            parse_select_spec,
        )
        from pytae.dataframe import DataFrame as PytaeDataFrame

        target_var: str | None = None
        sql_cell_mode = False
        if cell is not None:
            header_tokens = shlex.split(line.strip()) if line.strip() else []
            for htok in header_tokens:
                if htok in ("-sql", "--sql"):
                    sql_cell_mode = True
                elif target_var is None and htok.isidentifier():
                    target_var = htok
                else:
                    raise ValueError(
                        f"%%pt header accepts an optional target variable and/or '-sql', got {htok!r}"
                    )
            if sql_cell_mode:
                raw_sql = cell.strip()
                if not raw_sql:
                    return None
                query = _substitute_ns_vars(raw_sql, ns)
                tables = self.discover_tables(ns)
                if not tables:
                    raise ValueError("No DataFrames found in namespace for %%pt -sql query.")
                ctx = pl.SQLContext()
                for tname, tframe in tables.items():
                    ctx.register(tname, to_polars_frame(tframe))
                sql_res_cell: pl.DataFrame | pl.LazyFrame = ctx.execute(query)
                if isinstance(sql_res_cell, pl.LazyFrame):
                    sql_res_cell = sql_res_cell.collect()
                result_df = PytaeDataFrame(sql_res_cell)
                if target_var is not None:
                    ns[target_var] = result_df
                    return None
                return result_df
            body_lines = [
                ln.strip()
                for ln in cell.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            raw_cmd = " ".join(body_lines)
        else:
            raw_cmd = line.strip()

        if not raw_cmd:
            return None

        tokens = shlex.split(raw_cmd)

        # In-process offline documentation search & cheatsheet: `%pt -doc <query>`, `%pt -cheatsheet`
        if tokens and tokens[0] in ("-doc", "--doc"):
            from pytae.doc_search import format_search_results, search_docs

            doc_query = " ".join(tokens[1:]).strip().strip("\"'")
            if not doc_query:
                output_fn("Usage: %pt -doc <keyword or query>  (e.g. %pt -doc explode)")
                return None
            results = search_docs(doc_query, limit=3)
            output_fn(format_search_results(results, query=doc_query))
            return None

        if tokens and tokens[0] in ("-cheatsheet", "--cheatsheet", "-quick_start", "-quickstart"):
            from pytae.cheatsheet import CHEATSHEET_TEXT

            output_fn(CHEATSHEET_TEXT)
            return None

        tokens = [_substitute_ns_vars(t, ns) for t in tokens]

        tables = self.discover_tables(ns)

        # Rewrite references to in-memory tables in positional args, -join, -concat, -diff
        # and detect whether primary source is an in-memory DataFrame or a disk path.
        source_df: pl.DataFrame | pl.LazyFrame | None = None
        source_name: str = "data"
        memory_tables_pl: dict[str, pl.DataFrame | pl.LazyFrame] = {
            k: to_polars_frame(v) for k, v in tables.items()
        }

        # Check positional tokens (before the first flag) for in-memory DataFrames or `alias=varname`.
        cli_tokens: list[str] = []
        extra_named_memory: dict[str, pl.DataFrame | pl.LazyFrame] = {}
        i = 0
        seen_flag = False
        while i < len(tokens):
            tok = tokens[i]
            if not seen_flag and not tok.startswith("-"):
                if tok in memory_tables_pl:
                    if source_df is None and not extra_named_memory:
                        source_df = memory_tables_pl[tok]
                        source_name = tok
                        cli_tokens.append("<memory>")
                    else:
                        extra_named_memory[tok] = memory_tables_pl[tok]
                        cli_tokens.append(f"{tok}=<memory:{tok}>")
                    i += 1
                    continue
                if "=" in tok:
                    alias, _, rhs = tok.partition("=")
                    if rhs in memory_tables_pl:
                        extra_named_memory[alias] = memory_tables_pl[rhs]
                        cli_tokens.append(f"{alias}=<memory:{alias}>")
                        i += 1
                        continue
                cli_tokens.append(tok)
                i += 1
                continue
            seen_flag = True
            cli_tokens.append(tok)
            i += 1

        # If pipeline starts directly with a flag (e.g. `-sql "SELECT * FROM penguins"`),
        # handle standalone SQL across all `ns` DataFrames directly!
        if source_df is None and cli_tokens and cli_tokens[0] == "-sql" and len(cli_tokens) >= 2:
            if not memory_tables_pl:
                raise ValueError("No DataFrames found in namespace for -sql query.")
            query = cli_tokens[1]
            ctx = pl.SQLContext()
            for tname, tframe in memory_tables_pl.items():
                ctx.register(tname, tframe)
            sql_res: pl.DataFrame | pl.LazyFrame = ctx.execute(query)
            if isinstance(sql_res, pl.LazyFrame):
                sql_res = sql_res.collect()
            result_df = PytaeDataFrame(sql_res)
            if target_var is not None:
                ns[target_var] = result_df
                return None
            return result_df

        exec_argv = _normalize_cli_args(cli_tokens)
        parser = build_parser(exit_on_error=False)
        parser.repl_output_fn = output_fn  # type: ignore[attr-defined]
        try:
            args, extras = parser.parse_known_args(exec_argv)
            if extras:
                raise ValueError(f"Unrecognized arguments: {' '.join(extras)}")
        except (argparse.ArgumentError, SystemExit) as exc:
            raise ValueError(f"pytae syntax error: {exc}") from None

        rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
        select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
        filter_specs = [parse_filter(raw) for raw in (args.filter or [])]
        mutate_specs = list(args.mutate or [])
        sql_specs = list(args.sql or [])
        join_specs = [parse_join_arg(raw) for raw in (args.join or [])]
        concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]
        op_order = getattr(args, "op_order", [])

        # Determine if this invocation has a terminal non-DF op or file/clip output
        has_terminal_non_df = any(op in NON_DF_TERMINAL_OPS for op in op_order) or any(
            [
                args.shape,
                args.cols is not None,
                args.dtype is not None,
                args.nulls is not None,
                args.schema is not None,
                args.describe,
                args.glimpse,
                args.browse,
                args.meta,
                args.diff is not None,
                args.freq is not None,
                args.hist is not None,
                args.bar is not None,
                args.scatter is not None,
                args.corr is not None,
                args.plot is not None,
                args.output is not None,
            ]
        )

        # Resolve in-memory table references inside -diff by spilling to temp parquet if needed
        temp_paths: list[Path] = []
        try:
            if args.diff is not None:
                diff_parts = args.diff.split(",", 1)
                first_part = diff_parts[0].strip()
                if first_part in memory_tables_pl:
                    tmp_p = self._spill_temp_table(memory_tables_pl[first_part], first_part)
                    temp_paths.append(tmp_p)
                    rest = f",{diff_parts[1]}" if len(diff_parts) > 1 else ""
                    args.diff = f"{tmp_p}{rest}"
                elif first_part in self.checkpoints and source_name in self.checkpoints[first_part].tables:
                    cp_entry = self.checkpoints[first_part].tables[source_name]
                    rest = f",{diff_parts[1]}" if len(diff_parts) > 1 else ""
                    args.diff = f"{cp_entry.path}{rest}"

            raw_paths = args.path if isinstance(args.path, list) else ([args.path] if args.path else [])
            frames_map: dict[str, Any] | None = None
            if extra_named_memory or join_specs or concat_specs:
                frames_map = {}
                if source_df is not None:
                    frames_map[source_name] = source_df.collect() if isinstance(source_df, pl.LazyFrame) else source_df
                for alias, frm in extra_named_memory.items():
                    frames_map[alias] = frm.collect() if isinstance(frm, pl.LazyFrame) else frm
                for tname, frm in memory_tables_pl.items():
                    if tname not in frames_map:
                        frames_map[tname] = frm.collect() if isinstance(frm, pl.LazyFrame) else frm

            target_path: Path | None
            if source_df is not None:
                target_path = Path("<memory>")
                args._memory_df = source_df
                args._table_name = source_name
            elif frames_map is not None:
                target_path = None
            elif raw_paths:
                first_p = str(raw_paths[0])
                if first_p.lower() == "clip":
                    from pytae.readers import read as pt_read

                    clip_df = pt_read("clip")
                    target_path = Path("<memory>")
                    args._memory_df = to_polars_frame(clip_df)
                    args._table_name = "clip"
                else:
                    target_path = Path(first_p)
            else:
                raise ValueError("pytae: no input DataFrame or file path provided.")

            args.in_repl = True
            args.repl = True
            # Only print inside _process_path when it's a terminal non-DF op or -o output;
            # otherwise suppress ASCII table printing so IPython displays the returned DataFrame cleanly!
            args.quiet = not has_terminal_non_df
            args.output_fn = output_fn if has_terminal_non_df else (lambda _s: None)

            with pl.Config(**self.settings.to_polars_config()):
                failed = _process_path(
                    target_path,
                    args,
                    parser,
                    batch=True,
                    show_all=False,
                    select_specs=select_specs,
                    filter_specs=filter_specs,
                    mutate_specs=mutate_specs,
                    sql_specs=sql_specs,
                    rename_specs=rename_specs,
                    frames=frames_map,
                    join_specs=join_specs,
                    concat_specs=concat_specs,
                )

            if failed:
                if cell_index > 0:
                    self.failed_cells.add(cell_index)
                return None

            if has_terminal_non_df:
                res_fig: Any = getattr(args, "_result_fig", None)
                if res_fig is not None:
                    if target_var is not None:
                        ns[target_var] = res_fig
                        return None
                    return res_fig
                return None

            res_frame: Any = getattr(args, "_result_frame", None)
            if res_frame is None:
                return None
            if isinstance(res_frame, pl.LazyFrame):
                if source_df is not None and isinstance(source_df, pl.LazyFrame):
                    out_df = PytaeDataFrame(res_frame)
                else:
                    out_df = PytaeDataFrame(res_frame.collect())
            elif isinstance(res_frame, pl.DataFrame):
                out_df = PytaeDataFrame(res_frame)
            else:
                out_df = PytaeDataFrame(pl.from_pandas(res_frame))

            if target_var is not None:
                ns[target_var] = out_df
                return None
            return out_df
        finally:
            for tp in temp_paths:
                try:
                    tp.unlink(missing_ok=True)
                except OSError:
                    pass

    def _spill_temp_table(self, frame: pl.DataFrame | pl.LazyFrame, label: str) -> Path:
        cp_dir = self._get_or_create_cp_dir()
        eager = frame.collect() if isinstance(frame, pl.LazyFrame) else frame
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
        p = cp_dir / f"_tmp_{safe}_{id(frame)}.parquet"
        eager.write_parquet(p)
        return p

    # ------------------------------------------------------------------
    # Export history to .py / .ipynb with rollback pruning (D12)
    # ------------------------------------------------------------------

    def save_session_meta(self, session_id: int) -> None:
        """Persist lightweight failed-cell and rollback metadata for post-hoc `pytae -export`."""
        if session_id <= 0:
            return
        if not self.failed_cells and not self.restore_events:
            return
        try:
            meta_dir = get_session_meta_dir()
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_path = meta_dir / f"session_{session_id}.json"
            payload = {
                "session_id": session_id,
                "failed_cells": sorted(self.failed_cells),
                "restore_events": [[a, b] for a, b in self.restore_events],
            }
            meta_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def load_session_meta(session_id: int) -> tuple[set[int], list[tuple[int, int]]]:
        """Load persisted failed-cell and rollback metadata for an IPython session ID."""
        meta_path = get_session_meta_dir() / f"session_{session_id}.json"
        if not meta_path.exists():
            return set(), []
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            failed = {int(x) for x in data.get("failed_cells", [])}
            restores = [(int(a), int(b)) for a, b in data.get("restore_events", [])]
            return failed, restores
        except Exception:
            return set(), []

    def export_session(
        self,
        dest_path: str | Path,
        history_cells: list[tuple[int, str]],
        *,
        exclude_cell_index: int | None = None,
        relative_paths: bool = False,
    ) -> str:
        """Export IPython session cells to a clean `.py` or `.ipynb` file.

        Automatically prunes:
        - Cells that raised an error during execution (or have invalid Python syntax)
        - Cells rolled back by `%restore` (between checkpoint cell and restore cell)
        - Workbench / inspection magics (`%status`, `%checkpoint`, `%restore`, `%free`, `%export`, `exit -s`, etc.)
        - Read-only previews (bare `df`, `df.head()`, unassigned `%pt df -head`)
        - Consecutive duplicate cells and dead overwritten assignments

        By default resolves local input file paths to full absolute paths (pass `relative_paths=True`
        or `-relative` to emit paths relative to the exported file's directory).
        """
        dest = Path(os.path.expanduser(str(dest_path)))
        if dest.suffix.lower() not in (".py", ".ipynb"):
            dest = dest.with_suffix(".py")
        dest.parent.mkdir(parents=True, exist_ok=True)
        base_dir = dest.parent.resolve() if relative_paths else None
        pruned_pairs, pruned_count = self._clean_session_pairs(
            history_cells,
            exclude_cell_index=exclude_cell_index,
            relative_to=base_dir,
        )

        if dest.suffix.lower() == ".ipynb":
            final_nb_cells = [orig for orig, _py in pruned_pairs]
            final_py_for_imports = [py for _orig, py in pruned_pairs]
            missing_imports = _infer_missing_imports(final_py_for_imports, always_include_pt=False)
            if missing_imports:
                final_nb_cells = ["\n".join(missing_imports)] + final_nb_cells
            nb = _build_notebook_json(final_nb_cells)
            dest.write_text(json.dumps(nb, indent=2) + "\n", encoding="utf-8")
        else:
            final_py_cells = [py for _orig, py in pruned_pairs]
            script = _build_python_script(final_py_cells)
            dest.write_text(script, encoding="utf-8")

        return (
            f"Exported {len(pruned_pairs)} cell(s) "
            f"(pruned {pruned_count} errored/rolled-back/dead/inspection cell(s)) -> {dest}"
        )

    def _clean_session_pairs(
        self,
        history_cells: list[tuple[int, str]],
        *,
        exclude_cell_index: int | None = None,
        relative_to: Path | None = None,
    ) -> tuple[list[tuple[str, str]], int]:
        """Filter, rewrite, syntax-check, and prune dead/duplicate session cells."""
        kept_cells, pruned_count = self._filter_export_cells(
            history_cells, exclude_cell_index=exclude_cell_index
        )

        # Rewrite each kept cell to Python form for AST dead-code/duplicate/syntax analysis
        rewritten = [_rewrite_cell_for_python(c, relative_to=relative_to) for c in kept_cells]
        valid_pairs: list[tuple[str, str]] = []
        for orig, py_code in zip(kept_cells, rewritten):
            if not py_code.strip():
                pruned_count += 1
                continue
            try:
                ast.parse(py_code)
            except SyntaxError:
                pruned_count += 1
                continue
            valid_pairs.append((orig, py_code))

        pruned_pairs, dead_dups = _prune_dead_and_duplicate_cells(valid_pairs)
        return pruned_pairs, pruned_count + dead_dups

    def build_clean_session_cells(
        self,
        history_cells: list[tuple[int, str]],
        *,
        exclude_cell_index: int | None = None,
        relative_to: Path | None = None,
    ) -> tuple[list[str], int]:
        """Return `(clean_python_cells, pruned_count)` with inferred startup imports prepended if needed."""
        pruned_pairs, pruned_count = self._clean_session_pairs(
            history_cells,
            exclude_cell_index=exclude_cell_index,
            relative_to=relative_to,
        )
        final_py_cells = [py for _orig, py in pruned_pairs]
        missing_imports = _infer_missing_imports(final_py_cells, always_include_pt=True)
        if missing_imports:
            final_py_cells = ["\n".join(missing_imports)] + final_py_cells
        return final_py_cells, pruned_count

    def build_clean_session_script(
        self,
        history_cells: list[tuple[int, str]],
        *,
        exclude_cell_index: int | None = None,
        relative_to: Path | None = None,
    ) -> tuple[str, int, int]:
        """Return `(clean_python_script, kept_count, pruned_count)` for a session's cells."""
        pruned_pairs, pruned_count = self._clean_session_pairs(
            history_cells,
            exclude_cell_index=exclude_cell_index,
            relative_to=relative_to,
        )
        final_py_cells = [py for _orig, py in pruned_pairs]
        script = _build_python_script(final_py_cells)
        return script, len(pruned_pairs), pruned_count

    def _filter_export_cells(
        self,
        history_cells: list[tuple[int, str]],
        *,
        exclude_cell_index: int | None = None,
    ) -> tuple[list[str], int]:
        # Build set of rolled-back cell ranges (exclusive of checkpoint cell, inclusive of restore cell)
        pruned_indices: set[int] = set(self.failed_cells)
        if exclude_cell_index is not None:
            pruned_indices.add(exclude_cell_index)
        for cp_idx, restore_idx in self.restore_events:
            for idx in range(cp_idx + 1, restore_idx + 1):
                pruned_indices.add(idx)

        kept: list[str] = []
        pruned = 0
        for cell_idx, raw_code in history_cells:
            code = raw_code.strip()
            if not code:
                continue
            if cell_idx in pruned_indices:
                pruned += 1
                continue
            if _is_skippable_cell(code):
                pruned += 1
                continue
            kept.append(code)
        return kept, pruned


