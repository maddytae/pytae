# pytae — Multi-file merge (`-file` / `-merge`)

See [CLI Reference](CLI.md) for everything else. This page covers `-file`/`-merge`, the mode for joining **two or more named files** into a single pipeline — everything else in the CLI operates on **one** file (the positional `path`).

`-file` is a separate mode, paired with either `-merge` (pandas `merge()`) or `-sql` (raw SQL join, see below) as the founding op. `-file` **replaces** the positional `path` entirely — you can't mix a positional path with `-file`.

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola,colb:colb',how=inner"
```

## `-file` — load named inputs

Value is `;`-separated entries (at least two), each `PATH=ALIAS` optionally followed by `,dlim=`/`,encoding=` overrides for reading *that* file (handy when joining mismatched formats, e.g. a pipe-delimited `.txt` with a `.csv`):

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" ...
pytae -file "sales.txt=sales,dlim='|'; customers.csv=customers,encoding='latin-1'" ...
```

## `-merge` — join two `-file` aliases

Must be the **first** operation when `-file` is used (it's what creates the pipeline's starting DataFrame — everything after it, `-select`/`-shape`/`-o`/etc., runs on the merged result exactly like the single-file mode), unless you use [`-sql` instead](#sql-alternative). Value is `key=value` tokens:

| Key | Required? | Meaning |
|---|---|---|
| `left=` / `right=` | required | the two `-file` aliases to join |
| `on=` | required | shared join column(s) (comma list) when names match on both sides, or `left:right` pairs when they differ — **quote the whole value** if it has more than one column/pair, e.g. `on='col a:cola,colb:colb'` |
| `how=` | optional (default `inner`) | `inner`/`left`/`right`/`outer`/`cross`, passed straight to pandas `merge()` |
| `validate=` | optional | e.g. `one_to_one`/`one_to_many`/`many_to_one`/`many_to_many`, passed straight to pandas `merge()` |

```bash
# join column names differ between the two files
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola',how=inner"

# join column name is shared, outer join, then keep going like any other pipeline
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on='id',how=outer" -select id,x,y -shape

# validate the join is truly one-to-one, erroring otherwise
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on='id',validate=one_to_one"
```

<a id="sql-alternative"></a>
## `-sql` as an alternative to `-merge`

`-sql` may be used **instead of `-merge`** as the founding op in `-file` mode. Every `-file` alias is registered as its own duckdb table (by its alias name), so you can write the join yourself — more flexible than `-merge`'s `key=value` syntax (arbitrary conditions, multiple joins, inline aggregation, …):

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -sql 'select * from df1 inner join df2 on df1."col a" = df2.cola'
```

Once something in the pipeline has produced a current view (e.g. after `-merge`, or a later `-sql` call), `df` also becomes queryable — same as single-file mode:

```bash
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on='id'" -sql "select count(*) as n from df"
```

## Notes

- `-convert` after a merge requires `-o`/`--output` explicitly (there's no single source file to derive a default `.csv` name from).
- Glob-pattern batch mode (`pytae 'data/*.parquet' -convert`) is a different, unrelated feature — it can't be combined with `-file`.
