"""Execute one CLI pipeline: display/convert/agg ops against a file or named frames."""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

from pytae.agg_df import agg_df
from pytae.cli_parsing import (
    parse_agg,
    parse_clean_columns_arg,
    parse_columns,
    parse_crosstab_arg,
    parse_group_agg,
    parse_group_x_arg,
    parse_long_arg,
    parse_sort_by,
    parse_wide_arg,
    unknown_columns_message,
)
from pytae.cli_pipeline import _Pipeline
from pytae.other_utilities import clean_columns, group_x, handle_missing
from pytae.readers import _split_path_suffixes, get_reader, write_dataframe


def _apply_round(df: pd.DataFrame, ndigits: int | None) -> pd.DataFrame:
    """Round numeric columns to ndigits; non-numeric columns pass through unchanged."""
    return df.round(ndigits) if ndigits is not None else df


def _dataframe_info(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.info(buf=buf)
    return buf.getvalue().rstrip()


def _format_table(df: pd.DataFrame, *, index: bool = False, pretty: bool = False) -> str:
    """Render a DataFrame as standard pandas text, or a markdown/bordered table when pretty=True."""
    if not pretty:
        return df.to_string(index=index)
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return df.to_string(index=index)


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


def _extract_metadata(path: Path) -> str:
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
            reader = get_reader(path)
            cols = reader.columns()
            lines.append(f"Columns: {len(cols)}")
            lines.append(f"Column names: {', '.join(cols[:15])}{'...' if len(cols) > 15 else ''}")
        except Exception:
            pass
    return "\n".join(lines)


def _compute_diff(left_df: pd.DataFrame, right_path: Path, left_name: str) -> str:
    """Compare the current pipeline result against another tabular file."""
    if not right_path.exists():
        return f"Diff target not found: {right_path}"
    try:
        reader = get_reader(right_path)
        right_df = reader.to_dataframe()
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
NON_DF_TERMINAL_OPS = frozenset({"shape", "cols", "dtype", "nulls", "info", "meta", "diff"})


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
    drop_specs: list[list[str]],
    qry_specs: list[dict],
    mutate_specs: list[str],
    query_specs: list[str],
    sql_specs: list[str],
    replace_specs: list[tuple[list[str] | None, dict[str, str], bool]],
    rename_specs: list[dict[str, str]],
    frames: dict[str, pd.DataFrame] | None = None,
    merge_specs: list[dict] | None = None,
    concat_specs: list[dict] | None = None,
) -> bool:
    """Run every requested display/export/-agg action against one file, or (when frames
    is given, i.e. -file/-merge mode) against named in-memory frames instead. Returns True
    if an error occurred."""
    merge_specs = merge_specs or []
    concat_specs = concat_specs or []
    if frames is None:
        if path is None or not path.exists():
            return _fail(parser, batch, f"file not found: {path}")

        chunk_size = getattr(args, "chunk_size", None) or 200_000
        try:
            reader = get_reader(path, sep=args.dlim, encoding=args.encoding, chunk_size=chunk_size)
        except (ValueError,ImportError) as exc:
            return _fail(parser, batch, str(exc))

        pipeline = _Pipeline(
            reader, nrows=args.nrows, progress=args.progress, chunk_size=chunk_size,
        )
    else:
        pipeline = _Pipeline(frames=frames)

    out_target = str(args.output).strip() if args.output is not None else None
    is_clip = out_target is not None and out_target.lower() in ("clip", "clipboard")
    is_file = out_target is not None and not is_clip
    clip_action = None
    emit_stdout = not is_clip and not is_file

    if show_all:
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if emit_stdout:
            print(_format_table(df, pretty=args.pretty))
        if is_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    select_iter = iter(select_specs)
    drop_iter = iter(drop_specs)
    qry_iter = iter(qry_specs)
    mutate_iter = iter(mutate_specs)
    query_iter = iter(query_specs)
    sql_iter = iter(sql_specs)
    replace_iter = iter(replace_specs)
    rename_iter = iter(rename_specs)
    merge_iter = iter(merge_specs)
    concat_iter = iter(concat_specs)

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
        elif op == "drop":
            err = pipeline.apply_drop(next(drop_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "rename":
            err = pipeline.apply_rename(next(rename_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "qry":
            err = pipeline.apply_qry(next(qry_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "mutate":
            err = pipeline.apply_mutate(next(mutate_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "query":
            err = pipeline.apply_query(next(query_iter))
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
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
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
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
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
            described = _apply_round(pipeline.dataframe().describe(), args.round_ndigits)
            pipeline._df = described
            if should_print(idx):
                _output_text(_format_table(described, index=True, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=described: d.to_clipboard(index=True)
        elif op == "info":
            info_str = _dataframe_info(pipeline.dataframe())
            if should_print(idx):
                _output_text(info_str, args)
            if is_clip:
                clip_action = lambda s=info_str: _copy_to_clipboard(s)
        elif op == "meta":
            meta_str = _extract_metadata(path if path is not None else Path("<merged>"))
            if should_print(idx):
                _output_text(meta_str, args)
            if is_clip:
                clip_action = lambda s=meta_str: _copy_to_clipboard(s)
        elif op == "diff":
            diff_path = Path(args.diff)
            diff_str = _compute_diff(pipeline.dataframe(), diff_path, path.name if path is not None else "<pipeline>")
            if should_print(idx):
                _output_text(diff_str, args)
            if is_clip:
                clip_action = lambda s=diff_str: _copy_to_clipboard(s)
        elif op == "value_counts":
            source_df = pipeline.dataframe()
            value_count_cols = list(source_df.columns)

            if len(value_count_cols) == 1:
                col = value_count_cols[0]
                result = source_df[col].value_counts(dropna=args.dropna).rename("count").reset_index()
                result.columns = [col, "count"]
            else:
                result = source_df.value_counts(subset=value_count_cols, dropna=args.dropna).rename("count").reset_index()
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "unique":
            unique_df = _apply_round(pipeline.dataframe().drop_duplicates().reset_index(drop=True), args.round_ndigits)
            pipeline._df = unique_df
            if should_print(idx):
                _output_text(_format_table(unique_df, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=unique_df: d.to_clipboard(index=False)
        elif op == "head":
            df = _apply_round(pipeline.head(args.head), args.round_ndigits)
            if should_print(idx):
                _output_text(_format_table(df, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "tail":
            df = _apply_round(pipeline.tail(args.tail), args.round_ndigits)
            if should_print(idx):
                _output_text(_format_table(df, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "sample":
            sampled = _apply_round(pipeline.sample(args.sample, seed=args.seed, frac=args.frac), args.round_ndigits)
            n = len(sampled)
            if should_print(idx):
                _output_text(_format_table(sampled, pretty=args.pretty) if n else "(no rows)", args)
            if is_clip and n:
                clip_action = lambda d=sampled: d.to_clipboard(index=False)
        elif op == "sort_by":
            source_df = pipeline.dataframe()
            sort_cols, order = parse_sort_by(args.sort_by)
            if any(c not in source_df.columns for c in sort_cols):
                return _fail(parser, batch, unknown_columns_message("-sort_by", sort_cols, list(source_df.columns)))
            ascending = order != "desc"
            sorted_df = _apply_round(source_df.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True), args.round_ndigits)
            pipeline._df = sorted_df
            if should_print(idx):
                _output_text(_format_table(sorted_df, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=sorted_df: d.to_clipboard(index=False)
        elif op == "agg_df":
            aggfunc = parse_agg(args.agg_df)
            if isinstance(aggfunc, dict):
                result = _apply_round(agg_df(pipeline.dataframe(), dropna=args.dropna, **aggfunc), args.round_ndigits)
            else:
                result = _apply_round(agg_df(pipeline.dataframe(), aggfunc, dropna=args.dropna), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "agg":
            if not args.group_by:
                return _fail(parser, batch, "-agg requires -group_by")
            source_df = pipeline.dataframe()
            group_cols = parse_columns(args.group_by)
            if any(c not in source_df.columns for c in group_cols):
                return _fail(parser, batch, unknown_columns_message("-group_by", group_cols, list(source_df.columns)))
            agg_spec = parse_group_agg(args.agg)
            named_agg = {}
            for col, out_name, aggfunc in agg_spec:
                if col not in source_df.columns:
                    return _fail(parser, batch, unknown_columns_message("-agg", [col], list(source_df.columns)))
                named_agg[out_name] = pd.NamedAgg(column=col, aggfunc=aggfunc)
            result = source_df.groupby(group_cols, dropna=args.dropna, observed=True, as_index=False).agg(**named_agg)
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "group_x":
            source_df = pipeline.dataframe()
            gx = parse_group_x_arg(args.group_x)
            if "group" not in gx and args.group_by:
                gx["group"] = parse_columns(args.group_by)
            gx["dropna"] = args.dropna
            group_cols = gx.get("group") or []
            if group_cols and any(c not in source_df.columns for c in group_cols):
                return _fail(parser, batch, unknown_columns_message("-group_x", group_cols, list(source_df.columns)))
            value_col = gx.get("v")
            if value_col and value_col not in source_df.columns:
                return _fail(parser, batch, unknown_columns_message("-group_x", [value_col], list(source_df.columns)))
            result = _apply_round(group_x(source_df, **gx), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "handle_missing":
            result = _apply_round(handle_missing(pipeline.dataframe(), fillna=args.handle_missing), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "clean_columns":
            opts = parse_clean_columns_arg(args.clean_columns)
            result = _apply_round(clean_columns(pipeline.dataframe(), **opts), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "long":
            from pytae.shape import long as long_fn
            result = _apply_round(long_fn(pipeline.dataframe(), **parse_long_arg(args.long)), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "wide":
            from pytae.shape import wide as wide_fn
            source_df = pipeline.dataframe()
            wide_kwargs = parse_wide_arg(args.wide)
            wide_kwargs["dropna"] = args.dropna
            missing = [c for c in (wide_kwargs.get("c", "variable"), wide_kwargs.get("v", "value"))
                       if c not in source_df.columns]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-wide", missing, list(source_df.columns)))
            result = _apply_round(wide_fn(source_df, **wide_kwargs), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "crosstab":
            source_df = pipeline.dataframe()
            ct = parse_crosstab_arg(args.crosstab)
            index_cols = parse_columns(ct["index"])
            needed = index_cols + [ct["columns"]] + ([ct["values"]] if "values" in ct else [])
            missing = [c for c in needed if c not in source_df.columns]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-crosstab", missing, list(source_df.columns)))
            ct_kwargs = {"dropna": args.dropna}
            if "margins" in ct:
                ct_kwargs["margins"] = ct["margins"]
            if "margins_name" in ct:
                ct_kwargs["margins_name"] = ct["margins_name"]
            if "normalize" in ct:
                ct_kwargs["normalize"] = ct["normalize"]
            if "values" in ct:
                ct_kwargs["values"] = source_df[ct["values"]]
                ct_kwargs["aggfunc"] = ct["aggfunc"]
            result = _apply_round(
                pd.crosstab([source_df[c] for c in index_cols], source_df[ct["columns"]], **ct_kwargs),
                args.round_ndigits,
            )
            pipeline._df = result
            if should_print(idx):
                _output_text(_format_table(result, index=True, pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: d.to_clipboard(index=True)

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
            if path is None:
                return _fail(parser, batch, f"-o {out_target}: in -file/-merge mode, an explicit output file path is required")
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


