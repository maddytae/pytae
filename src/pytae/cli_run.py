"""Execute one CLI pipeline: display/convert/agg ops against a file or named frames."""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from pytae.agg import agg
from pytae.cli_parsing import (
    parse_agg,
    parse_clean_columns_arg,
    parse_columns,
    parse_kv_spec,
    parse_long_arg,
    parse_pivot_arg,
    parse_wide_arg,
    unknown_columns_message,
)
from pytae.cli_pipeline import _Pipeline
from pytae.other_utilities import clean_columns, handle_missing
from pytae.readers import (
    DataFrameReader,
    StdinReader,
    _split_path_suffixes,
    get_reader,
    write_dataframe,
)


def _apply_round(df: pd.DataFrame, ndigits: int | None) -> pd.DataFrame:
    """Round numeric columns to ndigits; non-numeric columns pass through unchanged."""
    return df.round(ndigits) if ndigits is not None else df


def _dataframe_info(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.info(buf=buf)
    return buf.getvalue().rstrip()


def _format_table(df: pd.DataFrame, *, index: bool | None = None, pretty: bool = False) -> str:
    """Render a DataFrame as standard pandas text, or a markdown/bordered table when pretty=True."""
    if index is None:
        index = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
    if not pretty:
        return df.to_string(index=index)
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return df.to_string(index=index)


def _compute_freq(source_df: pd.DataFrame, col: str | None, dropna: bool) -> pd.DataFrame:
    if col is None:
        if len(source_df.columns) == 1:
            col = source_df.columns[0]
        else:
            raise SystemExit("-freq: requires a column name (or a single-column DataFrame)")
    col = col.strip()
    if col not in source_df.columns:
        raise SystemExit(unknown_columns_message("-freq", [col], list(source_df.columns)))

    counts = source_df[col].value_counts(dropna=dropna)
    total = counts.sum()
    max_cnt = counts.max() if not counts.empty else 1
    bar_max_width = 20
    data = []
    for category, count in counts.items():
        bar_len = int(round((count / max_cnt) * bar_max_width)) if max_cnt > 0 else 0
        bar_str = "█" * bar_len
        pct_str = f"({(count / total * 100):.1f}%)" if total > 0 else "(0.0%)"
        dist_str = f"{bar_str} {pct_str}".strip()
        data.append({col: str(category), "Count": count, "Distribution": dist_str})
    return pd.DataFrame(data)


def _compute_hist(source_df: pd.DataFrame, hist_arg: str | None) -> pd.DataFrame:
    raw = (hist_arg or "").strip()
    bins = 10
    col = None
    if ":" in raw:
        col_part, _, b_str = raw.partition(":")
        col = col_part.strip()
        try:
            bins = int(b_str.strip())
        except ValueError:
            pass
    elif "," in raw and "bins=" in raw:
        col_part, _, b_part = raw.partition(",")
        col = col_part.strip()
        b_str = b_part.replace("bins=", "").strip()
        try:
            bins = int(b_str)
        except ValueError:
            pass
    elif raw:
        col = raw
    else:
        if len(source_df.columns) == 1:
            col = source_df.columns[0]
        else:
            raise SystemExit("-hist: requires a column name (e.g. -hist mass or -hist mass:10)")

    if col not in source_df.columns:
        raise SystemExit(unknown_columns_message("-hist", [col], list(source_df.columns)))

    s = pd.to_numeric(source_df[col], errors="coerce").dropna()
    if s.empty:
        return pd.DataFrame(columns=["Range", "Count", "Distribution"])

    cut_series = pd.cut(s, bins=bins, include_lowest=True)
    counts = cut_series.value_counts(sort=False)
    total = len(s)
    max_cnt = counts.max() if not counts.empty else 1
    bar_max_width = 20
    data = []
    for interval, count in counts.items():
        bar_len = int(round((count / max_cnt) * bar_max_width)) if max_cnt > 0 else 0
        bar_str = "█" * bar_len
        pct_str = f"({(count / total * 100):.1f}%)" if total > 0 else "(0.0%)"
        dist_str = f"{bar_str} {pct_str}".strip()
        left_fmt = f"{interval.left:.2f}".rstrip("0").rstrip(".")
        right_fmt = f"{interval.right:.2f}".rstrip("0").rstrip(".")
        range_str = f"[{left_fmt}, {right_fmt}]"
        data.append({"Range": range_str, "Count": count, "Distribution": dist_str})
    return pd.DataFrame(data)



def _copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard via pbcopy/clip/xclip; warns on stderr if none is available."""
    if sys.platform == "darwin":
        cmd = ["pbcopy"]
    elif sys.platform == "win32":
        cmd = ["clip"]
    else:
        cmd = ["xclip", "-selection", "clipboard"]
    try:
        subprocess.run(cmd, input=text.encode(), check=True)
    except (OSError, subprocess.CalledProcessError):
        print("pytae: unable to copy to clipboard (no clipboard utility found)", file=sys.stderr)


def _output_text(text: str, args: argparse.Namespace) -> None:
    """Output text to stdout, piping through pydoc.pager if -pager is requested."""
    if getattr(args, "pager", False):
        import pydoc

        pydoc.pager(text)
    else:
        print(text)


def _format_bytes(num: int | float) -> str:
    """Format byte counts into human-readable strings (e.g. 1.2 KB, 3.4 MB)."""
    val = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(val) < 1024.0:
            return f"{val:3.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} PB"


def _extract_metadata(path: Path, *, sep: str | None = None, encoding: str | None = None) -> str:
    """Extract file metadata without scanning full row data (fastest on Parquet)."""
    if not path.exists():
        return f"File not found: {path}"
    suffix, compression = _split_path_suffixes(path)
    file_bytes = path.stat().st_size
    lines: list[str] = [f"File: {path.name}", f"File size: {_format_bytes(file_bytes)}"]
    if suffix in (".parquet", ".pq"):
        try:
            import pyarrow.parquet as pa_parquet

            pf = pa_parquet.ParquetFile(path)
            md = pf.metadata
            lines.append(f"Format: Parquet (version {md.format_version})")
            lines.append(f"Rows: {md.num_rows:,}")
            lines.append(f"Columns: {md.num_columns}")
            lines.append(f"Row groups: {md.num_row_groups}")
            codecs: set[str] = set()
            total_uncompressed = 0
            for j in range(md.num_row_groups):
                rg = md.row_group(j)
                total_uncompressed += rg.total_byte_size
                for i in range(md.num_columns):
                    codecs.add(str(rg.column(i).compression))
            codec_str = ", ".join(sorted(codecs)) if codecs else "None"
            lines.append(f"Compression: {codec_str}")
            lines.append(f"Uncompressed data size: {_format_bytes(total_uncompressed)}")
            ratio = (file_bytes / total_uncompressed * 100) if total_uncompressed else 100
            lines.append(f"Space saving: {100 - ratio:.1f}%")
            lines.append("")
            lines.append("Schema:")
            schema = pf.schema_arrow
            max_name_len = max(len(name) for name in schema.names) if schema.names else 10
            lines.append(f"  {'#':<4} {'Column':<{max_name_len}}  {'Type'}")
            lines.append(f"  {'-'*4} {'-'*max_name_len}  {'-'*20}")
            for idx, field in enumerate(schema):
                lines.append(f"  {idx:<4} {field.name:<{max_name_len}}  {field.type}")
        except Exception as exc:
            lines.append(f"Error reading Parquet metadata: {exc}")
    else:
        fmt_name = "CSV" if suffix == ".csv" else ("JSON Lines" if suffix in (".jsonl", ".ndjson") else suffix.lstrip(".").upper())
        comp_str = f" ({compression})" if compression else ""
        lines.append(f"Format: {fmt_name}{comp_str}")
        try:
            reader = get_reader(path, sep=sep, encoding=encoding)
            cols = reader.columns()
            lines.append(f"Columns: {len(cols)}")
            lines.append(f"Column names: {', '.join(cols[:15])}{'...' if len(cols) > 15 else ''}")
        except UnicodeError as exc:
            lines.append(f"Error reading encoding: {_encoding_error_message(path, encoding, exc)}")
        except Exception as exc:
            lines.append(f"Error reading column info: {exc}")
    return "\n".join(lines)


def _compute_diff(
    left_df: pd.DataFrame,
    right_path: Path,
    left_name: str,
    *,
    sep: str | None = None,
    encoding: str | None = None,
) -> str:
    """Compare the current pipeline result against another tabular file."""
    if not right_path.exists():
        return f"Diff target not found: {right_path}"
    try:
        reader = get_reader(right_path, sep=sep, encoding=encoding)
        right_df = reader.to_dataframe()
    except UnicodeError as exc:
        return _encoding_error_message(right_path, encoding, exc)
    except Exception as exc:
        return f"Cannot read diff target '{right_path}': {exc}"

    r1, c1 = left_df.shape
    r2, c2 = right_df.shape
    cols1 = list(left_df.columns)
    cols2 = list(right_df.columns)

    lines: list[str] = [
        "Comparing:",
        f"  Left (source):  {left_name} ({r1:,} rows, {c1} cols)",
        f"  Right (target): {right_path.name} ({r2:,} rows, {c2} cols)",
        "",
        "Shape:",
        f"  Rows: {r1:,} vs {r2:,} ({'+' if r1 >= r2 else ''}{r1 - r2:,})",
        f"  Cols: {c1} vs {c2} ({'+' if c1 >= c2 else ''}{c1 - c2})",
    ]

    added_cols = [c for c in cols1 if c not in cols2]
    removed_cols = [c for c in cols2 if c not in cols1]
    common_cols = [c for c in cols1 if c in cols2]

    lines.append("")
    lines.append("Columns:")
    if added_cols:
        lines.append(f"  + Added in left ({len(added_cols)}):   {', '.join(added_cols)}")
    if removed_cols:
        lines.append(f"  - Removed in left ({len(removed_cols)}): {', '.join(removed_cols)}")
    lines.append(f"  Common ({len(common_cols)}):        {', '.join(common_cols)}")

    dtype_diffs: list[str] = []
    for c in common_cols:
        d1 = str(left_df[c].dtype)
        d2 = str(right_df[c].dtype)
        if d1 != d2:
            dtype_diffs.append(f"  * {c}: {d2} (right) -> {d1} (left)")

    lines.append("")
    lines.append("Schema Drift:")
    if dtype_diffs:
        lines.extend(dtype_diffs)
    else:
        lines.append("  None (all common columns have matching dtypes)")

    null_diffs: list[str] = []
    for c in common_cols:
        n1 = int(left_df[c].isna().sum())
        n2 = int(right_df[c].isna().sum())
        if n1 != n2:
            null_diffs.append(f"  * {c}: {n1:,} vs {n2:,} nulls ({'+' if n1 >= n2 else ''}{n1 - n2:,})")

    if null_diffs:
        lines.append("")
        lines.append("Null Counts:")
        lines.extend(null_diffs)

    if r1 == r2 and common_cols:
        try:
            mismatches = 0
            for c in common_cols:
                s1 = left_df[c]
                s2 = right_df[c]
                diff = ~((s1 == s2) | (s1.isna() & s2.isna()))
                mismatches += int(diff.sum())
            lines.append("")
            lines.append("Values:")
            if mismatches == 0 and cols1 == cols2:
                lines.append("  Identical: all cell values match exactly.")
            elif mismatches == 0:
                lines.append("  Matching: all cell values in common columns match.")
            else:
                lines.append(f"  Mismatches found in {mismatches:,} cells across common columns.")
        except Exception:
            pass

    return "\n".join(lines)


# Ops whose pandas equivalent does not return a DataFrame (shape -> tuple, cols -> Index,
# dtype -> Series, nulls -> Series, info() -> None, meta -> str, diff -> str). Like real method
# chaining, nothing can follow them except -o clip.
NON_DF_TERMINAL_OPS = frozenset({"shape", "cols", "dtype", "nulls", "info", "meta", "diff", "glimpse"})


def _list_order_names(names, order):
    if order == "asc":
        return sorted(names)
    if order == "desc":
        return sorted(names, reverse=True)
    return list(names)



def _list_order_index(series: pd.Series, order) -> pd.Series:
    if order == "asc":
        return series.sort_index(ascending=True)
    if order == "desc":
        return series.sort_index(ascending=False)
    return series





def cmd_convert(
    df: pd.DataFrame,
    source: Path,
    output: Path | None,
    *,
    rename: dict[str, str] | None = None,
    sep: str | None = None,
    encoding: str | None = None,
    progress: bool = False,
    announce: bool = True,
    chunk_size: int = 200_000,
    index: bool | None = None,
) -> None:
    if rename:
        df = df.rename(columns=rename)
    dest = output if output is not None else source.with_suffix(".csv")
    if dest.resolve() == source.resolve():
        raise SystemExit(
            f"refusing to overwrite the source file '{source}'; "
            f"specify a different format or an explicit path with -o/--output"
        )
    try:
        write_dataframe(df, dest, sep=sep, encoding=encoding, progress=progress, chunk_size=chunk_size, index=index)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if announce:
        print(f"Wrote {len(df)} rows to {dest}")


def _fail(parser: argparse.ArgumentParser, batch: bool, msg: str) -> bool:
    """Abort immediately outside batch mode; in batch mode, warn on stderr and signal failure instead."""
    if not batch:
        parser.error(msg)
    print(f"pytae: {msg}", file=sys.stderr)
    return True


_COMMON_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")


def _encoding_error_message(path: Path, encoding: str | None, exc: UnicodeError) -> str:
    used = encoding or "utf-8"
    suggestions = ", ".join(enc for enc in _COMMON_ENCODINGS if enc != used)
    return f"can't decode '{path}' with encoding '{used}'; try -encoding {suggestions}"


def _resolve_alias(alias: str, frames: dict[str, pd.DataFrame], pipeline: _Pipeline, flag: str) -> tuple[pd.DataFrame | None, str | None]:
    """Look up a -merge/-concat alias: a -file alias, or 'df' for the pipeline's current
    result so far (lets repeated -merge/-concat calls fold in one more file at a time).
    Returns (frame, error_message)."""
    if alias == "data":
        if pipeline._df is None:
            return None, f"{flag}: 'data' isn't available yet — nothing has produced a pipeline result yet"
        return pipeline._df, None
    if alias not in frames:
        return None, f"{flag}: unknown -file alias '{alias}'"
    return frames[alias], None


def _process_path(
    path: Path | None,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    batch: bool,
    *,
    show_all: bool,
    select_specs: list[tuple[list[str], dict]],
    filter_specs: list[list[tuple[str, Any]]] | None = None,
    mutate_specs: list[str] | None = None,
    sql_specs: list[str] | None = None,
    replace_specs: list[tuple[list[str] | None, dict[str, str], bool]] | None = None,
    rename_specs: list[dict[str, str]] | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    merge_specs: list[dict] | None = None,
    concat_specs: list[dict] | None = None,
    qry_specs: list[list[tuple[str, Any]]] | None = None,
) -> bool:
    """Run every requested display/export/-agg action against one file, or (when frames
    is given, i.e. -file/-merge mode) against named in-memory frames instead. Returns True
    if an error occurred."""
    merge_specs = merge_specs or []
    concat_specs = concat_specs or []
    if frames is None:
        chunk_size = getattr(args, "chunk_size", None) or 200_000
        reader: Any
        if str(path).lower() == "clip":
            try:
                clip_sep = args.dlim if args.dlim else r"\s+"
                clip_df = pd.read_clipboard(sep=clip_sep)
            except Exception as exc:
                return _fail(parser, batch, f"clipboard error: {exc}")
            reader = DataFrameReader(clip_df, path="<clipboard>")
            pipeline = _Pipeline(
                reader, nrows=args.nrows, progress=args.progress, chunk_size=chunk_size,
            )
        elif str(path) == "-":
            data_bytes = sys.stdin.buffer.read()
            try:
                reader = StdinReader(
                    data_bytes,
                    fmt=getattr(args, "fmt", None),
                    sep=args.dlim,
                    encoding=args.encoding,
                    chunk_size=chunk_size,
                )
            except (ValueError, ImportError) as exc:
                return _fail(parser, batch, str(exc))

            pipeline = _Pipeline(
                reader, nrows=args.nrows, progress=args.progress, chunk_size=chunk_size,
            )
        elif path is None or not path.exists():
            return _fail(parser, batch, f"file not found: {path}")
        else:
            try:
                reader = get_reader(path, sep=args.dlim, encoding=args.encoding, chunk_size=chunk_size)
            except (ValueError, ImportError) as exc:
                return _fail(parser, batch, str(exc))

            pipeline = _Pipeline(
                reader, nrows=args.nrows, progress=args.progress, chunk_size=chunk_size,
            )
    else:
        pipeline = _Pipeline(frames=frames)

    out_target = str(args.output).strip() if args.output is not None else None
    image_exts = (".png", ".svg", ".pdf", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")
    is_image_out = out_target is not None and any(out_target.lower().endswith(ext) for ext in image_exts)
    is_clip = out_target is not None and out_target.lower() in ("clip", "clipboard")
    is_file = out_target is not None and not is_clip and not is_image_out
    clip_action = None
    emit_stdout = not is_clip and not is_file and not is_image_out

    if show_all:
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if emit_stdout:
            print(_format_table(df, pretty=args.pretty))
        if is_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    op_values = getattr(args, "_op_values", {})
    op_iters = {k: iter(v) for k, v in op_values.items()}

    def _next_op_val(op_name: str, fallback: Any = None) -> Any:
        it = op_iters.get(op_name)
        if it is not None:
            try:
                return next(it)
            except StopIteration:
                pass
        return fallback

    select_iter = iter(select_specs)
    filter_iter = iter(filter_specs if filter_specs is not None else (qry_specs or []))
    mutate_iter = iter(mutate_specs or [])
    sql_iter = iter(sql_specs or [])
    replace_iter = iter(replace_specs or [])
    rename_iter = iter(rename_specs or [])
    merge_iter = iter(merge_specs or [])
    concat_iter = iter(concat_specs or [])

    def should_print(idx: int) -> bool:
        return emit_stdout and idx == last_idx

    def emit_frame(idx: int) -> None:
        nonlocal clip_action
        if not (should_print(idx) or is_clip):
            return
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if should_print(idx):
            print(_format_table(df, pretty=args.pretty))
        if is_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    for idx, op in enumerate(op_order):
        if op == "select":
            names, kwargs = next(select_iter)
            err = pipeline.apply_select(names, kwargs)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "rename":
            err = pipeline.apply_rename(next(rename_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op in ("filter", "qry"):
            err = pipeline.apply_filter(next(filter_iter), flag_name=f"-{op}")
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "mutate":
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols:
                df_cur = pipeline.dataframe()
                if any(c not in df_cur.columns for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, list(df_cur.columns)))
            err = pipeline.apply_mutate(next(mutate_iter), by=by_cols, dropna=False)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "sql":
            err = pipeline.apply_sql(next(sql_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "replace_values":
            cols, mapping, exact = next(replace_iter)
            err = pipeline.apply_replace_values(cols, mapping, exact)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "merge":
            spec = next(merge_iter)
            if frames is None:
                return _fail(parser, batch, "-merge requires -file")
            left_df, err = _resolve_alias(spec["left"], frames, pipeline, "-merge")
            if err or left_df is None:
                return _fail(parser, batch, err or "-merge: missing left frame")
            right_df, err = _resolve_alias(spec["right"], frames, pipeline, "-merge")
            if err or right_df is None:
                return _fail(parser, batch, err or "-merge: missing right frame")
            merge_kwargs = {"how": spec["how"]}
            if spec["validate"]:
                merge_kwargs["validate"] = spec["validate"]
            if spec["how"] == "cross":
                pass  # cross joins don't take on=/left_on=/right_on=
            elif spec["on"] is not None:
                missing = [c for c in spec["on"] if c not in left_df.columns or c not in right_df.columns]
                if missing:
                    return _fail(parser, batch, f"-merge: on= column(s) not in both frames: {', '.join(missing)}")
                merge_kwargs["on"] = spec["on"]
            else:
                missing_left = [c for c in spec["left_on"] if c not in left_df.columns]
                missing_right = [c for c in spec["right_on"] if c not in right_df.columns]
                if missing_left:
                    return _fail(parser, batch, unknown_columns_message("-merge (left)", missing_left, list(left_df.columns)))
                if missing_right:
                    return _fail(parser, batch, unknown_columns_message("-merge (right)", missing_right, list(right_df.columns)))
                merge_kwargs["left_on"] = spec["left_on"]
                merge_kwargs["right_on"] = spec["right_on"]
            try:
                result = pd.merge(left_df, right_df, **merge_kwargs)
            except Exception as exc:
                return _fail(parser, batch, f"-merge: {exc}")
            pipeline._df = result
            if should_print(idx):
                print(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty))
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "concat":
            spec = next(concat_iter)
            if frames is None:
                return _fail(parser, batch, "-concat requires -file")
            dfs = []
            for alias in spec["frames"]:
                df, err = _resolve_alias(alias, frames, pipeline, "-concat")
                if err or df is None:
                    return _fail(parser, batch, err or f"-concat: missing frame '{alias}'")
                dfs.append(df)
            try:
                result = pd.concat(dfs, ignore_index=True)
            except Exception as exc:
                return _fail(parser, batch, f"-concat: {exc}")
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "shape":
            shape_str = str(pipeline.shape())
            if should_print(idx):
                _output_text(shape_str, args)
            if is_clip:
                clip_action = lambda s=shape_str: _copy_to_clipboard(s)
        elif op == "cols":
            names = _list_order_names(pipeline.columns(), args.cols)
            if should_print(idx):
                _output_text("\n".join(names), args)
            if is_clip:
                clip_action = lambda n=names: pd.Series(n).to_clipboard(index=False, header=False)
        elif op == "dtype":
            dtypes = _list_order_index(pipeline.dtypes(), args.dtype)
            if should_print(idx):
                _output_text(dtypes.to_string(), args)
            if is_clip:
                clip_action = lambda s=dtypes: s.to_clipboard()
        elif op == "nulls":
            nulls = _list_order_index(pipeline.dataframe().isna().sum(), args.nulls)
            if should_print(idx):
                _output_text(nulls.to_string(), args)
            if is_clip:
                clip_action = lambda s=nulls: s.to_clipboard()
        elif op == "describe":
            described = pipeline.dataframe().describe()
            pipeline._df = described
            if should_print(idx):
                _output_text(_format_table(_apply_round(described, args.round_ndigits), index=True, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=described: _apply_round(d, args.round_ndigits).to_clipboard(index=True)
        elif op == "info":
            info_str = _dataframe_info(pipeline.dataframe())
            if should_print(idx):
                _output_text(info_str, args)
            if is_clip:
                clip_action = lambda s=info_str: _copy_to_clipboard(s)
        elif op == "glimpse":
            from pytae.other_utilities import format_glimpse
            glimpse_str = format_glimpse(pipeline.dataframe())
            if should_print(idx):
                _output_text(glimpse_str, args)
            if is_clip:
                clip_action = lambda s=glimpse_str: _copy_to_clipboard(s)
        elif op == "meta":
            meta_str = _extract_metadata(path if path is not None else Path("<merged>"), sep=args.dlim, encoding=args.encoding)
            if should_print(idx):
                _output_text(meta_str, args)
            if is_clip:
                clip_action = lambda s=meta_str: _copy_to_clipboard(s)
        elif op == "diff":
            diff_path = Path(args.diff)
            diff_str = _compute_diff(pipeline.dataframe(), diff_path, path.name if path is not None else "<pipeline>", sep=args.dlim, encoding=args.encoding)
            if should_print(idx):
                _output_text(diff_str, args)
            if is_clip:
                clip_action = lambda s=diff_str: _copy_to_clipboard(s)
        elif op == "value_counts":
            source_df = pipeline.dataframe()
            value_count_cols = list(source_df.columns)

            if "count" in value_count_cols and "n" in value_count_cols:
                return _fail(parser, batch, "-value_counts: columns contain both 'count' and 'n'; rename one to avoid ambiguous count headers")

            try:
                if len(value_count_cols) == 1:
                    col = value_count_cols[0]
                    count_name = "count" if col != "count" else "n"
                    result = source_df[col].value_counts(dropna=False if args.dropna is None else args.dropna).rename(count_name).reset_index()
                    result.columns = [col, count_name]
                else:
                    count_name = "count" if "count" not in value_count_cols else "n"
                    result = source_df.value_counts(subset=value_count_cols, dropna=False if args.dropna is None else args.dropna).rename(count_name).reset_index()
            except Exception as exc:
                return _fail(parser, batch, str(exc))
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "freq":
            freq_col = _next_op_val("freq", getattr(args, "freq", None))
            source_df = pipeline.dataframe()
            result = _compute_freq(source_df, freq_col, False if args.dropna is None else args.dropna)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "hist":
            hist_arg = _next_op_val("hist", getattr(args, "hist", None))
            source_df = pipeline.dataframe()
            result = _compute_hist(source_df, hist_arg)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "distinct":
            distinct_val = _next_op_val("distinct", getattr(args, "distinct", None))
            err = pipeline.apply_distinct(distinct_val)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "head":
            head_val = _next_op_val("head", args.head)
            df = pipeline.head(head_val)
            if should_print(idx):
                _output_text(_format_table(_apply_round(df, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_idx = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
                clip_action = lambda d=df, ci=clip_idx: _apply_round(d, args.round_ndigits).to_clipboard(index=ci)
        elif op == "tail":
            tail_val = _next_op_val("tail", args.tail)
            df = pipeline.tail(tail_val)
            if should_print(idx):
                _output_text(_format_table(_apply_round(df, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_idx = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
                clip_action = lambda d=df, ci=clip_idx: _apply_round(d, args.round_ndigits).to_clipboard(index=ci)
        elif op == "sample":
            sample_val = _next_op_val("sample", args.sample)
            sampled = pipeline.sample(sample_val, seed=args.seed, frac=args.frac)
            n = len(sampled)
            if should_print(idx):
                _output_text(_format_table(_apply_round(sampled, args.round_ndigits), pretty=args.pretty) if n else "(no rows)", args)
            if is_clip and n:
                clip_action = lambda d=sampled: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "arrange":
            arrange_val = _next_op_val("arrange", getattr(args, "arrange", None))
            err = pipeline.apply_arrange(arrange_val)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "pick":
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols:
                df_cur = pipeline.dataframe()
                if any(c not in df_cur.columns for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, list(df_cur.columns)))
            pick_val = _next_op_val("pick", getattr(args, "pick", None))
            err = pipeline.apply_pick(pick_val, by=by_cols, flag="-pick")
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "slice_max":
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols:
                df_cur = pipeline.dataframe()
                if any(c not in df_cur.columns for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, list(df_cur.columns)))
            slice_val = _next_op_val("slice_max", getattr(args, "slice_max", None))
            err = pipeline.apply_pick(slice_val, by=by_cols, flag="-slice_max")
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "slice_min":
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols:
                df_cur = pipeline.dataframe()
                if any(c not in df_cur.columns for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, list(df_cur.columns)))
            slice_val = _next_op_val("slice_min", getattr(args, "slice_min", None))
            err = pipeline.apply_pick(slice_val, by=by_cols, flag="-slice_min")
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "agg":
            agg_val = _next_op_val("agg", args.agg)
            if isinstance(agg_val, str):
                parse_agg(agg_val)
            df_cur = pipeline.dataframe()
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols and any(c not in df_cur.columns for c in by_cols):
                return _fail(parser, batch, unknown_columns_message("-by", by_cols, list(df_cur.columns)))
            try:
                from pytae.by import by as _by
                work_df = _by(df_cur.copy(deep=False), *by_cols) if by_cols else df_cur
                result = agg(work_df, agg_val, dropna=False)
            except Exception as e:
                return _fail(parser, batch, str(e))
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "handle_missing":
            hm_val = _next_op_val("handle_missing", args.handle_missing)
            result = handle_missing(pipeline.dataframe(), fillna=hm_val)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "dropna":
            dropna_val = _next_op_val("dropna", getattr(args, "dropna", None))
            err = pipeline.apply_dropna(dropna_val)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "clean_columns":
            cc_val = _next_op_val("clean_columns", args.clean_columns)
            opts = parse_clean_columns_arg(cc_val)
            result = clean_columns(pipeline.dataframe(), **opts)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "long":
            from pytae.shape import long as long_fn
            source_df = pipeline.dataframe()
            long_val = _next_op_val("long", args.long)
            long_kwargs = parse_long_arg(long_val)
            cols_arg = long_kwargs.get("cols")
            if cols_arg:
                cols_list = parse_columns(cols_arg) if isinstance(cols_arg, str) else list(cols_arg)
                missing = [c for c in cols_list if c not in source_df.columns]
                if missing:
                    return _fail(parser, batch, unknown_columns_message("-long", missing, list(source_df.columns)))
            try:
                result = long_fn(source_df, **long_kwargs)
            except (KeyError, ValueError) as exc:
                return _fail(parser, batch, str(exc))
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "wide":
            from pytae.shape import wide as wide_fn
            source_df = pipeline.dataframe()
            wide_val = _next_op_val("wide", args.wide)
            wide_kwargs = parse_wide_arg(wide_val)
            to_check = [wide_kwargs.get("c", "variable"), wide_kwargs.get("v", "value")]
            by_cols = wide_kwargs.get("by") or wide_kwargs.get("index") or wide_kwargs.get("r") or wide_kwargs.get("rows")
            if by_cols:
                to_check.extend(parse_columns(by_cols) if isinstance(by_cols, str) else list(by_cols))
            missing = [c for c in to_check if c not in source_df.columns]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-wide", missing, list(source_df.columns)))
            try:
                result = wide_fn(source_df, **wide_kwargs)
            except (KeyError, ValueError) as exc:
                return _fail(parser, batch, str(exc))
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "pivot":
            from pytae.shape import pivot as pivot_fn
            source_df = pipeline.dataframe()
            pivot_val = _next_op_val("pivot", getattr(args, "pivot", None))
            pivot_kwargs = parse_pivot_arg(pivot_val)
            if "dropna" not in pivot_kwargs:
                pivot_kwargs["dropna"] = False if args.dropna is None else args.dropna
            to_check = []
            for k in ("r", "rows", "index", "by", "c", "cols", "columns", "v", "values", "val", "vals"):
                val = pivot_kwargs.get(k)
                if val:
                    to_check.extend(parse_columns(val) if isinstance(val, str) else list(val))
            missing = [col for col in to_check if col not in source_df.columns]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-pivot", missing, list(source_df.columns)))
            try:
                result = pivot_fn(source_df, **pivot_kwargs)
            except Exception as exc:
                return _fail(parser, batch, str(exc))
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "plot":
            plot_spec = _next_op_val("plot", getattr(args, "plot", None))
            plot_kwargs = parse_kv_spec(plot_spec, flag="-plot")
            finalize_kwargs = parse_kv_spec(getattr(args, "finalize", None), flag="-finalize")

            source_df = pipeline.dataframe()
            import matplotlib

            from pytae.plotting import Plotter
            if is_image_out or not should_print(idx):
                matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            if isinstance(finalize_kwargs.get("style"), str):
                try:
                    plt.style.use(finalize_kwargs["style"])
                except Exception as exc:
                    return _fail(parser, batch, f"-finalize style: {exc}")

            plotter_keys = {"mosaic", "figsize", "sharex", "sharey", "nrows", "ncols"}
            init_kwargs = {k: v for k, v in plot_kwargs.items() if k in plotter_keys}
            chart_kwargs = {k: v for k, v in plot_kwargs.items() if k not in plotter_keys}
            if "dropna" not in chart_kwargs and getattr(args, "dropna", None) is not None:
                chart_kwargs["dropna"] = args.dropna

            try:
                p = Plotter(source_df, **init_kwargs)
                p.plot(**chart_kwargs)
                p.finalize(**finalize_kwargs)
            except Exception as exc:
                return _fail(parser, batch, str(exc))

            if is_image_out:
                assert out_target is not None
                dest_path = Path(out_target)
                if args.out_dir is not None:
                    args.out_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = args.out_dir / dest_path.name
                p.save(dest_path)
                print(f"Saved plot to {dest_path}")
            elif should_print(idx):
                p.show()

    if is_clip and clip_action is not None:
        clip_action()
    elif is_file:
        assert out_target is not None
        fmt = out_target.lower()
        out_dir: Path | None = getattr(args, "out_dir", None)
        valid_formats = (
            "csv", "parquet", "pq", "txt", "dat", "jsonl", "ndjson",
            "csv.gz", "txt.gz", "dat.gz", "jsonl.gz", "ndjson.gz",
        )
        if fmt in valid_formats:
            if path is None or str(path) == "-":
                return _fail(parser, batch, f"-o {out_target}: when reading from STDIN or -file mode, an explicit output file path is required")
            ext = ".parquet" if fmt == "pq" else f".{fmt}"
            clean_name = path.name[:-3] if path.name.lower().endswith(".gz") else path.name
            dest_name = f"{Path(clean_name).stem}{ext}"
            dest = (out_dir / dest_name) if out_dir is not None else path.with_name(dest_name)
        else:
            dest = Path(out_target)
            if out_dir is not None and not dest.is_absolute():
                dest = out_dir / dest

        df_to_write = _apply_round(pipeline.dataframe(), args.round_ndigits)
        try:
            cmd_convert(
                df_to_write,
                path if path is not None else Path("<merged>"),
                dest,
                sep=args.dlim,
                encoding=args.encoding,
                progress=args.progress,
                announce=True,
                chunk_size=getattr(args, "chunk_size", None) or 200_000,
            )
        except SystemExit as exc:
            return _fail(parser, batch, str(exc))

    return False


