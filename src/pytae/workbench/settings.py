"""Persistent display settings (`%set`) for Pytae Workbench."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pytae.workbench.system import get_config_path

# ---------------------------------------------------------------------------
# Persistent display settings
# ---------------------------------------------------------------------------


@dataclass
class DisplaySettings:
    """Display formatting settings persisted in ~/.pytae/config.json."""

    max_rows: int = 10
    max_cols: int | None = None
    float_precision: int | None = None
    comma: bool = False

    def to_polars_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "tbl_rows": self.max_rows,
            "tbl_cols": self.max_cols if self.max_cols is not None else -1,
        }
        if self.float_precision is not None:
            cfg["float_precision"] = self.float_precision
        if self.comma:
            cfg["thousands_separator"] = True
        return cfg

    def load(self) -> None:
        cfg_path = get_config_path()
        if not cfg_path.exists():
            return
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        if isinstance(data.get("max_rows"), int) and data["max_rows"] > 0:
            self.max_rows = data["max_rows"]
        mc = data.get("max_cols")
        if mc is None or (isinstance(mc, int) and mc > 0):
            self.max_cols = mc
        fp = data.get("float_precision")
        if fp is None or (isinstance(fp, int) and fp >= 0):
            self.float_precision = fp
        if isinstance(data.get("comma"), bool):
            self.comma = data["comma"]

    def save(self) -> Path:
        cfg_path = get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if cfg_path.exists():
            try:
                loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                pass
        existing.update(
            {
                "max_rows": self.max_rows,
                "max_cols": self.max_cols,
                "float_precision": self.float_precision,
                "comma": self.comma,
            }
        )
        cfg_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        return cfg_path

    def reset(self) -> None:
        self.max_rows = 10
        self.max_cols = None
        self.float_precision = None
        self.comma = False

    def format_summary(self) -> str:
        return (
            f"max_rows        = {self.max_rows}\n"
            f"max_cols        = {self.max_cols}\n"
            f"float_precision = {self.float_precision}\n"
            f"comma           = {self.comma}"
        )

    def format_inline(self) -> str:
        return (
            f"max_rows={self.max_rows}, max_cols={self.max_cols}, "
            f"float_precision={self.float_precision}, comma={self.comma}"
        )

    def apply_spec(self, spec: str) -> str:
        """Parse and apply `%set` arguments (`key=val`, `save`, `reset`, or bare show)."""
        raw = spec.strip()
        if not raw:
            return self.format_summary()
        low = raw.lower()
        if low == "save":
            p = self.save()
            return f"Saved display settings to {p}"
        if low == "reset":
            self.reset()
            return f"Display settings reset to defaults ({self.format_inline()})"

        pairs = _parse_set_pairs(raw)
        if not pairs:
            return self.format_summary()

        updated: list[str] = []
        for k, v in pairs:
            key = k.strip().lower()
            val = v.strip()
            vlow = val.lower()
            if key in ("max_rows", "rows"):
                try:
                    n = int(val)
                    if n <= 0:
                        raise ValueError
                except ValueError:
                    raise ValueError(f"max_rows must be a positive integer, got {val!r}") from None
                self.max_rows = n
                updated.append(f"max_rows={n}")
            elif key in ("max_cols", "cols"):
                if vlow in ("none", "all", "null", "-1"):
                    self.max_cols = None
                    updated.append("max_cols=None")
                else:
                    try:
                        n = int(val)
                        if n <= 0:
                            raise ValueError
                    except ValueError:
                        raise ValueError(f"max_cols must be a positive integer or 'none', got {val!r}") from None
                    self.max_cols = n
                    updated.append(f"max_cols={n}")
            elif key in ("float_precision", "precision", "round"):
                if vlow in ("none", "auto", "null"):
                    self.float_precision = None
                    updated.append("float_precision=None")
                else:
                    try:
                        n = int(val)
                        if n < 0:
                            raise ValueError
                    except ValueError:
                        raise ValueError(
                            f"float_precision must be a non-negative integer or 'none', got {val!r}"
                        ) from None
                    self.float_precision = n
                    updated.append(f"float_precision={n}")
            elif key == "comma":
                if vlow in ("true", "1", "on", "yes"):
                    self.comma = True
                    updated.append("comma=True")
                elif vlow in ("false", "0", "off", "no"):
                    self.comma = False
                    updated.append("comma=False")
                else:
                    raise ValueError(f"comma must be true/false, got {val!r}")
            else:
                raise ValueError(
                    f"Unknown setting {key!r}. Valid settings: max_rows, max_cols, float_precision, comma"
                )
        return "Updated: " + ", ".join(updated)


def _parse_set_pairs(raw: str) -> list[tuple[str, str]]:
    """Parse `k=v k2=v2`, `k=v, k2=v2`, or `k v` into (key, value) pairs."""
    tokens = shlex.split(raw.replace(",", " "))
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "=" in tok:
            k, _, v = tok.partition("=")
            pairs.append((k, v))
            i += 1
        elif i + 1 < len(tokens) and tokens[i + 1] == "=" and i + 2 < len(tokens):
            pairs.append((tok, tokens[i + 2]))
            i += 3
        elif i + 1 < len(tokens) and "=" not in tokens[i + 1]:
            pairs.append((tok, tokens[i + 1]))
            i += 2
        else:
            raise ValueError(f"Invalid setting specification near {tok!r}; expected key=value")
    return pairs


