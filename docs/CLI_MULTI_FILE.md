# pytae — Multi-file operations (`-file` / `-merge` / `-concat`)

See [CLI Reference](CLI.md) for everything else. This page covers `-file`-based multi-file mode — loading **two or more named files** into a single pipeline instead of the usual one (the positional `path`).

`-file` is a separate mode, paired with `-merge` (join), `-concat` (stack), or `-sql` (raw SQL) as the founding op. `-file` **replaces** the positional `path` entirely — you can't mix a positional path with `-file`.

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola,colb:colb',how=inner"
```

## `-file` — load named inputs

Value is `;`-separated entries (at least two — any number is fine), each `PATH=ALIAS` optionally followed by `,dlim=`/`,encoding=` overrides for reading *that* file (handy when joining mismatched formats, e.g. a pipe-delimited `.txt` with a `.csv`):

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" ...
pytae -file "a.csv=a; b.csv=b; c.csv=c" ...   # three (or more) files are fine
pytae -file "sales.txt=sales,dlim='|'; customers.csv=customers,encoding=latin-1" ...
```

## `-merge` — join `-file` aliases

Must be the **first** operation when `-file` is used, unless [`-sql`](#sql-alternative) or `-concat` starts it instead. **Repeatable** — each occurrence runs one more `pd.merge()`, so you can fold in one file at a time. Value is `key=value` tokens:

| Key | Required? | Meaning |
|---|---|---|
| `left=` / `right=` | required | a `-file` alias, or the literal `df` for the pipeline's current result so far (only valid once something earlier has produced one) |
| `on=` | required | shared join column(s) (comma list) when names match on both sides, or `left:right` pairs when they differ — **quote the whole value** if it has more than one column/pair, e.g. `on='col a:cola,colb:colb'` |
| `how=` | optional (default `inner`) | `inner`/`left`/`right`/`outer`/`cross`, passed straight to pandas `merge()` |
| `validate=` | optional | e.g. `one_to_one`/`one_to_many`/`many_to_one`/`many_to_many`, passed straight to pandas `merge()` |

```bash
# join column names differ between the two files
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on=col a:cola,how=inner"

# join column name is shared, outer join, then keep going like any other pipeline
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on=id,how=outer" -select "id,x,y" -shape

# validate the join is truly one-to-one, erroring otherwise
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on=id,validate=one_to_one"

# fold a third file in: (a ⋈ b) ⋈ c — 'df' means "the result so far"
pytae -file "a.csv=a; b.csv=b; c.csv=c" \
      -merge "left=a,right=b,on=id" \
      -merge "left=df,right=c,on=id"
```

## `-concat` — stack `-file` aliases (pandas `concat()`)

Must be the **first** operation when `-file` is used, unless `-merge` or [`-sql`](#sql-alternative) starts it instead. **Repeatable**, and its `frames=` list already accepts more than two names in one call. The index is always reset (`ignore_index=True`) — not configurable, always on. Value is `key=value` tokens:

| Key | Required? | Meaning |
|---|---|---|
| `frames=` | required | an ordered, comma-separated list of `-file` aliases (or `df` for the pipeline's current result so far) — **quote the whole value**, e.g. `frames='df1,df2,df3'` |

```bash
# stack three files in one call
pytae -file "a.csv=a; b.csv=b; c.csv=c" -concat "frames='a,b,c'"

# or stack incrementally, folding more files onto the running result
pytae -file "a.csv=a; b.csv=b; c.csv=c" -concat "frames='a,b'" -concat "frames='df,c'"
```

<a id="sql-alternative"></a>
## `-sql` as an alternative to `-merge`/`-concat`

`-sql` may be used **instead of `-merge`/`-concat`** as the founding op in `-file` mode. Every `-file` alias is registered as its own duckdb table (by its alias name), so you can write the join (or `union all`, for stacking) yourself — more flexible than `-merge`'s/`-concat`'s `key=value` syntax (arbitrary conditions, multiple joins, inline aggregation, …):

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -sql 'select * from df1 inner join df2 on df1."col a" = df2.cola'
```

Once something in the pipeline has produced a current view (e.g. after `-merge`/`-concat`, or a later `-sql` call), `df` also becomes queryable — same as single-file mode:

```bash
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on=id" -sql "select count(*) as n from df"
```

## Notes

- `-convert` after a merge/concat requires `-o`/`--output` explicitly (there's no single source file to derive a default `.csv` name from).
- Glob-pattern batch mode (`pytae 'data/*.parquet' -convert`) is a different, unrelated feature — it can't be combined with `-file`.

