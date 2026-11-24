"""Paths, OS memory management, and DataFrame inspection/conversion helpers for Pytae Workbench."""

from __future__ import annotations

import datetime
import gc
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import polars as pl

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


def get_default_ipython_history_db() -> Path:
    """Return IPython's default SQLite history database path."""
    ipython_dir = Path(os.environ.get("IPYTHONDIR", str(Path.home() / ".ipython"))).expanduser()
    return ipython_dir / "profile_default" / "history.sqlite"


def get_ipython_history_db() -> Path:
    """Resolve IPython's SQLite history DB path.

    Precedence:
    1. `PYTAE_HISTORY_DB` environment variable
    2. `"history_db"` in `~/.pytae/config.json`
    3. `$IPYTHONDIR/profile_default/history.sqlite` (default `~/.ipython/profile_default/history.sqlite`)
    """
    env_db = os.environ.get("PYTAE_HISTORY_DB")
    if env_db and env_db.strip():
        return Path(env_db.strip()).expanduser()

    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg_db = data.get("history_db")
                if isinstance(cfg_db, str) and cfg_db.strip():
                    return Path(cfg_db.strip()).expanduser()
        except Exception:
            pass

    return get_default_ipython_history_db()


def set_ipython_history_db(path: str | None) -> tuple[Path, bool]:
    """Persist or reset `"history_db"` in `~/.pytae/config.json`.

    Returns `(resolved_path, is_reset)`.
    """
    cfg_path = get_config_path()
    existing: dict[str, Any] = {}
    if cfg_path.exists():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception:
            pass

    if path is None or path.strip().lower() in ("", "reset", "default"):
        existing.pop("history_db", None)
        if cfg_path.exists() or existing:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        return get_default_ipython_history_db(), True

    resolved = Path(path.strip()).expanduser().resolve()
    existing["history_db"] = str(resolved)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return resolved, False


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
            with open("/proc/self/status", encoding="utf-8") as f:
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


_USER_VAR_TYPES = (int, float, str, bool, type(None), list, tuple, dict, set, Path, datetime.date, datetime.datetime)


def is_user_var(obj: Any) -> bool:
    """Return True if `obj` is a snapshottable user data variable (scalar, collection, Path, date)."""
    if is_dataframe(obj) or callable(obj):
        return False
    return isinstance(obj, _USER_VAR_TYPES)


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


