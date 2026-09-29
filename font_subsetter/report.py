"""Text and JSON reports."""
from __future__ import annotations

from .ranges import describe, format_unicode_range


def kb(n: int) -> str:
    return f"{n / 1000:.1f} KB"


def _pct(before: int, after: int) -> str:
    return f"{(after - before) / before * 100:+.1f}%" if before else "n/a"


def text_report(results, pages=(), page_chars: int = 0, preset_chars: int = 0) -> str:
    lines = []
    for p in pages:
        state = p.skipped or f"HTTP {p.status}, {len(set(p.text))} distinct characters"
        lines.append(f"page  {p.url}  {state}")
    if pages:
        lines.append("")
    lines.append(f"characters requested: {page_chars} from the text sources, "
                 f"{preset_chars} from presets/ranges")
    total_before = total_after = total_page = 0
    for r in results:
        i = r.info
        variable = ""
        if i.axes:
            variable = "  variable: " + ", ".join(
                f"{tag} {lo:g}-{hi:g}" for tag, (lo, _, hi) in i.axes.items())
        lines += ["", f"{r.source.name}  {i.family}, {i.weight}, {i.style}{variable}"]
        lines.append(f"  before  {r.source_format:<5} {kb(r.source_size):>10}  "
                     f"{len(i.codepoints)} characters, {i.glyphs} glyphs")
        size = 0
        for o in r.outputs:
            size += o.size
            lines.append(f"  {o.role:<6}  {o.fmt:<5} {kb(o.size):>10}  {len(o.codepoints)} characters  "
                         f"{_pct(r.source_size, o.size)}  {o.path.name}")
        first = r.outputs[0].size
        total_before += r.source_size
        total_after += size
        total_page += first
        kept = ", ".join(sorted(r.features_kept)) or "none"
        lines.append(f"  features in subset: {kept}")
        if r.features_dropped:
            lines.append(f"  features dropped (--features): {', '.join(sorted(r.features_dropped))}")
        if r.missing_page:
            lines.append(f"  page characters not in this font (they fall back): {describe(r.missing_page)}")
        if r.missing_preset:
            lines.append(f"  preset characters not in this font: {len(r.missing_preset)}")
        lines.append(f"  font characters removed: {len(r.removed)}"
                     + (f" ({describe(r.removed, 40)})" if r.removed else ""))
    lines.append("")
    split = any(o.role == "page" for r in results for o in r.outputs)
    line = f"total: {kb(total_before)} -> {kb(total_after)} ({_pct(total_before, total_after)})"
    if split:
        line += f"; page files only: {kb(total_page)} ({_pct(total_before, total_page)})"
    lines.append(line)
    return "\n".join(lines)


def json_report(results, pages=(), page_chars: int = 0, preset_chars: int = 0) -> dict:
    fonts = []
    for r in results:
        i = r.info
        fonts.append({
            "source": str(r.source),
            "format": r.source_format,
            "size": r.source_size,
            "family": i.family,
            "weight": i.weight,
            "style": i.style,
            "stretch": i.stretch or None,
            "axes": {t: {"min": a[0], "default": a[1], "max": a[2]} for t, a in i.axes.items()},
            "characters": len(i.codepoints),
            "glyphs": i.glyphs,
            "outputs": [{
                "role": o.role,
                "file": str(o.path),
                "format": o.fmt,
                "size": o.size,
                "characters": len(o.codepoints),
                "unicode_range": format_unicode_range(o.codepoints),
            } for o in r.outputs],
            "features_kept": sorted(r.features_kept),
            "features_dropped": sorted(r.features_dropped),
            "missing_page_characters": "".join(chr(c) for c in sorted(r.missing_page)),
            "missing_preset_count": len(r.missing_preset),
            "removed_characters": "".join(chr(c) for c in sorted(r.removed)),
        })
    before = sum(f["size"] for f in fonts)
    after = sum(o["size"] for f in fonts for o in f["outputs"])
    return {
        "pages": [{"url": p.url, "status": p.status, "skipped": p.skipped or None,
                   "lang": p.lang or None} for p in pages],
        "requested": {"text_sources": page_chars, "presets": preset_chars},
        "fonts": fonts,
        "total": {"before": before, "after": after},
    }
