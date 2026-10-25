"""Execute one CLI pipeline: display/convert/agg ops against a file or named frames."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from pytae.cli_parsing import (
    parse_agg,
    parse_clean_columns_arg,
    parse_columns,
    parse_fillna_spec,
    parse_kv_spec,
    parse_long_arg,
    parse_pivot_arg,
    parse_wide_arg,
    unknown_columns_message,
)
from pytae.cli_pipeline import _Pipeline
from pytae.readers import (
    DataFrameReader,
    StdinReader,
    _split_path_suffixes,
    get_reader,
    write_dataframe,
)


def _apply_round(df: Any, ndigits: int | None) -> Any:
    """Round numeric columns to ndigits; non-numeric columns pass through unchanged."""
    import polars as pl

    from pytae.dataframe import DataFrame as PytaeDataFrame

    if isinstance(df, PytaeDataFrame):
        df = df._df
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
    if ndigits is None:
        return df
    if isinstance(df, pd.DataFrame):
        return df.round(ndigits)
    try:
        import polars.selectors as cs

        if isinstance(df, pl.DataFrame):
            return df.with_columns(cs.numeric().round(ndigits))
    except Exception:
        pass
    return df


def _format_table(
    df: Any,
    *,
    index: bool | None = None,
    pretty: bool = False,
    is_tty: bool | None = None,
    tbl_rows: int | None = None,
) -> str:
    """Render tabular data directly using Polars.

    Auto-detects TTY output:
    - Interactive terminal (isatty): renders Polars default boxed table with shape & dtypes.
    - Piped / redirected (not isatty): renders bare unbordered plain text without shape or dtype headers.
    """
    if is_tty is None:
        is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    import polars as pl

    from pytae.dataframe import DataFrame as PytaeDataFrame

    if isinstance(df, PytaeDataFrame):
        df = df._df

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    if is_tty:
        if isinstance(df, pl.DataFrame):
            pldf = df
        elif isinstance(df, pd.DataFrame):
            if index is None:
                index = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
            try:
                pldf = pl.from_pandas(df.reset_index() if index else df)
            except Exception:
                return df.to_string(index=index)
        else:
            return str(df)

        n_rows = len(pldf)
        if tbl_rows is None:
            tbl_rows = max(n_rows, 10) if n_rows <= 25 else 10
        with pl.Config(tbl_rows=tbl_rows):
            return str(pldf)

    # Non-TTY / Piped / Redirected: Bare output
    if isinstance(df, pd.DataFrame):
        if index is None:
            index = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
        return df.to_string(index=index)

    if isinstance(df, pl.DataFrame):
        if len(df) == 0:
            return f"Empty DataFrame\nColumns: {list(df.columns)}\nIndex: []"
        if len(df) <= 1000:
            return df.to_pandas().to_string(index=False)
        with pl.Config(
            tbl_formatting="NOTHING",
            tbl_hide_column_data_types=True,
            tbl_hide_dataframe_shape=True,
            tbl_width_chars=10_000,
            tbl_rows=-1,
            tbl_cols=-1,
        ):
            return "\n".join(line.strip() for line in str(df).splitlines())

    return str(df)


def _compute_freq(source_df: Any, col: str | None, dropna: bool) -> Any:
    from pytae.other_utilities import freq

    width = 20
    target_col = col
    if col and ",width=" in col:
        c_part, _, w_part = col.partition(",width=")
        target_col = c_part.strip()
        try:
            width = int(w_part.strip())
        except ValueError:
            raise SystemExit(f"-freq: invalid width='{w_part.strip()}'; expected positive integer")
    try:
        return freq(source_df, col=target_col, dropna=dropna, width=width)
    except KeyError as exc:
        raise SystemExit(str(exc))
    except ValueError as exc:
        raise SystemExit(f"-freq: {exc}")


def _compute_hist(source_df: Any, hist_arg: str | None) -> Any:
    from pytae.other_utilities import hist

    width = 20
    target_arg = hist_arg
    if hist_arg and ",width=" in hist_arg:
        h_part, _, w_part = hist_arg.partition(",width=")
        target_arg = h_part.strip()
        try:
            width = int(w_part.strip())
        except ValueError:
            raise SystemExit(f"-hist: invalid width='{w_part.strip()}'; expected positive integer")
    try:
        return hist(source_df, col=target_arg, width=width)
    except KeyError as exc:
        raise SystemExit(str(exc))
    except ValueError as exc:
        raise SystemExit(f"-hist: {exc}")


def _compute_bar(source_df: Any, bar_arg: str | None) -> Any:
    from pytae.cli_parsing import parse_bar_spec
    from pytae.other_utilities import bar

    spec = parse_bar_spec(bar_arg)
    try:
        return bar(
            source_df,
            cat=spec["cat"],
            val=spec["val"],
            limit=spec["limit"],
            pct=spec["pct"],
            width=spec["width"],
        )
    except KeyError as exc:
        raise SystemExit(str(exc))
    except ValueError as exc:
        raise SystemExit(f"-bar: {exc}")


def _compute_scatter(source_df: Any, scatter_arg: str | None) -> str:
    from pytae.cli_parsing import parse_scatter_spec
    from pytae.other_utilities import scatter

    spec = parse_scatter_spec(scatter_arg)
    try:
        return scatter(
            source_df,
            x=spec["x"],
            y=spec["y"],
            width=spec["width"],
            height=spec["height"],
            limit_x=spec["limit_x"],
            limit_y=spec["limit_y"],
        )
    except KeyError as exc:
        raise SystemExit(str(exc))
    except ValueError as exc:
        raise SystemExit(f"-scatter: {exc}")


def _compute_corr(source_df: Any, corr_arg: str | None) -> Any:
    from pytae.cli_parsing import parse_corr_spec
    from pytae.other_utilities import corr

    spec = parse_corr_spec(corr_arg)
    try:
        return corr(
            source_df,
            target=spec["target"],
            pairs=spec["pairs"],
            method=spec["method"],
        )
    except KeyError as exc:
        raise SystemExit(str(exc))
    except ValueError as exc:
        raise SystemExit(f"-corr: {exc}")


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
            lines.append(f"  {'-' * 4} {'-' * max_name_len}  {'-' * 20}")
            for idx, field in enumerate(schema):
                lines.append(f"  {idx:<4} {field.name:<{max_name_len}}  {field.type}")
        except Exception as exc:
            lines.append(f"Error reading Parquet metadata: {exc}")
    else:
        fmt_name = (
            "CSV"
            if suffix == ".csv"
            else ("JSON Lines" if suffix in (".jsonl", ".ndjson") else suffix.lstrip(".").upper())
        )
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
    right_target: Any,
    left_name: str,
    *,
    tol: float = 0.0,
    rtol: float = 0.0,
    sep: str | None = None,
    encoding: str | None = None,
) -> str:
    """Compare the current pipeline result against another tabular file or DataFrame."""
    if isinstance(right_target, pd.DataFrame):
        right_df = right_target
        right_name = getattr(right_target, "_name", "<right>")
    elif hasattr(right_target, "to_pandas"):
        right_df = right_target.to_pandas()
        right_name = getattr(right_target, "_name", "<right>")
    else:
        right_path = Path(right_target)
        if not right_path.exists():
            return f"Diff target not found: {right_path}"
        try:
            reader = get_reader(right_path, sep=sep, encoding=encoding)
            right_df = reader.to_dataframe()
            right_name = right_path.name
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
        f"  Right (target): {right_name} ({r2:,} rows, {c2} cols)",
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
            col_mismatches: dict[str, tuple[int, float | None]] = {}
            for c in common_cols:
                s1 = left_df[c]
                s2 = right_df[c]
                is_num1 = pd.api.types.is_numeric_dtype(s1)
                is_num2 = pd.api.types.is_numeric_dtype(s2)
                if (tol > 0 or rtol > 0) and is_num1 and is_num2:
                    both_na = s1.isna() & s2.isna()
                    v1 = pd.to_numeric(s1, errors="coerce")
                    v2 = pd.to_numeric(s2, errors="coerce")
                    abs_diff = (v1 - v2).abs()
                    within_tol = abs_diff <= (tol + rtol * v2.abs())
                    match = both_na | within_tol.fillna(False)
                    diff = ~match
                    cnt = int(diff.sum())
                    if cnt > 0:
                        max_d = float(abs_diff[diff].max()) if not abs_diff[diff].empty else None
                        col_mismatches[c] = (cnt, max_d)
                        mismatches += cnt
                else:
                    diff = ~((s1 == s2) | (s1.isna() & s2.isna()))
                    cnt = int(diff.sum())
                    if cnt > 0:
                        max_d = None
                        if is_num1 and is_num2:
                            try:
                                v1 = pd.to_numeric(s1, errors="coerce")
                                v2 = pd.to_numeric(s2, errors="coerce")
                                abs_diff = (v1 - v2).abs()
                                max_d = float(abs_diff[diff].max()) if not abs_diff[diff].empty else None
                            except Exception:
                                pass
                        col_mismatches[c] = (cnt, max_d)
                        mismatches += cnt

            lines.append("")
            lines.append("Values:")
            if tol > 0 or rtol > 0:
                tol_desc = []
                if tol > 0:
                    tol_desc.append(f"threshold/atol={tol:g}")
                if rtol > 0:
                    tol_desc.append(f"rtol={rtol:g}")
                lines.append(f"  Tolerance: {', '.join(tol_desc)} (for numeric columns)")

            if mismatches == 0 and cols1 == cols2:
                if tol > 0 or rtol > 0:
                    lines.append("  Identical: all cell values match within tolerance.")
                else:
                    lines.append("  Identical: all cell values match exactly.")
            elif mismatches == 0:
                if tol > 0 or rtol > 0:
                    lines.append("  Matching: all cell values in common columns match within tolerance.")
                else:
                    lines.append("  Matching: all cell values in common columns match.")
            else:
                if tol > 0 or rtol > 0:
                    lines.append(
                        f"  Mismatches found in {mismatches:,} cells exceeding tolerance across common columns:"
                    )
                else:
                    lines.append(f"  Mismatches found in {mismatches:,} cells across common columns:")
                for c, (cnt, max_d) in col_mismatches.items():
                    if max_d is not None:
                        lines.append(f"    * {c}: {cnt:,} cell(s) differ (max diff: {max_d:g})")
                    else:
                        lines.append(f"    * {c}: {cnt:,} cell(s) differ")
        except Exception:
            pass

    return "\n".join(lines)


# Ops whose pandas equivalent does not return a DataFrame (shape -> tuple, cols -> Index,
# dtype -> Series, nulls -> Series, info() -> None, meta -> str, diff -> str). Like real method
# chaining, nothing can follow them except -o clip.
NON_DF_TERMINAL_OPS = frozenset({"shape", "cols", "dtype", "nulls", "meta", "diff", "glimpse", "scatter"})


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
    df: Any,
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
        if isinstance(df, pd.DataFrame):
            df = df.rename(columns=rename)
        elif hasattr(df, "rename"):
            df = df.rename(rename)
    dest = output if output is not None else source.with_suffix(".csv")
    if dest.resolve() == source.resolve():
        raise SystemExit(
            f"refusing to overwrite the source file '{source}'; "
            f"specify a different format or an explicit path with -o/--output"
        )
    try:
        write_dataframe(df, dest, sep=sep, encoding=encoding, progress=progress, chunk_size=chunk_size, index=index)
    except Exception as exc:
        try:
            from pytae.readers import get_reader

            fallback_reader = get_reader(source, sep=sep, encoding=encoding, chunk_size=chunk_size)
            fallback_df = fallback_reader.to_dataframe()
            if rename:
                fallback_df = fallback_df.rename(columns=rename)
            write_dataframe(
                fallback_df, dest, sep=sep, encoding=encoding, progress=progress, chunk_size=chunk_size, index=index
            )
            df = fallback_df
        except Exception:
            raise SystemExit(str(exc)) from exc
    if announce:
        import polars as pl

        if isinstance(df, pl.LazyFrame):
            if dest.suffix in (".parquet", ".pq") and dest.exists():
                import pyarrow.parquet as pa_parquet

                num_rows = pa_parquet.ParquetFile(dest).metadata.num_rows
            elif dest.suffix in (".csv", ".tsv", ".txt") and dest.exists():
                num_rows = pl.scan_csv(dest, separator=sep or ",").select(pl.len()).collect().item()
            elif dest.suffix in (".jsonl", ".ndjson") and dest.exists():
                num_rows = pl.scan_ndjson(dest).select(pl.len()).collect().item()
            else:
                num_rows = df.select(pl.len()).collect().item()
        else:
            num_rows = len(df)
        print(f"Wrote {num_rows} rows to {dest}")


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


def _resolve_alias(
    alias: str, frames: dict[str, pd.DataFrame], pipeline: _Pipeline, flag: str
) -> tuple[pd.DataFrame | None, str | None]:
    """Look up a -join/-concat alias: a -file alias, or 'data' for the pipeline's current
    result so far (lets repeated -join/-concat calls fold in one more file at a time).
    Returns (frame, error_message)."""
    if alias == "data":
        if pipeline._df is None and pipeline._pldf is None:
            return None, f"{flag}: 'data' isn't available yet — nothing has produced a pipeline result yet"
        return pipeline.dataframe(), None
    if alias == "df":
        return None, f"{flag}: 'df' is not a valid alias; use 'data' for the pipeline's current result"
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
    rename_specs: list[dict[str, str]] | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    join_specs: list[dict] | None = None,
    concat_specs: list[dict] | None = None,
    qry_specs: list[list[tuple[str, Any]]] | None = None,
) -> bool:
    """Run every requested display/export/-agg action against one file, or (when frames
    is given, i.e. -file/-join mode) against named in-memory frames instead. Returns True
    if an error occurred."""
    join_specs = join_specs or []
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
                reader,
                nrows=args.nrows,
                progress=args.progress,
                chunk_size=chunk_size,
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
                reader,
                nrows=args.nrows,
                progress=args.progress,
                chunk_size=chunk_size,
            )
        elif str(path) == "<memory>":
            mem_df = getattr(args, "_memory_df", None)
            reader = DataFrameReader(mem_df, path="<memory>")
            pipeline = _Pipeline(
                reader,
                nrows=args.nrows,
                progress=args.progress,
                chunk_size=chunk_size,
            )
        elif str(path).startswith("sample:"):
            from pytae import _DATASET_NAMES, DATA_PATH

            sample_name = str(path)[7:].strip().removesuffix(".parquet")
            sample_file = DATA_PATH / f"{sample_name}.parquet"
            if not sample_file.exists():
                available = ", ".join(_DATASET_NAMES)
                return _fail(parser, batch, f"unknown sample dataset '{sample_name}'. Available: {available}")

            try:
                reader = get_reader(sample_file, sep=args.dlim, encoding=args.encoding, chunk_size=chunk_size)
            except (ValueError, ImportError) as exc:
                return _fail(parser, batch, str(exc))

            pipeline = _Pipeline(
                reader,
                nrows=args.nrows,
                progress=args.progress,
                chunk_size=chunk_size,
            )
        elif path is None or not path.exists():
            return _fail(parser, batch, f"file not found: {path}")
        else:
            try:
                reader = get_reader(path, sep=args.dlim, encoding=args.encoding, chunk_size=chunk_size)
            except (ValueError, ImportError) as exc:
                return _fail(parser, batch, str(exc))

            pipeline = _Pipeline(
                reader,
                nrows=args.nrows,
                progress=args.progress,
                chunk_size=chunk_size,
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
        frame = pipeline.current_frame()
        rounded = _apply_round(frame, args.round_ndigits)
        if emit_stdout:
            _output_text(_format_table(rounded, pretty=args.pretty), args)
        if is_clip:
            df = rounded.to_pandas() if hasattr(rounded, "to_pandas") else rounded
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
    rename_iter = iter(rename_specs or [])
    join_iter = iter(join_specs or [])
    concat_iter = iter(concat_specs or [])

    def should_print(idx: int) -> bool:
        return emit_stdout and idx == last_idx

    def emit_frame(idx: int) -> None:
        nonlocal clip_action
        if not (should_print(idx) or is_clip):
            return
        frame = pipeline.current_frame()
        rounded = _apply_round(frame, args.round_ndigits)
        if should_print(idx):
            _output_text(_format_table(rounded, pretty=args.pretty), args)
        if is_clip:
            df = rounded.to_pandas() if hasattr(rounded, "to_pandas") else rounded
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
        elif op == "filter":
            err = pipeline.apply_filter(next(filter_iter), flag_name="-filter")
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "mutate":
            by_cols = parse_columns(args.by) if args.by else None
            if by_cols:
                avail_cols = pipeline.columns()
                if any(c not in avail_cols for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, avail_cols))
            err = pipeline.apply_mutate(next(mutate_iter), by=by_cols, dropna=False)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "sql":
            err = pipeline.apply_sql(next(sql_iter))
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "join":
            spec = next(join_iter)
            if frames is None:
                return _fail(parser, batch, "-join requires -file")
            left_df, err = _resolve_alias(spec["left"], frames, pipeline, "-join")
            if err or left_df is None:
                return _fail(parser, batch, err or "-join: missing left frame")
            right_df, err = _resolve_alias(spec["right"], frames, pipeline, "-join")
            if err or right_df is None:
                return _fail(parser, batch, err or "-join: missing right frame")
            if spec["how"] == "cross":
                pass  # cross joins don't take on=/left_on=/right_on=
            elif spec["on"] is not None:
                missing = [c for c in spec["on"] if c not in left_df.columns or c not in right_df.columns]
                if missing:
                    return _fail(parser, batch, f"-join: on= column(s) not in both frames: {', '.join(missing)}")
            else:
                missing_left = [c for c in spec["left_on"] if c not in left_df.columns]
                missing_right = [c for c in spec["right_on"] if c not in right_df.columns]
                if missing_left:
                    return _fail(
                        parser, batch, unknown_columns_message("-join (left)", missing_left, list(left_df.columns))
                    )
                if missing_right:
                    return _fail(
                        parser, batch, unknown_columns_message("-join (right)", missing_right, list(right_df.columns))
                    )
            import polars as pl

            left_pl = left_df if isinstance(left_df, pl.DataFrame) else pl.from_pandas(left_df)
            right_pl = right_df if isinstance(right_df, pl.DataFrame) else pl.from_pandas(right_df)
            how: Any = "full" if spec["how"] == "outer" else spec["how"]
            val_map = {
                "1:1": "1:1",
                "one_to_one": "1:1",
                "1:m": "1:m",
                "one_to_many": "1:m",
                "m:1": "m:1",
                "many_to_one": "m:1",
                "m:m": "m:m",
                "many_to_many": "m:m",
            }
            validate_arg: Any = val_map.get(spec["validate"], "m:m") if spec["validate"] else "m:m"
            try:
                if how == "cross":
                    res_pl = left_pl.join(right_pl, how="cross")
                elif spec["on"] is not None:
                    res_pl = left_pl.join(right_pl, on=spec["on"], how=how, validate=validate_arg, coalesce=True)
                elif spec["left_on"] == spec["right_on"]:
                    res_pl = left_pl.join(right_pl, on=spec["left_on"], how=how, validate=validate_arg, coalesce=True)
                else:
                    res_pl = left_pl.join(
                        right_pl,
                        left_on=spec["left_on"],
                        right_on=spec["right_on"],
                        how=how,
                        validate=validate_arg,
                        coalesce=False,
                    )
            except Exception as exc:
                return _fail(parser, batch, f"-join: {exc}")
            pipeline._pldf = res_pl
            pipeline._df = None
            if should_print(idx):
                print(_format_table(_apply_round(res_pl, args.round_ndigits), pretty=args.pretty))
            if is_clip:
                df = res_pl.to_pandas()
                clip_action = lambda d=df: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
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
            import polars as pl

            pl_dfs = [df if isinstance(df, pl.DataFrame) else pl.from_pandas(df) for df in dfs]
            try:
                res_pl = pl.concat(pl_dfs, how="diagonal_relaxed")
            except Exception as exc:
                return _fail(parser, batch, f"-concat: {exc}")
            pipeline._pldf = res_pl
            pipeline._df = None
            if should_print(idx):
                _output_text(_format_table(_apply_round(res_pl, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                df = res_pl.to_pandas()
                clip_action = lambda d=df: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
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
            nulls_s = pipeline.polars_frame().null_count().to_pandas().iloc[0]
            nulls = _list_order_index(nulls_s, args.nulls)
            if should_print(idx):
                _output_text(nulls.to_string(), args)
            if is_clip:
                clip_action = lambda s=nulls: s.to_clipboard()
        elif op == "describe":
            described = pipeline.dataframe().describe()
            pipeline._df = described
            if should_print(idx):
                _output_text(
                    _format_table(_apply_round(described, args.round_ndigits), index=True, pretty=args.pretty), args
                )
            if is_clip:
                clip_action = lambda d=described: _apply_round(d, args.round_ndigits).to_clipboard(index=True)
        elif op == "glimpse":
            from pytae.other_utilities import format_glimpse

            glimpse_str = format_glimpse(pipeline.current_frame())
            if should_print(idx):
                _output_text(glimpse_str, args)
            if is_clip:
                clip_action = lambda s=glimpse_str: _copy_to_clipboard(s)
        elif op == "meta":
            meta_str = _extract_metadata(
                path if path is not None else Path("<joined>"), sep=args.dlim, encoding=args.encoding
            )
            if should_print(idx):
                _output_text(meta_str, args)
            if is_clip:
                clip_action = lambda s=meta_str: _copy_to_clipboard(s)
        elif op == "diff":
            diff_path = Path(args.diff)
            diff_tol = getattr(args, "tol", None) or 0.0
            diff_str = _compute_diff(
                pipeline.dataframe(),
                diff_path,
                path.name if path is not None else "<pipeline>",
                tol=diff_tol,
                sep=args.dlim,
                encoding=args.encoding,
            )
            if should_print(idx):
                _output_text(diff_str, args)
            if is_clip:
                clip_action = lambda s=diff_str: _copy_to_clipboard(s)
        elif op == "freq":
            freq_col = _next_op_val("freq", getattr(args, "freq", None))
            source_df = pipeline.current_frame()
            result = _compute_freq(source_df, freq_col, False if args.dropna is None else args.dropna)
            pipeline._pldf = result._df if hasattr(result, "_df") else result
            pipeline._df = None
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "hist":
            hist_arg = _next_op_val("hist", getattr(args, "hist", None))
            source_df = pipeline.current_frame()
            result = _compute_hist(source_df, hist_arg)
            pipeline._pldf = result._df if hasattr(result, "_df") else result
            pipeline._df = None
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty, tbl_rows=250), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "bar":
            bar_arg = _next_op_val("bar", getattr(args, "bar", None))
            source_df = pipeline.current_frame()
            result = _compute_bar(source_df, bar_arg)
            pipeline._pldf = result._df if hasattr(result, "_df") else result
            pipeline._df = None
            if should_print(idx):
                _output_text(_format_table(_apply_round(result, args.round_ndigits), pretty=args.pretty, tbl_rows=250), args)
            if is_clip:
                clip_action = lambda d=result: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "scatter":
            scatter_arg = _next_op_val("scatter", getattr(args, "scatter", None))
            source_df = pipeline.current_frame()
            scatter_str = _compute_scatter(source_df, scatter_arg)
            if should_print(idx):
                _output_text(scatter_str, args)
            if is_clip:
                clip_action = lambda s=scatter_str: _copy_to_clipboard(s)
        elif op == "corr":
            corr_arg = _next_op_val("corr", getattr(args, "corr", None))
            source_df = pipeline.current_frame()
            result = _compute_corr(source_df, corr_arg)
            pipeline._pldf = result._df if hasattr(result, "_df") else result
            pipeline._df = None
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
        elif op == "count":
            by_cols = parse_columns(args.by) if (args.by and args.agg is None and not args.mutate) else None
            count_val = _next_op_val("count", getattr(args, "count", None))
            err = pipeline.apply_count(count_val, by_cols=by_cols)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "head":
            by_cols = parse_columns(args.by) if (args.by and args.agg is None and not args.mutate) else None
            if by_cols:
                avail_cols = pipeline.columns()
                if any(c not in avail_cols for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, avail_cols))
            head_val = _next_op_val("head", args.head)
            try:
                frame = pipeline.head(head_val, by=by_cols)
            except Exception as exc:
                return _fail(parser, batch, f"-head: {exc}")
            if hasattr(frame, "collect"):
                frame = frame.collect()
            if should_print(idx):
                _output_text(_format_table(_apply_round(frame, args.round_ndigits), pretty=args.pretty, tbl_rows=max(len(frame), 10)), args)
            if is_clip:
                df = frame.to_pandas() if hasattr(frame, "to_pandas") else frame
                clip_idx = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
                clip_action = lambda d=df, ci=clip_idx: _apply_round(d, args.round_ndigits).to_clipboard(index=ci)
        elif op == "tail":
            by_cols = parse_columns(args.by) if (args.by and args.agg is None and not args.mutate) else None
            if by_cols:
                avail_cols = pipeline.columns()
                if any(c not in avail_cols for c in by_cols):
                    return _fail(parser, batch, unknown_columns_message("-by", by_cols, avail_cols))
            tail_val = _next_op_val("tail", args.tail)
            try:
                frame = pipeline.tail(tail_val, by=by_cols)
            except Exception as exc:
                return _fail(parser, batch, f"-tail: {exc}")
            if hasattr(frame, "collect"):
                frame = frame.collect()
            if should_print(idx):
                _output_text(_format_table(_apply_round(frame, args.round_ndigits), pretty=args.pretty, tbl_rows=max(len(frame), 10)), args)
            if is_clip:
                df = frame.to_pandas() if hasattr(frame, "to_pandas") else frame
                clip_idx = not (isinstance(df.index, pd.RangeIndex) and df.index.name is None)
                clip_action = lambda d=df, ci=clip_idx: _apply_round(d, args.round_ndigits).to_clipboard(index=ci)
        elif op == "sample":
            sample_val = _next_op_val("sample", args.sample)
            sampled = pipeline.sample(sample_val, seed=args.seed, frac=args.frac)
            n = len(sampled)
            if should_print(idx):
                _output_text(
                    _format_table(_apply_round(sampled, args.round_ndigits), pretty=args.pretty, tbl_rows=max(n, 10)) if n else "(no rows)",
                    args,
                )
            if is_clip and n:
                df = sampled.to_pandas() if hasattr(sampled, "to_pandas") else sampled
                clip_action = lambda d=df: _apply_round(d, args.round_ndigits).to_clipboard(index=False)
        elif op == "arrange":
            arrange_val = _next_op_val("arrange", getattr(args, "arrange", None))
            err = pipeline.apply_arrange(arrange_val)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "agg":
            agg_val = _next_op_val("agg", args.agg)
            if isinstance(agg_val, str):
                parse_agg(agg_val)
            by_cols = parse_columns(args.by) if args.by else None
            avail_cols = pipeline.columns()
            if by_cols and any(c not in avail_cols for c in by_cols):
                return _fail(parser, batch, unknown_columns_message("-by", by_cols, avail_cols))
            try:
                from pytae.polars_engine import agg_polars

                pl_res = agg_polars(pipeline.polars_frame(), agg_val, by=by_cols, dropna=False)
                pipeline._pldf = pl_res
                pipeline._df = None
            except Exception as e:
                return _fail(parser, batch, str(e))
            emit_frame(idx)
        elif op == "fillna":
            val_str = _next_op_val("fillna", args.fillna)
            fill_val, fill_cols, fill_nans = parse_fillna_spec(
                val_str, flag_name="-fillna", available_cols=pipeline.columns()
            )
            err = pipeline.apply_fillna(fill_val, cols=fill_cols, nans=fill_nans)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "dropna":
            dropna_val = _next_op_val("dropna", getattr(args, "dropna", None))
            err = pipeline.apply_dropna(dropna_val)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "clean_columns":
            cc_val = _next_op_val("clean_columns", args.clean_columns)
            opts = parse_clean_columns_arg(cc_val)
            try:
                from pytae.polars_engine import clean_columns_polars

                pl_res = clean_columns_polars(pipeline.polars_frame(), **opts)
                pipeline._pldf = pl_res
                pipeline._df = None
            except Exception:
                from pytae.other_utilities import clean_columns

                result = clean_columns(pipeline.dataframe(), **opts)
                pipeline._df = result
                pipeline._pldf = None
            emit_frame(idx)
        elif op == "mask":
            mask_val = _next_op_val("mask", getattr(args, "mask", None))
            err = pipeline.apply_mask(mask_val, key=args.key, salt=args.salt, vault=args.vault)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "unmask":
            unmask_val = _next_op_val("unmask", getattr(args, "unmask", None))
            err = pipeline.apply_unmask(unmask_val, key=args.key, vault=args.vault)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "long":
            long_val = _next_op_val("long", args.long)
            long_kwargs = parse_long_arg(long_val)
            cols_arg = long_kwargs.get("cols")
            avail_cols = pipeline.columns()
            if cols_arg:
                cols_list = parse_columns(cols_arg) if isinstance(cols_arg, str) else list(cols_arg)
                missing = [c for c in cols_list if c not in avail_cols]
                if missing:
                    return _fail(parser, batch, unknown_columns_message("-long", missing, avail_cols))
            try:
                from pytae.polars_engine import long_polars

                pl_res = long_polars(pipeline.polars_frame(), **long_kwargs)
                pipeline._pldf = pl_res
                pipeline._df = None
            except Exception as exc:
                return _fail(parser, batch, str(exc))
            emit_frame(idx)
        elif op == "wide":
            wide_val = _next_op_val("wide", args.wide)
            wide_kwargs = parse_wide_arg(wide_val)
            to_check = [wide_kwargs.get("c", "variable"), wide_kwargs.get("v", "value")]
            r_cols = wide_kwargs.get("r")
            if r_cols:
                to_check.extend(parse_columns(r_cols) if isinstance(r_cols, str) else list(r_cols))
            avail_cols = pipeline.columns()
            missing = [c for c in to_check if c not in avail_cols]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-wide", missing, avail_cols))
            try:
                from pytae.polars_engine import wide_polars

                pl_res = wide_polars(pipeline.polars_frame(), **wide_kwargs)
                pipeline._pldf = pl_res
                pipeline._df = None
            except Exception as exc:
                return _fail(parser, batch, str(exc))
            emit_frame(idx)
        elif op == "pivot":
            pivot_val = _next_op_val("pivot", getattr(args, "pivot", None))
            pivot_kwargs = parse_pivot_arg(pivot_val)
            if "dropna" not in pivot_kwargs:
                pivot_kwargs["dropna"] = False if args.dropna is None else args.dropna
            to_check = []
            for k in ("r", "c"):
                val = pivot_kwargs.get(k)
                if val:
                    to_check.extend(parse_columns(val) if isinstance(val, str) else list(val))
            if pivot_kwargs.get("v"):
                from pytae._parsing import parse_pivot_metrics

                parsed_metrics = parse_pivot_metrics(pivot_kwargs["v"], a=pivot_kwargs.get("a", "sum"))
                for m in parsed_metrics:
                    if m.src_col is not None:
                        to_check.append(m.src_col)
            available_cols = pipeline.columns()
            missing = [col for col in to_check if col not in available_cols]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-pivot", missing, available_cols))
            try:
                from pytae.polars_engine import pivot_polars

                pl_res = pivot_polars(pipeline.polars_frame(), **pivot_kwargs)
                pipeline._pldf = pl_res
                pipeline._df = None
            except Exception as exc:
                return _fail(parser, batch, str(exc))
            emit_frame(idx)
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
            "csv",
            "parquet",
            "pq",
            "txt",
            "dat",
            "jsonl",
            "ndjson",
            "csv.gz",
            "txt.gz",
            "dat.gz",
            "jsonl.gz",
            "ndjson.gz",
        )
        if fmt in valid_formats:
            if path is None or str(path) == "-":
                return _fail(
                    parser,
                    batch,
                    f"-o {out_target}: when reading from STDIN or -file mode, an explicit output file path is required",
                )
            ext = ".parquet" if fmt == "pq" else f".{fmt}"
            clean_name = path.name[:-3] if path.name.lower().endswith(".gz") else path.name
            dest_name = f"{Path(clean_name).stem}{ext}"
            dest = (out_dir / dest_name) if out_dir is not None else path.with_name(dest_name)
        else:
            dest = Path(out_target)
            if out_dir is not None and not dest.is_absolute():
                dest = out_dir / dest

        import polars as pl

        if (
            args.round_ndigits is None
            and pipeline._df is None
            and not pipeline._progress
            and pipeline._reader is not None
            and hasattr(pipeline._reader, "to_polars_lazy")
        ) or (args.round_ndigits is None and isinstance(pipeline._pldf, pl.LazyFrame)):
            df_to_write = pipeline.polars_lazy_frame()
        else:
            df_to_write = _apply_round(pipeline.current_frame(), args.round_ndigits)
        try:
            cmd_convert(
                df_to_write,
                path if path is not None else Path("<joined>"),
                dest,
                sep=args.dlim,
                encoding=args.encoding,
                progress=args.progress,
                announce=True,
                chunk_size=getattr(args, "chunk_size", None) or 200_000,
            )
        except SystemExit as exc:
            return _fail(parser, batch, str(exc))

    if getattr(args, "repl", False) or str(path) == "<memory>":
        setattr(args, "_result_frame", pipeline.current_frame())
    setattr(args, "_result_pipeline", pipeline)
    return False
