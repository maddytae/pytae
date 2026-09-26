"""Command line tool for inspecting tabular files (parquet/csv/txt/sas7bdat) and converting between formats."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import pandas as pd

from pytae.cli_parsing import (
    expand_paths,
    parse_bool_text,
    parse_concat_arg,
    parse_drop_spec,
    parse_file_arg,
    parse_fraction,
    parse_list_order,
    parse_merge_arg,
    parse_positive_int,
    parse_qry,
    parse_rename,
    parse_replace_values_arg,
    parse_select_spec,
)
from pytae.cli_pipeline import (
    _OrderedAppend,
    _OrderedFlag,
    _OrderedStore,
    _OrderedValue,
)
from pytae.cli_run import (
    NON_DF_TERMINAL_OPS,
    _encoding_error_message,
    _fail,
    _process_path,
)
from pytae.readers import get_reader

try:
    __version__ = _pkg_version("pytae")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytae",
        description="Inspect and convert parquet/csv/txt/dat/sas7bdat files (glob patterns convert multiple files at once), or read a Databricks table / remote SSH file via a .yaml connection config.",
        allow_abbrev=False,
    )
    parser.add_argument("path", nargs="*", default=None,
                         help="path to a .parquet, .csv, .txt, .dat, or .sas7bdat file, "
                              "a .yaml/.yml connection config (Databricks table or remote SSH file), "
                              "or glob patterns/multiple files for batch operations; "
                              "omit when using -file with -merge/-concat/-sql")
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
    parser.add_argument("-sort_by", "--sort_by", dest="sort_by", default=None, metavar="SPEC",
                         action=_OrderedStore,
                         help="sort rows by a comma-separated column list, optionally ending with "
                              "asc or desc (default: asc), e.g. species,body_mass_g desc")
    parser.add_argument("-group_by", "--group_by", dest="group_by", default=None, metavar="COLUMNS",
                         help="explicit group-by columns for -agg (comma-separated); also used by -group_x "
                              "if group= is omitted")
    parser.add_argument("-nrows", "--nrows", "-limit", "--limit", dest="nrows", type=parse_positive_int, default=None, metavar="N",
                         help="cap the number of rows loaded (default: no cap)")
    parser.add_argument("--select", "-select", dest="select", action=_OrderedAppend, default=None, metavar="SPEC",
                         help="restrict columns at this point in the pipeline (union of tokens in one SPEC): "
                              "names, start:end slices, and key=value (dtype, contains, startswith, endswith, "
                              "regex, exclude_dtype); repeat to filter remaining columns, including after "
                              '-agg_df/-long/-wide, e.g. -select "dtype=numeric" -select "contains=bill"')
    parser.add_argument("--drop", "-drop", dest="drop", action=_OrderedAppend, default=None, metavar="COLUMNS",
                         help="drop columns by exact name at this point in the pipeline (comma-separated names "
                              "only; use -select for dtype=/contains=/regex=/slices); remaining columns keep "
                              'their order, e.g. -drop "sex,island"')
    parser.add_argument("-agg_df", "--agg_df", dest="agg_df", nargs="?", const="sum", default=None,
                         metavar="AGGFUNC", action=_OrderedValue,
                         help="aggregate using pytae agg_df; auto-detects group columns (non-numeric); "
                              "defaults to sum when no value given; "
                              "accepts a name (mean), a comma list (mean,sum), or a mapping "
                              "(body_mass_g: mean, n: n)")
    parser.add_argument("-agg", "--agg", dest="agg", metavar="KEY=VALUE,...", action=_OrderedStore,
                         help="aggregate using explicit -group_by columns; key=value specs "
                              "(column=, aggfunc=, optional as=), e.g. "
                              "column=value,aggfunc=sum,as=v; several specs separated by ';'; requires -group_by")
    parser.add_argument("-group_x", "--group_x", dest="group_x", nargs="?", const="", default=None,
                         metavar="KEY=VALUE,...", action=_OrderedValue,
                         help="broadcast a group aggregate back to every row (pytae group_x()); default is group "
                              "size n on non-numeric columns; e.g. group=species,v=body_mass_g,a=max")
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
                              "v=value; e.g. c=metric,v=reading")
    parser.add_argument("-wide", "--wide", dest="wide", nargs="?", const="", default=None,
                         metavar="KEY=VALUE,...", action=_OrderedValue,
                         help="pivot long form to wide (pytae wide()); defaults c=variable, v=value; "
                              "e.g. c=country,v=balance,a=mean; a=n is an alias for pandas' 'size' "
                              "(group row count), matching agg_df's convention; honors -dropna")
    parser.add_argument("-crosstab", "--crosstab", dest="crosstab", metavar="KEY=VALUE,...", action=_OrderedStore,
                         help="cross-tabulate columns into a matrix (pandas crosstab()); key=value specs: "
                              "index= (one or more comma-separated columns), columns= (single column, required), "
                              "optional values=+aggfunc= together to aggregate instead of count, "
                              "normalize=index|columns|all, margins=true|false, margins_name= (default 'All'; "
                              "requires margins=true); honors -dropna")
    parser.add_argument("-dropna", "--dropna", dest="dropna", type=parse_bool_text, default=True,
                         metavar="BOOL",
                         help="for -agg_df, -agg, -group_x, -wide, -value_counts, and -crosstab: "
                              "include NA keys when false; accepts true or false (default: true)")
    parser.add_argument("-o", "--output", dest="output", default=None, metavar="TARGET",
                         help="output destination: a file path (e.g. 'out.csv', 'out.parquet'), "
                              "a format for in-place or batch conversion ('csv', 'parquet', 'txt', 'dat'), "
                              "or 'clip'/'clipboard' to copy to system clipboard")
    parser.add_argument("-dlim", "--dlim", dest="dlim", default=None, metavar="CHAR",
                         help="field delimiter for reading/writing .csv/.txt/.dat (default: ',' for .csv, "
                              "tab for .txt, '|' for .dat); not used for .parquet or .sas7bdat")
    parser.add_argument("-encoding", "--encoding", dest="encoding", default=None, metavar="ENC",
                         help="text encoding for .csv/.txt/.dat/.sas7bdat, e.g. latin-1 "
                              "(default: utf-8 for .sas7bdat, latin-1 for .dat, pandas infer for .csv/.txt); "
                              "not used for .parquet")
    parser.add_argument("-rename", "--rename", dest="rename", action=_OrderedAppend, default=None, metavar="OLD:NEW,...",
                         help="rename columns at this point in the pipeline (or during conversion), e.g. \"old_a:new_a,old_b:new_b\"")
    parser.add_argument("-file", "--file", dest="file", default=None, metavar="PATH=ALIAS;...",
                         help="load multiple named files for -merge/-concat/-sql, instead of the positional path; "
                              "';'-separated entries, each PATH=ALIAS optionally followed by "
                              ",dlim=/,encoding= overrides for that file, e.g. "
                              "\"data1.parquet=df1; data2.parquet=df2,encoding='latin-1'\"; "
                              "requires -merge, -concat, or -sql as the first operation, and can't be "
                              "combined with the positional path")
    parser.add_argument("-query", "--query", dest="query", action=_OrderedAppend, default=None, metavar="EXPR",
                         help="filter rows at this point in the pipeline using pandas query(), e.g. \"col > 5\"")
    parser.add_argument("-qry", "--qry", dest="qry", action=_OrderedAppend, default=None, metavar="CONDITIONS",
                         help="filter rows at this point in the pipeline using pytae qry(); conditions like "
                              "\"col = 'val', col > 5\"")
    parser.add_argument("-mutate", "--mutate", dest="mutate", action=_OrderedAppend, default=None, metavar="SPEC",
                         help="create/overwrite columns at this point in the pipeline using pytae mutate(); "
                              "\"new_col = expression\" entries, comma-separated, quoting the key optional; "
                              "the expression is pandas eval() syntax and column names in it must stay unquoted, e.g. "
                              "\"bmi = body_mass_g / bill_length_mm ** 2\"")
    parser.add_argument("-sql", "--sql", dest="sql", action=_OrderedAppend, default=None, metavar="QUERY",
                         help="run a SQL query (via duckdb) against the current view at this point in "
                              "the pipeline; the view is queryable as table `data`; standard SQL identifier "
                              "quoting applies (double quotes for names with spaces, e.g. \"col a\"; single "
                              "quotes are string literals, not identifiers), e.g. "
                              "\"select \\\"col a\\\" from data where \\\"col a\\\" > 10\"; "
                              "in -file/-merge mode, may be used instead of -merge as the first op, with "
                              "every -file alias queryable by its own name (e.g. \"select * from df1 "
                              "inner join df2 on df1.\\\"col a\\\" = df2.cola\") — `data` becomes queryable "
                              "too once something later in the pipeline has produced a current view")
    parser.add_argument("-replace_values", "--replace_values", dest="replace_values", action=_OrderedAppend, default=None, metavar="SPEC",
                         help="replace values at this point in the pipeline; key=value tokens: v= (required) "
                              "an old:new mapping, e.g. \"v='old:new,alpha:bravo'\"; c= (optional) restrict "
                              "to specific columns, e.g. \"c='col a,col b',v='old:new'\"; exact= (optional bool, "
                              "default true) — true matches whole cell values, false matches a substring "
                              "anywhere in the cell, e.g. \"v='old:new',exact=false\"")
    parser.add_argument("-merge", "--merge", dest="merge", action=_OrderedAppend, default=None, metavar="KEY=VALUE,...",
                         help="merge two frames into the pipeline (pandas merge()); repeatable, to fold in "
                              "one more file at a time; must be the first op when using -file (unless -sql/"
                              "-concat starts it instead); key=value tokens: left=/right= (required — -file "
                              "aliases, or 'data' for the pipeline's current result so far), "
                              "on= (required; shared column name(s), or 'left:right' pairs if they "
                              "differ between sides — quote on= if it has more than one column/pair, e.g. "
                              "\"on='col a:cola,colb:colb'\"), how= (optional, default 'inner': "
                              "inner/left/right/outer/cross), validate= (optional, e.g. one_to_one)")
    parser.add_argument("-concat", "--concat", dest="concat", action=_OrderedAppend, default=None, metavar="KEY=VALUE,...",
                         help="stack frames row-wise into the pipeline (pandas concat(), always with "
                              "ignore_index=True); repeatable; must be the first op when using -file "
                              "(unless -sql/-merge starts it instead); key=value tokens: frames= (required) "
                              "an ordered comma-separated list of -file aliases (or 'data' for the pipeline's "
                              "current result so far), quoted since it has internal commas, e.g. "
                              "\"frames='df1,df2,df3'\"")
    parser.add_argument("-progress", "--progress", action="store_true",
                         help="show row-count progress while converting large files")
    parser.add_argument("-pretty", "--pretty", action="store_true",
                         help="render tables as a bordered markdown table instead of plain pandas text")
    parser.add_argument("-round", "--round", dest="round_ndigits", type=int, default=None, metavar="N",
                         help="round numeric columns to N decimal places before printing/copying; "
                              "non-numeric columns are left unchanged")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args(argv)
    if extras:
        if any(e in ("-to_clip", "--to_clip") for e in extras):
            parser.error("'-to_clip' has been removed; use '-o clip' or '-o clipboard' instead")
        if any(e in ("-convert", "--convert") for e in extras):
            parser.error("'-convert' has been removed; use '-o <filename>' or '-o <format>' instead")
        msg = f"unrecognized arguments: {' '.join(extras)}"
        if extras and all(not e.startswith("-") for e in extras):
            # likely an unquoted value with a space (e.g. a column name) split by the
            # shell into separate argv tokens -- the whole spec needs one pair of quotes
            msg += (
                "\nIf this is part of a value with a space (e.g. a column name), wrap the "
                'whole spec in quotes, e.g. -select "col a,col b" -- see docs/CLI.md#quoting.'
            )
        parser.error(msg)

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    for idx, op in enumerate(op_order):
        if op in NON_DF_TERMINAL_OPS and idx != last_idx:
            parser.error(
                f"-{op} does not return a DataFrame/Series, so no flag may follow it "
                f"(matches pandas: you can't chain another call off "
                f"df.shape/df.columns/df.dtypes/df.info())"
            )

    out_target = str(args.output).strip() if args.output is not None else None
    args.output = out_target
    is_clip = out_target is not None and out_target.lower() in ("clip", "clipboard")
    is_file = out_target is not None and not is_clip

    if is_file and any(op in NON_DF_TERMINAL_OPS for op in op_order):
        bad_op = next(op for op in op_order if op in NON_DF_TERMINAL_OPS)
        parser.error(
            f"-{bad_op} does not produce a tabular DataFrame, so it cannot be exported to a file; "
            f"use '-o clip' or view in terminal"
        )

    raw_paths = args.path if isinstance(args.path, list) else ([args.path] if args.path else [])

    if args.merge and args.file is None:
        parser.error("-merge requires -file")
    if args.concat and args.file is None:
        parser.error("-concat requires -file")
    if args.file is not None:
        if raw_paths:
            parser.error("-file/-merge can't be combined with a positional path; list every input via -file instead")
        if not op_order or op_order[0] not in ("merge", "sql", "concat"):
            parser.error("-file requires -merge, -concat, or -sql as its first operation")
        if is_file and out_target is not None and out_target.lower() in ("csv", "parquet", "pq", "txt", "dat"):
            parser.error(f"-o {out_target}: in -file/-merge mode, an explicit output file path is required")
    elif not raw_paths:
        parser.error("the following arguments are required: path")

    show_all = not any([args.shape, args.cols, args.dtype, args.nulls, args.describe, args.info,
                         args.value_counts, args.unique, args.head is not None,
                         args.tail is not None, args.sample is not None, args.sort_by is not None,
                         args.agg_df is not None, args.agg is not None,
                         args.group_x is not None, args.handle_missing is not None,
                         args.long is not None, args.wide is not None, args.crosstab is not None,
                         args.select, args.drop, args.qry, args.query, args.sql, args.replace_values,
                         args.rename, args.clean_columns is not None, args.merge, args.concat])

    wants_df = any([args.cols, args.dtype, args.nulls, args.describe, show_all,
                     args.value_counts, args.unique, args.head is not None,
                     args.tail is not None, args.sample is not None, args.sort_by is not None,
                     args.agg_df is not None, args.agg is not None,
                     args.group_x is not None, args.handle_missing is not None,
                     args.long is not None, args.wide is not None, args.crosstab is not None,
                     args.clean_columns is not None, args.merge, args.concat])
    if is_clip and args.shape and wants_df:
        parser.error("-o clip can't combine -shape (not a DataFrame/Series) with a DataFrame-producing flag "
                     "like -head/-tail/-cols/-dtype/-nulls/-describe/-value_counts/-unique/-sample/-sort_by/"
                     "-agg_df/-agg/-group_x/-handle_missing/-long/-wide/-crosstab/-clean_columns/-merge/-concat; "
                     "run -shape separately")
    if args.agg_df is not None and args.agg is not None:
        parser.error("-agg_df and -agg can't be combined; choose one")
    if args.group_by is not None and args.agg is None and args.group_x is None:
        parser.error("-group_by requires -agg or -group_x")
    if args.frac is not None and args.sample is None:
        parser.error("-frac requires -sample")

    rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
    select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
    drop_specs = [parse_drop_spec(raw) for raw in (args.drop or [])]
    qry_specs = [parse_qry(raw) for raw in (args.qry or [])]
    mutate_specs = list(args.mutate or [])
    query_specs = list(args.query or [])
    sql_specs = list(args.sql or [])
    replace_specs = [parse_replace_values_arg(raw) for raw in (args.replace_values or [])]
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
                                drop_specs=drop_specs,
                                qry_specs=qry_specs, mutate_specs=mutate_specs, query_specs=query_specs, sql_specs=sql_specs,
                                replace_specs=replace_specs, rename_specs=rename_specs, frames=frames,
                                merge_specs=merge_specs, concat_specs=concat_specs)
        return 1 if failed else 0

    if not raw_paths:
        parser.error("the following arguments are required: path")
    paths = expand_paths(raw_paths)
    batch = len(paths) > 1

    if batch and args.output is not None:
        if is_clip:
            parser.error("-o clip cannot be used with multiple matched files")
        if out_target is not None and out_target.lower() not in ("csv", "parquet", "pq", "txt", "dat"):
            parser.error(
                "-o/--output with multiple matched files requires a format (e.g. '-o csv' or '-o parquet'), "
                "not a single file path"
            )

    exit_code = 0

    for path in paths:
        if batch:
            print(f"== {path} ==")
        try:
            failed = _process_path(path, args, parser, batch, show_all=show_all, select_specs=select_specs,
                                    drop_specs=drop_specs,
                                    qry_specs=qry_specs, mutate_specs=mutate_specs, query_specs=query_specs, sql_specs=sql_specs,
                                    replace_specs=replace_specs, rename_specs=rename_specs)
        except UnicodeError as exc:
            failed = _fail(parser, batch, _encoding_error_message(path, args.encoding, exc))
        if failed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())