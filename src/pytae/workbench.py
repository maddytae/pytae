"""Pure-Python stateful workbench engine for Pytae (used by the IPython extension).

Manages:
- Ephemeral Arrow IPC checkpoints on disk (0 MB RAM) with strict rollback
- OS-level memory trimming (`release_memory`, `get_process_rss_mb`)
- Persistent display settings (~/.pytae/config.json)
- In-process, immutable CLI pipeline execution (`run_pt`)
- Session history export to clean `.py` or `.ipynb` with rollback pruning
"""

from __future__ import annotations

import argparse
import ast
import atexit
import datetime
import gc
import json
import os
import re
import shlex
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from pytae.cli_run import NON_DF_TERMINAL_OPS, _format_bytes, _process_path

# ---------------------------------------------------------------------------
# Paths & OS memory utilities
# ---------------------------------------------------------------------------


def get_pytae_home() -> Path:
    """Return the base Pytae configuration directory (default: ~/.pytae)."""
    env_home = os.environ.get("PYTAE_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return Path.home() / ".pytae"


def get_config_path() -> Path:
    """Return path to persistent display configuration (~/.pytae/config.json)."""
    return get_pytae_home() / "config.json"


def get_session_meta_dir() -> Path:
    """Return directory for lightweight IPython session metadata (~/.pytae/sessions)."""
    return get_pytae_home() / "sessions"


def get_ipython_history_db() -> Path:
    """Return path to IPython's default SQLite history database."""
    ipython_dir = Path(os.environ.get("IPYTHONDIR", str(Path.home() / ".ipython"))).expanduser()
    return ipython_dir / "profile_default" / "history.sqlite"


def release_memory() -> None:
    """Force Python GC and return freed memory pages back to the OS."""
    gc.collect()
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            h_process = kernel32.GetCurrentProcess()

            c_size_t = ctypes.c_size_t
            kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, c_size_t, c_size_t]
            kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
            flg = c_size_t(-1).value
            kernel32.SetProcessWorkingSetSize(h_process, flg, flg)

            try:
                empty_ws = kernel32.K32EmptyWorkingSet
            except AttributeError:
                psapi = ctypes.WinDLL("psapi", use_last_error=True)
                empty_ws = psapi.EmptyWorkingSet
            empty_ws.argtypes = [wintypes.HANDLE]
            empty_ws.restype = wintypes.BOOL
            empty_ws(h_process)
        except Exception:
            pass
    elif sys.platform == "linux":
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import ctypes

            libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            libc.malloc_zone_pressure_relief.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            libc.malloc_zone_pressure_relief.restype = ctypes.c_size_t
            libc.malloc_zone_pressure_relief(None, 0)
        except Exception:
            pass


def get_process_rss_mb() -> float | None:
    """Return current process RSS / Working Set size in megabytes."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            h_process = kernel32.GetCurrentProcess()
            try:
                get_mem_info = kernel32.K32GetProcessMemoryInfo
            except AttributeError:
                psapi = ctypes.WinDLL("psapi", use_last_error=True)
                get_mem_info = psapi.GetProcessMemoryInfo

            get_mem_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            get_mem_info.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if get_mem_info(h_process, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            pass
    elif sys.platform == "linux":
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import ctypes

            libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")

            class _MachTaskBasicInfo(ctypes.Structure):
                _fields_ = [
                    ("virtual_size", ctypes.c_uint64),
                    ("resident_size", ctypes.c_uint64),
                    ("resident_size_max", ctypes.c_uint64),
                    ("user_time", ctypes.c_uint64),
                    ("system_time", ctypes.c_uint64),
                    ("policy", ctypes.c_int32),
                    ("suspend_count", ctypes.c_int32),
                ]

            info = _MachTaskBasicInfo()
            count = ctypes.c_uint32(ctypes.sizeof(_MachTaskBasicInfo) // ctypes.sizeof(ctypes.c_uint32))
            kr = libc.task_info(libc.mach_task_self(), 20, ctypes.byref(info), ctypes.byref(count))
            if kr == 0 and info.resident_size > 0:
                return info.resident_size / (1024 * 1024)
        except Exception:
            pass
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / (1024 * 1024)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# DataFrame inspection & conversion helpers
# ---------------------------------------------------------------------------

_IPYTHON_INTERNAL_RE = re.compile(r"^(_.*|In|Out|get_ipython|exit|quit|open)$")


def _is_pandas_df(obj: Any) -> bool:
    cls = type(obj)
    return cls.__name__ == "DataFrame" and cls.__module__.startswith("pandas")


def _is_pytae_df(obj: Any) -> bool:
    from pytae.dataframe import DataFrame as PytaeDataFrame

    return isinstance(obj, PytaeDataFrame)


def is_dataframe(obj: Any) -> bool:
    """Return True if obj is a pytae.DataFrame, polars DataFrame/LazyFrame, or pandas DataFrame."""
    return isinstance(obj, (pl.DataFrame, pl.LazyFrame)) or _is_pytae_df(obj) or _is_pandas_df(obj)


def frame_kind(obj: Any) -> str:
    """Return canonical kind tag for restoring exact Python type."""
    if _is_pytae_df(obj):
        return "pytae_lazy" if getattr(obj, "is_lazy", False) else "pytae"
    if isinstance(obj, pl.LazyFrame):
        return "polars_lazy"
    if isinstance(obj, pl.DataFrame):
        return "polars"
    if _is_pandas_df(obj):
        return "pandas"
    return "polars"


def to_polars_frame(obj: Any) -> pl.DataFrame | pl.LazyFrame:
    """Extract or convert a supported DataFrame to a Polars DataFrame or LazyFrame."""
    if _is_pytae_df(obj):
        return obj._df
    if isinstance(obj, (pl.DataFrame, pl.LazyFrame)):
        return obj
    if _is_pandas_df(obj):
        return pl.from_pandas(obj)
    raise TypeError(f"Unsupported DataFrame type: {type(obj).__name__}")


def from_polars_frame(frame: pl.DataFrame | pl.LazyFrame, kind: str) -> Any:
    """Convert a Polars frame back into the requested Python DataFrame type."""
    from pytae.dataframe import DataFrame as PytaeDataFrame

    if kind == "pytae":
        return PytaeDataFrame(frame)
    if kind == "pytae_lazy":
        lf = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
        return PytaeDataFrame(lf)
    if kind == "polars_lazy":
        return frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    if kind == "pandas":
        edf = frame.collect() if isinstance(frame, pl.LazyFrame) else frame
        return edf.to_pandas()
    return frame


def frame_columns(obj: Any) -> list[str]:
    """Return column names cleanly across pytae, Polars eager/lazy, and pandas."""
    raw = obj._df if _is_pytae_df(obj) else obj
    if isinstance(raw, pl.LazyFrame):
        return list(raw.collect_schema().names())
    if isinstance(raw, pl.DataFrame):
        return list(raw.columns)
    return [str(c) for c in raw.columns]


def frame_shape_str(obj: Any) -> str:
    """Return compact human-readable shape string."""
    raw = obj._df if _is_pytae_df(obj) else obj
    if isinstance(raw, pl.LazyFrame):
        ncols = len(raw.collect_schema().names())
        return f"lazy × {ncols:,}"
    rows, cols = raw.shape
    return f"{rows:,} × {cols:,}"


def frame_memory_bytes(obj: Any) -> int | None:
    """Return estimated in-memory size in bytes, or None for LazyFrames."""
    raw = obj._df if _is_pytae_df(obj) else obj
    if isinstance(raw, pl.LazyFrame):
        return None
    if isinstance(raw, pl.DataFrame):
        return int(raw.estimated_size())
    if _is_pandas_df(raw):
        return int(raw.memory_usage(deep=True).sum())
    return None


def _dir_size_bytes(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            if p.exists():
                total += p.stat().st_size
        except OSError:
            pass
    return total


# ---------------------------------------------------------------------------
# Persistent display settings
# ---------------------------------------------------------------------------


@dataclass
class DisplaySettings:
    """Display formatting settings persisted in ~/.pytae/config.json."""

    max_rows: int = 10
    max_cols: int | None = None
    float_precision: int | None = None
    comma: bool = False

    def to_polars_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "tbl_rows": self.max_rows,
            "tbl_cols": self.max_cols if self.max_cols is not None else -1,
        }
        if self.float_precision is not None:
            cfg["float_precision"] = self.float_precision
        if self.comma:
            cfg["thousands_separator"] = True
        return cfg

    def load(self) -> None:
        cfg_path = get_config_path()
        if not cfg_path.exists():
            return
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        if isinstance(data.get("max_rows"), int) and data["max_rows"] > 0:
            self.max_rows = data["max_rows"]
        mc = data.get("max_cols")
        if mc is None or (isinstance(mc, int) and mc > 0):
            self.max_cols = mc
        fp = data.get("float_precision")
        if fp is None or (isinstance(fp, int) and fp >= 0):
            self.float_precision = fp
        if isinstance(data.get("comma"), bool):
            self.comma = data["comma"]

    def save(self) -> Path:
        cfg_path = get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if cfg_path.exists():
            try:
                loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                pass
        existing.update(
            {
                "max_rows": self.max_rows,
                "max_cols": self.max_cols,
                "float_precision": self.float_precision,
                "comma": self.comma,
            }
        )
        cfg_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        return cfg_path

    def reset(self) -> None:
        self.max_rows = 10
        self.max_cols = None
        self.float_precision = None
        self.comma = False

    def format_summary(self) -> str:
        return (
            f"max_rows        = {self.max_rows}\n"
            f"max_cols        = {self.max_cols}\n"
            f"float_precision = {self.float_precision}\n"
            f"comma           = {self.comma}"
        )

    def format_inline(self) -> str:
        return (
            f"max_rows={self.max_rows}, max_cols={self.max_cols}, "
            f"float_precision={self.float_precision}, comma={self.comma}"
        )

    def apply_spec(self, spec: str) -> str:
        """Parse and apply `%set` arguments (`key=val`, `save`, `reset`, or bare show)."""
        raw = spec.strip()
        if not raw:
            return self.format_summary()
        low = raw.lower()
        if low == "save":
            p = self.save()
            return f"Saved display settings to {p}"
        if low == "reset":
            self.reset()
            return f"Display settings reset to defaults ({self.format_inline()})"

        pairs = _parse_set_pairs(raw)
        if not pairs:
            return self.format_summary()

        updated: list[str] = []
        for k, v in pairs:
            key = k.strip().lower()
            val = v.strip()
            vlow = val.lower()
            if key in ("max_rows", "rows"):
                try:
                    n = int(val)
                    if n <= 0:
                        raise ValueError
                except ValueError:
                    raise ValueError(f"max_rows must be a positive integer, got {val!r}")
                self.max_rows = n
                updated.append(f"max_rows={n}")
            elif key in ("max_cols", "cols"):
                if vlow in ("none", "all", "null", "-1"):
                    self.max_cols = None
                    updated.append("max_cols=None")
                else:
                    try:
                        n = int(val)
                        if n <= 0:
                            raise ValueError
                    except ValueError:
                        raise ValueError(f"max_cols must be a positive integer or 'none', got {val!r}")
                    self.max_cols = n
                    updated.append(f"max_cols={n}")
            elif key in ("float_precision", "precision", "round"):
                if vlow in ("none", "auto", "null"):
                    self.float_precision = None
                    updated.append("float_precision=None")
                else:
                    try:
                        n = int(val)
                        if n < 0:
                            raise ValueError
                    except ValueError:
                        raise ValueError(f"float_precision must be a non-negative integer or 'none', got {val!r}")
                    self.float_precision = n
                    updated.append(f"float_precision={n}")
            elif key == "comma":
                if vlow in ("true", "1", "on", "yes"):
                    self.comma = True
                    updated.append("comma=True")
                elif vlow in ("false", "0", "off", "no"):
                    self.comma = False
                    updated.append("comma=False")
                else:
                    raise ValueError(f"comma must be true/false, got {val!r}")
            else:
                raise ValueError(
                    f"Unknown setting {key!r}. Valid settings: max_rows, max_cols, float_precision, comma"
                )
        return "Updated: " + ", ".join(updated)


def _parse_set_pairs(raw: str) -> list[tuple[str, str]]:
    """Parse `k=v k2=v2`, `k=v, k2=v2`, or `k v` into (key, value) pairs."""
    tokens = shlex.split(raw.replace(",", " "))
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "=" in tok:
            k, _, v = tok.partition("=")
            pairs.append((k, v))
            i += 1
        elif i + 1 < len(tokens) and tokens[i + 1] == "=" and i + 2 < len(tokens):
            pairs.append((tok, tokens[i + 2]))
            i += 3
        elif i + 1 < len(tokens) and "=" not in tokens[i + 1]:
            pairs.append((tok, tokens[i + 1]))
            i += 2
        else:
            raise ValueError(f"Invalid setting specification near {tok!r}; expected key=value")
    return pairs


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

    @property
    def disk_bytes(self) -> int:
        return _dir_size_bytes([entry.path for entry in self.tables.values()])


# ---------------------------------------------------------------------------
# Workbench engine
# ---------------------------------------------------------------------------

_INSPECTION_MAGICS = frozenset(
    {
        "status",
        "checkpoint",
        "checkpoints",
        "restore",
        "free",
        "export",
        "set",
        "exit",
        "quit",
        "whos",
        "who",
        "load_ext",
        "reload_ext",
        "unload_ext",
        "clear",
        "cls",
        "history",
        "hist",
        "lsmagic",
        "colors",
        "theme",
        "magic",
        "pinfo",
        "pdoc",
        "pwd",
        "ls",
    }
)


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

    # ------------------------------------------------------------------
    # Checkpoints & strict restore (D11)
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        name: str,
        ns: dict[str, Any],
        *,
        table_names: list[str] | None = None,
        cell_index: int = 0,
    ) -> str:
        """Save an ephemeral Arrow IPC snapshot of DataFrames in `ns`."""
        cp_name = name.strip()
        if not cp_name:
            raise ValueError("Checkpoint name cannot be empty.")

        all_tables = self.discover_tables(ns)
        if table_names:
            missing = [t for t in table_names if t not in all_tables]
            if missing:
                raise KeyError(f"Table(s) not found in namespace: {', '.join(missing)}")
            selected = {t: all_tables[t] for t in table_names}
        else:
            selected = all_tables

        # Overwrite existing checkpoint cleanly if reusing name
        if cp_name in self.checkpoints:
            self._delete_checkpoint_files(self.checkpoints[cp_name])
            if cp_name in self.checkpoint_order:
                self.checkpoint_order.remove(cp_name)

        cp_dir = self._get_or_create_cp_dir()
        safe_cp = re.sub(r"[^A-Za-z0-9_.-]+", "_", cp_name)
        entries: dict[str, CheckpointTableEntry] = {}

        for tbl_name, obj in selected.items():
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

        rec = CheckpointRecord(
            name=cp_name,
            created_at=datetime.datetime.now(),
            cell_index=cell_index,
            tables=entries,
        )
        self.checkpoints[cp_name] = rec
        self.checkpoint_order.append(cp_name)

        if not entries:
            return f"Checkpoint '{cp_name}' saved (0 tables)."
        names_str = ", ".join(entries.keys())
        disk_str = _format_bytes(rec.disk_bytes)
        return f"Checkpoint '{cp_name}' saved ({len(entries)} table{'s' if len(entries) != 1 else ''}: {names_str} | {disk_str} on disk)."

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

        if names == ["*"]:
            targets = list(self.discover_tables(ns).keys())
        else:
            targets = names

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
        if cell is not None:
            header = line.strip()
            if header:
                if not header.isidentifier():
                    raise ValueError(f"%%pt target variable must be a valid Python identifier, got {header!r}")
                target_var = header
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
        tokens = [_substitute_ns_vars(t, ns) for t in tokens]

        tables = self.discover_tables(ns)

        # Rewrite references to in-memory tables in positional args, -join, -concat, -diff
        # and detect whether primary source is an in-memory DataFrame or a disk path.
        source_df: pl.DataFrame | pl.LazyFrame | None = None
        source_name: str = "data"
        memory_tables_pl: dict[str, pl.DataFrame | pl.LazyFrame] = {
            k: to_polars_frame(v) for k, v in tables.items()
        }

        # Check if first positional token (before any flag) is a known DataFrame in `ns`
        # or `alias=varname` where `varname` is in `ns`.
        cli_tokens: list[str] = []
        extra_named_memory: dict[str, pl.DataFrame | pl.LazyFrame] = {}
        i = 0
        first_source_handled = False
        while i < len(tokens):
            tok = tokens[i]
            if not first_source_handled and not tok.startswith("-"):
                if tok in memory_tables_pl:
                    source_df = memory_tables_pl[tok]
                    source_name = tok
                    cli_tokens.append("<memory>")
                    first_source_handled = True
                    i += 1
                    continue
                if "=" in tok:
                    alias, _, rhs = tok.partition("=")
                    if rhs in memory_tables_pl:
                        extra_named_memory[alias] = memory_tables_pl[rhs]
                        cli_tokens.append(f"{alias}=<memory:{alias}>")
                        i += 1
                        continue
                first_source_handled = True
                cli_tokens.append(tok)
                i += 1
                continue
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
            if source_df is not None:
                target_path = Path("<memory>")
                args._memory_df = source_df
                args._table_name = source_name
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
                    join_specs=join_specs,
                    concat_specs=concat_specs,
                )

            if failed:
                if cell_index > 0:
                    self.failed_cells.add(cell_index)
                return None

            if has_terminal_non_df:
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
    ) -> str:
        """Export IPython session cells to a clean `.py` or `.ipynb` file.

        Automatically prunes:
        - Cells that raised an error during execution (or have invalid Python syntax)
        - Cells rolled back by `%restore` (between checkpoint cell and restore cell)
        - Workbench / inspection magics (`%status`, `%checkpoint`, `%restore`, `%free`, `%export`, `exit -s`, etc.)
        - Read-only previews (bare `df`, `df.head()`, unassigned `%pt df -head`)
        - Consecutive duplicate cells and dead overwritten assignments
        """
        dest = Path(os.path.expanduser(str(dest_path)))
        if dest.suffix.lower() not in (".py", ".ipynb"):
            dest = dest.with_suffix(".py")
        dest.parent.mkdir(parents=True, exist_ok=True)

        kept_cells, pruned_count = self._filter_export_cells(
            history_cells, exclude_cell_index=exclude_cell_index
        )

        # Rewrite each kept cell to Python form for AST dead-code/duplicate/syntax analysis
        rewritten = [_rewrite_cell_for_python(c) for c in kept_cells]
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
        pruned_count += dead_dups

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


def _has_output_flag(cmd: str) -> bool:
    return bool(re.search(r"(?:^|\s)-o(?:\s|=)", cmd))


_PURE_INSPECTION_METHODS = frozenset(
    {
        "head",
        "tail",
        "glimpse",
        "schema",
        "describe",
        "cols",
        "nulls",
        "freq",
        "hist",
        "bar",
        "scatter",
        "corr",
        "info",
        "sample",
        "explain",
    }
)


def _is_pure_python_inspection(code: str) -> bool:
    """Return True if valid Python code contains only side-effect-free interactive previews."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    if not tree.body:
        return True
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr):
            return False
        val = stmt.value
        if isinstance(val, (ast.Name, ast.Attribute, ast.Subscript, ast.Constant)):
            continue
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute):
            if val.func.attr in _PURE_INSPECTION_METHODS:
                continue
        return False
    return True


def _is_skippable_cell(code: str) -> bool:
    """Return True if a cell is purely an inspection/meta magic or unassigned read-only preview."""
    lines = [ln.strip() for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return True

    # Cell magic `%%pt` with no target var and no `-o` output flag is a read-only preview
    if lines[0].startswith("%%"):
        header_parts = lines[0][2:].split()
        magic_name = header_parts[0].lower() if header_parts else ""
        if magic_name in _INSPECTION_MAGICS:
            return True
        if magic_name == "pt":
            has_target = len(header_parts) >= 2 and header_parts[1].isidentifier()
            body = " ".join(lines[1:])
            if not has_target and not _has_output_flag(body):
                return True
            return False
        return False

    all_magic_skippable = True
    for ln in lines:
        if ln.startswith("%"):
            rest = ln.lstrip("%")
            magic_name = rest.split(None, 1)[0].lower() if rest else ""
            if magic_name in _INSPECTION_MAGICS:
                continue
            if magic_name == "pt":
                # Unassigned `%pt ...` without `-o` is read-only exploration
                if not _has_output_flag(rest[2:]):
                    continue
                all_magic_skippable = False
                break
            all_magic_skippable = False
            break
        # Bare automagic commands (e.g. `exit -s maddy.py`, `status`, `checkpoint raw`, `restore`)
        first_tok = ln.split(None, 1)[0].lower()
        if first_tok in _INSPECTION_MAGICS and not ln.startswith(f"{first_tok}=") and not ln.startswith(f"{first_tok} ="):
            continue
        all_magic_skippable = False
        break

    if all_magic_skippable:
        return True

    return _is_pure_python_inspection(code)


_FLUENT_REQ_ARG_FLAGS: dict[str, str] = {
    "-filter": "filter",
    "-mutate": "mutate",
    "-select": "select",
    "-rename": "rename",
    "-by": "by",
    "-arrange": "arrange",
    "-explode": "explode",
    "-assert": "assert_",
    "-o": "to",
}

_FLUENT_OPT_ARG_FLAGS: dict[str, str] = {
    "-agg": "agg",
    "-distinct": "distinct",
    "-dups": "dups",
    "-outliers": "outliers",
    "-count": "count",
    "-dropna": "dropna",
    "-fillna": "fillna",
    "-head": "head",
    "-tail": "tail",
    "-sample": "sample",
}

_FLUENT_INT_FLAGS: dict[str, str] = {
    "-round": "round",
}


def _unquote_token(tok: str) -> str:
    if len(tok) >= 2 and ((tok[0] == '"' and tok[-1] == '"') or (tok[0] == "'" and tok[-1] == "'")):
        return tok[1:-1]
    return tok


def _transpile_pt_to_fluent(cmd: str) -> str | None:
    """Transpile standard `%pt` CLI pipelines into idiomatic fluent Python, or return None to fall back."""
    try:
        raw_tokens = shlex.split(cmd, posix=False)
    except ValueError:
        return None
    if not raw_tokens:
        return None

    tokens = [_unquote_token(t) for t in raw_tokens]
    first = tokens[0]
    if first.startswith("-"):
        return None

    # Source expression
    m_sample = re.match(r"^sample:([A-Za-z0-9_.-]+)$", first)
    if m_sample:
        source_expr = f"pt.sample({m_sample.group(1)!r})"
    elif first.isidentifier() and first.lower() != "clip":
        source_expr = first
    else:
        source_expr = f"pt.read({first!r})"

    if len(tokens) == 1:
        return source_expr

    steps: list[str] = []
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            return None
        flag = tok.lower()
        val: str | None = None
        if "=" in flag:
            flag, _, eq_val = flag.partition("=")
            # Preserve original case for eq_val from tok
            val = tok.partition("=")[2]
            i += 1
        elif flag in _FLUENT_REQ_ARG_FLAGS or flag in _FLUENT_INT_FLAGS:
            if i + 1 >= len(tokens):
                return None
            val = tokens[i + 1]
            i += 2
        elif flag in _FLUENT_OPT_ARG_FLAGS:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                val = tokens[i + 1]
                i += 2
            else:
                i += 1
        else:
            return None

        if flag in _FLUENT_REQ_ARG_FLAGS:
            assert val is not None
            steps.append(f".{_FLUENT_REQ_ARG_FLAGS[flag]}({val!r})")
        elif flag in _FLUENT_INT_FLAGS:
            assert val is not None
            try:
                n = int(val)
            except ValueError:
                return None
            steps.append(f".{_FLUENT_INT_FLAGS[flag]}({n})")
        elif flag in _FLUENT_OPT_ARG_FLAGS:
            method = _FLUENT_OPT_ARG_FLAGS[flag]
            if val is None:
                steps.append(f".{method}()")
            elif flag in ("-head", "-tail", "-sample") and val.isdigit():
                steps.append(f".{method}({int(val)})")
            else:
                steps.append(f".{method}({val!r})")
        else:
            return None

    if len(steps) == 1:
        return f"{source_expr}{steps[0]}"
    joined = "\n    ".join([source_expr] + steps)
    return f"(\n    {joined}\n)"


def _rewrite_pt_cmd_to_python(cmd: str, target_var: str | None = None) -> str:
    """Convert a `%pt` / `%%pt` invocation into standalone valid Python."""
    stripped = cmd.strip()
    fluent = _transpile_pt_to_fluent(stripped)
    expr = fluent if fluent is not None else f"pt.eval_cli({stripped!r}, locals())"
    if target_var:
        return f"{target_var} = {expr}"
    return expr


def _rewrite_cell_for_python(code: str) -> str:
    """Rewrite IPython `%pt` / `%%pt` magics into standalone valid Python for `.py` export."""
    lines = code.splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    if first.startswith("%%pt"):
        parts = first[4:].strip().split()
        target_var = parts[0] if parts and parts[0].isidentifier() else None
        body = " ".join(
            ln.strip() for ln in lines[1:] if ln.strip() and not ln.strip().startswith("#")
        )
        return _rewrite_pt_cmd_to_python(body, target_var=target_var)

    out_lines: list[str] = []
    for raw_ln in lines:
        ln = raw_ln.strip()
        m_assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*%pt\s+(.+)$", ln)
        if m_assign:
            indent = raw_ln[: len(raw_ln) - len(raw_ln.lstrip())]
            out_lines.append(indent + _rewrite_pt_cmd_to_python(m_assign.group(2), target_var=m_assign.group(1)))
            continue
        m_bare = re.match(r"^%pt\s+(.+)$", ln)
        if m_bare:
            indent = raw_ln[: len(raw_ln) - len(raw_ln.lstrip())]
            out_lines.append(indent + _rewrite_pt_cmd_to_python(m_bare.group(1)))
            continue
        if ln.startswith("%"):
            # Comment out any other IPython magic so exported .py is always valid Python
            out_lines.append(f"# {raw_ln}")
            continue
        out_lines.append(raw_ln)
    return "\n".join(out_lines)


def _substitute_ns_vars(token: str, ns: dict[str, Any]) -> str:
    """Substitute `@var` references in CLI flag strings using scalar/list values in `ns`."""
    if "@" not in token:
        return token

    def _repl(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name not in ns:
            return match.group(0)
        val = ns[var_name]
        if is_dataframe(val) or callable(val):
            return match.group(0)
        if isinstance(val, str):
            return repr(val)
        if isinstance(val, (int, float, bool)):
            return str(val)
        if isinstance(val, (list, tuple)):
            return "[" + ", ".join(repr(x) for x in val) + "]"
        return match.group(0)

    return re.sub(r"(?<![A-Za-z0-9_])@([A-Za-z_][A-Za-z0-9_]*)", _repl, token)


_AUTO_IMPORT_MAP: tuple[tuple[str, str], ...] = (
    ("pt", "import pytae as pt"),
    ("pd", "import pandas as pd"),
    ("pl", "import polars as pl"),
    ("np", "import numpy as np"),
    ("Path", "from pathlib import Path"),
)


def _infer_missing_imports(py_cells: list[str], *, always_include_pt: bool = True) -> list[str]:
    """Detect common startup-imported aliases (pt, pd, pl, np, Path) used without explicit imports."""
    loaded: set[str] = set()
    defined: set[str] = set()
    for cell in py_cells:
        try:
            tree = ast.parse(cell)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    loaded.add(node.id)
                elif isinstance(node.ctx, ast.Store):
                    defined.add(node.id)

    missing: list[str] = []
    for sym, stmt in _AUTO_IMPORT_MAP:
        if sym in defined:
            continue
        if sym in loaded or (sym == "pt" and always_include_pt):
            missing.append(stmt)
    return missing


def _build_python_script(cells: list[str]) -> str:
    header = [
        "# Exported from Pytae IPython Workbench",
        f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    missing_imports = _infer_missing_imports(cells, always_include_pt=True)
    if missing_imports:
        header.extend(missing_imports)
        header.append("")

    body = "\n\n".join(cells)
    return "\n".join(header) + ("\n" if header[-1] == "" and body else "") + body + ("\n" if body else "")


def _build_notebook_json(cells: list[str]) -> dict[str, Any]:
    nb_cells: list[dict[str, Any]] = []
    for code in cells:
        src_lines = [ln + "\n" for ln in code.splitlines()]
        if src_lines:
            src_lines[-1] = src_lines[-1].rstrip("\n")
        nb_cells.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": src_lines,
            }
        )
    return {
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ---------------------------------------------------------------------------
# AST dead-assignment & duplicate pruning + CLI post-hoc export from SQLite
# ---------------------------------------------------------------------------

_SIDE_EFFECT_CALLS = frozenset({"to", "write", "write_parquet", "write_csv", "write_ipc", "print", "finalize", "save"})


def _analyze_python_cell(py_code: str) -> tuple[str | None, set[str], bool]:
    """Return `(single_assigned_var, referenced_names, has_side_effect)` for a valid Python cell."""
    try:
        tree = ast.parse(py_code)
    except SyntaxError:
        return None, set(), True

    used: set[str] = set()
    has_side_effect = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in _SIDE_EFFECT_CALLS:
                    has_side_effect = True
                if node.func.attr == "eval_cli" and node.args and isinstance(node.args[0], ast.Constant):
                    cmd_str = str(node.args[0].value)
                    if _has_output_flag(cmd_str):
                        has_side_effect = True
                    # Tokens inside eval_cli('df -filter "x > @k"', locals()) may reference variables
                    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cmd_str):
                        used.add(tok)
            elif isinstance(node.func, ast.Name) and node.func.id in _SIDE_EFFECT_CALLS:
                has_side_effect = True

    single_def: str | None = None
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Assign):
        assign = tree.body[0]
        if len(assign.targets) == 1 and isinstance(assign.targets[0], ast.Name):
            single_def = assign.targets[0].id

    return single_def, used, has_side_effect


def _prune_dead_and_duplicate_cells(pairs: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
    """Drop duplicate consecutive cells, duplicate `import pytae` lines, and dead overwritten assignments."""
    # 1. Deduplicate consecutive identical cells & repeated `import pytae as pt`
    deduped: list[tuple[str, str]] = []
    seen_pt_import = False
    pruned = 0
    for orig, py_code in pairs:
        norm = py_code.strip()
        if deduped and deduped[-1][1].strip() == norm:
            pruned += 1
            continue
        if re.fullmatch(r"import\s+pytae(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?", norm):
            if seen_pt_import:
                pruned += 1
                continue
            seen_pt_import = True
        deduped.append((orig, py_code))

    # 2. Prune dead overwritten single-variable assignments
    analyzed = [_analyze_python_cell(py) for _orig, py in deduped]
    dead_indices: set[int] = set()
    n = len(deduped)
    for i in range(n):
        def_var, _used_i, has_side_effect = analyzed[i]
        if def_var is None or has_side_effect:
            continue
        # Scan forward until `def_var` is either read or unconditionally overwritten
        for j in range(i + 1, n):
            next_def, next_used, _next_se = analyzed[j]
            if def_var in next_used:
                break
            if next_def == def_var:
                dead_indices.add(i)
                break

    final = [pair for idx, pair in enumerate(deduped) if idx not in dead_indices]
    return final, pruned + len(dead_indices)


def _infer_restore_events(history_cells: list[tuple[int, str]]) -> list[tuple[int, int]]:
    """Infer `(checkpoint_cell_idx, restore_cell_idx)` ranges from raw history lines."""
    cp_indices: dict[str, int] = {}
    cp_order: list[str] = []
    restores: list[tuple[int, int]] = []
    for idx, raw in history_cells:
        ln = raw.strip()
        m_cp = re.match(r"^%?checkpoint\s+([A-Za-z0-9_.-]+)", ln)
        if m_cp:
            name = m_cp.group(1)
            if name.lower() not in ("list", "rm", "drop", "delete", "diff"):
                cp_indices[name] = idx
                if name in cp_order:
                    cp_order.remove(name)
                cp_order.append(name)
            continue
        m_res = re.match(r"^%?restore(?:\s+([A-Za-z0-9_.-]+))?\s*$", ln)
        if m_res:
            target = m_res.group(1) or (cp_order[-1] if cp_order else None)
            if target and target in cp_indices:
                restores.append((cp_indices[target], idx))
    return restores


def _read_ipython_sessions(db_path: Path, limit: int = 20) -> list[tuple[int, str, int, str]]:
    """Return recent IPython sessions as `(session_id, start_str, num_cmds, preview)`."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT session, start, COALESCE(num_cmds, 0) FROM sessions ORDER BY session DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        out: list[tuple[int, str, int, str]] = []
        for sess_id, start_ts, num_cmds in rows:
            p_cur = conn.execute(
                "SELECT source_raw FROM history WHERE session = ? ORDER BY line ASC LIMIT 3",
                (sess_id,),
            )
            samples = [str(r[0]).splitlines()[0].strip() for r in p_cur.fetchall() if r[0] and str(r[0]).strip()]
            preview = "; ".join(samples)[:60]
            out.append((int(sess_id), str(start_ts or ""), int(num_cmds), preview))
        return out
    finally:
        conn.close()


def _read_ipython_session_cells(db_path: Path, session_id: int) -> list[tuple[int, str]]:
    """Return `[(line_no, source_raw), ...]` for a given IPython session ID."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT line, source_raw FROM history WHERE session = ? ORDER BY line ASC",
            (session_id,),
        )
        return [(int(line_no), str(src)) for line_no, src in cur.fetchall() if src is not None]
    finally:
        conn.close()


def run_cli_export(argv: list[str], *, db_path: Path | None = None, output_fn: Callable[[str], None] = print) -> int:
    """CLI handler for `pytae -export [session_id | ~N] [-o <dest.py|dest.ipynb>]`."""
    hist_db = db_path or get_ipython_history_db()

    # Parse simple args: optional custom .sqlite path, optional session_id / ~N, optional -o dest
    session_spec: str | None = None
    dest_path: str | None = None
    list_only = False

    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("-list", "--list", "-l"):
            list_only = True
            i += 1
        elif tok in ("-o", "--output"):
            if i + 1 >= len(argv):
                sys.stderr.write("pytae error: '-o' requires an output file path (e.g. -o analysis.py)\n")
                return 1
            dest_path = argv[i + 1]
            i += 2
        elif tok.startswith("-o="):
            dest_path = tok.split("=", 1)[1]
            i += 1
        elif tok.endswith(".sqlite") or tok.endswith(".db"):
            hist_db = Path(os.path.expanduser(tok))
            i += 1
        elif tok.endswith((".py", ".ipynb")) and dest_path is None:
            dest_path = tok
            i += 1
        elif session_spec is None and not tok.startswith("-"):
            session_spec = tok
            i += 1
        else:
            sys.stderr.write(f"pytae error: unrecognized argument for -export: {tok!r}\n")
            return 1

    if not hist_db.exists():
        sys.stderr.write(f"pytae error: IPython history database not found at {hist_db}\n")
        return 1

    sessions = _read_ipython_sessions(hist_db, limit=25)
    if not sessions:
        output_fn("No IPython sessions found in history database.")
        return 0

    if list_only or (session_spec is None and dest_path is None):
        output_fn(f"IPython History ({hist_db}):")
        output_fn(f"{'Session':>8}  {'Started':<19}  {'Cmds':>5}  Preview")
        output_fn("-" * 80)
        for sess_id, start_ts, num_cmds, preview in sessions:
            output_fn(f"{sess_id:>8}  {start_ts[:19]:<19}  {num_cmds:>5}  {preview}")
        output_fn("\nExport with: pytae -export [session_id | ~1] -o <script.py | notebook.ipynb>")
        return 0

    # Resolve target session ID (default: latest non-empty session)
    if session_spec is None or session_spec == "~0":
        target_session = sessions[0][0]
    elif session_spec.startswith("~"):
        try:
            offset = int(session_spec[1:])
            if offset < 1 or offset > len(sessions):
                raise ValueError
            target_session = sessions[offset - 1][0]
        except ValueError:
            sys.stderr.write(f"pytae error: invalid relative session {session_spec!r} (e.g. ~1 for latest)\n")
            return 1
    else:
        try:
            target_session = int(session_spec)
        except ValueError:
            sys.stderr.write(f"pytae error: invalid session ID {session_spec!r}\n")
            return 1

    cells = _read_ipython_session_cells(hist_db, target_session)
    if not cells:
        sys.stderr.write(f"pytae error: session {target_session} has no recorded commands.\n")
        return 1

    out_file = dest_path or f"session_{target_session}.py"
    wb = Workbench(load_config=False)
    try:
        failed, restores = Workbench.load_session_meta(target_session)
        wb.failed_cells = failed
        wb.restore_events = restores or _infer_restore_events(cells)
        msg = wb.export_session(out_file, cells)
        output_fn(f"[session {target_session}] {msg}")
        return 0
    finally:
        wb.cleanup()
