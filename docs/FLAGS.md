# Which flag?

One page. Full reference: [CLI.md](CLI.md). Library: `import pytae as pt` then `pt.select(df, …)` or `df.pt.select(…)`. CLI flags are unchanged.

| I want to… | Flag | Not that one |
|---|---|---|
| Keep these columns | `-select` | `-drop` is subtract; `-cols` only prints names |
| Remove known column names | `-drop` | names only; patterns stay on `-select` |
| Filter rows (odd strings, dict syntax) | `-qry` | `-query` is pandas `query()` |
| Filter rows with a pandas expression | `-query` | |
| Create/overwrite columns | `-mutate` | |
| Run SQL | `-sql` | view is table `df`; library: `pt.sql(df, …)` / `df.pt.sql(…)` |
| Sort rows | `-sort_by` | |
| Unique rows | `-unique` | `-drop` is columns |
| Replace cell values | `-replace_values` | `-rename` is headers; `-clean_columns` is header *cleanup* |
| Rename headers | `-rename` | only at `-convert` / write |
| Clean messy headers | `-clean_columns` | |
| Fill NA | `-handle_missing` | `-dropna` is NA *keys* in agg/crosstab/value_counts |
| Aggregate (auto groups = non-numeric cols) | `-agg_df` | |
| Aggregate (you name the groups) | `-group_by` + `-agg` | |
| Broadcast a group stat back to rows | `-group_x` | |
| Melt numerics to rows | `-long` | |
| Pivot long → wide | `-wide` | `-crosstab` is a count/mean *matrix* |
| Two-way counts / rates | `-crosstab` | |
| Peek | `-head` / `-tail` / `-sample` | |
| Schema | `-cols` / `-dtype` / `-shape` / `-nulls` / `-info` / `-describe` | `-shape`/`-cols`/`-dtype`/`-nulls`/`-info` cannot be followed except `-to_clip` |
| Write a file | `-convert` | |
| Combine files | `-file` + `-merge` / `-concat` / `-sql` | see [CLI_MULTI_FILE.md](CLI_MULTI_FILE.md) |

**Compose polarities by chaining**, not by mixing tokens:

```bash
pytae penguins.parquet -select "dtype=numeric,species" -drop "body_mass_g" -cols
pytae penguins.parquet -qry "species: 'Adelie'" -drop "species" -head
```

`-select` picks (and may reorder). `-drop` subtracts and leaves order alone.

## Pytae kwargs are `c=` / `v=` / `a=`

Those three letters are pytae's own names. They stay:

| Key | Meaning | Flags |
|---|---|---|
| `c=` | column role (melt/pivot dimension, or replace scope) | `-long`, `-wide`, `-replace_values` |
| `v=` | value column (or the value map on replace) | `-long`, `-wide`, `-group_x`, `-replace_values` |
| `a=` | aggregation | `-wide`, `-group_x`, `-agg_df` |

When the spec *is* the column list, names stay bare (`-select`, `-drop`, `-group_by`, `-sort_by`) — not `c=`.

Pandas-mirrored flags keep pandas names: `-agg` uses `column=` / `aggfunc=` / `as=`; `-crosstab` uses `index=` / `columns=` / `values=` / `aggfunc=`.

Library: `pt.select(df, …)` or `df.pt.select(…)`. CLI flags are unchanged.
