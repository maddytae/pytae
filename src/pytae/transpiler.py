"""Transpiler and history compiler for converting Pytae REPL logs to Python/Pytae scripts."""

from __future__ import annotations

import ast
import os
import re
import shlex
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from pytae.repl_utils import (
    _normalize_unquoted_windows_paths,
    _parse_reader_options,
    _to_relative_path,
)


class _CTransformer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in ("True", "False", "None", "c", "col"):
            return node
        return ast.Attribute(value=ast.Name(id="c", ctx=ast.Load()), attr=node.id, ctx=node.ctx)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        node = self.generic_visit(node)  # type: ignore[assignment]
        if len(node.ops) == 1:
            if isinstance(node.ops[0], ast.In):
                return ast.Call(
                    func=ast.Attribute(value=node.left, attr="is_in", ctx=ast.Load()),
                    args=[node.comparators[0]],
                    keywords=[],
                )
            elif isinstance(node.ops[0], ast.NotIn):
                call_node = ast.Call(
                    func=ast.Attribute(value=node.left, attr="is_in", ctx=ast.Load()),
                    args=[node.comparators[0]],
                    keywords=[],
                )
                return ast.UnaryOp(op=ast.Invert(), operand=call_node)
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        node = self.generic_visit(node)  # type: ignore[assignment]
        if isinstance(node.op, ast.And):
            res = node.values[0]
            for v in node.values[1:]:
                res = ast.BinOp(left=res, op=ast.BitAnd(), right=v)
            return res
        elif isinstance(node.op, ast.Or):
            res = node.values[0]
            for v in node.values[1:]:
                res = ast.BinOp(left=res, op=ast.BitOr(), right=v)
            return res
        return node


def _transpile_filter_expr(expr_str: str) -> str:
    try:
        clean = expr_str.strip()
        tree = ast.parse(clean, mode="eval")
        if isinstance(tree.body, ast.BoolOp) and isinstance(tree.body.op, ast.And):
            # Top-level `and` conditions transpile to canonical comma-separated arguments:
            # df.filter(c.sex == 'Male', c.body_mass_g > 4000)
            transformer = _CTransformer()
            args = [ast.unparse(transformer.visit(v)) for v in tree.body.values]
            return ", ".join(args)
        tree = _CTransformer().visit(tree)
        return ast.unparse(tree)
    except Exception:
        return repr(expr_str)


def _transpile_mutate_spec(spec_str: str) -> str:
    try:
        parts = [p.strip() for p in spec_str.split(",") if p.strip()]
        kw_parts: list[str] = []
        for p in parts:
            if "=" in p:
                target, rhs = p.split("=", 1)
                target = target.strip()
                rhs = rhs.strip()
                tree = ast.parse(rhs, mode="eval")
                tree = _CTransformer().visit(tree)
                rhs_code = ast.unparse(tree)
                if target.isidentifier():
                    kw_parts.append(f"{target}={rhs_code}")
                else:
                    kw_parts.append(f"**{{{repr(target)}: {rhs_code}}}")
            else:
                return repr(spec_str)
        return ", ".join(kw_parts)
    except Exception:
        return repr(spec_str)


def _transpile_select_spec(cols_val: str) -> str:
    parts = [c.strip() for c in cols_val.split(",") if c.strip()]
    res: list[str] = []
    for p in parts:
        is_neg = p.startswith(("!", "~", "-"))
        inner = p[1:].strip() if is_neg else p

        if ":" in inner:
            start, end = inner.split(":", 1)
            start, end = start.strip().strip("[]'\""), end.strip().strip("[]'\"")
            s_expr = f"c.{start}" if start.isidentifier() else f"c[{repr(start)}]"
            e_expr = f"c.{end}" if end.isidentifier() else f"c[{repr(end)}]"
            range_expr = f"{s_expr}.to({e_expr})"
            res.append(f"~{range_expr}" if is_neg else range_expr)
        else:
            col = inner.strip("[]'\"")
            col_expr = f"c.{col}" if col.isidentifier() else f"c[{repr(col)}]"
            res.append(f"~{col_expr}" if is_neg else col_expr)
    return ", ".join(res)


def _transpile_arrange_spec(col_val: str, desc: bool = False) -> str:
    parts = [p.strip() for p in col_val.split(",") if p.strip()]
    res: list[str] = []
    for p in parts:
        p_clean = p.strip()
        is_desc = desc
        col = p_clean
        if p_clean.lower().endswith(".desc()"):
            col = p_clean[:-7].strip()
            is_desc = True
        elif p_clean.lower().endswith(".asc()"):
            col = p_clean[:-6].strip()
            is_desc = False
        else:
            toks = p_clean.split()
            col = toks[0]
            if len(toks) > 1 and toks[1].lower() in ("desc", "descending"):
                is_desc = True
            elif len(toks) > 1 and toks[1].lower() in ("asc", "ascending"):
                is_desc = False
        col = col.strip("[]'\"")
        c_expr = f"c.{col}" if col.isidentifier() else f"c[{repr(col)}]"
        method = "desc()" if is_desc else "asc()"
        res.append(f"{c_expr}.{method}")
    return ", ".join(res)


def _transpile_pipeline_tokens_to_python(tokens: list[str]) -> str:
    """Convert REPL pipeline tokens into Python method chaining syntax."""
    calls: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        low = tok.lower()

        # -filter <expr>
        if low in ("-filter", "--filter") and i + 1 < n:
            calls.append(f".filter({_transpile_filter_expr(tokens[i + 1])})")
            i += 2
            continue

        # -select <cols>
        if low in ("-select", "--select") and i + 1 < n:
            calls.append(f".select({_transpile_select_spec(tokens[i + 1])})")
            i += 2
            continue

        # -mutate <expr>
        if low in ("-mutate", "--mutate") and i + 1 < n:
            calls.append(f".mutate({_transpile_mutate_spec(tokens[i + 1])})")
            i += 2
            continue

        # -by <cols>
        if low in ("-by", "--by") and i + 1 < n:
            cols_val = tokens[i + 1]
            col_parts = [c.strip() for c in cols_val.split(",") if c.strip()]
            formatted_cols = ", ".join(repr(c) for c in col_parts)
            calls.append(f".by({formatted_cols})")
            i += 2
            continue

        # -agg <specs>
        if low in ("-agg", "--agg") and i + 1 < n:
            calls.append(f".agg({repr(tokens[i + 1])})")
            i += 2
            continue

        # -clean_columns [spec]
        if low in ("-clean_columns", "--clean_columns"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                from pytae.cli_parsing import parse_clean_columns_arg

                try:
                    cc_opts = parse_clean_columns_arg(tokens[i + 1])
                    cc_args = [f"{k}={repr(v)}" for k, v in cc_opts.items()]
                    calls.append(f".clean_columns({', '.join(cc_args)})")
                except Exception:
                    calls.append(".clean_columns()")
                i += 2
            else:
                calls.append(".clean_columns()")
                i += 1
            continue

        # -rename <spec>
        if low in ("-rename", "--rename") and i + 1 < n:
            calls.append(f".rename({repr(tokens[i + 1])})")
            i += 2
            continue

        # -count [cols]
        if low in ("-count", "--count"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                cols_val = tokens[i + 1]
                col_parts = [c.strip() for c in cols_val.split(",") if c.strip()]
                formatted_cols = ", ".join(repr(c) for c in col_parts)
                calls.append(f".count({formatted_cols})")
                i += 2
            else:
                calls.append(".count()")
                i += 1
            continue

        # -sort / -arrange <col> [desc]
        if low in ("-sort", "--sort", "-arrange", "--arrange") and i + 1 < n:
            col_val = tokens[i + 1]
            if i + 2 < n and tokens[i + 2].lower() in ("desc", "descending"):
                calls.append(f".arrange({_transpile_arrange_spec(col_val, desc=True)})")
                i += 3
            else:
                calls.append(f".arrange({_transpile_arrange_spec(col_val)})")
                i += 2
            continue

        # -distinct [spec]
        if low in ("-distinct", "--distinct"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                from pytae.cli_parsing import parse_distinct_spec

                try:
                    d_cols, d_keep = parse_distinct_spec(tokens[i + 1])
                    d_args = [repr(c) for c in d_cols]
                    if d_keep and d_keep != "first":
                        d_args.append(f"keep={repr(d_keep)}")
                    calls.append(f".distinct({', '.join(d_args)})")
                except Exception:
                    calls.append(".distinct()")
                i += 2
            else:
                calls.append(".distinct()")
                i += 1
            continue

        # -dropna [spec]
        if low in ("-dropna", "--dropna"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                from pytae.cli_parsing import parse_dropna_spec

                try:
                    dr_cols, dr_how, _ = parse_dropna_spec(tokens[i + 1])
                    dr_args = [repr(c) for c in dr_cols]
                    if dr_how:
                        dr_args.append(f"how={repr(dr_how)}")
                    calls.append(f".dropna({', '.join(dr_args)})")
                except Exception:
                    calls.append(".dropna()")
                i += 2
            else:
                calls.append(".dropna()")
                i += 1
            continue

        # -fillna <val>
        if low in ("-fillna", "--fillna") and i + 1 < n:
            calls.append(f".fillna({repr(tokens[i + 1])})")
            i += 2
            continue

        # -head [N]
        if low in ("-head", "--head"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".head({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".head(10)")
                i += 1
            continue

        # -tail [N]
        if low in ("-tail", "--tail"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".tail({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".tail(10)")
                i += 1
            continue

        # -sample [N]
        if low in ("-sample", "--sample"):
            if i + 1 < n and tokens[i + 1].isdigit():
                calls.append(f".sample({int(tokens[i + 1])})")
                i += 2
            else:
                calls.append(".sample(5)")
                i += 1
            continue

        # -join <other> [on=<key>|-on <key>] [how=<how>|-how <how>] [left_on=...] [right_on=...] ...
        if low in ("-join", "--join") and i + 1 < n:
            other_tbl = tokens[i + 1]
            on_key = None
            left_on = None
            right_on = None
            how = "inner"
            validate = None
            fuzzy = None
            score = None
            suffix = None
            j = i + 2
            while j < n:
                arg = tokens[j]
                arg_low = arg.lower()
                if arg_low in ("-on", "--on") and j + 1 < n:
                    on_key = tokens[j + 1].strip("\"'")
                    j += 2
                elif arg_low.startswith("on="):
                    on_key = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low in ("-left_on", "--left_on") and j + 1 < n:
                    left_on = tokens[j + 1].strip("\"'")
                    j += 2
                elif arg_low.startswith("left_on="):
                    left_on = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low in ("-right_on", "--right_on") and j + 1 < n:
                    right_on = tokens[j + 1].strip("\"'")
                    j += 2
                elif arg_low.startswith("right_on="):
                    right_on = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low in ("-how", "--how") and j + 1 < n:
                    how = tokens[j + 1].strip("\"'")
                    j += 2
                elif arg_low.startswith("how="):
                    how = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low.startswith("validate="):
                    validate = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low.startswith("fuzzy="):
                    fuzzy = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low.startswith("score="):
                    score = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif arg_low.startswith("suffix="):
                    suffix = arg.split("=", 1)[1].strip("\"'")
                    j += 1
                elif not arg.startswith("-"):
                    j += 1
                else:
                    break

            join_args = [other_tbl]
            if on_key:
                join_args.append(f"on={repr(on_key)}")
            if left_on:
                join_args.append(f"left_on={repr(left_on)}")
            if right_on:
                join_args.append(f"right_on={repr(right_on)}")
            join_args.append(f"how={repr(how)}")
            if validate:
                join_args.append(f"validate={repr(validate)}")
            if fuzzy is not None:
                try:
                    join_args.append(f"fuzzy={float(fuzzy)}")
                except ValueError:
                    join_args.append(f"fuzzy={repr(fuzzy)}")
            if score is not None:
                join_args.append(f"score={repr(score)}")
            if suffix:
                join_args.append(f"suffix={repr(suffix)}")

            calls.append(f".join({', '.join(join_args)})")
            i = j
            continue

        # -concat [spec]
        if low in ("-concat", "--concat"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                c_val = tokens[i + 1]
                if c_val.lower().startswith("frames="):
                    c_val = c_val.split("=", 1)[1]
                c_parts = [c.strip().strip("\"'") for c in c_val.split(",") if c.strip().strip("\"'")]
                if c_parts:
                    calls.append(f".concat({', '.join(c_parts)})")
                else:
                    calls.append(".concat()")
                i += 2
            else:
                calls.append(".concat()")
                i += 1
            continue

        # -collect
        if low in ("-collect", "--collect"):
            calls.append(".collect()")
            i += 1
            continue

        # -pivot <spec>
        if low in ("-pivot", "--pivot") and i + 1 < n:
            from pytae.cli_parsing import parse_pivot_arg

            pspec = parse_pivot_arg(tokens[i + 1])
            p_args: list[str] = []
            if pspec.get("r") is not None:
                p_args.append(f"r={repr(pspec['r'])}")
            if pspec.get("c") is not None:
                p_args.append(f"c={repr(pspec['c'])}")
            if pspec.get("v") is not None:
                p_args.append(f"v={repr(pspec['v'])}")
            if pspec.get("a") is not None and pspec["a"] != "sum":
                p_args.append(f"a={repr(pspec['a'])}")
            calls.append(f".pivot({', '.join(p_args)})")
            i += 2
            continue

        # -long [spec]
        if low in ("-long", "--long"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                from pytae.cli_parsing import parse_long_arg

                lspec = parse_long_arg(tokens[i + 1])
                l_args: list[str] = []
                if lspec.get("cols") is not None:
                    l_args.append(f"cols={repr(lspec['cols'])}")
                if lspec.get("id_vars") is not None:
                    l_args.append(f"id_vars={repr(lspec['id_vars'])}")
                if lspec.get("c") is not None and lspec["c"] != "variable":
                    l_args.append(f"c={repr(lspec['c'])}")
                if lspec.get("v") is not None and lspec["v"] != "value":
                    l_args.append(f"v={repr(lspec['v'])}")
                calls.append(f".long({', '.join(l_args)})")
                i += 2
            else:
                calls.append(".long()")
                i += 1
            continue

        # -wide [spec]
        if low in ("-wide", "--wide"):
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                from pytae.cli_parsing import parse_wide_arg

                wspec = parse_wide_arg(tokens[i + 1])
                w_args: list[str] = []
                if wspec.get("r") is not None:
                    w_args.append(f"r={repr(wspec['r'])}")
                if wspec.get("c") is not None and wspec["c"] != "variable":
                    w_args.append(f"c={repr(wspec['c'])}")
                if wspec.get("v") is not None and wspec["v"] != "value":
                    w_args.append(f"v={repr(wspec['v'])}")
                calls.append(f".wide({', '.join(w_args)})")
                i += 2
            else:
                calls.append(".wide()")
                i += 1
            continue

        # -assert <expr>
        if low in ("-assert", "--assert") and i + 1 < n:
            calls.append(f".assert_({repr(tokens[i + 1])})")
            i += 2
            continue

        # -explode <cols>
        if low in ("-explode", "--explode") and i + 1 < n:
            cols_val = tokens[i + 1]
            col_parts = [c.strip() for c in cols_val.split(",") if c.strip()]
            formatted_cols = ", ".join(repr(c) for c in col_parts)
            calls.append(f".explode({formatted_cols})")
            i += 2
            continue

        # -mask <spec>
        if low in ("-mask", "--mask") and i + 1 < n:
            calls.append(f".mask({repr(tokens[i + 1])})")
            i += 2
            continue

        # -unmask <cols>
        if low in ("-unmask", "--unmask") and i + 1 < n:
            calls.append(f".unmask({repr(tokens[i + 1])})")
            i += 2
            continue

        # -o <dest>
        if low == "-o" and i + 1 < n:
            dest = tokens[i + 1].strip("\"'")
            calls.append(f".to({repr(dest)})")
            i += 2
            continue

        # Advance if unknown or unhandled flag
        i += 1

    return "".join(calls)


def _prune_rolled_back_entries(entries: list[str]) -> list[str]:
    """Prune commands that were rolled back between 'checkpoint <name>' and 'restore <name>'."""
    cp_indices: dict[str, int] = {}
    result: list[str] = []
    for entry in entries:
        clean = entry.strip()
        if clean.startswith("checkpoint "):
            toks = clean.split()
            if len(toks) >= 2:
                cp_name = toks[1].strip("\"'")
                cp_indices[cp_name] = len(result)
            continue
        elif clean.startswith("restore "):
            toks = clean.split()
            if len(toks) >= 2:
                cp_name = toks[1].strip("\"'")
                if cp_name in cp_indices:
                    idx = cp_indices[cp_name]
                    result = result[:idx]
                    continue
            continue
        result.append(entry)
    return result


def _extract_entry_def_and_uses(entry: str) -> tuple[set[str], set[str], bool, bool]:
    """Analyze a replayable entry to determine its definitions, usages, side-effects, and barriers.

    Returns:
        (defs, uses, has_side_effect, is_barrier)
    """
    clean = _normalize_unquoted_windows_paths(entry.strip())
    if not clean or clean.startswith("#"):
        return set(), set(), False, False

    # 1. Python blocks: opaque barrier with potential side effects
    if clean.startswith("py"):
        return set(), set(), True, True

    # 2. History / Session barriers and explicit resets
    if clean.startswith(("reset", "restore ", "checkpoint ", "rm table ", "rename ", "switch ")):
        toks = clean.split()
        if len(toks) >= 3 and toks[0] == "rename":
            return {toks[2]}, {toks[1]}, False, True
        return set(), set(), True, True

    toks = clean.split()
    has_side_effect = False
    uses: set[str] = set()
    defs: set[str] = set()

    # 3. Output commands: <tbl> -o <path>, export <path>, save <path>
    for i, t in enumerate(toks):
        if t in ("-o", "-output", "--output") and i + 1 < len(toks):
            has_side_effect = True
            src = toks[0] if i > 0 else "df"
            if src.isidentifier():
                uses.add(src)
        elif t.startswith(("-o=", "-output=", "--output=")):
            has_side_effect = True
            src = toks[0] if i > 0 else "df"
            if src.isidentifier():
                uses.add(src)

    if toks and toks[0] in ("export", "save", "-export", "-save"):
        has_side_effect = True
        uses.add("df")

    # 4. Ingestion commands: load <path> [as <alias>] or scan <path> [as <alias>]
    if toks and toks[0] in ("load", "scan"):
        alias = "df"
        if len(toks) >= 4 and toks[2].lower() == "as":
            alias = toks[3]
        elif len(toks) >= 2:
            p = toks[1].strip("'\"")
            stem = Path(p).stem
            alias = stem if stem.isidentifier() else "df"
        defs.add(alias)
        return defs, uses, has_side_effect, False

    # 5. Variable assignments: target = expr
    if "=" in clean and not clean.startswith("-"):
        parts = clean.split("=", 1)
        left = parts[0].strip()
        right = parts[1].strip()
        if left.isidentifier():
            defs.add(left)
            # Find uses on the right side:
            if re.match(r"^(?:sql\s*\{|-sql|--sql)\b", right, re.IGNORECASE):
                words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", right))
                sql_keywords = {
                    "select", "from", "where", "join", "inner", "left", "right", "outer",
                    "full", "cross", "on", "group", "by", "order", "having", "limit",
                    "as", "and", "or", "not", "distinct", "union", "all", "case", "when",
                    "then", "else", "end", "is", "null", "in", "like", "ilike", "between",
                    "sql", "insert", "into", "update", "delete", "create", "table", "drop",
                    "view", "with", "true", "false",
                }
                for w in words:
                    if w.lower() not in sql_keywords and w != left:
                        uses.add(w)
            else:
                # If right-hand side starts with a pipeline flag (e.g. df = -filter ... or df = -mutate ...),
                # it is an in-place pipeline transformation of the target table (and default 'df')
                if right.startswith("-"):
                    uses.add(left)
                    uses.add("df")

                try:
                    r_toks = shlex.split(right)
                except Exception:
                    r_toks = right.split()

                if r_toks:
                    first = r_toks[0].strip("'\"")
                    is_path_or_literal = (
                        first.startswith("-")
                        or "." in first
                        or "/" in first
                        or "\\" in first
                        or first.lower() in ("clip", "clipboard")
                        or first.startswith("sample:")
                        or first in ("load", "scan")
                    )
                    if not is_path_or_literal and first.isidentifier():
                        uses.add(first)

                    for idx_t, tok in enumerate(r_toks):
                        if tok in ("-join", "--join", "-concat", "--concat") and idx_t + 1 < len(r_toks):
                            next_tok = r_toks[idx_t + 1].strip("'\"")
                            for candidate in next_tok.split(","):
                                cand = candidate.strip()
                                if cand.isidentifier():
                                    uses.add(cand)
                        if tok in ("-o", "-output", "--output") and idx_t + 1 < len(r_toks):
                            has_side_effect = True
                        elif tok.startswith(("-o=", "-output=", "--output=")):
                            has_side_effect = True

                    # Check if left variable is referenced on RHS (e.g. df = df -head)
                    if re.search(r"\b" + re.escape(left) + r"\b", right):
                        uses.add(left)

            return defs, uses, has_side_effect, False

    # 6. Direct SQL statement: sql { ... } (non-destructive preview) or legacy -sql
    if clean.startswith(("-sql", "--sql")) or clean.lower().startswith(("sql {", "sql{")):
        words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", clean))
        return defs, words, False, False

    # 7. Bare table action or collect: e.g. tbl -collect
    if toks and toks[0].isidentifier():
        uses.add(toks[0])

    return defs, uses, has_side_effect, False


def _prune_dead_assignments(entries: list[str]) -> list[str]:
    """Prune non-side-effecting variable assignments that are overwritten before being read.

    Eliminates redundant or superseded definitions (e.g., consecutive 'df = test.csv'
    or scratchpad re-reads) while faithfully preserving repeated computations in sequential
    pipelines where intermediate values are read or exported (e.g. batch loops with '-o').
    """
    entries = [_normalize_unquoted_windows_paths(e) for e in entries]
    analyzed = [_extract_entry_def_and_uses(e) for e in entries]
    n = len(entries)
    keep = [True] * n

    for i in range(n):
        defs_i, uses_i, side_i, barrier_i = analyzed[i]
        if barrier_i or side_i or not defs_i:
            continue

        all_dead = True
        for target in defs_i:
            target_is_dead = False
            for j in range(i + 1, n):
                defs_j, uses_j, side_j, barrier_j = analyzed[j]

                # If j reads target, then definition i was used!
                if target in uses_j:
                    target_is_dead = False
                    break

                # If j is an opaque barrier, we cannot prune across it
                if barrier_j:
                    target_is_dead = False
                    break

                # If j redefines target without reading it:
                if target in defs_j:
                    target_is_dead = True
                    break

            if not target_is_dead:
                all_dead = False
                break

        if all_dead:
            keep[i] = False

    return [entries[i] for i in range(n) if keep[i]]


def _compile_history_to_python(
    entries: list[str],
    table_sources: dict[str, str] | None = None,
    *,
    relative: bool = False,
    prune_dead: bool = True,
) -> str:
    """Compile replayable REPL history into a standalone, executable Python script."""
    entries = [_normalize_unquoted_windows_paths(e) for e in entries]
    entries = _prune_rolled_back_entries(entries)
    if prune_dead:
        entries = _prune_dead_assignments(entries)

    lines: list[str] = [
        '"""Auto-generated standalone Python pipeline script from pytae REPL session."""',
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "import pandas as pd",
        "import polars as pl",
        "import pytae as pt",
        "from pytae import c",
        "",
    ]

    known_tables: set[str] = set()
    seen_imports: set[tuple[Any, ...]] = {
        ("import", "pandas", "pd"),
        ("import", "polars", "pl"),
        ("import", "pytae", "pt"),
        ("from", "pytae", 0, "c", None),
    }

    if table_sources:
        initially_defined: set[str] = set()
        for e in entries:
            c = e.strip()
            if c.startswith(("load ", "scan ")):
                toks = c.split()
                if len(toks) >= 4 and toks[2].lower() == "as":
                    initially_defined.add(toks[3])
                elif len(toks) >= 2:
                    p_stem = Path(toks[1].strip("\"'")).stem
                    initially_defined.add(p_stem if p_stem.isidentifier() else "df")
            elif "=" in c and not c.startswith("-"):
                tgt = c.split("=", 1)[0].strip()
                rhs = c.split("=", 1)[1].strip()
                if tgt.isidentifier() and not rhs.startswith("-"):
                    initially_defined.add(tgt)
            elif c.startswith("py"):
                py_c = c[2:].strip().strip("{}")
                try:
                    tree_c = ast.parse(py_c)
                    for node in ast.walk(tree_c):
                        if isinstance(node, ast.Assign):
                            for target_node in node.targets:
                                if isinstance(target_node, ast.Name):
                                    initially_defined.add(target_node.id)
                except Exception:
                    pass

        valid_exts = {
            ".parquet", ".csv", ".tsv", ".txt", ".json", ".jsonl", ".ndjson",
            ".ipc", ".arrow", ".feather", ".dat", ".xlsx", ".sas7bdat",
        }
        for t_name, t_src in table_sources.items():
            var_name = (
                t_name
                if t_name.isidentifier()
                else (Path(t_name).stem if Path(t_name).stem.isidentifier() else "df")
            )
            if (
                var_name not in initially_defined
                and var_name not in known_tables
                and t_src
                and t_src not in ("<memory>", "python")
                and not t_src.startswith("sql:")
                and (Path(t_src).suffix.lower() in valid_exts or Path(t_src).exists())
            ):
                in_src = _to_relative_path(t_src) if relative else t_src
                lines.append(f"{var_name} = pt.read({repr(in_src)})")
                known_tables.add(var_name)

        if "df" not in known_tables and "df" not in initially_defined:
            uses_df = any(
                "df" in _extract_entry_def_and_uses(e)[1]
                or e.strip().startswith(("df ", "df=", "df ="))
                or (e.strip().startswith("-") or ("=" in e and e.split("=", 1)[1].strip().startswith("-")))
                for e in entries
            )
            if uses_df and known_tables:
                first_tbl = next(iter(sorted(known_tables)))
                lines.append(f"df = {first_tbl}")
                known_tables.add("df")

    def _compile_sql_assignment(target_var: str, query_text: str) -> str:
        sql_words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", query_text)
        ref_tables: list[str] = []
        seen_t: set[str] = set()
        for w in sql_words:
            if w in known_tables and w not in seen_t:
                seen_t.add(w)
                ref_tables.append(w)
        if not ref_tables and "df" in known_tables:
            ref_tables.append("df")
        if not ref_tables and known_tables:
            ref_tables.extend(sorted(known_tables))
        q_lit = f'"""\n{query_text}\n"""' if ("\n" in query_text and '"""' not in query_text) else repr(query_text)
        if ref_tables:
            frames_str = ", ".join(f"{repr(t)}: {t}" for t in ref_tables)
            return f"{target_var} = pt.sql({{{frames_str}}}, {q_lit})"
        return f"{target_var} = pt.sql(df, {q_lit})"

    for raw_entry in entries:
        clean = raw_entry.strip()
        if not clean or clean.startswith("#"):
            continue

        # 1. Python blocks: emit Python code directly
        if clean.startswith("py"):
            py_body = clean[2:].strip()
            if py_body.endswith("\npy"):
                py_body = py_body[:-3].strip()
            elif py_body.endswith(" py"):
                py_body = py_body[:-3].strip()
            if py_body.startswith("{") and py_body.endswith("}"):
                import textwrap

                py_body = textwrap.dedent(py_body[1:-1]).strip()
            if py_body:
                try:
                    py_tree = ast.parse(py_body)
                    py_lines = py_body.splitlines()
                    line_replacements: dict[int, tuple[int, list[str]]] = {}
                    for stmt in py_tree.body:
                        if isinstance(stmt, ast.Import):
                            new_parts: list[str] = []
                            for alias in stmt.names:
                                key = ("import", alias.name, alias.asname)
                                if key not in seen_imports:
                                    seen_imports.add(key)
                                    new_parts.append(
                                        f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                                    )
                            if len(new_parts) < len(stmt.names):
                                start_idx = stmt.lineno - 1
                                end_idx = (stmt.end_lineno or stmt.lineno) - 1
                                line_replacements[start_idx] = (
                                    end_idx,
                                    [f"import {', '.join(new_parts)}"] if new_parts else [],
                                )
                            continue
                        if isinstance(stmt, ast.ImportFrom):
                            new_parts = []
                            for alias in stmt.names:
                                key = ("from", stmt.module or "", stmt.level, alias.name, alias.asname)
                                if key not in seen_imports:
                                    seen_imports.add(key)
                                    new_parts.append(
                                        f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                                    )
                            if len(new_parts) < len(stmt.names):
                                start_idx = stmt.lineno - 1
                                end_idx = (stmt.end_lineno or stmt.lineno) - 1
                                dots = "." * stmt.level
                                mod = stmt.module or ""
                                line_replacements[start_idx] = (
                                    end_idx,
                                    [f"from {dots}{mod} import {', '.join(new_parts)}"] if new_parts else [],
                                )
                            continue
                        targets = []
                        if isinstance(stmt, ast.Assign):
                            targets = stmt.targets
                        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
                            targets = [stmt.target]
                        elif isinstance(stmt, ast.Delete):
                            targets = stmt.targets
                        for tgt in targets:
                            if isinstance(tgt, ast.Name):
                                if not isinstance(stmt, ast.Delete):
                                    known_tables.add(tgt.id)
                                seen_imports = {
                                    imp
                                    for imp in seen_imports
                                    if (
                                        (imp[2] or imp[1].split(".")[0])
                                        if imp[0] == "import"
                                        else (imp[4] or imp[3] if len(imp) >= 5 else imp[-1])
                                    )
                                    != tgt.id
                                }
                    if line_replacements:
                        rebuilt: list[str] = []
                        idx = 0
                        while idx < len(py_lines):
                            if idx in line_replacements:
                                end_idx, repl = line_replacements[idx]
                                rebuilt.extend(repl)
                                idx = end_idx + 1
                            else:
                                rebuilt.append(py_lines[idx])
                                idx += 1
                        py_body = "\n".join(rebuilt).strip()
                except SyntaxError:
                    pass
                if py_body:
                    lines.append("# Custom Python transformation")
                    lines.append(py_body)
                    lines.append("")
            continue

        # 2. Ingestion: `load <path> as <alias>` or `load <path>`
        if clean.startswith("load "):
            toks = clean.split()
            if len(toks) >= 4 and toks[2].lower() == "as":
                alias = toks[3]
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                if path.lower() in ("clip", "clipboard"):
                    lines.append(f"{alias} = pl.from_pandas(pd.read_clipboard())")
                else:
                    lines.append(f"{alias} = pt.read({repr(in_path)})")
                known_tables.add(alias)
            elif len(toks) >= 2:
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                if path.lower() in ("clip", "clipboard"):
                    lines.append("df = pl.from_pandas(pd.read_clipboard())")
                    known_tables.add("df")
                else:
                    alias = Path(path).stem or "df"
                    lines.append(f"{alias} = pt.read({repr(in_path)})")
                    known_tables.add(alias)
            continue

        # 2b. Lazy scan: `scan <path> as <alias>` or `scan <path>`
        if clean.startswith("scan "):
            toks = shlex.split(clean)
            scan_extra = ""
            for idx_p, sp in enumerate(toks[1:]):
                if sp in ("-dlim", "--dlim", "-sep", "--sep") and idx_p + 1 < len(toks[1:]):
                    scan_extra = f", separator={repr(toks[1:][idx_p + 1])}"
            if len(toks) >= 4 and toks[2].lower() == "as":
                alias = toks[3]
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                suf = Path(path).suffix.lower()
                scan_fn = (
                    "scan_csv"
                    if suf in (".csv", ".tsv", ".txt")
                    else (
                        "scan_ipc"
                        if suf in (".ipc", ".arrow", ".feather")
                        else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                    )
                )
                lines.append(f"{alias} = pl.{scan_fn}({repr(in_path)}{scan_extra})")
                known_tables.add(alias)
            elif len(toks) >= 2:
                path = toks[1].strip("\"'")
                in_path = _to_relative_path(path) if relative else path
                alias = Path(path).stem or "df"
                suf = Path(path).suffix.lower()
                scan_fn = (
                    "scan_csv"
                    if suf in (".csv", ".tsv", ".txt")
                    else (
                        "scan_ipc"
                        if suf in (".ipc", ".arrow", ".feather")
                        else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                    )
                )
                lines.append(f"{alias} = pl.{scan_fn}({repr(in_path)}{scan_extra})")
                known_tables.add(alias)
            continue

        # 3. Assignments: `<target> = <expression>`
        if "=" in clean and not clean.startswith("-"):
            target, expr = [p.strip() for p in clean.split("=", 1)]
            if target.isidentifier():
                if expr.startswith("scan "):
                    scan_tail = expr[5:].strip()
                    scan_parts = shlex.split(scan_tail)
                    raw_sp = scan_parts[0].strip("\"'") if scan_parts else ""
                    in_sp = _to_relative_path(raw_sp) if relative else raw_sp
                    suf = Path(raw_sp).suffix.lower()
                    scan_fn = (
                        "scan_csv"
                        if suf in (".csv", ".tsv", ".txt")
                        else (
                            "scan_ipc"
                            if suf in (".ipc", ".arrow", ".feather")
                            else ("scan_ndjson" if suf in (".ndjson", ".jsonl") else "scan_parquet")
                        )
                    )
                    scan_extra = ""
                    for idx_p, sp in enumerate(scan_parts[1:]):
                        if sp in ("-dlim", "--dlim", "-sep", "--sep") and idx_p + 1 < len(scan_parts[1:]):
                            scan_extra = f", separator={repr(scan_parts[1:][idx_p + 1])}"
                    lines.append(f"{target} = pl.{scan_fn}({repr(in_sp)}{scan_extra})")
                    known_tables.add(target)
                    continue
                if re.match(r"^sql\s*\{", expr, re.IGNORECASE):
                    import textwrap

                    raw_sql = expr[expr.index("{") + 1 :]
                    if raw_sql.endswith("}"):
                        raw_sql = raw_sql[:-1]
                    q = textwrap.dedent(raw_sql).strip()
                    lines.append(_compile_sql_assignment(target, q))
                    known_tables.add(target)
                    continue
                if expr.startswith(("-sql", "--sql")):
                    q = expr.split(None, 1)[1].strip().strip("\"'") if len(expr.split(None, 1)) > 1 else ""
                    lines.append(_compile_sql_assignment(target, q))
                    known_tables.add(target)
                    continue
                toks = shlex.split(expr)
                if toks and toks[0].lower() in ("clip", "clipboard"):
                    clip_code = "pl.from_pandas(pd.read_clipboard())"
                    for idx_tok, tok in enumerate(toks):
                        if tok in ("-nrows", "--nrows", "-limit", "--limit") and idx_tok + 1 < len(toks):
                            try:
                                clip_code += f".head({int(toks[idx_tok + 1])})"
                            except ValueError:
                                pass
                    lines.append(f"{target} = {clip_code}")
                    known_tables.add(target)
                    continue
                if expr.startswith("sample:"):
                    s_name = expr.split(":", 1)[1].strip()
                    lines.append(f"{target} = pt.sample({repr(s_name)})")
                    known_tables.add(target)
                    continue
                if expr.startswith("load "):
                    load_tail = expr[5:].strip()
                    try:
                        load_toks = shlex.split(load_tail)
                    except Exception:
                        load_toks = load_tail.split()
                    if load_toks:
                        p = load_toks[0].strip("\"'")
                        in_p = _to_relative_path(p) if relative else p
                        if p.lower() in ("clip", "clipboard"):
                            src_code = "pl.from_pandas(pd.read_clipboard())"
                        else:
                            src_code = f"pt.read({repr(in_p)})"
                        chain = _transpile_pipeline_tokens_to_python(load_toks[1:])
                        lines.append(f"{target} = {src_code}{chain}")
                        known_tables.add(target)
                        continue

                if expr.startswith("-"):
                    src_code = target if target in known_tables else "df"
                    chain = _transpile_pipeline_tokens_to_python(toks)
                    lines.append(f"{target} = {src_code}{chain}")
                    known_tables.add(target)
                    continue

                cleaned_src_tokens, src_reader_kwargs, src_nrows = _parse_reader_options(toks)
                if cleaned_src_tokens:
                    src_token = cleaned_src_tokens[0]
                    if src_token.startswith("-"):
                        src_code = target if target in known_tables else "df"
                        pipe_toks = cleaned_src_tokens
                    elif "." in src_token or "/" in src_token or "\\" in src_token:
                        raw_src = src_token.strip("\"'")
                        in_src = _to_relative_path(raw_src) if relative else raw_src
                        opts_call = []
                        if src_reader_kwargs:
                            for k, v in src_reader_kwargs.items():
                                if k == "separator":
                                    opts_call.append(f"separator={repr(v)}")
                                elif k == "encoding":
                                    opts_call.append(f"encoding={repr(v)}")
                                else:
                                    opts_call.append(f"{k}={repr(v)}")
                        if src_nrows is not None:
                            opts_call.append(f"nrows={src_nrows}")
                        extra_args = f", {', '.join(opts_call)}" if opts_call else ""
                        src_code = f"pt.read({repr(in_src)}{extra_args})"
                        pipe_toks = cleaned_src_tokens[1:]
                    else:
                        src_code = src_token
                        pipe_toks = toks[1:]
                    chain = _transpile_pipeline_tokens_to_python(pipe_toks)
                    lines.append(f"{target} = {src_code}{chain}")
                    known_tables.add(target)
                    continue

        # 5. Exploratory bare SQL preview: skip or comment in script
        if clean.lower().startswith(("sql {", "sql{")):
            continue
        if clean.startswith(("-sql", "--sql")):
            parts = clean.split(None, 1)
            q = parts[1].strip().strip("\"'") if len(parts) > 1 else ""
            lines.append(_compile_sql_assignment("res", q))
            continue

        # 6. Output commands: `<tbl> -o <path>` or `export <path>`
        try:
            toks = shlex.split(clean)
        except Exception:
            toks = clean.split()

        if toks and toks[0] in ("export", "save"):
            dest = toks[1].strip("\"'") if len(toks) >= 2 else "out"
            if dest.lower() in ("clip", "clipboard"):
                lines.append("df.to('clip')")
            else:
                lines.append(f"df.to({repr(dest)})")
            continue

        has_output_flag = any(
            t in ("-o", "-output", "--output") or t.startswith(("-o=", "-output=", "--output=")) for t in toks
        )
        if has_output_flag and toks:
            if toks[0].startswith("-"):
                src_code = "df"
                pipe_toks = toks
            elif "." in toks[0] or "/" in toks[0] or "\\" in toks[0]:
                raw_src = toks[0].strip("\"'")
                in_src = _to_relative_path(raw_src) if relative else raw_src
                src_code = f"pt.read({repr(in_src)})"
                pipe_toks = toks[1:]
            else:
                src_code = toks[0]
                pipe_toks = toks[1:]
            chain = _transpile_pipeline_tokens_to_python(pipe_toks)
            lines.append(f"{src_code}{chain}")
            continue

    code_str = "\n".join(lines) + "\n"
    try:
        ast.parse(code_str)
    except SyntaxError:
        pass
    return code_str


def _compile_history_to_pt(
    entries: list[str],
    filename: str = "pipeline.pt",
    table_sources: dict[str, str] | None = None,
    *,
    relative: bool = False,
    prune_dead: bool = True,
) -> str:
    """Compile replayable REPL history into a clean, replayable Pytae script."""
    entries = [_normalize_unquoted_windows_paths(e) for e in entries]
    entries = _prune_rolled_back_entries(entries)
    if prune_dead:
        entries = _prune_dead_assignments(entries)

    lines: list[str] = [
        f"# Pytae Script: {filename}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if table_sources:
        initially_defined: set[str] = set()
        for e in entries:
            c = e.strip()
            if c.startswith(("load ", "scan ")):
                toks = c.split()
                if len(toks) >= 4 and toks[2].lower() == "as":
                    initially_defined.add(toks[3])
                elif len(toks) >= 2:
                    p_stem = Path(toks[1].strip("\"'")).stem
                    initially_defined.add(p_stem if p_stem.isidentifier() else "df")
            elif "=" in c and not c.startswith("-"):
                tgt = c.split("=", 1)[0].strip()
                rhs = c.split("=", 1)[1].strip()
                if tgt.isidentifier() and not rhs.startswith("-"):
                    initially_defined.add(tgt)
            elif c.startswith("py"):
                py_c = c[2:].strip().strip("{}")
                try:
                    tree_c = ast.parse(py_c)
                    for node in ast.walk(tree_c):
                        if isinstance(node, ast.Assign):
                            for target_node in node.targets:
                                if isinstance(target_node, ast.Name):
                                    initially_defined.add(target_node.id)
                except Exception:
                    pass

        valid_exts = {
            ".parquet", ".csv", ".tsv", ".txt", ".json", ".jsonl", ".ndjson",
            ".ipc", ".arrow", ".feather", ".dat", ".xlsx", ".sas7bdat",
        }
        seen_preloaded: set[str] = set()
        for t_name, t_src in table_sources.items():
            var_name = (
                t_name
                if t_name.isidentifier()
                else (Path(t_name).stem if Path(t_name).stem.isidentifier() else "df")
            )
            if (
                var_name not in initially_defined
                and var_name not in seen_preloaded
                and t_src
                and t_src not in ("<memory>", "python")
                and not t_src.startswith("sql:")
                and (Path(t_src).suffix.lower() in valid_exts or Path(t_src).exists())
            ):
                rel_src = _to_relative_path(t_src) if relative else t_src
                if var_name == "df":
                    lines.append(f"load {rel_src}")
                else:
                    lines.append(f"load {rel_src} as {var_name}")
                seen_preloaded.add(var_name)

        if "df" not in seen_preloaded and "df" not in initially_defined:
            uses_df = any(
                "df" in _extract_entry_def_and_uses(e)[1]
                or e.strip().startswith(("df ", "df=", "df ="))
                or (e.strip().startswith("-") or ("=" in e and e.split("=", 1)[1].strip().startswith("-")))
                for e in entries
            )
            if uses_df and seen_preloaded:
                first_tbl = next(iter(sorted(seen_preloaded)))
                lines.append(f"df = {first_tbl}")
                seen_preloaded.add("df")

    for raw_entry in entries:
        clean = raw_entry.strip()
        if not clean or clean.startswith("#"):
            continue
        if relative:
            if clean.startswith("load "):
                toks = shlex.split(clean)
                if len(toks) >= 2:
                    rel_p = _to_relative_path(toks[1])
                    if len(toks) >= 4 and toks[2].lower() == "as":
                        lines.append(f"load {rel_p} as {toks[3]}")
                    else:
                        lines.append(f"load {rel_p}")
                    continue
            elif clean.startswith("scan "):
                toks = shlex.split(clean)
                if len(toks) >= 2:
                    rel_p = _to_relative_path(toks[1])
                    if len(toks) >= 4 and toks[2].lower() == "as":
                        lines.append(f"scan {rel_p} as {toks[3]}")
                    else:
                        lines.append(f"scan {rel_p}")
                    continue
            elif "=" in clean and not clean.startswith("-"):
                target, expr = [p.strip() for p in clean.split("=", 1)]
                if target.isidentifier():
                    if expr.startswith("load "):
                        raw_lp = expr[5:].strip().strip("\"'")
                        rel_lp = _to_relative_path(raw_lp)
                        lines.append(f"{target} = load {rel_lp}")
                        continue
                    if expr.startswith(("scan ", "scan:")):
                        raw_sp = expr[4:].lstrip(": ").strip().strip("\"'")
                        rel_sp = _to_relative_path(raw_sp)
                        lines.append(f"{target} = scan {rel_sp}")
                        continue
                    toks = shlex.split(expr)
                    if toks and ("." in toks[0] or "/" in toks[0] or "\\" in toks[0]):
                        raw_src = toks[0].strip("\"'")
                        rel_src = _to_relative_path(raw_src)
                        rem = expr[len(toks[0]) :].strip()
                        lines.append(f"{target} = {rel_src} {rem}".strip())
                        continue
        lines.append(clean)

    return "\n".join(lines) + "\n"


def _is_replayable_entry_static(entry: str) -> bool:
    """Determine if a history entry is a state-mutating transformation or artifact export.

    Exploratory previews (bare -pivot, -head, -describe, inspection, etc.) and session
    comments are excluded from exported replay scripts.
    """
    clean = _normalize_unquoted_windows_paths(entry.strip())
    if not clean or clean.startswith("#"):
        return False
    if clean.startswith("*checkpoint:") and clean.endswith("*"):
        return False
    if clean.startswith(("checkpoint ", "restore ")):
        return False
    if clean.startswith("history") or clean in ("tables", "checkpoints", "session", "sessions", "status", "clear", "help"):
        return False
    if clean.startswith("status "):
        return False

    # Script export commands themselves are excluded from exported replay scripts
    if clean.startswith(("export script", "export code", "save script", "save code", "-export script", "-save script")):
        return False

    # Python snippets: replayable when mutating state (assignments, definitions)
    # or defining reusable imports/functions/classes (while skipping pure inspections).
    if re.match(r"^py(?:\s|\{|$)", clean):
        py_body = clean[2:].strip()
        if py_body.endswith("\npy"):
            py_body = py_body[:-3].strip()
        elif py_body.endswith(" py"):
            py_body = py_body[:-3].strip()
        if py_body.startswith("{") and py_body.endswith("}"):
            py_body = textwrap.dedent(py_body[1:-1]).strip()
        if not py_body:
            return False

        try:
            tree = ast.parse(py_body)
        except SyntaxError:
            return False
        mutating_nodes = (
            ast.Assign,
            ast.AnnAssign,
            ast.AugAssign,
            ast.Import,
            ast.ImportFrom,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Delete,
            ast.Global,
            ast.Nonlocal,
        )
        return any(isinstance(node, mutating_nodes) for node in ast.walk(tree))

    # Session configuration commands ('set ...') are excluded from exported scripts
    if clean == "set" or clean.startswith("set ") or clean.startswith("set="):
        return False

    # Variable assignments (df = ..., df1 = df -pivot ..., etc.) are state mutations
    if "=" in clean and not clean.startswith("-"):
        left_part = clean.split("=", 1)[0].strip()
        if left_part.isidentifier():
            return True

    # Ingestion commands: load <path> [as <alias>] or scan <path> [as <alias>]
    if clean.startswith(("load ", "scan ")):
        return True

    # Export commands: export <path>, save <path>
    if clean.startswith(("export ", "save ", "-export ", "-save ")):
        tokens = clean.split()
        if len(tokens) >= 2:
            target = tokens[1].lower().strip("'\"")
            if target not in ("clip", "clipboard", "script", "code"):
                if target.endswith((".pt", ".py")):
                    return False
                return True
        return False

    tokens = clean.split()
    for i, t in enumerate(tokens):
        if t == "-o" and i + 1 < len(tokens):
            target = tokens[i + 1].lower().strip("'\"")
            if target in ("clip", "clipboard"):
                continue
            return True
        if t.startswith("-o="):
            target = t.split("=", 1)[1].lower().strip("'\"")
            if target in ("clip", "clipboard"):
                continue
            return True

    # Bare SQL statements: sql { ... } are non-destructive previews (not replayable state changes)
    if clean.lower().startswith(("sql {", "sql{", "sql ")) or clean.lower() == "sql":
        return False
    if clean.startswith(("-sql", "--sql")):
        return True

    # Explicit reset / restore / table removal or mutation of state
    if clean.startswith("reset") or clean.startswith("restore "):
        return True
    if clean.startswith("rm table ") or clean == "rm table *":
        return True
    if clean.startswith("rename ") or clean.startswith("switch "):
        return True
    if clean.endswith(" -collect") or clean == "-collect":
        return True

    return False


def run_cli_export(argv: list[str]) -> int:
    """Export a recorded history log file to a standalone Python (.py) or Pytae (.pt) script."""
    if not argv:
        print("Usage: pytae -export <history_file> [-o <target.py|target.pt>] [-relative] [-no-prune]")
        return 1

    if "--relative" in argv:
        print("pytae: '--relative' is not recognized; use '-relative'.")
        return 1

    relative = "-relative" in argv
    no_prune = any(a in ("-no-prune", "--no-prune") for a in argv)
    clean_argv = [a for a in argv if a not in ("-relative", "-no-prune", "--no-prune")]
    if not clean_argv:
        print("Usage: pytae -export <history_file> [-o <target.py|target.pt>] [-relative] [-no-prune]")
        return 1

    history_file_str = clean_argv[0]
    out_target: str | None = None
    i = 1
    while i < len(clean_argv):
        arg = clean_argv[i]
        if arg in ("-o", "-output", "--output") and i + 1 < len(clean_argv):
            out_target = clean_argv[i + 1]
            i += 2
        elif arg.startswith(("-o=", "-output=", "--output=")):
            out_target = arg.split("=", 1)[1]
            i += 1
        elif out_target is None and not arg.startswith("-"):
            out_target = arg
            i += 1
        else:
            i += 1

    hist_p = Path(os.path.expanduser(history_file_str)).resolve()
    if not hist_p.exists():
        print(f"pytae error: history file '{history_file_str}' not found.")
        return 1

    lines = _prune_rolled_back_entries([_normalize_unquoted_windows_paths(ln) for ln in hist_p.read_text(encoding="utf-8").splitlines()])
    replayable = [item.strip() for item in lines if _is_replayable_entry_static(item)]

    if not replayable:
        print(f"pytae: No state-mutating commands found in '{history_file_str}'.")
        return 0

    if out_target is None:
        out_p = hist_p.with_suffix(".pt")
    else:
        out_p = Path(os.path.expanduser(out_target)).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if out_p.suffix.lower() == ".py":
        content = _compile_history_to_python(replayable, relative=relative, prune_dead=not no_prune)
        desc = "standalone Python script"
    else:
        content = _compile_history_to_pt(replayable, out_p.name, relative=relative, prune_dead=not no_prune)
        desc = "Pytae script"

    out_p.write_text(content, encoding="utf-8")
    path_desc = " (relative paths)" if relative else " (absolute paths)"
    print(f"Exported {desc}{path_desc} to {out_p}.")
    return 0
