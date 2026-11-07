"""Interactive REPL (Read-Eval-Print Loop) for pytae with in-memory state.

Provides stateful, iterative data manipulation without repeatedly reloading datasets from disk.
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
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import polars as pl

from pytae.cli_run import _format_bytes, _format_table, _process_path
from pytae.readers import DataFrameReader, get_reader


def _normalize_unquoted_windows_paths(text: str) -> str:
    """Normalize unquoted Windows drive paths with backslashes (e.g. C:\\Users\\... -> C:/Users/...) so shlex does not eat backslashes."""
    return re.sub(
        r'(?<!["\'])\b([a-zA-Z]):\\([^\s"\'=]+)',
        lambda m: f"{m.group(1)}:/{m.group(2).replace(chr(92), '/')}",
        text,
    )


def _resolve_to_canonical_path(path_str: str) -> str:
    """Resolve a file path to its canonical absolute path, converting Windows mapped network drives to UNC and using portable forward slashes."""
    from pytae.cli_parsing import normalize_git_bash_path

    raw = path_str.strip().strip("'\"")
    raw = normalize_git_bash_path(raw)
    if not raw or raw.lower() in ("clip", "clipboard") or raw.startswith("sample:") or raw.startswith("http://") or raw.startswith("https://"):
        return raw

    try:
        p = Path(os.path.expanduser(raw)).resolve()
        if not p.exists():
            from pytae import DATA_PATH

            cand = DATA_PATH / p.name
            if not cand.exists():
                cand = DATA_PATH / f"{p.stem}.parquet"
            if cand.exists():
                p = cand.resolve()
    except Exception:
        return raw

    canon_str = p.as_posix()
    if sys.platform == "win32":
        drive = p.drive  # e.g. "Z:"
        if drive and len(drive) == 2 and drive[1] == ":":
            try:
                import ctypes
                from ctypes import wintypes

                mpr = ctypes.windll.mpr
                buffer = ctypes.create_unicode_buffer(1024)
                buf_len = wintypes.DWORD(1024)
                # WNetGetConnectionW resolves drive letter to UNC path (e.g. \\server\share)
                res = mpr.WNetGetConnectionW(ctypes.c_wchar_p(drive), buffer, ctypes.byref(buf_len))
                if res == 0:  # NO_ERROR
                    unc_remote = buffer.value.rstrip("\\/").replace("\\", "/")
                    sub_path = str(p)[len(drive) :].lstrip("\\/").replace("\\", "/")
                    canon_str = f"{unc_remote}/{sub_path}"
            except Exception:
                pass

    if " " in canon_str and not (canon_str.startswith('"') and canon_str.endswith('"')):
        canon_str = f'"{canon_str}"'

    return canon_str


def _to_relative_path(path_str: str, base_dir: Path | str | None = None) -> str:
    """Convert an absolute file path to a relative POSIX path from base_dir (default: CWD)."""
    clean = path_str.strip().strip("'\"")
    if (
        not clean
        or clean.lower() in ("clip", "clipboard")
        or clean.startswith("sample:")
        or clean.startswith("http://")
        or clean.startswith("https://")
    ):
        return path_str

    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    try:
        target_p = Path(clean).resolve()
        rel = os.path.relpath(target_p, start=base)
        rel_posix = Path(rel).as_posix()
        if " " in rel_posix and not (rel_posix.startswith('"') and rel_posix.endswith('"')):
            return f'"{rel_posix}"'
        return rel_posix
    except Exception:
        return path_str


def _get_frame_columns(df: Any) -> list[str]:
    """Retrieve column names cleanly across pl.DataFrame, pl.LazyFrame, and pd.DataFrame."""
    if hasattr(df, "collect_schema"):
        return list(df.collect_schema().names())
    return list(df.columns)


def _read_checkpoint_file(path: Path) -> pl.DataFrame:
    """Read a checkpoint table file, supporting both .parquet and .ipc."""
    target_p = path
    if not target_p.exists():
        if target_p.suffix == ".ipc":
            alt = target_p.with_suffix(".parquet")
            if alt.exists():
                target_p = alt
        elif target_p.suffix == ".parquet":
            alt = target_p.with_suffix(".ipc")
            if alt.exists():
                target_p = alt
        if not target_p.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {path}")

    if target_p.suffix in (".parquet", ".pq"):
        return pl.read_parquet(target_p)
    return pl.read_ipc(target_p)


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


def _get_pytae_home() -> Path:
    """Return the base Pytae configuration and state directory (default: ~/.pytae)."""
    env_home = os.environ.get("PYTAE_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return Path.home() / ".pytae"


def _get_config_path() -> Path:
    """Return path to persistent REPL configuration file (~/.pytae/config.json)."""
    return _get_pytae_home() / "config.json"


def _get_history_dir(create: bool = True) -> Path:
    """Return directory for session history transcripts (default: ~/.pytae/history)."""
    custom = os.environ.get("PYTAE_HISTORY_DIR")
    if custom:
        d = Path(custom).expanduser().resolve()
    else:
        d = _get_pytae_home() / "history"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def get_code_dir() -> Path:
    """Return directory for session command logs (unified under history directory)."""
    return _get_history_dir()


def get_commands_dir() -> Path:
    """Legacy alias for get_code_dir()."""
    return get_code_dir()


_CONFIGURED_SESSIONS_DIR: Path | None = None


def get_sessions_dir() -> Path:
    """Return the base directory for persistent Pytae sessions (defaults to current working directory)."""
    global _CONFIGURED_SESSIONS_DIR
    if _CONFIGURED_SESSIONS_DIR is not None:
        p = _CONFIGURED_SESSIONS_DIR
    else:
        env_dir = os.environ.get("PYTAE_SESSIONS_DIR")
        if env_dir:
            p = Path(env_dir).expanduser().resolve()
        else:
            p = Path.cwd().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_sessions_dir(path: Path | str | None) -> Path:
    """Configure the base directory for persistent Pytae sessions."""
    global _CONFIGURED_SESSIONS_DIR
    if path is None or str(path).lower() in ("default", "none", "reset", "cwd"):
        _CONFIGURED_SESSIONS_DIR = None
        return get_sessions_dir()
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    _CONFIGURED_SESSIONS_DIR = p
    return p


def _format_friendly_path(p: Path | str) -> str:
    """Format path with ~ for user home directory if applicable."""
    path_obj = Path(p).resolve()
    try:
        home = Path.home().resolve()
        if path_obj == home or home in path_obj.parents:
            rel = path_obj.relative_to(home)
            rel_str = str(rel).replace("\\", "/")
            return "~" if rel_str == "." else f"~/{rel_str}"
    except Exception:
        pass
    return str(path_obj).replace("\\", "/")


def is_session_dir(path: Path | str) -> bool:
    """Check if a path is a valid Pytae session directory via standard session markers.

    Recognized markers:
      - `session.json` metadata manifest
      - `checkpoints` directory
      - `.pytae_session` marker file
    """
    p = Path(path).expanduser().resolve()
    try:
        if not p.is_dir():
            return False
        return (p / "session.json").exists() or (p / "checkpoints").is_dir() or (p / ".pytae_session").exists()
    except (OSError, PermissionError):
        return False


_RETIRED_SESSION_MSG = (
    "pytae: persistent disk sessions have been retired. Use 'checkpoint <name>' for in-memory undo, "
    "'export script <path.py|path.pt>' to save pipelines, or 'pytae <script.pt>' to replay."
)


def list_saved_sessions(
    output_fn: Callable[[str], None] = print,
    *,
    verbose: bool = False,
    ready_only: bool = False,
    pattern: str | None = None,
    directory: Path | str | None = None,
) -> None:
    """Persistent disk sessions have been retired."""
    output_fn(_RETIRED_SESSION_MSG)


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


_HIST_FILE: Path | None = None


def _get_readline_hist_file() -> Path:
    if _HIST_FILE is not None:
        return Path(_HIST_FILE)
    return _get_history_dir() / ".readline_history"


def _load_history_from_file() -> list[str]:
    """Read saved command history lines from disk."""
    hist_file = _get_readline_hist_file()
    if hist_file.exists():
        try:
            return [line.strip() for line in hist_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return []
    return []


def _save_raw_history(history: list[str]) -> None:
    """Save raw command history list to disk (used when readline is unavailable)."""
    try:
        lines = history[-1000:]
        hist_file = _get_readline_hist_file()
        hist_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _win_console_input(
    prompt_text: str,
    history: list[str],
    completer: Callable[[str, int], str | None] | None = None,
    completions_fn: Callable[[str, str, int, int], list[str]] | None = None,
    read_char_fn: Callable[[], str] | None = None,
    has_input_fn: Callable[[], bool] | None = None,
) -> str:
    """Read console input on Windows with arrow key history navigation, line editing, and Tab autocompletion."""
    if read_char_fn is None:
        try:
            import msvcrt

            read_char_fn = msvcrt.getwch
            has_input_fn = getattr(msvcrt, "kbhit", None)
        except ImportError:
            return input(prompt_text)

    sys.stdout.write(prompt_text)
    sys.stdout.flush()

    line_chars: list[str] = []
    cursor_pos = 0
    hist_idx = len(history)
    draft = ""
    prev_c_row = 0
    prev_total_rows = 0

    def calc_pos(prompt: str, chars: list[str], cur_pos: int, width: int) -> tuple[int, int, int, int]:
        clean_prompt = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", prompt)
        full = clean_prompt + "".join(chars)
        target_idx = len(clean_prompt) + cur_pos
        row = 0
        col = 0
        c_row = 0
        c_col = 0
        for i, ch_item in enumerate(full):
            if i == target_idx:
                c_row = row
                c_col = col
            if ch_item == "\n":
                row += 1
                col = 0
            else:
                col += 1
                if col >= width:
                    row += 1
                    col = 0
        if target_idx >= len(full):
            c_row = row
            c_col = col
        return c_row, c_col, row, col

    def render() -> None:
        nonlocal prev_c_row, prev_total_rows
        width = max(20, shutil.get_terminal_size((80, 24)).columns or 80)
        text = "".join(line_chars)
        c_row, c_col, total_rows, _ = calc_pos(prompt_text, line_chars, cursor_pos, width)

        # Move cursor from previous cursor row back to prompt start (Row 0, Col 0)
        if prev_c_row > 0:
            sys.stdout.write(f"\x1b[{prev_c_row}A\r")
        else:
            sys.stdout.write("\r")

        # Write prompt and text
        sys.stdout.write(prompt_text + text)

        # Clear remaining screen if previous text occupied more rows or trailing cols
        if prev_total_rows > total_rows:
            sys.stdout.write("\x1b[J")
        else:
            sys.stdout.write("\x1b[K")

        # Move cursor from bottom (total_rows) up to target row (c_row) and column (c_col)
        row_up = total_rows - c_row
        if row_up > 0:
            sys.stdout.write(f"\x1b[{row_up}A")
        sys.stdout.write(f"\x1b[{c_col + 1}G")
        sys.stdout.flush()

        prev_c_row = c_row
        prev_total_rows = total_rows

    while True:
        try:
            ch = read_char_fn()
        except (KeyboardInterrupt, EOFError):
            raise
        except Exception:
            return "".join(line_chars)

        code: str | None = None
        if ch in ("\x00", "\xe0"):
            try:
                code = read_char_fn()
            except Exception:
                continue
        elif ch == "\x1b":
            # ANSI escape sequence from terminal emulators (e.g. Git Bash, Windows Terminal)
            seq = ""
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
                "[1;5H": "G",
                "[1;3H": "G",
                "[F": "O",
                "OF": "O",
                "[4~": "O",
                "[8~": "O",  # End
                "[1;5F": "O",
                "[1;3F": "O",
                "[3~": "S",  # Delete
                "[1;5D": "word_prev",
                "[1;3D": "word_prev",
                "[5D": "word_prev",
                "[1;5C": "word_next",
                "[1;3C": "word_next",
                "[5C": "word_next",
            }
            try:
                import time

                if has_input_fn is not None:
                    for _ in range(8):
                        if has_input_fn():
                            seq += read_char_fn()
                            if seq in ansi_map:
                                break
                        else:
                            time.sleep(0.002)
                            if has_input_fn():
                                seq += read_char_fn()
                                if seq in ansi_map:
                                    break
                            else:
                                break
                else:
                    for _ in range(8):
                        try:
                            seq += read_char_fn()
                            if seq in ansi_map:
                                break
                        except Exception:
                            break
            except Exception:
                pass

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
                    render()
            elif code == "M":  # Right arrow
                if cursor_pos < len(line_chars):
                    cursor_pos += 1
                    render()
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
            elif code == "word_prev":
                if cursor_pos > 0:
                    delims = " \t\n\"'=(),;[]"
                    while cursor_pos > 0 and line_chars[cursor_pos - 1] in delims:
                        cursor_pos -= 1
                    while cursor_pos > 0 and line_chars[cursor_pos - 1] not in delims:
                        cursor_pos -= 1
                    render()
            elif code == "word_next":
                if cursor_pos < len(line_chars):
                    delims = " \t\n\"'=(),;[]"
                    while cursor_pos < len(line_chars) and line_chars[cursor_pos] not in delims:
                        cursor_pos += 1
                    while cursor_pos < len(line_chars) and line_chars[cursor_pos] in delims:
                        cursor_pos += 1
                    render()
        elif ch in ("\r", "\n"):
            row_down = prev_total_rows - prev_c_row
            if row_down > 0:
                sys.stdout.write(f"\x1b[{row_down}B")
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(line_chars)
        elif ch == "\x01":  # Ctrl+A: beginning of line
            if cursor_pos > 0:
                cursor_pos = 0
                render()
        elif ch == "\x05":  # Ctrl+E: end of line
            if cursor_pos < len(line_chars):
                cursor_pos = len(line_chars)
                render()
        elif ch == "\x17":  # Ctrl+W: delete previous word
            if cursor_pos > 0:
                delims = " \t\n\"'=(),;[]"
                new_pos = cursor_pos
                while new_pos > 0 and line_chars[new_pos - 1] in delims:
                    new_pos -= 1
                while new_pos > 0 and line_chars[new_pos - 1] not in delims:
                    new_pos -= 1
                del line_chars[new_pos:cursor_pos]
                cursor_pos = new_pos
                render()
        elif ch == "\x0b":  # Ctrl+K: kill to end of line
            if cursor_pos < len(line_chars):
                del line_chars[cursor_pos:]
                render()
        elif ch == "\x15":  # Ctrl+U: kill to beginning of line
            if cursor_pos > 0:
                del line_chars[:cursor_pos]
                cursor_pos = 0
                render()
        elif ch in ("\x08", "\x7f"):  # Backspace (0x08 on CMD/conhost, 0x7f on MinTTY/xterm)
            if cursor_pos > 0:
                cursor_pos -= 1
                line_chars.pop(cursor_pos)
                render()
        elif ch == "\x03":  # Ctrl+C
            row_down = prev_total_rows - prev_c_row
            if row_down > 0:
                sys.stdout.write(f"\x1b[{row_down}B")
            sys.stdout.write("\n")
            sys.stdout.flush()
            raise KeyboardInterrupt
        elif ch in ("\x04", "\x1a"):  # Ctrl+D or Ctrl+Z
            row_down = prev_total_rows - prev_c_row
            if row_down > 0:
                sys.stdout.write(f"\x1b[{row_down}B")
            sys.stdout.write("\n")
            sys.stdout.flush()
            if not line_chars:
                raise EOFError
        elif ch == "\t":
            # Tab autocompletion
            delims = " \t\n\"'=(),;[]"
            begidx = cursor_pos
            while begidx > 0 and line_chars[begidx - 1] not in delims:
                begidx -= 1
            endidx = cursor_pos
            word = "".join(line_chars[begidx:endidx])
            line_buf = "".join(line_chars)

            matches: list[str] = []
            if completions_fn is not None:
                try:
                    matches = completions_fn(word, line_buf, begidx, endidx)
                except Exception:
                    matches = []
            elif completer is not None:
                try:
                    state = 0
                    while True:
                        m = completer(word, state)
                        if m is None:
                            break
                        matches.append(m)
                        state += 1
                        if state > 500:
                            break
                except Exception:
                    matches = []

            if not matches:
                continue

            if len(matches) == 1:
                match = matches[0]
                line_chars[begidx:endidx] = list(match)
                cursor_pos = begidx + len(match)
                if not match.endswith(("/", "\\", "=", os.sep)):
                    line_chars.insert(cursor_pos, " ")
                    cursor_pos += 1
                render()
            else:
                common = os.path.commonprefix(matches)
                if len(common) > len(word):
                    line_chars[begidx:endidx] = list(common)
                    cursor_pos = begidx + len(common)
                    render()
                else:
                    sys.stdout.write("\n")
                    col_width = min(40, max(len(m) for m in matches) + 2)
                    term_cols = 80
                    try:
                        term_cols = shutil.get_terminal_size((80, 20)).columns
                    except Exception:
                        pass
                    num_cols = max(1, term_cols // col_width)
                    disp_matches = matches[:40]
                    for i in range(0, len(disp_matches), num_cols):
                        row_items = disp_matches[i : i + num_cols]
                        sys.stdout.write("  " + "".join(m.ljust(col_width) for m in row_items).rstrip() + "\n")
                    if len(matches) > 40:
                        sys.stdout.write(f"  ... and {len(matches) - 40} more\n")
                    prev_c_row = 0
                    prev_total_rows = 0
                    render()
        elif ch >= " ":  # Printable character
            line_chars.insert(cursor_pos, ch)
            cursor_pos += 1
            render()


def _complete_paths(text: str) -> list[str]:
    """Provide filesystem path completions for files and directories."""
    quote = ""
    clean_text = text
    if clean_text.startswith(('"', "'")):
        quote = clean_text[0]
        clean_text = clean_text[1:]
    raw = os.path.expanduser(clean_text)
    if os.path.isdir(raw) and clean_text and not clean_text.endswith(os.sep):
        return [quote + clean_text + os.sep]
    dirname = os.path.dirname(raw) or "."
    prefix = os.path.basename(raw)
    orig_dir = os.path.dirname(clean_text)
    if orig_dir and not orig_dir.endswith(os.sep):
        orig_dir += os.sep
    try:
        entries = os.listdir(dirname)
    except Exception:
        return []
    matches = []
    for entry in sorted(entries):
        if entry.startswith(".") and not prefix.startswith("."):
            continue
        if entry.startswith(prefix):
            full = os.path.join(dirname, entry)
            is_dir = os.path.isdir(full)
            m = (orig_dir if orig_dir else "") + entry + (os.sep if is_dir else "")
            matches.append(quote + m)
    return matches


def _init_readline(
    completer_fn: Callable[[str, int], str | None] | None = None,
    initial_history: list[str] | None = None,
) -> None:
    """Initialize readline history file, arrow key navigation, and tab completion."""
    if readline is None:
        return
    doc = getattr(readline, "__doc__", "") or ""
    if "libedit" in doc:
        try:
            readline.parse_and_bind("bind -e")
            # History navigation
            readline.parse_and_bind(r'bind "\e[A" ed-prev-history')
            readline.parse_and_bind(r'bind "\e[B" ed-next-history')
            readline.parse_and_bind(r'bind "\eOA" ed-prev-history')
            readline.parse_and_bind(r'bind "\eOB" ed-next-history')
            # Character motion (Left / Right)
            readline.parse_and_bind(r'bind "\e[C" ed-next-char')
            readline.parse_and_bind(r'bind "\e[D" ed-prev-char')
            readline.parse_and_bind(r'bind "\eOC" ed-next-char')
            readline.parse_and_bind(r'bind "\eOD" ed-prev-char')
            # Line beginning & end: Jump across all wrapped lines / newlines directly to the beginning or end of the command
            readline.parse_and_bind('bind "^X^A" ed-move-to-beg')
            readline.parse_and_bind('bind "^X^B" ed-prev-char')
            readline.parse_and_bind('bind "^X^E" ed-move-to-end')
            readline.parse_and_bind('bind "^X^F" ed-next-char')
            macro_beg = ("^X^A^X^B" * 20) + "^X^A"
            macro_end = ("^X^E^X^F" * 20) + "^X^E"
            readline.parse_and_bind(f'bind -s "^A" "{macro_beg}"')
            readline.parse_and_bind(rf'bind -s "\e[H" "{macro_beg}"')
            readline.parse_and_bind(rf'bind -s "\e[1~" "{macro_beg}"')
            readline.parse_and_bind(rf'bind -s "\e[7~" "{macro_beg}"')
            readline.parse_and_bind(rf'bind -s "\eOH" "{macro_beg}"')
            readline.parse_and_bind(f'bind -s "^E" "{macro_end}"')
            readline.parse_and_bind(rf'bind -s "\e[F" "{macro_end}"')
            readline.parse_and_bind(rf'bind -s "\e[4~" "{macro_end}"')
            readline.parse_and_bind(rf'bind -s "\e[8~" "{macro_end}"')
            readline.parse_and_bind(rf'bind -s "\eOF" "{macro_end}"')
            # Word motion: Option+Left / Option+Right / Ctrl+Left / Ctrl+Right
            readline.parse_and_bind(r'bind "\eb" ed-prev-word')
            readline.parse_and_bind(r'bind "\ef" em-next-word')
            readline.parse_and_bind(r'bind "\e[1;3D" ed-prev-word')
            readline.parse_and_bind(r'bind "\e[1;3C" em-next-word')
            readline.parse_and_bind(r'bind "\e[1;5D" ed-prev-word')
            readline.parse_and_bind(r'bind "\e[1;5C" em-next-word')
            readline.parse_and_bind(r'bind "\e[5D" ed-prev-word')
            readline.parse_and_bind(r'bind "\e[5C" em-next-word')
            readline.parse_and_bind(r'bind "\e\e[D" ed-prev-word')
            readline.parse_and_bind(r'bind "\e\e[C" em-next-word')
            # Deletions: Delete key, Option+Backspace, Ctrl+W, Ctrl+K, Ctrl+U
            readline.parse_and_bind(r'bind "\e[3~" ed-delete-next-char')
            readline.parse_and_bind(r'bind "\C-w" ed-delete-prev-word')
            readline.parse_and_bind(r'bind "\C-k" ed-kill-line')
            readline.parse_and_bind(r'bind "\C-u" vi-kill-line-prev')
            readline.parse_and_bind("bind ^I rl_complete")
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
            # Line beginning & end: Jump across all wrapped lines / newlines directly to the beginning or end of the command
            readline.parse_and_bind(r'"\C-x\C-a": beginning-of-line')
            readline.parse_and_bind(r'"\C-x\C-b": backward-char')
            readline.parse_and_bind(r'"\C-x\C-e": end-of-line')
            readline.parse_and_bind(r'"\C-x\C-f": forward-char')
            gnu_beg = (r"\C-x\C-a\C-x\C-b" * 20) + r"\C-x\C-a"
            gnu_end = (r"\C-x\C-e\C-x\C-f" * 20) + r"\C-x\C-e"
            readline.parse_and_bind(f'"\\C-a": "{gnu_beg}"')
            readline.parse_and_bind(f'"\\e[H": "{gnu_beg}"')
            readline.parse_and_bind(f'"\\e[1~": "{gnu_beg}"')
            readline.parse_and_bind(f'"\\e[7~": "{gnu_beg}"')
            readline.parse_and_bind(f'"\\eOH": "{gnu_beg}"')
            readline.parse_and_bind(f'"\\C-e": "{gnu_end}"')
            readline.parse_and_bind(f'"\\e[F": "{gnu_end}"')
            readline.parse_and_bind(f'"\\e[4~": "{gnu_end}"')
            readline.parse_and_bind(f'"\\e[8~": "{gnu_end}"')
            readline.parse_and_bind(f'"\\eOF": "{gnu_end}"')
            readline.parse_and_bind(r'"\e[3~": delete-char')
            readline.parse_and_bind(r'"\eb": backward-word')
            readline.parse_and_bind(r'"\ef": forward-word')
            readline.parse_and_bind(r'"\e[1;3D": backward-word')
            readline.parse_and_bind(r'"\e[1;3C": forward-word')
            readline.parse_and_bind(r'"\e[1;5D": backward-word')
            readline.parse_and_bind(r'"\e[1;5C": forward-word')
            readline.parse_and_bind(r'"\e[5D": backward-word')
            readline.parse_and_bind(r'"\e[5C": forward-word')
            readline.parse_and_bind(r'"\e\e[D": backward-word')
            readline.parse_and_bind(r'"\e\e[C": forward-word')
            readline.parse_and_bind(r'"\C-w": backward-kill-word')
            readline.parse_and_bind(r'"\C-k": kill-line')
            readline.parse_and_bind(r'"\C-u": unix-line-discard')
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("Tab: complete")
            readline.parse_and_bind(r'"\t": complete')
            readline.parse_and_bind("bind ^I rl_complete")
        except Exception:
            pass
    if completer_fn is not None and hasattr(readline, "set_completer"):
        try:
            readline.set_completer(completer_fn)
            # Exclude '-', '_', '/', and '.' from completion delimiters so flags, identifiers, and file paths complete cleanly
            if hasattr(readline, "set_completer_delims"):
                readline.set_completer_delims(" \t\n\"'=(),;[]")
        except Exception:
            pass
    # Clear any previous session history so arrow keys only replay current session commands
    if hasattr(readline, "clear_history"):
        try:
            readline.clear_history()
        except Exception:
            pass

    if initial_history:
        for item in initial_history:
            try:
                readline.add_history(item)
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
                    PYTAE INTERACTIVE WORKBENCH (v{version})
================================================================================
Type '-help' (or 'help') for full commands reference, or '-quick_start' for cheat sheet recipes.
To inspect specific commands or flags, type '-help <topic>' (e.g. -help restore, -help filter).

Quick Start:
  df = sample:penguins           Load built-in sample (penguins, tips, titanic)
  df = orders.parquet            Load local dataset (Parquet, CSV, IPC, Excel)
  df = clip                      Load table directly from system clipboard
  status table                   List all loaded tables in memory and RAM footprint
  exit                           Exit REPL (or 'exit -s' to save session commands)

Tip: Press [Tab] to autocomplete table names, columns, commands, and flags.
================================================================================\
"""

REPL_BANNER_LOADED = """\
================================================================================
                    PYTAE INTERACTIVE WORKBENCH (v{version})
================================================================================
Type '-help' (or 'help') for full commands reference, or '-quick_start' for cheat sheet recipes.
To inspect specific commands or flags, type '-help <topic>' (e.g. -help restore, -help filter).

Quick Start:
  -head 10                       Preview active dataset
  status table                   List all loaded tables in memory and RAM footprint
  exit                           Exit REPL (or 'exit -s' to save session commands)

Tip: Press [Tab] to autocomplete table names, columns, commands, and flags.
================================================================================\
"""

REPL_HELP = """\
================================================================================
                             PYTAE REPL COMMANDS                                
================================================================================
DATASET INGEST & MANAGEMENT:
  <var> = <path> [options]: Load dataset into named table (e.g. df = data.parquet, df = clip)
  <var> = scan <path>...  : Lazily scan dataset (Parquet, CSV, IPC, NDJSON) without RAM overhead
  scan <path> [as <alias>]: Scan dataset into lazy table (e.g. scan large.parquet as df)
  load <path> as <var>... : Load dataset with alias and options (-encoding, -dlim, -nrows)
  status table [name] [-v] : Inspect active table or loaded table inventory with RAM
  switch <name>          : Switch active dataset (e.g. switch df, switch orders; 'use' deprecated)
  rename <old> <new>     : Rename in-memory table (zero-copy alias reassignment)
  rm table <table_name>  : Remove in-memory table (e.g. rm table df1, or rm table *)

DATA TRANSFORMATION & PIPELINES:
  -filter <condition>    : Filter active table, e.g. -filter "species == 'Gentoo'"
  -mutate <expr>         : Add/modify columns, e.g. -mutate "mass_kg = body_mass_g / 1000"
  -select <cols>         : Column projection, e.g. -select "species,island,!mass_kg"
  -arrange <specs>       : Sort rows, e.g. -arrange "mass_kg desc"
  -by <g> -agg <specs>   : Grouped aggregation, e.g. -by species -agg "m=mass:mean, n=count"
  -distinct <cols>       : Deduplicate rows
  -dropna [cols]         : Drop missing values
  -fillna <specs>        : Impute missing values
  <tbl> -<pipeline>      : Run pipeline on specific table (e.g. df1 -filter "amount > 100")
  <tbl> -join <t2> on=<k>: Join tables (e.g. df1 -join df2 on=cust_id -o merged.parquet)
  <var> = <tbl> -<pipe>  : Assign pipeline result to new variable (e.g. df3 = df1 -filter ...)
  <var> = -sql "<query>" : Create table from ANSI SQL across loaded tables

INSPECTION & EXPORT:
  -head [N] / -tail [N]  : Non-destructive preview of top/bottom N rows (e.g. -head 10)
  -shape                 : Display row and column counts
  -schema                : Display structured schema breakdown (columns, dtypes, nulls, cardinality)
  -cols [asc|desc]       : List column names (file order, or asc/desc sorted)
  -dtype / -nulls        : Inspect schema dtypes and missing value counts
  -diff [<tbl1>] <tbl2> [on=<key>] : Compare two tables or active table against <tbl2> (or checkpoint)
  -time [N]              : Benchmark execution over N runs (default: 1), e.g. -distinct -time 3
  -o <path> / -o clip    : Export table to file (Parquet/CSV/NDJSON) or clipboard
  export <path> / clip   : Export table to file or clipboard (synonym for -o)
  export script <path> [-relative] : Export reproducible pipeline to standalone Python (.py) or Pytae (.pt) script
  -collect               : Materialize active lazy table into memory
  -explain               : Display optimized Polars query execution plan for lazy table
  <cmd> | <shell_cmd>    : Pipe command output to shell tool (e.g. -cols | grep bill)

STATE & WORKBENCH:
  reset                  : Revert to latest checkpoint (or initial read if no checkpoints)
  reset initial          : Strictly revert to initial read even if checkpoints exist
  history [N]            : Show numbered audit log of all commands executed in session
  export script <path>   : Export session pipeline to runnable Python (.py) or Pytae (.pt) script
  checkpoint <name>      : Save ephemeral IPC snapshot of entire workbench to disk (0 MB RAM)
  restore [name]         : Restore entire workbench to saved checkpoint (or bare 'restore' for latest)
  status checkpoint [name] : Inspect checkpoint snapshot or list all saved checkpoints
  rm table <name>        : Delete an in-memory table (or 'rm table *')
  rm checkpoint <name>   : Delete a saved checkpoint (or 'rm checkpoint *')
  rm var <name>          : Delete a session variable (or 'rm var *')
  set [key [= value]]    : Configure display settings (max_rows, max_cols, float_precision, comma)
  set save               : Save current display settings permanently to ~/.pytae/config.json
  clear                  : Clear the terminal screen
  exit [-s [path]]       : Exit REPL (optionally save session history to ./history.txt or <path>)

VARIABLES & PARAMETERS:
  <name> = <literal>     : Define scalar, list, or dict variable (e.g. min_mass = 3500, cfg = {"a": 1})
  @<name>                : Print value of variable (e.g. @min_mass, @cfg.a)
  @<name> in expressions : Reference variable in -filter / -mutate / -sql (e.g. -filter "mass > @min_mass")
  status var [name] [-v] : List all session variables and constants (or inspect specific variable)
  rm var <name>          : Delete a session variable (or 'rm var *')

QUERY & PYTHON EXPRESSIONS:
  -sql "<query>"         : Run ANSI SQL across loaded tables (e.g. -sql "SELECT * FROM df1 JOIN df2 ON ...")
  py <expr>              : Evaluate Python expression with 'df' (pytae) and 'pldf' (polars)

AUTOCOMPLETION & SHORTCUTS:
  [Tab]                  : Autocomplete table names, column names, commands, flags, and file paths
================================================================================\
"""

_DISALLOWED_ALIASES: dict[str, str] = {
    # Session controls hyphenated forms (must be bare words)
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
    "-set": "set",
    "--set": "set",
    "-restore": "restore",
    "--restore": "restore",
    "-session": "session",
    "--session": "session",
    "-sessions": "sessions",
    "--sessions": "sessions",
    "-switch": "switch",
    "--switch": "switch",
    "-use": "switch",
    "--use": "switch",
    "-load": "load",
    "--load": "load",
    # Double-hyphen data inspection forms
    "--shape": "-shape",
    "--schema": "-schema",
    "--cols": "-cols",
    "--dtype": "-dtype",
    "--nulls": "-nulls",
    "--glimpse": "-glimpse",
    "--describe": "-describe",
    "--head": "-head",
    "--tail": "-tail",
    # Double-hyphen pipeline flags
    "--filter": "-filter",
    "--assert": "-assert",
    "--explode": "-explode",
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
    "quit": "exit",
    "q": "exit",
    ":q": "exit",
    "?": "help",
}

_BARE_PIPELINE_VERBS = frozenset(
    (
        "filter",
        "assert",
        "explode",
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
        "diff",
        "mask",
        "unmask",
        "long",
        "wide",
        "pivot",
        "sample",
        "join",
        "concat",
        "shape",
        "schema",
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

_RESERVED_VARIABLE_NAMES = _BARE_PIPELINE_VERBS | frozenset(
    (
        "help",
        "exit",
        "quit",
        "status",
        "set",
        "checkpoint",
        "restore",
        "reset",
        "rm",
        "clear",
        "history",
        "load",
        "save",
        "tables",
        "table",
        "use",
        "diff",
        "quick_start",
        "cheatsheet",
        "var",
        "vars",
        "variables",
        "variable",
        "clip",
        "clipboard",
        "scan",
    )
)

_VAR_REF_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9_])@([a-zA-Z_][a-zA-Z0-9_]*(?:(?:\.[a-zA-Z_][a-zA-Z0-9_]*)|(?:\[(?:\'[^\']+\'|\"[^\"]+\"|[0-9]+)\]))*)'
)


def _eval_var_reference(expr_str: str, variables: dict[str, Any]) -> Any:
    """Evaluate a variable path like 'min_mass', 'cfg.island', 'target[0]', 'cfg[\"a\"]' against variables."""
    tokens = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)|\[\'([^\']+)\'\]|\[\"([^\"]+)\"\]|\[([0-9]+)\]", expr_str)
    parts: list[str | int] = []
    for t in tokens:
        if t[0]:
            parts.append(t[0])
        elif t[1]:
            parts.append(t[1])
        elif t[2]:
            parts.append(t[2])
        elif t[3]:
            parts.append(int(t[3]))

    if not parts:
        raise KeyError(f"invalid variable reference '@{expr_str}'")

    base = str(parts[0])
    if base not in variables:
        raise KeyError(f"variable '@{base}' is not defined. Use 'status var' to view defined variables.")

    val = variables[base]
    for p in parts[1:]:
        if isinstance(val, dict) and str(p) in val:
            val = val[str(p)]
        elif isinstance(val, (list, tuple)) and isinstance(p, int) and 0 <= p < len(val):
            val = val[p]
        else:
            raise KeyError(f"cannot access '{p}' on '@{base}' (type: {type(val).__name__})")

    return val


def _substitute_variables(text: str, variables: dict[str, Any]) -> str:
    """Substitute @var, @var.key, @var['key'], and @var[idx] with their literal representations."""
    if not variables or "@" not in text:
        return text

    def repl(match: re.Match[str]) -> str:
        expr_str = match.group(1)
        val = _eval_var_reference(expr_str, variables)
        return repr(val)

    return _VAR_REF_PATTERN.sub(repl, text)


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
        elif tok in ("-opts", "--opts") and i + 1 < len(tokens):
            from pytae.cli_parsing import parse_reader_opts

            global_opts, _ = parse_reader_opts(tokens[i + 1])
            reader_kwargs.update(global_opts)
            i += 2
        else:
            cleaned.append(tok)
            i += 1

    truly_cleaned: list[str] = []
    for idx_c, c_tok in enumerate(cleaned):
        if idx_c == 0:
            truly_cleaned.append(c_tok.rstrip(","))
        elif "=" in c_tok:
            from pytae.cli_parsing import parse_reader_opts

            opts_part, _ = parse_reader_opts(c_tok.strip(","))
            reader_kwargs.update(opts_part)
        else:
            truly_cleaned.append(c_tok)
    cleaned = truly_cleaned

    return cleaned, reader_kwargs, nrows_val


def _split_respecting_quotes(s: str, seps: str = ",;") -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    escaped = False
    for ch in s:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            current.append(ch)
            continue
        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
        elif ch in seps and in_quote is None:
            chunk = "".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
        else:
            current.append(ch)
    chunk = "".join(current).strip()
    if chunk:
        chunks.append(chunk)
    return chunks


_SET_KNOWN_KEYS = {
    "max_rows",
    "rows",
    "max_cols",
    "cols",
    "float_precision",
    "precision",
    "comma",
}

_SET_RETIRED_KEYS = {
    "new_session",
    "load_session",
    "save_session",
    "copy_session",
    "move_session",
    "session_name",
    "session_load",
    "checkpoint_format",
    "checkpoint_fmt",
    "cp_format",
    "cp_fmt",
    "sessions_dir",
    "session_dir",
    "convert",
    "move",
    "overwrite",
    "force",
}


def _parse_set_pairs(line: str) -> list[tuple[str, str]]:
    """Parse key=value setting pairs from a command line.

    Supports:
      - Comma-separated: set max_rows = 20, comma = on
      - Semicolon-separated: set max_rows = 20; set comma = on
      - Space-separated: set max_rows = 20 comma = on
      - Multiple 'set' keywords on the same line
    """
    pairs: list[tuple[str, str]] = []
    import re

    # If commas or semicolons present outside of quotes
    chunks = _split_respecting_quotes(line, ",;")
    if len(chunks) > 1 or (len(chunks) == 1 and ("," in line or ";" in line)):
        for chunk in chunks:
            if chunk.lower().startswith("set "):
                chunk = chunk[4:].strip()
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                pairs.append((k.strip(), v.strip()))
            else:
                tokens = chunk.split(None, 1)
                if len(tokens) == 2:
                    pairs.append((tokens[0].strip(), tokens[1].strip()))
                elif len(tokens) == 1:
                    pairs.append((tokens[0].strip(), ""))
        return pairs

    # Multiple assignments on one line without commas/semicolons
    tokens = re.split(r"(\b(?:set\s+)?[a-zA-Z0-9_\-]+\s*=)", line)
    current_k = None
    for item in tokens:
        item_s = item.strip()
        if not item_s:
            continue
        if item_s.endswith("="):
            k = item_s[:-1].strip()
            if k.lower().startswith("set "):
                k = k[4:].strip()
            current_k = k
        elif current_k is not None:
            pairs.append((current_k, item_s))
            current_k = None
    if pairs:
        return pairs

    if "=" in line:
        k, v = line.split("=", 1)
        if k.lower().startswith("set "):
            k = k[4:].strip()
        return [(k.strip(), v.strip())]

    clean_line = line
    if clean_line.lower().startswith("set "):
        clean_line = clean_line[4:].strip()

    tokens = clean_line.split(None, 1)
    if len(tokens) == 2:
        return [(tokens[0].strip(), tokens[1].strip())]
    if len(tokens) == 1:
        return [(tokens[0].strip(), "")]
    return []


def _is_multiline_complete(buffer: str) -> bool:
    """Return True if the accumulated input buffer is syntactically complete.

    A buffer is considered incomplete (requiring continuation with prompt '... ') if:
    1. The last non-whitespace character is a trailing backslash '\\'.
    2. It contains an unclosed string quote (single, double, or triple quotes).
    3. It contains unclosed brackets '()', '[]', or '{}'.
    """
    stripped = buffer.rstrip()
    if not stripped:
        return True

    # 1. Trailing backslash means explicit line continuation
    if stripped.endswith("\\"):
        return False

    # 2. Track quotes and brackets
    in_single_quote = False
    in_double_quote = False
    in_triple_single = False
    in_triple_double = False
    escaped = False
    bracket_depth = 0

    i = 0
    n = len(buffer)
    while i < n:
        c = buffer[i]
        if escaped:
            escaped = False
            i += 1
            continue

        if c == "\\":
            escaped = True
            i += 1
            continue

        # Check for triple quotes if not already inside single/double quotes
        if not (in_single_quote or in_double_quote):
            if buffer[i : i + 3] == '"""':
                in_triple_double = not in_triple_double
                i += 3
                continue
            if buffer[i : i + 3] == "'''":
                in_triple_single = not in_triple_single
                i += 3
                continue

        if in_triple_double or in_triple_single:
            i += 1
            continue

        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            i += 1
            continue
        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            i += 1
            continue

        if not (in_single_quote or in_double_quote):
            if c in "([{":
                bracket_depth += 1
            elif c in ")]}":
                bracket_depth = max(0, bracket_depth - 1)
        i += 1

    if in_single_quote or in_double_quote or in_triple_single or in_triple_double:
        return False
    if bracket_depth > 0:
        return False

    return True


def _transpile_pipeline_tokens_to_python(tokens: list[str]) -> str:
    """Convert REPL pipeline tokens into Python method chaining syntax."""
    calls: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        low = tok.lower()

        # -filter <expr>
        if low in ("-filter", "--filter") and i + 1 < n:
            calls.append(f".filter({repr(tokens[i + 1])})")
            i += 2
            continue

        # -select <cols>
        if low in ("-select", "--select") and i + 1 < n:
            cols_val = tokens[i + 1]
            col_parts = [c.strip() for c in cols_val.split(",") if c.strip()]
            formatted_cols = ", ".join(repr(c) for c in col_parts)
            calls.append(f".select({formatted_cols})")
            i += 2
            continue

        # -mutate <expr>
        if low in ("-mutate", "--mutate") and i + 1 < n:
            calls.append(f".mutate({repr(tokens[i + 1])})")
            i += 2
            continue

        # -sort / -arrange <col> [desc]
        if low in ("-sort", "--sort", "-arrange", "--arrange") and i + 1 < n:
            col_val = tokens[i + 1]
            if i + 2 < n and tokens[i + 2].lower() in ("desc", "descending"):
                calls.append(f".sort({repr(col_val)}, descending=True)")
                i += 3
            else:
                calls.append(f".sort({repr(col_val)})")
                i += 2
            continue

        # -distinct
        if low in ("-distinct", "--distinct"):
            calls.append(".distinct()")
            i += 1
            continue

        # -dropna
        if low in ("-dropna", "--dropna"):
            calls.append(".dropna()")
            i += 1
            continue

        # -fillna <val>
        if low in ("-fillna", "--fillna") and i + 1 < n:
            calls.append(f".fillna({repr(tokens[i + 1])})")
            i += 2
            continue

        # -head [N]
        if low in ("-head", "--head"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".head({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".head(10)")
                i += 1
            continue

        # -tail [N]
        if low in ("-tail", "--tail"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".tail({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".tail(10)")
                i += 1
            continue

        # -sample [N]
        if low in ("-sample", "--sample"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".sample({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".sample(5)")
                i += 1
            continue

        # -join <other> [on=<key>] [how=<how>]
        if low in ("-join", "--join") and i + 1 < n:
            other_tbl = tokens[i + 1]
            on_key = None
            how = "inner"
            j = i + 2
            while j < n and not tokens[j].startswith("-"):
                arg = tokens[j]
                if arg.lower().startswith("on="):
                    on_key = arg.split("=", 1)[1].strip("\"'")
                elif arg.lower().startswith("how="):
                    how = arg.split("=", 1)[1].strip("\"'")
                j += 1
            on_str = f", on={repr(on_key)}" if on_key else ""
            calls.append(f".join({other_tbl}{on_str}, how={repr(how)})")
            i = j
            continue

        # -collect
        if low in ("-collect", "--collect"):
            calls.append(".collect()")
            i += 1
            continue

        # -o <dest>
        if low == "-o" and i + 1 < n:
            dest = tokens[i + 1].strip("\"'")
            calls.append(f".save({repr(dest)})")
            i += 2
            continue

        # Advance if unknown or unhandled flag
        i += 1

    return "".join(calls)


def _prune_rolled_back_entries(entries: list[str]) -> list[str]:
    """Prune commands that were rolled back between 'checkpoint <name>' and 'restore <name>'."""
    cp_indices: dict[str, int] = {}
    result: list[str] = []
    for entry in entries:
        clean = entry.strip()
        if clean.startswith("checkpoint "):
            toks = clean.split()
            if len(toks) >= 2:
                cp_name = toks[1]
                cp_indices[cp_name] = len(result)
            continue
        elif clean.startswith("restore "):
            toks = clean.split()
            if len(toks) >= 2:
                cp_name = toks[1]
                if cp_name in cp_indices:
                    idx = cp_indices[cp_name]
                    result = result[:idx]
                    continue
            continue
        result.append(entry)
    return result


def _compile_history_to_python(
    entries: list[str],
    table_sources: dict[str, str] | None = None,
    *,
    relative: bool = False,
) -> str:
    """Compile replayable REPL history into a standalone, executable Python script."""
    import ast
    import shlex
    from datetime import datetime

    entries = _prune_rolled_back_entries(entries)

    lines: list[str] = [
        '"""Auto-generated standalone Python pipeline script from pytae REPL session."""',
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "import pandas as pd",
        "import polars as pl",
        "import pytae as pt",
        "",
    ]

    for raw_entry in entries:
        clean = raw_entry.strip()
        if not clean or clean.startswith("#"):
            continue

        # 1. Python blocks: emit Python code directly
        if clean.startswith("py"):
            py_body = clean[2:].strip()
            if py_body.endswith("\npy"):
                py_body = py_body[:-3].strip()
            elif py_body.endswith(" py"):
                py_body = py_body[:-3].strip()
            if py_body:
                lines.append("# Custom Python transformation")
                lines.append(py_body)
                lines.append("")
            continue

        # 2. Ingestion: `load <path> as <alias>` or `load <path>`
        if clean.startswith("load "):
            toks = clean.split()
            if len(toks) >= 4 and toks[2].lower() == "as":
                alias = toks[3]
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                if path.lower() in ("clip", "clipboard"):
                    lines.append(f"{alias} = pl.from_pandas(pd.read_clipboard())")
                else:
                    lines.append(f"{alias} = pt.read({repr(in_path)})")
            elif len(toks) >= 2:
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                if path.lower() in ("clip", "clipboard"):
                    lines.append("df = pl.from_pandas(pd.read_clipboard())")
                else:
                    alias = Path(path).stem or "df"
                    lines.append(f"{alias} = pt.read({repr(in_path)})")
            continue

        # 2b. Lazy scan: `scan <path> as <alias>` or `scan <path>`
        if clean.startswith("scan "):
            toks = shlex.split(clean)
            scan_extra = ""
            for idx_p, sp in enumerate(toks[1:]):
                if sp in ("-dlim", "--dlim", "-sep", "--sep") and idx_p + 1 < len(toks[1:]):
                    scan_extra = f", separator={repr(toks[1:][idx_p + 1])}"
            if len(toks) >= 4 and toks[2].lower() == "as":
                alias = toks[3]
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                suf = Path(path).suffix.lower()
                scan_fn = (
                    "scan_csv"
                    if suf in (".csv", ".tsv", ".txt")
                    else (
                        "scan_ipc"
                        if suf in (".ipc", ".arrow", ".feather")
                        else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                    )
                )
                lines.append(f"{alias} = pl.{scan_fn}({repr(in_path)}{scan_extra})")
            elif len(toks) >= 2:
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                alias = Path(path).stem or "df"
                suf = Path(path).suffix.lower()
                scan_fn = (
                    "scan_csv"
                    if suf in (".csv", ".tsv", ".txt")
                    else (
                        "scan_ipc"
                        if suf in (".ipc", ".arrow", ".feather")
                        else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                    )
                )
                lines.append(f"{alias} = pl.{scan_fn}({repr(in_path)}{scan_extra})")
            continue

        # 3. Colon ingestion: `<alias>: <path>`
        if ":" in clean and not clean.startswith(("-", "*", "py")) and "=" not in clean:
            parts = clean.split(":", 1)
            alias = parts[0].strip()
            path = parts[1].strip().strip("\"'")
            if alias.isidentifier() and path:
                in_path = _to_relative_path(path) if relative else path
                if path.lower() in ("clip", "clipboard"):
                    lines.append(f"{alias} = pl.from_pandas(pd.read_clipboard())")
                else:
                    lines.append(f"{alias} = pt.read({repr(in_path)})")
                continue

        # 4. Assignments: `<target> = <expression>`
        if "=" in clean and not clean.startswith("-"):
            target, expr = [p.strip() for p in clean.split("=", 1)]
            if target.isidentifier():
                if expr.startswith(("scan ", "scan:")):
                    scan_tail = expr[4:].lstrip(": ").strip()
                    scan_parts = shlex.split(scan_tail)
                    raw_sp = scan_parts[0].strip("\"'") if scan_parts else ""
                    in_sp = _to_relative_path(raw_sp) if relative else raw_sp
                    suf = Path(raw_sp).suffix.lower()
                    scan_fn = (
                        "scan_csv"
                        if suf in (".csv", ".tsv", ".txt")
                        else (
                            "scan_ipc"
                            if suf in (".ipc", ".arrow", ".feather")
                            else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                        )
                    )
                    scan_extra = ""
                    for idx_p, sp in enumerate(scan_parts[1:]):
                        if sp in ("-dlim", "--dlim", "-sep", "--sep") and idx_p + 1 < len(scan_parts[1:]):
                            scan_extra = f", separator={repr(scan_parts[1:][idx_p + 1])}"
                    lines.append(f"{target} = pl.{scan_fn}({repr(in_sp)}{scan_extra})")
                    continue
                toks = shlex.split(expr)
                if toks and toks[0].lower() in ("clip", "clipboard"):
                    clip_code = "pl.from_pandas(pd.read_clipboard())"
                    for idx_tok, tok in enumerate(toks):
                        if tok in ("-nrows", "--nrows", "-limit", "--limit") and idx_tok + 1 < len(toks):
                            try:
                                clip_code += f".head({int(toks[idx_tok + 1])})"
                            except ValueError:
                                pass
                    lines.append(f"{target} = {clip_code}")
                    continue
                if expr.startswith("sample:"):
                    s_name = expr.split(":", 1)[1].strip()
                    lines.append(f"{target} = pt.sample({repr(s_name)})")
                    continue
                if expr.startswith("load "):
                    p = expr.split("load ", 1)[1].strip().strip("\"'")
                    in_p = _to_relative_path(p) if relative else p
                    if p.lower() in ("clip", "clipboard"):
                        lines.append(f"{target} = pl.from_pandas(pd.read_clipboard())")
                    else:
                        lines.append(f"{target} = pt.read({repr(in_p)})")
                    continue
                if expr.startswith(("-sql", "--sql")):
                    q = expr.split(None, 1)[1].strip().strip("\"'") if len(expr.split(None, 1)) > 1 else ""
                    lines.append(f"{target} = pt.sql({repr(q)})")
                    continue

                if toks:
                    src_token = toks[0]
                    if "." in src_token or "/" in src_token or "\\" in src_token:
                        raw_src = src_token.strip("\"'")
                        in_src = _to_relative_path(raw_src) if relative else raw_src
                        src_code = f"pt.read({repr(in_src)})"
                    else:
                        src_code = src_token
                    chain = _transpile_pipeline_tokens_to_python(toks[1:])
                    lines.append(f"{target} = {src_code}{chain}")
                    continue

        # 5. Direct SQL: `-sql "<query>"`
        if clean.startswith(("-sql", "--sql")):
            parts = clean.split(None, 1)
            q = parts[1].strip().strip("\"'") if len(parts) > 1 else ""
            lines.append(f"res = pt.sql({repr(q)})")
            continue

        # 6. Output commands: `<tbl> -o <path>` or `export <path>`
        toks = clean.split()
        if len(toks) >= 2 and toks[-2] == "-o":
            dest = toks[-1].strip("\"'")
            src = toks[0] if len(toks) > 2 else "df"
            if dest.lower() in ("clip", "clipboard"):
                lines.append(f"{src}.to_pandas().to_clipboard(index=False)")
            else:
                lines.append(f"{src}.save({repr(dest)})")
            continue
        if len(toks) >= 2 and toks[0] in ("export", "save"):
            dest = toks[1].strip("\"'")
            if dest.lower() in ("clip", "clipboard"):
                lines.append("df.to_pandas().to_clipboard(index=False)")
            else:
                lines.append(f"df.save({repr(dest)})")
            continue

    code_str = "\n".join(lines) + "\n"
    try:
        ast.parse(code_str)
    except SyntaxError:
        pass
    return code_str


def _compile_history_to_pt(
    entries: list[str],
    filename: str = "pipeline.pt",
    *,
    relative: bool = False,
) -> str:
    """Compile replayable REPL history into a clean, replayable Pytae script."""
    import shlex
    from datetime import datetime

    entries = _prune_rolled_back_entries(entries)

    lines: list[str] = [
        f"# Pytae Script: {filename}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for raw_entry in entries:
        clean = raw_entry.strip()
        if not clean or clean.startswith("#"):
            continue
        if relative:
            if clean.startswith("load "):
                toks = shlex.split(clean)
                if len(toks) >= 2:
                    rel_p = _to_relative_path(toks[1])
                    if len(toks) >= 4 and toks[2].lower() == "as":
                        lines.append(f"load {rel_p} as {toks[3]}")
                    else:
                        lines.append(f"load {rel_p}")
                    continue
            elif clean.startswith("scan "):
                toks = shlex.split(clean)
                if len(toks) >= 2:
                    rel_p = _to_relative_path(toks[1])
                    if len(toks) >= 4 and toks[2].lower() == "as":
                        lines.append(f"scan {rel_p} as {toks[3]}")
                    else:
                        lines.append(f"scan {rel_p}")
                    continue
            elif "=" in clean and not clean.startswith("-"):
                target, expr = [p.strip() for p in clean.split("=", 1)]
                if target.isidentifier():
                    if expr.startswith(("scan ", "scan:")):
                        raw_sp = expr[4:].lstrip(": ").strip().strip("\"'")
                        rel_sp = _to_relative_path(raw_sp)
                        lines.append(f"{target} = scan {rel_sp}")
                        continue
                    toks = shlex.split(expr)
                    if toks and ("." in toks[0] or "/" in toks[0] or "\\" in toks[0]):
                        raw_src = toks[0].strip("\"'")
                        rel_src = _to_relative_path(raw_src)
                        rem = expr[len(toks[0]) :].strip()
                        lines.append(f"{target} = {rel_src} {rem}".strip())
                        continue
        lines.append(clean)

    return "\n".join(lines) + "\n"


def _is_replayable_entry_static(entry: str) -> bool:
    """Determine if a history entry is a state-mutating transformation or artifact export.

    Exploratory previews (bare -pivot, -head, -describe, inspection, etc.) and session
    comments are excluded from exported replay scripts.
    """
    clean = entry.strip()
    if not clean or clean.startswith("#"):
        return False
    if clean.startswith("*checkpoint:") and clean.endswith("*"):
        return False
    if clean.startswith(("checkpoint ", "restore ")):
        return False
    if clean.startswith("history") or clean in ("tables", "checkpoints", "session", "sessions", "status", "clear", "help"):
        return False
    if clean.startswith("status "):
        return False

    # Script export commands themselves are excluded from exported replay scripts
    if clean.startswith(("export script", "export code", "save script", "save code", "-export script", "-save script")):
        return False

    # Python snippets: only replayable if they perform state mutation via .to_pytae()
    if clean.startswith("py"):
        return ".to_pytae(" in clean

    # Session configuration commands ('set ...') are excluded from exported scripts
    if clean == "set" or clean.startswith("set ") or clean.startswith("set="):
        return False

    # Variable assignments (df = ..., df1 = df -pivot ..., etc.) are state mutations
    if "=" in clean and not clean.startswith("-"):
        left_part = clean.split("=", 1)[0].strip()
        if left_part.isidentifier():
            return True

    # Ingestion commands: load <path> [as <alias>] or scan <path> [as <alias>]
    if clean.startswith(("load ", "scan ")):
        return True

    # Colon-style ingestion: <alias>: <path>
    if ":" in clean and not clean.startswith(("-", "*", "py")) and "=" not in clean:
        parts = clean.split(":", 1)
        if parts[0].strip().isidentifier() and not parts[1].strip().startswith("="):
            return True

    # Export commands: export <path>, save <path>
    if clean.startswith(("export ", "save ", "-export ", "-save ")):
        tokens = clean.split()
        if len(tokens) >= 2:
            target = tokens[1].lower().strip("'\"")
            if target not in ("clip", "clipboard", "script", "code"):
                return True
        return False

    tokens = clean.split()
    for i, t in enumerate(tokens):
        if t == "-o" and i + 1 < len(tokens):
            target = tokens[i + 1].lower().strip("'\"")
            if target in ("clip", "clipboard"):
                continue
            return True
        if t.startswith("-o="):
            target = t.split("=", 1)[1].lower().strip("'\"")
            if target in ("clip", "clipboard"):
                continue
            return True

    # SQL statements: -sql "<query>"
    if clean.startswith(("-sql", "--sql")):
        return True

    # Explicit reset / restore / table removal or mutation of state
    if clean.startswith("reset") or clean.startswith("restore "):
        return True
    if clean.startswith("rm table ") or clean == "rm table *":
        return True
    if clean.startswith("rename ") or clean.startswith(("switch ", "use ")):
        return True
    if clean.endswith(" -collect") or clean == "-collect":
        return True

    return False


def run_cli_export(argv: list[str]) -> int:
    """Export a recorded history log file to a standalone Python (.py) or Pytae (.pt) script."""
    if not argv:
        print("Usage: pytae -export <history_file> [-o <target.py|target.pt>] [-relative]")
        return 1

    if "--relative" in argv:
        print("pytae: '--relative' is not recognized; use '-relative'.")
        return 1

    relative = "-relative" in argv
    clean_argv = [a for a in argv if a != "-relative"]
    if not clean_argv:
        print("Usage: pytae -export <history_file> [-o <target.py|target.pt>] [-relative]")
        return 1

    history_file_str = clean_argv[0]
    out_target: str | None = None
    i = 1
    while i < len(clean_argv):
        arg = clean_argv[i]
        if arg in ("-o", "-output", "--output") and i + 1 < len(clean_argv):
            out_target = clean_argv[i + 1]
            i += 2
        elif arg.startswith(("-o=", "-output=", "--output=")):
            out_target = arg.split("=", 1)[1]
            i += 1
        elif out_target is None and not arg.startswith("-"):
            out_target = arg
            i += 1
        else:
            i += 1

    hist_p = Path(os.path.expanduser(history_file_str)).resolve()
    if not hist_p.exists():
        print(f"pytae error: history file '{history_file_str}' not found.")
        return 1

    lines = _prune_rolled_back_entries(hist_p.read_text(encoding="utf-8").splitlines())
    replayable = [item.strip() for item in lines if _is_replayable_entry_static(item)]

    if not replayable:
        print(f"pytae: No state-mutating commands found in '{history_file_str}'.")
        return 0

    if out_target is None:
        out_target = f"{hist_p.stem}.py"

    out_p = Path(os.path.expanduser(out_target)).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if out_p.suffix.lower() == ".py":
        content = _compile_history_to_python(replayable, relative=relative)
        desc = "standalone Python script"
    else:
        content = _compile_history_to_pt(replayable, out_p.name, relative=relative)
        desc = "Pytae script"

    out_p.write_text(content, encoding="utf-8")
    path_desc = " (relative paths)" if relative else " (absolute paths)"
    print(f"Exported {desc}{path_desc} to {out_p}.")
    return 0


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
        variables: dict[str, Any] | None = None,
        script: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        self.prompt = prompt
        self.session_name: str | None = None
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

        self.tables: dict[str, pl.DataFrame] = {}
        self.orig_tables: dict[str, pl.DataFrame] = {}
        self.initial_tables: dict[str, pl.DataFrame] = {}
        self.initial_df: pl.DataFrame | None = None
        self.checkpoints: dict[str, dict[str, Any]] = {}
        self._cp_dir: Path | None = None
        try:
            atexit.register(self._cleanup_cp_dir)
        except Exception:
            pass
        self.save_history_file: str | None = None
        self.max_rows: int = 10
        self.max_cols: int | None = None
        self.float_precision: int | None = None
        self.comma: bool = False
        self._load_config()
        self.table_sources: dict[str, str] = {}
        self.history: list[str] = []
        self._raw_history: list[str] = []
        self._history_cursor: int | None = None
        self.variables: dict[str, Any] = dict(variables or {})
        self.initial_variables: dict[str, Any] = dict(self.variables)

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
            self._load_file(self.path, **self.reader_kwargs)
            initial_name = self.path_str or self.path.stem or "df"
            self.tables[initial_name] = self.current_df
            self.orig_tables[initial_name] = self.current_df
            self.initial_tables[initial_name] = self.current_df
            self.initial_df = self.current_df
            self.table_sources[initial_name] = self.path.name

        self._session_start_time = datetime.datetime.now()
        timestamp_str = self._session_start_time.strftime("%Y_%m_%d_%H_%M_%S")
        self.session_history_path: Path = _get_history_dir() / f"history_{timestamp_str}.txt"
        self.session_commands_path: Path | None = None
        self.session_code_path: Path | None = None
        self.session_log_path: Path = self.session_history_path
        self.session_raw_cmd_count: int = 0
        self.session_cmd_count: int = 0
        self._completion_matches: list[str] = []

        init_target = str(path) if path else (str(paths[0]) if paths else "(none)")
        hist_header = [
            f"# Pytae REPL Session History: started {self._session_start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Target: {init_target}",
            "",
        ]
        try:
            self.session_history_path.write_text("\n".join(hist_header), encoding="utf-8")
        except Exception:
            pass

        if script:
            self._load_and_run_script(script)

    def _load_and_run_script(self, script_path_str: Path | str) -> bool:
        """Load and execute a .pt script file into the REPL state before interactive prompt."""
        p = Path(os.path.expanduser(str(script_path_str))).resolve()
        if not p.exists():
            return False
        lines = p.read_text(encoding="utf-8").splitlines()
        in_py = False
        py_buf: list[str] = []
        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "py":
                if not in_py:
                    in_py = True
                    py_buf.clear()
                else:
                    in_py = False
                    self.execute_line(f"py\n{chr(10).join(py_buf)}")
                    py_buf.clear()
                continue
            if in_py:
                py_buf.append(line)
                continue
            self.execute_line(stripped)
        return True

    def _is_replayable_entry(self, entry: str) -> bool:
        """Determine if a history entry is a state-mutating transformation or artifact export."""
        return _is_replayable_entry_static(entry)

    def _log_history_line(self, raw_line: str) -> None:
        """Faithfully record every input line to the session history file (~/.pytae/history/)."""
        clean = raw_line.strip()
        if not clean:
            return
        if clean.lower() not in ("exit", "quit", "q") and not clean.lower().startswith("exit "):
            self.session_raw_cmd_count += 1
        try:
            with open(self.session_history_path, "a", encoding="utf-8") as f:
                f.write(f"{clean}\n")
                f.flush()
        except Exception:
            pass

    def _log_session_line(self, entry: str) -> None:
        """Record replayable commands to the session command count."""
        clean = entry.strip()
        if not self._is_replayable_entry(clean):
            return
        self.session_cmd_count += 1
        if self.session_commands_path is not None:
            try:
                with open(self.session_commands_path, "a", encoding="utf-8") as f:
                    f.write(f"{clean}\n")
                    f.flush()
            except Exception:
                pass

    def _record_history(self, entry: str) -> None:
        self.history.append(entry)
        self._log_session_line(entry)

    def _substitute_variables(self, text: str) -> str:
        """Substitute session variables into text."""
        return _substitute_variables(text, self.variables)

    def _eval_var_expr(self, expr_str: str) -> Any:
        """Evaluate a variable expression against session variables."""
        return _eval_var_reference(expr_str, self.variables)

    def _update_last_history_log_line(self, canonical_line: str) -> None:
        """Replace the last logged line in session_history_path with its canonicalized version."""
        try:
            if not self.session_history_path.exists():
                return
            lines = self.session_history_path.read_text(encoding="utf-8").splitlines()
            if lines:
                lines[-1] = canonical_line
                self.session_history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _cmd_export_script(
        self,
        target_path_str: str,
        output_fn: Callable[[str], None],
        *,
        relative: bool = False,
    ) -> bool:
        """Export session commands to an executable Python (.py) or Pytae (.pt) script."""
        if not target_path_str:
            output_fn("Usage: export script <path.py|path.pt> [-relative]")
            return False

        from pytae.cli_parsing import normalize_git_bash_path

        clean_path = normalize_git_bash_path(target_path_str.strip("'\""))
        target_path = Path(os.path.expanduser(clean_path)).resolve()

        pruned_history = _prune_rolled_back_entries(self.history)
        replayable = [e for e in pruned_history if self._is_replayable_entry(e)]
        if not replayable:
            output_fn(f"pytae: No state-mutating commands executed; '{target_path.name}' not created.")
            return False

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.suffix.lower() == ".py":
                content = _compile_history_to_python(replayable, self.table_sources, relative=relative)
                desc = "standalone Python script"
            else:
                content = _compile_history_to_pt(replayable, target_path.name, relative=relative)
                desc = "Pytae script"

            target_path.write_text(content, encoding="utf-8")
            path_desc = " (-relative)" if relative else ""
            output_fn(f"Exported {desc} to {target_path}{path_desc}.")
            return True
        except Exception as exc:
            output_fn(f"pytae: Error exporting script to '{target_path_str}': {exc}")
            return False

    def _export_session_history(self, target_path_str: str, output_fn: Callable[[str], None]) -> bool:
        """Export session commands to a named file (used by exit -s [path])."""
        from pytae.cli_parsing import normalize_git_bash_path

        clean_path = normalize_git_bash_path(target_path_str.strip("'\""))
        target_path = Path(os.path.expanduser(clean_path)).resolve()
        pruned_history = _prune_rolled_back_entries(self.history)
        replayable = [e for e in pruned_history if self._is_replayable_entry(e)]
        if not replayable:
            output_fn(f"pytae: No commands were executed; '{target_path.name}' not created.")
            return False

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.suffix.lower() == ".py":
                content = _compile_history_to_python(replayable, self.table_sources)
            else:
                content = _compile_history_to_pt(replayable, target_path.name)

            target_path.write_text(content, encoding="utf-8")
            output_fn(f"Session code saved to {target_path}.")
            return True
        except Exception as exc:
            output_fn(f"pytae: Error saving code to '{target_path_str}': {exc}")
            return False

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

    def _get_or_create_cp_dir(self) -> Path:
        """Get or create the ephemeral process-bound temporary directory for IPC checkpoints."""
        if self._cp_dir is None or not self._cp_dir.exists():
            self._cp_dir = Path(tempfile.mkdtemp(prefix="pytae_cp_"))
        return self._cp_dir

    def _cleanup_cp_dir(self) -> None:
        """Wipe the ephemeral temporary checkpoint directory completely."""
        if self._cp_dir is not None:
            try:
                if self._cp_dir.exists():
                    shutil.rmtree(self._cp_dir, ignore_errors=True)
            except Exception:
                pass
            self._cp_dir = None

    def _delete_checkpoint_files(self, name: str) -> None:
        """Delete disk IPC and JSON files for a specific checkpoint."""
        if self._cp_dir is None or not self._cp_dir.exists():
            return
        prefix = f"{name}__"
        for p in self._cp_dir.glob(f"{prefix}*"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    def _delete_checkpoint(self, name: str) -> bool:
        """Delete a saved checkpoint from ephemeral disk and registry."""
        if name not in self.checkpoints:
            return False
        self._delete_checkpoint_files(name)
        self.checkpoints.pop(name, None)
        return True

    def _clear_all_checkpoints(self) -> int:
        """Delete all saved checkpoints from ephemeral disk and registry."""
        count = len(self.checkpoints)
        for name in list(self.checkpoints.keys()):
            self._delete_checkpoint_files(name)
        self.checkpoints.clear()
        self._cleanup_cp_dir()
        return count

    def _get_checkpoint_df(self, name: str) -> pl.DataFrame | None:
        """Retrieve a DataFrame from a checkpoint (reading from ephemeral IPC disk)."""
        if name not in self.checkpoints:
            return None
        snap = self.checkpoints[name]
        if isinstance(snap, pl.DataFrame):
            return snap
        if isinstance(snap, dict):
            # Check ephemeral disk IPC tables
            tbls = snap.get("tables", {})
            act = snap.get("active_table")
            if act and act in tbls:
                val = tbls[act]
                if isinstance(val, pl.DataFrame):
                    return val
                if isinstance(val, dict) and "path" in val and Path(val["path"]).exists():
                    return pl.read_ipc(val["path"])
            if tbls:
                for k, val in tbls.items():
                    if isinstance(val, pl.DataFrame):
                        return val
                    if isinstance(val, dict) and "path" in val and Path(val["path"]).exists():
                        return pl.read_ipc(val["path"])
            if snap.get("current_df_path") and Path(snap["current_df_path"]).exists():
                return pl.read_ipc(snap["current_df_path"])
            if snap.get("current_df") is not None and isinstance(snap["current_df"], pl.DataFrame):
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
            tbls = snap.get("tables", {})
            for k, val in tbls.items():
                if k == table_name or k.lower() == table_name.lower():
                    if isinstance(val, pl.DataFrame):
                        return val.clone()
                    if isinstance(val, dict) and "path" in val and Path(val["path"]).exists():
                        return pl.read_ipc(val["path"])
        return None

    def _cleanup_empty_session_dirs(self) -> None:
        if getattr(self, "session_cmd_count", 0) == 0 and getattr(self, "session_commands_path", None) is not None:
            if self.session_commands_path.exists():
                try:
                    self.session_commands_path.unlink()
                except Exception:
                    pass
        if getattr(self, "session_raw_cmd_count", 0) == 0 and getattr(self, "session_history_path", None) is not None:
            if self.session_history_path.exists():
                try:
                    self.session_history_path.unlink()
                except Exception:
                    pass
        if getattr(self, "session_raw_cmd_count", 0) == 0:
            try:
                hist_dir = _get_history_dir(create=False)
                if hist_dir.exists() and not any(hist_dir.iterdir()):
                    hist_dir.rmdir()
            except Exception:
                pass
            try:
                pytae_home = _get_pytae_home()
                if pytae_home.exists() and not any(pytae_home.iterdir()):
                    pytae_home.rmdir()
            except Exception:
                pass

    def close(self) -> None:
        """Release all in-memory tables, ephemeral disk checkpoints, and sessions."""
        self._cleanup_empty_session_dirs()
        self._cleanup_cp_dir()
        self.checkpoints.clear()
        self.tables.clear()
        self.orig_tables.clear()
        self.initial_tables.clear()
        self.table_sources.clear()
        self.variables.clear()
        self.current_df = None
        self.orig_df = None
        self.initial_df = None
        self.path_str = None
        _release_memory()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _read_file_to_df(self, path: Path | str, **reader_opts: Any) -> tuple[Path, pl.DataFrame]:
        """Resolve a dataset path and load it into a Polars DataFrame using reader kwargs with schema fallback."""
        from pytae.cli_parsing import parse_input_target

        target = parse_input_target(str(path))
        raw_path = target["path"]
        if raw_path.strip().lower() in ("clip", "clipboard"):
            import pandas as pd

            opts = dict(reader_opts)
            sep_val = opts.pop("sep", None) or opts.pop("delimiter", None) or r"\s+"
            nrows_val = opts.pop("nrows", None)
            try:
                clip_df = pd.read_clipboard(sep=sep_val)
            except Exception as exc:
                raise RuntimeError(f"clipboard error: {exc}") from exc
            if nrows_val is not None:
                clip_df = clip_df.iloc[:nrows_val]
            df = pl.from_pandas(clip_df)
            return Path("<clipboard>"), df

        p = Path(raw_path).expanduser()
        if str(p).startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = str(p)[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                raise FileNotFoundError(f"unknown sample dataset '{sample_name}'. Available: {available}")
            p = sample_file
        elif not p.exists():
            if any(ch in str(p) for ch in "*?["):
                pass
            else:
                from pytae import DATA_PATH

                candidate = DATA_PATH / p.name
                if not candidate.exists():
                    candidate = DATA_PATH / f"{p.stem}.parquet"
                if candidate.exists():
                    p = candidate
                else:
                    raise FileNotFoundError(f"File not found: {p}")
        p = p.resolve()
        opts = dict(reader_opts)
        if "sheet" in opts and "sheet_name" not in opts:
            opts["sheet_name"] = opts.pop("sheet")
        sep_val = opts.pop("sep", None) or opts.pop("delimiter", None)
        enc_val = opts.pop("encoding", None)
        chunk_val = opts.pop("chunk_size", 200_000)
        nrows_val = opts.pop("nrows", None)
        sheet_name_val = opts.pop("sheet_name", None)
        reader = get_reader(
            p,
            sep=sep_val,
            encoding=enc_val,
            chunk_size=chunk_val,
            sheet_name=sheet_name_val,
            **opts,
        )
        df = reader.to_polars(nrows=nrows_val)
        return p, df

    def _scan_file_to_df(self, path: Path | str, **scan_opts: Any) -> tuple[Path, pl.LazyFrame]:
        """Resolve a dataset path and lazily scan it into a Polars LazyFrame."""
        import polars as pl

        from pytae.cli_parsing import parse_input_target

        target = parse_input_target(str(path))
        raw_path = target["path"]
        if raw_path.strip().lower() in ("clip", "clipboard"):
            raise ValueError("scan is not supported for clipboard. Use '<var> = clip' to load into memory.")

        p = Path(raw_path).expanduser()
        if str(p).startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = str(p)[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                raise FileNotFoundError(f"unknown sample dataset '{sample_name}'. Available: {available}")
            p = sample_file
        elif not p.exists():
            if any(ch in str(p) for ch in "*?["):
                pass
            else:
                from pytae import DATA_PATH

                candidate = DATA_PATH / p.name
                if not candidate.exists():
                    candidate = DATA_PATH / f"{p.stem}.parquet"
                if candidate.exists():
                    p = candidate
                else:
                    raise FileNotFoundError(f"File not found: {p}")
        p = p.resolve()
        suffix = p.suffix.lower()
        if suffix in (".parquet", ".pq"):
            lf = pl.scan_parquet(p)
        elif suffix in (".csv", ".tsv", ".txt", ".dat"):
            sep = scan_opts.get("sep") or scan_opts.get("delimiter")
            if sep:
                lf = pl.scan_csv(p, separator=sep)
            else:
                lf = pl.scan_csv(p)
        elif suffix in (".ipc", ".arrow", ".feather"):
            lf = pl.scan_ipc(p)
        elif suffix in (".ndjson", ".jsonl"):
            lf = pl.scan_ndjson(p)
        else:
            raise ValueError(
                f"scan is not supported for '{suffix}' files. "
                "Supported formats for lazy scanning: Parquet, CSV, Arrow IPC, and NDJSON. "
                f"Use '<var> = {p.name}' to load eagerly into memory."
            )
        return p, lf

    def _load_file(self, path: Path | str, **reader_opts: Any) -> None:
        p, df = self._read_file_to_df(path, **reader_opts)
        self.path = p
        self.path_str = p.name
        self.orig_df = df
        self.current_df = df

    def _get_shape_str(self) -> str:
        if self.current_df is None:
            return "no dataset"
        import polars as pl

        if isinstance(self.current_df, pl.LazyFrame):
            return f"lazy, {len(_get_frame_columns(self.current_df))} cols"
        return f"{self.current_df.shape[0]:,}x{self.current_df.shape[1]}"

    def _resolve_table_name(self, target: str) -> str | None:
        """Resolve a table identifier to the canonical key in self.tables.

        Supports:
        1. Exact match (e.g. 'penguins.parquet', 'df1')
        2. Case-insensitive match (e.g. 'PENGUINS.PARQUET')
        3. Path stem match (e.g. 'penguins' matches 'penguins.parquet' or 'data/penguins.parquet')
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
        return None

    def _build_prompt(self) -> str:
        import polars as pl

        prefix = self.prompt
        if len(self.tables) > 1:
            table_names = ", ".join(
                f"{k} (lazy)" if isinstance(v, pl.LazyFrame) else k
                for k, v in self.tables.items()
            )
            return f"{prefix} [{table_names}]> "
        elif self.current_df is not None:
            name = self.path_str or "<dataframe>"
            return f"{prefix} [{name}: {self._get_shape_str()}]> "
        return f"{prefix}> "

    def execute_line(self, raw_line: str, output_fn: Callable[[str], None] = print) -> bool:
        """Execute one REPL input line. Returns False if REPL should terminate."""
        line = raw_line.strip()
        if not line:
            return True
        self._log_history_line(line)
        if line.startswith("#"):
            return True

        try:
            return self._execute_line_core(line, output_fn)
        except SystemExit as exc:
            msg = str(exc)
            if msg and msg != "0":
                if msg.startswith("-") or msg.startswith("pytae") or msg.startswith("invalid"):
                    output_fn(msg)
                else:
                    output_fn(f"pytae error: {msg}")
            return True
        except Exception as exc:
            output_fn(f"pytae error: {exc}")
            return True

    def _execute_line_core(self, line: str, output_fn: Callable[[str], None] = print) -> bool:
        """Core dispatch logic for one REPL command line."""
        # Collapse multi-line line continuations (trailing backslash followed by newline)
        if "\\" in line:
            line = re.sub(r"\s*\\\s*\n\s*", " ", line)
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

        hist_line = line
        if not line.startswith("py\n") and not line.startswith("py "):
            hist_line = re.sub(r"\s*\\\s*\n\s*", " ", hist_line)
            if "\n" in hist_line:
                hist_line = re.sub(r"\s*\n\s*", " ", hist_line).strip()

        if not self._raw_history or self._raw_history[-1] != hist_line:
            self._raw_history.append(hist_line)

        if readline is not None:
            try:
                cur_len = readline.get_current_history_length()
                if cur_len == 0 or readline.get_history_item(cur_len) != hist_line:
                    readline.add_history(hist_line)
            except Exception:
                pass

        # Check for top-level shell pipe: <repl_command> | <shell_command>
        pipe_parts = _split_repl_pipe(line)
        if pipe_parts is not None:
            left_cmd, shell_cmd = pipe_parts
            buffer: list[str] = []
            cont = self._execute_line_core(left_cmd, output_fn=buffer.append)
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

        # Check for exit (supports 'exit' and 'exit -s <path>')
        clean_line_lower = line.lower()
        if clean_line_lower == "exit":
            if self.save_history_file:
                self._export_session_history(self.save_history_file, output_fn)
            output_fn("Exiting pytae REPL.")
            return False

        norm_exit_line = _normalize_unquoted_windows_paths(line)
        try:
            exit_tokens = shlex.split(norm_exit_line)
        except Exception:
            exit_tokens = norm_exit_line.split()

        if exit_tokens and exit_tokens[0].lower() == "exit":
            if len(exit_tokens) >= 3 and exit_tokens[1] in ("-s", "-save", "save"):
                target = exit_tokens[2]
                self._export_session_history(target, output_fn)
                output_fn("Exiting pytae REPL.")
                return False
            elif len(exit_tokens) == 2 and exit_tokens[1] in ("-s", "-save", "save"):
                target = "history.txt"
                self._export_session_history(target, output_fn)
                output_fn("Exiting pytae REPL.")
                return False
            elif len(exit_tokens) == 2 and (exit_tokens[1].startswith("-s=") or exit_tokens[1].startswith("-s:")):
                target = exit_tokens[1][3:]
                self._export_session_history(target, output_fn)
                output_fn("Exiting pytae REPL.")
                return False
            else:
                output_fn(f"Usage: exit [-s [path]] (unrecognized option: '{' '.join(exit_tokens[1:])}')")
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

        # Bare variable inspection: `@min_mass` or `@cfg.island`
        clean_strip = line.strip()
        if clean_strip.startswith("@") and "=" not in clean_strip and not clean_strip.startswith(("-", "!", "?")):
            try:
                val = self._eval_var_expr(clean_strip[1:])
                output_fn(f"{clean_strip} = {repr(val)} ({type(val).__name__})")
                return True
            except KeyError as exc:
                output_fn(f"pytae: {exc}")
                return True

        # Tokenize line
        norm_line = _normalize_unquoted_windows_paths(line)
        tokens = shlex.split(norm_line)
        first_lower = tokens[0].lower()

        # Quick start cheat sheet (e.g. -quick_start, quick_start, -cheatsheet)
        if first_lower in ("quick_start", "-quick_start", "--quick_start", "quickstart", "-quickstart", "--quickstart", "-cheatsheet", "cheatsheet"):
            from pytae.cheatsheet import CHEATSHEET_TEXT
            output_fn(CHEATSHEET_TEXT)
            return True

        # Help commands: 'help', '-help', '--help', 'help <topic>', '-help <topic>'
        if first_lower in ("help", "-help", "--help"):
            topic_tokens = tokens[1:]
            if not topic_tokens:
                output_fn(REPL_HELP)
                return True
            from pytae.cli_help import get_keyword_help
            topic = " ".join(topic_tokens)
            help_out = get_keyword_help(topic)
            output_fn(help_out)
            return True

        # Status: `status`, `status tables` / `status table [name]`, `status checkpoints` / `status checkpoint [name]`
        if first_lower == "status":
            self._cmd_status(output_fn, args=tokens[1:])
            return True

        # History
        if first_lower == "history":
            self._cmd_history(output_fn, args=tokens[1:])
            return True

        # Export / Save Script: export script <path> [-relative], save script <path>, export clip, export <path>
        if first_lower in ("export", "-export") or (first_lower in ("save", "-save") and len(tokens) >= 2 and tokens[1].lower() in ("script", "code")):
            if len(tokens) >= 2 and tokens[1].lower() in ("script", "code"):
                if len(tokens) < 3:
                    output_fn(f"Usage: {first_lower} script <path.py|path.pt> [-relative]")
                    return True
                target = tokens[2]
                if any(t == "--relative" for t in tokens[3:]):
                    output_fn("pytae: '--relative' is not recognized; use '-relative'.")
                    return True
                relative = any(t == "-relative" for t in tokens[3:])
                self._cmd_export_script(target, output_fn, relative=relative)
                return True
            if len(tokens) >= 2:
                target = tokens[1]
                if target.lower().endswith((".py", ".pt")):
                    if any(t == "--relative" for t in tokens[2:]):
                        output_fn("pytae: '--relative' is not recognized; use '-relative'.")
                        return True
                    relative = any(t == "-relative" for t in tokens[2:])
                    self._cmd_export_script(target, output_fn, relative=relative)
                    return True
                if self._cmd_save(target, output_fn):
                    self._record_history(f"-o {target}")
                return True
            output_fn("Usage: export script <path.py|path.pt> [-relative] or export <path.parquet|csv|ndjson|clip>")
            return True

        # Reject disallowed aliases, legacy synonyms, or hyphenated inspection commands
        if first_lower in _DISALLOWED_ALIASES:
            canonical = _DISALLOWED_ALIASES[first_lower]
            output_fn(f"pytae: '{first_lower}' is not recognized; use '{canonical}'.")
            return True

        # Reset (supports bare 'reset' and 'reset initial')
        if first_lower == "reset":
            self._cmd_reset(tokens[1:], output_fn)
            return True

        # Session configuration settings: 'set [key [= value]]'
        if first_lower == "set":
            raw_args = line.strip()[3:].strip() if line.strip().lower().startswith("set") else ""
            self._cmd_set(tokens[1:], output_fn, raw_line=raw_args)
            return True

        # Notice for retired persistent sessions
        if first_lower in ("sessions", "session"):
            output_fn(_RETIRED_SESSION_MSG)
            return True

        # Rename an in-memory table (`rename <old> <new>`)
        if first_lower == "rename" and len(tokens) >= 2 and "=" not in line:
            self._cmd_rename(tokens[1:], output_fn)
            return True

        # Compare two datasets (`-diff <tbl1> <tbl2>` or `-diff <tbl>`)
        if first_lower == "-diff":
            self._cmd_diff(tokens[1:], output_fn)
            return True

        # Reject bare pipeline verbs and suggest hyphenated CLI flag
        is_assign_attempt = (tokens and "=" in tokens[0] and not tokens[0].startswith("-")) or (
            len(tokens) >= 2 and tokens[1] == "="
        )
        if first_lower in _BARE_PIPELINE_VERBS and not is_assign_attempt:
            output_fn(f"pytae: bare '{first_lower}' is not recognized; use '-{first_lower}' (matching CLI syntax).")
            return True

        # Tables list (disabled bare tables -> guide to status table)
        if first_lower == "tables":
            output_fn("pytae: bare 'tables' is not recognized; use 'status table' (or 'status table -v').")
            return True

        # Variables list (disabled bare vars -> guide to status var)
        if first_lower in ("vars", "variables"):
            output_fn("pytae: bare 'vars' is not recognized; use 'status var' (or 'status var -v').")
            return True

        # Switch active dataset (`switch <name>`, or deprecated `use <name>`)
        if first_lower in ("switch", "use"):
            is_use = (first_lower == "use")
            if len(tokens) >= 2:
                self._cmd_switch(tokens[1], output_fn, is_deprecated_use=is_use)
            else:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                cmd_name = "use" if is_use else "switch"
                output_fn(f"Usage: {cmd_name} <table_name> (available: {avail})")
            return True

        # Remove entity: `rm table <name>`, `rm table *`, `rm checkpoint <name>`, `rm checkpoint *`, `rm var <name>`, `rm var *`
        if first_lower == "rm":
            if len(tokens) < 2:
                output_fn(
                    "Usage: rm <category> <target>\n"
                    "  rm table <name>        : Remove in-memory table\n"
                    "  rm table *             : Remove all in-memory tables\n"
                    "  rm checkpoint <name>   : Remove saved checkpoint\n"
                    "  rm checkpoint *        : Remove all saved checkpoints\n"
                    "  rm var <name>          : Remove session variable\n"
                    "  rm var *               : Remove all session variables"
                )
                return True

            category = tokens[1].lower()

            if category in ("vars", "variables"):
                output_fn("pytae: plural 'vars' is not recognized; use 'rm var <name>' or 'rm var *'.")
                return True

            if category == "var":
                if len(tokens) < 3:
                    output_fn("Usage: rm var <name> or rm var *")
                    return True
                target = tokens[2].lstrip("@")
                if target == "*":
                    if not self.variables:
                        output_fn("No variables defined to remove.")
                        return True
                    count = len(self.variables)
                    self.variables.clear()
                    self._record_history("rm var *")
                    output_fn(f"Removed all session variables ({count} removed).")
                    return True
                if target in self.variables:
                    del self.variables[target]
                    self._record_history(f"rm var {target}")
                    output_fn(f"Removed variable '@{target}'.")
                    return True
                avail = ", ".join(f"@{k}" for k in self.variables) if self.variables else "none"
                output_fn(f"pytae: variable '@{target}' not found. Available: {avail}")
                return True

            if category in ("session", "sessions"):
                output_fn(_RETIRED_SESSION_MSG)
                return True

            if category == "table":
                if len(tokens) < 3:
                    output_fn("Usage: rm table <name> or rm table *")
                    return True
                target = tokens[2]
                if target == "*":
                    if not self.tables:
                        output_fn("No tables loaded to remove.")
                        return True
                    count = len(self.tables)
                    self.tables.clear()
                    self.orig_tables.clear()
                    self.initial_tables.clear()
                    self.table_sources.clear()
                    self.current_df = None
                    self.orig_df = None
                    self.initial_df = None
                    self.path_str = None
                    self._record_history("rm table *")
                    _release_memory()
                    output_fn(f"Removed all {count} loaded tables. No tables remain loaded.")
                    return True

                if target in ("-all", "--all", "all", "-*"):
                    output_fn(f"pytae: 'rm table {target}' is not recognized; use 'rm table *'.")
                    return True

                resolved = self._resolve_table_name(target)
                if resolved is not None:
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
                    self._record_history(f"rm table {target}")
                    _release_memory()
                    return True

                if target in self.checkpoints:
                    output_fn(f"pytae: '{target}' is a checkpoint, not a table. Use 'rm checkpoint {target}' to remove it.")
                    return True

                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(f"pytae: table '{target}' not found. Available: {avail}")
                return True

            if category == "tables":
                if len(tokens) > 2 and tokens[2] in ("-all", "--all", "all", "-*", "*"):
                    output_fn("pytae: 'rm tables' is not recognized; use 'rm table *'.")
                elif len(tokens) > 2:
                    output_fn(f"pytae: 'rm tables' is not recognized; use 'rm table {tokens[2]}'.")
                else:
                    output_fn("pytae: 'rm tables' is not recognized; use 'rm table <name>' or 'rm table *'.")
                return True

            if category == "checkpoints":
                if len(tokens) > 2 and tokens[2] in ("-all", "--all", "all", "-*"):
                    output_fn("pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint *'.")
                elif len(tokens) > 2:
                    output_fn(f"pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint {tokens[2]}'.")
                else:
                    output_fn("pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint'.")
                return True

            if category == "checkpoint":
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

            # If user entered bare `rm <target>` or `rm *` without category
            if category == "*":
                output_fn("pytae: 'rm *' requires a category; use 'rm table *', 'rm checkpoint *', or 'rm var *'.")
                return True

            if self._resolve_table_name(tokens[1]) is not None or tokens[1] in self.tables:
                output_fn(f"pytae: 'rm {tokens[1]}' requires explicit category; use 'rm table {tokens[1]}'.")
                return True

            if tokens[1] in self.checkpoints:
                output_fn(f"pytae: 'rm {tokens[1]}' requires explicit category; use 'rm checkpoint {tokens[1]}'.")
                return True

            if tokens[1].lstrip("@") in self.variables:
                output_fn(f"pytae: 'rm {tokens[1]}' requires explicit category; use 'rm var {tokens[1].lstrip('@')}'.")
                return True

            output_fn(f"pytae: unrecognized rm category '{tokens[1]}'. Use 'rm table <name>', 'rm checkpoint <name>', or 'rm var <name>'.")
            return True

        # Variable Assignment: `df1 = orders.parquet` or `df3 = df1 -filter "..."` or `df3 = -sql ...` or `min_mass = 3500`
        if "=" in line and not line.startswith("-"):
            left_part, right_part = line.split("=", 1)
            var_name = left_part.strip()
            if var_name.startswith("@"):
                var_name = var_name[1:].strip()
            if (
                var_name.isidentifier()
                and not right_part.startswith("=")
                and not (left_part and left_part[-1] in "<>!+-*/")
            ):
                self._cmd_assign(var_name, right_part.strip(), output_fn)
                return True

        # Bare table name displays shape and status without changing active dataset
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
                "set",
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
            target_df = self.tables[resolved_table]
            is_lazy = isinstance(target_df, pl.LazyFrame)
            for _ in range(runs):
                t0 = _time.perf_counter()
                if is_lazy:
                    n_rows, n_cols = -1, len(_get_frame_columns(target_df))
                else:
                    n_rows, n_cols = target_df.shape
                durations.append(_time.perf_counter() - t0)

            timing_str = ""
            if is_bare_switch_timed:
                if len(durations) == 1:
                    timing_str = f" | Elapsed: {_format_duration_ms(durations[0])}"
                else:
                    timing_str = f" | {_format_timing_summary(durations)}"

            is_active = self.path_str == resolved_table
            active_info = " [active]" if is_active else f" (tip: 'switch {resolved_table}' to switch active dataset)"
            shape_desc = f"lazy, {n_cols} cols" if is_lazy else f"{n_rows:,} rows x {n_cols} cols"
            output_fn(f"{resolved_table}: {shape_desc}{timing_str}{active_info}")
            return True

        # Targeted table command (e.g. `df1 -filter ...` or `df -cols` or `penguins head 5`)
        if (
            resolved_table
            and len(tokens) > 1
            and first_lower
            not in (
                "switch",
                "use",
                "rm",
                "checkpoint",
                "restore",
                "revert",
                "rollback",
                "session",
                "sessions",
                "reset",
                "set",
                "save",
                "write",
                "pipe",
                "load",
                "py",
            )
        ):
            if len(tokens) > 1 and tokens[1].lower() == "-diff":
                self._cmd_diff([resolved_table] + tokens[2:], output_fn)
                return True
            self._cmd_targeted_pipeline(resolved_table, norm_line[len(tokens[0]) :].strip(), output_fn)
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

        if first_lower in ("restore", "revert"):
            if len(tokens) < 2:
                if self.checkpoints:
                    latest_cp = list(self.checkpoints.keys())[-1]
                    self._cmd_restore(latest_cp, output_fn)
                else:
                    output_fn("Usage: restore <name> (e.g. restore baseline)")
                return True
            self._cmd_restore(tokens[1], output_fn)
            return True

        if first_lower == "rollback":
            target_cp = tokens[1] if len(tokens) >= 2 else (list(self.checkpoints.keys())[-1] if self.checkpoints else None)
            if target_cp is None:
                output_fn("pytae: no saved checkpoints to restore. (Note: 'rollback' is deprecated; use 'restore [name]' instead.)")
                return True
            output_fn("(Note: 'rollback' is deprecated; use 'restore [name]' instead.)")
            self._cmd_restore(target_cp, output_fn)
            return True

        if first_lower == "checkpoints":
            output_fn("pytae: bare 'checkpoints' is not recognized; use 'status checkpoint' (or 'status checkpoint -v').")
            return True

        # Load file as table
        if first_lower == "load":
            if len(tokens) < 2:
                output_fn("Usage: load <path> [as <alias>] (e.g. load penguins.parquet as peng)")
                return True
            self._cmd_load(tokens, output_fn)
            return True

        # Scan file as lazy table
        if first_lower == "scan":
            if len(tokens) < 2:
                output_fn("Usage: scan <path> [as <alias>] (e.g. scan penguins.parquet as peng)")
                return True
            self._cmd_scan(tokens, output_fn)
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
            if self._cmd_save(target, output_fn):
                self._record_history(f"-o {target}")
            return True
        elif first_lower.startswith("-o="):
            target = first_lower[3:].strip("\"'")
            if self._cmd_save(target, output_fn):
                self._record_history(f"-o {target}")
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
        if not has_time:
            handled = self._try_fast_inspection(self.current_df, tokens, output_fn)
            if handled:
                if not any(t in ("-o", "-output", "--output") or t.startswith(("-o=", "-output=", "--output=")) for t in tokens):
                    self._record_history(line)
                return True

        # Reject unrecognized bare commands/tokens that do not start with a pipeline flag '-'
        if tokens and not tokens[0].startswith("-"):
            output_fn(f"pytae: '{tokens[0]}' is not recognized as a command, table, or flag. Use 'status table' to list loaded tables.")
            return True

        # Otherwise, process as a pytae pipeline command
        self._cmd_pipeline(line, tokens, output_fn)
        return True

    def _format_table(self, df: Any, tbl_rows: int | None = None) -> str:
        """Format a DataFrame using the REPL's current display settings."""
        effective_rows = tbl_rows if tbl_rows is not None else self.max_rows
        effective_cols = self.max_cols if self.max_cols is not None else -1

        import polars as pl

        from pytae.dataframe import DataFrame as PytaeDataFrame

        if isinstance(df, PytaeDataFrame):
            df = df._df
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        cfg_kwargs: dict[str, Any] = {
            "tbl_rows": effective_rows,
            "tbl_cols": effective_cols,
        }
        if self.float_precision is not None:
            cfg_kwargs["float_precision"] = self.float_precision
        if self.comma:
            cfg_kwargs["thousands_separator"] = True

        with pl.Config(**cfg_kwargs):
            text = _format_table(df, tbl_rows=effective_rows, is_tty=True)

        return text

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
        if any("@" in t for t in tokens):
            try:
                tokens = [self._substitute_variables(t) for t in tokens]
            except KeyError as exc:
                output_fn(f"pytae: {exc}")
                return True
        first_lower = tokens[0].lower()
        is_inspect = (
            first_lower
            in (
                "-shape",
                "-schema",
                "-glimpse",
                "-describe",
                "-head",
                "-tail",
                "-collect",
                "-explain",
            )
            or first_lower == "-cols"
            or first_lower.startswith("-cols=")
            or first_lower == "-dtype"
            or first_lower.startswith("-dtype=")
            or first_lower == "-nulls"
            or first_lower.startswith("-nulls=")
            or (allow_sample and first_lower == "-sample")
            or first_lower == "-frac"
        )
        if not is_inspect:
            return False
        has_output = any(
            t in ("-o", "-output", "--output") or t.startswith(("-o=", "-output=", "--output="))
            for t in tokens
        )
        if has_output:
            tbl = getattr(self, "path_str", None) or "df"
            target_out = "<path>"
            for idx_t, tok_t in enumerate(tokens):
                if tok_t in ("-o", "-output", "--output") and idx_t + 1 < len(tokens):
                    target_out = tokens[idx_t + 1]
                    break
                elif tok_t.startswith(("-o=", "-output=", "--output=")):
                    target_out = tok_t.split("=", 1)[1].strip("\"'")
                    break
            example_args = [tokens[0]]
            if len(tokens) > 1 and tokens[1].isdigit():
                example_args.append(tokens[1])
            cmd_example = f"{tbl} {' '.join(example_args)}"
            output_fn(
                f"pytae: '{first_lower}' is an interactive screen preview and does not save with '-o' directly.\n"
                f"To save this subset, assign it to a table first:\n"
                f"  k = {cmd_example}\n"
                f"  k -o {target_out}"
            )
            return True
        if first_lower == "-frac":
            output_fn("pytae: -frac is deprecated and removed; use '-sample <val>' (e.g. -sample 0.05 or -sample 5%).")
            return True
        if df is None:
            output_fn("No dataset loaded.")
            return True
        import polars as pl

        if first_lower == "-collect":
            if isinstance(df, pl.LazyFrame):
                materialized = df.collect()
                tbl_name = getattr(self, "path_str", None) or "df"
                self.tables[tbl_name] = materialized
                self.orig_tables[tbl_name] = materialized
                self.initial_tables[tbl_name] = materialized
                self.current_df = materialized
                output_fn(
                    f"Materialized '{tbl_name}' ({materialized.shape[0]:,} rows x {materialized.shape[1]} cols)."
                )
                self._record_history(f"{tbl_name} -collect")
                return True
            else:
                tbl_name = getattr(self, "path_str", None) or "df"
                output_fn(f"pytae: '{tbl_name}' is already an in-memory DataFrame.")
                return True
        elif first_lower == "-explain":
            if isinstance(df, pl.LazyFrame):
                output_fn(df.explain())
                return True
            else:
                tbl_name = getattr(self, "path_str", None) or "df"
                output_fn(f"pytae: '{tbl_name}' is an in-memory DataFrame; -explain applies to lazy scanned tables.")
                return True
        elif first_lower == "-shape":
            if isinstance(df, pl.LazyFrame):
                output_fn(f"(LazyFrame: {len(_get_frame_columns(df))} cols; use '-collect' or '-head' to view rows)")
            else:
                output_fn(f"({df.shape[0]}, {df.shape[1]})")
        elif first_lower == "-schema":
            from pytae.other_utilities import format_schema

            if isinstance(df, pl.LazyFrame):
                collected = df.head(5).collect()
                output_fn(format_schema(collected))
            else:
                output_fn(format_schema(df))
        elif first_lower == "-cols" or first_lower.startswith("-cols="):
            order = "file"
            if "=" in first_lower:
                order = first_lower.split("=", 1)[1].strip("\"'").lower()
            elif len(tokens) > 1:
                order = tokens[1].lower()
            cols = _get_frame_columns(df)
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
            nulls_df = df.null_count().collect() if isinstance(df, pl.LazyFrame) else df.null_count()
            nulls_s = nulls_df.to_pandas().iloc[0]
            if order == "asc":
                nulls_s = nulls_s.sort_index(ascending=True)
            elif order == "desc":
                nulls_s = nulls_s.sort_index(ascending=False)
            output_fn(nulls_s.to_string())
        elif first_lower == "-glimpse":
            from pytae.other_utilities import format_glimpse

            collected = df.head(10).collect() if isinstance(df, pl.LazyFrame) else df
            output_fn(format_glimpse(collected))
        elif first_lower == "-describe":
            collected = df.collect() if isinstance(df, pl.LazyFrame) else df
            output_fn(self._format_table(collected.describe()))
        elif first_lower == "-head":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            collected = df.head(n).collect() if isinstance(df, pl.LazyFrame) else df.head(n)
            output_fn(self._format_table(collected, tbl_rows=n))
        elif first_lower == "-tail":
            n = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 5
            collected = df.tail(n).collect() if isinstance(df, pl.LazyFrame) else df.tail(n)
            output_fn(self._format_table(collected, tbl_rows=n))
        elif first_lower == "-sample":
            if isinstance(df, pl.LazyFrame):
                output_fn(
                    "pytae: -sample is not supported directly on lazy scans. Materialize a sample first with '-head [N] -collect'."
                )
                return True
            n = 5
            frac = None
            if len(tokens) > 1:
                val = tokens[1].strip()
                if val.endswith("%"):
                    try:
                        frac = float(val[:-1].strip()) / 100.0
                    except ValueError:
                        pass
                elif "." in val:
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
            output_fn(self._format_table(sampled, tbl_rows=len(sampled)))
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

    def _show_single_table_status(
        self, resolved: str, output_fn: Callable[[str], None], verbose: bool = False
    ) -> None:
        tbl_df = self.tables[resolved]
        import polars as pl

        is_active = self.path_str == resolved or (self.current_df is not None and self.current_df is tbl_df)
        src = self.table_sources.get(resolved, "")
        src_str = f" ({src})" if src else ""
        act_str = " [active]" if is_active else ""
        status_desc = "active" if is_active else "inactive (tip: 'switch " + resolved + "' to switch active cursor)"

        if isinstance(tbl_df, pl.LazyFrame):
            lazy_cols = _get_frame_columns(tbl_df)
            n_cols = len(lazy_cols)
            output_fn(f"Table          : {resolved}{src_str}{act_str}")
            output_fn(f"Shape          : lazy scan ({n_cols} columns)")
            output_fn("Table memory   : 0 MB (lazy, unmaterialized)")
            output_fn(f"Status         : {status_desc}")
            if verbose:
                output_fn(f"Columns ({n_cols}):")
                for col_name, dtype in zip(lazy_cols, tbl_df.dtypes, strict=False):
                    output_fn(f"  {col_name:<20}: {dtype}")
            return

        n_rows, n_cols = tbl_df.shape
        tbl_mem_mb = tbl_df.estimated_size() / (1024 * 1024)
        output_fn(f"Table          : {resolved}{src_str}{act_str}")
        output_fn(f"Shape          : {n_rows:,} rows x {n_cols} columns")
        output_fn(f"Table memory   : ~{tbl_mem_mb:.2f} MB")
        output_fn(f"Status         : {status_desc}")
        if verbose:
            output_fn(f"Columns ({n_cols}):")
            for col_name, dtype in zip(tbl_df.columns, tbl_df.dtypes, strict=False):
                output_fn(f"  {col_name:<20}: {dtype}")

    def _get_checkpoint_vars(self, snap: dict, cp_path: Path | None) -> dict[str, Any]:
        """Retrieve variables dictionary from vars.json file (or fallback to legacy meta)."""
        if cp_path and cp_path.exists():
            v_file = cp_path / "vars.json"
            if v_file.exists():
                try:
                    return json.loads(v_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
        # Fallback for legacy checkpoints where values were stored directly in meta["variables"]
        vars_meta = snap.get("variables")
        if isinstance(vars_meta, dict) and "names" not in vars_meta and "count" not in vars_meta:
            return vars_meta
        if cp_path and cp_path.exists():
            m_file = cp_path / "meta.json"
            if m_file.exists():
                try:
                    data = json.loads(m_file.read_text(encoding="utf-8"))
                    legacy_vars = data.get("variables")
                    if isinstance(legacy_vars, dict) and "names" not in legacy_vars and "count" not in legacy_vars:
                        return legacy_vars
                except Exception:
                    pass
        return {}

    def _get_checkpoint_var_summary(self, snap: dict, cp_path: Path | None) -> tuple[int, list[str]]:
        """Return (count, names) of variables in checkpoint from metadata or vars.json."""
        vars_meta = snap.get("variables")
        if isinstance(vars_meta, dict):
            if "names" in vars_meta and "count" in vars_meta:
                return vars_meta.get("count", len(vars_meta["names"])), list(vars_meta.get("names", []))
            # Legacy format: variables was a dict of key-value pairs
            return len(vars_meta), list(vars_meta.keys())
        if cp_path and cp_path.exists():
            v_file = cp_path / "vars.json"
            if v_file.exists():
                try:
                    data = json.loads(v_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return len(data), list(data.keys())
                except Exception:
                    pass
        return 0, []

    def _show_single_checkpoint_status(
        self, cp_name: str, output_fn: Callable[[str], None], verbose: bool = False
    ) -> None:
        snap = self.checkpoints[cp_name]
        created_at = snap.get("created_at", "unknown")
        size_bytes = snap.get("size_bytes", 0)
        output_fn(f"Checkpoint     : {cp_name}")
        output_fn(f"Created        : {created_at}")
        output_fn(f"Storage        : ephemeral disk IPC ({_format_bytes(size_bytes)} on disk, 0 MB RAM)")
        tbls = snap.get("tables", {})
        if isinstance(tbls, dict) and tbls:
            output_fn(f"Tables ({len(tbls)}):")
            for t_name, val in tbls.items():
                s = getattr(val, "shape", []) if hasattr(val, "shape") else val.get("shape", [])
                shape_str = f"{s[0]:,} rows x {s[1]} cols" if len(s) == 2 else ""
                output_fn(f"  - {t_name:<14}: {shape_str}")

        vars_dict = snap.get("variables", {})
        if vars_dict:
            output_fn(f"Variables ({len(vars_dict)}):")
            for var_name, var_val in vars_dict.items():
                v_repr = repr(var_val)
                if not verbose and len(v_repr) > 50:
                    v_repr = v_repr[:47] + "..."
                output_fn(f"  * @{var_name:<14}: {v_repr} ({type(var_val).__name__})")
        elif verbose:
            output_fn("Variables      : 0 defined")

    def _show_session_status(self, output_fn: Callable[[str], None], verbose: bool = False) -> None:
        """Display REPL workbench status, loaded tables, and resource health."""
        rss = _get_process_rss_mb()
        rss_str = f"~{rss:.1f} MB (PID {os.getpid()})" if rss is not None else f"PID {os.getpid()}"

        output_fn("=== REPL Session Status ===")
        output_fn("Session Name  : <none> (in-memory workbench)")
        output_fn("Storage       : in-memory (zero disk footprint)")

        # Active Table
        if self.current_df is not None:
            active_name = self.path_str or "df"
            if isinstance(self.current_df, pl.LazyFrame):
                output_fn(f"Active Table  : {active_name} (lazy, {len(_get_frame_columns(self.current_df))} cols, 0 MB)")
            else:
                n_rows, n_cols = self.current_df.shape
                mem_mb = self.current_df.estimated_size() / (1024 * 1024)
                output_fn(f"Active Table  : {active_name} ({n_rows:,} rows x {n_cols} cols, ~{mem_mb:.2f} MB)")
        else:
            output_fn("Active Table  : (none)")

        # Loaded Tables
        if not self.tables:
            output_fn("Loaded Tables : 0 tables loaded (use '<var> = <path>' to load)")
        elif len(self.tables) == 1:
            t_name = next(iter(self.tables.keys()))
            t_df = self.tables[t_name]
            if isinstance(t_df, pl.LazyFrame):
                output_fn(f"Loaded Tables : 1 table [{t_name}*] (lazy in memory)")
            else:
                t_mb = t_df.estimated_size() / (1024 * 1024)
                output_fn(f"Loaded Tables : 1 table [{t_name}*] (~{t_mb:.2f} MB in memory)")
        else:
            total_mb = sum((t.estimated_size() / (1024 * 1024)) if not isinstance(t, pl.LazyFrame) else 0.0 for t in self.tables.values())
            t_list = [f"{t}*" if t == self.path_str else t for t in self.tables.keys()]
            output_fn(f"Loaded Tables : {len(self.tables)} tables [{', '.join(t_list)}] (~{total_mb:.2f} MB in memory)")

        if verbose and self.tables:
            for t_name, t_df in self.tables.items():
                is_act = " [active]" if t_name == self.path_str else ""
                src = self.table_sources.get(t_name, "")
                src_info = f" (source: {src})" if src else ""
                if isinstance(t_df, pl.LazyFrame):
                    c_c = len(t_df.columns)
                    output_fn(f"  - {t_name}{is_act:<9}: lazy ({c_c} cols, 0 MB){src_info}")
                else:
                    r_c, c_c = t_df.shape
                    mb = t_df.estimated_size() / (1024 * 1024)
                    output_fn(f"  - {t_name}{is_act:<9}: {r_c:,} rows x {c_c} cols (~{mb:.2f} MB){src_info}")

        # Variables
        if not self.variables:
            output_fn("Variables     : 0 defined")
        elif len(self.variables) == 1:
            v_name = next(iter(self.variables.keys()))
            v_val = self.variables[v_name]
            v_repr = repr(v_val)
            if not verbose and len(v_repr) > 40:
                v_repr = v_repr[:37] + "..."
            output_fn(f"Variables     : 1 defined [@{v_name} = {v_repr}]")
        else:
            v_list = [f"@{k}" for k in self.variables.keys()]
            output_fn(f"Variables     : {len(self.variables)} defined [{', '.join(v_list)}]")

        if verbose and self.variables:
            for v_name, v_val in self.variables.items():
                v_repr = repr(v_val)
                if len(v_repr) > 60:
                    v_repr = v_repr[:57] + "..."
                output_fn(f"  * @{v_name:<14}: {v_repr} ({type(v_val).__name__})")

        # Checkpoints
        if not self.checkpoints:
            output_fn("Checkpoints   : 0 saved")
        else:
            latest_cp = list(self.checkpoints.keys())[-1]
            output_fn(f"Checkpoints   : {len(self.checkpoints)} saved (latest: {latest_cp})")

        if verbose and self.checkpoints:
            for cp_name, cp_meta in self.checkpoints.items():
                created = cp_meta.get("created_at", "")
                t_count = len(cp_meta.get("tables", {}))
                output_fn(f"  - {cp_name:<12}: ephemeral IPC created {created} ({t_count} tables, 0 MB RAM)")

        # Session Logs & Settings in verbose mode
        if verbose:
            if getattr(self, "session_history_path", None) and self.session_history_path.exists():
                hist_str = _format_friendly_path(self.session_history_path)
                output_fn(f"History Log   : {hist_str}")
            mr = getattr(self, "max_rows", "default")
            mc = getattr(self, "max_cols", "all")
            fp = getattr(self, "float_precision", "auto")
            output_fn(
                f"Settings      : max_rows={mr}, max_cols={mc}, float_precision={fp}"
            )

        # Process RAM
        output_fn(f"Process RAM   : {rss_str}")

        # Footer tip
        output_fn("-" * 60)
        output_fn(
            "(Tip: Use 'status table [name]' for table details, 'status checkpoint [name]' for checkpoints, 'status var [name]' for variables)"
        )

    def _show_external_session_status(self, path_or_name: str, output_fn: Callable[[str], None], verbose: bool = False) -> None:
        """Notice for retired external persistent session inspection."""
        output_fn(_RETIRED_SESSION_MSG)

    def _cmd_status(self, output_fn: Callable[[str], None], args: list[str] | None = None) -> None:
        args = args or []
        verbose = any(a in ("-v", "-verbose", "--verbose", "verbose", "v") for a in args)
        target_args = [a for a in args if a not in ("-v", "-verbose", "--verbose", "verbose", "v")]

        # Direct user to specific subcommands if bare 'status' or 'status -v' is typed
        if not target_args:
            output_fn("pytae: please specify a status category to inspect:")
            output_fn("  - status session [-v]        : Inspect active in-memory session status, tables, and memory")
            output_fn("  - status table [name] [-v]   : Inspect active table schema or loaded table inventory")
            output_fn("  - status checkpoint [name]   : Inspect saved checkpoints or checkpoint details")
            output_fn("  - status var [name] [-v]     : Inspect session variables, parameters and constants")
            return

        raw_cat = target_args[0].lower()
        if raw_cat.startswith("-"):
            clean_cmd = raw_cat.lstrip("-")
            output_fn(
                f"pytae: unrecognized status category '{target_args[0]}'. "
                f"Status subcommands do not use a leading '-'. Use 'status {clean_cmd}' instead."
            )
            return

        cat = raw_cat
        if cat in ("tables",):
            output_fn("pytae: plural 'tables' is not recognized; use 'status table' instead.")
            return

        if cat in ("checkpoints",):
            output_fn("pytae: plural 'checkpoints' is not recognized; use 'status checkpoint' instead.")
            return

        if cat in ("vars", "variables"):
            output_fn("pytae: plural 'vars' is not recognized; use 'status var' instead.")
            return

        if cat in ("sessions",):
            output_fn("pytae: plural 'sessions' is not recognized; use 'status session' instead.")
            return

        if cat == "session":
            if len(target_args) > 1:
                self._show_external_session_status(target_args[1], output_fn, verbose=verbose)
            else:
                self._show_session_status(output_fn, verbose=verbose)
            return

        if cat == "table":
            if len(target_args) == 1:
                if not self.tables:
                    output_fn(
                        "No tables loaded in memory. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table."
                    )
                    return
                target_tbl = self.path_str or (next(iter(self.tables.keys())) if self.tables else None)
                if target_tbl and target_tbl in self.tables:
                    self._show_single_table_status(target_tbl, output_fn, verbose=verbose)
                if len(self.tables) > 1:
                    output_fn("")
                    self._cmd_list_tables(output_fn, verbose=verbose)
                return
            # Specific table: `status table <name>`
            tbl_name = target_args[1]
            resolved = self._resolve_table_name(tbl_name)
            if resolved is None:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(f"pytae: table '{tbl_name}' not found. Available tables: {avail}")
                return
            self._show_single_table_status(resolved, output_fn, verbose=verbose)
            return

        if cat == "checkpoint":
            if len(target_args) == 1:
                self._cmd_list_checkpoints(output_fn, verbose=verbose)
                return
            # Specific checkpoint: `status checkpoint <name>`
            cp_name = target_args[1]
            if cp_name not in self.checkpoints:
                avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
                output_fn(f"pytae: checkpoint '{cp_name}' not found. Available checkpoints: {avail}")
                return
            self._show_single_checkpoint_status(cp_name, output_fn, verbose=verbose)
            return

        if cat == "var":
            if len(target_args) == 1:
                if not self.variables:
                    output_fn("No variables defined in session workbench. Define one with '<name> = <val>' (e.g. min_mass = 3500).")
                else:
                    output_fn(f"Session Variables ({len(self.variables)}):")
                    for k, v in self.variables.items():
                        v_repr = repr(v)
                        if not verbose and len(v_repr) > 50:
                            v_repr = v_repr[:47] + "..."
                        output_fn(f"  * @{k:<16} : {v_repr} ({type(v).__name__})")
                    if verbose:
                        output_fn("\nRaw JSON:")
                        output_fn(json.dumps(self.variables, indent=2))
                return
            var_name = target_args[1].lstrip("@")
            if var_name in self.variables:
                v = self.variables[var_name]
                output_fn(f"Variable '@{var_name}':")
                output_fn(f"  Type  : {type(v).__name__}")
                if isinstance(v, (dict, list)):
                    output_fn(f"  Length: {len(v)}")
                    try:
                        val_str = json.dumps(v, indent=2)
                    except Exception:
                        val_str = repr(v)
                    output_fn(f"  Value :\n{val_str}")
                else:
                    output_fn(f"  Value : {repr(v)}")
            else:
                avail = ", ".join(f"@{k}" for k in self.variables) if self.variables else "none"
                output_fn(f"pytae: variable '@{var_name}' not found. Available variables: {avail}")
            return

        output_fn(
            f"pytae: unrecognized status category '{target_args[0]}'. "
            "Use 'status session [-v]', 'status table [name] [-v]', 'status checkpoint [name] [-v]', or 'status var [name] [-v]'."
        )

    def _cmd_reset(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        if not args:
            # Bare 'reset': Reverts all tables to latest checkpoint if any exist; otherwise reverts to initial file read
            if self.checkpoints:
                latest_cp = list(self.checkpoints.keys())[-1]
                self._cmd_restore(latest_cp, output_fn, record_history=False)
                self._record_history("reset")
                output_fn(f"Reset to latest checkpoint '{latest_cp}'.")
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
                self._record_history(f"reset {table_name}")
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

        self._record_history(f"reset {table_name} initial" if is_explicit_initial else f"reset {table_name}")
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

        self.variables = dict(self.initial_variables)
        _release_memory()

        if is_explicit_initial:
            self._record_history("reset initial")
            desc = "initial dataset"
        else:
            self._record_history("reset")
            desc = "initial dataset (no checkpoints exist)"

        if self.current_df is not None:
            output_fn(f"Restored {desc}. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")
        else:
            output_fn(f"Restored {desc}.")

    def _cmd_history(self, output_fn: Callable[[str], None], args: list[str] | None = None) -> None:
        if args:
            arg0 = args[0].strip()
            clean_arg0 = arg0.lower().lstrip("-")
            if clean_arg0 in ("s", "save") or arg0.startswith("-s=") or arg0.startswith("-s:"):
                output_fn(
                    "pytae: 'history -s' is not supported. Use 'export script <path>' or 'exit -s [path]' on exit."
                )
                return
            if clean_arg0 in ("cli", "sh", "bash", "py", "python"):
                log_dest = str(getattr(self, "session_log_path", "~/.pytae/history/"))
                output_fn(
                    f"pytae: 'history {arg0}' is not supported. "
                    f"'history' displays the session audit log, and all commands are automatically recorded in {log_dest}"
                )
                return
            if arg0.isdigit():
                limit = int(arg0)
                entries = self.history[-limit:]
            else:
                output_fn(f"Usage: history [N] (unrecognized option: '{arg0}')")
                return
        else:
            entries = self.history

        # Filter out comments (# ...) to keep a clean verbatim command list
        clean_entries = [e for e in entries if not e.startswith("#")]

        if not clean_entries:
            output_fn("No commands recorded in this session.")
            return

        output_fn("Session History:")
        for idx, entry in enumerate(clean_entries, start=1):
            output_fn(f"  {idx:2d}: {entry}")

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

    def _load_config(self) -> None:
        """Load persistent REPL configuration from ~/.pytae/config.json, generating default if missing."""
        cfg_path = _get_config_path()
        if not cfg_path.exists():
            try:
                cfg_path.parent.mkdir(parents=True, exist_ok=True)
                default_data = {
                    "max_rows": 10,
                    "max_cols": "all",
                    "float_precision": "auto",
                    "comma": "off",
                }
                cfg_path.write_text(json.dumps(default_data, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
            return
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            # 1. max_rows: <int> or "default" (default 10)
            if "max_rows" in data:
                val = data["max_rows"]
                if val == "default":
                    self.max_rows = 10
                elif isinstance(val, int) and val > 0:
                    self.max_rows = val
                elif isinstance(val, str):
                    clean_v = val.lower().strip()
                    if clean_v == "default":
                        self.max_rows = 10
                    elif clean_v.isdigit() and int(clean_v) > 0:
                        self.max_rows = int(clean_v)

            # 2. max_cols: <int>, "all", "default"
            if "max_cols" in data:
                val = data["max_cols"]
                if val in ("all", "default", None) or str(val).lower() in ("all", "default", "none"):
                    self.max_cols = None
                elif isinstance(val, int) and val > 0:
                    self.max_cols = val
                elif isinstance(val, str):
                    clean_v = val.lower().strip()
                    if clean_v in ("all", "default", "none"):
                        self.max_cols = None
                    elif clean_v.isdigit() and int(clean_v) > 0:
                        self.max_cols = int(clean_v)

            # 3. float_precision: <int>, "auto", "default"
            if "float_precision" in data:
                val = data["float_precision"]
                if val in ("auto", "default", None) or str(val).lower() in ("auto", "default", "none"):
                    self.float_precision = None
                elif isinstance(val, int) and val >= 0:
                    self.float_precision = val
                elif isinstance(val, str):
                    clean_v = val.lower().strip()
                    if clean_v in ("auto", "default", "none"):
                        self.float_precision = None
                    elif clean_v.isdigit() and int(clean_v) >= 0:
                        self.float_precision = int(clean_v)

            # 4. comma: "on", "off" (or boolean)
            if "comma" in data:
                val = data["comma"]
                if isinstance(val, bool):
                    self.comma = val
                elif str(val).lower() in ("on", "true", "1", "yes"):
                    self.comma = True
                elif str(val).lower() in ("off", "false", "0", "no"):
                    self.comma = False
        except Exception:
            pass

    def _save_config(self) -> None:
        """Save current REPL settings to ~/.pytae/config.json."""
        cfg_path = _get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        max_cols_val: Any = self.max_cols if self.max_cols is not None else "all"
        prec_val: Any = self.float_precision if self.float_precision is not None else "auto"
        comma_val = "on" if self.comma else "off"
        data = {
            "max_rows": self.max_rows,
            "max_cols": max_cols_val,
            "float_precision": prec_val,
            "comma": comma_val,
        }
        cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _cmd_set(self, args: list[str], output_fn: Callable[[str], None], raw_line: str = "") -> None:
        """Handle REPL configuration settings (max_rows, max_cols, float_precision, comma)."""
        if not args:
            max_cols_str = str(self.max_cols) if self.max_cols is not None else "all"
            prec_str = str(self.float_precision) if self.float_precision is not None else "auto"
            comma_str = "on" if self.comma else "off"

            output_fn(f"max_rows        = {self.max_rows} (options: <int>, default)")
            output_fn(f"max_cols        = {max_cols_str} (options: <int>, all, default)")
            output_fn(f"float_precision = {prec_str} (options: <int>, auto, default)")
            output_fn(f"comma           = {comma_str} (options: on, off)")
            output_fn("(Tip: Run 'set save' to persist settings across REPL sessions)")
            return

        line = raw_line if raw_line else " ".join(args).strip()
        if line.lower() in ("save", "save_config", "persist"):
            self._save_config()
            output_fn(f"Saved configuration to {_get_config_path()}.")
            return

        pairs = _parse_set_pairs(line)
        if not pairs:
            output_fn(
                "Usage: set [key [= value]] (e.g. set max_rows = 20, set max_cols = all, set comma = on, set save)"
            )
            return

        pair_map: dict[str, str] = {}
        for k, v in pairs:
            pair_map[k.lower().replace("-", "_")] = v

        # Check for retired session keys
        for k in list(pair_map.keys()):
            if k in _SET_RETIRED_KEYS or k.startswith(("session", "new_session", "load_session", "save_session")):
                output_fn(_RETIRED_SESSION_MSG)
                return

        for k, val in list(pair_map.items()):
            if k in ("save", "save_config", "persist"):
                clean_v = val.lower().strip("'\"") if val else ""
                if clean_v and clean_v not in ("true", "on", "1", "yes", ""):
                    output_fn(
                        "pytae: unknown setting 'save'. Legacy 'set save = <path>' has been retired; "
                        "use 'set save' to persist settings to config.json, or 'export script <path>' to save pipelines."
                    )
                else:
                    self._save_config()
                    output_fn(f"Saved configuration to {_get_config_path()}.")
            elif k in ("max_rows", "rows"):
                if not val:
                    output_fn(f"max_rows        = {self.max_rows} (options: <int>, default)")
                    continue
                clean_val = val.lower().strip("'\"")
                if clean_val == "default":
                    self.max_rows = 10
                    output_fn("Set max_rows = 10 (default).")
                else:
                    try:
                        num = int(clean_val)
                        if num <= 0:
                            raise ValueError
                        self.max_rows = num
                        output_fn(f"Set max_rows = {num}.")
                    except ValueError:
                        output_fn(f"pytae: invalid max_rows '{val}'. Expected a positive integer or 'default'.")
            elif k in ("max_cols", "cols"):
                if not val:
                    curr = str(self.max_cols) if self.max_cols is not None else "all"
                    output_fn(f"max_cols        = {curr} (options: <int>, all, default)")
                    continue
                clean_val = val.lower().strip("'\"")
                if clean_val in ("all", "default", "none"):
                    self.max_cols = None
                    output_fn("Set max_cols = all (show all columns).")
                else:
                    try:
                        num = int(clean_val)
                        if num <= 0:
                            raise ValueError
                        self.max_cols = num
                        output_fn(f"Set max_cols = {num}.")
                    except ValueError:
                        output_fn(f"pytae: invalid max_cols '{val}'. Expected a positive integer, 'all', or 'default'.")
            elif k in ("float_precision", "precision"):
                if not val:
                    curr = str(self.float_precision) if self.float_precision is not None else "auto"
                    output_fn(f"float_precision = {curr} (options: <int>, auto, default)")
                    continue
                clean_val = val.lower().strip("'\"")
                if clean_val in ("auto", "default", "none"):
                    self.float_precision = None
                    output_fn("Set float_precision = auto (default precision).")
                else:
                    try:
                        num = int(clean_val)
                        if num < 0:
                            raise ValueError
                        self.float_precision = num
                        output_fn(f"Set float_precision = {num}.")
                    except ValueError:
                        output_fn(f"pytae: invalid float_precision '{val}'. Expected a non-negative integer, 'auto', or 'default'.")
            elif k == "comma":
                if not val:
                    curr = "on" if self.comma else "off"
                    output_fn(f"comma           = {curr} (options: on, off)")
                    continue
                clean_val = val.lower().strip("'\"")
                if clean_val in ("on", "true", "1", "yes"):
                    self.comma = True
                    output_fn("Set comma = on (numeric values will be formatted with thousands comma separators for display).")
                elif clean_val in ("off", "false", "0", "no"):
                    self.comma = False
                    output_fn("Set comma = off.")
                else:
                    output_fn(f"pytae: invalid comma '{val}'. Supported options: on, off.")
            else:
                output_fn(
                    f"pytae: unknown setting '{k}'. Supported settings: max_rows, max_cols, float_precision, comma."
                )

    def _cmd_checkpoint(self, name: str, output_fn: Callable[[str], None]) -> None:
        if not self.tables and self.current_df is None and not self.variables:
            output_fn("pytae: no dataset or variables loaded to checkpoint.")
            return

        self._delete_checkpoint_files(name)
        cp_dir = self._get_or_create_cp_dir()

        snap_tables: dict[str, dict[str, Any]] = {}
        snap_orig_tables: dict[str, dict[str, Any]] = {}
        snap_initial_tables: dict[str, dict[str, Any]] = {}
        total_bytes = 0

        for tbl_name, tbl_df in self.tables.items():
            if isinstance(tbl_df, pl.LazyFrame):
                snap_tables[tbl_name] = {
                    "is_lazy": True,
                    "frame": tbl_df,
                    "shape": [-1, len(_get_frame_columns(tbl_df))],
                    "size_bytes": 0,
                }
            else:
                p = cp_dir / f"{name}__tbl__{tbl_name}.ipc"
                tbl_df.write_ipc(p)
                sz = p.stat().st_size
                total_bytes += sz
                snap_tables[tbl_name] = {
                    "is_lazy": False,
                    "path": str(p),
                    "shape": list(tbl_df.shape),
                    "size_bytes": sz,
                }

        for tbl_name, tbl_df in self.orig_tables.items():
            if tbl_name in self.tables and tbl_df is self.tables[tbl_name]:
                snap_orig_tables[tbl_name] = {"same_as": "tables", "shape": list(tbl_df.shape) if not isinstance(tbl_df, pl.LazyFrame) else [-1, 0]}
            elif isinstance(tbl_df, pl.LazyFrame):
                snap_orig_tables[tbl_name] = {"is_lazy": True, "frame": tbl_df, "shape": [-1, len(_get_frame_columns(tbl_df))], "size_bytes": 0}
            else:
                p = cp_dir / f"{name}__orig__{tbl_name}.ipc"
                tbl_df.write_ipc(p)
                sz = p.stat().st_size
                total_bytes += sz
                snap_orig_tables[tbl_name] = {"is_lazy": False, "path": str(p), "shape": list(tbl_df.shape), "size_bytes": sz}

        for tbl_name, tbl_df in self.initial_tables.items():
            if tbl_name in self.tables and tbl_df is self.tables[tbl_name]:
                snap_initial_tables[tbl_name] = {"same_as": "tables", "shape": list(tbl_df.shape) if not isinstance(tbl_df, pl.LazyFrame) else [-1, 0]}
            elif tbl_name in self.orig_tables and tbl_df is self.orig_tables[tbl_name]:
                snap_initial_tables[tbl_name] = {"same_as": "orig_tables", "shape": list(tbl_df.shape) if not isinstance(tbl_df, pl.LazyFrame) else [-1, 0]}
            elif isinstance(tbl_df, pl.LazyFrame):
                snap_initial_tables[tbl_name] = {"is_lazy": True, "frame": tbl_df, "shape": [-1, len(_get_frame_columns(tbl_df))], "size_bytes": 0}
            else:
                p = cp_dir / f"{name}__init__{tbl_name}.ipc"
                tbl_df.write_ipc(p)
                sz = p.stat().st_size
                total_bytes += sz
                snap_initial_tables[tbl_name] = {"is_lazy": False, "path": str(p), "shape": list(tbl_df.shape), "size_bytes": sz}

        cur_df_path = None
        cur_df_shape = None
        if self.current_df is not None:
            if not isinstance(self.current_df, pl.LazyFrame):
                cur_df_shape = list(self.current_df.shape)
            if not any(self.current_df is t for t in self.tables.values()):
                if not isinstance(self.current_df, pl.LazyFrame):
                    p = cp_dir / f"{name}__current_df.ipc"
                    self.current_df.write_ipc(p)
                    sz = p.stat().st_size
                    total_bytes += sz
                    cur_df_path = str(p)

        vars_path = None
        if self.variables:
            p_vars = cp_dir / f"{name}__vars.json"
            try:
                p_vars.write_text(json.dumps(self.variables, indent=2, default=str), encoding="utf-8")
                total_bytes += p_vars.stat().st_size
                vars_path = str(p_vars)
            except Exception:
                pass

        self.checkpoints[name] = {
            "tables": snap_tables,
            "orig_tables": snap_orig_tables,
            "initial_tables": snap_initial_tables,
            "table_sources": dict(self.table_sources),
            "active_table": self.path_str,
            "current_df_path": cur_df_path,
            "current_df_shape": cur_df_shape,
            "variables": dict(self.variables),
            "variables_path": vars_path,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": total_bytes,
        }

        self._record_history(f"checkpoint {name}")
        _release_memory()

        parts_saved = []
        if len(self.tables) > 1:
            table_names = ", ".join(self.tables.keys())
            parts_saved.append(f"{len(self.tables)} tables: {table_names}")
        elif self.current_df is not None:
            s = cur_df_shape or [0, 0]
            parts_saved.append(f"{s[0]:,} rows x {s[1]} cols")
        if self.variables:
            var_names = ", ".join(f"@{k}" for k in self.variables.keys())
            parts_saved.append(f"{len(self.variables)} variables: {var_names}")
        detail_tag = f" ({', '.join(parts_saved)})" if parts_saved else ""
        output_fn(f"Saved checkpoint '{name}'{detail_tag}.")

    def _cmd_restore(self, name: str, output_fn: Callable[[str], None], record_history: bool = True) -> None:
        if name not in self.checkpoints:
            avail = ", ".join(self.checkpoints.keys()) if self.checkpoints else "none"
            output_fn(f"pytae: checkpoint '{name}' not found. Available checkpoints: {avail}")
            return

        snap = self.checkpoints[name]

        self.tables.clear()
        self.orig_tables.clear()
        self.initial_tables.clear()
        self.table_sources.clear()
        self.variables.clear()
        self.current_df = None
        self.orig_df = None
        self.initial_df = None
        self.path_str = None

        if isinstance(snap, dict):
            tbls_meta = snap.get("tables", {})
            for t_name, t_info in tbls_meta.items():
                if isinstance(t_info, pl.DataFrame):
                    self.tables[t_name] = t_info.clone()
                elif isinstance(t_info, dict):
                    if t_info.get("is_lazy") and "frame" in t_info:
                        self.tables[t_name] = t_info["frame"]
                    elif "path" in t_info and Path(t_info["path"]).exists():
                        self.tables[t_name] = pl.read_ipc(t_info["path"])

            orig_meta = snap.get("orig_tables", {})
            for t_name, t_info in orig_meta.items():
                if isinstance(t_info, pl.DataFrame):
                    self.orig_tables[t_name] = t_info.clone()
                elif isinstance(t_info, dict):
                    if t_info.get("same_as") == "tables" and t_name in self.tables:
                        self.orig_tables[t_name] = self.tables[t_name]
                    elif t_info.get("is_lazy") and "frame" in t_info:
                        self.orig_tables[t_name] = t_info["frame"]
                    elif "path" in t_info and Path(t_info["path"]).exists():
                        self.orig_tables[t_name] = pl.read_ipc(t_info["path"])

            init_meta = snap.get("initial_tables", {})
            for t_name, t_info in init_meta.items():
                if isinstance(t_info, pl.DataFrame):
                    self.initial_tables[t_name] = t_info.clone()
                elif isinstance(t_info, dict):
                    if t_info.get("same_as") == "tables" and t_name in self.tables:
                        self.initial_tables[t_name] = self.tables[t_name]
                    elif t_info.get("same_as") == "orig_tables" and t_name in self.orig_tables:
                        self.initial_tables[t_name] = self.orig_tables[t_name]
                    elif t_info.get("is_lazy") and "frame" in t_info:
                        self.initial_tables[t_name] = t_info["frame"]
                    elif "path" in t_info and Path(t_info["path"]).exists():
                        self.initial_tables[t_name] = pl.read_ipc(t_info["path"])

            self.table_sources = dict(snap.get("table_sources", {}))
            self.path_str = snap.get("active_table")
            if self.path_str and self.path_str in self.tables:
                self.current_df = self.tables[self.path_str]
            elif snap.get("current_df_path") and Path(snap["current_df_path"]).exists():
                self.current_df = pl.read_ipc(snap["current_df_path"])
            elif snap.get("current_df") is not None and isinstance(snap["current_df"], pl.DataFrame):
                self.current_df = snap["current_df"].clone()
            elif self.tables:
                first_k = next(iter(self.tables.keys()))
                self.path_str = first_k
                self.current_df = self.tables[first_k]

            self.orig_df = self.orig_tables.get(self.path_str, self.current_df)
            self.initial_df = self.initial_tables.get(self.path_str, self.orig_df)
            if "variables" in snap and isinstance(snap["variables"], dict):
                self.variables = dict(snap["variables"])
            elif snap.get("variables_path") and Path(snap["variables_path"]).exists():
                try:
                    self.variables = json.loads(Path(snap["variables_path"]).read_text(encoding="utf-8"))
                except Exception:
                    self.variables = {}
            else:
                self.variables = {}

        elif isinstance(snap, pl.DataFrame):
            self.current_df = snap.clone()
            self.orig_df = self.current_df
            self.initial_df = self.current_df
            self.tables["df"] = self.current_df
            self.orig_tables["df"] = self.current_df
            self.initial_tables["df"] = self.current_df
            self.path_str = "df"

        if record_history:
            self._record_history(f"restore {name}")
        _release_memory()

        parts_restored = []
        if len(self.tables) > 1:
            active_info = f"; active: {self.path_str}" if self.path_str else ""
            parts_restored.append(f"{len(self.tables)} tables: {', '.join(self.tables.keys())}{active_info}")
        elif self.current_df is not None:
            parts_restored.append(f"active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})")
        if self.variables:
            parts_restored.append(f"{len(self.variables)} variables: {', '.join(f'@{k}' for k in self.variables.keys())}")
        restored_desc = f" ({', '.join(parts_restored)})" if parts_restored else ""
        output_fn(f"Restored checkpoint '{name}'{restored_desc}.")

    def _cmd_list_checkpoints(self, output_fn: Callable[[str], None], *, verbose: bool = False) -> None:
        if not self.checkpoints:
            output_fn("No checkpoints saved. Use 'checkpoint <name>' to save one.")
            return
        output_fn(f"Saved Checkpoints ({len(self.checkpoints)}):")
        for name, snap in self.checkpoints.items():
            if isinstance(snap, dict):
                tbls = snap.get("tables", {})
                created_at = snap.get("created_at")
                time_str = f"  {created_at}" if created_at else ""

                summary_parts: list[str] = []
                if isinstance(tbls, dict) and tbls:
                    if len(tbls) == 1:
                        t_name = next(iter(tbls.keys()))
                        summary_parts.append(f"1 table [{t_name}]")
                    else:
                        summary_parts.append(f"{len(tbls)} tables [{', '.join(tbls.keys())}]")
                elif snap.get("current_df") is not None or snap.get("current_df_path") is not None:
                    summary_parts.append("1 table [df]")
                else:
                    summary_parts.append("0 tables")

                if snap.get("active_table"):
                    if summary_parts:
                        summary_parts[-1] += f" [active: {snap['active_table']}]"
                    else:
                        summary_parts.append(f"[active: {snap['active_table']}]")

                vars_dict = snap.get("variables", {})
                if vars_dict:
                    summary_parts.append(f"{len(vars_dict)} var{'s' if len(vars_dict) != 1 else ''} [{', '.join(f'@{k}' for k in vars_dict.keys())}]")

                summary = ", ".join(summary_parts) if summary_parts else "(empty checkpoint)"
                size_bytes = snap.get("size_bytes", 0)
                storage_str = f" ({_format_bytes(size_bytes)} disk, 0 MB RAM)" if size_bytes > 0 else " (0 MB RAM)"
                output_fn(f"  - {name:<15}: {summary}{storage_str}{time_str}")

                if isinstance(tbls, dict) and tbls:
                    for t_name, val in tbls.items():
                        s = getattr(val, "shape", []) if hasattr(val, "shape") else (val.get("shape", []) if isinstance(val, dict) else [])
                        shape_info = f": {s[0]:,} rows x {s[1]} cols" if len(s) == 2 and s[0] >= 0 else ""
                        output_fn(f"      - {t_name}{shape_info}")
                elif snap.get("current_df_shape") is not None:
                    s = snap["current_df_shape"]
                    output_fn(f"      - df: {s[0]:,} rows x {s[1]} cols")

                if vars_dict:
                    for v_name, v_val in vars_dict.items():
                        v_repr = repr(v_val)
                        if not verbose and len(v_repr) > 40:
                            v_repr = v_repr[:37] + "..."
                        output_fn(f"      * @{v_name}: {v_repr} ({type(v_val).__name__})")
            elif isinstance(snap, pl.DataFrame):
                output_fn(f"  - {name:<15}: 1 table [df] (in-memory)")
                output_fn(f"      - df: {snap.shape[0]:,} rows x {snap.shape[1]} cols")

    def _cmd_list_tables(self, output_fn: Callable[[str], None], *, verbose: bool = False) -> None:
        if not self.tables:
            output_fn(
                "No tables loaded in memory. Use '<var> = <path.parquet>' (e.g. df1 = orders.parquet) to load a table."
            )
            return
        output_fn(f"Loaded Tables ({len(self.tables)}):")
        total_mem_mb = 0.0
        for name, tbl_df in self.tables.items():
            tbl_mem_mb = tbl_df.estimated_size() / (1024 * 1024)
            total_mem_mb += tbl_mem_mb
            source = self.table_sources.get(name, "")
            source_info = f" ({source})" if source else ""
            is_active = self.path_str == name or (self.current_df is not None and self.current_df is tbl_df)
            marker = " *" if is_active else "  "
            status = " [active]" if is_active else ""
            if verbose:
                output_fn(
                    f"{marker} {name:<12}: {tbl_df.shape[0]:,} rows x {tbl_df.shape[1]} cols "
                    f"(~{tbl_mem_mb:.2f} MB){source_info}{status}"
                )
                output_fn(f"       Columns ({tbl_df.shape[1]}): {', '.join(tbl_df.columns)}")
            else:
                output_fn(f"{marker} {name:<12}: {tbl_df.shape[0]:,} rows x {tbl_df.shape[1]} cols{source_info}{status}")
        if verbose:
            rss = _get_process_rss_mb()
            proc_str = f" | Process RAM: ~{rss:.1f} MB" if rss is not None else ""
            output_fn(f"Total Tables: ~{total_mem_mb:.2f} MB{proc_str}")

    def _cmd_rename(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        """Rename an in-memory table via zero-copy dictionary key reassignment."""
        if len(args) < 2:
            output_fn("Usage: rename <old_name> <new_name> (e.g. rename df1 customers)")
            return

        old_name, new_name = args[0].strip(), args[1].strip()
        resolved_old = self._resolve_table_name(old_name)
        if resolved_old is None:
            avail = ", ".join(self.tables.keys()) if self.tables else "none"
            output_fn(f"pytae: table '{old_name}' not found. Available tables: {avail}")
            return

        if not new_name.isidentifier() or new_name.lower() in _BARE_PIPELINE_VERBS:
            output_fn(f"pytae: invalid table name '{new_name}'. Must be a valid Python identifier.")
            return

        if new_name.lower() in _RESERVED_VARIABLE_NAMES:
            output_fn(f"pytae: table name '{new_name}' is reserved; choose a different name.")
            return

        if new_name in self.variables:
            output_fn(
                f"pytae: '{new_name}' is already a session variable; cannot rename table to a variable name. Use 'rm var {new_name}' first."
            )
            return

        if new_name in self.tables and new_name != resolved_old:
            output_fn(f"pytae: table '{new_name}' already exists. Remove it first with 'rm {new_name}' before renaming.")
            return

        # Zero-copy dictionary key reassignment
        self.tables[new_name] = self.tables.pop(resolved_old)
        if resolved_old in self.orig_tables:
            self.orig_tables[new_name] = self.orig_tables.pop(resolved_old)
        if resolved_old in self.initial_tables:
            self.initial_tables[new_name] = self.initial_tables.pop(resolved_old)
        if resolved_old in self.table_sources:
            self.table_sources[new_name] = self.table_sources.pop(resolved_old)

        if self.path_str == resolved_old:
            self.path_str = new_name
            self.current_df = self.tables[new_name]
            self.orig_df = self.orig_tables.get(new_name)
            self.initial_df = self.initial_tables.get(new_name)

        self._record_history(f"rename {resolved_old} {new_name}")
        output_fn(f"Renamed table '{resolved_old}' to '{new_name}'.")

    def _cmd_diff(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        """Compare two tables or compare active table against another table / checkpoint."""
        if not args:
            output_fn("Usage: -diff <tbl1> <tbl2> [on=<key>] [-tol N] or -diff <tbl2> [on=<key>] [-tol N]")
            return

        left_tbl_name: str | None = None
        right_tbl_name: str | None = None
        tol_val: float = 0.0
        on_val: str | list[str] | None = None

        clean_args = []
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-tol", "--tol") and i + 1 < len(args):
                try:
                    tol_val = float(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif a.startswith(("-tol=", "--tol=")):
                try:
                    tol_val = float(a.split("=", 1)[1])
                except ValueError:
                    pass
                i += 1
            elif a in ("-on", "--on") and i + 1 < len(args):
                raw_on = args[i + 1].strip("'\"")
                on_cols = [c.strip() for c in raw_on.replace(":", ",").split(",") if c.strip()]
                on_val = on_cols[0] if len(on_cols) == 1 else on_cols
                i += 2
            elif a.startswith(("-on=", "--on=", "on=")):
                raw_on = a.split("=", 1)[1].strip("'\"")
                on_cols = [c.strip() for c in raw_on.replace(":", ",").split(",") if c.strip()]
                on_val = on_cols[0] if len(on_cols) == 1 else on_cols
                i += 1
            else:
                clean_args.append(a)
                i += 1

        # Check for embedded ',on=' or ',tol=' in targets (e.g. "df2,on=id" or 'df2,on=id:date,tol=1e-3')
        for idx, arg_item in enumerate(clean_args):
            if "," in arg_item and any(k in arg_item.lower() for k in ("on=", "tol=", "atol=")):
                parts = [p.strip() for p in arg_item.split(",")]
                clean_args[idx] = parts[0]
                for p in parts[1:]:
                    if "=" in p:
                        pk, pv = p.split("=", 1)
                        pk_clean = pk.strip().lower()
                        pv_clean = pv.strip().strip("'\"")
                        if pk_clean in ("on", "key", "keys") and on_val is None:
                            cols = [c.strip() for c in pv_clean.replace(":", ",").split(",") if c.strip()]
                            on_val = cols[0] if len(cols) == 1 else cols
                        elif pk_clean in ("tol", "atol") and tol_val == 0.0:
                            try:
                                tol_val = float(pv_clean)
                            except ValueError:
                                pass

        if len(clean_args) == 1:
            if self.current_df is None:
                output_fn("pytae: no active dataset loaded to compare. Usage: diff <tbl1> <tbl2>")
                return
            left_tbl_name = self.path_str or "active"
            left_df = self.current_df
            right_target = clean_args[0]
            resolved_right = self._resolve_table_name(right_target)
            if resolved_right is not None:
                right_tbl_name = resolved_right
                right_df = self.tables[resolved_right]
            elif right_target in self.checkpoints:
                right_tbl_name = f"checkpoint:{right_target}"
                right_df = self._get_checkpoint_df(right_target)
                if right_df is None:
                    output_fn(f"pytae: could not load table from checkpoint '{right_target}'.")
                    return
            else:
                try:
                    p, right_df = self._read_file_to_df(right_target)
                    right_tbl_name = p.name
                except Exception:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: comparison target '{right_target}' not found. Available: {avail}")
                    return
        elif len(clean_args) >= 2:
            left_target, right_target = clean_args[0], clean_args[1]
            resolved_left = self._resolve_table_name(left_target)
            if resolved_left is not None:
                left_tbl_name = resolved_left
                left_df = self.tables[resolved_left]
            elif left_target in self.checkpoints:
                left_tbl_name = f"checkpoint:{left_target}"
                left_df = self._get_checkpoint_df(left_target)
                if left_df is None:
                    output_fn(f"pytae: could not load table from checkpoint '{left_target}'.")
                    return
            else:
                try:
                    p, left_df = self._read_file_to_df(left_target)
                    left_tbl_name = p.name
                except Exception:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: left comparison table '{left_target}' not found. Available: {avail}")
                    return

            resolved_right = self._resolve_table_name(right_target)
            if resolved_right is not None:
                right_tbl_name = resolved_right
                right_df = self.tables[resolved_right]
            elif right_target in self.checkpoints:
                right_tbl_name = f"checkpoint:{right_target}"
                right_df = self._get_checkpoint_df(right_target)
                if right_df is None:
                    output_fn(f"pytae: could not load table from checkpoint '{right_target}'.")
                    return
            else:
                try:
                    p, right_df = self._read_file_to_df(right_target)
                    right_tbl_name = p.name
                except Exception:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: right comparison table '{right_target}' not found. Available: {avail}")
                    return
        else:
            output_fn("Usage: -diff <tbl1> <tbl2> [on=<key>] [-tol N] or -diff <tbl2> [on=<key>] [-tol N]")
            return

        from pytae import diff as pt_diff

        try:
            diff_res = pt_diff(left_df, right_df, tol=tol_val, on=on_val)
            # Re-label header for clarity
            header = f"Comparing '{left_tbl_name}' vs '{right_tbl_name}':"
            output_fn(header)
            output_fn(diff_res)
        except Exception as exc:
            output_fn(f"pytae diff error: {exc}")

    def _cmd_switch(self, name: str, output_fn: Callable[[str], None], is_deprecated_use: bool = False) -> None:
        resolved = self._resolve_table_name(name)
        if resolved is None:
            avail = ", ".join(self.tables.keys()) if self.tables else "none"
            output_fn(f"pytae: table '{name}' not found. Available tables: {avail}")
            return
        self.current_df = self.tables[resolved]
        self.orig_df = self.orig_tables.get(resolved)
        self.initial_df = self.initial_tables.get(resolved)
        self.path_str = resolved
        msg = f"Switched active dataset to '{resolved}'. Active shape: ({self.current_df.shape[0]:,}, {self.current_df.shape[1]})"
        if is_deprecated_use:
            msg += "\n(Note: 'use' is deprecated and will be removed in a future release; use 'switch <name>' instead.)"
        output_fn(msg)

    def _cmd_use(self, name: str, output_fn: Callable[[str], None]) -> None:
        """Deprecated: use switch <table_name> instead."""
        self._cmd_switch(name, output_fn, is_deprecated_use=True)

    def _cmd_assign(self, var_name: str, right_expr: str, output_fn: Callable[[str], None]) -> None:
        if var_name.lower() in _RESERVED_VARIABLE_NAMES:
            output_fn(f"pytae: '{var_name}' is a reserved command or verb; choose a different variable name.")
            return

        # 1. SQL query assignment: `df3 = -sql "<query>"`
        if right_expr.startswith(("-sql ", "-sql=", "-sql\n", "-sql\t")):
            if var_name in self.variables:
                output_fn(
                    f"pytae: '{var_name}' is already a session variable; cannot assign as a table. Use 'rm var {var_name}' first."
                )
                return
            query = right_expr[4:].lstrip(" =").strip().strip("\"'")
            try:
                query = self._substitute_variables(query)
            except KeyError as exc:
                output_fn(f"pytae: {exc}")
                return
            try:
                ctx = pl.SQLContext()
                for tbl_name, tbl_df in self.tables.items():
                    ctx.register(tbl_name, tbl_df)
                for cp_name in self.checkpoints:
                    if cp_name not in self.tables:
                        cp_df = self._get_checkpoint_df(cp_name)
                        if cp_df is not None:
                            ctx.register(cp_name, cp_df)
                res = ctx.execute(query).collect()
                self.variables.pop(var_name, None)
                self.tables[var_name] = res
                self.table_sources[var_name] = f"sql: {query[:30]}"
                self.current_df = res
                self.orig_df = self.orig_tables.get(var_name)
                self.initial_df = self.initial_tables.get(var_name)
                self.path_str = var_name
                self._record_history(f'{var_name} = -sql "{query}"')
                output_fn(f"Created '{var_name}' from SQL query ({res.shape[0]:,} rows x {res.shape[1]} cols).")
                return
            except Exception as exc:
                output_fn(f"pytae SQL Error: {exc}")
                return

        if right_expr.lower().startswith("sql "):
            output_fn("pytae: bare 'sql' is not recognized; use '-sql \"<query>\"' (matching CLI syntax).")
            return

        # 1b. Literal collection assignment: `species = ['Gentoo', 'Adelie']` or `cfg = {'a': 1}`
        if right_expr.lstrip().startswith(("[", "{")):
            if var_name in self.tables:
                output_fn(
                    f"pytae: '{var_name}' is already an active table; cannot assign as a variable. Use 'rm table {var_name}' first."
                )
                return
            try:
                subbed_val_str = self._substitute_variables(right_expr)
                val = ast.literal_eval(subbed_val_str)
                json.dumps(val)
                self.variables[var_name] = val
                self._record_history(f"{var_name} = {right_expr}")
                output_fn(f"Set @{var_name} = {val!r}")
                return
            except KeyError as exc:
                output_fn(f"pytae: {exc}")
                return
            except Exception:
                pass

        # 2. File path assignment: `df1 = orders.parquet` or `df1 = data.csv -encoding latin1 -dlim ";"`
        # Normalize unquoted Windows backslash paths (e.g. C:\Users\... -> C:/Users/...) so shlex does not eat backslashes
        norm_expr = _normalize_unquoted_windows_paths(right_expr)
        right_tokens = shlex.split(norm_expr)

        # 2a. Lazy scan assignment: `df = scan data.parquet` or `df = scan data.csv -dlim ","`
        if right_tokens and right_tokens[0].lower() == "scan":
            if var_name in self.variables:
                output_fn(
                    f"pytae: '{var_name}' is already a session variable; cannot assign as a table. Use 'rm var {var_name}' first."
                )
                return
            scan_toks = right_tokens[1:]
            cleaned_toks, reader_kwargs, _ = _parse_reader_options(scan_toks)
            if not cleaned_toks:
                output_fn("Usage: <var> = scan <path> [-dlim <char>]")
                return
            clean_path = cleaned_toks[0].strip("\"' ")
            try:
                p, lf = self._scan_file_to_df(clean_path, **reader_kwargs)
                self.tables[var_name] = lf
                self.orig_tables[var_name] = lf
                self.initial_tables[var_name] = lf
                self.initial_df = lf
                self.table_sources[var_name] = p.name
                self.current_df = lf
                self.orig_df = lf
                self.path_str = var_name
                canonical_target = _resolve_to_canonical_path(clean_path)
                unquoted_canon = canonical_target.strip("\"'")
                quoted_canon = f'"{unquoted_canon}"' if " " in unquoted_canon else unquoted_canon
                opts_str = ""
                if reader_kwargs:
                    opts_items = [f"-{k} {v}" for k, v in reader_kwargs.items()]
                    opts_str = f" {' '.join(opts_items)}"
                canonical_line = f"{var_name} = scan {quoted_canon}{opts_str}"
                self._record_history(canonical_line)
                self._update_last_history_log_line(canonical_line)
                output_fn(
                    f"Scanned {p.name} as '{var_name}' (lazy, {len(_get_frame_columns(lf))} cols)."
                )
                return
            except Exception as exc:
                output_fn(f"pytae: failed to scan {clean_path}: {exc}")
                return

        cleaned_tokens, reader_kwargs, nrows_val = _parse_reader_options(right_tokens)
        if cleaned_tokens:
            clean_path = cleaned_tokens[0].removeprefix("load ").strip("\"' ")
            if clean_path in self.checkpoints:
                output_fn(
                    f"pytae: '{clean_path}' is a saved checkpoint, not a table or file. Use 'restore {clean_path}' to restore session workbench."
                )
                return
            is_known_table = self._resolve_table_name(clean_path) is not None
            if not is_known_table:
                from pytae.cli_parsing import parse_input_target

                try:
                    target = parse_input_target(clean_path)
                except ValueError as exc:
                    output_fn(f"pytae: {exc}")
                    return

                target_path = target["path"]
                p = Path(target_path).expanduser()
                is_clip = target_path.strip().lower() in ("clip", "clipboard")
                is_sample = target_path.startswith("sample:")
                import glob

                from pytae import DATA_PATH

                has_glob = any(ch in target_path for ch in "*?[")
                is_file = (
                    (p.exists() and not p.is_dir())
                    or (p.exists() and p.is_dir())
                    or (has_glob and bool(glob.glob(target_path)))
                )
                is_data_cand = (DATA_PATH / p.name).exists() or (DATA_PATH / f"{p.stem}.parquet").exists()
                if is_clip or is_sample or is_file or is_data_cand:
                    if var_name in self.variables:
                        output_fn(
                            f"pytae: '{var_name}' is already a session variable; cannot assign as a table. Use 'rm var {var_name}' first."
                        )
                        return
                    try:
                        load_opts = dict(reader_kwargs)
                        if nrows_val is not None:
                            load_opts["nrows"] = nrows_val
                        p, df = self._read_file_to_df(target_path, **load_opts)
                        self.tables[var_name] = df
                        self.orig_tables[var_name] = df
                        self.initial_tables[var_name] = df
                        self.initial_df = df
                        self.table_sources[var_name] = p.name
                        self.current_df = df
                        self.orig_df = df
                        self.path_str = var_name
                        canonical_target = _resolve_to_canonical_path(clean_path)
                        # Reconstruct right_expr with canonical path for replay portability
                        unquoted_canon = canonical_target.strip("\"'")
                        quoted_canon = f'"{unquoted_canon}"' if " " in unquoted_canon else unquoted_canon
                        if f'"{clean_path}"' in norm_expr:
                            canonical_right = norm_expr.replace(f'"{clean_path}"', quoted_canon, 1)
                        elif f"'{clean_path}'" in norm_expr:
                            canonical_right = norm_expr.replace(f"'{clean_path}'", quoted_canon, 1)
                        else:
                            canonical_right = norm_expr.replace(clean_path, quoted_canon, 1)
                        self._record_history(f"{var_name} = {canonical_right}")
                        self._update_last_history_log_line(f"{var_name} = {canonical_right}")
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
                        output_fn(f"pytae: {exc}" if is_clip else f"pytae: failed to load {clean_path}: {exc}")
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
                if first_tok == "-join" and "left=" in right_expr:
                    source_df = pl.DataFrame()
                    source_label = "join"
                    pipe_tokens = right_tokens
                    pipe_line = right_expr
                elif self.current_df is None:
                    output_fn("pytae: no active dataset loaded to apply pipeline.")
                    return
                else:
                    source_df = self.current_df
                    source_label = self.path_str or "active"
                    pipe_tokens = right_tokens
                    pipe_line = right_expr
            else:
                resolved_src = self._resolve_table_name(first_tok)
                if resolved_src is not None:
                    source_df = self.tables[resolved_src]
                    source_label = first_tok
                    pipe_tokens = right_tokens[1:]
                    pipe_line = right_expr[len(first_tok) :].strip()
                    if not pipe_tokens:
                        if var_name in self.variables:
                            output_fn(
                                f"pytae: '{var_name}' is already a session variable; cannot assign as a table. Use 'rm var {var_name}' first."
                            )
                            return
                        self.tables[var_name] = source_df.clone()
                        self.table_sources[var_name] = f"copy of {first_tok}"
                        self.current_df = self.tables[var_name]
                        self.orig_df = self.orig_tables.get(var_name)
                        self.initial_df = self.initial_tables.get(var_name)
                        self.path_str = var_name
                        self._record_history(f"{var_name} = {right_expr}")
                        if isinstance(source_df, pl.LazyFrame):
                            shape_desc = f"lazy, {len(source_df.columns)} cols"
                        else:
                            shape_desc = f"{source_df.shape[0]:,} rows x {source_df.shape[1]} cols"
                        output_fn(
                            f"Assigned '{var_name}' from '{first_tok}' ({shape_desc})."
                        )
                        return

            if source_df is not None:
                if var_name in self.variables:
                    output_fn(
                        f"pytae: '{var_name}' is already a session variable; cannot assign as a table. Use 'rm var {var_name}' first."
                    )
                    return
                has_collect = any(t == "-collect" for t in pipe_tokens)
                if has_collect:
                    pipe_tokens = [t for t in pipe_tokens if t != "-collect"]

                if not pipe_tokens:
                    if has_collect and isinstance(source_df, pl.LazyFrame):
                        res_df = source_df.collect()
                        durations = None
                    else:
                        res_df = source_df.clone()
                        durations = None
                else:
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
                    if has_collect and isinstance(res_df, pl.LazyFrame):
                        res_df = res_df.collect()

                was_existing = var_name in self.tables
                self.tables[var_name] = res_df
                self.table_sources[var_name] = f"{source_label} {pipe_line[:20]}"
                self.current_df = res_df
                self.orig_df = self.orig_tables.get(var_name)
                self.initial_df = self.initial_tables.get(var_name)
                self.path_str = var_name
                self._record_history(f"{var_name} = {right_expr}")
                action = "Updated" if was_existing else "Created"
                timing_str = ""
                if durations:
                    from pytae.cli import _format_duration_ms, _format_timing_summary

                    if len(durations) == 1:
                        timing_str = f" | Elapsed: {_format_duration_ms(durations[0])}"
                    else:
                        timing_str = f" | {_format_timing_summary(durations)}"
                if isinstance(res_df, pl.LazyFrame):
                    shape_desc = f"lazy, {len(_get_frame_columns(res_df))} cols"
                else:
                    shape_desc = f"{res_df.shape[0]:,} rows x {res_df.shape[1]} cols"
                output_fn(f"{action} '{var_name}' ({shape_desc}){timing_str}.")
                return

        # 4. Variable literal assignment (scalars, lists, dicts)
        if var_name in self.tables:
            output_fn(
                f"pytae: '{var_name}' is already an active table; cannot assign as a variable. Use 'rm table {var_name}' first."
            )
            return

        try:
            subbed_val_str = self._substitute_variables(right_expr)
            val = ast.literal_eval(subbed_val_str)
            if isinstance(val, tuple):
                val = list(val)
            # Verify JSON serializability
            json.dumps(val)
            self.variables[var_name] = val
            self._record_history(f"{var_name} = {right_expr}")
            output_fn(f"Set @{var_name} = {val!r}")
            return
        except KeyError as exc:
            output_fn(f"pytae: {exc}")
            return
        except (ValueError, SyntaxError, TypeError):
            pass

        output_fn(
            f"pytae: could not assign '{var_name}'. '{right_expr}' is not an existing file or table, or valid literal."
        )

    def _cmd_targeted_pipeline(self, table_name: str, sub_line: str, output_fn: Callable[[str], None]) -> None:
        target_df = self.tables[table_name]
        old_active = self.current_df
        old_path = self.path_str
        self.current_df = target_df
        self.path_str = table_name

        norm_sub = _normalize_unquoted_windows_paths(sub_line)
        sub_tokens = shlex.split(norm_sub)
        first_sub = sub_tokens[0].lower() if sub_tokens else ""

        if first_sub in _DISALLOWED_ALIASES:
            canonical = _DISALLOWED_ALIASES[first_sub]
            output_fn(f"pytae: '{first_sub}' is not recognized; use '{canonical}'.")
            self.current_df = old_active
            self.path_str = old_path
            return

        has_time = any(t == "-time" or t.startswith("-time=") for t in sub_tokens)
        if has_time:
            self._cmd_pipeline(norm_sub, sub_tokens, output_fn)
            self.current_df = old_active
            self.path_str = old_path
            return

        if first_sub in _BARE_PIPELINE_VERBS:
            output_fn(f"pytae: bare '{first_sub}' is not recognized; use '-{first_sub}' (matching CLI syntax).")
        elif self._try_fast_inspection(target_df, sub_tokens, output_fn, allow_sample=True):
            pass
        elif first_sub == "-o":
            dest = sub_tokens[1] if len(sub_tokens) > 1 else "output.parquet"
            if self._cmd_save(dest, output_fn):
                self._record_history(f"{table_name} -o {dest}")
        elif first_sub.startswith("-o="):
            dest = first_sub[3:].strip("\"'")
            if self._cmd_save(dest, output_fn):
                self._record_history(f"{table_name} -o {dest}")
        elif first_sub.startswith(("-output", "--output")):
            output_fn("pytae: '-output' is not recognized; use '-o <path>'.")
        elif first_sub == "-join":
            self._cmd_join(sub_tokens[1:], output_fn)
        elif first_sub == "-sql":
            raw_query = norm_sub[4:].strip()
            query = raw_query.strip("\"'")
            self._cmd_sql(query, output_fn)
        else:
            self._cmd_pipeline(norm_sub, sub_tokens, output_fn)

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

        if alias and alias.lower() in _RESERVED_VARIABLE_NAMES:
            output_fn(f"pytae: '{alias}' is a reserved command or verb; choose a different alias.")
            return
        if alias and alias in self.variables:
            output_fn(
                f"pytae: '{alias}' is already a session variable; cannot assign as a table. Use 'rm var {alias}' first."
            )
            return

        is_clip = path_str.strip().lower() in ("clip", "clipboard")
        if not is_clip:
            p = Path(path_str).expanduser()
            if not path_str.startswith("sample:") and not p.exists() and not any(ch in path_str for ch in "*?["):
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
            load_opts = dict(reader_kwargs)
            if nrows_val is not None:
                load_opts["nrows"] = nrows_val
            p, loaded_df = self._read_file_to_df(path_str, **load_opts)
            target_alias = alias or self.path_str or ("df" if is_clip else p.stem or p.name)
            self.tables[target_alias] = loaded_df
            self.orig_tables[target_alias] = loaded_df
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
            canonical_target = _resolve_to_canonical_path(path_str)
            unquoted_canon = canonical_target.strip("\"'")
            quoted_canon = f'"{unquoted_canon}"' if " " in unquoted_canon else unquoted_canon
            if alias:
                hist_line = f"load {quoted_canon} as {alias}"
                self._record_history(hist_line)
                self._update_last_history_log_line(hist_line)
                output_fn(
                    f"Loaded {p.name} as '{alias}' ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols){opts_desc}."
                )
            else:
                hist_line = f"load {quoted_canon}"
                self._record_history(hist_line)
                self._update_last_history_log_line(hist_line)
                output_fn(
                    f"Loaded {p.name} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols){opts_desc}."
                )
        except Exception as exc:
            output_fn(f"pytae: {exc}" if is_clip else f"pytae: failed to load {path_str}: {exc}")

    def _cmd_scan(self, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        cleaned_tokens, reader_kwargs, _ = _parse_reader_options(tokens)
        if len(cleaned_tokens) < 2:
            output_fn("Usage: scan <path> [as <alias>] [-dlim <char>]")
            return
        path_str = cleaned_tokens[1].strip("\"' ")
        alias: str | None = None
        if len(cleaned_tokens) >= 4 and cleaned_tokens[2].lower() == "as":
            alias = cleaned_tokens[3]

        if alias and alias.lower() in _RESERVED_VARIABLE_NAMES:
            output_fn(f"pytae: '{alias}' is a reserved command or verb; choose a different alias.")
            return
        if alias and alias in self.variables:
            output_fn(
                f"pytae: '{alias}' is already a session variable; cannot assign as a table. Use 'rm var {alias}' first."
            )
            return

        try:
            p, lf = self._scan_file_to_df(path_str, **reader_kwargs)
            target_alias = alias or self.path_str or (p.stem or p.name)
            self.tables[target_alias] = lf
            self.orig_tables[target_alias] = lf
            self.initial_tables[target_alias] = lf
            self.initial_df = lf
            self.table_sources[target_alias] = p.name
            self.current_df = lf
            self.orig_df = lf
            self.path_str = target_alias
            canonical_target = _resolve_to_canonical_path(path_str)
            unquoted_canon = canonical_target.strip("\"'")
            quoted_canon = f'"{unquoted_canon}"' if " " in unquoted_canon else unquoted_canon
            opts_str = ""
            if reader_kwargs:
                opts_items = [f"-{k} {v}" for k, v in reader_kwargs.items()]
                opts_str = f" {' '.join(opts_items)}"
            lazy_cols = _get_frame_columns(lf)
            if alias:
                hist_line = f"scan {quoted_canon} as {alias}{opts_str}"
                output_fn(f"Scanned {p.name} as '{alias}' (lazy, {len(lazy_cols)} cols).")
            else:
                hist_line = f"scan {quoted_canon}{opts_str}"
                output_fn(f"Scanned {p.name} (lazy, {len(lazy_cols)} cols).")
            self._record_history(hist_line)
            self._update_last_history_log_line(hist_line)
        except Exception as exc:
            output_fn(f"pytae: failed to scan {path_str}: {exc}")

    def _cmd_join(self, args: list[str], output_fn: Callable[[str], None]) -> None:
        if not args:
            output_fn("Usage: -join [left=<tbl>,]right=<tbl>,on=<key> [how=left|inner|outer|semi|anti|cross] [-o <file>]")
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
            output_fn("pytae: -join requires a target table or file (e.g. -join df2 on=customer_id or -join left=df1,right=df2,on=id)")
            return

        if on_key is None and how != "cross":
            output_fn("pytae: -join requires 'on=<key>' (e.g. -join df2 on=customer_id or -join left=df1,right=df2,on=id)")
            return

        # 3. Resolve left table
        if left_name is not None:
            left_res = self._resolve_table_name(left_name)
            if left_res is not None:
                left_df = self.tables[left_res]
                left_name = left_res
            else:
                try:
                    lp, left_df = self._read_file_to_df(left_name)
                except Exception:
                    avail = ", ".join(self.tables.keys()) if self.tables else "none"
                    output_fn(f"pytae: left table '{left_name}' not found. Available: {avail}")
                    return
        elif self.current_df is not None:
            left_df = self.current_df
            left_name = self.path_str or "active"
        else:
            output_fn("pytae: no dataset loaded to join into. Load a dataset first with '<var> = <file.parquet>' or specify left=<tbl>.")
            return

        # 4. Resolve right table
        right_res = self._resolve_table_name(right_name)
        if right_res is not None:
            right_df = self.tables[right_res]
            right_name = right_res
        else:
            try:
                rp, right_df = self._read_file_to_df(right_name)
            except Exception:
                avail = ", ".join(self.tables.keys()) if self.tables else "none"
                output_fn(
                    f"pytae: join target '{right_name}' not found. Must be a loaded table or existing file (available: {avail})"
                )
                return

        # 5. Column matching (skipped for cross joins)
        if how != "cross":
            assert on_key is not None
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
            joined = (
                left_df.join(right_df, how="cross")
                if how == "cross"
                else left_df.join(
                    right_df,
                    left_on=left_col,
                    right_on=right_col,
                    how=how_polars,  # type: ignore[arg-type]
                )
            )
            self.current_df = joined
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = joined
            rec_line = f"-join left={left_name},right={right_name}" + (f",on={on_key}" if on_key else "") + f",how={how}"
            self._record_history(rec_line)
            joined_desc = f"on '{on_key}' " if on_key else ""
            output_fn(
                f"Joined '{left_name}' with '{right_name}' {joined_desc}(how={how}): {joined.shape[0]:,} rows x {joined.shape[1]} cols"
            )

            # 7. If -o was passed, export immediately
            if output_file is not None:
                self._cmd_save(output_file, output_fn)
        except Exception as exc:
            output_fn(f"pytae join error: {exc}")

    def _cmd_save(self, target: str, output_fn: Callable[[str], None]) -> bool:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded to save.")
            return False
        import polars as pl

        is_lazy = isinstance(self.current_df, pl.LazyFrame)
        if target.lower() in ("clip", "clipboard"):
            try:
                df_to_copy = self.current_df.collect() if is_lazy else self.current_df
                df_to_copy.to_pandas().to_clipboard(index=False)
            except Exception as exc:
                output_fn(f"pytae: failed to copy to clipboard: {exc}")
                return False
            output_fn(f"Copied {df_to_copy.shape[0]:,} rows to system clipboard.")
            return True
        from pytae.cli_parsing import normalize_git_bash_path

        clean_target = normalize_git_bash_path(target.strip("'\""))
        out_path = Path(clean_target)
        try:
            from pytae.readers import write_dataframe

            write_dataframe(self.current_df, out_path)
            if is_lazy:
                output_fn(f"Streamed lazy pipeline to {out_path}.")
            else:
                output_fn(f"Saved {self.current_df.shape[0]:,} rows to {out_path}.")
            return True
        except Exception as exc:
            output_fn(f"pytae: failed to save to {out_path}: {exc}")
            return False

    def _cmd_sql(self, query: str, output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded for SQL query.")
            return
        if not query:
            output_fn('Usage: -sql "<query>" (e.g. -sql "SELECT species, COUNT(*) FROM df GROUP BY 1")')
            return
        try:
            query = self._substitute_variables(query)
        except KeyError as exc:
            output_fn(f"pytae: {exc}")
            return
        try:
            ctx = pl.SQLContext()
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
            self.current_df = res
            if self.path_str and self.path_str in self.tables:
                self.tables[self.path_str] = res
            self._record_history(f'-sql "{query}"')
        except Exception as exc:
            output_fn(f"pytae SQL Error: {exc}")

    def _cmd_py(self, expr: str, output_fn: Callable[[str], None]) -> None:
        if not expr:
            output_fn("Usage: py <expression> (or enter 'py' on an empty line for multi-line block mode)")
            return
        lines = expr.splitlines()
        if lines and lines[-1].strip() == "py":
            expr = "\n".join(lines[:-1]).strip()
        if not expr:
            return
        local_scope: dict[str, Any] = {}
        try:
            import pytae as pt
            from pytae.accessor import _BasePtAccessor
            from pytae.dataframe import DataFrame as PytaeDataFrame
            from pytae.dataframe import GroupedDataFrame as PytaeGroupedDataFrame

            local_scope = {
                "df": PytaeDataFrame(self.current_df) if self.current_df is not None else None,
                "pldf": self.current_df,
                "pl": pl,
                "pt": pt,
                "DataFrame": PytaeDataFrame,
            }
            orig_table_instances: dict[str, Any] = {}
            for tbl_name, tbl_df in self.tables.items():
                inst = PytaeDataFrame(tbl_df)
                local_scope[tbl_name] = inst
                orig_table_instances[tbl_name] = inst

            for cp_name in self.checkpoints:
                if cp_name not in local_scope:
                    cp_df = self._get_checkpoint_df(cp_name)
                    if cp_df is not None:
                        local_scope[cp_name] = PytaeDataFrame(cp_df)
            for var_name, var_val in self.variables.items():
                if var_name not in local_scope:
                    local_scope[var_name] = var_val

            orig_df_obj = local_scope.get("df")

            try:
                res = eval(expr, {}, local_scope)
                if isinstance(res, (pl.DataFrame, PytaeDataFrame)):
                    output_fn(self._format_table(res))
                elif res is not None:
                    output_fn(repr(res))
            except SyntaxError:
                import contextlib
                import io

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(expr, {}, local_scope)
                out_val = buf.getvalue().rstrip()
                if out_val:
                    output_fn(out_val)

            # Model A registration: Only keep dataframes explicitly converted via .to_pytae()
            mutated = False
            # 1. Active table update: check if 'df' was modified or reassigned to a PytaeDataFrame
            current_df_val = local_scope.get("df")
            if isinstance(current_df_val, _BasePtAccessor):
                output_fn("pytae: active 'df' cannot be an accessor proxy. Use 'df = df.to_pytae()' to update active table.")
            elif (
                isinstance(current_df_val, (PytaeDataFrame, PytaeGroupedDataFrame))
                and current_df_val is not orig_df_obj
            ):
                new_pl = (
                    current_df_val._eager_df()
                    if hasattr(current_df_val, "_eager_df")
                    else current_df_val._df
                )
                if isinstance(new_pl, pl.LazyFrame):
                    new_pl = new_pl.collect()
                self.current_df = new_pl
                target_key = self.path_str or "df"
                self.tables[target_key] = new_pl
                output_fn(f"Updated active table '{target_key}' ({new_pl.shape[0]:,} rows x {new_pl.shape[1]} cols).")
                mutated = True

            # 2. Check for newly assigned or updated variables in local_scope
            for k, val in list(local_scope.items()):
                if k in ("df", "pldf", "pl", "pt", "DataFrame", "__builtins__"):
                    continue
                if isinstance(val, _BasePtAccessor):
                    output_fn(f"pytae: '{k}' is an accessor proxy, not a Pytae table. Use '{k} = {k}.to_pytae()' to register as a table.")
                elif isinstance(val, (PytaeDataFrame, PytaeGroupedDataFrame)):
                    if k in orig_table_instances and val is orig_table_instances[k]:
                        continue
                    new_pl = (
                        val._eager_df()
                        if hasattr(val, "_eager_df")
                        else val._df
                    )
                    if isinstance(new_pl, pl.LazyFrame):
                        new_pl = new_pl.collect()
                    self.variables.pop(k, None)
                    self.tables[k] = new_pl
                    self.table_sources[k] = "python"
                    action_word = "Updated" if k in orig_table_instances else "Registered"
                    output_fn(f"{action_word} table '{k}' ({new_pl.shape[0]:,} rows x {new_pl.shape[1]} cols).")
                    mutated = True

            if mutated:
                rec_entry = f"py\n{expr}\npy" if "\n" in expr else f"py {expr}"
                self._record_history(rec_entry)

        except Exception as exc:
            output_fn(f"pytae Python Error: {exc}")
        finally:
            # Model A: Immediately remove everything associated from RAM
            local_scope.clear()
            del local_scope
            _release_memory()

    def _run_pipeline_on_df(
        self,
        source_df: pl.DataFrame,
        tokens: list[str],
        output_fn: Callable[[str], None],
        *,
        quiet: bool = False,
    ) -> tuple[pl.DataFrame | None, list[float] | None, bool]:
        """Parse and run a CLI pipeline on source_df. Returns (res_df, durations, failed)."""
        from pytae.cli import (
            _normalize_cli_args,
            build_parser,
            parse_concat_arg,
            parse_filter,
            parse_join_arg,
            parse_rename,
            parse_select_spec,
        )

        try:
            subbed_tokens = [self._substitute_variables(t) for t in tokens]
        except KeyError as exc:
            if not quiet:
                output_fn(f"pytae: {exc}")
            return None, None, True

        exec_argv = _normalize_cli_args(["<memory>"] + subbed_tokens)
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
                return None, None, True
        except (argparse.ArgumentError, SystemExit) as exc:
            output_fn(f"pytae syntax error: {exc}")
            return None, None, True

        try:
            rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
            select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
            filter_specs = [parse_filter(raw) for raw in (args.filter or [])]
            mutate_specs = list(args.mutate or [])
            sql_specs = list(args.sql or [])
            join_specs = [parse_join_arg(raw) for raw in (args.join or [])]
            concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]
        except (argparse.ArgumentError, SystemExit, Exception) as exc:
            msg = str(exc)
            if msg and not quiet:
                if msg.startswith("-") or msg.startswith("pytae") or msg.startswith("invalid"):
                    output_fn(msg)
                else:
                    output_fn(f"pytae syntax error: {msg}")
            return None, None, True
        op_order = getattr(args, "op_order", [])

        cfg_kwargs: dict[str, Any] = {
            "tbl_rows": self.max_rows,
            "tbl_cols": self.max_cols if self.max_cols is not None else -1,
        }
        if self.float_precision is not None:
            cfg_kwargs["float_precision"] = self.float_precision
        if self.comma:
            cfg_kwargs["thousands_separator"] = True

        args._memory_df = source_df
        args.in_repl = True
        args.quiet = quiet
        args.output_fn = (lambda s: None) if quiet else output_fn

        has_action = bool(op_order) or any(
            [
                args.shape,
                args.cols,
                args.dtype,
                args.nulls,
                getattr(args, "schema", False),
                args.describe,
                args.glimpse,
                args.head is not None,
                args.tail is not None,
                args.sample is not None,
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

        has_output = getattr(args, "output", None) is not None
        if isinstance(source_df, pl.LazyFrame) and any(
            [
                getattr(args, "plot", None) is not None,
                getattr(args, "hist", None) is not None,
                getattr(args, "bar", None) is not None,
                getattr(args, "scatter", None) is not None,
                getattr(args, "corr", None) is not None,
            ]
        ):
            output_fn(
                "pytae: plotting commands cannot be run directly on lazy scanned tables.\n"
                "Materialize a sample or subset first with '-head [N] -collect' or '-collect'."
            )
            return None, None, True

        if has_output and (
            args.head is not None
            or args.tail is not None
            or args.describe
            or args.glimpse
            or getattr(args, "schema", False)
            or args.cols
            or args.dtype
            or args.nulls
            or args.sample is not None
        ):
            inspect_cmd = (
                f"-head {args.head}"
                if args.head is not None
                else f"-tail {args.tail}"
                if args.tail is not None
                else "-describe"
                if args.describe
                else "-glimpse"
                if args.glimpse
                else "-schema"
                if getattr(args, "schema", False)
                else "-cols"
                if args.cols
                else "-dtype"
                if args.dtype
                else "-nulls"
                if args.nulls
                else "-sample"
            )
            out_target = getattr(args, "output", "<path>")
            tbl = getattr(self, "path_str", None) or "df"
            output_fn(
                f"pytae: '{inspect_cmd.split()[0]}' is an interactive screen preview and does not save with '-o' directly.\n"
                f"To save this subset, assign it to a table first:\n"
                f"  k = {tbl} {inspect_cmd}\n"
                f"  k -o {out_target}"
            )
            return None, None, True

        runs = getattr(args, "time", None)
        durations: list[float] | None = None
        try:
            with pl.Config(**cfg_kwargs):
                if runs:
                    import time as _time

                    durations = []
                    failed = False
                    for run_idx in range(runs):
                        t0 = _time.perf_counter()
                        curr_args = args if (run_idx == 0 and not quiet) else argparse.Namespace(**vars(args))
                        if run_idx > 0 or quiet:
                            curr_args.output_fn = lambda s: None
                        failed = _process_path(
                            Path("<memory>"),
                            curr_args,
                            parser,
                            batch=True,
                            show_all=show_all if (run_idx == 0 and not quiet) else False,
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
                return None, None, True
            res_frame = getattr(args, "_result_frame", None)
            res_pl: pl.DataFrame | pl.LazyFrame | None = None
            if res_frame is not None:
                if isinstance(res_frame, pl.LazyFrame):
                    if isinstance(source_df, pl.LazyFrame):
                        res_pl = res_frame
                    else:
                        res_pl = res_frame.collect()
                elif isinstance(res_frame, pl.DataFrame):
                    res_pl = res_frame
                else:
                    res_pl = pl.from_pandas(res_frame)
            else:
                res_pl = source_df
            return res_pl, durations, False
        except (Exception, SystemExit) as exc:
            msg = str(exc)
            if msg and not quiet:
                if msg.startswith("-") or msg.startswith("pytae") or msg.startswith("invalid"):
                    output_fn(msg)
                else:
                    output_fn(f"pytae error: {msg}")
            return None, None, True

    def _eval_pipeline_df(
        self,
        source_df: pl.DataFrame,
        tokens: list[str],
        output_fn: Callable[[str], None] = print,
    ) -> tuple[pl.DataFrame | None, list[float] | None]:
        """Evaluate a pipeline on source_df without printing, returning (resulting_df, durations)."""
        res_pl, durations, failed = self._run_pipeline_on_df(source_df, tokens, output_fn, quiet=True)
        if failed:
            return None, None
        return res_pl, durations

    def _cmd_pipeline(self, line: str, tokens: list[str], output_fn: Callable[[str], None]) -> None:
        if self.current_df is None:
            output_fn("pytae: no dataset loaded. Load a dataset first with '<var> = <path.parquet>'.")
            return

        res_pl, durations, failed = self._run_pipeline_on_df(self.current_df, tokens, output_fn, quiet=False)
        if failed:
            output_fn("pytae: command failed with errors.")
            return

        if durations:
            from pytae.cli import _format_timing_summary

            output_fn(_format_timing_summary(durations))

        self._record_history(line)

    def _complete(self, text: str, state: int) -> str | None:
        """Readline tab-autocompletion callback."""
        if state == 0:
            line_buf = ""
            begidx = -1
            endidx = -1
            if readline is not None:
                try:
                    buf = readline.get_line_buffer()
                    if buf is not None:
                        line_buf = buf
                    b = readline.get_begidx()
                    if b is not None and isinstance(b, int):
                        begidx = b
                    e = readline.get_endidx()
                    if e is not None and isinstance(e, int):
                        endidx = e
                except Exception:
                    pass
            self._completion_matches = self._get_completions(text, line_buf, begidx, endidx)
        if state < len(self._completion_matches):
            return self._completion_matches[state]
        return None

    def _get_completions(
        self,
        text: str,
        line_buf: str = "",
        begidx: int = -1,
        endidx: int = -1,
    ) -> list[str]:
        """Compute candidate autocompletions based on context."""
        if begidx is not None and begidx >= 0:
            prefix = line_buf[:begidx]
        elif text and line_buf.endswith(text):
            prefix = line_buf[:-len(text)]
        else:
            prefix = line_buf

        prefix_tokens = prefix.strip().split()
        first_token = prefix_tokens[0].lower() if prefix_tokens else ""
        last_token = prefix_tokens[-1].lower() if prefix_tokens else ""

        # Variable reference completion (@var)
        if text.startswith("@"):
            return [f"@{v}" for v in self.variables.keys() if f"@{v}".startswith(text)]

        # Case: 'set ' configuration keys and values
        if first_token == "set":
            if last_token == "set":
                configs = [
                    "max_rows",
                    "max_cols",
                    "float_precision",
                    "comma",
                ]
                return [c for c in configs if c.startswith(text)]
            if "checkpoint_format" in [t.lower() for t in prefix_tokens]:
                return [fmt for fmt in ("ipc", "parquet", "arrow") if fmt.startswith(text)]
            if "comma" in [t.lower() for t in prefix_tokens]:
                return [opt for opt in ("on", "off") if opt.startswith(text)]
            if any(k in [t.lower() for t in prefix_tokens] for k in ("max_rows", "rows")):
                return [opt for opt in ("10", "20", "50", "100", "default") if opt.startswith(text)]
            if any(k in [t.lower() for t in prefix_tokens] for k in ("max_cols", "cols")):
                return [opt for opt in ("all", "default", "5", "10", "20") if opt.startswith(text)]
            if any(k in [t.lower() for t in prefix_tokens] for k in ("float_precision", "precision")):
                return [opt for opt in ("auto", "default", "2", "4", "6") if opt.startswith(text)]

        # Case 0b: 'export ' or 'save ' -> complete subcommands and paths
        if first_token in ("export", "save"):
            if len(prefix_tokens) == 1:
                opts = ["script", "clip"] + list(self.tables.keys())
                return [opt for opt in opts if opt.startswith(text)]
            if len(prefix_tokens) >= 2 and prefix_tokens[1].lower() in ("script", "code"):
                return _complete_paths(text)
            return _complete_paths(text)

        # Case 0c: 'help ' or '-help ' -> complete available topics and keywords
        if first_token in ("help", "-help"):
            from pytae.cli_help import KEYWORD_DOCS
            topics = sorted(list(KEYWORD_DOCS.keys()))
            return [t for t in topics if t.startswith(text)]

        # Case 1: Ingestion / Export / Path completion
        if last_token in ("load", "-o") or last_token.startswith("-o=") or prefix.rstrip().endswith("="):
            return _complete_paths(text)

        if text.startswith(("./", "../", "/", "~")):
            return _complete_paths(text)

        # Case 2: 'switch ' (or 'use ') -> complete table names
        if last_token in ("switch", "use"):
            return [t for t in self.tables if t.startswith(text)]

        # Case 3: 'rename ' -> complete table names (for first argument)
        if last_token == "rename":
            return [t for t in self.tables if t.startswith(text)]

        # Case 4: 'restore ' (or 'revert ', 'rollback ') -> complete checkpoint names
        if last_token in ("restore", "revert", "rollback"):
            return [c for c in self.checkpoints if c.startswith(text)]

        # Case 5: 'rm ' -> complete categories: table, checkpoint, var
        if last_token == "rm":
            return [opt for opt in ("table", "checkpoint", "var") if opt.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "rm" and prefix_tokens[-1].lower() == "table":
            options = ["*"] + list(self.tables.keys())
            return [t for t in options if t.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "rm" and prefix_tokens[-1].lower() == "checkpoint":
            options = ["*"] + list(self.checkpoints.keys())
            return [c for c in options if c.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "rm" and prefix_tokens[-1].lower() == "var":
            options = ["*"] + list(self.variables.keys())
            return [v for v in options if v.startswith(text)]

        # Case 5b: 'status ' -> complete subcommands: session, table, checkpoint, var, -v
        if last_token == "status":
            return [
                opt
                for opt in (
                    "session",
                    "table",
                    "checkpoint",
                    "var",
                    "-v",
                )
                if opt.startswith(text)
            ]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "status" and prefix_tokens[-1].lower() == "session":
            return [opt for opt in ("-v", "-verbose") if opt.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "status" and prefix_tokens[-1].lower() == "table":
            options = list(self.tables.keys()) + ["-v"]
            return [t for t in options if t.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "status" and prefix_tokens[-1].lower() == "checkpoint":
            options = list(self.checkpoints.keys()) + ["-v"]
            return [c for c in options if c.startswith(text)]
        if len(prefix_tokens) >= 2 and prefix_tokens[-2].lower() == "status" and prefix_tokens[-1].lower() == "var":
            options = list(self.variables.keys()) + ["-v"]
            return [v for v in options if v.startswith(text)]

        # Case 6: '-diff ' -> complete table names, checkpoint names, flags, or on= columns
        if first_token == "-diff":
            if prefix.rstrip().endswith("on=") or last_token in ("-on", "--on"):
                target_df = self.current_df
                if target_df is not None:
                    return [c for c in target_df.columns if c.startswith(text)]
            candidates = list(self.tables.keys()) + list(self.checkpoints.keys()) + ["-tol", "on="]
            return [c for c in candidates if c.startswith(text)]

        # Case 7: Flag completion (starts with '-')
        if text.startswith("-"):
            flags = [
                "-filter", "-select", "-mutate", "-arrange", "-group_by", "-by",
                "-summarize", "-count", "-slice", "-distinct", "-join", "-left_join",
                "-inner_join", "-outer_join", "-cross_join", "-semi_join", "-anti_join",
                "-pivot", "-pivot_longer", "-pivot_wider", "-unpivot",
                "-head", "-tail", "-sample", "-describe", "-glimpse", "-schema",
                "-columns", "-cols", "-info", "-shape", "-print", "-o", "-sort", "-where",
                "-drop", "-rename", "-relocate", "-tol", "-save", "-restore", "-time",
                "-dropna", "-fillna", "-sql", "-opts",
            ]
            return [f for f in flags if f.startswith(text)]

        # Case 10: Start of line (no prefix tokens)
        if not prefix_tokens:
            top_cmds = [
                "use", "diff", "rename", "rm", "status", "set", "load", "checkpoint", "restore",
                "reset", "history", "session", "sessions", "sql",
                "python", "exit", "quit", "help", "time",
                "clear",
                # Bare verbs
                "filter", "select", "mutate", "arrange", "group_by", "by", "summarize",
                "count", "slice", "distinct", "join", "pivot", "head", "tail", "sample",
                "describe", "glimpse", "schema", "columns", "info", "shape", "print",
            ]
            candidates = top_cmds + list(self.tables.keys())
            return [c for c in candidates if c.startswith(text)]

        # Case 11: SQL Context (Option A: only explicit table names and checkpoints, no magic aliases)
        if first_token in ("sql", "-sql") or "SELECT" in [t.upper() for t in prefix_tokens]:
            sql_keywords = [
                "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "JOIN",
                "LEFT JOIN", "INNER JOIN", "ON", "AS", "COUNT", "SUM", "AVG", "MIN", "MAX",
            ]
            sql_tables = list(self.tables.keys()) + list(self.checkpoints.keys())
            cols = []
            if self.current_df is not None:
                cols = list(self.current_df.columns)
            candidates = sql_keywords + sql_tables + cols
            return [c for c in candidates if c.lower().startswith(text.lower())]

        # Case 12: Pipeline context (columns of active or referenced table)
        target_df = self.current_df
        if prefix_tokens and prefix_tokens[0] in self.tables:
            target_df = self.tables[prefix_tokens[0]]

        matches: list[str] = []
        if target_df is not None:
            matches.extend([c for c in target_df.columns if c.startswith(text)])

        if last_token in ("-join", "-left_join", "-inner_join", "-outer_join", "-cross_join", "-semi_join", "-anti_join", "join"):
            matches.extend([t for t in self.tables if t.startswith(text)])

        return list(dict.fromkeys(matches))

    def run(
        self,
        input_fn: Callable[[str], str] | None = None,
        output_fn: Callable[[str], None] = print,
    ) -> Any:
        """Run the REPL interactive loop until user exits. Returns final active DataFrame."""
        _init_readline(self._complete, initial_history=self._raw_history)
        from pytae import __version__

        if self.current_df is not None:
            output_fn(REPL_BANNER_LOADED.format(version=__version__))
            active_alias = self.path_str or "df"
            output_fn(
                f"Loaded: {active_alias} ({self.current_df.shape[0]:,} rows x {self.current_df.shape[1]} cols)"
            )
        else:
            output_fn(REPL_BANNER.format(version=__version__))
            output_fn(
                "No initial dataset loaded. Use '<var> = <path>' (e.g. 'df = clip' or 'df = sample:penguins') to start."
            )
        is_redirected_input = False
        is_pty = False
        try:
            import stat

            mode = os.fstat(sys.stdin.fileno()).st_mode
            if stat.S_ISREG(mode):
                is_redirected_input = True
            elif sys.platform != "win32":
                is_redirected_input = not sys.stdin.isatty()
            elif stat.S_ISFIFO(mode):
                # On Windows: check if FIFO is an interactive mintty / msys pty pipe
                try:
                    import ctypes
                    import msvcrt

                    handle = msvcrt.get_osfhandle(sys.stdin.fileno())
                    buf = ctypes.create_unicode_buffer(512)
                    if ctypes.windll.kernel32.GetNamedPipeHandleStateW(
                        handle, None, None, None, None, buf, 512
                    ):
                        if "pty" in buf.value.lower():
                            is_pty = True
                except Exception:
                    pass
                is_redirected_input = not is_pty
        except Exception:
            pass

        git_bash_raw_active = False
        git_bash_orig_stty: str | None = None
        if sys.platform == "win32" and is_pty and not is_redirected_input:
            import subprocess

            stty_exe = shutil.which("stty")
            if stty_exe:
                try:
                    git_bash_orig_stty = subprocess.check_output([stty_exe, "-g"], text=True).strip()
                    subprocess.run(
                        [stty_exe, "-icanon", "-echo", "min", "1"],
                        check=True,
                        capture_output=True,
                    )
                    git_bash_raw_active = True
                except Exception:
                    git_bash_raw_active = False

        def _restore_git_bash() -> None:
            nonlocal git_bash_raw_active
            if git_bash_raw_active and git_bash_orig_stty:
                try:
                    import subprocess

                    stty_exe = shutil.which("stty")
                    if stty_exe:
                        subprocess.run([stty_exe, git_bash_orig_stty], capture_output=True)
                except Exception:
                    pass
                git_bash_raw_active = False

        if git_bash_raw_active:
            import atexit

            atexit.register(_restore_git_bash)

        if sys.platform == "win32" and not sys.stdin.isatty() and not is_redirected_input and not git_bash_raw_active:
            output_fn(
                "  (Tip: If running in Git Bash on Windows, run 'winpty pytae ...' for interactive arrow key navigation)"
            )
        output_fn("")

        def _pipe_has_input() -> bool:
            try:
                import ctypes
                import msvcrt

                handle = msvcrt.get_osfhandle(sys.stdin.fileno())
                avail = ctypes.c_ulong()
                if ctypes.windll.kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None):
                    return avail.value > 0
            except Exception:
                pass
            return False

        def _get_input(prompt_text: str) -> str:
            effective_prompt = "" if is_redirected_input else prompt_text
            if input_fn is not None:
                try:
                    return input_fn(effective_prompt)
                except TypeError:
                    return input_fn()  # type: ignore[call-arg]

            if sys.platform == "win32":
                if sys.stdin.isatty():
                    try:
                        return _win_console_input(
                            effective_prompt,
                            self._raw_history,
                            completer=self._complete,
                            completions_fn=self._get_completions,
                        )
                    except Exception:
                        pass
                elif git_bash_raw_active:
                    try:
                        return _win_console_input(
                            effective_prompt,
                            self._raw_history,
                            completer=self._complete,
                            completions_fn=self._get_completions,
                            read_char_fn=lambda: sys.stdin.read(1),
                            has_input_fn=_pipe_has_input,
                        )
                    except Exception:
                        pass
                if readline is not None:
                    try:
                        return input(effective_prompt)
                    except Exception:
                        pass
            return input(effective_prompt)

        multi_buffer: list[str] = []
        in_py_block = False

        try:
            while True:
                if in_py_block or multi_buffer:
                    prompt = "... "
                else:
                    prompt = self._build_prompt()

                try:
                    line = _get_input(prompt)
                    if (in_py_block or multi_buffer) and readline is not None and hasattr(readline, "remove_history_item"):
                        try:
                            cur_len = readline.get_current_history_length()
                            if cur_len > 0:
                                readline.remove_history_item(cur_len - 1)
                        except Exception:
                            pass
                except KeyboardInterrupt:
                    if multi_buffer and readline is not None and hasattr(readline, "remove_history_item"):
                        try:
                            cur_len = readline.get_current_history_length()
                            if cur_len > 0:
                                readline.remove_history_item(cur_len - 1)
                        except Exception:
                            pass
                    multi_buffer.clear()
                    in_py_block = False
                    output_fn("\n(KeyboardInterrupt - command cancelled)")
                    continue
                except EOFError:
                    if self.save_history_file:
                        self._export_session_history(self.save_history_file, output_fn)
                    output_fn("\nExiting pytae REPL.")
                    break

                # 1. Check if entering Python block mode (bare 'py' on empty buffer)
                if not multi_buffer and not in_py_block and line.strip() == "py":
                    in_py_block = True
                    if readline is not None and hasattr(readline, "remove_history_item"):
                        try:
                            cur_len = readline.get_current_history_length()
                            if cur_len > 0:
                                readline.remove_history_item(cur_len - 1)
                        except Exception:
                            pass
                    continue

                # 2. Inside Python block mode
                if in_py_block:
                    if line == "":
                        full_code = "\n".join(multi_buffer)
                        multi_buffer.clear()
                        in_py_block = False
                        if full_code.strip():
                            try:
                                should_continue = self.execute_line(f"py\n{full_code}", output_fn=output_fn)
                                if not should_continue:
                                    break
                            except KeyboardInterrupt:
                                output_fn("\n(KeyboardInterrupt - command cancelled)")
                            except (Exception, SystemExit) as exc:
                                if isinstance(exc, SystemExit) and exc.code in (0, None):
                                    break
                                msg = str(exc)
                                if msg:
                                    output_fn(f"pytae error: {msg}")
                        continue
                    multi_buffer.append(line)
                    continue

                # 3. Standard CLI multi-line buffer
                multi_buffer.append(line)
                accumulated = "\n".join(multi_buffer)
                if _is_multiline_complete(accumulated):
                    if len(multi_buffer) > 1 and readline is not None and hasattr(readline, "remove_history_item"):
                        try:
                            cur_len = readline.get_current_history_length()
                            if cur_len > 0:
                                readline.remove_history_item(cur_len - 1)
                        except Exception:
                            pass
                    multi_buffer.clear()
                    try:
                        should_continue = self.execute_line(accumulated, output_fn=output_fn)
                        if not should_continue:
                            break
                    except KeyboardInterrupt:
                        output_fn("\n(KeyboardInterrupt - command cancelled)")
                    except (Exception, SystemExit) as exc:
                        if isinstance(exc, SystemExit) and exc.code in (0, None):
                            break
                        msg = str(exc)
                        if msg:
                            if msg.startswith("-") or msg.startswith("pytae") or msg.startswith("invalid"):
                                output_fn(msg)
                            else:
                                output_fn(f"pytae error: {msg}")
        finally:
            _restore_git_bash()
            self._cleanup_empty_session_dirs()
            self._cleanup_cp_dir()
            # Release in-memory resources
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
    script: Path | str | None = None,
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
        Deprecated parameter retained for backwards compatibility.
    script : str | Path, optional
        Path to a .pt script file to execute and populate memory before prompt.

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
        script=script,
        **kwargs,
    )
    return runner.run()


def run_script_file(script_path_str: str, output_fn: Callable[[str], None] = print) -> int:
    """Execute a Pytae (.pt) script file line-by-line in batch headless mode.

    Parameters
    ----------
    script_path_str : str
        Path to the .pt script file.
    output_fn : Callable[[str], None], optional
        Function to handle output messages (defaults to print).

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on failure.
    """
    from pytae.cli_parsing import normalize_git_bash_path

    clean_path = normalize_git_bash_path(script_path_str.strip("'\""))
    script_path = Path(clean_path).resolve()
    if not script_path.exists():
        output_fn(f"pytae error: script file '{script_path_str}' not found.")
        return 1

    repl_inst = PytaeRepl()
    lines = script_path.read_text(encoding="utf-8").splitlines()
    in_py = False
    py_buffer: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "py":
            if not in_py:
                in_py = True
                py_buffer.clear()
            else:
                in_py = False
                py_code = "\n".join(py_buffer)
                py_buffer.clear()
                ok = repl_inst.execute_line(f"py\n{py_code}", output_fn=output_fn)
                if not ok:
                    return 1
            continue

        if in_py:
            py_buffer.append(line)
            continue

        ok = repl_inst.execute_line(stripped, output_fn=output_fn)
        if not ok:
            if stripped.lower().startswith("exit"):
                return 0
            return 1

    return 0
