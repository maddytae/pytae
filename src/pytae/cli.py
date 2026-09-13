"""Command line tool for inspecting tabular files (parquet/csv/txt/sas7bdat) and converting between formats."""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

import pandas as pd

from pytae.agg_df import agg_df  # noqa: F401  — registers pd.DataFrame.agg_df
from pytae.cli_parsing import (
    expand_paths,
    parse_agg,
    parse_bool_text,
    parse_clean_columns_arg,
    parse_columns,
    parse_concat_arg,
    parse_crosstab_arg,
    parse_file_arg,
    parse_fraction,
    parse_group_agg,
    parse_group_x_arg,
    parse_list_order,
    parse_long_arg,
    parse_merge_arg,
    parse_positive_int,
    parse_qry,
    parse_rename,
    parse_replace_arg,
    parse_select_spec,
    parse_wide_arg,
    unknown_columns_message,
)
from pytae.cli_pipeline import (
    _OrderedAppend,
    _OrderedFlag,
    _OrderedSortBy,
    _OrderedStore,
    _OrderedValue,
    _Pipeline,
)
from pytae.other_utilities import group_x, handle_missing  # noqa: F401
from pytae.qry import qry  # noqa: F401
from pytae.readers import get_reader, write_dataframe
from pytae.select import select  # noqa: F401

try:
    __version__ = _pkg_version("pytae")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


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


# Ops whose pandas equivalent does not return a DataFrame (shape -> tuple, cols -> Index,
# dtype -> Series, nulls -> Series, info() -> None). Like real method chaining, nothing can
# follow them except -to_clip. -describe is excluded: df.describe() returns a DataFrame.
NON_DF_TERMINAL_OPS = frozenset({"shape", "cols", "dtype", "nulls", "info"})


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
) -> None:
    if rename:
        df = df.rename(columns=rename)
    dest = output if output is not None else source.with_suffix(".csv")
    if dest.resolve() == source.resolve():
        raise SystemExit(f"refusing to overwrite the source file '{source}'; pass -o/--output to choose a different path")
    try:
        write_dataframe(df, dest, sep=sep, encoding=encoding, progress=progress)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if announce:
        print(f"Wrote {len(df)} rows to {dest}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytae",
        description="Inspect and convert parquet/csv/txt/dat/sas7bdat files (glob patterns convert multiple files at once).",
        allow_abbrev=False,
    )
    parser.add_argument("path", nargs="?", default=None,
                         help="path to a .parquet, .csv, .txt, .dat, or .sas7bdat file, "
                                      "or a glob pattern like 'data/*.parquet' for batch conversion; "
                                      "omit when using -file/-merge instead")
    parser.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-head", "--head", nargs="?", const=5, type=parse_positive_int, default=None, metavar="N",
                         action=_OrderedValue, help="print the first N rows (default 5)")
    parser.add_argument("-tail", "--tail", nargs="?", const=5, type=parse_positive_int, default=None, metavar="N",
                         action=_OrderedValue, help="print the last N rows (default 5)")
    parser.add_argument("-shape", "--shape", action=_OrderedFlag, help="print (rows, cols)")
    parser.add_argument("-cols", "--cols", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print column names; optional asc|desc sorts names (default: file order)")
    parser.add_argument("-dtype", "--dtype", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print column dtypes; optional asc|desc sorts by name (default: file order)")
    parser.add_argument("-nulls", "--nulls", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print null/NaN count per column; optional asc|desc sorts by name (default: file order)")
    parser.add_argument("-describe", "--describe", dest="describe", action=_OrderedFlag,
                         help="print pandas describe() summary (count/mean/std/min/quartiles/max)")
    parser.add_argument("-info", "--info", dest="info", action=_OrderedFlag,
                         help="print pandas info() (columns, non-null counts, dtypes, memory)")
    parser.add_argument("-value_counts", "--value_counts", dest="value_counts", action=_OrderedFlag,
                         help="show pandas value_counts across current working columns (use -select to choose columns)")
    parser.add_argument("-unique", "--unique", dest="unique", action=_OrderedFlag,
                         help="drop duplicate rows and print unique rows")
    parser.add_argument("-sample", "--sample", nargs="?", const=5, type=parse_positive_int, default=None, metavar="N",
                         action=_OrderedValue, help="print N randomly sampled rows (default 5)")
    parser.add_argument("-seed", "--seed", dest="seed", type=int, default=None, metavar="N",
                         help="random seed for -sample, for reproducible rows (default: random each run)")
    parser.add_argument("-frac", "--frac", dest="frac", type=parse_fraction, default=None, metavar="P",
                         help="sample a fraction of rows instead of a count (0 < P <= 1, e.g. 0.1 for 10 percent); "
                              "requires -sample and overrides its N")
    parser.add_argument("-sort_by", "--sort_by", dest="sort_by", nargs="+", default=None, metavar="COLUMNS",
                         action=_OrderedSortBy,
                         help="sort rows by column(s), comma-separated; optional asc|desc (default: asc)")
    parser.add_argument("-group_by", "--group_by", dest="group_by", default=None, metavar="COLUMNS",
                         help="explicit group-by columns for -agg (comma-separated); also used by -group_x "
                              "if group= is omitted")
    parser.add_argument("-nrows", "--nrows", "-limit", "--limit", dest="nrows", type=parse_positive_int, default=None, metavar="N",
                         help="cap the number of rows loaded (default: no cap)")
    parser.add_argument("--select", "-select", dest="select", action=_OrderedAppend, default=None, metavar="SPEC",
                         help="restrict columns at this point in the pipeline (union of tokens in one SPEC): "
                              "names, start:end slices, and key=value (dtype, contains, startswith, endswith, "
                              "regex, exclude_dtype); repeat to filter remaining columns, including after "
                              "-agg_df/-long/-wide, e.g. -select dtype=numeric -select contains=bill")
    parser.add_argument("-convert", "--convert", dest="convert",
                         action=_OrderedFlag,
                         help="convert to another format (.parquet/.csv/.txt/.dat, inferred from -o's extension, "
                              "defaults to .csv); use -select to restrict columns")
    parser.add_argument("-agg_df", "--agg_df", dest="agg_df", nargs="?", const="sum", default=None,
                         metavar="AGGFUNC", action=_OrderedValue,
                         help="aggregate using pytae agg_df; auto-detects group columns (non-numeric); "
                              "defaults to 'sum' when no value given; "
                              "accepts string ('mean'), list (\"['sum','mean']\"), or dict, surrounding {} "
                              "optional (\"'col':'sum','n':'n'\")")
    parser.add_argument("-agg", "--agg", dest="agg", metavar="KEY=VALUE,...", action=_OrderedStore,
                         help="aggregate using explicit -group_by columns; key=value specs "
                              "(column=, aggfunc=, optional as=), e.g. "
                              "column='value',aggfunc='sum',as='v'; several specs separated by ';'; requires -group_by")
    parser.add_argument("-group_x", "--group_x", dest="group_x", nargs="?", const="", default=None,
                         metavar="KEY=VALUE,...", action=_OrderedValue,
                         help="broadcast a group aggregate back to every row (pytae group_x()); default is group "
                              "size n on non-numeric columns; e.g. group='species',v='body_mass_g',a='max'")
    parser.add_argument("-handle_missing", "--handle_missing", dest="handle_missing", nargs="?", const=".", default=None,
                         metavar="FILL", action=_OrderedValue,
                         help="fill NaN using pytae handle_missing(): FILL (default '.') for object/category "
                              "columns, 0 for numeric columns")
    parser.add_argument("-clean_columns", "--clean_columns", dest="clean_columns", action=_OrderedStore,
                         metavar="KEY=VALUE,...",
                         help="clean column header names, in order strip -> strip_special -> squeeze -> "
                              "fill -> case -> dedupe: strip/squeeze/strip_special/dedupe are bools (bare "
                              "key means true, e.g. \"strip\"), fill[=STR] replaces whitespace in a header "
                              "(bare \"fill\" defaults to '_', omit entirely for no fill), "
                              "case=lower|upper|proper (always needs a value); e.g. "
                              "\"strip,fill,case=lower\" or \"fill='$',case=proper,dedupe=true\"")
    parser.add_argument("-long", "--long", dest="long", nargs="?", const="", default=None,
                         metavar="KEY=VALUE,...", action=_OrderedValue,
                         help="melt numeric columns to long form (pytae long()); defaults c=variable, "
                              "v=value; e.g. c='metric',v='reading'")
    parser.add_argument("-wide", "--wide", dest="wide", nargs="?", const="", default=None,
                         metavar="KEY=VALUE,...", action=_OrderedValue,
                         help="pivot long form to wide (pytae wide()); defaults c=variable, v=value; "
                              "e.g. c='country',v='balance',a='mean'; a='n' is an alias for pandas' 'size' "
                              "(group row count), matching agg_df's convention")
    parser.add_argument("-crosstab", "--crosstab", dest="crosstab", metavar="KEY=VALUE,...", action=_OrderedStore,
                         help="cross-tabulate columns into a matrix (pandas crosstab()); key=value specs: "
                              "index= (one or more comma-separated columns), columns= (single column, required), "
                              "optional values=+aggfunc= together to aggregate instead of count, "
                              "normalize=index|columns|all, margins=true|false, margins_name= (default 'All'; "
                              "requires margins=true); honors -dropna")
    parser.add_argument("-dropna", "--dropna", dest="dropna", type=parse_bool_text, default=True,
                         metavar="BOOL",
                         help="for -agg_df, -agg, -value_counts, and -crosstab: include NA keys when false; accepts true or false (default: true)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="output path; its extension picks the format (default: .csv alongside the source file)")
    parser.add_argument("-dlim", "--dlim", dest="dlim", default=None, metavar="CHAR",
                         help="field delimiter for reading/writing .csv/.txt/.dat/.sas7bdat (default: ',' for .csv, "
                              "tab for .txt, '|' for .dat); not used for .parquet")
    parser.add_argument("-encoding", "--encoding", dest="encoding", default=None, metavar="ENC",
                         help="text encoding for .csv/.txt/.dat/.sas7bdat, e.g. latin-1 "
                              "(default: utf-8 for .sas7bdat, pandas infer for .csv/.txt/.dat); not used for .parquet")
    parser.add_argument("-rename", "--rename", dest="rename", default=None, metavar="OLD:NEW,...",
                         help="rename columns during conversion, e.g. \"old_a:new_a,old_b:new_b\"")
    parser.add_argument("-file", "--file", dest="file", default=None, metavar="PATH=ALIAS,...",
                         help="load multiple named files for -merge, instead of the positional path; "
                              "';'-separated entries, each PATH=ALIAS optionally followed by "
                              ",dlim=/,encoding= overrides for that file, e.g. "
                              "\"data1.parquet=df1; data2.parquet=df2,encoding='latin-1'\"; "
                              "requires -merge, and can't be combined with the positional path")
    parser.add_argument("-query", "--query", dest="query", action=_OrderedAppend, default=None, metavar="EXPR",
                         help="filter rows at this point in the pipeline using pandas query(), e.g. \"col > 5\"")
    parser.add_argument("-qry", "--qry", dest="qry", action=_OrderedAppend, default=None, metavar="CONDITIONS",
                         help="filter rows at this point in the pipeline using pytae qry(); dict entries, "
                              "surrounding {} optional, e.g. \"'col': ('>', 5), 'other': ['a', 'b']\"")
    parser.add_argument("-sql", "--sql", dest="sql", action=_OrderedAppend, default=None, metavar="QUERY",
                         help="run a SQL query (via duckdb) against the current view at this point in "
                              "the pipeline; the view is queryable as table `df`; standard SQL identifier "
                              "quoting applies (double quotes for names with spaces, e.g. \"col a\"; single "
                              "quotes are string literals, not identifiers), e.g. "
                              "\"select \\\"col a\\\" from df where \\\"col a\\\" > 10\"; "
                              "in -file/-merge mode, may be used instead of -merge as the first op, with "
                              "every -file alias queryable by its own name (e.g. \"select * from df1 "
                              "inner join df2 on df1.\\\"col a\\\" = df2.cola\") — `df` becomes queryable "
                              "too once something later in the pipeline has produced a current view")
    parser.add_argument("-replace", "--replace", dest="replace", action=_OrderedAppend, default=None, metavar="SPEC",
                         help="replace values at this point in the pipeline; key=value tokens: v= (required) "
                              "an old:new mapping, e.g. \"v='old:new,alpha:bravo'\"; c= (optional) restrict "
                              "to specific columns, e.g. \"c='col a,col b',v='old:new'\"; exact= (optional bool, "
                              "default true) — true matches whole cell values, false matches a substring "
                              "anywhere in the cell, e.g. \"v='old:new',exact=false\"")
    parser.add_argument("-merge", "--merge", dest="merge", action=_OrderedAppend, default=None, metavar="KEY=VALUE,...",
                         help="merge two frames into the pipeline (pandas merge()); repeatable, to fold in "
                              "one more file at a time; must be the first op when using -file (unless -sql/"
                              "-concat starts it instead); key=value tokens: left=/right= (required — -file "
                              "aliases, or 'df' for the pipeline's current result so far), "
                              "on= (required; shared column name(s), or 'left:right' pairs if they "
                              "differ between sides — quote on= if it has more than one column/pair, e.g. "
                              "\"on='col a:cola,colb:colb'\"), how= (optional, default 'inner': "
                              "inner/left/right/outer/cross), validate= (optional, e.g. one_to_one)")
    parser.add_argument("-concat", "--concat", dest="concat", action=_OrderedAppend, default=None, metavar="KEY=VALUE,...",
                         help="stack frames row-wise into the pipeline (pandas concat(), always with "
                              "ignore_index=True); repeatable; must be the first op when using -file "
                              "(unless -sql/-merge starts it instead); key=value tokens: frames= (required) "
                              "an ordered comma-separated list of -file aliases (or 'df' for the pipeline's "
                              "current result so far), quoted since it has internal commas, e.g. "
                              "\"frames='df1,df2,df3'\"")
    parser.add_argument("-progress", "--progress", action="store_true",
                         help="show row-count progress while converting large files")
    parser.add_argument("-pretty", "--pretty", action="store_true",
                         help="render tables as a bordered markdown table instead of plain pandas text")
    parser.add_argument("-round", "--round", dest="round_ndigits", type=int, default=None, metavar="N",
                         help="round numeric columns to N decimal places before printing/copying; "
                              "non-numeric columns are left unchanged")
    parser.add_argument("-to_clip", "--to_clip", action="store_true",
                         help="also copy the result to the system clipboard: real tab-separated data "
                              "for DataFrame/Series output (-head/-tail/-nulls/-cols/etc.), plain text for -shape "
                              "(cannot combine -shape with a DataFrame-producing flag)")
    return parser


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
    if alias == "df":
        if pipeline._df is None:
            return None, f"{flag}: 'df' isn't available yet — nothing has produced a pipeline result yet"
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
    qry_specs: list[dict],
    query_specs: list[str],
    sql_specs: list[str],
    replace_specs: list[tuple[list[str] | None, dict[str, str], bool]],
    rename_map: dict[str, str] | None,
    frames: dict[str, pd.DataFrame] | None = None,
    merge_specs: list[dict] = (),
    concat_specs: list[dict] = (),
) -> bool:
    """Run every requested display/-convert/-agg action against one file, or (when frames
    is given, i.e. -file/-merge mode) against named in-memory frames instead. Returns True
    if an error occurred."""
    if frames is None:
        if not path.exists():
            return _fail(parser, batch, f"file not found: {path}")

        try:
            reader = get_reader(path, sep=args.dlim, encoding=args.encoding)
        except ValueError as exc:
            return _fail(parser, batch, str(exc))

        pipeline = _Pipeline(
            reader, nrows=args.nrows, progress=args.progress,
        )
    else:
        pipeline = _Pipeline(frames=frames)

    clip_action = None
    emit_stdout = not args.to_clip

    if show_all:
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if emit_stdout:
            print(_format_table(df, pretty=args.pretty))
        if args.to_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    select_iter = iter(select_specs)
    qry_iter = iter(qry_specs)
    query_iter = iter(query_specs)
    sql_iter = iter(sql_specs)
    replace_iter = iter(replace_specs)
    merge_iter = iter(merge_specs)
    concat_iter = iter(concat_specs)

    def should_print(idx: int) -> bool:
        return emit_stdout and idx == last_idx

    def emit_frame(idx: int) -> None:
        nonlocal clip_action
        if not (should_print(idx) or args.to_clip):
            return
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if should_print(idx):
            print(_format_table(df, pretty=args.pretty))
        if args.to_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    for idx, op in enumerate(op_order):
        if op == "select":
            names, kwargs = next(select_iter)
            err = pipeline.apply_select(names, kwargs)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "qry":
            err = pipeline.apply_qry(next(qry_iter))
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
        elif op == "replace":
            cols, mapping, exact = next(replace_iter)
            err = pipeline.apply_replace(cols, mapping, exact)
            if err:
                return _fail(parser, batch, err)
            emit_frame(idx)
        elif op == "merge":
            spec = next(merge_iter)
            left_df, err = _resolve_alias(spec["left"], frames, pipeline, "-merge")
            if err:
                return _fail(parser, batch, err)
            right_df, err = _resolve_alias(spec["right"], frames, pipeline, "-merge")
            if err:
                return _fail(parser, batch, err)
            merge_kwargs = {"how": spec["how"]}
            if spec["validate"]:
                merge_kwargs["validate"] = spec["validate"]
            if spec["on"] is not None:
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
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "concat":
            spec = next(concat_iter)
            dfs = []
            for alias in spec["frames"]:
                df, err = _resolve_alias(alias, frames, pipeline, "-concat")
                if err:
                    return _fail(parser, batch, err)
                dfs.append(df)
            try:
                result = pd.concat(dfs, ignore_index=True)
            except Exception as exc:
                return _fail(parser, batch, f"-concat: {exc}")
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "shape":
            shape_str = str(pipeline.shape())
            if should_print(idx):
                print(shape_str)
            if args.to_clip:
                clip_action = lambda s=shape_str: _copy_to_clipboard(s)
        elif op == "cols":
            names = _list_order_names(pipeline.columns(), args.cols)
            if should_print(idx):
                for name in names:
                    print(name)
            if args.to_clip:
                clip_action = lambda n=names: pd.Series(n).to_clipboard(index=False, header=False)
        elif op == "dtype":
            dtypes = _list_order_index(pipeline.dtypes(), args.dtype)
            if should_print(idx):
                print(dtypes.to_string())
            if args.to_clip:
                clip_action = lambda s=dtypes: s.to_clipboard()
        elif op == "nulls":
            nulls = _list_order_index(pipeline.dataframe().isna().sum(), args.nulls)
            if should_print(idx):
                print(nulls.to_string())
            if args.to_clip:
                clip_action = lambda s=nulls: s.to_clipboard()
        elif op == "describe":
            described = _apply_round(pipeline.dataframe().describe(), args.round_ndigits)
            pipeline._df = described
            if should_print(idx):
                print(_format_table(described, index=True, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=described: d.to_clipboard(index=True)
        elif op == "info":
            info_str = _dataframe_info(pipeline.dataframe())
            if should_print(idx):
                print(info_str)
            if args.to_clip:
                clip_action = lambda s=info_str: _copy_to_clipboard(s)
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
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "unique":
            unique_df = _apply_round(pipeline.dataframe().drop_duplicates().reset_index(drop=True), args.round_ndigits)
            pipeline._df = unique_df
            if should_print(idx):
                print(_format_table(unique_df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=unique_df: d.to_clipboard(index=False)
        elif op == "head":
            df = _apply_round(pipeline.head(args.head), args.round_ndigits)
            if should_print(idx):
                print(_format_table(df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "tail":
            df = _apply_round(pipeline.tail(args.tail), args.round_ndigits)
            if should_print(idx):
                print(_format_table(df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "sample":
            sampled = _apply_round(pipeline.sample(args.sample, seed=args.seed, frac=args.frac), args.round_ndigits)
            n = len(sampled)
            if should_print(idx):
                print(_format_table(sampled, pretty=args.pretty) if n else "(no rows)")
            if args.to_clip and n:
                clip_action = lambda d=sampled: d.to_clipboard(index=False)
        elif op == "sort_by":
            source_df = pipeline.dataframe()
            sort_cols = parse_columns(args.sort_by)
            if any(c not in source_df.columns for c in sort_cols):
                return _fail(parser, batch, unknown_columns_message("-sort_by", sort_cols, list(source_df.columns)))
            ascending = getattr(args, "sort_by_order", "asc") != "desc"
            sorted_df = _apply_round(source_df.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True), args.round_ndigits)
            pipeline._df = sorted_df
            if should_print(idx):
                print(_format_table(sorted_df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=sorted_df: d.to_clipboard(index=False)
        elif op == "agg_df":
            aggfunc = parse_agg(args.agg_df)
            result = _apply_round(pipeline.dataframe().agg_df(a=aggfunc, dropna=args.dropna), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
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
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "group_x":
            source_df = pipeline.dataframe()
            gx = parse_group_x_arg(args.group_x)
            if "group" not in gx and args.group_by:
                gx["group"] = parse_columns(args.group_by)
            if "dropna" not in gx:
                gx["dropna"] = args.dropna
            group_cols = gx.get("group")
            if group_cols and any(c not in source_df.columns for c in group_cols):
                return _fail(parser, batch, unknown_columns_message("-group_x", group_cols, list(source_df.columns)))
            value_col = gx.get("v")
            if value_col and value_col not in source_df.columns:
                return _fail(parser, batch, unknown_columns_message("-group_x", [value_col], list(source_df.columns)))
            result = _apply_round(source_df.group_x(**gx), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "handle_missing":
            result = _apply_round(pipeline.dataframe().handle_missing(fillna=args.handle_missing), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "clean_columns":
            opts = parse_clean_columns_arg(args.clean_columns)
            result = _apply_round(pipeline.dataframe().clean_columns(**opts), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "long":
            from pytae.shape import long as long_fn
            result = _apply_round(long_fn(pipeline.dataframe(), **parse_long_arg(args.long)), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "wide":
            from pytae.shape import wide as wide_fn
            source_df = pipeline.dataframe()
            wide_kwargs = parse_wide_arg(args.wide)
            missing = [c for c in (wide_kwargs.get("c", "variable"), wide_kwargs.get("v", "value"))
                       if c not in source_df.columns]
            if missing:
                return _fail(parser, batch, unknown_columns_message("-wide", missing, list(source_df.columns)))
            result = _apply_round(wide_fn(source_df, **wide_kwargs), args.round_ndigits)
            pipeline._df = result
            if should_print(idx):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
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
                print(_format_table(result, index=True, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=True)
        elif op == "convert":
            if path is None and args.output is None:
                return _fail(parser, batch, "-convert requires -o/--output in -file/-merge mode (no source file to derive a default from)")
            cmd_convert(
                pipeline.dataframe(), path if path is not None else Path("<merged>"), args.output,
                rename=rename_map, sep=args.dlim, encoding=args.encoding, progress=args.progress,
                announce=should_print(idx),
            )

    if args.to_clip and clip_action is not None:
        clip_action()

    return False


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    for idx, op in enumerate(op_order):
        if op in NON_DF_TERMINAL_OPS and idx != last_idx:
            parser.error(
                f"-{op} does not return a DataFrame/Series, so no flag may follow it "
                f"except -to_clip (matches pandas: you can't chain another call off "
                f"df.shape/df.columns/df.dtypes/df.info())"
            )

    if args.merge and args.file is None:
        parser.error("-merge requires -file")
    if args.concat and args.file is None:
        parser.error("-concat requires -file")
    if args.file is not None:
        if args.path is not None:
            parser.error("-file/-merge can't be combined with a positional path; list every input via -file instead")
        if not op_order or op_order[0] not in ("merge", "sql", "concat"):
            parser.error("-file requires -merge, -concat, or -sql as its first operation")
    elif args.path is None:
        parser.error("the following arguments are required: path")

    show_all = not any([args.shape, args.cols, args.dtype, args.nulls, args.describe, args.info,
                         args.value_counts, args.unique, args.head is not None,
                         args.tail is not None, args.sample is not None, args.sort_by is not None,
                         args.convert, args.agg_df is not None, args.agg is not None,
                         args.group_x is not None, args.handle_missing is not None,
                         args.long is not None, args.wide is not None, args.crosstab is not None,
                         args.select, args.qry, args.query, args.sql, args.replace,
                         args.clean_columns is not None, args.merge, args.concat])

    wants_df = any([args.cols, args.dtype, args.nulls, args.describe, show_all,
                     args.value_counts, args.unique, args.head is not None,
                     args.tail is not None, args.sample is not None, args.sort_by is not None,
                     args.agg_df is not None, args.agg is not None,
                     args.group_x is not None, args.handle_missing is not None,
                     args.long is not None, args.wide is not None, args.crosstab is not None,
                     args.clean_columns is not None, args.merge, args.concat])
    if args.to_clip and args.shape and wants_df:
        parser.error("-to_clip can't combine -shape (not a DataFrame/Series) with a DataFrame-producing flag "
                     "like -head/-tail/-cols/-dtype/-nulls/-describe/-value_counts/-unique/-sample/-sort_by/"
                     "-agg_df/-agg/-group_x/-handle_missing/-long/-wide/-crosstab/-clean_columns/-merge/-concat; "
                     "run -shape separately")
    if args.agg_df is not None and args.agg is not None:
        parser.error("-agg_df and -agg can't be combined; choose one")
    if args.group_by is not None and args.agg is None and args.group_x is None:
        parser.error("-group_by requires -agg or -group_x")
    if args.frac is not None and args.sample is None:
        parser.error("-frac requires -sample")

    rename_map = parse_rename(args.rename) if args.rename else None
    select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
    qry_specs = [parse_qry(raw) for raw in (args.qry or [])]
    query_specs = list(args.query or [])
    sql_specs = list(args.sql or [])
    replace_specs = [parse_replace_arg(raw) for raw in (args.replace or [])]
    merge_specs = [parse_merge_arg(raw) for raw in (args.merge or [])]
    concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]

    if args.file is not None:
        frames: dict[str, pd.DataFrame] = {}
        for entry in parse_file_arg(args.file):
            entry_path = Path(entry["path"])
            if not entry_path.exists():
                parser.error(f"-file: file not found: {entry_path}")
            try:
                reader = get_reader(entry_path, sep=entry["dlim"], encoding=entry["encoding"])
            except ValueError as exc:
                parser.error(f"-file: {exc}")
            try:
                frames[entry["alias"]] = reader.to_dataframe(nrows=args.nrows, progress=args.progress)
            except UnicodeError as exc:
                parser.error(_encoding_error_message(entry_path, entry["encoding"], exc))
        failed = _process_path(None, args, parser, False, show_all=show_all, select_specs=select_specs,
                                qry_specs=qry_specs, query_specs=query_specs, sql_specs=sql_specs,
                                replace_specs=replace_specs, rename_map=rename_map, frames=frames,
                                merge_specs=merge_specs, concat_specs=concat_specs)
        return 1 if failed else 0

    paths = expand_paths(args.path)
    if len(paths) > 1 and args.output is not None:
        parser.error("-o/--output cannot be used with multiple matched files; each output path is derived automatically")

    batch = len(paths) > 1
    exit_code = 0

    for path in paths:
        if batch:
            print(f"== {path} ==")
        try:
            failed = _process_path(path, args, parser, batch, show_all=show_all, select_specs=select_specs,
                                    qry_specs=qry_specs, query_specs=query_specs, sql_specs=sql_specs,
                                    replace_specs=replace_specs, rename_map=rename_map)
        except UnicodeError as exc:
            failed = _fail(parser, batch, _encoding_error_message(path, args.encoding, exc))
        if failed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())