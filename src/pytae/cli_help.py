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
        syntax="pytae <path> -sql \"<QUERY>\" [other flags...]",
        summary="Run full analytical SQL queries via DuckDB directly against data.",
        description=(
            "Executes zero-copy, vectorized SQL queries via embedded DuckDB.\n"
            "- In single-file pipelines, the current dataset view is queryable as table `data`.\n"
            "- In multi-file mode (-file), each file alias (e.g. df1, df2) is queryable directly by name.\n"
            "- Standard SQL identifier quoting applies: double quotes for names with spaces (\"col a\"),\n"
            "  and single quotes for string literals ('Gentoo').\n"
            "- To run queries from a file, prefix the filename with '@' (e.g. -sql @query.sql)."
        ),
        options=[
            "`data` : Default in-memory table representing the current pipeline view.",
            "@file.sql : Load SQL query string directly from an external SQL file.",
            "DuckDB functions : Full support for CTEs, WINDOW functions, aggregate functions, and math.",
        ],
        examples=[
            'pytae penguins.parquet -sql "select species, island, body_mass_g from data where body_mass_g > 5000" -head 5',
            'pytae penguins.parquet -sql "select species, count(*) as n, round(avg(body_mass_g), 1) as avg_mass from data group by species"',
            'pytae penguins.parquet -sql "select [bill length mm], body_mass_g from data" -head 3',
            'pytae -file "sales.parquet=s; stores.parquet=st" -sql "select s.*, st.city from s join st using (store_id)"',
            'pytae sales.parquet -sql @queries/quarterly_report.sql -o report.csv',
        ],
        see_also=["-qry", "-agg", "-pivot", "-file"],
    ),
    "qry": KeywordHelp(
        name="qry",
        flag="-qry, --qry CONDITIONS",
        syntax="pytae <path> -qry \"<CONDITIONS>\"",
        summary="Filter DataFrame rows using expressions, interval bounds, and string checks.",
        description=(
            "Filters rows at this point in the pipeline using pytae qry().\n"
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
            "pytae penguins.parquet -qry \"species == 'Gentoo', body_mass_g > 5000\"",
            "pytae penguins.parquet -qry \"body_mass_g = [4000, 5000]\" -shape",
            "pytae penguins.parquet -qry \"island in ['Biscoe', 'Dream']\"",
            "pytae data.csv -qry \"[customer name] = 'Acme Corp'\"",
        ],
        see_also=["-sql", "-select", "-dropna"],
    ),
    "select": KeywordHelp(
        name="select",
        flag="-select, --select SPEC",
        syntax="pytae <path> -select \"<SPEC>\"",
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
            "pytae penguins.parquet -select \"species,island,body_mass_g\"",
            "pytae penguins.parquet -select \"bill_length_mm:body_mass_g\"",
            "pytae penguins.parquet -select \"-sex, -year\"",
            "pytae penguins.parquet -select \"contains=bill, species\"",
            "pytae penguins.parquet -select \"dtype=numeric\"",
        ],
        see_also=["-cols", "-qry", "-clean_columns"],
    ),
    "mutate": KeywordHelp(
        name="mutate",
        flag="-mutate, --mutate SPEC",
        syntax="pytae <path> -mutate \"<col1 = expr1, col2 = expr2>\"",
        summary="Create, modify, or engineer columns using vectorized expressions or grouped window transforms.",
        description=(
            "Evaluates column assignments sequentially from left to right.\n"
            "Expressions support standard arithmetic, boolean logic, pandas Series methods,\n"
            "and window aggregations when combined with -by (e.g. -by species -mutate \"avg = mean(mass)\")."
        ),
        options=[
            "new_col = expr : Define new column calculated from existing columns.",
            "[col with spaces] : Target or reference column headers that contain spaces.",
            "-by <col> : Evaluate window aggregations (mean, sum, min, max, std, n) per group without collapsing rows.",
        ],
        examples=[
            "pytae penguins.parquet -mutate \"mass_kg = body_mass_g / 1000\" -head 3",
            "pytae penguins.parquet -mutate \"bill_ratio = bill_length_mm / bill_depth_mm\"",
            "pytae penguins.parquet -by species -mutate \"avg_mass = mean(body_mass_g), diff = body_mass_g - avg_mass\"",
            "pytae penguins.parquet -mutate \"source = '2024_survey'\"",
        ],
        see_also=["-agg", "-by", "-select"],
    ),
    "arrange": KeywordHelp(
        name="arrange",
        flag="-arrange, --arrange SPEC",
        syntax="pytae <path> -arrange \"<col1 [desc], -col2, ...>\"",
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
            "pytae penguins.parquet -arrange \"body_mass_g desc\" -head 5",
            "pytae penguins.parquet -arrange \"species, -body_mass_g\"",
            "pytae penguins.parquet -arrange \"island, bill_length_mm asc\"",
        ],
        see_also=["-slice_max", "-slice_min", "-head"],
    ),
    "slice_max": KeywordHelp(
        name="slice_max",
        flag="-slice_max, --slice_max SPEC",
        syntax="pytae <path> [-by <cols>] -slice_max \"<col>[,n=N]\"",
        summary="Slice top N rows with the largest values, optionally grouped by column(s).",
        description=(
            "Selects rows with the highest values of a target column.\n"
            "When paired with -by, extracts the top N rows per group."
        ),
        options=[
            "col : Column to rank by (defaults to n=1).",
            "col,n=N : Extract the top N rows (e.g. 'body_mass_g,n=3').",
            "-by <cols> : Grouping column(s) to partition by before slicing.",
        ],
        examples=[
            "pytae penguins.parquet -slice_max body_mass_g",
            "pytae penguins.parquet -slice_max \"body_mass_g,n=5\"",
            "pytae penguins.parquet -by species -slice_max \"body_mass_g,n=2\"",
        ],
        see_also=["-slice_min", "-arrange", "-head"],
    ),
    "slice_min": KeywordHelp(
        name="slice_min",
        flag="-slice_min, --slice_min SPEC",
        syntax="pytae <path> [-by <cols>] -slice_min \"<col>[,n=N]\"",
        summary="Slice bottom N rows with the smallest values, optionally grouped by column(s).",
        description=(
            "Selects rows with the lowest values of a target column.\n"
            "When paired with -by, extracts the bottom N rows per group."
        ),
        options=[
            "col : Column to rank by (defaults to n=1).",
            "col,n=N : Extract bottom N rows (e.g. 'body_mass_g,n=3').",
            "-by <cols> : Grouping column(s) to partition by before slicing.",
        ],
        examples=[
            "pytae penguins.parquet -slice_min body_mass_g",
            "pytae penguins.parquet -slice_min \"body_mass_g,n=3\"",
            "pytae penguins.parquet -by species -slice_min \"body_mass_g,n=1\"",
        ],
        see_also=["-slice_max", "-arrange", "-tail"],
    ),
    "agg": KeywordHelp(
        name="agg",
        flag="-agg, --agg [AGGFUNC]",
        syntax="pytae <path> [-by <cols>] -agg [AGGFUNC]",
        summary="Aggregate numeric columns grouped by -by (or whole-table summary without -by).",
        description=(
            "Computes summary statistics on numeric columns.\n"
            "If -by is omitted, produces a whole-table grand total summary.\n"
            "Accepts a function name ('mean'), a list ('mean,sum,n'), or mapped expressions ('avg=mean,total=sum')."
        ),
        options=[
            "-by <cols> : Grouping column(s) (comma-separated).",
            "mean, sum, median, min, max, std, var : Built-in aggregation functions.",
            "n : Group row count (pure integer).",
            "col = func : Column-specific mapping (e.g. 'total=sum,avg=mean').",
        ],
        examples=[
            "pytae penguins.parquet -by species -agg mean",
            "pytae penguins.parquet -by \"species,island\" -agg \"mean,sum,n\"",
            "pytae penguins.parquet -agg \"mean,n\"   # Whole-table summary (grand total)",
            "pytae penguins.parquet -by species -agg \"total_mass = body_mass_g:sum, n = n\"",
        ],
        see_also=["-by", "-pivot", "-mutate"],
    ),
    "pivot": KeywordHelp(
        name="pivot",
        flag="-pivot, --pivot [KEY=VALUE,...]",
        syntax="pytae <path> -pivot \"r=rows,c=cols,v=values,a=func\"",
        summary="Create 2D Excel-style contingency tables and pivot matrices.",
        description=(
            "Full multi-dimensional pivot table engine.\n"
            "Flattens multi-level column hierarchies to clean 1D strings and resets index to RangeIndex.\n"
            "Missing combinations default to fill_value (or 0 for row counts a=n)."
        ),
        options=[
            "r=row_cols : Row grouping dimension(s).",
            "c=col_cols : Column dimension(s) to spread as headers.",
            "v=value_cols : Metric column(s) to aggregate (optional when a=n).",
            "a=func : Aggregation function (default: sum; 'n' for counts).",
            "fill_value=val : Replacement for empty grid cells (default 0 for a=n).",
            "dropna=true|false : Whether to drop NA categories (default: false).",
        ],
        examples=[
            "pytae penguins.parquet -pivot \"r=island,c=species,v=body_mass_g,a=mean\"",
            "pytae penguins.parquet -pivot \"r=island,c=species,a=n\"   # Frequency cross-tabulation",
            "pytae penguins.parquet -pivot \"r='species,island',c=sex,v=body_mass_g,a=median,fill_value=0\"",
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
            "pytae penguins.parquet -long \"c=measurement,v=value\"",
            "pytae data.csv -long \"cols='q1,q2,q3,q4',c=quarter,v=revenue\"",
        ],
        see_also=["-wide", "-pivot"],
    ),
    "wide": KeywordHelp(
        name="wide",
        flag="-wide, --wide [KEY=VALUE,...]",
        syntax="pytae <path> -wide [c=var,v=val,index=id_cols]",
        summary="Spread tall rows into wide headers (pure 1-to-1 reshaping, reverse of -long).",
        description=(
            "Spreads unique key/value pairs back into columns without aggregating.\n"
            "Requires unique (index, c) pairs; if duplicates exist, use -pivot instead."
        ),
        options=[
            "c=name : Column whose distinct values become column headers (default: 'variable').",
            "v=name : Column containing cell values (default: 'value').",
            "index=cols : Explicit row identifier column(s) (default: all remaining columns).",
        ],
        examples=[
            "pytae tall.csv -wide",
            "pytae tall.csv -wide \"c=metric,v=measurement\"",
            "pytae tall.csv -wide \"c=quarter,v=revenue,index=customer_id\"",
        ],
        see_also=["-long", "-pivot"],
    ),
    "by": KeywordHelp(
        name="by",
        flag="-by, --by, -group_by COLUMNS",
        syntax="pytae <path> -by <COLUMNS> [operation]",
        summary="Set grouping columns for subsequent group-aware operations (-agg, -mutate, -slice_max, -slice_min).",
        description=(
            "Partitions the dataset by one or more columns for subsequent operations.\n"
            "Works with -agg, window -mutate, and -slice_max / -slice_min."
        ),
        options=[
            "col : Single grouping column.",
            "col1,col2 : Multiple grouping columns (comma-separated).",
            "[col a], [col b] : Bracketed grouping columns with spaces.",
        ],
        examples=[
            "pytae penguins.parquet -by species -agg mean",
            "pytae penguins.parquet -by \"species,island\" -agg \"mean,n\"",
            "pytae penguins.parquet -by species -slice_max \"body_mass_g,n=2\"",
            "pytae penguins.parquet -by species -mutate \"avg = mean(body_mass_g)\"",
        ],
        see_also=["-agg", "-mutate", "-slice_max", "-slice_min"],
    ),
    "clean_columns": KeywordHelp(
        name="clean_columns",
        flag="-clean_columns, --clean_columns SPEC",
        syntax="pytae <path> -clean_columns \"<KEY=VALUE,...>\"",
        summary="Systematically sanitize, normalize, and rename messy column headers.",
        description=(
            "Sanitizes headers in deterministic order:\n"
            "strip -> strip_special -> squeeze -> fill -> case -> dedupe."
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
            "pytae dirty.csv -clean_columns \"strip,fill,case=lower,dedupe\"",
            "pytae dirty.csv -clean_columns \"fill='_',case=lower\"",
            "pytae dirty.csv -clean_columns \"case=upper\"",
        ],
        see_also=["-rename", "-select", "-cols"],
    ),
    "replace_values": KeywordHelp(
        name="replace_values",
        flag="-replace_values, --replace_values SPEC",
        syntax="pytae <path> -replace_values \"v='old:new',c='col1,col2',exact=true\"",
        summary="Search and replace cell values across the entire DataFrame or specific columns.",
        description=(
            "Wraps pandas cell replacement with flexible scope and matching modes."
        ),
        options=[
            "v='old1:new1,old2:new2' : Mapping of replacement pairs (REQUIRED).",
            "c='col1,col2' : Restrict replacement to specific columns (default: entire DataFrame).",
            "exact=true|false : True matches exact full cell values; False matches substring (regex).",
        ],
        examples=[
            "pytae penguins.parquet -replace_values \"v='Biscoe:Biscoe Island'\"",
            "pytae file.csv -replace_values \"c=status,v='0:Inactive,1:Active'\"",
            "pytae file.csv -replace_values \"v='N/A:NaN,null:NaN',exact=true\"",
        ],
        see_also=["-mutate", "-clean_columns", "-handle_missing"],
    ),
    "file": KeywordHelp(
        name="file",
        flag="-file, --file PATH=ALIAS;...",
        syntax="pytae -file \"path1=alias1; path2=alias2\" [operation]",
        summary="Load multiple tabular datasets for multi-file joins (-merge, -concat, or -sql).",
        description=(
            "Replaces the positional path to enable multi-dataset pipelines.\n"
            "Each file is assigned an alias and can be joined via -merge, stacked via -concat, or queried via -sql."
        ),
        options=[
            "path=alias : Assign an in-memory alias to a file.",
            "; (semicolon) : Delimiter between file entries.",
            ",dlim=CHAR : Override field delimiter per file.",
            ",encoding=ENC : Override text encoding per file.",
        ],
        examples=[
            "pytae -file \"orders.parquet=o; cust.csv=c\" -merge \"left=o,right=c,on=cust_id\" -head 5",
            "pytae -file \"2023.parquet=df1; 2024.parquet=df2\" -concat \"frames='df1,df2'\" -o combined.parquet",
            "pytae -file \"orders.parquet=o; items.parquet=i\" -sql \"select o.*, i.name from o join i using (item_id)\"",
        ],
        see_also=["-merge", "-concat", "-sql"],
    ),
    "merge": KeywordHelp(
        name="merge",
        flag="-merge, --merge KEY=VALUE,...",
        syntax="pytae -file \"...\" -merge \"left=alias1,right=alias2,on=key[,how=inner]\"",
        summary="Merge/join two datasets in the pipeline (pandas merge).",
        description=(
            "Combines two datasets by key columns. Repeatable to join additional files sequentially."
        ),
        options=[
            "left=alias : Left dataset alias (or 'data' for current pipeline state).",
            "right=alias : Right dataset alias.",
            "on=col : Shared join key column (or 'on=\"col1,col2\"').",
            "left_on=col, right_on=col : Join keys with differing names (or 'on=\"left_col:right_col\"').",
            "how=inner|left|right|outer|cross : Join method (default: 'inner').",
            "validate=one_to_one|one_to_many : Join cardinality assertion.",
        ],
        examples=[
            "pytae -file \"orders.parquet=o; users.csv=u\" -merge \"left=o,right=u,on=user_id\"",
            "pytae -file \"a.csv=a; b.csv=b\" -merge \"left=a,right=b,on='id:user_id',how=left\"",
        ],
        see_also=["-file", "-concat", "-sql"],
    ),
    "concat": KeywordHelp(
        name="concat",
        flag="-concat, --concat KEY=VALUE,...",
        syntax="pytae -file \"...\" -concat \"frames='alias1,alias2,...'\"",
        summary="Stack multiple datasets vertically row-wise into one pipeline DataFrame.",
        description=(
            "Concatenates two or more datasets along rows (pandas concat with ignore_index=True)."
        ),
        options=[
            "frames='alias1,alias2,...' : Comma-separated list of dataset aliases to stack.",
        ],
        examples=[
            "pytae -file \"jan.csv=m1; feb.csv=m2; mar.csv=m3\" -concat \"frames='m1,m2,m3'\" -o q1.parquet",
        ],
        see_also=["-file", "-merge"],
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
            "pytae penguins.parquet -qry \"species == 'Gentoo'\" -o gentoo.csv",
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
        description=(
            "Displays a text-based distribution chart for categorical columns directly in your terminal."
        ),
        options=[
            "COLUMN : Categorical column name to profile.",
        ],
        examples=[
            "pytae penguins.parquet -freq species",
            "pytae penguins.parquet -freq island",
        ],
        see_also=["-hist", "-value_counts", "-describe"],
    ),
    "hist": KeywordHelp(
        name="hist",
        flag="-hist, --hist COLUMN[:BINS]",
        syntax="pytae <path> -hist <COLUMN[:BINS]>",
        summary="Render in-terminal distribution histogram for numeric columns.",
        description=(
            "Displays ASCII bar distribution and bin counts for numeric columns."
        ),
        options=[
            "COLUMN : Numeric column to bin.",
            "COLUMN:BINS : Optional bin count (default: 10, e.g. body_mass_g:15).",
        ],
        examples=[
            "pytae penguins.parquet -hist body_mass_g",
            "pytae penguins.parquet -hist \"body_mass_g:15\"",
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
        see_also=["-shape", "-cols", "-dtype", "-info"],
    ),
    "diff": KeywordHelp(
        name="diff",
        flag="-diff, --diff PATH",
        syntax="pytae <file1> -diff <file2>",
        summary="Compare schema and contents between two tabular datasets.",
        description=(
            "Compares column lists, types, row counts, and value differences between two files."
        ),
        options=[
            "PATH : Second file path to compare against.",
        ],
        examples=[
            "pytae current.parquet -diff previous.parquet",
            "pytae staging.csv -diff prod.parquet",
        ],
        see_also=["-meta", "-describe"],
    ),
    "head": KeywordHelp(
        name="head",
        flag="-head, --head [N]",
        syntax="pytae <path> -head [N]",
        summary="Print the first N rows (default: 5).",
        description="Limits the working DataFrame to the first N rows.",
        options=["N : Number of rows (default: 5)."],
        examples=[
            "pytae penguins.parquet -head",
            "pytae penguins.parquet -head 10",
        ],
        see_also=["-tail", "-sample", "-nrows"],
    ),
    "tail": KeywordHelp(
        name="tail",
        flag="-tail, --tail [N]",
        syntax="pytae <path> -tail [N]",
        summary="Print the last N rows (default: 5).",
        description="Limits the working DataFrame to the last N rows.",
        options=["N : Number of rows (default: 5)."],
        examples=[
            "pytae penguins.parquet -tail",
            "pytae penguins.parquet -tail 10",
        ],
        see_also=["-head", "-sample"],
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
            "pytae penguins.parquet -qry \"species == 'Gentoo'\" -shape",
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
        see_also=["-cols", "-info", "-nulls"],
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
        see_also=["-dropna", "-handle_missing"],
    ),
    "dropna": KeywordHelp(
        name="dropna",
        flag="-dropna, --dropna [COLS]",
        syntax="pytae <path> -dropna [\"col1,col2\"]",
        summary="Drop rows containing missing (NaN) values.",
        description="Bare -dropna drops rows with any missing value; -dropna 'col1,col2' checks only specified columns.",
        options=[
            "Bare flag : Drop row if ANY column contains NaN.",
            "\"col1,col2\" : Drop row if specified columns contain NaN.",
        ],
        examples=[
            "pytae penguins.parquet -dropna",
            "pytae penguins.parquet -dropna \"sex, body_mass_g\"",
        ],
        see_also=["-handle_missing", "-nulls"],
    ),
    "handle_missing": KeywordHelp(
        name="handle_missing",
        flag="-handle_missing, --handle_missing [FILL]",
        syntax="pytae <path> -handle_missing [FILL]",
        summary="Impute missing values (FILL for strings, 0 for numeric).",
        description="Fills missing values: string/categorical filled with FILL (default '.'), numeric filled with 0.",
        options=["FILL : String replacement scalar (default: '.')."],
        examples=[
            "pytae penguins.parquet -handle_missing",
            "pytae penguins.parquet -handle_missing \"NA\"",
        ],
        see_also=["-dropna", "-nulls"],
    ),
    "dedupe": KeywordHelp(
        name="dedupe",
        flag="-dedupe, --dedupe [COLS]",
        syntax="pytae <path> -dedupe [\"col1,col2\"]",
        summary="Drop duplicate rows (across all or specific columns).",
        description="Drops duplicate records, keeping the first occurrence.",
        options=[
            "Bare flag : Deduplicate across all columns.",
            "\"col1,col2\" : Deduplicate restricted to specified subset of columns.",
        ],
        examples=[
            "pytae data.csv -dedupe",
            "pytae data.csv -dedupe customer_id",
        ],
        see_also=["-dropna", "-qry"],
    ),
    "pretty": KeywordHelp(
        name="pretty",
        flag="-pretty, --pretty",
        syntax="pytae <path> [operations] -pretty",
        summary="Render terminal output as a bordered Markdown table.",
        description="Formats DataFrame output as a GitHub-flavored Markdown bordered table via df.to_markdown().",
        options=[],
        examples=[
            "pytae penguins.parquet -head 5 -pretty",
            "pytae penguins.parquet -by species -agg mean -pretty",
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
}

# Aliases mapping alternative names to canonical keyword entries
KEYWORD_ALIASES: dict[str, str] = {
    "o": "output",
    "-o": "output",
    "--output": "output",
    "group_by": "by",
    "-group_by": "by",
    "--group_by": "by",
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
    "query": "qry",
    "-query": "qry",
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
