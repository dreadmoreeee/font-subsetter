"""Reading fonts, subsetting them and writing WOFF2 (or WOFF without brotli)."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fontTools import subset as ftsubset
from fontTools.ttLib import TTFont, woff2

# Features kept unless --features says otherwise.
DEFAULT_FEATURES = ("kern", "liga", "locl")
# Features browsers apply unconditionally to shape text correctly (combining
# accents, required ligatures, variable-font substitutions). Always kept
# unless removed explicitly with --features -name.
REQUIRED_FEATURES = ("ccmp", "mark", "mkmk", "rlig", "rvrn", "curs")
# Name records kept: copyright, family, subfamily, unique ID, full name,
# version, PostScript name, license and license URL. IDs used by fvar/STAT are
# kept by fontTools on top of these, so variable fonts stay valid.
NAME_IDS = (0, 1, 2, 3, 4, 5, 6, 13, 14)

# Control characters never need a glyph from a web font.
CONTROLS = frozenset(range(0x20)) | frozenset(range(0x7F, 0xA0))

BROTLI_MESSAGE = ("brotli is not installed, so WOFF2 cannot be written; writing WOFF "
                  "(zlib) instead, which is larger. Run: pip install brotli")


def have_brotli() -> bool:
    return bool(woff2.haveBrotli)


def resolve_features(spec: str | None) -> list[str]:
    """'kern,liga' replaces the defaults; '+calt,-liga' edits them; '*' keeps all."""
    base = list(REQUIRED_FEATURES) + list(DEFAULT_FEATURES)
    if not spec:
        return base
    items = [s.strip() for s in spec.split(",") if s.strip()]
    if "*" in items:
        return ["*"]
    if all(i[0] in "+-" for i in items):
        out = list(base)
    else:
        out = list(REQUIRED_FEATURES)
    for item in items:
        name = item.lstrip("+-")
        if len(name) > 4 or not name:
            raise ValueError(f"bad OpenType feature tag: {item!r}")
        if item.startswith("-"):
            out = [f for f in out if f != name]
        elif name not in out:
            out.append(name)
    return out


def detect_format(data: bytes) -> str:
    sig = data[:4]
    if sig == b"wOF2":
        return "woff2"
    if sig == b"wOFF":
        return "woff"
    if sig == b"OTTO":
        return "otf"
    if sig in (b"\x00\x01\x00\x00", b"true"):
        return "ttf"
    if sig == b"ttcf":
        return "ttc"
    raise ValueError("not a font file (unknown signature)")


def _woff2_to_sfnt_without_brotli(data: bytes) -> bytes:
    from .browser import BrotliBridge

    with BrotliBridge() as bridge:
        saved = (woff2.haveBrotli, getattr(woff2, "brotli", None))
        woff2.haveBrotli = True
        woff2.brotli = SimpleNamespace(decompress=bridge.decompress)
        try:
            font = TTFont(BytesIO(data))
        finally:
            woff2.haveBrotli, woff2.brotli = saved
    return _to_sfnt(font)


def _to_sfnt(font: TTFont) -> bytes:
    font.flavor = None
    buf = BytesIO()
    font.save(buf, reorderTables=False)
    return buf.getvalue()


def read_sfnt(data: bytes) -> bytes:
    """Any web font -> plain TTF/OTF bytes."""
    fmt = detect_format(data)
    if fmt == "ttc":
        raise ValueError("font collections (.ttc) are not supported; extract one font first")
    if fmt in ("ttf", "otf"):
        return data
    if fmt == "woff2" and not have_brotli():
        print("note: brotli is not installed; reading WOFF2 through headless Chromium. "
              "pip install brotli makes this faster.", file=sys.stderr)
        return _woff2_to_sfnt_without_brotli(data)
    return _to_sfnt(TTFont(BytesIO(data)))


@dataclass
class FontInfo:
    family: str
    weight: str
    style: str
    stretch: str
    axes: dict[str, tuple[float, float, float]]
    codepoints: set[int]
    features: set[str]
    glyphs: int
    is_cff: bool


def _name(font: TTFont, *ids: int) -> str:
    table = font["name"] if "name" in font else None
    for i in ids:
        if table is not None:
            rec = table.getDebugName(i)
            if rec:
                return rec
    return ""


def family_name(font: TTFont) -> str:
    """Typographic family (name ID 16), else name ID 1. Variable fonts without
    ID 16 often carry the default instance's style in ID 1 ("Serif Light");
    those trailing style words are removed."""
    family = _name(font, 16)
    if family:
        return family
    family = _name(font, 1) or "Unnamed"
    if "fvar" in font:
        defaults = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        for inst in font["fvar"].instances:
            if inst.coordinates == defaults:
                style = set(_name(font, inst.subfamilyNameID).split())
                words = family.split()
                while len(words) > 1 and words[-1] in style:
                    words.pop()
                family = " ".join(words)
                break
    return family


def font_features(font: TTFont) -> set[str]:
    tags: set[str] = set()
    for tag in ("GSUB", "GPOS"):
        if tag in font and font[tag].table.FeatureList is not None:
            tags |= {r.FeatureTag for r in font[tag].table.FeatureList.FeatureRecord}
    if "kern" in font:
        tags.add("kern")
    return tags


def font_info(font: TTFont) -> FontInfo:
    axes = {}
    if "fvar" in font:
        axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes}
    os2 = font["OS/2"] if "OS/2" in font else None
    if "wght" in axes:
        lo, _, hi = axes["wght"]
        weight = f"{lo:g}" if lo == hi else f"{lo:g} {hi:g}"
    else:
        weight = str(os2.usWeightClass if os2 else 400)
    italic = bool(os2 and os2.fsSelection & 1) or bool(font["head"].macStyle & 2)
    if italic or ("ital" in axes and axes["ital"][1] >= 1):
        style = "italic"
    elif "slnt" in axes:
        lo, _, hi = axes["slnt"]
        a, b = sorted((-lo, -hi))
        style = f"oblique {a:g}deg {b:g}deg"
    elif "post" in font and font["post"].italicAngle:
        style = "italic"
    else:
        style = "normal"
    stretch = ""
    if "wdth" in axes:
        lo, _, hi = axes["wdth"]
        stretch = f"{lo:g}%" if lo == hi else f"{lo:g}% {hi:g}%"
    return FontInfo(
        family=family_name(font),
        weight=weight,
        style=style,
        stretch=stretch,
        axes=axes,
        codepoints=set(font.getBestCmap() or {}),
        features=font_features(font),
        glyphs=len(font.getGlyphOrder()),
        is_cff="CFF " in font or "CFF2" in font,
    )


def parse_axis_limits(specs) -> dict[str, float | tuple[float, float]]:
    """['wght=400:700', 'wdth=100'] -> {'wght': (400, 700), 'wdth': 100}."""
    out: dict[str, float | tuple[float, float]] = {}
    for spec in specs or ():
        tag, _, value = spec.partition("=")
        tag = tag.strip()
        if not tag or not value or len(tag) > 4:
            raise ValueError(f"bad --axis value {spec!r}; use TAG=VALUE or TAG=MIN:MAX")
        if ":" in value:
            lo, hi = (float(v) for v in value.split(":", 1))
            out[tag] = (min(lo, hi), max(lo, hi))
        else:
            out[tag] = float(value)
    return out


def load(sfnt: bytes, axis_limits=None) -> TTFont:
    """A fresh TTFont (subsetting changes fonts in place), with variable axes
    pinned or narrowed when asked."""
    font = TTFont(BytesIO(sfnt))
    if axis_limits and "fvar" in font:
        from fontTools.varLib import instancer

        present = {a.axisTag for a in font["fvar"].axes}
        limits = {k: v for k, v in axis_limits.items() if k in present}
        if limits:
            font = instancer.instantiateVariableFont(font, limits, updateFontNames=False)
            # Round-trip so every table is compiled and consistent again.
            font = TTFont(BytesIO(_to_sfnt(font)))
    return font


def subset_bytes(sfnt: bytes, unicodes, *, features, flavor: str, hinting: bool = True,
                 axis_limits=None) -> bytes:
    """Subset to `unicodes` and return the compiled font in `flavor`
    ('woff2', 'woff' or None for TTF/OTF)."""
    font = load(sfnt, axis_limits)
    options = ftsubset.Options()
    options.layout_features = list(features)
    options.name_IDs = list(NAME_IDS)
    options.name_languages = [0x0409]
    options.hinting = hinting
    options.notdef_outline = True
    options.recalc_bounds = True
    options.flavor = flavor
    sub = ftsubset.Subsetter(options)
    sub.populate(unicodes=sorted(unicodes))
    sub.subset(font)
    font.flavor = flavor
    buf = BytesIO()
    font.save(buf)
    return buf.getvalue()


@dataclass
class Output:
    role: str          # "subset", "page" or "rest"
    path: Path
    size: int
    codepoints: set[int]
    fmt: str


@dataclass
class FontResult:
    source: Path
    source_format: str
    source_size: int
    info: FontInfo
    outputs: list[Output] = field(default_factory=list)
    missing_page: set[int] = field(default_factory=set)
    missing_preset: set[int] = field(default_factory=set)
    removed: set[int] = field(default_factory=set)
    features_kept: set[str] = field(default_factory=set)
    features_dropped: set[str] = field(default_factory=set)


def process_font(path, page_cps: set[int], preset_cps: set[int], out_dir, *, split: bool = False,
                 features=None, hinting: bool = True, axis_limits=None,
                 overrides: dict | None = None) -> FontResult:
    path = Path(path)
    data = path.read_bytes()
    fmt = detect_format(data)
    sfnt = read_sfnt(data)
    font = load(sfnt, axis_limits)
    info = font_info(font)
    for key, value in (overrides or {}).items():
        if value:
            setattr(info, key, value)
    features = list(features or resolve_features(None))
    flavor = "woff2" if have_brotli() else "woff"

    cmap = info.codepoints
    page_cps, preset_cps = page_cps - CONTROLS, preset_cps - CONTROLS
    result = FontResult(path, fmt, len(data), info)
    result.missing_page = page_cps - cmap
    result.missing_preset = preset_cps - page_cps - cmap
    if split:
        groups = [("page", page_cps & cmap), ("rest", (preset_cps - page_cps) & cmap)]
    else:
        groups = [("subset", (page_cps | preset_cps) & cmap)]
    groups = [(role, cps) for role, cps in groups if cps]
    if not any(cps - {0x20} for _, cps in groups):
        raise ValueError(f"{path.name}: none of the requested characters are in this font")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kept: set[int] = set()
    stem = path.name.split(".")[0]
    for role, cps in groups:
        blob = subset_bytes(sfnt, cps, features=features, flavor=flavor, hinting=hinting,
                            axis_limits=axis_limits)
        target = out_dir / f"{stem}.{role}.{flavor}"
        target.write_bytes(blob)
        kept |= cps
        result.outputs.append(Output(role, target, len(blob), cps, flavor))
        result.features_kept |= font_features(TTFont(BytesIO(blob)))
    result.removed = cmap - kept
    # Features removed by the --features choice (features whose glyphs are
    # all gone disappear too, but that is not a loss for this text).
    result.features_dropped = set() if "*" in features else info.features - set(features)
    return result
