"""Interactive REPL (Read-Eval-Print Loop) for pytae with in-memory state and undo/redo.

Provides stateful, iterative data manipulation without repeatedly reloading datasets from disk.
"""

from __future__ import annotations

import argparse
import atexit
import datetime
import gc
import json
import os
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import polars as pl

from pytae.cli_run import _format_table, _process_path
from pytae.readers import DataFrameReader, get_reader


def _safe_ipc_filename(name: str) -> str:
    """Generate a filesystem-safe filename for an IPC table file across all OS platforms."""
    safe = "".join(c if (c.isalnum() or c in ("_", "-")) else f"_{ord(c):02x}_" for c in name)
    return f"{safe}.ipc"


def _release_memory() -> None:
    """Force Python garbage collection and return unmapped/freed memory pages back to the OS."""
    gc.collect()
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            h_process = kernel32.GetCurrentProcess()

            # 1. SetProcessWorkingSetSize(h_process, (SIZE_T)-1, (SIZE_T)-1)
            # Tells the Windows memory manager to trim all unreferenced pages from working set back to the OS
            c_size_t = ctypes.c_size_t
            kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, c_size_t, c_size_t]
            kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
            flg = c_size_t(-1).value
            kernel32.SetProcessWorkingSetSize(h_process, flg, flg)

            # 2. K32EmptyWorkingSet / psapi.EmptyWorkingSet
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


def _get_process_rss_mb() -> float | None:
    """Return the current process RSS / Working Set size in megabytes."""
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
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / (1024 * 1024)
        except Exception:
            pass
    return None


_DEFAULT_SESSIONS_DIR = Path.home() / ".pytae" / "sessions"


def get_sessions_dir() -> Path:
    """Return the base directory for persistent Pytae sessions."""
    env_dir = os.environ.get("PYTAE_SESSIONS_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
    else:
        p = _DEFAULT_SESSIONS_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_saved_sessions(output_fn: Callable[[str], None] = print) -> None:
    """List all saved persistent Pytae sessions stored on disk."""
    s_dir = get_sessions_dir()
    if not s_dir.exists():
        output_fn("No saved sessions found. Use 'session save <name>' or 'pytae -session <name>' to create one.")
        return
    sessions = sorted([p for p in s_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])
    if not sessions:
        output_fn("No saved sessions found. Use 'session save <name>' or 'pytae -session <name>' to create one.")
        return
    output_fn("Saved Sessions:")
    for s_path in sessions:
        meta_file = s_path / "session.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        cp_dir = s_path / "checkpoints"
        cps = [p.name for p in cp_dir.iterdir() if p.is_dir()] if cp_dir.exists() else []
        total_bytes = sum(f.stat().st_size for f in s_path.rglob("*") if f.is_file())
        if total_bytes >= 1024 * 1024:
            size_str = f"~{total_bytes / (1024 * 1024):.1f} MB"
        elif total_bytes >= 1024:
            size_str = f"~{total_bytes / 1024:.1f} KB"
        else:
            size_str = f"{total_bytes} B"
        up_date = meta.get("updated_at") or meta.get("created_at") or ""
        date_str = f"; updated {up_date}" if up_date else ""
        cp_str = f"{len(cps)} checkpoints: {', '.join(cps)}" if cps else "0 checkpoints"
        output_fn(f"  - {s_path.name:<15} ({cp_str}; {size_str}{date_str})")


try:
    import readline  # Standard Unix / macOS readline
except ImportError:
    try:
        import pyreadline3 as readline  # Windows pyreadline3 package
    except ImportError:
        try:
            import pyreadline as readline  # Windows legacy pyreadline
        except ImportError:
            try:
                from _pyrepl import readline  # Python 3.13+ standard library
            except ImportError:
                readline = None

_HIST_FILE = Path.home() / ".pytae_history"


def _load_history_from_file() -> list[str]:
    """Read saved command history lines from disk."""
    if _HIST_FILE.exists():
        try:
            return [line.strip() for line in _HIST_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return []
    return []


def _save_raw_history(history: list[str]) -> None:
    """Save raw command history list to disk (used when readline is unavailable)."""
    try:
        lines = history[-1000:]
        _HIST_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _win_console_input(prompt_text: str, history: list[str]) -> str:
    """Read console input on Windows with arrow key history navigation and line editing."""
    try:
        import msvcrt
    except ImportError:
        return input(prompt_text)

    sys.stdout.write(prompt_text)
    sys.stdout.flush()

    line_chars: list[str] = []
    cursor_pos = 0
    hist_idx = len(history)
    draft = ""
    last_rendered_len = 0

    def render() -> None:
        nonlocal last_rendered_len
        text = "".join(line_chars)
        pad = max(0, last_rendered_len - len(text))
        sys.stdout.write("\r" + prompt_text + text + (" " * pad))
        backtrack = pad + (len(text) - cursor_pos)
        if backtrack > 0:
            sys.stdout.write("\b" * backtrack)
        sys.stdout.flush()
        last_rendered_len = len(text)

    while True:
        try:
            ch = msvcrt.getwch()
        except (KeyboardInterrupt, EOFError):
            raise
        except Exception:
            return "".join(line_chars)

        code: str | None = None
        if ch in ("\x00", "\xe0"):
            try:
                code = msvcrt.getwch()
            except Exception:
                continue
        elif ch == "\x1b":
            # ANSI escape sequence from terminal emulators (e.g. Git Bash, Windows Terminal)
            seq = ""
            try:
                import time

                kbhit_fn = getattr(msvcrt, "kbhit", None)
                if kbhit_fn is not None:
                    for _ in range(8):
                        if kbhit_fn():
                            seq += msvcrt.getwch()
                            if seq in (
                                "[A",
                                "OA",
                                "[B",
                                "OB",
                                "[C",
                                "OC",
                                "[D",
                                "OD",
                                "[H",
                                "OH",
                                "[F",
                                "OF",
                                "[3~",
                                "[1~",
                                "[4~",
                                "[7~",
                                "[8~",
                            ):
                                break
                        else:
                            time.sleep(0.002)
                            if kbhit_fn():
                                seq += msvcrt.getwch()
                            else:
                                break
                else:
                    for _ in range(4):
                        try:
                            seq += msvcrt.getwch()
                            if seq in (
                                "[A",
                                "OA",
                                "[B",
                                "OB",
                                "[C",
                                "OC",
                                "[D",
                                "OD",
                                "[H",
                                "OH",
                                "[F",
                                "OF",
                                "[3~",
                                "[1~",
                                "[4~",
                                "[7~",
                                "[8~",
                            ):
                                break
                        except Exception:
                            break
            except Exception:
                pass

            ansi_map = {
                "[A": "H",
                "OA": "H",  # Up arrow
                "[B": "P",
                "OB": "P",  # Down arrow
                "[D": "K",
                "OD": "K",  # Left arrow
                "[C": "M",
                "OC": "M",  # Right arrow
                "[H": "G",
                "OH": "G",
                "[1~": "G",
                "[7~": "G",  # Home
                "[F": "O",
                "OF": "O",
                "[4~": "O",
                "[8~": "O",  # End
                "[3~": "S",  # Delete
            }
            if seq in ansi_map:
                code = ansi_map[seq]
            elif not seq:
                # Bare Escape key pressed: clear current line
                line_chars.clear()
                cursor_pos = 0
                render()
                continue
            else:
                continue

        if code is not None:
            if code == "H":  # Up arrow
                if history:
                    if hist_idx == len(history):
                        draft = "".join(line_chars)
                    if hist_idx > 0:
                        hist_idx -= 1
                        line_chars = list(history[hist_idx])
                        cursor_pos = len(line_chars)
                        render()
            elif code == "P":  # Down arrow
                if history and hist_idx < len(history):
                    hist_idx += 1
                    if hist_idx == len(history):
                        line_chars = list(draft)
                    else:
                        line_chars = list(history[hist_idx])
                    cursor_pos = len(line_chars)
                    render()
            elif code == "K":  # Left arrow
                if cursor_pos > 0:
                    cursor_pos -= 1
                    sys.stdout.write("\b")
                    sys.stdout.flush()
            elif code == "M":  # Right arrow
                if cursor_pos < len(line_chars):
                    sys.stdout.write(line_chars[cursor_pos])
                    cursor_pos += 1
                    sys.stdout.flush()
            elif code == "G":  # Home
                if cursor_pos > 0:
                    cursor_pos = 0
                    render()
            elif code == "O":  # End
                if cursor_pos < len(line_chars):
                    cursor_pos = len(line_chars)
                    render()
            elif code == "S":  # Delete
                if cursor_pos < len(line_chars):
                    line_chars.pop(cursor_pos)
                    render()
        elif ch in ("\r", "\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(line_chars)
        elif ch == "\x08":  # Backspace
            if cursor_pos > 0:
                cursor_pos -= 1
                line_chars.pop(cursor_pos)
                render()
        elif ch == "\x03":  # Ctrl+C
            sys.stdout.write("\n")
            sys.stdout.flush()
            raise KeyboardInterrupt
        elif ch in ("\x04", "\x1a"):  # Ctrl+D or Ctrl+Z
            sys.stdout.write("\n")
            sys.stdout.flush()
            if not line_chars:
                raise EOFError
        elif ch >= " ":  # Printable character
            line_chars.insert(cursor_pos, ch)
            cursor_pos += 1
            render()


def _init_readline() -> None:
    """Initialize readline history file and arrow key navigation."""
    if readline is None:
        return
    doc = getattr(readline, "__doc__", "") or ""
    if "libedit" in doc:
        try:
            readline.parse_and_bind("bind -e")
            readline.parse_and_bind(r"bind '\e[A' ed-prev-history")
            readline.parse_and_bind(r"bind '\e[B' ed-next-history")
            readline.parse_and_bind(r"bind '\eOA' ed-prev-history")
            readline.parse_and_bind(r"bind '\eOB' ed-next-history")
        except Exception:
            pass
    else:
        try:
            readline.parse_and_bind(r'"\e[A": previous-history')
            readline.parse_and_bind(r'"\e[B": next-history')
            readline.parse_and_bind(r'"\eOA": previous-history')
            readline.parse_and_bind(r'"\eOB": next-history')
            readline.parse_and_bind(r'"\e[C": forward-char')
            readline.parse_and_bind(r'"\e[D": backward-char')
            readline.parse_and_bind(r'"\eOC": forward-char')
            readline.parse_and_bind(r'"\eOD": backward-char')
            readline.parse_and_bind(r'"\e[H": beginning-of-line')
            readline.parse_and_bind(r'"\e[F": end-of-line')
        except Exception:
            pass
    if _HIST_FILE.exists():
        try:
            readline.read_history_file(str(_HIST_FILE))
        except Exception:
            pass
    import atexit

    atexit.register(_save_readline_history)


def _save_readline_history() -> None:
    """Persist readline history to disk."""
    if readline is not None:
        try:
            readline.set_history_length(1000)
            readline.write_history_file(str(_HIST_FILE))
        except Exception:
            pass


def _split_repl_pipe(raw: str) -> tuple[str, str] | None:
    """Split line on top-level '|' outside quotes and brackets for shell piping."""
    in_single = False
    in_double = False
    bracket_depth = 0
    escape = False
    for idx, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "[" and not in_single and not in_double:
            bracket_depth += 1
        elif ch == "]" and not in_single and not in_double and bracket_depth > 0:
            bracket_depth -= 1
        elif ch == "|" and not in_single and not in_double and bracket_depth == 0:
            left = raw[:idx].strip()
            right = raw[idx + 1 :].strip()
            if left and right:
                return left, right
    return None


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
  -select <cols>         : Column projection, e.g. -select "species,island,!mass_kg"
  -arrange <specs>       : Sort rows, e.g. -arrange "mass_kg desc"
  -by <g> -agg <specs>   : Grouped aggregation, e.g. -by species -agg "m=mass:mean, n=count"
  -distinct <cols>       : Deduplicate rows
  -dropna [cols]         : Drop missing values
  -fillna <specs>        : Impute missing values
  -head [N] / -tail [N]  : Non-destructive preview of top/bottom N rows (e.g. -head 10)
  -shape                 : Display row and column counts
  -cols [asc|desc]       : List column names (file order, or asc/desc sorted)
  -dtype / -nulls        : Inspect schema dtypes and missing value counts
  -time [N]              : Benchmark execution over N runs (default: 1), e.g. -distinct -time 3
  -o <path> / -o clip    : Export table to file (Parquet/CSV/NDJSON) or clipboard
  <cmd> | <shell_cmd>    : Pipe command output to shell tool (e.g. -cols | grep bill)

MODE 2: MULTI-TABLE WORKBENCH (pytae -i):
  Load multiple datasets and operate with subject-first syntax (<tbl> -<cmd>):
  <var> = <path> [options]: Ingest dataset (e.g. df1 = data.csv -encoding latin1 -dlim ";")
  load <path> as <var>... : Load dataset with alias and options (-encoding, -dlim, -nrows)
  <tbl> -head [N]        : Preview specific table (e.g. df1 -head 5, df2 -head 3)
  <tbl> -shape / -cols   : Inspect table metadata (e.g. df1 -shape, df2 -cols asc)
  <tbl> -time [N]        : Switch active dataset and measure elapsed time (e.g. df1 -time)
  <tbl> -<pipeline>      : Run pipeline directly on table (e.g. df1 -filter "amount > 100")
  <tbl> -join <t2> on=<k>: Join tables (e.g. df1 -join df2 on=cust_id -o merged.parquet)
  <tbl> -o <path>        : Export specific table (e.g. df1 -o clean_orders.parquet)
  <var> = <tbl> -<pipe>  : Assign pipeline result to new variable (e.g. df3 = df1 -filter ...)
  <var> = <t1> -join <t2>: Assign join result (e.g. df3 = df1 -join df2 on=cust_id)
  <var> = -sql "<query>" : Create table from ANSI SQL across loaded tables
  rm <table_name>        : Remove in-memory table (e.g. rm df1, rm df, or rm *)
  tables                 : List all loaded datasets in memory
  use <name>             : Switch active dataset (or type bare table name e.g. df1)

STATE NAVIGATION (Undoable):
  undo                   : Revert the last transformation step
  redo                   : Re-apply the last undone transformation step
  reset                  : Revert to latest checkpoint (or initial read if no checkpoints)
  reset initial          : Strictly revert to initial read even if checkpoints exist
  history                : Show numbered transformation log and milestone banners
  checkpoint <name>      : Save snapshot of entire workbench (all tables in session)
  restore <name>         : Restore entire workbench to saved checkpoint
  checkpoints            : List saved checkpoints and their tables
  rm checkpoint <name>   : Delete a saved checkpoint (or 'rm checkpoint *')
  session                : Show persistent session status
  session save <name>    : Persist workbench checkpoints to ~/.pytae/sessions/<name> (or $PYTAE_SESSIONS_DIR)
  session load <name>    : Load persistent session checkpoints from disk
  sessions               : List all saved persistent sessions on disk
  rm session <name>      : Remove a saved persistent session from disk
  clear                  : Clear the terminal screen
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
    "cls": "clear",
    "-cls": "clear",
    "--cls": "clear",
    "-clear": "clear",
    "--clear": "clear",
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
    "-rm": "rm",
    "--rm": "rm",
    "-checkpoint": "checkpoint",
    "--checkpoint": "checkpoint",
    "-checkpoints": "checkpoints",
    "--checkpoints": "checkpoints",
    "-restore": "restore",
    "--restore": "restore",
    "-session": "session",
    "--session": "session",
    "-sessions": "sessions",
    "--sessions": "sessions",
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
    "--time": "-time",
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
        "time",
    )
)


def _parse_reader_options(tokens: list[str]) -> tuple[list[str], dict[str, Any], int | None]:
    """Parse inline reader flags (-encoding, -dlim, -nrows) from a token list.

    Returns (cleaned_tokens, reader_kwargs, nrows_val).
    """
    cleaned: list[str] = []
    reader_kwargs: dict[str, Any] = {}
    nrows_val: int | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-encoding", "--encoding") and i + 1 < len(tokens):
            reader_kwargs["encoding"] = tokens[i + 1]
            i += 2
        elif tok in ("-dlim", "--dlim") and i + 1 < len(tokens):
            reader_kwargs["sep"] = tokens[i + 1]
            i += 2
        elif tok in ("-nrows", "--nrows", "-limit", "--limit") and i + 1 < len(tokens):
            try:
                nrows_val = int(tokens[i + 1])
            except ValueError:
                pass
            i += 2
        elif tok in ("-fmt", "--fmt") and i + 1 < len(tokens):
            i += 2
        else:
            cleaned.append(tok)
            i += 1

    return cleaned, reader_kwargs, nrows_val


class PytaeRepl:
    """Stateful interactive REPL environment for pytae."""

    def __init__(
        self,
        df: Any | None = None,
        path: Path | str | None = None,
        paths: list[Path | str] | None = None,
        prompt: str = "pytae",
        encoding: str | None = None,
        sep: str | None = None,
        delimiter: str | None = None,
        nrows: int | None = None,
        chunk_size: int | None = None,
        reader_kwargs: dict[str, Any] | None = None,
        session: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.prompt = prompt
        self.session_name: str | None = session.strip() if session and str(session).strip() else None
        self.reader_kwargs: dict[str, Any] = dict(reader_kwargs or {})
        if encoding:
            self.reader_kwargs["encoding"] = encoding
        if sep or delimiter:
            self.reader_kwargs["sep"] = sep or delimiter
        if nrows is not None:
            self.reader_kwargs["nrows"] = nrows
        if chunk_size is not None:
            self.reader_kwargs["chunk_size"] = chunk_size
        for k, v in kwargs.items():
            if k not in self.reader_kwargs:
                self.reader_kwargs[k] = v

        self.max_undo_steps: int = 10
        self.undo_stack: list[tuple[str, Any]] = []
        self.redo_stack: list[tuple[str, Any]] = []
        self.tables: dict[str, pl.DataFrame] = {}
        self.orig_tables: dict[str, pl.DataFrame] = {}
        self.initial_tables: dict[str, pl.DataFrame] = {}
        self.initial_df: pl.DataFrame | None = None
        self.checkpoints: dict[str, Any] = {}
        self._cp_temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.table_sources: dict[str, str] = {}
        self.history: list[str] = []
        self._raw_history: list[str] = _load_history_from_file()
        self._history_cursor: int | None = None

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
                try:
                    p, t_df = self._read_file_to_df(path_val)
                    self.tables[var_name] = t_df
                    self.orig_tables[var_name] = t_df
                    self.initial_tables[var_name] = t_df
                    self.table_sources[var_name] = p.name
                    self.current_df = t_df
                    self.orig_df = t_df
                    if self.initial_df is None:
                        self.initial_df = t_df
                    self.path_str = var_name
                except Exception:
                    pass
        elif df is not None:
            self._set_initial_df(df)
            self.path = Path(path) if path else None
            self.path_str = self.path.name if self.path else "df"
            initial_name = self.path_str
            self.tables[initial_name] = self.current_df
            self.orig_tables[initial_name] = self.current_df
            self.initial_tables[initial_name] = self.current_df
            self.initial_df = self.current_df
            self.table_sources[initial_name] = str(self.path) if self.path else "<memory>"
        elif path is not None:
            self.path = Path(path)
            self._load_file(self.path)
            initial_name = self.path_str or self.path.stem or "df"
            self.tables[initial_name] = self.current_df
            self.orig_tables[initial_name] = self.current_df
            self.initial_tables[initial_name] = self.current_df
            self.initial_df = self.current_df
            self.table_sources[initial_name] = self.path.name

        if self.session_name:
            self._load_session_from_disk(self.session_name)

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

    def _get_cp_dir(self) -> Path:
        """Return the checkpoint directory for disk-backed checkpoints, creating lazily if needed."""
        if self.session_name:
            p = get_sessions_dir() / self.session_name / "checkpoints"
            p.mkdir(parents=True, exist_ok=True)
            return p
        if self._cp_temp_dir is None:
            self._cp_temp_dir = tempfile.TemporaryDirectory(prefix="pytae_cp_")
            atexit.register(self._cleanup_cp_dir)
        return Path(self._cp_temp_dir.name)

    def _cleanup_cp_dir(self) -> None:
        """Clean up the temporary session checkpoint directory from disk."""
        if self.session_name is not None:
            return
        if self._cp_temp_dir is not None:
            try:
                self._cp_temp_dir.cleanup()
            except Exception:
                pass
            self._cp_temp_dir = None

    def _delete_checkpoint(self, name: str) -> bool:
        """Delete a saved checkpoint and remove its files from disk."""
        if name not in self.checkpoints:
            return False
        snap = self.checkpoints.pop(name)
        if isinstance(snap, dict) and "dir" in snap:
            shutil.rmtree(snap["dir"], ignore_errors=True)
        if self.session_name:
            self._save_session_metadata()
        return True

    def _clear_all_checkpoints(self) -> int:
        """Delete all saved checkpoints and wipe their directory trees from disk."""
        count = len(self.checkpoints)
        for name in list(self.checkpoints.keys()):
            self._delete_checkpoint(name)
        return count

    def _get_checkpoint_df(self, name: str) -> pl.DataFrame | None:
        """Retrieve a DataFrame from a checkpoint (loads on-demand from disk IPC or memory)."""
        if name not in self.checkpoints:
            return None
        snap = self.checkpoints[name]
        if isinstance(snap, pl.DataFrame):
            return snap
        if isinstance(snap, dict):
            if "dir" in snap:
                cp_dir = Path(snap["dir"])
                meta_file = cp_dir / "meta.json"
                meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else snap
                tbl_meta = meta.get("tables", {})
                if not tbl_meta:
                    return None
                act = meta.get("active_table")
                if act and act in tbl_meta:
                    f_name = (
                        tbl_meta[act].get("file", _safe_ipc_filename(act))
                        if isinstance(tbl_meta[act], dict)
                        else _safe_ipc_filename(act)
                    )
                    ipc_p = cp_dir / f_name
                    if ipc_p.exists():
                        return pl.read_ipc(ipc_p)
                if len(tbl_meta) == 1:
                    first_k, first_v = next(iter(tbl_meta.items()))
                    f_name = (
                        first_v.get("file", _safe_ipc_filename(first_k))
                        if isinstance(first_v, dict)
                        else _safe_ipc_filename(first_k)
                    )
                    ipc_p = cp_dir / f_name
                    if ipc_p.exists():
                        return pl.read_ipc(ipc_p)
                if "_current_df" in tbl_meta:
                    f_name = (
                        tbl_meta["_current_df"].get("file", "_current_df.ipc")
                        if isinstance(tbl_meta["_current_df"], dict)
                        else "_current_df.ipc"
                    )
                    ipc_p = cp_dir / f_name
                    if ipc_p.exists():
                        return pl.read_ipc(ipc_p)
                for k, v in tbl_meta.items():
                    f_name = v.get("file", _safe_ipc_filename(k)) if isinstance(v, dict) else _safe_ipc_filename(k)
                    ipc_p = cp_dir / f_name
                    if ipc_p.exists():
                        return pl.read_ipc(ipc_p)
                return None
            tbls = snap.get("tables", {})
            if snap.get("active_table") and snap["active_table"] in tbls:
                return tbls[snap["active_table"]]
            if len(tbls) == 1:
                return next(iter(tbls.values()))
            if snap.get("current_df") is not None:
                return snap["current_df"]
        return None

    def _get_checkpoint_table_df(self, cp_name: str, table_name: str) -> pl.DataFrame | None:
        """Retrieve a specific table's DataFrame from a named checkpoint."""
        if cp_name not in self.checkpoints:
            return None
        snap = self.checkpoints[cp_name]
        if isinstance(snap, pl.DataFrame):
            return snap if table_name in ("df", "_current_df") else None
        if isinstance(snap, dict):
            if "dir" in snap:
                cp_dir = Path(snap["dir"])
                meta_file = cp_dir / "meta.json"
                meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else snap
                tbl_meta = meta.get("tables", {})
                for k, tbl_info in tbl_meta.items():
                    if k == table_name or k.lower() == table_name.lower() or Path(k).stem.lower() == table_name.lower():
                        f_name = (
                            tbl_info.get("file", _safe_ipc_filename(k))
                            if isinstance(tbl_info, dict)
                            else _safe_ipc_filename(k)
                        )
                        ipc_p = cp_dir / f_name
                        if ipc_p.exists():
                            return pl.read_ipc(ipc_p)
                if "_current_df" in tbl_meta and (len(tbl_meta) == 1 or meta.get("active_table") == table_name):
                    ipc_p = cp_dir / "_current_df.ipc"
                    if ipc_p.exists():
                        return pl.read_ipc(ipc_p)
                return None
            tbls = snap.get("tables", {})
            for k, val in tbls.items():
                if k == table_name or k.lower() == table_name.lower() or Path(k).stem.lower() == table_name.lower():
                    return val.clone() if hasattr(val, "clone") else val
        return None

    def close(self) -> None:
        """Clean up temporary checkpoint disk storage and release all in-memory tables."""
        if self.session_name is None:
            self._clear_all_checkpoints()
            self._cleanup_cp_dir()
        self.tables.clear()
        self.orig_tables.clear()
        self.initial_tables.clear()
        self.table_sources.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_df = None
        self.orig_df = None
        self.initial_df = None
        self.path_str = None
        _release_memory()

    def __del__(self) -> None:
        self._cleanup_cp_dir()

    def _read_file_to_df(self, path: Path | str, **reader_opts: Any) -> tuple[Path, pl.DataFrame]:
        """Resolve a dataset path and load it into a Polars DataFrame using reader kwargs with schema fallback."""
        p = Path(path).expanduser()
        if str(p).startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = str(p)[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                raise FileNotFoundError(f"unknown sample dataset '{sample_name}'. Available: {available}")
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
        opts = dict(self.reader_kwargs)
        opts.update(reader_opts)
        sep_val = opts.get("sep") or opts.get("delimiter")
        enc_val = opts.get("encoding")
        chunk_val = opts.get("chunk_size", 200_000)
        nrows_val = opts.get("nrows")
        reader = get_reader(p, sep=sep_val, encoding=enc_val, chunk_size=chunk_val)
        df = reader.to_polars(nrows=nrows_val)
        return p, df

    def _load_file(self, path: Path | str, **reader_opts: Any) -> None:
        p, df = self._read_file_to_df(path, **reader_opts)
        self.path = p
        self.path_str = p.name
        self.orig_df = df
        self.current_df = df

    def _get_shape_str(self) -> str:
        if self.current_df is None:
            return "no dataset"
        return f"{self.current_df.shape[0]:,}x{self.current_df.shape[1]}"

    def _resolve_table_name(self, target: str) -> str | None:
        """Resolve a table identifier to the canonical key in self.tables.

        Supports:
        1. Exact match (e.g. 'penguins.parquet', 'df1')
        2. Case-insensitive match (e.g. 'PENGUINS.PARQUET')
        3. Path stem match (e.g. 'penguins' matches 'penguins.parquet' or 'data/penguins.parquet')
        4. Universal alias 'df', 'data', 'self', 'active': resolves to current active table
           (self.path_str) if set and in self.tables, or the sole loaded table if only one exists.
        """
        if not self.tables:
            return None
        if target in self.tables:
            return target
        target_lower = target.lower()
        for k in self.tables:
            if k.lower() == target_lower:
                return k
        for k in self.tables:
            stem = Path(k).stem.lower()
            if stem == target_lower:
                return k
        if target_lower in ("df", "data", "self", "active"):
            if self.path_str and self.path_str in self.tables:
                return self.path_str
            if len(self.tables) == 1:
                return next(iter(self.tables.keys()))
        return None

    def _build_prompt(self) -> str:
        prefix = f"{self.prompt}:{self.session_name}" if self.session_name else self.prompt
        if len(self.tables) > 1:
            table_names = ", ".join(self.tables.keys())
            return f"{prefix} [{table_names}]> "
        elif self.current_df is not None:
            name = self.path_str or "<dataframe>"
            return f"{prefix} [{name}: {self._get_shape_str()}]> "
        return f"{prefix}> "

    def _save_session_metadata(self) -> None:
        """Save session manifest and pipeline history to disk under the session directory."""
        if not self.session_name:
            return
        s_dir = get_sessions_dir() / self.session_name
        s_dir.mkdir(parents=True, exist_ok=True)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta: dict[str, Any] = {
            "name": self.session_name,
            "updated_at": now_str,
            "checkpoints": list(self.checkpoints.keys()),
            "latest_checkpoint": list(self.checkpoints.keys())[-1] if self.checkpoints else None,
        }
        meta_file = s_dir / "session.json"
        if not meta_file.exists():
            meta["created_at"] = now_str
        else:
            try:
                old = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["created_at"] = old.get("created_at", now_str)
            except Exception:
                meta["created_at"] = now_str
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (s_dir / "history.json").write_text(json.dumps(self.history, indent=2), encoding="utf-8")

    def _load_session_from_disk(self, name: str, output_fn: Callable[[str], None] | None = None) -> bool:
        """Load session history and saved checkpoints from disk, activating the latest checkpoint."""
        s_dir = get_sessions_dir() / name
        if not s_dir.exists():
            return False

        hist_file = s_dir / "history.json"
        if hist_file.exists():
            try:
                loaded_hist = json.loads(hist_file.read_text(encoding="utf-8"))
                if isinstance(loaded_hist, list):
                    self.history = [str(x) for x in loaded_hist]
            except Exception:
                pass

        cp_dir = s_dir / "checkpoints"
        if cp_dir.exists():
            cp_subdirs = sorted([p for p in cp_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])
            meta_file = s_dir / "session.json"
            cp_order: list[str] = []
            if meta_file.exists():
                try:
                    s_meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    cp_order = s_meta.get("checkpoints", [])
                except Exception:
                    pass

            ordered_subs: list[Path] = []
            for cp_n in cp_order:
                sub = cp_dir / cp_n
                if sub.is_dir() and sub not in ordered_subs:
                    ordered_subs.append(sub)
            for sub in cp_subdirs:
                if sub not in ordered_subs:
                    ordered_subs.append(sub)

            self.checkpoints.clear()
            for sub in ordered_subs:
                cp_name = sub.name
                m_path = sub / "meta.json"
                if m_path.exists():
                    try:
                        cp_meta = json.loads(m_path.read_text(encoding="utf-8"))
                    except Exception:
                        cp_meta = {"dir": str(sub)}
                else:
                    cp_meta = {"dir": str(sub)}
                cp_meta["dir"] = str(sub)
                self.checkpoints[cp_name] = cp_meta

            if self.checkpoints:
                latest_cp = list(self.checkpoints.keys())[-1]
                self._cmd_restore(latest_cp, output_fn or (lambda s: None), record_history=False)
                if output_fn:
                    output_fn(f"Resumed session '{name}' from latest checkpoint '{latest_cp}'.")
                return True

        return True

    def _cmd_session(self, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        """Handle session inspection, saving, loading, and deletion."""
        if not tokens:
            if self.session_name:
                output_fn(
                    f"Active session: '{self.session_name}' ({len(self.checkpoints)} checkpoints; "
                    f"location: {get_sessions_dir() / self.session_name})"
                )
            else:
                output_fn(
                    "No active session (ephemeral). Use 'session save <name>' or 'pytae -session <name>' to persist."
                )
            return

        subcmd = tokens[0].lower()
        if subcmd == "save":
            if len(tokens) < 2:
                output_fn("Usage: session save <name>")
                return
            self._cmd_session_save(tokens[1], output_fn)
            return

        if subcmd == "load":
            if len(tokens) < 2:
                output_fn("Usage: session load <name>")
                return
            self._cmd_session_load(tokens[1], output_fn)
            return

        if subcmd in ("list", "ls"):
            list_saved_sessions(output_fn)
            return

        if subcmd == "rm":
            if len(tokens) < 2:
                output_fn("Usage: session rm <name> or rm session <name>")
                return
            self._cmd_rm_session(tokens[1], output_fn)
            return

        output_fn(
            f"pytae: unknown session action '{subcmd}'. "
            f"Usage: session, session save <name>, session load <name>, sessions, or rm session <name>"
        )

    def _cmd_session_save(self, name: str, output_fn: Callable[[str], None]) -> None:
        target_name = name.strip()
        if not target_name or any(c in target_name for c in ("/", "\\", "..", "\0")):
            output_fn("pytae: invalid session name. Use alphanumeric characters, dashes, and underscores.")
            return

        s_dir = get_sessions_dir() / target_name
        target_cp_dir = s_dir / "checkpoints"
        target_cp_dir.mkdir(parents=True, exist_ok=True)

        if self._cp_temp_dir is not None:
            temp_p = Path(self._cp_temp_dir.name)
            for cp_name, cp_meta in list(self.checkpoints.items()):
                src_sub = temp_p / cp_name
                dst_sub = target_cp_dir / cp_name
                if src_sub.exists() and src_sub != dst_sub:
                    if dst_sub.exists():
                        shutil.rmtree(dst_sub, ignore_errors=True)
                    shutil.copytree(src_sub, dst_sub)
                    if isinstance(cp_meta, dict):
                        cp_meta["dir"] = str(dst_sub)
                        m_json = dst_sub / "meta.json"
                        if m_json.exists():
                            try:
                                m_data = json.loads(m_json.read_text(encoding="utf-8"))
                                m_data["dir"] = str(dst_sub)
                                m_json.write_text(json.dumps(m_data), encoding="utf-8")
                            except Exception:
                                pass
            self._cleanup_cp_dir()
        elif self.session_name and self.session_name != target_name:
            src_cp_dir = get_sessions_dir() / self.session_name / "checkpoints"
            if src_cp_dir.exists():
                for cp_name, cp_meta in list(self.checkpoints.items()):
                    src_sub = src_cp_dir / cp_name
                    dst_sub = target_cp_dir / cp_name
                    if src_sub.exists() and src_sub != dst_sub:
                        if dst_sub.exists():
                            shutil.rmtree(dst_sub, ignore_errors=True)
                        shutil.copytree(src_sub, dst_sub)
                        if isinstance(cp_meta, dict):
                            cp_meta["dir"] = str(dst_sub)

        self.session_name = target_name
        self._save_session_metadata()
        output_fn(f"Session saved as '{target_name}' ({len(self.checkpoints)} checkpoints saved).")

    def _cmd_session_load(self, name: str, output_fn: Callable[[str], None]) -> None:
        target_name = name.strip()
        s_dir = get_sessions_dir() / target_name
        if not s_dir.exists():
            output_fn(f"pytae: session '{target_name}' not found. Use 'sessions' to list saved sessions.")
            return

        self.close()
        self.session_name = target_name
        self._load_session_from_disk(target_name, output_fn)

    def _cmd_rm_session(self, name: str, output_fn: Callable[[str], None]) -> None:
        target_name = name.strip()
        s_dir = get_sessions_dir() / target_name
        if not s_dir.exists():
            avail = (
                [p.name for p in get_sessions_dir().iterdir() if p.is_dir() and not p.name.startswith(".")]
                if get_sessions_dir().exists()
                else []
            )
            avail_str = ", ".join(avail) if avail else "none"
            output_fn(f"pytae: session '{target_name}' not found. Available: {avail_str}")
            return
        shutil.rmtree(s_dir, ignore_errors=True)
        if self.session_name == target_name:
            self.session_name = None
            output_fn(f"Removed session '{target_name}'. Active session reverted to ephemeral.")
        else:
            output_fn(f"Removed session '{target_name}'.")

    def execute_line(self, raw_line: str, output_fn: Callable[[str], None] = print) -> bool:
        """Execute one REPL input line. Returns False if REPL should terminate."""
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return True

        # Handle ANSI arrow keys sent directly via Git Bash / MinTTY terminal pipe
        ansi_up_count = line.count("\x1b[A") + line.count("\x1bOA") + line.count("^[[A") + line.count("^[OA")
        ansi_down_count = line.count("\x1b[B") + line.count("\x1bOB") + line.count("^[[B") + line.count("^[OB")
        cleaned_ansi = (
            line.replace("\x1b[A", "")
            .replace("\x1bOA", "")
            .replace("^[[A", "")
            .replace("^[OA", "")
            .replace("\x1b[B", "")
            .replace("\x1bOB", "")
            .replace("^[[B", "")
            .replace("^[OB", "")
            .strip()
        )
        if (ansi_up_count > 0 or ansi_down_count > 0) and not cleaned_ansi:
            if not self._raw_history:
                output_fn("pytae: no previous commands in history.")
                return True
            if self._history_cursor is None:
                self._history_cursor = len(self._raw_history)
            delta = ansi_up_count - ansi_down_count
            self._history_cursor = max(0, min(len(self._raw_history) - 1, self._history_cursor - delta))
            recalled = self._raw_history[self._history_cursor]
            output_fn(f"(recalled from history: {recalled})")
            return self.execute_line(recalled, output_fn=output_fn)

        self._history_cursor = None

        if not self._raw_history or self._raw_history[-1] != line:
            self._raw_history.append(line)

        if readline is not None:
            try:
                readline.add_history(line)
            except Exception:
                pass

        # Check for top-level shell pipe: <repl_command> | <shell_command>
        pipe_parts = _split_repl_pipe(line)
        if pipe_parts is not None:
            left_cmd, shell_cmd = pipe_parts
            buffer: list[str] = []
            cont = self.execute_line(left_cmd, output_fn=buffer.append)
            if buffer:
                combined_output = "\n".join(buffer)
                if not combined_output.endswith("\n"):
                    combined_output += "\n"
                import subprocess

                try:
                    capture = output_fn is not print
                    proc = subprocess.Popen(
                        shell_cmd,
                        shell=True,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE if capture else None,
                        stderr=subprocess.PIPE if capture else None,
                        text=True,
                    )
                    stdout_data, stderr_data = proc.communicate(input=combined_output)
                    if capture:
                        if stdout_data:
                            output_fn(stdout_data.rstrip("\r\n"))
                        if stderr_data:
                            output_fn(stderr_data.rstrip("\r\n"))
                except BrokenPipeError:
                    pass
                except Exception as exc:
                    output_fn(f"Pipe error: {exc}")
            return cont

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

        # Clear screen (strictly 'clear', not 'cls')
        if line.lower() == "clear":
            self._cmd_clear(output_fn)
            return True

        # Status
        if line.lower() == "status":
            self._cmd_status(output_fn)
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

        # Reset (supports bare 'reset' and 'reset initial')
        if first_lower == "reset":
            self._cmd_reset(tokens[1:], output_fn)
            return True

        # Persistent REPL sessions
        if first_lower == "sessions":
            list_saved_sessions(output_fn)
            return True

        if first_lower == "session":
            self._cmd_session(tokens[1:], output_fn)
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

        # Force immediate OS memory release: `gc` or `free`
        if first_lower in ("gc", "free"):
            _release_memory()
            rss = _get_process_rss_mb()
            if rss is not None:
                output_fn(f"Memory released to operating system. Process RAM: ~{rss:.1f} MB (PID {os.getpid()}).")
            else:
                output_fn(f"Memory released to operating system (PID {os.getpid()}).")
            return True

        # Remove table or checkpoint: `rm <table_name>` or `rm checkpoint <name>`
        if first_lower == "rm":
            if len(tokens) < 2:
                output_fn("Usage: rm <table_name> (e.g. rm df1), rm df, or rm *")
                return True
            target = tokens[1]
            if target.lower() == "session":
                if len(tokens) < 3:
                    output_fn("Usage: rm session <name> (or session rm <name>)")
                    return True
                self._cmd_rm_session(tokens[2], output_fn)
                return True

            if target.lower() == "sessions":
                output_fn("pytae: 'rm sessions' is not recognized; use 'rm session <name>'.")
                return True

            if target.lower() == "checkpoints":
                if len(tokens) > 2 and tokens[2] in ("-all", "--all", "all", "-*"):
                    output_fn("pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint *'.")
                elif len(tokens) > 2:
                    output_fn(f"pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint {tokens[2]}'.")
                else:
                    output_fn("pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint'.")
                return True

            if target.lower() == "checkpoint":
                if len(tokens) < 3:
                    output_fn("Usage: rm checkpoint <name> or rm checkpoint *")
                    return True
                cp_name = tokens[2]
                if cp_name == "*":
                    count = self._clear_all_checkpoints()
                    output_fn(f"Cleared all {count} saved checkpoints.")
                    return True
                if cp_name in ("-all", "--all", "all", "-*"):
                    output_fn(f"pytae: 'rm checkpoint {cp_name}' is not recognized; use 'rm checkpoint *'.")
                    return True
                if cp_name in self.checkpoints:
                    self._delete_checkpoint(cp_name)
                    output_fn(f"Removed checkpoint '{cp_name}'.")
                    return True
                avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
                output_fn(f"pytae: checkpoint '{cp_name}' not found. Available: {avail}")
                return True

            if target == "*":
                if not self.tables:
                    output_fn("No tables loaded to remove.")
                    return True
                self.undo_stack.clear()
                self.redo_stack.clear()
                count = len(self.tables)
                self.tables.clear()
                self.orig_tables.clear()
                self.initial_tables.clear()
                self.table_sources.clear()
                self.current_df = None
                self.orig_df = None
                self.initial_df = None
                self.path_str = None
                self.history.append("rm *")
                _release_memory()
                output_fn(f"Removed all {count} loaded tables. No tables remain loaded.")
                return True

            if target in ("-all", "--all", "all", "-*"):
                output_fn(f"pytae: 'rm {target}' is not recognized; use 'rm *'.")
                return True

            resolved = self._resolve_table_name(target)
            if resolved is not None:
                self.undo_stack.clear()
                self.redo_stack.clear()
                del self.tables[resolved]
                if resolved in self.orig_tables:
                    del self.orig_tables[resolved]
                if resolved in self.initial_tables:
                    del self.initial_tables[resolved]
                if resolved in self.table_sources:
                    del self.table_sources[resolved]
                if self.path_str == resolved:
                    if self.tables:
                        next_tbl = next(iter(self.tables.keys()))
                        self.path_str = next_tbl
                        self.current_df = self.tables[next_tbl]
                        self.orig_df = self.orig_tables.get(next_tbl)
                        self.initial_df = self.initial_tables.get(next_tbl)
                        output_fn(f"Removed table '{resolved}'. Switched active dataset to '{next_tbl}'.")
                    else:
                        self.path_str = None
                        self.current_df = None
                        self.orig_df = None
                        self.initial_df = None
                        output_fn(f"Removed table '{resolved}'. No tables remain loaded.")
                else:
                    if self.path_str and self.path_str in self.tables:
                        self.current_df = self.tables[self.path_str]
                        self.orig_df = self.orig_tables.get(self.path_str)
                        self.initial_df = self.initial_tables.get(self.path_str)
                    else:
                        self.path_str = None
                        self.current_df = None
                        self.orig_df = None
                        self.initial_df = None
                    output_fn(f"Removed table '{resolved}'.")
                self.history.append(f"rm {target}")
                _release_memory()
                return True

            if target in self.checkpoints:
                output_fn(f"pytae: '{target}' is a checkpoint, not a table. Use 'rm checkpoint {target}' to remove it.")
                return True

            avail = ", ".join(self.tables.keys()) if self.tables else "none"
            output_fn(f"pytae: table '{target}' not found. Available: {avail}")
            return True

        # Variable Assignment: `df1 = orders.parquet` or `df3 = df1 -filter "..."` or `df3 = -sql ...`
        if "=" in line and not line.startswith("-"):
            left_part, right_part = line.split("=", 1)
            var_name = left_part.strip()
            if var_name.isidentifier() and var_name.lower() not in _BARE_PIPELINE_VERBS:
                self._cmd_assign(var_name, right_part.strip(), output_fn)
                return True

        # Bare table name switches active dataset and shows shape only (Model 2: no table dump)
        resolved_table = self._resolve_table_name(tokens[0])
        is_bare_switch_timed = False
        if resolved_table and len(tokens) >= 2:
            sub = tokens[1:]
            if (
                sub == ["-time"]
                or (len(sub) == 2 and sub[0] == "-time" and sub[1].isdigit())
                or (len(sub) == 1 and sub[0].startswith("-time="))
            ):
                is_bare_switch_timed = True

        if (
            resolved_table
            and (len(tokens) == 1 or is_bare_switch_timed)
            and first_lower
            not in (
                "help",
                "exit",
                "quit",
                "tables",
                "undo",
                "redo",
                "history",
                "stats",
                "diff",
                "head",
                "tail",
                "glimpse",
                "schema",
                "view",
                "save",
                "write",
                "pipe",
                "use",
                "rm",
                "checkpoint",
                "restore",
                "checkpoints",
                "session",
                "sessions",
                "load",
                "py",
                "status",
                "reset",
                "gc",
                "free",
            )
        ):
            import time as _time

            from pytae.cli import _format_duration_ms, _format_timing_summary

            runs = 1
            if len(tokens) == 3 and tokens[1] == "-time" and tokens[2].isdigit():
                runs = max(1, int(tokens[2]))
            elif len(tokens) == 2 and tokens[1].startswith("-time="):
                try:
                    runs = max(1, int(tokens[1].split("=", 1)[1]))
                except ValueError:
                    runs = 1

            durations = []
            for _ in range(runs):
                t0 = _time.perf_counter()
                self.current_df = self.tables[resolved_table]
                self.orig_df = self.orig_tables.get(resolved_table)
                self.initial_df = self.initial_tables.get(resolved_table)
                self.path_str = resolved_table
                n_rows, n_cols = self.current_df.shape
                durations.append(_time.perf_counter() - t0)

            timing_str = ""
            if is_bare_switch_timed:
                if len(durations) == 1:
                    timing_str = f" | Elapsed: {_format_duration_ms(durations[0])}"
                else:
                    timing_str = f" | {_format_timing_summary(durations)}"
            output_fn(f"{resolved_table}: {n_rows:,} rows x {n_cols} cols{timing_str}")
            return True

        # Targeted table command (e.g. `df1 -filter ...` or `df -cols` or `penguins head 5`)
        if (
            resolved_table
            and len(tokens) > 1
            and first_lower
            not in (
                "use",
                "rm",
                "checkpoint",
                "restore",
                "session",
                "sessions",
                "reset",
                "save",
                "write",
                "pipe",
                "load",
                "py",
            )
        ):
            self._cmd_targeted_pipeline(resolved_table, line[len(tokens[0]) :].strip(), output_fn)
            return True

        # Bare checkpoint name hint
        if first_lower in self.checkpoints and len(tokens) == 1:
            output_fn(
                f"pytae: '{first_lower}' is a saved checkpoint. Use 'restore {first_lower}' to activate it, or 'checkpoints' to list all."
            )
            return True

        if first_lower == "checkpoint":
            if len(tokens) < 2:
                output_fn(
                    "Usage: checkpoint <name> (e.g. checkpoint baseline), checkpoint rm <name>, or checkpoint rm *"
                )
                return True
            if tokens[1].lower() == "rm":
                if len(tokens) < 3:
                    output_fn("Usage: checkpoint rm <name> or checkpoint rm *")
                    return True
                cp_name = tokens[2]
                if cp_name == "*":
                    count = self._clear_all_checkpoints()
                    output_fn(f"Cleared all {count} saved checkpoints.")
                    return True
                if cp_name in ("-all", "--all", "all", "-*"):
                    output_fn(f"pytae: 'checkpoint rm {cp_name}' is not recognized; use 'checkpoint rm *'.")
                    return True
                if cp_name in self.checkpoints:
                    self._delete_checkpoint(cp_name)
                    output_fn(f"Removed checkpoint '{cp_name}'.")
                    return True
                avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
                output_fn(f"pytae: checkpoint '{cp_name}' not found. Available: {avail}")
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
        has_time = any(t == "-time" or t.startswith("-time=") for t in tokens)
        if not has_time and self._try_fast_inspection(self.current_df, tokens, output_fn):
            return True

        # Otherwise, process as a pytae pipeline command
        self._cmd_pipeline(line, tokens, output_fn)
        return True

    def _try_fast_inspection(
        self,
        df: pl.DataFrame | None,
        tokens: list[str],
        output_fn: Callable[[str], None],
        *,
        allow_sample: bool = False,
    ) -> bool:
        """Handle fast single-flag inspection commands on `df`. Returns True if handled."""
        if not tokens:
            return False
        first_lower = tokens[0].lower()
        is_inspect = (
            first_lower in ("-shape", "-glimpse", "-describe", "-head", "-tail")
            or first_lower == "-cols"
            or first_lower.startswith("-cols=")
            or first_lower == "-dtype"
            or first_lower.startswith("-dtype=")
            or first_lower == "-nulls"
            or first_lower.startswith("-nulls=")
            or (allow_sample and first_lower == "-sample")
        )
        if not is_inspect:
            return False
        if df is None:
            output_fn("No dataset loaded.")
            return True
        if first_lower == "-shape":
            output_fn(f"({df.shape[0]}, {df.shape[1]})")
        elif first_lower == "-cols" or first_lower.startswith("-cols="):
            order = "file"
            if "=" in first_lower:
                order = first_lower.split("=", 1)[1].strip("\"'").lower()
            elif len(tokens) > 1:
                order = tokens[1].lower()
            cols = list(df.columns)
            if order == "asc":
                cols = sorted(cols, key=lambda s: (s.lower(), s))
            elif order == "desc":
                cols = sorted(cols, key=lambda s: (s.lower(), s), reverse=True)
            elif order != "file":
                cols = [c for c in cols if order in c.lower()]
            output_fn("\n".join(cols))
        elif first_lower == "-dtype" or first_lower.startswith("-dtype="):
            order = "file"
            if "=" in first_lower:
                order = first_lower.split("=", 1)[1].strip("\"'").lower()
            elif len(tokens) > 1:
                order = tokens[1].lower()
            dtypes = DataFrameReader(df).dtypes()
            if order == "asc":
                dtypes = dtypes.sort_index(ascending=True)
            elif order == "desc":
                dtypes = dtypes.sort_index(ascending=False)
            output_fn(dtypes.to_string())
        elif first_lower == "-nulls" or first_lower.startswith("-nulls="):
            order = "file"
            if "=" in first_lower:
                order = first_lower.split("=", 1)[1].strip("\"'").lower()
            elif len(tokens) > 1:
                order = tokens[1].lower()
            nulls_s = df.null_count().to_pandas().iloc[0]
            if order == "asc":
                nulls_s = nulls_s.sort_index(ascending=True)
            elif order == "desc":
                nulls_s = nulls_s.sort_index(ascending=False)
            output_fn(nulls_s.to_string())
        elif first_lower == "-glimpse":
            from pytae.other_utilities import format_glimpse

            output_fn(format_glimpse(df))
        elif first_lower == "-describe":
            output_fn(_format_table(df.describe()))
        elif first_lower == "-head":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            output_fn(_format_table(df.head(n), tbl_rows=max(n, 10)))
        elif first_lower == "-tail":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            output_fn(_format_table(df.tail(n), tbl_rows=max(n, 10)))
        elif first_lower == "-sample":
            n = 5
            frac = None
            if len(tokens) > 1:
                val = tokens[1]
                if "." in val:
                    try:
                        frac = float(val)
                    except ValueError:
                        pass
                elif val.isdigit():
                    n = int(val)
            if frac is not None:
                sampled = df.sample(fraction=frac)
            else:
                sample_n = min(n, len(df))
                sampled = df.sample(n=sample_n) if sample_n > 0 else df.head(0)
            output_fn(_format_table(sampled, tbl_rows=max(len(sampled), 10)))
        return True

    def clear(self, output_fn: Callable[[str], None] = print) -> None:
        """Clear the terminal screen."""
        self._cmd_clear(output_fn)

    def _cmd_clear(self, output_fn: Callable[[str], None] = print) -> None:
        """Clear the terminal screen."""
        import os

        if output_fn is print:
            try:
                os.system("cls" if os.name == "nt" else "clear")
            except Exception:
                sys.stdout.write("\033[H\033[2J")
                sys.stdout.flush()
        else:
            output_fn("\033[H\033[2J")

    def _cmd_status(self, output_fn: Callable[[str], None]) -> None:
        rss = _get_process_rss_mb()
        rss_str = f"~{rss:.1f} MB (PID {os.getpid()})" if rss is not None else f"PID {os.getpid()}"
        if self.current_df is None:
            output_fn("No dataset loaded. Use '<var> = <path.parquet>' to load a table.")
            output_fn(f"Process RAM   : {rss_str}")
            if self.checkpoints:
                output_fn(f"Checkpoints   : {len(self.checkpoints)} saved ({', '.join(self.checkpoints.keys())})")
            return
        n_rows, n_cols = self.current_df.shape
        mem_mb = self.current_df.estimated_size() / (1024 * 1024)
        output_fn(f"Active dataset: {self.path_str or '<memory>'}")
        output_fn(f"Shape         : {n_rows:,} rows x {n_cols} columns")
        output_fn(f"Active table  : ~{mem_mb:.2f} MB")
        output_fn(f"Process RAM   : {rss_str}")
        output_fn(f"Undo steps    : {len(self.undo_stack)} available")
        output_fn(f"Checkpoints   : {len(self.checkpoints)} saved")
        output_fn(f"Columns ({n_cols}): {', '.join(self.current_df.columns[:10])}{'...' if n_cols > 10 else ''}")

    def _cmd_reset(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        if not args:
            # Bare 'reset': Reverts all tables to latest checkpoint if any exist; otherwise reverts to initial file read
            if self.checkpoints:
                latest_cp = list(self.checkpoints.keys())[-1]
                self._cmd_restore(latest_cp, output_fn, record_history=False)
                self.history.append(f"reset [reverted to checkpoint: {latest_cp}]")
                output_fn(f"Reset to latest checkpoint '{latest_cp}'.")
                if self.session_name:
                    self._save_session_metadata()
                return

            self._reset_to_initial(output_fn, is_explicit_initial=False)
            return

        is_explicit_initial = any(a.lower() == "initial" for a in args)
        target_args = [a for a in args if a.lower() != "initial"]

        if not target_args:
            # `reset initial`: resets all tables strictly to initial file read
            self._reset_to_initial(output_fn, is_explicit_initial=True)
            return

        if len(target_args) > 1:
            output_fn("Usage: reset [table_name] [initial]")
            return

        target_name = target_args[0]
        resolved = self._resolve_table_name(target_name)
        if resolved is None:
            if target_name in self.initial_tables or target_name in self.orig_tables:
                resolved = target_name
            else:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(f"pytae: table '{target_name}' not found. Available: {avail}")
                return

        self._reset_single_table(resolved, output_fn, is_explicit_initial=is_explicit_initial)

    def _reset_single_table(
        self, table_name: str, output_fn: Callable[[str], None], is_explicit_initial: bool = False
    ) -> None:
        """Reset a single table to its checkpoint state or initial file read without touching any other tables."""
        # 1. If not explicit initial and checkpoints exist, revert to state in latest checkpoint
        if not is_explicit_initial and self.checkpoints:
            latest_cp = list(self.checkpoints.keys())[-1]
            cp_df = self._get_checkpoint_table_df(latest_cp, table_name)
            if cp_df is not None:
                self.tables[table_name] = cp_df
                if self.path_str == table_name or self.current_df is None:
                    self.path_str = table_name
                    self.current_df = cp_df
                    self.orig_df = cp_df
                self.undo_stack.clear()
                self.redo_stack.clear()
                self.history.append(f"reset {table_name} [reverted to checkpoint: {latest_cp}]")
                if self.session_name:
                    self._save_session_metadata()
                _release_memory()
                output_fn(f"Reset table '{table_name}' to latest checkpoint '{latest_cp}'.")
                return

        # 2. Revert strictly to initial/original file read state
        orig_df = self.initial_tables.get(table_name)
        if orig_df is None:
            orig_df = self.orig_tables.get(table_name)

        if orig_df is None:
            output_fn(f"pytae: no original state found for table '{table_name}'.")
            return

        restored_df = orig_df.clone() if hasattr(orig_df, "clone") else orig_df
        self.tables[table_name] = restored_df
        if table_name in self.orig_tables:
            self.orig_tables[table_name] = restored_df
        if table_name in self.initial_tables:
            self.initial_tables[table_name] = restored_df

        if self.path_str == table_name or self.current_df is None:
            self.path_str = table_name
            self.current_df = restored_df
            self.orig_df = restored_df
            self.initial_df = restored_df

        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history.append(f"reset {table_name} [reverted to initial read]")
        if self.session_name:
            self._save_session_metadata()
        _release_memory()
        output_fn(
            f"Reset table '{table_name}' to initial state ({restored_df.shape[0]:,} rows x {restored_df.shape[1]} cols)."
        )

    def _reset_to_initial(self, output_fn: Callable[[str], None], is_explicit_initial: bool = False) -> None:
        source_tables = self.initial_tables if self.initial_tables else self.orig_tables
        source_df = self.initial_df if self.initial_df is not None else self.orig_df
        if not source_tables and source_df is None:
            output_fn("pytae: no original dataset loaded to reset.")
            return

        # Purge post-read tables and restore original state
        if source_tables:
            current_keys = list(self.tables.keys())
            for k in current_keys:
                if k not in source_tables:
                    del self.tables[k]
                    if k in self.table_sources:
                        del self.table_sources[k]
            for k, orig_df in source_tables.items():
                self.tables[k] = orig_df
                self.orig_tables[k] = orig_df
                self.initial_tables[k] = orig_df

            if self.path_str and self.path_str in self.tables:
                self.current_df = self.tables[self.path_str]
                self.orig_df = self.current_df
                self.initial_df = self.current_df
            elif self.tables:
                first_k = next(iter(self.tables.keys()))
                self.path_str = first_k
                self.current_df = self.tables[first_k]
                self.orig_df = self.current_df
                self.initial_df = self.current_df
        elif source_df is not None:
            self.current_df = source_df
            self.orig_df = source_df
            self.initial_df = source_df
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = self.current_df

        self.undo_stack.clear()
        self.redo_stack.clear()
        _release_memory()

        if is_explicit_initial:
            self.history.append("reset initial [reverted to initial read]")
            desc = "initial dataset"
        else:
            self.history.append("reset [reverted to initial read]")
            desc = "initial dataset (no checkpoints exist)"

        if self.session_name:
            self._save_session_metadata()

        if self.current_df is not None:
            output_fn(f"Restored {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")
        else:
            output_fn(f"Restored {desc}.")

    def _push_undo(self, desc: str, snapshot: Any) -> None:
        """Push an entry onto undo_stack, enforcing MAX_UNDO_STEPS sliding window."""
        self.undo_stack.append((desc, snapshot))
        while len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)

    def _push_redo(self, desc: str, snapshot: Any) -> None:
        """Push an entry onto redo_stack, enforcing MAX_UNDO_STEPS sliding window."""
        self.redo_stack.append((desc, snapshot))
        while len(self.redo_stack) > self.max_undo_steps:
            self.redo_stack.pop(0)

    def _cmd_undo(self, output_fn: Callable[[str], None]) -> None:
        if not self.undo_stack:
            output_fn("Nothing to undo.")
            return
        desc, prev_state = self.undo_stack.pop()
        self._push_redo(desc, self._capture_session_state())
        self._apply_session_state(prev_state)
        self.history.append(f"undo [{desc}]")
        if self.current_df is not None:
            output_fn(f"Undid: {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")
        else:
            output_fn(f"Undid: {desc}.")

    def _cmd_redo(self, output_fn: Callable[[str], None]) -> None:
        if not self.redo_stack:
            output_fn("Nothing to redo.")
            return
        desc, next_state = self.redo_stack.pop()
        self._push_undo(desc, self._capture_session_state())
        self._apply_session_state(next_state)
        self.history.append(f"redo [{desc}]")
        if self.current_df is not None:
            output_fn(f"Redid: {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")
        else:
            output_fn(f"Redid: {desc}.")

    def _cmd_history(self, output_fn: Callable[[str], None]) -> None:
        if not self.history:
            output_fn("No transformations recorded in this session.")
            return
        output_fn("Pipeline History:")
        step_num = 1
        for entry in self.history:
            if entry.startswith("*checkpoint:") and entry.endswith("*"):
                output_fn(f"  {entry}")
            else:
                output_fn(f"  {step_num:2d}: {entry}")
                step_num += 1

    def _capture_session_state(self) -> dict[str, Any]:
        return {
            "tables": {k: v.clone() for k, v in self.tables.items()},
            "orig_tables": {k: v.clone() for k, v in self.orig_tables.items()},
            "initial_tables": {k: v.clone() for k, v in self.initial_tables.items()},
            "table_sources": dict(self.table_sources),
            "active_table": self.path_str,
            "current_df": self.current_df.clone() if self.current_df is not None else None,
        }

    def _apply_session_state(self, state: Any) -> None:
        if isinstance(state, pl.DataFrame):
            self.current_df = state
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = state
            return
        if isinstance(state, dict):
            self.tables = {k: v.clone() for k, v in state.get("tables", {}).items()}
            self.orig_tables = {k: v.clone() for k, v in state.get("orig_tables", {}).items()}
            self.initial_tables = {k: v.clone() for k, v in state.get("initial_tables", {}).items()}
            self.table_sources = dict(state.get("table_sources", {}))
            self.path_str = state.get("active_table")
            if self.path_str and self.path_str in self.tables:
                self.current_df = self.tables[self.path_str]
                self.orig_df = self.orig_tables.get(self.path_str)
                self.initial_df = self.initial_tables.get(self.path_str)
            elif state.get("current_df") is not None:
                self.current_df = state["current_df"].clone()
                self.orig_df = self.current_df
                self.initial_df = self.current_df
            else:
                self.current_df = None
                self.orig_df = None
                self.initial_df = None

    def _cmd_checkpoint(self, name: str, output_fn: Callable[[str], None]) -> None:
        if not self.tables and self.current_df is None:
            output_fn("pytae: no dataset loaded to checkpoint.")
            return

        # Prepare checkpoint directory on disk
        cp_path = self._get_cp_dir() / name
        if cp_path.exists():
            shutil.rmtree(cp_path, ignore_errors=True)
        cp_path.mkdir(parents=True, exist_ok=True)

        saved_tables: dict[str, Any] = {}
        if self.tables:
            for tbl_name, tbl_df in self.tables.items():
                ipc_file = _safe_ipc_filename(tbl_name)
                tbl_df.write_ipc(cp_path / ipc_file)
                saved_tables[tbl_name] = {
                    "file": ipc_file,
                    "shape": list(tbl_df.shape),
                }
        elif self.current_df is not None:
            ipc_file = "_current_df.ipc"
            self.current_df.write_ipc(cp_path / ipc_file)
            saved_tables["_current_df"] = {
                "file": ipc_file,
                "shape": list(self.current_df.shape),
            }

        meta = {
            "dir": str(cp_path),
            "tables": saved_tables,
            "table_sources": dict(self.table_sources),
            "active_table": self.path_str,
            "has_current_df": self.current_df is not None,
            "current_df_shape": list(self.current_df.shape) if self.current_df is not None else None,
        }
        (cp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        self.checkpoints[name] = meta

        # Record checkpoint banner in history
        self.history.append(f"*checkpoint: {name}*")
        if self.session_name:
            self._save_session_metadata()

        # Reset undo and redo stacks upon creating a checkpoint to establish new baseline and free intermediate memory
        self.undo_stack.clear()
        self.redo_stack.clear()
        _release_memory()

        if len(self.tables) > 1:
            table_names = ", ".join(self.tables.keys())
            output_fn(f"Saved checkpoint '{name}' ({len(self.tables)} tables: {table_names}).")
        elif self.current_df is not None:
            output_fn(
                f"Saved checkpoint '{name}' ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)."
            )
        else:
            output_fn(f"Saved checkpoint '{name}'.")

    def _cmd_restore(self, name: str, output_fn: Callable[[str], None], record_history: bool = True) -> None:
        if name not in self.checkpoints:
            avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
            output_fn(f"pytae: checkpoint '{name}' not found. Available checkpoints: {avail}")
            return

        snap = self.checkpoints[name]

        # Purge active session tables to guarantee RAM strictly reflects checkpoint
        self.tables.clear()
        self.orig_tables.clear()
        self.table_sources.clear()
        self.current_df = None
        self.orig_df = None
        self.path_str = None

        if isinstance(snap, dict) and "dir" in snap:
            cp_dir = Path(snap["dir"])
            meta_file = cp_dir / "meta.json"
            meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else snap

            self.table_sources = dict(meta.get("table_sources", {}))
            self.path_str = meta.get("active_table")

            tbl_meta = meta.get("tables", {})
            for tbl_name, tbl_info in tbl_meta.items():
                if tbl_name == "_current_df":
                    ipc_path = cp_dir / tbl_info.get("file", "_current_df.ipc")
                    if ipc_path.exists():
                        self.current_df = pl.read_ipc(ipc_path)
                        self.orig_df = self.current_df
                        if self.initial_df is None:
                            self.initial_df = self.current_df
                    continue
                ipc_path = cp_dir / tbl_info.get("file", _safe_ipc_filename(tbl_name))
                if ipc_path.exists():
                    df = pl.read_ipc(ipc_path)
                    self.tables[tbl_name] = df
                    self.orig_tables[tbl_name] = df
                    if tbl_name not in self.initial_tables:
                        self.initial_tables[tbl_name] = df

            if self.path_str and self.path_str in self.tables:
                self.current_df = self.tables[self.path_str]
                self.orig_df = self.orig_tables[self.path_str]
                self.initial_df = self.initial_tables.get(self.path_str)
            elif self.tables:
                first_tbl = next(iter(self.tables.keys()))
                self.path_str = first_tbl
                self.current_df = self.tables[first_tbl]
                self.orig_df = self.orig_tables[first_tbl]
                self.initial_df = self.initial_tables.get(first_tbl)
        else:
            self._apply_session_state(snap)

        # Reset undo and redo stacks upon restore to anchor session strictly at the restored milestone
        self.undo_stack.clear()
        self.redo_stack.clear()
        if record_history:
            self.history.append(f"restore {name}")
        if self.session_name:
            self._save_session_metadata()

        # Explicitly release any memory held by pre-restore intermediate tables
        _release_memory()

        if len(self.tables) > 1:
            active_info = f"; active: {self.path_str}" if self.path_str else ""
            output_fn(
                f"Restored checkpoint '{name}' ({len(self.tables)} tables: {', '.join(self.tables.keys())}{active_info})."
            )
        elif self.current_df is not None:
            output_fn(
                f"Restored checkpoint '{name}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
            )
        else:
            output_fn(f"Restored checkpoint '{name}'.")

    def _cmd_list_checkpoints(self, output_fn: Callable[[str], None]) -> None:
        if not self.checkpoints:
            output_fn("No checkpoints saved. Use 'checkpoint <name>' to save one.")
            return
        output_fn("Saved Checkpoints:")
        for name, snap in self.checkpoints.items():
            if isinstance(snap, dict):
                tbls = snap.get("tables", {})
                if isinstance(tbls, dict):
                    if len(tbls) > 1:
                        parts = []
                        for t, val in tbls.items():
                            if isinstance(val, dict) and "shape" in val:
                                s = val["shape"]
                                parts.append(f"{t} ({s[0]:,}x{s[1]})")
                            elif isinstance(val, pl.DataFrame):
                                parts.append(f"{t} ({val.shape[0]:,}x{val.shape[1]})")
                            else:
                                parts.append(str(t))
                        summary = ", ".join(parts)
                        active_suffix = f" [active: {snap['active_table']}]" if snap.get("active_table") else ""
                        output_fn(f"  - {name:<15}: {summary}{active_suffix}")
                    elif tbls:
                        t_name, val = next(iter(tbls.items()))
                        shape = (
                            val["shape"] if isinstance(val, dict) and "shape" in val else getattr(val, "shape", None)
                        )
                        if shape:
                            output_fn(f"  - {name:<15}: {shape[0]:,} rows x {shape[1]} cols")
                        else:
                            output_fn(f"  - {name:<15}: 1 table ({t_name})")
                    elif snap.get("current_df_shape") is not None:
                        s = snap["current_df_shape"]
                        output_fn(f"  - {name:<15}: {s[0]:,} rows x {s[1]} cols")
                    elif snap.get("current_df") is not None:
                        df = snap["current_df"]
                        output_fn(f"  - {name:<15}: {df.shape[0]:,} rows x {df.shape[1]} cols")
                    else:
                        output_fn(f"  - {name:<15}: (empty session)")
            elif isinstance(snap, pl.DataFrame):
                output_fn(f"  - {name:<15}: {snap.shape[0]:,} rows x {snap.shape[1]} cols")

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
        resolved = self._resolve_table_name(name)
        if resolved is None:
            avail = ", ".join(self.tables.keys()) if self.tables else "none"
            output_fn(f"pytae: table '{name}' not found. Available tables: {avail}")
            return
        self.current_df = self.tables[resolved]
        self.orig_df = self.orig_tables.get(resolved)
        self.initial_df = self.initial_tables.get(resolved)
        self.path_str = resolved
        output_fn(
            f"Switched active dataset to '{resolved}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
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
                for cp_name in self.checkpoints:
                    if cp_name not in self.tables:
                        cp_df = self._get_checkpoint_df(cp_name)
                        if cp_df is not None:
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

        # 2. File path assignment: `df1 = orders.parquet` or `df1 = data.csv -encoding latin1 -dlim ";"`
        right_tokens = shlex.split(right_expr)
        cleaned_tokens, reader_kwargs, nrows_val = _parse_reader_options(right_tokens)
        if cleaned_tokens:
            clean_path = cleaned_tokens[0].removeprefix("load ").strip("\"' ")
            is_known_table = self._resolve_table_name(clean_path) is not None or clean_path in self.checkpoints
            if not is_known_table:
                p = Path(clean_path).expanduser()
                is_sample = clean_path.startswith("sample:")
                from pytae import DATA_PATH

                is_file = p.exists() and not p.is_dir()
                is_data_cand = (DATA_PATH / p.name).exists() or (DATA_PATH / f"{p.stem}.parquet").exists()
                if is_sample or is_file or is_data_cand:
                    try:
                        load_opts = dict(reader_kwargs)
                        if nrows_val is not None:
                            load_opts["nrows"] = nrows_val
                        p, df = self._read_file_to_df(clean_path, **load_opts)
                        self.tables[var_name] = df
                        self.orig_tables[var_name] = df
                        if var_name not in self.initial_tables:
                            self.initial_tables[var_name] = df
                        self.initial_df = df
                        self.table_sources[var_name] = p.name
                        self.current_df = df
                        self.orig_df = df
                        self.path_str = var_name
                        self.history.append(f"{var_name} = {right_expr}")
                        opts_desc = ""
                        if reader_kwargs or nrows_val is not None:
                            opts_items = [f"{k}={v}" for k, v in reader_kwargs.items()]
                            if nrows_val is not None:
                                opts_items.append(f"nrows={nrows_val}")
                            opts_desc = f" [{', '.join(opts_items)}]"
                        output_fn(
                            f"Loaded {p.name} as '{var_name}' ({df.shape[0]:,} rows x {df.shape[1]} cols){opts_desc}."
                        )
                        return
                    except FileNotFoundError as exc:
                        output_fn(f"pytae: {exc}")
                        return
                    except Exception as exc:
                        output_fn(f"pytae: failed to load {clean_path}: {exc}")
                        return

        # 3. Pipeline / Table assignment: `df3 = df1 -filter ...` or `df3 = -filter ...` or `df3 = df1`
        if right_tokens:
            first_tok = right_tokens[0]
            first_lower = first_tok.lower()
            if first_lower in _BARE_PIPELINE_VERBS:
                output_fn(f"pytae: bare '{first_tok}' is not recognized; use '-{first_tok}' (matching CLI syntax).")
                return

            source_df: pl.DataFrame | None = None
            source_label = ""
            pipe_tokens: list[str] = []
            pipe_line = ""

            if first_tok.startswith("-"):
                if self.current_df is None:
                    output_fn("pytae: no active dataset loaded to apply pipeline.")
                    return
                source_df = self.current_df
                source_label = self.path_str or "active"
                pipe_tokens = right_tokens
                pipe_line = right_expr
            else:
                resolved_src = self._resolve_table_name(first_tok)
                if resolved_src is not None or first_tok in self.checkpoints:
                    if resolved_src is not None:
                        source_df = self.tables[resolved_src]
                    else:
                        source_df = self._get_checkpoint_df(first_tok)
                        if source_df is None:
                            output_fn(
                                f"pytae: checkpoint '{first_tok}' contains multiple tables. Use 'restore {first_tok}' to restore entire workbench."
                            )
                            return
                    source_label = first_tok
                    pipe_tokens = right_tokens[1:]
                    pipe_line = right_expr[len(first_tok) :].strip()
                    if not pipe_tokens:
                        self.tables[var_name] = source_df.clone()
                        self.table_sources[var_name] = f"copy of {first_tok}"
                        self.current_df = self.tables[var_name]
                        self.path_str = var_name
                        output_fn(
                            f"Assigned '{var_name}' from '{first_tok}' ({source_df.shape[0]:,} rows x {source_df.shape[1]} cols)."
                        )
                        return

            if source_df is not None:
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
                if first_pipe == "-join":
                    self.current_df = source_df.clone()
                    self._cmd_join(pipe_tokens[1:], output_fn)
                    res_df = self.current_df
                    durations = None
                else:
                    res_df, durations = self._eval_pipeline_df(source_df, pipe_tokens, output_fn)
                    if res_df is None:
                        return
                was_existing = var_name in self.tables
                self._push_undo(f"{var_name} = {right_expr}", self._capture_session_state())
                self.tables[var_name] = res_df
                self.table_sources[var_name] = f"{source_label} {pipe_line[:20]}"
                self.current_df = res_df
                self.path_str = var_name
                self.history.append(f"{var_name} = {right_expr}")
                action = "Updated" if was_existing else "Created"
                timing_str = ""
                if durations:
                    from pytae.cli import _format_duration_ms, _format_timing_summary

                    if len(durations) == 1:
                        timing_str = f" | Elapsed: {_format_duration_ms(durations[0])}"
                    else:
                        timing_str = f" | {_format_timing_summary(durations)}"
                output_fn(f"{action} '{var_name}' ({res_df.shape[0]:,} rows x {res_df.shape[1]} cols){timing_str}.")
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

        has_time = any(t == "-time" or t.startswith("-time=") for t in sub_tokens)
        if has_time:
            self._cmd_pipeline(sub_line, sub_tokens, output_fn)
            self.current_df = old_active
            self.path_str = old_path
            return

        if first_sub in _BARE_PIPELINE_VERBS:
            output_fn(f"pytae: bare '{first_sub}' is not recognized; use '-{first_sub}' (matching CLI syntax).")
        elif self._try_fast_inspection(target_df, sub_tokens, output_fn, allow_sample=True):
            pass
        elif first_sub == "-o":
            dest = sub_tokens[1] if len(sub_tokens) > 1 else "output.parquet"
            self._cmd_save(dest, output_fn)
        elif first_sub.startswith(("-output", "--output")):
            output_fn("pytae: '-output' is not recognized; use '-o <path>'.")
        elif first_sub == "-join":
            self._cmd_join(sub_tokens[1:], output_fn)
        elif first_sub == "-sql":
            raw_query = sub_line[4:].strip()
            query = raw_query.strip("\"'")
            self._cmd_sql(query, output_fn)
        else:
            self._cmd_pipeline(sub_line, sub_tokens, output_fn)

        self.current_df = old_active
        self.path_str = old_path

    def _cmd_load(self, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        cleaned_tokens, reader_kwargs, nrows_val = _parse_reader_options(tokens)
        if len(cleaned_tokens) < 2:
            output_fn("Usage: load <path> [as <alias>] [-encoding <enc>] [-dlim <char>] [-nrows <N>]")
            return
        path_str = cleaned_tokens[1].strip("\"' ")
        alias: str | None = None
        if len(cleaned_tokens) >= 4 and cleaned_tokens[2].lower() == "as":
            alias = cleaned_tokens[3]

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
            reader = get_reader(p, **reader_kwargs)
            loaded_df = reader.to_polars(nrows=nrows_val)
            self.undo_stack.clear()
            self.redo_stack.clear()
            target_alias = alias or self.path_str or p.stem or p.name
            self.tables[target_alias] = loaded_df
            self.orig_tables[target_alias] = loaded_df
            if target_alias not in self.initial_tables:
                self.initial_tables[target_alias] = loaded_df
            self.initial_df = loaded_df
            self.table_sources[target_alias] = p.name
            self.current_df = loaded_df
            self.orig_df = loaded_df
            self.path_str = target_alias
            opts_desc = ""
            if reader_kwargs or nrows_val is not None:
                opts_items = [f"{k}={v}" for k, v in reader_kwargs.items()]
                if nrows_val is not None:
                    opts_items.append(f"nrows={nrows_val}")
                opts_desc = f" [{', '.join(opts_items)}]"
            if alias:
                self.history.append(f"load {p.name} as {alias}")
                output_fn(
                    f"Loaded {p.name} as '{alias}' ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols){opts_desc}."
                )
            else:
                self.history.append(f"load {p.name}")
                output_fn(
                    f"Loaded {p.name} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols){opts_desc}."
                )
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
            left_res = self._resolve_table_name(left_name)
            if left_res is not None:
                left_df = self.tables[left_res]
                left_name = left_res
            elif left_name in self.checkpoints:
                left_df = self._get_checkpoint_df(left_name)
                if left_df is None:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: could not load left table from checkpoint '{left_name}'. Available: {avail}")
                    return
            else:
                try:
                    lp, left_df = self._read_file_to_df(left_name)
                except Exception:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: left table '{left_name}' not found. Available: {avail}")
                    return
        else:
            left_df = self.current_df
            left_name = self.path_str or "active"

        # 4. Resolve right table
        right_res = self._resolve_table_name(right_name)
        if right_res is not None:
            right_df = self.tables[right_res]
            right_name = right_res
        elif right_name in self.checkpoints:
            right_df = self._get_checkpoint_df(right_name)
            if right_df is None:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(f"pytae: could not load right table from checkpoint '{right_name}'. Available: {avail}")
                return
        else:
            try:
                rp, right_df = self._read_file_to_df(right_name)
            except Exception:
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
            self._push_undo(f"-join {right_name} on={on_key} (how={how})", self.current_df.clone())
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
            for cp_name in self.checkpoints:
                if cp_name not in self.tables:
                    cp_df = self._get_checkpoint_df(cp_name)
                    if cp_df is not None:
                        ctx.register(cp_name, cp_df)
            res = ctx.execute(query).collect()
            output_fn(f"-> {self.path_str or 'df'}: {res.shape[0]:,} rows x {res.shape[1]} cols")
            # Update state with SQL query result
            self._push_undo(f'-sql "{query[:40]}..."', self.current_df.clone())
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
            for cp_name in self.checkpoints:
                if cp_name not in local_scope:
                    cp_df = self._get_checkpoint_df(cp_name)
                    if cp_df is not None:
                        local_scope[cp_name] = PytaeDataFrame(cp_df)
            res = eval(expr, {}, local_scope)
            if isinstance(res, (pl.DataFrame, PytaeDataFrame)):
                output_fn(_format_table(res))
            else:
                output_fn(repr(res))
        except Exception as exc:
            output_fn(f"pytae Python Error: {exc}")

    def _eval_pipeline_df(
        self,
        source_df: pl.DataFrame,
        tokens: list[str],
        output_fn: Callable[[str], None] = print,
    ) -> tuple[pl.DataFrame | None, list[float] | None]:
        """Evaluate a pipeline on source_df without printing, returning (resulting_df, durations)."""
        from pytae.cli import (
            _normalize_cli_args,
            build_parser,
            parse_concat_arg,
            parse_filter,
            parse_join_arg,
            parse_rename,
            parse_select_spec,
        )

        exec_argv = _normalize_cli_args(["<memory>"] + tokens)
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
                return None, None
        except (argparse.ArgumentError, SystemExit) as exc:
            output_fn(f"pytae syntax error: {exc}")
            return None, None

        rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
        select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
        filter_specs = [parse_filter(raw) for raw in (args.filter or [])]
        mutate_specs = list(args.mutate or [])
        sql_specs = list(args.sql or [])
        join_specs = [parse_join_arg(raw) for raw in (args.join or [])]
        concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]
        op_order = getattr(args, "op_order", [])

        args._memory_df = source_df
        args.in_repl = True
        args.quiet = True
        args.output_fn = lambda s: None

        has_action = bool(op_order) or any(
            [
                args.shape,
                args.cols,
                args.dtype,
                args.nulls,
                args.describe,
                args.glimpse,
                args.head is not None,
                args.tail is not None,
                args.sample is not None,
                args.stats,
                getattr(args, "diff", None) is not None,
                getattr(args, "meta", False),
                getattr(args, "plot", None) is not None,
                getattr(args, "hist", None) is not None,
                getattr(args, "bar", None) is not None,
                getattr(args, "scatter", None) is not None,
                getattr(args, "corr", None) is not None,
            ]
        )
        show_all = not has_action

        runs = getattr(args, "time", None)
        durations: list[float] | None = None
        try:
            if runs:
                import time as _time

                durations = []
                for _ in range(runs):
                    t0 = _time.perf_counter()
                    failed = _process_path(
                        Path("<memory>"),
                        args,
                        parser,
                        batch=True,
                        show_all=show_all,
                        select_specs=select_specs,
                        filter_specs=filter_specs,
                        mutate_specs=mutate_specs,
                        sql_specs=sql_specs,
                        rename_specs=rename_specs,
                        join_specs=join_specs,
                        concat_specs=concat_specs,
                    )
                    durations.append(_time.perf_counter() - t0)
                    if failed:
                        break
            else:
                failed = _process_path(
                    Path("<memory>"),
                    args,
                    parser,
                    batch=True,
                    show_all=show_all,
                    select_specs=select_specs,
                    filter_specs=filter_specs,
                    mutate_specs=mutate_specs,
                    sql_specs=sql_specs,
                    rename_specs=rename_specs,
                    join_specs=join_specs,
                    concat_specs=concat_specs,
                )
            if failed:
                return None, None
            res_frame = getattr(args, "_result_frame", None)
            res_pl: pl.DataFrame | None = None
            if res_frame is not None:
                if isinstance(res_frame, pl.LazyFrame):
                    res_pl = res_frame.collect()
                elif isinstance(res_frame, pl.DataFrame):
                    res_pl = res_frame
                else:
                    res_pl = pl.from_pandas(res_frame)
            else:
                res_pl = source_df
            return res_pl, durations
        except Exception as exc:
            output_fn(f"pytae error: {exc}")
            return None, None

    def _cmd_pipeline(self, line: str, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded. Load a dataset first with '<var> = <path.parquet>'.")
            return

        from pytae.cli import (
            _format_timing_summary,
            _normalize_cli_args,
            build_parser,
            parse_concat_arg,
            parse_filter,
            parse_join_arg,
            parse_rename,
            parse_select_spec,
        )

        exec_argv = _normalize_cli_args(["<memory>"] + tokens)
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

        args._memory_df = self.current_df
        args.in_repl = True
        args.output_fn = output_fn

        has_action = bool(op_order) or any(
            [
                args.shape,
                args.cols,
                args.dtype,
                args.nulls,
                args.describe,
                args.glimpse,
                args.head is not None,
                args.tail is not None,
                args.sample is not None,
                args.stats,
                getattr(args, "diff", None) is not None,
                getattr(args, "meta", False),
                getattr(args, "plot", None) is not None,
                getattr(args, "hist", None) is not None,
                getattr(args, "bar", None) is not None,
                getattr(args, "scatter", None) is not None,
                getattr(args, "corr", None) is not None,
            ]
        )
        show_all = not has_action

        runs = getattr(args, "time", None)
        try:
            if runs:
                import time as _time

                durations: list[float] = []
                failed = False
                for run_idx in range(runs):
                    t0 = _time.perf_counter()
                    if run_idx == 0:
                        failed = _process_path(
                            Path("<memory>"),
                            args,
                            parser,
                            batch=True,
                            show_all=show_all,
                            select_specs=select_specs,
                            filter_specs=filter_specs,
                            mutate_specs=mutate_specs,
                            sql_specs=sql_specs,
                            rename_specs=rename_specs,
                            join_specs=join_specs,
                            concat_specs=concat_specs,
                        )
                    else:
                        quiet_args = argparse.Namespace(**vars(args))
                        quiet_args.output_fn = lambda s: None
                        failed = _process_path(
                            Path("<memory>"),
                            quiet_args,
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
                    durations.append(_time.perf_counter() - t0)
                    if failed:
                        break
                if failed:
                    output_fn("pytae: command failed with errors.")
                    return
                output_fn(_format_timing_summary(durations))
            else:
                failed = _process_path(
                    Path("<memory>"),
                    args,
                    parser,
                    batch=True,
                    show_all=show_all,
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

            self.history.append(line)
        except Exception as exc:
            output_fn(f"pytae error: {exc}")

    def run(
        self,
        input_fn: Callable[[str], str] | None = None,
        output_fn: Callable[[str], None] = print,
    ) -> Any:
        """Run the REPL interactive loop until user exits. Returns final active DataFrame."""
        _init_readline()
        output_fn(REPL_BANNER)
        if self.current_df is not None:
            output_fn(
                f"Loaded: {self.path_str or '<dataframe>'} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)"
            )
        else:
            output_fn(
                "No initial dataset loaded. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table."
            )
        if sys.platform == "win32" and not sys.stdin.isatty():
            output_fn(
                "  (Tip: If running in Git Bash on Windows, run 'winpty pytae ...' for interactive arrow key navigation)"
            )
        output_fn("")

        def _get_input(prompt_text: str) -> str:
            if input_fn is not None:
                try:
                    return input_fn(prompt_text)
                except TypeError:
                    return input_fn()  # type: ignore[call-arg]

            if sys.platform == "win32":
                if readline is not None:
                    try:
                        return input(prompt_text)
                    except Exception:
                        pass
                if sys.stdin.isatty():
                    try:
                        return _win_console_input(prompt_text, self._raw_history)
                    except Exception:
                        pass
            return input(prompt_text)

        try:
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

                try:
                    should_continue = self.execute_line(line, output_fn=output_fn)
                    if not should_continue:
                        break
                except KeyboardInterrupt:
                    output_fn("\n(KeyboardInterrupt - command cancelled)")
                except Exception as exc:
                    output_fn(f"pytae error: {exc}")
        finally:
            _save_readline_history()
            _save_raw_history(self._raw_history)
            self._cleanup_cp_dir()
            _release_memory()
        return self.current_df


def repl(
    df: Any | None = None,
    path: Path | str | None = None,
    paths: list[Path | str] | None = None,
    prompt: str = "pytae",
    encoding: str | None = None,
    sep: str | None = None,
    delimiter: str | None = None,
    nrows: int | None = None,
    chunk_size: int | None = None,
    reader_kwargs: dict[str, Any] | None = None,
    session: str | None = None,
    **kwargs: Any,
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
    encoding : str, optional
        Text encoding for file reading (e.g. 'latin-1', 'cp1252', 'utf-8').
    sep, delimiter : str, optional
        Column delimiter for delimited text files (e.g. '|', ';', '\t').
    nrows : int, optional
        Maximum number of rows to load initially.
    chunk_size : int, optional
        Chunk size in rows for streaming ingestion.
    reader_kwargs : dict, optional
        Additional keyword arguments to pass to dataset reader.
    session : str, optional
        Persistent session name (saves checkpoints across restarts in ~/.pytae/sessions/<name>).

    Returns
    -------
    DataFrame | None
        The active DataFrame upon exiting the REPL.
    """
    runner = PytaeRepl(
        df=df,
        path=path,
        paths=paths,
        prompt=prompt,
        encoding=encoding,
        sep=sep,
        delimiter=delimiter,
        nrows=nrows,
        chunk_size=chunk_size,
        reader_kwargs=reader_kwargs,
        session=session,
        **kwargs,
    )
    return runner.run()
