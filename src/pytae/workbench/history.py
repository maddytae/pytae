"""CLI IPython history inspection, search, export, and cell-by-cell `-load` replay."""

from __future__ import annotations

import ast
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from pytae.workbench.core import Workbench
from pytae.workbench.export import _infer_restore_events
from pytae.workbench.system import (
    get_config_path,
    get_ipython_history_db,
    set_ipython_history_db,
)


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


def _read_ipython_session_info(db_path: Path, session_id: int) -> tuple[int, str, str, int] | None:
    """Return `(session_id, start_str, end_str, num_cmds)` for a given IPython session ID."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT session, start, end, COALESCE(num_cmds, 0) FROM sessions WHERE session = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return (int(row[0]), str(row[1] or ""), str(row[2] or ""), int(row[3]))
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


def _search_ipython_history(db_path: Path, query: str, limit: int = 50) -> list[tuple[int, int, str]]:
    """Case-insensitive substring search across all IPython sessions (newest first)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT session, line, source_raw FROM history "
            "WHERE LOWER(source_raw) LIKE ? "
            "ORDER BY session DESC, line ASC LIMIT ?",
            (f"%{query.lower()}%", limit),
        )
        return [(int(s), int(ln), str(src)) for s, ln, src in cur.fetchall() if src is not None]
    finally:
        conn.close()


def _resolve_session_id(session_spec: str | None, db_path: Path) -> int:
    """Resolve an absolute (`42`) or relative (`~1`, `~2`, `~0`) session spec to a session ID."""
    if session_spec is None or session_spec in ("~0", "~1"):
        recent = _read_ipython_sessions(db_path, limit=1)
        if not recent:
            raise ValueError("No IPython sessions found in history database.")
        return recent[0][0]
    if session_spec.startswith("~"):
        try:
            offset = int(session_spec[1:])
            if offset < 1:
                raise ValueError
        except ValueError:
            raise ValueError(f"invalid relative session {session_spec!r} (e.g. ~1 for latest)") from None
        recent = _read_ipython_sessions(db_path, limit=offset)
        if offset > len(recent):
            raise ValueError(f"relative session {session_spec!r} out of range (only {len(recent)} session(s) found)")
        return recent[offset - 1][0]
    try:
        return int(session_spec)
    except ValueError:
        raise ValueError(f"invalid session ID {session_spec!r}") from None


def _format_session_cells(session_id: int, cells: list[tuple[int, str]], info: tuple[int, str, str, int] | None) -> str:
    """Format a single session's raw cells in plain numbered text."""
    header_parts = [f"Session {session_id}"]
    if info and info[1]:
        header_parts.append(f"Started: {info[1][:19]}")
    header_parts.append(f"{len(cells)} cmd{'s' if len(cells) != 1 else ''}")
    lines = [" | ".join(header_parts), "-" * 80]
    max_line_no = max((ln for ln, _ in cells), default=1)
    width = len(str(max_line_no))
    pad = " " * (width + 4)
    for line_no, src in cells:
        src_lines = src.splitlines() or [""]
        lines.append(f"[{line_no:>{width}}] {src_lines[0]}")
        for cont in src_lines[1:]:
            lines.append(f"{pad}{cont}")
    return "\n".join(lines)


def _cells_from_notebook(path: Path) -> list[str]:
    """Extract non-empty code cells from a Jupyter `.ipynb` file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_cells = data.get("cells", []) if isinstance(data, dict) else []
    out: list[str] = []
    for cell in raw_cells:
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        code = "".join(src) if isinstance(src, list) else str(src)
        if code.strip():
            out.append(code.strip("\n"))
    return out


def _cells_from_python_script(path: Path) -> list[str]:
    """Split a `.py` script into logical top-level cells (grouping consecutive imports)."""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fallback for scripts containing IPython magics: split on blank lines
        blocks: list[str] = []
        cur: list[str] = []
        for ln in lines:
            if not ln.strip():
                if cur:
                    block = "\n".join(cur).strip()
                    if block and any(not b.strip().startswith("#") for b in cur):
                        blocks.append(block)
                    cur = []
            else:
                cur.append(ln)
        if cur:
            block = "\n".join(cur).strip()
            if block and any(not b.strip().startswith("#") for b in cur):
                blocks.append(block)
        return blocks

    cells: list[str] = []
    import_buf: list[str] = []
    for node in tree.body:
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", start + 1)
        snippet = "\n".join(lines[start:end]).strip("\n")
        if not snippet.strip():
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_buf.append(snippet)
        else:
            if import_buf:
                cells.append("\n".join(import_buf))
                import_buf = []
            cells.append(snippet)
    if import_buf:
        cells.append("\n".join(import_buf))
    return cells


def _build_ipython_replay_bootstrap(cells: list[str]) -> str:
    """Build a small bootstrap script that replays `cells` via IPython `run_cell(..., store_history=True)`."""
    payload = json.dumps(cells)
    return (
        "import json as _pytae_json\n"
        "_pytae_ip = get_ipython()\n"
        f"_pytae_cells = _pytae_json.loads({payload!r})\n"
        "for _pytae_cell in _pytae_cells:\n"
        "    _pytae_res = _pytae_ip.run_cell(_pytae_cell, store_history=True)\n"
        "    if getattr(_pytae_res, 'error_before_exec', None) is not None or getattr(_pytae_res, 'error_in_exec', None) is not None:\n"
        "        break\n"
        "for _pytae_k in ('_pytae_json', '_pytae_ip', '_pytae_cells', '_pytae_cell', '_pytae_res', '_pytae_k'):\n"
        "    globals().pop(_pytae_k, None)\n"
    )


def _default_ipython_launcher(script_path: Path) -> int:
    """Launch an interactive IPython session with `script_path` pre-executed."""
    res = subprocess.run([sys.executable, "-m", "IPython", "-i", str(script_path)])
    return int(res.returncode)


def launch_ipython_cells(
    cells: list[str],
    *,
    label: str,
    output_fn: Callable[[str], None] = print,
    launcher_fn: Callable[[Path], int] | None = None,
) -> int:
    """Launch interactive IPython replaying `cells` into `%history` via `run_cell(..., store_history=True)`."""
    if not cells:
        sys.stderr.write(f"pytae error: {label} has no runnable cells to load.\n")
        return 1
    bootstrap = _build_ipython_replay_bootstrap(cells)
    tmp_dir = Path(tempfile.mkdtemp(prefix="pytae_load_"))
    tmp_script = tmp_dir / "pytae_replay.py"
    try:
        tmp_script.write_text(bootstrap, encoding="utf-8")
        output_fn(f"Loading {label} ({len(cells)} cell(s)) into IPython...")
        launch = launcher_fn or _default_ipython_launcher
        return launch(tmp_script)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_cli_load(
    target: str,
    *,
    output_fn: Callable[[str], None] = print,
    launcher_fn: Callable[[Path], int] | None = None,
) -> int:
    """CLI handler for `pytae <script.py | notebook.ipynb> -load`."""
    path = Path(os.path.expanduser(target))
    if not path.exists():
        sys.stderr.write(f"pytae error: file not found: {path}\n")
        return 1
    suffix = path.suffix.lower()
    if suffix == ".ipynb":
        try:
            cells = _cells_from_notebook(path)
        except Exception as exc:
            sys.stderr.write(f"pytae error: failed to read notebook {path}: {exc}\n")
            return 1
    elif suffix == ".py":
        try:
            cells = _cells_from_python_script(path)
        except Exception as exc:
            sys.stderr.write(f"pytae error: failed to read script {path}: {exc}\n")
            return 1
    else:
        sys.stderr.write(f"pytae error: '-load' supports .py and .ipynb files, got {path.name!r}\n")
        return 1

    return launch_ipython_cells(cells, label=path.name, output_fn=output_fn, launcher_fn=launcher_fn)


def run_cli_history(
    argv: list[str],
    *,
    db_path: Path | None = None,
    output_fn: Callable[[str], None] = print,
    launcher_fn: Callable[[Path], int] | None = None,
) -> int:
    """CLI handler for `pytae -history`.

    Supports:
    - `pytae -history [-n N]`                              List recent IPython sessions
    - `pytae -history <id | ~N>`                           View session cells (plain formatted)
    - `pytae -history <id | ~N> -clean`                    Print cleaned/pruned Python to stdout
    - `pytae -history -search <term> [-n N]`               Search across all sessions
    - `pytae -history [id | ~N] -o <dest.py|dest.ipynb>`   Export cleaned script or notebook
    - `pytae -history [id | ~N] -load`                     Launch IPython with cleaned session loaded
    - `pytae -history -db <path>`                          One-off history SQLite DB override
    - `pytae -history -set-db <path | reset>`              Persist/reset history DB path in ~/.pytae/config.json
    """
    session_spec: str | None = None
    dest_path: str | None = None
    search_query: str | None = None
    clean_view = False
    load_session = False
    relative_paths = False
    limit: int | None = None
    cli_db_override: Path | None = None
    set_db_target: str | None = None
    has_set_db = False

    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("-n", "--n", "-limit"):
            if i + 1 >= len(argv):
                sys.stderr.write(f"pytae error: '{tok}' requires a positive integer (e.g. -n 50)\n")
                return 1
            try:
                val = int(argv[i + 1])
                if val <= 0:
                    raise ValueError
            except ValueError:
                sys.stderr.write(f"pytae error: '{tok}' must be a positive integer, got {argv[i + 1]!r}\n")
                return 1
            limit = val
            i += 2
        elif tok.startswith("-n="):
            raw_n = tok.split("=", 1)[1]
            try:
                val = int(raw_n)
                if val <= 0:
                    raise ValueError
            except ValueError:
                sys.stderr.write(f"pytae error: '-n' must be a positive integer, got {raw_n!r}\n")
                return 1
            limit = val
            i += 1
        elif tok in ("-clean", "--clean"):
            clean_view = True
            i += 1
        elif tok in ("-load", "--load"):
            load_session = True
            i += 1
        elif tok in ("-relative", "--relative"):
            relative_paths = True
            i += 1
        elif tok in ("-search", "--search", "-g"):
            if i + 1 >= len(argv):
                sys.stderr.write(f"pytae error: '{tok}' requires a search term (e.g. -search \"penguins\")\n")
                return 1
            search_query = argv[i + 1]
            i += 2
        elif tok.startswith("-search="):
            search_query = tok.split("=", 1)[1]
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
        elif tok in ("-db", "--db"):
            if i + 1 >= len(argv):
                sys.stderr.write("pytae error: '-db' requires a path to an IPython history.sqlite file\n")
                return 1
            cli_db_override = Path(argv[i + 1]).expanduser()
            i += 2
        elif tok.startswith("-db="):
            cli_db_override = Path(tok.split("=", 1)[1]).expanduser()
            i += 1
        elif tok in ("-set-db", "--set-db", "-set_db"):
            if i + 1 >= len(argv):
                sys.stderr.write("pytae error: '-set-db' requires a path or 'reset'\n")
                return 1
            set_db_target = argv[i + 1]
            has_set_db = True
            i += 2
        elif tok.startswith(("-set-db=", "-set_db=")):
            set_db_target = tok.split("=", 1)[1]
            has_set_db = True
            i += 1
        elif tok.endswith((".sqlite", ".db")) and cli_db_override is None:
            cli_db_override = Path(tok).expanduser()
            i += 1
        elif session_spec is None and not tok.startswith("-"):
            if load_session:
                sys.stderr.write(
                    f"pytae error: put the session ID before '-load' (e.g. pytae -history {tok} -load)\n"
                )
                return 1
            session_spec = tok
            i += 1
        else:
            sys.stderr.write(f"pytae error: unrecognized argument for -history: {tok!r}\n")
            return 1

    # Handle persistent DB path configuration (`pytae -history -set-db <path | reset>`)
    if has_set_db:
        resolved_db, is_reset = set_ipython_history_db(set_db_target)
        if is_reset:
            output_fn(f"History DB path reset to default: {resolved_db}")
        else:
            output_fn(f"Saved history DB path to {get_config_path()}: {resolved_db}")
        return 0

    if load_session and dest_path is not None:
        sys.stderr.write("pytae error: '-load' and '-o' cannot be used together\n")
        return 1

    hist_db = cli_db_override or db_path or get_ipython_history_db()
    if not hist_db.exists():
        sys.stderr.write(f"pytae error: IPython history database not found at {hist_db}\n")
        return 1

    # Search mode: `pytae -history -search <term> [-n N]`
    if search_query is not None:
        if not search_query.strip():
            sys.stderr.write("pytae error: search term cannot be empty\n")
            return 1
        matches = _search_ipython_history(hist_db, search_query, limit=limit or 50)
        if not matches:
            output_fn(f"No history entries matching {search_query!r}.")
            return 0
        for sess_id, line_no, src in matches:
            first_line = " ".join(ln.strip() for ln in src.splitlines() if ln.strip())
            output_fn(f"{sess_id}/{line_no}  {first_line}")
        return 0

    # List mode: bare `pytae -history [-n N]` (no session spec, no -o, no -load, no -clean)
    if session_spec is None and dest_path is None and not load_session and not clean_view:
        sessions = _read_ipython_sessions(hist_db, limit=limit or 25)
        if not sessions:
            output_fn("No IPython sessions found in history database.")
            return 0
        output_fn(f"IPython History ({hist_db}):")
        output_fn(f"{'Session':>8}  {'Started':<19}  {'Cmds':>5}  Preview")
        output_fn("-" * 80)
        for sess_id, start_ts, num_cmds, preview in sessions:
            output_fn(f"{sess_id:>8}  {start_ts[:19]:<19}  {num_cmds:>5}  {preview}")
        return 0

    # Single-session operations: view, -clean, -o (export), or -load
    try:
        target_session = _resolve_session_id(session_spec, hist_db)
    except ValueError as exc:
        sys.stderr.write(f"pytae error: {exc}\n")
        return 1

    cells = _read_ipython_session_cells(hist_db, target_session)
    if not cells:
        sys.stderr.write(f"pytae error: session {target_session} has no recorded commands.\n")
        return 1

    # Plain raw view: `pytae -history 42`
    if dest_path is None and not clean_view and not load_session:
        info = _read_ipython_session_info(hist_db, target_session)
        output_fn(_format_session_cells(target_session, cells, info))
        return 0

    wb = Workbench(load_config=False)
    try:
        failed, restores = Workbench.load_session_meta(target_session)
        wb.failed_cells = failed
        wb.restore_events = restores or _infer_restore_events(cells)

        # Export to .py / .ipynb: `pytae -history 42 -o out.py`
        if dest_path is not None:
            msg = wb.export_session(dest_path, cells, relative_paths=relative_paths)
            output_fn(f"[session {target_session}] {msg}")
            return 0

        # Preview cleaned Python: `pytae -history 42 -clean`
        if clean_view and not load_session:
            script, _kept_count, _pruned = wb.build_clean_session_script(cells)
            output_fn(script.rstrip("\n"))
            return 0

        # Load cleaned session into interactive IPython cell-by-cell (`store_history=True`)
        replay_cells, _pruned = wb.build_clean_session_cells(cells)
        return launch_ipython_cells(
            replay_cells,
            label=f"session {target_session}",
            output_fn=output_fn,
            launcher_fn=launcher_fn,
        )
    finally:
        wb.cleanup()
