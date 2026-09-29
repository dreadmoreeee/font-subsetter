"""Command line interface."""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from . import __version__, fonts as F, ranges, textsources
from .css import stylesheet
from .report import json_report, text_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="font-subsetter",
        description="Subset web fonts to the characters your pages use and write WOFF2 files "
                    "plus matching @font-face CSS.")
    p.add_argument("fonts", nargs="+", help="font files (ttf, otf, woff, woff2)")
    src = p.add_argument_group("text sources (combine freely)")
    src.add_argument("--url", action="append", default=[], metavar="URL",
                     help="page to render in headless Chromium and read the text of (repeatable)")
    src.add_argument("--html", action="append", default=[], metavar="FILE",
                     help="local HTML file (parsed, scripts not run; repeatable)")
    src.add_argument("--chars", action="append", default=[], metavar="FILE",
                     help="UTF-8 file whose characters are all kept (repeatable)")
    src.add_argument("--text", action="append", default=[], metavar="TEXT", help="literal characters to keep")
    src.add_argument("--preset", metavar="NAMES",
                     help=f"unicode-range presets, comma-separated: {', '.join(ranges.PRESETS)}")
    src.add_argument("--unicodes", metavar="RANGE", help='extra code points, e.g. "U+2013-2014, U+2192"')
    src.add_argument("--case-variants", action="store_true",
                     help="also keep the other case of every letter from the text sources")
    out = p.add_argument_group("output")
    out.add_argument("--out", default="subset", metavar="DIR", help="output folder (default: subset)")
    out.add_argument("--css", metavar="FILE", help="CSS file to write (default: OUT/fonts.css)")
    out.add_argument("--url-prefix", default="", metavar="PREFIX",
                     help='prefix for font URLs in the CSS, e.g. "/fonts/"')
    out.add_argument("--font-display", default="swap", help="font-display value (default: swap)")
    out.add_argument("--split", action="store_true",
                     help="two files per font: page characters, and the rest of the preset "
                          "(default preset latin), with non-overlapping unicode-range")
    out.add_argument("--json", action="store_true", help="print the report as JSON")
    out.add_argument("--dump-chars", metavar="FILE",
                     help="write the characters collected from the text sources (reuse with --chars)")
    fnt = p.add_argument_group("font")
    fnt.add_argument("--features", metavar="LIST",
                     help="OpenType features to keep: 'kern,liga' replaces the defaults "
                          f"({','.join(F.DEFAULT_FEATURES)}), '+calt,-liga' edits them, '*' keeps all")
    fnt.add_argument("--axis", action="append", default=[], metavar="TAG=VALUE",
                     help="variable fonts: pin (wght=400) or narrow (wght=400:700) an axis")
    fnt.add_argument("--no-hinting", action="store_true", help="drop TrueType hinting (smaller files)")
    fnt.add_argument("--family", help="font-family to write in the CSS (default: from the font)")
    fnt.add_argument("--weight", help="font-weight to write (default: from the font)")
    fnt.add_argument("--style", help="font-style to write (default: from the font)")
    web = p.add_argument_group("fetching URLs")
    web.add_argument("--follow-hreflang", action="store_true",
                     help="also read the same-site hreflang alternates of each --url")
    web.add_argument("--max-pages", type=int, default=10, help="most page loads (default: 10)")
    web.add_argument("--delay", type=float, default=1.0, help="seconds between page loads (default: 1)")
    web.add_argument("--timeout", type=float, default=30.0, help="seconds per page (default: 30)")
    web.add_argument("--user-agent", help="User-Agent for page loads and robots.txt")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def expand(paths) -> list[str]:
    """Expand * ? [ ] and ** patterns (Windows shells and CI YAML do not)."""
    out = []
    for path in paths:
        if any(c in path for c in "*?["):
            matches = sorted(glob.glob(path, recursive=True))
            if not matches:
                raise FileNotFoundError(f"no file matches {path!r}")
            out += matches
        else:
            out.append(path)
    return out


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    say = (lambda m: print(m, file=sys.stderr)) if args.json else print
    try:
        args.fonts, args.html, args.chars = expand(args.fonts), expand(args.html), expand(args.chars)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    text = "".join(args.text)
    for path in args.html:
        text += textsources.html_text(Path(path).read_text(encoding="utf-8", errors="replace"))
    for path in args.chars:
        text += textsources.read_text_file(path)
    pages = []
    if args.url:
        from .browser import USER_AGENT, fetch_pages

        pages = fetch_pages(args.url, delay=args.delay, timeout=args.timeout,
                            user_agent=args.user_agent or USER_AGENT,
                            follow_hreflang=args.follow_hreflang, max_pages=args.max_pages,
                            log=lambda m: print(m, file=sys.stderr))
        text += "".join(p.text for p in pages)
        if not any(p.text for p in pages):
            print("error: no page could be read", file=sys.stderr)
            return 2
    has_text = bool(text) or bool(args.html or args.chars or args.url)
    page_cps = textsources.codepoints_of(text) if has_text else set()
    if args.case_variants:
        page_cps = textsources.add_case_variants(page_cps)
    if args.dump_chars:
        Path(args.dump_chars).write_text("".join(chr(c) for c in sorted(page_cps)), encoding="utf-8")

    try:
        preset_name = args.preset or ("latin" if args.split else "")
        preset_cps = ranges.preset(preset_name) if preset_name else set()
        if args.unicodes:
            preset_cps |= ranges.parse_unicode_range(args.unicodes)
        features = F.resolve_features(args.features)
        axis_limits = F.parse_axis_limits(args.axis)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not page_cps and not preset_cps:
        print("error: give at least one text source (--url, --html, --chars, --text) "
              "or --preset/--unicodes", file=sys.stderr)
        return 2
    if args.split and not page_cps:
        print("error: --split needs a text source for the page file", file=sys.stderr)
        return 2
    if not F.have_brotli():
        print("warning: " + F.BROTLI_MESSAGE, file=sys.stderr)

    overrides = {"family": args.family, "weight": args.weight, "style": args.style}
    results = []
    for path in args.fonts:
        try:
            results.append(F.process_font(path, page_cps, preset_cps, args.out, split=args.split,
                                          features=features, hinting=not args.no_hinting,
                                          axis_limits=axis_limits, overrides=overrides))
        except (OSError, ValueError) as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            return 2
    css_path = Path(args.css) if args.css else Path(args.out) / "fonts.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(stylesheet(results, args.url_prefix, args.font_display), encoding="utf-8")

    if args.json:
        data = json_report(results, pages, len(page_cps), len(preset_cps))
        data["css"] = str(css_path)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        say(text_report(results, pages, len(page_cps), len(preset_cps)))
        say(f"css: {css_path}")
    return 0
