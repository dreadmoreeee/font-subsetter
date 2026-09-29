"""Code point sets: named presets, unicode-range parsing and formatting."""
from __future__ import annotations

import re
import unicodedata

# The unicode-range values Google Fonts uses for these subsets (css2 API).
# "latin" covers English, French, Spanish, German, Portuguese, Italian and the
# Nordic languages; "latin-ext" adds Central and Eastern European, Turkish,
# Baltic and other extended Latin letters and more currency signs. As
# published, the two overlap on seven code points (dotless i, OE/oe, three
# combining marks and the dagger); the overlap is kept.
PRESETS: dict[str, str] = {
    "latin": (
        "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
        "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, "
        "U+2212, U+2215, U+FEFF, U+FFFD"
    ),
    "latin-ext": (
        "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, "
        "U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, "
        "U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF"
    ),
}

_TOKEN = re.compile(r"^U\+([0-9A-F?]{1,6})(?:-([0-9A-F]{1,6}))?$", re.I)


def parse_unicode_range(value: str) -> set[int]:
    """'U+0-FF, U+2013, U+4??' -> set of code points."""
    out: set[int] = set()
    for token in re.split(r"[,\s]+", value.strip()):
        if not token:
            continue
        m = _TOKEN.match(token)
        if not m:
            raise ValueError(f"bad unicode-range token: {token!r}")
        start, end = m.group(1), m.group(2)
        if "?" in start:
            if end:
                raise ValueError(f"bad unicode-range token: {token!r}")
            lo, hi = int(start.replace("?", "0"), 16), int(start.replace("?", "F"), 16)
        else:
            lo = int(start, 16)
            hi = int(end, 16) if end else lo
        if hi < lo or hi > 0x10FFFF:
            raise ValueError(f"bad unicode-range token: {token!r}")
        out.update(range(lo, hi + 1))
    return out


def preset(names: str) -> set[int]:
    """'latin' or 'latin,latin-ext' -> set of code points."""
    out: set[int] = set()
    for name in (n.strip().lower() for n in names.split(",")):
        if not name:
            continue
        if name not in PRESETS:
            raise ValueError(f"unknown preset {name!r}; choose from {', '.join(PRESETS)}")
        out |= parse_unicode_range(PRESETS[name])
    return out


def to_ranges(codepoints) -> list[tuple[int, int]]:
    """Sorted, merged (start, end) pairs."""
    ranges: list[tuple[int, int]] = []
    for cp in sorted(set(codepoints)):
        if ranges and cp == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], cp)
        else:
            ranges.append((cp, cp))
    return ranges


def format_unicode_range(codepoints) -> str:
    """{0x41, 0x42, 0x43, 0xE9} -> 'U+41-43, U+E9' (the short form browsers print)."""
    parts = []
    for lo, hi in to_ranges(codepoints):
        parts.append(f"U+{lo:X}" if lo == hi else f"U+{lo:X}-{hi:X}")
    return ", ".join(parts)


def describe(codepoints, limit: int = 60) -> str:
    """Printable preview of a set of characters for reports."""
    cps = sorted(codepoints)
    shown = []
    for cp in cps[:limit]:
        ch = chr(cp)
        visible = ch.isprintable() and unicodedata.category(ch)[0] not in "MZC"
        shown.append(ch if visible else f"U+{cp:04X}")
    text = " ".join(shown)
    if len(cps) > limit:
        text += f" ... (+{len(cps) - limit})"
    return text
