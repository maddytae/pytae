"""Keyword-level help documentation and example lookup for pytae CLI."""

from __future__ import annotations

import difflib
from typing import NamedTuple


class KeywordHelp(NamedTuple):
    name: str
    flag: str
    syntax: str
    summary: str
    description: str
    options: list[str]
    examples: list[str]
    see_also: list[str]


KEYWORD_DOCS: dict[str, KeywordHelp] = {
    "sql": KeywordHelp(
        name="sql",
        flag="-sql, --sql QUERY",
        syntax='pytae <path> -sql "<QUERY>" [other flags...]',
        summary="Run full analytical SQL queries via Polars SQLContext directly against data.",
        description=(
            "Executes zero-copy, vectorized SQL queries via embedded Polars SQLContext.\n"
            "- In single-file pipelines, the current dataset view is queryable as table `data`.\n"
            "- In multi-file mode (-file), each file alias (e.g. df1, df2) is queryable directly by name.\n"
            '- Standard SQL identifier quoting applies: double quotes for names with spaces ("col a"),\n'
            "  and single quotes for string literals ('Gentoo').\n"
            "- To run queries from a file, prefix the filename with '@' (e.g. -sql @query.sql)."
        ),
        options=[
            "`data` : Default in-memory table representing the current pipeline view.",
            "@file.sql : Load SQL query string directly from an external SQL file.",
            "Polars SQL functions : Full support for CTEs, WINDOW functions, aggregate functions, and math.",
        ],
        examples=[
            'pytae penguins.parquet -sql "select species, island, body_mass_g from data where body_mass_g > 5000" -head 5',
            'pytae penguins.parquet -sql "select species, count(*) as n, round(avg(body_mass_g), 1) as avg_mass from data group by species"',
            'pytae penguins.parquet -sql "select [bill length mm], body_mass_g from data" -head 3',
            'pytae -file "sales.parquet=s; stores.parquet=st" -sql "select s.*, st.city from s join st using (store_id)"',
            "pytae sales.parquet -sql @queries/quarterly_report.sql -o report.csv",
        ],
        see_also=["-filter", "-agg", "-pivot", "-file"],
    ),
    "filter": KeywordHelp(
        name="filter",
        flag="-filter, --filter CONDITIONS",
        syntax='pytae <path> -filter "<CONDITIONS>"',
        summary="Filter DataFrame rows using expressions, interval bounds, and string checks.",
        description=(
            "Filters rows at this point in the pipeline using pytae filter().\n"
            "Supports equality ('==', '='), inequality ('>', '<=', '!='), interval notation [a, b],\n"
            "string matching (startswith, contains, regex), and column names with spaces."
        ),
        options=[
            "col = 'val' : Exact match (single quotes for string literals).",
            "col > 100 : Numeric comparison.",
            "col in ['A', 'B'] : Set membership.",
            "col = [3000, 5000] : Interval range (inclusive closed interval 3000 <= col <= 5000).",
            "col = '(3000, 5000)' : Open interval (3000 < col < 5000).",
            "[col with spaces] > 50 : Bracket notation for column names containing spaces.",
        ],
        examples=[
            "pytae penguins.parquet -filter \"species == 'Gentoo', body_mass_g > 5000\"",
            'pytae penguins.parquet -filter "body_mass_g = [4000, 5000]" -shape',
            "pytae penguins.parquet -filter \"island in ['Biscoe', 'Dream']\"",
            "pytae data.csv -filter \"[customer name] = 'Acme Corp'\"",
        ],
        see_also=["-sql", "-select", "-dropna"],
    ),
    "select": KeywordHelp(
        name="select",
        flag="-select, --select SPEC",
        syntax='pytae <path> -select "<SPEC>"',
        summary="Select, reorder, slice, or exclude columns.",
        description=(
            "Restricts and reorders columns at this point in the pipeline.\n"
            "Supports explicit column lists, contiguous slice ranges (start:end), negative drops (-col, ~col),\n"
            "and criteria matchers (contains=, startswith=, endswith=, regex=, dtype=, exclude=)."
        ),
        options=[
            "col1,col2 : Keep specific columns in the exact order requested.",
            "start:end : Contiguous slice range (inclusive of both bounds).",
            "-col, ~col : Exclude specified columns from the output.",
            "-start:end : Drop a contiguous range of columns.",
            "contains=substr : Match columns containing substring.",
            "startswith=prefix : Match columns starting with prefix.",
            "endswith=suffix : Match columns ending with suffix.",
            "regex=pattern : Match columns using regular expressions.",
            "dtype=numeric|datetime|category|bool : Filter columns by datatype.",
            "exclude_dtype=numeric : Exclude columns matching a datatype.",
        ],
        examples=[
            'pytae penguins.parquet -select "species,island,body_mass_g"',
            'pytae penguins.parquet -select "bill_length_mm:body_mass_g"',
            'pytae penguins.parquet -select "-sex, -year"',
            'pytae penguins.parquet -select "contains=bill, species"',
            'pytae penguins.parquet -select "dtype=numeric"',
        ],
        see_also=["-cols", "-filter", "-clean_columns"],
    ),
    "mutate": KeywordHelp(
        name="mutate",
        flag="-mutate, --mutate SPEC",
        syntax='pytae <path> -mutate "<col1 = expr1, (colA, colB) = _ * 2>"',
        summary="Create, modify, or engineer columns using vectorized expressions, multi-column transforms, or grouped window transforms.",
        description=(
            "Evaluates column assignments sequentially from left to right.\n"
            "Expressions support standard arithmetic, boolean logic, pandas Series methods,\n"
            "multi-column transforms via '(col1, col2) = expr' or '(startswith=prefix) = expr' using '_' as the column placeholder,\n"
            'and vectorized window aggregations when combined with -by (e.g. -by species -mutate "avg = mean(mass)").'
        ),
        options=[
            "new_col = expr : Define or overwrite a column calculated from existing columns.",
            "(col1, col2) = expr : Transform multiple columns in-place using '_' as the column placeholder.",
            "(col1, col2)_suffix = expr : Create new columns with a suffix (or prefix_(col1, col2)) without overwriting originals.",
            "(startswith=..., dtype=numeric) = expr : Apply an expression across columns matched by select() predicates.",
            "[col with spaces] : Target or reference column headers that contain spaces.",
            "-by <col> : Evaluate window aggregations (mean, sum, min, max, std, var, n) per group without collapsing rows.",
        ],
        examples=[
            'pytae penguins.parquet -mutate "mass_kg = body_mass_g / 1000" -head 3',
            'pytae penguins.parquet -mutate "(bill_length_mm, bill_depth_mm) = _ / 10"',
            'pytae penguins.parquet -mutate "(startswith=bill_)_cm = _ / 10"',
            'pytae penguins.parquet -by species -mutate "(dtype=numeric) = (_ - mean(_)) / std(_)"',
            'pytae penguins.parquet -by species -mutate "avg_mass = mean(body_mass_g), diff = body_mass_g - avg_mass"',
            "pytae penguins.parquet -mutate \"source = '2024_survey'\"",
        ],
        see_also=["-agg", "-by", "-select"],
    ),
    "arrange": KeywordHelp(
        name="arrange",
        flag="-arrange, --arrange SPEC",
        syntax='pytae <path> -arrange "<col1 [desc], -col2, ...>"',
        summary="Sort rows by one or more columns with inline ascending or descending directions.",
        description=(
            "Sorts rows by column specifications in order.\n"
            "Ascending is default; descending can be indicated via trailing 'desc', 'descending', or leading '-'."
        ),
        options=[
            "col : Ascending order.",
            "col desc : Descending order.",
            "-col : Descending order shorthand.",
            "[col with space] desc : Sort by spaced column header.",
        ],
        examples=[
            'pytae penguins.parquet -arrange "body_mass_g desc" -head 5',
            'pytae penguins.parquet -arrange "species, -body_mass_g"',
            'pytae penguins.parquet -arrange "island, bill_length_mm asc"',
        ],
        see_also=["-head", "-tail", "-by"],
    ),
    "pick": KeywordHelp(
        name="pick",
        flag="-pick (Removed)",
        syntax="Use -arrange ... -head N (or -by ... -arrange ... -head N) instead.",
        summary="Removed: use -arrange ... -head N (or -by ... -arrange ... -head N) instead.",
        description=(
            "The -pick verb has been removed in favor of composable sort and slice verbs:\n"
            "  - Whole table top N: -arrange '<col> desc' -head N\n"
            "  - Grouped top N:     -by <group> -arrange '<col> desc' -head N\n"
            "  - Percentage/ties:   -head 10% or -head '3, ties=true'"
        ),
        options=[],
        examples=[
            'pytae penguins.parquet -arrange "body_mass_g desc" -head 5',
            'pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 2',
        ],
        see_also=["-arrange", "-head", "-tail", "-by"],
    ),
    "agg": KeywordHelp(
        name="agg",
        flag="-agg, --agg [AGGFUNC]",
        syntax="pytae <path> [-by <cols>] -agg [AGGFUNC]",
        summary="Aggregate numeric columns grouped by -by (or whole-table summary without -by).",
        description=(
            "Computes summary statistics on numeric columns.\n"
            "If -by is omitted, produces a whole-table grand total summary.\n"
            "Accepts a function name ('mean'), a list ('mean,sum,n'), or mapped expressions ('avg=mean,total=sum').\n"
            "By default, missing values (NaN) in group columns form their own group (dropna=False) to prevent silent data loss.\n"
            "To exclude rows with missing group keys, chain -dropna before -agg (e.g. -dropna species -by species -agg mean)."
        ),
        options=[
            "-by <cols> : Grouping column(s) (comma-separated).",
            "mean, sum, median, min, max, std, var : Built-in aggregation functions.",
            "n : Group row count (pure integer).",
            "col = func : Column-specific mapping (e.g. 'total=sum,avg=mean').",
            "dropna = bool : In-spec dropna setting (default: false preserves NA groups).",
        ],
        examples=[
            "pytae penguins.parquet -by species -agg mean",
            'pytae penguins.parquet -by "species,island" -agg "mean,sum,n"',
            'pytae penguins.parquet -agg "mean,n"   # Whole-table summary (grand total)',
            'pytae penguins.parquet -by species -agg "total_mass = body_mass_g:sum, n = n"',
            'pytae penguins.parquet -by sex -agg "body_mass_g = mean, dropna = false"',
        ],
        see_also=["-by", "-pivot", "-mutate", "-dropna"],
    ),
    "pivot": KeywordHelp(
        name="pivot",
        flag="-pivot, --pivot [KEY=VALUE,...]",
        syntax='pytae <path> -pivot "r=rows,c=cols,v=values,a=func,f_v=val"',
        summary="Create 2D Excel-style contingency tables and pivot matrices.",
        description=(
            "Full multi-dimensional pivot table engine across 1D, 2D, and table rollups.\n"
            "Metric column 'v' is optional; omitting 'v' automatically defaults to row counts ('n').\n"
            "Supports rich metric mappings in v (e.g. col:func, new_col=col:func, count=n, col:[f1, f2]).\n"
            "Flattens multi-level column hierarchies to clean 1D strings and resets index to RangeIndex.\n"
            "Missing combinations default to f_v (or 0 for row counts)."
        ),
        options=[
            "r=row_cols : Row grouping dimension(s).",
            "c=col_cols : Column dimension(s) to spread as headers (optional for 1D aggregations).",
            "v=spec : Metric specification (optional; defaults to row count 'n' when omitted).",
            "a=func : Default aggregation function (default: sum; 'n' for counts).",
            "f_v=val : Replacement for empty grid cells (default 0 for counts, NaN for metric averages).",
            "dropna=true|false : Whether to drop NA categories (default: false).",
        ],
        examples=[
            'pytae penguins.parquet -pivot "r=island,c=species"   # 2D cross-tabulation count matrix',
            'pytae penguins.parquet -pivot "r=island,sex"   # 1D frequency table',
            'pytae penguins.parquet -pivot "r=island,c=species,v=body_mass_g,a=mean"',
            "pytae penguins.parquet -pivot \"r=island,v='avg_mass=body_mass_g:mean, count=n'\"   # 1D summary",
            "pytae penguins.parquet -pivot \"r=island,c=species,v='rev=body_mass_g:sum, orders=n'\"",
            "pytae penguins.parquet -pivot \"r='species,island',c=sex,v=body_mass_g,a=median,f_v=0\"",
        ],
        see_also=["-agg", "-long", "-wide"],
    ),
    "long": KeywordHelp(
        name="long",
        flag="-long, --long [KEY=VALUE,...]",
        syntax="pytae <path> -long [c=var,v=val,cols=cols,id_vars=id_cols]",
        summary="Melt wide tables to tall format (pure 1-to-1 unpivoting without aggregation).",
        description=(
            "Melts columns into variable/value rows.\n"
            "If cols is omitted, automatically melts all numeric columns, keeping non-numeric as ID variables."
        ),
        options=[
            "c=name : Header column name for melted variables (default: 'variable').",
            "v=name : Value column name for measurements (default: 'value').",
            "cols=col1,col2 : Explicit columns to melt into rows.",
            "id_vars=id1,id2 : Identifier columns to preserve as rows.",
        ],
        examples=[
            "pytae penguins.parquet -long",
            'pytae penguins.parquet -long "c=measurement,v=value"',
            "pytae data.csv -long \"cols='q1,q2,q3,q4',c=quarter,v=revenue\"",
        ],
        see_also=["-wide", "-pivot"],
    ),
    "wide": KeywordHelp(
        name="wide",
        flag="-wide, --wide [KEY=VALUE,...]",
        syntax="pytae <path> -wide [c=var,v=val,r=id_cols]",
        summary="Spread tall rows into wide headers (pure 1-to-1 reshaping, reverse of -long).",
        description=(
            "Spreads unique key/value pairs back into columns without aggregating.\n"
            "Requires unique (r, c) pairs; if duplicates exist, use -pivot instead."
        ),
        options=[
            "c=name : Column whose distinct values become column headers (default: 'variable').",
            "v=name : Column containing cell values (default: 'value').",
            "r=cols : Explicit row identifier column(s) (default: all remaining columns).",
        ],
        examples=[
            "pytae tall.csv -wide",
            'pytae tall.csv -wide "c=metric,v=measurement"',
            'pytae tall.csv -wide "c=quarter,v=revenue,r=customer_id"',
        ],
        see_also=["-long", "-pivot"],
    ),
    "by": KeywordHelp(
        name="by",
        flag="-by, --by COLUMNS",
        syntax="pytae <path> -by <COLUMNS> [operation]",
        summary="Set grouping columns for subsequent group-aware operations (-agg, -mutate, -head, -tail).",
        description=(
            "Partitions the dataset by one or more columns for subsequent operations.\n"
            "Works with -agg, window -mutate, and group-aware -head / -tail slicing."
        ),
        options=[
            "col : Single grouping column.",
            "col1,col2 : Multiple grouping columns (comma-separated).",
            "[col a], [col b] : Bracketed grouping columns with spaces.",
        ],
        examples=[
            "pytae penguins.parquet -by species -agg mean",
            'pytae penguins.parquet -by "species,island" -agg "mean,n"',
            'pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 2',
            'pytae penguins.parquet -by species -mutate "avg = mean(body_mass_g)"',
        ],
        see_also=["-agg", "-mutate", "-head", "-tail"],
    ),
    "clean_columns": KeywordHelp(
        name="clean_columns",
        flag="-clean_columns, --clean_columns SPEC",
        syntax='pytae <path> -clean_columns "<KEY=VALUE,...>"',
        summary="Systematically sanitize, normalize, and rename messy column headers.",
        description=(
            "Sanitizes headers in deterministic order:\nstrip -> strip_special -> squeeze -> fill -> case -> dedupe."
        ),
        options=[
            "strip : Trim leading/trailing whitespace (bare boolean flag).",
            "strip_special : Remove punctuation and symbols other than alphanumeric, underscore, or fill.",
            "squeeze : Collapse consecutive whitespace runs into single spaces.",
            "fill[=CHAR] : Replace spaces with character (bare 'fill' defaults to '_').",
            "case=lower|upper|proper : Transform letter casing.",
            "dedupe : Disambiguate duplicate column names with '_1', '_2' suffixes.",
        ],
        examples=[
            'pytae dirty.csv -clean_columns "strip,fill,case=lower,dedupe"',
            "pytae dirty.csv -clean_columns \"fill='_',case=lower\"",
            'pytae dirty.csv -clean_columns "case=upper"',
        ],
        see_also=["-rename", "-select", "-cols"],
    ),
    "rename": KeywordHelp(
        name="rename",
        flag="-rename, --rename SPEC",
        syntax='pytae <path> -rename "old1:new1,old2:new2"',
        summary="Rename one or more columns.",
        description=(
            "Renames columns at this point in the pipeline.\n"
            "Accepts comma-separated 'old:new' pairs. Validates that original columns exist."
        ),
        options=[
            "'old:new, ...' : One or more old_name:new_name mapping pairs.",
        ],
        examples=[
            'pytae penguins.parquet -rename "species:bird_species"',
            'pytae penguins.parquet -rename "bill_length_mm:culmen_length, bill_depth_mm:culmen_depth"',
        ],
        see_also=["-select", "-clean_columns"],
    ),
    "file": KeywordHelp(
        name="file",
        flag="-file, --file PATH=ALIAS;...",
        syntax='pytae -file "path1=alias1; path2=alias2" [operation]',
        summary="Load multiple tabular datasets for multi-file joins (-join, -concat, or -sql).",
        description=(
            "Replaces the positional path to enable multi-dataset pipelines.\n"
            "Each file is assigned an alias and can be joined via -join, stacked via -concat, or queried via -sql."
        ),
        options=[
            "path=alias : Assign an in-memory alias to a file.",
            "; (semicolon) : Delimiter between file entries.",
            ",dlim=CHAR : Override field delimiter per file.",
            ",encoding=ENC : Override text encoding per file.",
        ],
        examples=[
            'pytae -file "orders.parquet=o; cust.csv=c" -join "left=o,right=c,on=cust_id" -head 5',
            'pytae -file "2023.parquet=df1; 2024.parquet=df2" -concat "frames=\'df1,df2\'" -o combined.parquet',
            'pytae -file "orders.parquet=o; items.parquet=i" -sql "select o.*, i.name from o join i using (item_id)"',
        ],
        see_also=["-join", "-concat", "-sql"],
    ),
    "join": KeywordHelp(
        name="join",
        flag="-join, --join KEY=VALUE,...",
        syntax='pytae -file "..." -join "left=alias1,right=alias2,on=key[,how=inner]"',
        summary="Join two datasets in the pipeline using Polars SIMD multithreading.",
        description=("Combines two datasets by key columns. Repeatable to join additional files sequentially."),
        options=[
            "left=alias : Left dataset alias (or 'data' for current pipeline state).",
            "right=alias : Right dataset alias.",
            "on=col : Shared join key column (or 'on=\"col1,col2\"').",
            "left_on=col, right_on=col : Join keys with differing names (or 'on=\"left_col:right_col\"').",
            "how=inner|left|right|full|semi|anti|cross : Join method (default: 'inner').",
            "validate=1:1|1:m|m:1|m:m : Join cardinality assertion.",
        ],
        examples=[
            'pytae -file "orders.parquet=o; users.csv=u" -join "left=o,right=u,on=user_id"',
            'pytae -file "a.csv=a; b.csv=b" -join "left=a,right=b,on=\'id:user_id\',how=left"',
        ],
        see_also=["-file", "-concat", "-sql"],
    ),
    "concat": KeywordHelp(
        name="concat",
        flag="-concat, --concat KEY=VALUE,...",
        syntax='pytae -file "..." -concat "frames=\'alias1,alias2,...\'"',
        summary="Stack multiple datasets vertically row-wise into one pipeline DataFrame.",
        description=("Concatenates two or more datasets along rows using Polars."),
        options=[
            "frames='alias1,alias2,...' : Comma-separated list of dataset aliases to stack.",
        ],
        examples=[
            'pytae -file "jan.csv=m1; feb.csv=m2; mar.csv=m3" -concat "frames=\'m1,m2,m3\'" -o q1.parquet',
        ],
        see_also=["-file", "-join"],
    ),
    "output": KeywordHelp(
        name="output",
        flag="-o, --output TARGET",
        syntax="pytae <path> [operations] -o <TARGET> [-out_dir <DIR>]",
        summary="Export result to a file, batch format conversion, or clipboard.",
        description=(
            "Routes pipeline output to disk or system clipboard instead of stdout.\n"
            "Supports .parquet, .csv, .txt, .dat, .jsonl, .csv.gz, .jsonl.gz, and 'clip'."
        ),
        options=[
            "<filename> : Export single file to target path (e.g. out.parquet, out.csv).",
            "<format> : In-place or batch format conversion (e.g. -o parquet, -o csv).",
            "clip / clipboard : Copy tabular result directly to system clipboard as TSV.",
            "-out_dir <dir> : Destination folder for exported files.",
        ],
        examples=[
            "pytae penguins.parquet -filter \"species == 'Gentoo'\" -o gentoo.csv",
            "pytae *.csv -o parquet -out_dir converted/   # Batch convert all CSVs to Parquet",
            "pytae penguins.parquet -head 10 -o clip      # Copy 10 rows to clipboard",
        ],
        see_also=["-fmt", "-dlim", "-encoding", "-progress"],
    ),
    "freq": KeywordHelp(
        name="freq",
        flag="-freq, --freq COLUMN",
        syntax="pytae <path> -freq <COLUMN>",
        summary="Render in-terminal horizontal frequency bars with counts and percentages.",
        description=("Displays a text-based distribution chart for categorical columns directly in your terminal."),
        options=[
            "COLUMN : Categorical column name to profile.",
        ],
        examples=[
            "pytae penguins.parquet -freq species",
            "pytae penguins.parquet -freq island",
        ],
        see_also=["-hist", "-describe"],
    ),
    "hist": KeywordHelp(
        name="hist",
        flag="-hist, --hist COLUMN[:BINS]",
        syntax="pytae <path> -hist <COLUMN[:BINS]>",
        summary="Render in-terminal distribution histogram for numeric columns.",
        description=("Displays ASCII bar distribution and bin counts for numeric columns."),
        options=[
            "COLUMN : Numeric column to bin.",
            "COLUMN:BINS : Optional bin count (default: 10, e.g. body_mass_g:15).",
        ],
        examples=[
            "pytae penguins.parquet -hist body_mass_g",
            'pytae penguins.parquet -hist "body_mass_g:15"',
            "pytae penguins.parquet -hist bill_length_mm:5",
        ],
        see_also=["-freq", "-describe"],
    ),
    "meta": KeywordHelp(
        name="meta",
        flag="-meta, --meta",
        syntax="pytae <file.parquet> -meta",
        summary="Display Parquet metadata (row groups, column statistics, compression, schema) without loading data.",
        description=(
            "Zero-cost inspection: reads only the file footer to output Parquet schema,\n"
            "row counts, row group boundaries, compression codec, and min/max column statistics."
        ),
        options=[],
        examples=[
            "pytae sales.parquet -meta",
        ],
        see_also=["-shape", "-cols", "-dtype", "-glimpse"],
    ),
    "diff": KeywordHelp(
        name="diff",
        flag="-diff, --diff PATH [-tol N]",
        syntax="pytae <file1> -diff <file2> [-tol N]",
        summary="Compare schema and values between two tabular datasets.",
        description=(
            "Compares column lists, types, row counts, null counts, and value differences "
            "between two datasets. Use -tol or -tolerance to set an absolute numeric threshold."
        ),
        options=[
            "PATH : Target file path to compare against.",
            "-tol N, -tolerance N : Numeric tolerance threshold for floating-point comparisons (e.g. -tol 0.001).",
        ],
        examples=[
            "pytae current.parquet -diff previous.parquet",
            "pytae current.parquet -diff previous.parquet -tol 0.001",
            "pytae current.parquet -diff previous.parquet -tolerance 1e-4",
        ],
        see_also=["-meta", "-cols", "-dtype"],
    ),
    "tol": KeywordHelp(
        name="tol",
        flag="-tol, -tolerance N",
        syntax="pytae <file1> -diff <file2> -tol <N>",
        summary="Set numeric threshold / tolerance for -diff.",
        description=(
            "Specifies an absolute numeric threshold for cell-by-cell comparisons in -diff. "
            "Numeric cells differing by less than or equal to N are treated as matching."
        ),
        options=[
            "N : Floating-point threshold (e.g. 0.001, 1e-4).",
        ],
        examples=[
            "pytae current.parquet -diff previous.parquet -tol 0.001",
            "pytae current.parquet -diff previous.parquet -tolerance 1e-5",
        ],
        see_also=["-diff"],
    ),
    "head": KeywordHelp(
        name="head",
        flag="-head, --head [LIMIT]",
        syntax="pytae <path> [-by <cols>] -head [LIMIT]",
        summary="Print the first N rows or proportion (default: 5), group-aware with -by.",
        description=(
            "Limits the working DataFrame to the first N rows or proportion of rows.\n"
            "When paired with -by, extracts top rows per group. When paired with -arrange, selects top records."
        ),
        options=[
            "N : Number of rows (default: 5, e.g. -head 10).",
            "P% : Proportion of rows (e.g. -head 10% or -head 0.1).",
            "'N, ties=true' : Include all boundary ties from preceding -arrange.",
            "-by <cols> : Extract top rows within each group.",
        ],
        examples=[
            "pytae penguins.parquet -head",
            "pytae penguins.parquet -head 10",
            "pytae penguins.parquet -head 10%",
            'pytae penguins.parquet -arrange "body_mass_g desc" -head 3',
            'pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 2',
            'pytae penguins.parquet -arrange "body_mass_g desc" -head "3, ties=true"',
        ],
        see_also=["-tail", "-arrange", "-by", "-sample"],
    ),
    "tail": KeywordHelp(
        name="tail",
        flag="-tail, --tail [LIMIT]",
        syntax="pytae <path> [-by <cols>] -tail [LIMIT]",
        summary="Print the last N rows or proportion (default: 5), group-aware with -by.",
        description=(
            "Limits the working DataFrame to the last N rows or proportion of rows.\n"
            "When paired with -by, extracts bottom rows per group."
        ),
        options=[
            "N : Number of rows (default: 5, e.g. -tail 10).",
            "P% : Proportion of rows (e.g. -tail 10% or -tail 0.1).",
            "'N, ties=true' : Include all boundary ties from preceding -arrange.",
            "-by <cols> : Extract bottom rows within each group.",
        ],
        examples=[
            "pytae penguins.parquet -tail",
            "pytae penguins.parquet -tail 10",
            "pytae penguins.parquet -tail 10%",
            'pytae penguins.parquet -arrange "body_mass_g desc" -tail 3',
            'pytae penguins.parquet -by species -arrange "body_mass_g desc" -tail 2',
        ],
        see_also=["-head", "-arrange", "-by", "-sample"],
    ),
    "shape": KeywordHelp(
        name="shape",
        flag="-shape, --shape",
        syntax="pytae <path> -shape",
        summary="Print dataset dimensions as (rows, cols).",
        description="Prints (rows, cols) dimensions. For Parquet files, reads metadata instantly without loading rows into RAM.",
        options=[],
        examples=[
            "pytae penguins.parquet -shape",
            "pytae penguins.parquet -filter \"species == 'Gentoo'\" -shape",
        ],
        see_also=["-head", "-cols", "-meta"],
    ),
    "cols": KeywordHelp(
        name="cols",
        flag="-cols, --cols [ORDER]",
        syntax="pytae <path> -cols [asc|desc]",
        summary="Print column header names.",
        description="Prints column headers in file order (default) or sorted alphabetically (asc|desc).",
        options=[
            "asc : Sort alphabetically A-Z.",
            "desc : Sort alphabetically Z-A.",
        ],
        examples=[
            "pytae penguins.parquet -cols",
            "pytae penguins.parquet -cols asc",
        ],
        see_also=["-dtype", "-shape", "-select"],
    ),
    "dtype": KeywordHelp(
        name="dtype",
        flag="-dtype, --dtype [ORDER]",
        syntax="pytae <path> -dtype [asc|desc]",
        summary="Print column datatypes.",
        description="Prints column names and their pandas datatypes.",
        options=["asc|desc : Sort alphabetically by column name."],
        examples=[
            "pytae penguins.parquet -dtype",
            "pytae penguins.parquet -dtype asc",
        ],
        see_also=["-cols", "-glimpse", "-nulls"],
    ),
    "nulls": KeywordHelp(
        name="nulls",
        flag="-nulls, --nulls [ORDER]",
        syntax="pytae <path> -nulls [asc|desc]",
        summary="Print count and percentage of missing (NaN/null) values per column.",
        description="Counts nulls per column to quickly spot missing data.",
        options=["asc|desc : Sort alphabetically by column name."],
        examples=[
            "pytae penguins.parquet -nulls",
            "pytae penguins.parquet -nulls desc",
        ],
        see_also=["-dropna", "-fillna"],
    ),
    "dropna": KeywordHelp(
        name="dropna",
        flag="-dropna, --dropna [COLS]",
        syntax='pytae <path> -dropna ["col1,col2"]',
        summary="Drop rows containing missing (NaN) values.",
        description="Bare -dropna drops rows with any missing value; -dropna 'col1,col2' checks only specified columns.",
        options=[
            "Bare flag : Drop row if ANY column contains NaN.",
            '"col1,col2" : Drop row if specified columns contain NaN.',
        ],
        examples=[
            "pytae penguins.parquet -dropna",
            'pytae penguins.parquet -dropna "sex, body_mass_g"',
        ],
        see_also=["-fillna", "-nulls"],
    ),
    "fillna": KeywordHelp(
        name="fillna",
        flag="-fillna, --fillna SPEC",
        syntax='pytae <path> -fillna "<SPEC>"',
        summary="Fill missing values with a scalar, column mapping, or column subset.",
        description=(
            "Fills null/missing values across the DataFrame or in specific columns.\n"
            "- A scalar value fills all type-appropriate columns (e.g. 0 for numeric, 'missing' for string).\n"
            "- A column mapping 'col1:val1, col2:val2' fills specified columns with specific values.\n"
            "- A value followed by columns 'val, col1, col2' fills specific columns with that scalar."
        ),
        options=[
            "VAL : Scalar value to fill matching columns (e.g. 0, 'missing').",
            "'col1:val1, col2:val2' : Column-specific fill values.",
            "'val, col1, col2' : Fill specific columns with the given scalar value.",
        ],
        examples=[
            "pytae penguins.parquet -fillna 0",
            'pytae penguins.parquet -fillna "missing"',
            'pytae penguins.parquet -fillna "sex:unknown, body_mass_g:0"',
            'pytae penguins.parquet -fillna "0, bill_length_mm, body_mass_g"',
        ],
        see_also=["-dropna", "-nulls"],
    ),
    "distinct": KeywordHelp(
        name="distinct",
        flag="-distinct, --distinct [SPEC]",
        syntax='pytae <path> -distinct ["col1,col2[,keep=first|last|false]"]',
        summary="Drop duplicate rows (across all or specific columns, with keep control).",
        description="Drops duplicate records, with configurable duplicate retention (first, last, or drop all).",
        options=[
            "Bare flag : Deduplicate across all columns (default keep=first).",
            '"col1,col2" : Deduplicate restricted to specified subset of columns.',
            "keep=first : Keep first occurrence of duplicates (default).",
            "keep=last : Keep last occurrence of duplicates.",
            "keep=false / keep=none : Drop all occurrences of duplicates.",
        ],
        examples=[
            'pytae penguins.parquet -select "species,island" -distinct',
            'pytae penguins.parquet -distinct "species,island"',
            'pytae penguins.parquet -distinct "species,island,keep=last"',
            'pytae penguins.parquet -distinct "keep=last"',
        ],
        see_also=["-dropna", "-filter"],
    ),
    "count": KeywordHelp(
        name="count",
        flag="-count, --count [SPEC]",
        syntax='pytae <path> -count ["col1,col2[,sort=true|false][,name=n]"]',
        summary="Count occurrences of unique combinations of columns (or total rows).",
        description=(
            "Counts occurrences of unique combinations of columns, sorted descending by count by default.\n"
            "- Bare flag: counts total rows (or counts by -by columns if placed after -by).\n"
            "- Specified columns: counts occurrences of unique combinations of those columns.\n"
            "- sort=false: preserves original encounter order.\n"
            "- name=<name>: customizes the output count column name (default 'n')."
        ),
        options=[
            "Bare flag : Count total rows (or groups if preceded by -by).",
            '"col1,col2" : Count occurrences of unique combinations of specified columns.',
            "sort=false : Preserve encounter order instead of sorting descending by count.",
            "name=<name> : Custom column name for the count tally (default 'n').",
        ],
        examples=[
            "pytae penguins.parquet -count species",
            'pytae penguins.parquet -count "species,island"',
            'pytae penguins.parquet -count "species,sort=false"',
            'pytae penguins.parquet -count "species,name=total"',
            "pytae penguins.parquet -by species -count",
            "pytae penguins.parquet -count",
        ],
        see_also=["-agg", "-distinct", "-by", "-freq"],
    ),
    "pretty": KeywordHelp(
        name="pretty",
        flag="-pretty, --pretty",
        syntax="pytae <path> [operations] -pretty",
        summary="[Deprecated] Table formatting is automatically detected.",
        description="Deprecated. Table formatting is now automatically detected: boxed UTF-8 tables for interactive terminals and clean unbordered bare tables when piped or redirected.",
        options=[],
        examples=[
            "pytae penguins.parquet -head 5",
        ],
        see_also=["-pager", "-round"],
    ),
    "pager": KeywordHelp(
        name="pager",
        flag="-pager, --pager",
        syntax="pytae <path> [operations] -pager",
        summary="Pipe output through system pager ($PAGER or less).",
        description="Pipes wide or long output through the terminal pager for comfortable scrolling.",
        options=[],
        examples=[
            "pytae large.parquet -describe -pager",
            "pytae penguins.parquet -head 50 -pager",
        ],
        see_also=["-pretty"],
    ),
    "round": KeywordHelp(
        name="round",
        flag="-round, --round N",
        syntax="pytae <path> [operations] -round <N>",
        summary="Round numeric columns to N decimal places before printing.",
        description="Rounds numeric float columns to N decimal places; non-numeric columns remain untouched.",
        options=["N : Number of decimal places."],
        examples=[
            "pytae penguins.parquet -by species -agg mean -round 2",
            "pytae penguins.parquet -describe -round 1",
        ],
        see_also=["-pretty", "-agg"],
    ),
    "time": KeywordHelp(
        name="time",
        flag="-time, --time [N]",
        syntax="pytae <path> [operations] -time [N]",
        summary="Measure and print pipeline execution time over 1 or N runs.",
        description=(
            "Measures wall-clock execution time of the full CLI pipeline.\n"
            "- Bare '-time' (or '-time 1') runs the pipeline once and prints the elapsed time.\n"
            "- '-time N' (e.g. '-time 10') executes the full pipeline N times (printing normal output\n"
            "  on the first run) and reports average, minimum, maximum, and total execution time."
        ),
        options=[
            "Bare flag : Run once and report elapsed time.",
            "N : Positive integer number of benchmark runs (reports avg, min, max, and total).",
        ],
        examples=[
            "pytae penguins.parquet -shape -time",
            "pytae penguins.parquet -by species -agg mean -time 10",
        ],
        see_also=["-progress"],
    ),
}

# Aliases mapping alternative names to canonical keyword entries
KEYWORD_ALIASES: dict[str, str] = {
    "o": "output",
    "-o": "output",
    "--output": "output",
    "limit": "nrows",
    "-limit": "nrows",
    "--limit": "nrows",
    "out_dir": "output",
    "-out_dir": "output",
    "--out_dir": "output",
    "sort": "arrange",
    "-sort": "arrange",
    "sort_by": "arrange",
    "-sort_by": "arrange",
    "qry": "filter",
    "-qry": "filter",
    "query": "filter",
    "-query": "filter",
}


def get_keyword_help(query: str) -> str | None:
    """Look up keyword-specific help for a CLI flag or keyword name."""
    clean = query.strip().lstrip("-").lower()
    canonical = KEYWORD_ALIASES.get(clean, clean)
    doc = KEYWORD_DOCS.get(canonical)

    if doc is None:
        # Check closest matches
        available = sorted(list(KEYWORD_DOCS.keys()))
        matches = difflib.get_close_matches(clean, available, n=2, cutoff=0.6)
        hint = f" (did you mean: {', '.join('-' + m for m in matches)}?)" if matches else ""
        return (
            f"No dedicated help topic for keyword '{query}'{hint}.\n"
            f"Available keywords with help: {', '.join('-' + k for k in available)}\n"
            f"Run 'pytae -help' to see the full reference manual."
        )

    lines: list[str] = [
        "=" * 80,
        f"PYTAE CLI KEYWORD HELP: -{doc.name}",
        "=" * 80,
        f"FLAG:     {doc.flag}",
        f"SYNTAX:   {doc.syntax}",
        f"SUMMARY:  {doc.summary}",
        "",
        "DESCRIPTION:",
        doc.description,
        "",
    ]

    if doc.options:
        lines.append("PARAMETERS & OPTIONS:")
        for opt in doc.options:
            lines.append(f"  • {opt}")
        lines.append("")

    lines.append("EXAMPLES:")
    for ex in doc.examples:
        lines.append(f"  $ {ex}")
    lines.append("")

    if doc.see_also:
        lines.append(f"SEE ALSO: {', '.join(doc.see_also)}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)
