"""Subset web fonts to the characters a site uses; write WOFF2 and @font-face CSS."""
from __future__ import annotations

__version__ = "1.0.0"

from .fonts import FontResult, process_font, resolve_features  # noqa: E402
from .ranges import PRESETS, format_unicode_range, parse_unicode_range, preset  # noqa: E402
from .textsources import html_text  # noqa: E402

__all__ = ["process_font", "FontResult", "resolve_features", "PRESETS", "preset",
           "parse_unicode_range", "format_unicode_range", "html_text", "__version__"]
