"""Quote-aware string splitting shared by mutate() and the CLI parser."""

from __future__ import annotations


def tokenize(raw: str, seps: str, *, keep_quotes: bool = False, track_brackets: bool = False) -> list[str]:
    """Split raw into segments at top-level occurrences of any character in `seps`,
    respecting quotes (a matched quote pair is never split inside) and, if
    track_brackets, (), [], {} nesting depth. keep_quotes controls whether the quote
    characters themselves are kept in each segment's text (needed by callers that
    re-scan a segment for a second, nested split) or dropped as they're consumed.
    Every segment is returned (including empty ones) with surrounding whitespace
    stripped -- callers filter/validate as needed.
    """
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    depth = 0
    for ch in raw:
        if quote:
            if ch == quote:
                quote = None
                if keep_quotes:
                    buf.append(ch)
            else:
                buf.append(ch)
            continue
        if ch in "'\"":
            quote = ch
            if keep_quotes:
                buf.append(ch)
        elif track_brackets and ch in "([{":
            depth += 1
            buf.append(ch)
        elif track_brackets and ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif depth == 0 and ch in seps:
            segments.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    segments.append("".join(buf).strip())
    return segments


def _is_enclosed_pair(raw: str, open_ch: str, close_ch: str) -> bool:
    if len(raw) < 2 or raw[0] != open_ch or raw[-1] != close_ch:
        return False
    if open_ch == close_ch:
        for idx in range(1, len(raw)):
            if raw[idx] == open_ch:
                return idx == len(raw) - 1
        return False
    depth = 0
    for idx, ch in enumerate(raw):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return idx == len(raw) - 1
    return False


def unquote_name(raw: str) -> str:
    raw = raw.strip()
    changed = True
    while changed and len(raw) >= 2:
        changed = False
        if raw[0] in "'\"" and _is_enclosed_pair(raw, raw[0], raw[0]):
            raw = raw[1:-1].strip()
            changed = True
        elif raw[0] == "[" and _is_enclosed_pair(raw, "[", "]"):
            raw = raw[1:-1].strip()
            changed = True
    return raw

