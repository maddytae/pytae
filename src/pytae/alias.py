"""Deterministic human-readable aliasing (`-alias` / `pt.alias`) for Pytae.

Maps raw values or opaque cryptographic hashes into readable, deterministic
pseudonyms using curated zero-dependency presets (`company`, `name`, `email`,
`city`, `alias`, `code`), with automatic collision disambiguation and optional
vault persistence (reversible via `pt.unmask` / `-unmask -vault`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import polars as pl

from pytae.mask import _load_vault, _save_vault

_ADJECTIVES: tuple[str, ...] = (
    "Amber", "Apex", "Arctic", "Atlas", "Autumn", "Azure", "Birch", "Blue", "Bold", "Bright",
    "Bronze", "Calm", "Cedar", "Clear", "Cobalt", "Coral", "Crest", "Crimson", "Crystal", "Dawn",
    "Delta", "Dusk", "Emerald", "Ever", "Fair", "Field", "Flint", "Forest", "Frost", "Gale",
    "Glacier", "Gold", "Good", "Granite", "Green", "Harbor", "Hazel", "High", "Iron", "Ivory",
    "Jade", "Keystone", "Kind", "Laurel", "Linden", "Loyal", "Lunar", "Maple", "Marine", "Meadow",
    "Meridian", "Metro", "Misty", "Noble", "North", "Oak", "Ocean", "Olive", "Onyx", "Opal",
    "Orchard", "Pacific", "Peak", "Pearl", "Pine", "Plain", "Polar", "Prairie", "Prime", "Quartz",
    "Quiet", "Radiant", "Rapid", "Red", "Ridge", "River", "Royal", "Ruby", "Sage", "Sand",
    "Sapphire", "Scarlet", "Shadow", "Sierra", "Silver", "Sky", "Slate", "Solar", "South", "Spring",
    "Star", "Steel", "Stone", "Summit", "Sunny", "Swift", "Timber", "True", "Valley", "Vista",
)

_NOUNS: tuple[str, ...] = (
    "Acorn", "Anchor", "Arch", "Arrow", "Ash", "Aspen", "Bay", "Beacon", "Bear", "Bridge",
    "Brook", "Canyon", "Cape", "Castle", "Cedar", "Cliff", "Cloud", "Coast", "Compass", "Cove",
    "Creek", "Crown", "Current", "Dale", "Dune", "Eagle", "Echo", "Elm", "Estuary", "Falcon",
    "Ferry", "Field", "Finch", "Fjord", "Flame", "Forge", "Fountain", "Fox", "Garden", "Gate",
    "Grove", "Harbor", "Haven", "Hawk", "Heath", "Heron", "Hill", "Horizon", "Inlet", "Island",
    "Key", "Knoll", "Lake", "Lantern", "Lark", "Leaf", "Ledge", "Light", "Loom", "Marsh",
    "Mesa", "Mill", "Mist", "Moor", "Mount", "Oak", "Oasis", "Orchard", "Osprey", "Otter",
    "Pass", "Path", "Peak", "Pebble", "Pier", "Pine", "Plain", "Plaza", "Point", "Pond",
    "Port", "Quarry", "Rain", "Range", "Rapids", "Reef", "Ridge", "River", "Rock", "Shore",
    "Sky", "Sound", "Spire", "Spring", "Spruce", "Star", "Stone", "Stream", "Summit", "Weather",
)

_CORP_SUFFIXES: tuple[str, ...] = (
    "Corp", "LLC", "Inc", "Group", "Partners", "Holdings",
    "Labs", "Co", "Ventures", "Capital", "Systems", "Global",
)

_FIRST_NAMES: tuple[str, ...] = (
    "Aaron", "Aiden", "Alex", "Alice", "Amara", "Amelia", "Aria", "Arthur", "Avery", "Ben",
    "Blake", "Caleb", "Camila", "Carter", "Chloe", "Clara", "Cole", "Daniel", "David", "Diana",
    "Dylan", "Elena", "Eli", "Elias", "Ella", "Emma", "Ethan", "Eva", "Evan", "Felix",
    "Fiona", "Grace", "Hannah", "Harper", "Hazel", "Henry", "Isaac", "Isla", "Jack", "Jacob",
    "James", "Jordan", "Julia", "Julian", "Kai", "Kate", "Leo", "Liam", "Lily", "Logan",
    "Lucas", "Lucy", "Luke", "Maya", "Mason", "Mateo", "Max", "Mia", "Mila", "Nathan",
    "Nora", "Noah", "Oliver", "Olivia", "Omar", "Owen", "Priya", "Quinn", "Riley", "Rohan",
    "Ruby", "Ryan", "Sam", "Sara", "Sofia", "Stella", "Theo", "Victor", "Zara", "Zoe",
)

_LAST_NAMES: tuple[str, ...] = (
    "Adams", "Allen", "Baker", "Barnes", "Bell", "Bennett", "Brooks", "Brown", "Bryant", "Burns",
    "Butler", "Campbell", "Carter", "Chen", "Clark", "Cole", "Collins", "Cook", "Cooper", "Cox",
    "Cruz", "Davis", "Diaz", "Edwards", "Ellis", "Evans", "Fisher", "Flores", "Ford", "Foster",
    "Garcia", "Gibson", "Gomez", "Gordon", "Graham", "Grant", "Gray", "Green", "Griffin", "Hall",
    "Harris", "Hayes", "Hill", "Howard", "Hughes", "James", "Jenkins", "Johnson", "Jones", "Kelly",
    "Kim", "King", "Lee", "Lewis", "Lin", "Long", "Lopez", "Martin", "Mercer", "Miller",
    "Mitchell", "Moore", "Morgan", "Morris", "Murphy", "Myers", "Nelson", "Nguyen", "Parker", "Patel",
    "Perez", "Perry", "Powell", "Price", "Reed", "Reyes", "Rivera", "Roberts", "Ross", "Wright",
)

_CITY_PREFIXES: tuple[str, ...] = (
    "Alder", "Ash", "Bay", "Birch", "Blue", "Briar", "Bright", "Cedar", "Clear", "Cold",
    "Crest", "East", "Elm", "Fair", "Glen", "Gold", "Grand", "Green", "High", "Iron",
    "Lake", "Maple", "Meadow", "Mill", "New", "North", "Oak", "Pine", "Red", "River",
    "Rock", "Rose", "Sand", "Silver", "South", "Spring", "Stone", "Sun", "West", "White",
)

_CITY_SUFFIXES: tuple[str, ...] = (
    "bay", "boro", "bridge", "brook", "burg", "chester", "cliff", "creek", "crest", "dale",
    "falls", "field", "ford", "gate", "glen", "grove", "harbor", "haven", "hill", "hurst",
    "lake", "land", "mont", "moor", "park", "point", "port", "ridge", "side", "ton",
    "vale", "view", "ville", "water", "wood",
)

_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # omits I, O for readability

VALID_ALIAS_PRESETS: tuple[str, ...] = ("company", "name", "email", "city", "alias", "code")

_PRESET_ALIASES: dict[str, str] = {
    "company": "company",
    "corp": "company",
    "org": "company",
    "name": "name",
    "person": "name",
    "email": "email",
    "mail": "email",
    "city": "city",
    "place": "city",
    "region": "city",
    "alias": "alias",
    "friendly": "alias",
    "readable": "alias",
    "product": "alias",
    "code": "code",
    "short": "code",
    "id": "code",
}


def parse_alias_spec(
    spec: Any = None,
    *args: Any,
    default_preset: str = "alias",
    **kwargs: Any,
) -> dict[str, str]:
    """Parse `-alias` / `pt.alias()` specification into `{column_name: preset}`."""
    mapping: dict[str, str] = {}

    if spec is not None:
        if isinstance(spec, dict):
            for k, v in spec.items():
                mapping[str(k).strip()] = str(v).strip().lower()
        elif isinstance(spec, str):
            parts = [p.strip() for p in spec.split(",") if p.strip()]
            for p in parts:
                if "=" in p:
                    col, preset = p.split("=", 1)
                elif ":" in p:
                    col, preset = p.split(":", 1)
                else:
                    col, preset = p, default_preset
                mapping[col.strip()] = preset.strip().lower()
        elif isinstance(spec, (list, tuple, set)):
            for item in spec:
                mapping[str(item).strip()] = default_preset
        else:
            mapping[str(spec).strip()] = default_preset

    for arg in args:
        if isinstance(arg, str):
            mapping[arg.strip()] = default_preset
        elif isinstance(arg, (list, tuple)):
            for sub in arg:
                mapping[str(sub).strip()] = default_preset

    for k, v in kwargs.items():
        if k not in ("seed", "salt", "vault", "preset"):
            mapping[k.strip()] = str(v).strip().lower()

    preset_kw = kwargs.get("preset")
    if preset_kw is not None:
        target_p = str(preset_kw).strip().lower()
        for col, p in list(mapping.items()):
            if p == default_preset:
                mapping[col] = target_p

    normalized: dict[str, str] = {}
    for col, raw_preset in mapping.items():
        canon = _PRESET_ALIASES.get(raw_preset.lower())
        if canon is None:
            valid_str = ", ".join(repr(x) for x in VALID_ALIAS_PRESETS)
            raise ValueError(f"unknown alias preset '{raw_preset}' for column '{col}'; expected one of: {valid_str}")
        normalized[col] = canon

    return normalized


def _digest_ints(val_str: str, preset: str, seed: int | str | None, salt: str | None) -> tuple[int, int, int, int]:
    seed_part = "" if seed is None else str(seed)
    salt_part = salt or ""
    raw = f"{seed_part}:{salt_part}:{preset}:{val_str}".encode()
    h = hashlib.sha256(raw).digest()
    return (
        int.from_bytes(h[0:4], "big"),
        int.from_bytes(h[4:8], "big"),
        int.from_bytes(h[8:12], "big"),
        int.from_bytes(h[12:16], "big"),
    )


def _format_alias(val_str: str, preset: str, seed: int | str | None, salt: str | None) -> str:
    n0, n1, n2, n3 = _digest_ints(val_str, preset, seed, salt)
    if preset == "company":
        adj = _ADJECTIVES[n0 % len(_ADJECTIVES)]
        noun = _NOUNS[n1 % len(_NOUNS)]
        suffix = _CORP_SUFFIXES[n2 % len(_CORP_SUFFIXES)]
        return f"{adj} {noun} {suffix}"
    if preset == "name":
        first = _FIRST_NAMES[n0 % len(_FIRST_NAMES)]
        last = _LAST_NAMES[n1 % len(_LAST_NAMES)]
        return f"{first} {last}"
    if preset == "email":
        first = _FIRST_NAMES[n0 % len(_FIRST_NAMES)].lower()
        last = _LAST_NAMES[n1 % len(_LAST_NAMES)].lower()
        adj = _ADJECTIVES[n2 % len(_ADJECTIVES)].lower()
        noun = _NOUNS[n3 % len(_NOUNS)].lower()
        return f"{first}.{last}@{adj}{noun}.example"
    if preset == "city":
        prefix = _CITY_PREFIXES[n0 % len(_CITY_PREFIXES)]
        suffix = _CITY_SUFFIXES[n1 % len(_CITY_SUFFIXES)]
        return f"{prefix}{suffix}"
    if preset == "code":
        c0 = _CODE_LETTERS[n0 % len(_CODE_LETTERS)]
        d0 = n1 % 10
        c1 = _CODE_LETTERS[(n0 // len(_CODE_LETTERS)) % len(_CODE_LETTERS)]
        num = n2 % 1000
        return f"{c0}{d0}{c1}-{num:03d}"
    # default: "alias"
    adj = _ADJECTIVES[n0 % len(_ADJECTIVES)]
    noun = _NOUNS[n1 % len(_NOUNS)]
    return f"{adj} {noun}"


def _disambiguate(base: str, preset: str, counter: int) -> str:
    if preset == "email" and "@" in base:
        local, _, domain = base.partition("@")
        return f"{local}{counter}@{domain}"
    if preset == "code":
        return f"{base}-{counter}"
    return f"{base} {counter}"


def alias_polars(
    df: Any,
    spec: dict[str, str],
    *,
    seed: int | str | None = None,
    salt: str | None = None,
    vault: str | Path | None = None,
) -> Any:
    """Replace specified columns in a Polars DataFrame/LazyFrame with deterministic readable aliases."""
    if not spec:
        return df

    vault_path = Path(vault) if vault is not None else None
    vault_map: dict[str, dict[str, str]] = {}
    vault_dtypes: dict[str, str] = {}
    if vault_path is not None:
        vault_map, vault_dtypes = _load_vault(vault_path)

    exprs: list[pl.Expr] = []
    vault_updated = False

    for col, preset in spec.items():
        col_series = (
            df.select(pl.col(col).drop_nulls()).collect()[col]
            if isinstance(df, pl.LazyFrame)
            else df[col].drop_nulls()
        )
        orig_dtype_str = str(col_series.dtype)
        if vault_path is not None:
            vault_dtypes[col] = orig_dtype_str

        col_map: dict[str, str] = dict(vault_map.get(col, {})) if vault_path is not None else {}
        used_aliases: set[str] = set(col_map.values())

        # Sort unique stringified values so collision disambiguation is 100% deterministic
        unique_vals = sorted({str(v) for v in col_series.unique().to_list()})
        for val_str in unique_vals:
            if val_str in col_map:
                continue
            base = _format_alias(val_str, preset, seed=seed, salt=salt)
            cand = base
            counter = 2
            while cand in used_aliases:
                cand = _disambiguate(base, preset, counter)
                counter += 1
            col_map[val_str] = cand
            used_aliases.add(cand)
            if vault_path is not None:
                vault_map.setdefault(col, {})[val_str] = cand
                vault_updated = True

        col_as_str = pl.col(col).cast(pl.String)
        expr = col_as_str.replace_strict(col_map, default=col_as_str).alias(col)
        exprs.append(expr)

    if vault_updated and vault_path is not None:
        _save_vault(vault_map, vault_dtypes, vault_path)

    return df.with_columns(exprs)


def alias(
    df: Any,
    spec: Any = None,
    *args: Any,
    seed: int | str | None = None,
    salt: str | None = None,
    vault: str | Path | None = None,
    **kwargs: Any,
) -> Any:
    """Replace sensitive or hashed column values with deterministic, human-readable aliases.

    Presets:
    - `company` (`org`, `corp`): e.g. `"Good Weather Corp"`, `"Silver Cedar LLC"`
    - `name` (`person`): e.g. `"Jordan Brooks"`, `"Maya Lin"`
    - `email`: e.g. `"jordan.brooks@goodweather.example"`
    - `city` (`place`, `region`): e.g. `"Northbrook"`, `"Clearwater"`
    - `alias` (`friendly`, `readable`, `product`, default): e.g. `"Calm River"`
    - `code` (`short`, `id`): e.g. `"A7K-492"`

    Examples:
        pt.alias(df, "customer=company, rep=name", seed=42)
        pt.alias(df, customer="company", vault="map.parquet", seed=42)
    """
    from pytae.dataframe import DataFrame

    mapping = parse_alias_spec(spec, *args, default_preset="alias", **kwargs)

    is_pt = isinstance(df, DataFrame)
    underlying = df._df if is_pt else df

    if isinstance(underlying, (pl.DataFrame, pl.LazyFrame)):
        res = alias_polars(underlying, mapping, seed=seed, salt=salt, vault=vault)
        return DataFrame(res) if is_pt else res

    import pandas as pd

    if isinstance(underlying, pd.DataFrame):
        pl_df = pl.from_pandas(underlying)
        res_pl = alias_polars(pl_df, mapping, seed=seed, salt=salt, vault=vault)
        res_pd = res_pl.to_pandas()
        return DataFrame(res_pd) if is_pt else res_pd

    raise TypeError(f"alias() expected a DataFrame, got {type(df).__name__}")
