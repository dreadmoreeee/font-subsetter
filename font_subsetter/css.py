"""@font-face rules for the subset files."""
from __future__ import annotations

from .ranges import format_unicode_range


def _quote(family: str) -> str:
    return '"' + family.replace("\\", "\\\\").replace('"', '\\"') + '"'


def font_face(result, output, url_prefix: str = "", display: str = "swap") -> str:
    info = result.info
    lines = [
        "@font-face {",
        f"  font-family: {_quote(info.family)};",
        f"  font-style: {info.style};",
        f"  font-weight: {info.weight};",
    ]
    if info.stretch:
        lines.append(f"  font-stretch: {info.stretch};")
    lines += [
        f"  font-display: {display};",
        f'  src: url("{url_prefix}{output.path.name}") format("{output.fmt}");',
        f"  unicode-range: {format_unicode_range(output.codepoints)};",
        "}",
    ]
    return "\n".join(lines)


def stylesheet(results, url_prefix: str = "", display: str = "swap") -> str:
    blocks = []
    for result in results:
        for output in result.outputs:
            blocks.append(f"/* {result.source.name}: {output.role}, "
                          f"{len(output.codepoints)} characters */\n"
                          + font_face(result, output, url_prefix, display))
    return "\n\n".join(blocks) + "\n"
