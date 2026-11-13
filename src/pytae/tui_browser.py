"""Terminal-native interactive data grid browser for pytae datasets."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any, Callable

import polars as pl


def browse_dataframe(
    df: Any,
    title: str = "pytae browser",
    output_fn: Callable[[str], None] = print,
    *,
    input_fn: Callable[[], str] | None = None,
) -> None:
    """Launch full-screen alternate buffer interactive terminal data browser.

    Parameters
    ----------
    df : Any
        DataFrame to browse (Polars or Pytae DataFrame).
    title : str
        Header banner title or active table alias.
    output_fn : Callable[[str], None]
        Output function fallback when running non-interactively.
    input_fn : Callable[[], str] | None
        Key read function (used for testing and custom event pumps).
    """
    if df is None:
        output_fn("pytae browser: no data to browse.")
        return

    # Extract underlying Polars DataFrame
    raw_df: pl.DataFrame
    if isinstance(df, pl.DataFrame):
        raw_df = df
    elif isinstance(df, pl.LazyFrame):
        raw_df = df.collect()
    elif hasattr(df, "to_polars"):
        raw_df = df.to_polars()
    elif hasattr(df, "_df") and isinstance(df._df, pl.DataFrame):
        raw_df = df._df
    elif hasattr(df, "_eager_df"):
        raw_df = df._eager_df()
    else:
        try:
            raw_df = pl.DataFrame(df)
        except Exception as exc:
            output_fn(f"pytae browser error: cannot convert object to table: {exc}")
            return

    total_rows, total_cols = raw_df.shape
    if total_rows == 0 or total_cols == 0:
        output_fn(f"{title}: empty table (0 rows x {total_cols} cols)")
        return

    # Fallback to standard head preview if stdout or stdin is not an interactive terminal
    if input_fn is None and (not sys.stdout.isatty() or not sys.stdin.isatty()):
        output_fn(f"--- {title} ({total_rows:,} rows x {total_cols} cols) ---")
        output_fn(str(raw_df.head(50)))
        return

    # Working copy for sorting/filtering inside browser
    display_df = raw_df
    sort_col: str | None = None
    sort_descending: bool = False

    row_offset = 0
    col_offset = 0
    selected_col_idx = 0

    # Character reading setup
    fd: int | None = None
    old_termios: Any = None

    if input_fn is None:
        if sys.platform != "win32":
            try:
                import termios
                import tty

                fd = sys.stdin.fileno()
                old_termios = termios.tcgetattr(fd)
                tty.setcbreak(fd, when=termios.TCSADRAIN)

                def _read_key() -> str:
                    assert fd is not None
                    ch = os.read(fd, 1).decode("latin1")
                    if ch == "\x1b":
                        import select

                        if select.select([fd], [], [], 0.05)[0]:
                            seq = os.read(fd, 4).decode("latin1")
                            if seq == "[A":
                                return "up"
                            if seq == "[B":
                                return "down"
                            if seq == "[C":
                                return "right"
                            if seq == "[D":
                                return "left"
                            if seq in ("[5~", "[I"):
                                return "page_up"
                            if seq in ("[6~", "[G"):
                                return "page_down"
                            if seq == "[H":
                                return "home"
                            if seq == "[F":
                                return "end"
                            return "esc"
                        return "esc"
                    if ch == "\r" or ch == "\n":
                        return "enter"
                    if ch == "\x03":
                        return "ctrl_c"
                    return ch

                get_key = _read_key
            except Exception:
                output_fn(str(raw_df.head(50)))
                return
        else:
            try:
                import msvcrt

                def _win_read_key() -> str:
                    ch = msvcrt.getch()
                    if ch in (b"\x00", b"\xe0"):
                        ch2 = msvcrt.getch()
                        mapping = {
                            b"H": "up",
                            b"P": "down",
                            b"M": "right",
                            b"K": "left",
                            b"I": "page_up",
                            b"Q": "page_down",
                            b"G": "home",
                            b"O": "end",
                        }
                        return mapping.get(ch2, "")
                    if ch in (b"\r", b"\n"):
                        return "enter"
                    if ch == b"\x1b":
                        return "esc"
                    if ch == b"\x03":
                        return "ctrl_c"
                    return ch.decode("latin1", "replace")

                get_key = _win_read_key
            except Exception:
                output_fn(str(raw_df.head(50)))
                return
    else:
        get_key = input_fn

    try:
        # Enter alternate screen buffer, clear screen, hide cursor
        sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[?25l")
        sys.stdout.flush()

        while True:
            term_size = shutil.get_terminal_size((80, 24))
            term_w = max(40, term_size.columns)
            term_h = max(10, term_size.lines)

            # Available rows for data rows:
            # Term height minus Title (1), Header (1), Dtype (1), Divider (1), Status Bar (1), Prompt Help (1)
            visible_data_rows = max(3, term_h - 6)

            # Bounds check offsets
            max_row_offset = max(0, total_rows - visible_data_rows)
            row_offset = max(0, min(row_offset, max_row_offset))

            selected_col_idx = max(0, min(selected_col_idx, total_cols - 1))
            if selected_col_idx < col_offset:
                col_offset = selected_col_idx

            # Calculate visible column slice based on terminal width
            idx_w = len(f"{total_rows:,}") + 2
            rem_w = term_w - idx_w - 2

            col_names = display_df.columns
            col_widths: list[int] = []
            visible_cols: list[int] = []

            curr_w = 0
            for c_idx in range(col_offset, total_cols):
                c_name = col_names[c_idx]
                # Column width heuristic: max of name length and standard data snippet
                cw = max(len(c_name), 10) + 2
                if curr_w + cw > rem_w and visible_cols:
                    break
                visible_cols.append(c_idx)
                col_widths.append(cw)
                curr_w += cw

            if selected_col_idx >= col_offset + len(visible_cols) and visible_cols:
                col_offset = selected_col_idx - len(visible_cols) + 1
                visible_cols = []
                col_widths = []
                curr_w = 0
                for c_idx in range(col_offset, total_cols):
                    c_name = col_names[c_idx]
                    cw = max(len(c_name), 10) + 2
                    if curr_w + cw > rem_w and visible_cols:
                        break
                    visible_cols.append(c_idx)
                    col_widths.append(cw)
                    curr_w += cw

            # Slice current visible viewport chunk
            chunk = display_df.slice(row_offset, visible_data_rows)

            # Render Screen Buffer
            out: list[str] = ["\x1b[H"]  # Move to Top-Left (1,1)

            # 1. Header Banner
            sort_label = (
                f" | Sort: {sort_col} ({'desc' if sort_descending else 'asc'})"
                if sort_col
                else " | Natural Order"
            )
            banner = f" PYTAE WORKBENCH BROWSER :: {title} ({total_rows:,} rows x {total_cols} cols){sort_label}"
            out.append(f"\x1b[7m{banner.ljust(term_w)[:term_w]}\x1b[0m\n")

            # 2. Sticky Header Columns
            idx_header = "#".rjust(idx_w)
            header_parts = [f"\x1b[90m{idx_header}\x1b[0m"]
            dtype_parts = [f"\x1b[90m{''.rjust(idx_w)}\x1b[0m"]

            for i, c_idx in enumerate(visible_cols):
                c_name = col_names[c_idx]
                c_dtype = str(display_df.schema[c_name])
                cw = col_widths[i]
                is_selected = c_idx == selected_col_idx
                sort_mark = ""
                if c_name == sort_col:
                    sort_mark = "▼" if sort_descending else "▲"

                disp_name = (c_name + sort_mark).ljust(cw)[:cw]
                disp_dtype = f"({c_dtype})".ljust(cw)[:cw]

                if is_selected:
                    header_parts.append(f"\x1b[1;30;46m{disp_name}\x1b[0m")
                    dtype_parts.append(f"\x1b[36m{disp_dtype}\x1b[0m")
                else:
                    header_parts.append(f"\x1b[1;37m{disp_name}\x1b[0m")
                    dtype_parts.append(f"\x1b[90m{disp_dtype}\x1b[0m")

            out.append(" ".join(header_parts) + "\n")
            out.append(" ".join(dtype_parts) + "\n")
            out.append(f"\x1b[90m{'─' * term_w}\x1b[0m\n")

            # 3. Data Rows
            chunk_rows = chunk.shape[0]
            for r_idx in range(visible_data_rows):
                if r_idx < chunk_rows:
                    abs_row_idx = row_offset + r_idx + 1
                    row_parts = [f"\x1b[90m{str(abs_row_idx).rjust(idx_w)}\x1b[0m"]
                    for i, c_idx in enumerate(visible_cols):
                        c_name = col_names[c_idx]
                        cw = col_widths[i]
                        val = chunk[c_name][r_idx]
                        val_str = "null" if val is None else str(val)
                        disp_val = val_str.ljust(cw)[:cw]
                        if c_idx == selected_col_idx:
                            row_parts.append(f"\x1b[36m{disp_val}\x1b[0m")
                        elif val is None:
                            row_parts.append(f"\x1b[90m{disp_val}\x1b[0m")
                        else:
                            row_parts.append(disp_val)
                    out.append(" ".join(row_parts) + "\n")
                else:
                    out.append(f"\x1b[90m{'~'.rjust(idx_w)}\x1b[0m\n")

            # 4. Status Bar & Key Help
            cur_col_name = col_names[selected_col_idx]
            cur_dtype = str(display_df.schema[cur_col_name])
            row_end = min(total_rows, row_offset + chunk_rows)
            status_line = (
                f" Rows: {row_offset + 1:,}–{row_end:,} of {total_rows:,} | "
                f"Col [{selected_col_idx + 1}/{total_cols}]: '{cur_col_name}' ({cur_dtype})"
            )
            out.append(f"\x1b[7m{status_line.ljust(term_w)[:term_w]}\x1b[0m\n")

            help_line = " [↑/↓/j/k]: Row | [←/→/h/l]: Col | [s]: Sort | [r]: Reset Sort | [q/Esc]: Exit"
            out.append(f"\x1b[90m{help_line.ljust(term_w)[:term_w]}\x1b[0m")

            sys.stdout.write("".join(out))
            sys.stdout.flush()

            # Handle Keyboard Input
            key = get_key()
            if key in ("q", "Q", "esc", "ctrl_c"):
                break
            elif key in ("down", "j", "J"):
                row_offset = min(max_row_offset, row_offset + 1)
            elif key in ("up", "k", "K"):
                row_offset = max(0, row_offset - 1)
            elif key in ("page_down", " ", "d"):
                row_offset = min(max_row_offset, row_offset + visible_data_rows)
            elif key in ("page_up", "u"):
                row_offset = max(0, row_offset - visible_data_rows)
            elif key in ("home", "g"):
                row_offset = 0
            elif key in ("end", "G"):
                row_offset = max_row_offset
            elif key in ("right", "l", "L", "\t"):
                if selected_col_idx < total_cols - 1:
                    selected_col_idx += 1
            elif key in ("left", "h", "H"):
                if selected_col_idx > 0:
                    selected_col_idx -= 1
            elif key in ("s", "S"):
                # Multi-column sort toggle
                target_col = col_names[selected_col_idx]
                if sort_col == target_col:
                    if not sort_descending:
                        sort_descending = True
                        display_df = raw_df.sort(target_col, descending=True)
                    else:
                        sort_col = None
                        sort_descending = False
                        display_df = raw_df
                else:
                    sort_col = target_col
                    sort_descending = False
                    display_df = raw_df.sort(target_col, descending=False)
                row_offset = 0
            elif key in ("r", "R"):
                # Reset sort
                sort_col = None
                sort_descending = False
                display_df = raw_df
                row_offset = 0

    finally:
        # Restore main screen buffer and show cursor
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
        if fd is not None and old_termios is not None:
            try:
                import termios

                termios.tcsetattr(fd, termios.TCSADRAIN, old_termios)
            except Exception:
                pass
