"""Backward-compatibility re-exports for mutate parsing utilities and literals."""

from __future__ import annotations

from pytae._parsing import (
    _replace_underscore_placeholder,
    _resolve_multi_target_cols,
    _rewrite_fallback_col_refs,
    _strip_at_refs,
    parse_mutate_spec,
)

__all__ = [
    "_replace_underscore_placeholder",
    "_resolve_multi_target_cols",
    "_rewrite_fallback_col_refs",
    "_strip_at_refs",
    "parse_mutate_spec",
]
