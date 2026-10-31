"""High-performance, zero-dependency documentation search engine using SQLite FTS5 (BM25) and MCP server."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

SYNONYMS: dict[str, list[str]] = {
    "explode": ["flatten", "unnest", "list", "array", "expand", "items", "json", "iterable"],
    "diff": ["compare", "drift", "tolerance", "schema drift", "table diff", "mismatch", "align", "keys", "tol", "rtol"],
    "assert": ["validate", "validation", "check", "invariant", "data quality", "schema test", "ensure", "rule"],
    "filter": ["where", "subset", "condition", "slice rows", "row filter", "equals", "regex", "is_null", "is_not_null"],
    "mutate": ["assign", "compute", "transform", "feature engineering", "with_columns", "new column", "formula"],
    "by": ["group", "groupby", "group_by", "partition", "scoped", "subgroup"],
    "arrange": ["sort", "order", "rank", "descending", "ascending", "alphabetical"],
    "select": ["columns", "pick", "drop columns", "exclude", "slice columns", "rename"],
    "distinct": ["dedupe", "unique", "drop_duplicates", "distinct rows", "deduplicate"],
    "count": ["tally", "frequency", "size", "n", "occurrences"],
    "agg": ["summarize", "aggregate", "sum", "mean", "average", "median", "min", "max"],
    "pivot": ["crosstab", "cross-tabulation", "2d table", "excel pivot", "contingency table"],
    "long": ["melt", "unpivot", "gather", "long format", "variable value"],
    "wide": ["spread", "unmelt", "wide format", "1-to-1"],
    "dropna": ["missing", "drop null", "drop nan", "clean missing", "nulls"],
    "fillna": ["impute", "fill null", "fill nan", "imputation", "replacement"],
    "mask": ["pii", "privacy", "encrypt", "hash", "sha256", "tokenize", "redact", "security"],
    "unmask": ["decrypt", "de-tokenize", "revert masking", "reveal"],
    "join": ["merge", "lookup", "inner join", "left join", "anti join", "semi join", "relational"],
    "concat": ["stack", "union", "append", "vstack", "hstack", "vertical", "horizontal"],
    "repl": ["interactive", "shell", "undo", "redo", "checkpoint", "session", "history", "reset"],
    "plot": ["chart", "graph", "visualization", "histogram", "scatter", "bar chart", "correlation", "heatmap"],
    "clean_columns": ["sanitize headers", "clean names", "snake case", "dedupe columns", "column names"],
}


@dataclass
class DocResult:
    topic: str
    title: str
    category: str
    syntax: str
    content: str
    score: float = 0.0


def _get_db_path() -> Path:
    cand1 = Path(__file__).resolve().parent / "reference" / "pytae_docs.db"
    if cand1.exists():
        return cand1
    cand2 = Path(__file__).resolve().parent.parent.parent / "reference" / "pytae_docs.db"
    if cand2.exists():
        return cand2
    cache_dir = Path.home() / ".cache" / "pytae"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "pytae_docs.db"


def _extract_doc_chunks() -> list[dict[str, str]]:
    """Extract structured documentation chunks from keyword docs, manual text, and markdown files."""
    chunks: list[dict[str, str]] = []

    # 1. CLI keywords from KEYWORD_DOCS
    try:
        from pytae.cli_help import KEYWORD_DOCS

        for name, doc in KEYWORD_DOCS.items():
            syns = SYNONYMS.get(name, [])
            body_parts = [
                f"### Summary\n{doc.summary}\n",
                f"### Description\n{doc.description}\n",
            ]
            if doc.options:
                body_parts.append("### Options\n" + "\n".join(f"- {opt}" for opt in doc.options) + "\n")
            if doc.examples:
                body_parts.append("### Examples\n```bash\n" + "\n".join(doc.examples) + "\n```\n")
            if doc.see_also:
                body_parts.append("### See Also\n" + ", ".join(doc.see_also))

            content = "\n".join(body_parts)
            keywords = f"{name} {doc.flag} {' '.join(syns)} {doc.summary}"
            chunks.append({
                "topic": name,
                "title": f"CLI Flag: {doc.flag}",
                "category": "cli",
                "keywords": keywords,
                "syntax": doc.syntax,
                "content": content,
            })
    except Exception:
        pass

    # 2. Python API Verbs & Core Concepts
    python_verbs = [
        {
            "topic": "filter",
            "title": "Python API: pt.filter() / df.pt.filter()",
            "category": "python_api",
            "syntax": "pt.filter(df, *conditions) / df.filter(*conditions)",
            "keywords": "filter where query subset rows condition boolean equals in not is_null is_nan",
            "content": (
                "Filter rows using pytae expressions with Polars speed.\n\n"
                "### Syntax & Rules\n"
                "- Strict equality: '==' strictly required; single '=' raises an error.\n"
                "- Quoted string literals: 'species == \\'Gentoo\\''.\n"
                "- Logic: and, or, parentheses ().\n"
                "- Null checks: col.is_null(), col.is_not_null(), col.is_nan().\n"
                "- List membership: col in ['a', 'b'].\n\n"
                "### Examples\n"
                "```python\n"
                "df.filter(\"species == 'Gentoo' and body_mass_g > 4000\")\n"
                "df.filter(\"island in ['Biscoe', 'Dream']\")\n"
                "df.filter(\"bill_length_mm.is_not_null()\")\n"
                "```"
            ),
        },
        {
            "topic": "by",
            "title": "Python API: pt.by() / df.pt.by() — Scoped Grouping",
            "category": "python_api",
            "syntax": "df.by(*cols).agg(...) / df.by(*cols).mutate(...)",
            "keywords": "by groupby group group_by scoped grouping partition subtotal window",
            "content": (
                "Scoped grouping for aggregations, mutations, and row slicing.\n"
                "Unlike Pandas groupby(), pytae by() returns an active GroupedDataFrame that chain directly "
                "into .agg(), .mutate(), .head(), .tail().\n\n"
                "### Examples\n"
                "```python\n"
                "# Grouped aggregation:\n"
                "df.by('species').agg(avg_mass='body_mass_g:mean', n='count')\n\n"
                "# Grouped window mutation:\n"
                "df.by('species').mutate(pct_mass='body_mass_g / sum(body_mass_g)')\n\n"
                "# Top N per group:\n"
                "df.by('species').arrange('body_mass_g desc').head(2)\n"
                "```"
            ),
        },
        {
            "topic": "mutate",
            "title": "Python API: pt.mutate() / df.pt.mutate() — Column Creation",
            "category": "python_api",
            "syntax": "df.mutate(new_col='expr', ...) / pt.mutate(df, ...)",
            "keywords": "mutate assign create column feature engineering transform with_columns calculation",
            "content": (
                "Create or overwrite columns with expressions or multi-column formulas.\n\n"
                "### Single & Multi-Column Assignment\n"
                "- Single assignment: df.mutate(mass_kg='body_mass_g / 1000')\n"
                "- Multi-column placeholder '_': df.mutate('(c1, c2)_log'='log(_ + 1)')\n"
                "- Prefix/suffix mapping: df.mutate('log_(c1, c2)'='log(_)')\n\n"
                "### Examples\n"
                "```python\n"
                "df.mutate(ratio='bill_length_mm / bill_depth_mm')\n"
                "df.mutate(is_heavy='body_mass_g > 4500')\n"
                "```"
            ),
        },
        {
            "topic": "select",
            "title": "Python API: pt.select() / df.pt.select() — Column Selection",
            "category": "python_api",
            "syntax": "df.select(*cols, **renames) / pt.select(df, ...)",
            "keywords": "select columns pick drop keep exclude slice rename negative",
            "content": (
                "Select, slice, reorder, or drop columns using names, ranges, prefixes, or negation.\n\n"
                "### Patterns\n"
                "- By name: df.select('species', 'body_mass_g')\n"
                "- Inverted drop: df.select('!sex', '!year') or df.select('-sex')\n"
                "- Column slices: df.select('bill_length_mm:body_mass_g')\n"
                "- Select and rename: df.select('species', mass='body_mass_g')\n"
                "- Pattern matching: df.select('starts_with=bill', 'ends_with=mm')\n"
            ),
        },
        {
            "topic": "arrange",
            "title": "Python API: pt.arrange() / df.pt.arrange() — Row Sorting",
            "category": "python_api",
            "syntax": "df.arrange(*cols, ascending=True) / pt.arrange(df, ...)",
            "keywords": "arrange sort order rank ascending descending sort_by",
            "content": (
                "Sort rows by one or more columns with ascending/descending control.\n\n"
                "### Examples\n"
                "```python\n"
                "df.arrange('body_mass_g desc')\n"
                "df.arrange('species', 'body_mass_g desc')\n"
                "df.arrange('island', ascending=True)\n"
                "```"
            ),
        },
        {
            "topic": "assert",
            "title": "Python API: pt.assert_() / df.assert_() — Invariant Checking",
            "category": "python_api",
            "syntax": "df.assert_(*conditions) / pt.assert_(df, *conditions)",
            "keywords": "assert assert_ validate check data quality invariant schema test",
            "content": (
                "Enforce data quality and schema invariants at any point in the pipeline without filtering.\n"
                "If all rows satisfy the conditions, returns unmodified DataFrame for method chaining.\n"
                "If any condition fails, halts immediately with ValidationError showing failure count and samples.\n\n"
                "### Examples\n"
                "```python\n"
                "df.assert_('body_mass_g > 0', 'species.is_not_null()')\n"
                "df.filter(\"status == 'ACTIVE'\").assert_('amount >= 0').mutate(tax='amount * 0.08')\n"
                "```"
            ),
        },
        {
            "topic": "explode",
            "title": "Python API: pt.explode() / df.explode() — Unnest List Columns",
            "category": "python_api",
            "syntax": "df.explode(*cols) / pt.explode(df, *cols)",
            "keywords": "explode unnest flatten list array json expand items quantities",
            "content": (
                "Flattens and unnests list, array, or iterable columns into separate rows, "
                "duplicating non-exploded column values across each element.\n\n"
                "### Examples\n"
                "```python\n"
                "# Unnest a single list column:\n"
                "df.explode('tags')\n\n"
                "# Unnest multiple list columns simultaneously:\n"
                "df.explode('items', 'quantities')\n"
                "```"
            ),
        },
        {
            "topic": "diff",
            "title": "Python API: pt.diff() / df.diff() — Key-Aware Dataset Diffing",
            "category": "python_api",
            "syntax": "df.diff(other, on=None, tol=0.0, rtol=0.0) / pt.diff(left, right, ...)",
            "keywords": "diff compare schema drift table diff alignment on tolerance tol rtol",
            "content": (
                "Compares schema, dimensions, column drift, null counts, and cell values between two datasets.\n\n"
                "### Key-Aware Diffing (on=key)\n"
                "Aligns rows by primary or composite key, reporting added/removed keys and cell mismatches "
                "on matching keys even when row counts or order differ.\n\n"
                "### Examples\n"
                "```python\n"
                "# Simple positional diff:\n"
                "report = df1.diff(df2)\n\n"
                "# Key-aligned diff with numeric tolerance:\n"
                "report = pt.diff(df1, df2, on='id', tol=1e-4, rtol=1e-5)\n"
                "report = df1.diff(df2, on=['order_id', 'date'], tol=0.01)\n"
                "```"
            ),
        },
        {
            "topic": "pivot",
            "title": "Python API: pt.pivot() / df.pivot() — 2D Pivot Tables",
            "category": "python_api",
            "syntax": "df.pt.pivot(r='...', c='...', v='...', a='mean') / pt.pivot(df, ...)",
            "keywords": "pivot crosstab cross-tabulation 2d table excel aggregation rcva",
            "content": (
                "2D pivot tables and cross-tabulations with mathematical aggregation.\n"
                "Uses the unified rcva grammar: r=row, c=col, v=value, a=aggregation.\n\n"
                "### Examples\n"
                "```python\n"
                "# Value aggregation:\n"
                "df.pt.pivot(r='island', c='species', v='body_mass_g', a='mean')\n\n"
                "# Two-way frequency count:\n"
                "df.pt.pivot(r='island', c='species', a='count')\n"
                "```"
            ),
        },
        {
            "topic": "repl",
            "title": "Interactive REPL Shell: pytae -i / pt.repl()",
            "category": "repl",
            "syntax": "pytae -i / pytae data.parquet -i / pt.repl(df)",
            "keywords": "repl interactive shell undo redo checkpoint session history cli py export",
            "content": (
                "Stateful in-memory exploratory data analysis without reloading files from disk.\n\n"
                "### Core Commands\n"
                "- undo / redo: Instant O(1) step rollback and re-apply.\n"
                "- reset / reset initial: Revert to latest checkpoint or initial file read.\n"
                "- checkpoint <name> / restore <name>: Freeze and restore memory snapshots.\n"
                "- session save <name> / session load <name>: Disk-persisted multi-table workbenches.\n"
                "- history: View numbered audit log.\n"
                "- history -cli: Export reproducible one-shot CLI command reconstructing the session.\n"
                "- history -py: Export runnable Python script with pt/DataFrame calls.\n"
                "- load 'parts/*.parquet' as df4: Multi-file globbing and directory scanning.\n"
            ),
        },
    ]
    for pv in python_verbs:
        syns = SYNONYMS.get(pv["topic"], [])
        pv["keywords"] = f"{pv['keywords']} {' '.join(syns)}"
        chunks.append(pv)

    # 3. Detailed Markdown sections from docs/detailed_docs/cli/*.md
    repo_root = Path(__file__).resolve().parent.parent.parent
    detailed_dir = repo_root / "docs" / "detailed_docs" / "cli"
    if detailed_dir.exists():
        for md_path in sorted(detailed_dir.glob("*.md")):
            topic_name = md_path.stem
            try:
                text = md_path.read_text(encoding="utf-8")
                # Split by ## headers
                sections = re.split(r"\n(?=##\s+)", text)
                for sec in sections:
                    sec_clean = sec.strip()
                    if not sec_clean.startswith("##"):
                        continue
                    first_line = sec_clean.split("\n", 1)[0]
                    sec_title = first_line.lstrip("#").strip()
                    if sec_title.lower() in ("contents", "table of contents"):
                        continue
                    syns = SYNONYMS.get(topic_name, [])
                    keywords = f"{topic_name} {sec_title} {' '.join(syns)}"
                    chunks.append({
                        "topic": topic_name,
                        "title": f"{topic_name}: {sec_title}",
                        "category": "detailed_guide",
                        "keywords": keywords,
                        "syntax": f"pytae ... -{topic_name}",
                        "content": sec_clean,
                    })
            except Exception:
                pass

    return chunks


def build_search_index(db_path: Path | str | None = None) -> Path:
    """Build or rebuild the SQLite FTS5 search index."""
    if db_path is None:
        target_path = _get_db_path()
    else:
        target_path = Path(db_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        try:
            target_path.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(str(target_path))
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("""
            CREATE VIRTUAL TABLE docs_fts USING fts5(
                topic,
                title,
                category,
                keywords,
                syntax,
                content,
                tokenize = 'porter unicode61'
            );
        """)

        chunks = _extract_doc_chunks()
        conn.executemany(
            """
            INSERT INTO docs_fts (topic, title, category, keywords, syntax, content)
            VALUES (:topic, :title, :category, :keywords, :syntax, :content);
            """,
            chunks,
        )
        conn.commit()
    finally:
        conn.close()

    return target_path


def _open_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else _get_db_path()
    if not path.exists():
        build_search_index(path)
    return sqlite3.connect(str(path))


def _sanitize_fts_query(raw_query: str) -> str:
    """Sanitize user search query into valid SQLite FTS5 query with wildcard token matching."""
    cleaned = re.sub(r'[^a-zA-Z0-9_\s]', " ", raw_query).strip()
    tokens = [t.lower() for t in cleaned.split() if t.strip()]
    if not tokens:
        return ""

    clauses: list[str] = []
    for t in tokens:
        clauses.append(f'(topic:"{t}" OR title:"{t}"* OR keywords:"{t}"* OR content:"{t}"*)')
    return " AND ".join(clauses)


def search_docs(
    query: str,
    limit: int = 3,
    category: str | None = None,
    db_path: Path | None = None,
) -> list[DocResult]:
    """Search pytae documentation using BM25 full-text ranking."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []

    conn = _open_db(db_path)
    results: list[DocResult] = []
    try:
        if category:
            sql = """
                SELECT topic, title, category, syntax, content, rank
                FROM docs_fts
                WHERE docs_fts MATCH ? AND category = ?
                ORDER BY rank
                LIMIT ?;
            """
            cur = conn.execute(sql, (fts_query, category, limit))
        else:
            sql = """
                SELECT topic, title, category, syntax, content, rank
                FROM docs_fts
                WHERE docs_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """
            cur = conn.execute(sql, (fts_query, limit))

        for row in cur.fetchall():
            results.append(
                DocResult(
                    topic=row[0],
                    title=row[1],
                    category=row[2],
                    syntax=row[3],
                    content=row[4],
                    score=float(row[5]),
                )
            )

        # Fallback to substring search if FTS returned zero matches
        if not results:
            clean_word = re.sub(r'[^a-zA-Z0-9_]', "", query).strip().lower()
            if clean_word:
                sql_fallback = """
                    SELECT topic, title, category, syntax, content, 0.0
                    FROM docs_fts
                    WHERE topic LIKE ? OR title LIKE ? OR keywords LIKE ?
                    LIMIT ?;
                """
                pattern = f"%{clean_word}%"
                cur_fb = conn.execute(sql_fallback, (pattern, pattern, pattern, limit))
                for row in cur_fb.fetchall():
                    results.append(
                        DocResult(
                            topic=row[0],
                            title=row[1],
                            category=row[2],
                            syntax=row[3],
                            content=row[4],
                            score=0.0,
                        )
                    )
    finally:
        conn.close()

    return results


def format_search_results(results: list[DocResult], query: str = "") -> str:
    """Format documentation search results as clean Markdown."""
    if not results:
        msg = f"No documentation found matching '{query}'." if query else "No documentation found."
        msg += "\nTry searching for core verbs (filter, mutate, by, agg, explode, diff, assert, pivot, long, wide, repl)."
        return msg

    out: list[str] = []
    for i, res in enumerate(results, 1):
        out.append("=" * 80)
        out.append(f"[{i}] {res.title} ({res.category})")
        if res.syntax:
            out.append(f"Syntax: {res.syntax}")
        out.append("-" * 80)
        out.append(res.content.strip())
        out.append("")
    return "\n".join(out)


def cli_doc_search(argv: list[str]) -> int:
    """Handle `pytae doc <query>` CLI command."""
    if not argv:
        print("Usage: pytae doc <keyword or query>")
        print("Examples:")
        print("  pytae doc explode")
        print("  pytae doc 'key-aware diff'")
        print("  pytae doc assert")
        print("  pytae doc 'grouped percentiles'")
        return 0

    query = " ".join(argv).strip().strip("\"'")
    results = search_docs(query, limit=3)
    formatted = format_search_results(results, query=query)
    print(formatted)
    return 0


# ==============================================================================
# Model Context Protocol (MCP) Stdio JSON-RPC 2.0 Server Implementation
# ==============================================================================

def run_mcp_server() -> int:
    """Run lightweight stdio MCP server for Microsoft Copilot, Cursor, and VS Code."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    try:
        ver = _pkg_version("pytae")
    except PackageNotFoundError:
        ver = "3.12.8"

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            msg_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            # 1. Initialize
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "pytae-docs-mcp",
                            "version": ver,
                        },
                    },
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            # 2. Initialized notification (no response)
            elif method == "notifications/initialized":
                continue

            # 3. Ping
            elif method == "ping":
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            # 4. List Tools
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [
                            {
                                "name": "pytae_doc",
                                "description": (
                                    "Search official Pytae documentation, CLI flags, Python API verbs, "
                                    "syntax invariants (==, on=, assert_, explode, by), and recipes."
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "The search query (e.g. 'explode', 'diff on key', 'assert', 'by mutate', 'pivot')",
                                        },
                                        "limit": {
                                            "type": "integer",
                                            "description": "Maximum number of documentation chunks to return (default 3)",
                                            "default": 3,
                                        },
                                    },
                                    "required": ["query"],
                                },
                            }
                        ]
                    },
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            # 5. Call Tool
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                if tool_name == "pytae_doc":
                    q = str(tool_args.get("query", ""))
                    lim = int(tool_args.get("limit", 3))
                    results = search_docs(q, limit=lim)
                    content_str = format_search_results(results, query=q)
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": content_str,
                                }
                            ]
                        },
                    }
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}",
                        },
                    }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            # 6. Fallback / Unknown method
            else:
                if msg_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()

        except Exception as e:
            if "msg_id" in locals() and msg_id is not None:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": str(e),
                    },
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()

    return 0
