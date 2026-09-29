# font-subsetter

Cut web fonts down to the characters your site **actually renders**, and get WOFF2 files plus the matching `@font-face` CSS.

```
font-subsetter fonts/*.woff2 --url https://example.com/en/ --follow-hreflang --split --url-prefix /fonts/
```

- **Text from the rendered page.** URLs are loaded in headless Chromium, so the character set includes text built by JavaScript, `::before`/`::after` content, `text-transform: uppercase`, placeholders, `alt`/`title`/`aria-label` and form values. Local HTML files, character files and named ranges work too.
- **`--split` so nothing breaks when content changes.** Two files per font: the characters your pages use, and the rest of the language set, with **non-overlapping `unicode-range`**. Browsers download the second file only when a page needs one of its characters.
- **CSS you can paste.** `font-family`, `font-weight` (a range for variable fonts), `font-style`, `font-display: swap`, `unicode-range` and `src`, read from the font or overridden.
- **A report that says what was lost.** Sizes before/after, page characters the font does not have (they fall back to a system font), font characters removed and OpenType features dropped. Text or `--json`.
- **Polite.** GET only, robots.txt checked with RFC 9309 rules, one page at a time, 1 s apart, `/cdn-cgi/` skipped, nothing clicked or submitted.

## Measured result

The 4 self-hosted fonts of [demarkstudio.ca/en/](https://demarkstudio.ca/en/) (my own site), subset for the English and French pages. Run from Miramichi, NB, September 2026. These are **offline results**: the live site still serves the original files.

```
$ font-subsetter demo/fonts/*.woff2 --url https://demarkstudio.ca/en/ --url https://demarkstudio.ca/fr/conception-web/miramichi --follow-hreflang --max-pages 6 --split --out demo/split --url-prefix /static/fonts/ --dump-chars demo/chars.txt
reading https://demarkstudio.ca/en/
reading https://demarkstudio.ca/fr/conception-web/miramichi
reading https://demarkstudio.ca/en/web-design/miramichi
page  https://demarkstudio.ca/en/  HTTP 200, 83 distinct characters
page  https://demarkstudio.ca/fr/conception-web/miramichi  HTTP 200, 82 distinct characters
page  https://demarkstudio.ca/en/web-design/miramichi  HTTP 200, 72 distinct characters

characters requested: 96 from the text sources, 387 from presets/ranges

cormorant-garamond-italic-latin.woff2  Cormorant Garamond, 300 700, italic  variable: wght 300-700
  before  woff2    39.3 KB  231 characters, 374 glyphs
  page    woff2    18.4 KB  94 characters  -53.2%  cormorant-garamond-italic-latin.page.woff2
  rest    woff2    16.0 KB  130 characters  -59.3%  cormorant-garamond-italic-latin.rest.woff2
  features in subset: kern, liga, locl, mark, mkmk
  features dropped (--features): calt, dnom, frac, lnum, numr, pnum, tnum
  page characters not in this font (they fall back): ✓ ⤢
  preset characters not in this font: 98
  font characters removed: 7 (U+0000 U+000D U+0300 U+0301 U+0303 U+0309 U+0323)

cormorant-garamond-latin.woff2  Cormorant Garamond, 300 700, normal  variable: wght 300-700
  before  woff2    37.6 KB  229 characters, 373 glyphs
  page    woff2    17.4 KB  94 characters  -53.7%  cormorant-garamond-latin.page.woff2
  rest    woff2    15.1 KB  130 characters  -59.8%  cormorant-garamond-latin.rest.woff2
  features in subset: kern, liga, locl, mark, mkmk
  features dropped (--features): calt, dnom, frac, lnum, numr, tnum
  page characters not in this font (they fall back): ✓ ⤢
  preset characters not in this font: 98
  font characters removed: 5 (U+0300 U+0301 U+0303 U+0309 U+0323)

instrument-sans-normal-latin.woff2  Instrument Sans, 400 700, normal  variable: wght 400-700
  before  woff2    30.1 KB  208 characters, 244 glyphs
  page    woff2    15.4 KB  93 characters  -48.8%  instrument-sans-normal-latin.page.woff2
  rest    woff2    11.7 KB  111 characters  -61.1%  instrument-sans-normal-latin.rest.woff2
  features in subset: kern, liga, locl, mark, mkmk
  features dropped (--features): pnum, tnum
  page characters not in this font (they fall back): ¹ ✓ ⤢
  preset characters not in this font: 117
  font characters removed: 4 (Ă U+0300 U+0301 U+0303)

jetbrains-mono-latin.woff2  JetBrains Mono, 400 800, normal  variable: wght 400-800
  before  woff2    31.4 KB  229 characters, 394 glyphs
  page    woff2     8.1 KB  94 characters  -74.3%  jetbrains-mono-latin.page.woff2
  rest    woff2     9.5 KB  128 characters  -69.7%  jetbrains-mono-latin.rest.woff2
  features in subset: ccmp, locl, mark
  features dropped (--features): calt, frac
  page characters not in this font (they fall back): ✓ ⤢
  preset characters not in this font: 100
  font characters removed: 7 (U+000D Ă U+0300 U+0301 U+0303 U+0309 U+0323)

total: 138.4 KB -> 111.6 KB (-19.3%); page files only: 59.3 KB (-57.2%)
css: demo\split\fonts.css
```

The full report and the generated CSS are in [examples/demarkstudio-split-report.txt](examples/demarkstudio-split-report.txt) and [examples/demarkstudio-fonts.css](examples/demarkstudio-fonts.css). Other runs on the same files and characters (no extra page loads, `--chars demo/chars.txt`), next to [web-font-audit](https://github.com/dreadmoreeee/web-font-audit) run on /en/ the same day:

| 4 files, WOFF2 | Total | vs served |
|---|---:|---:|
| Served by the site | 138.4 KB | |
| web-font-audit "Latin subset" estimate (code points only) | 132.5 KB | -4.3% |
| `--preset latin --features '*'` (code points only) | 128.7 KB | -7.0% |
| `--preset latin` (default features) | 103.2 KB | -25.4% |
| 3 pages' characters, `--features '*'` | 69.4 KB | -49.9% |
| 3 pages' characters, default features (= the `--split` page files) | 59.3 KB | -57.1% |
| web-font-audit "page-only" ceiling, /en/ only, per face | 31.0 KB | -77.6% |

What that says, honestly:

- **The fonts are already Latin subsets**, as web-font-audit reported. Dropping code points alone saves 4 to 7%. The two tools agree; the gap between them is glyph names, which web-font-audit keeps for its estimate and this tool drops (the fontTools default), about 0.5 to 1 KB per file.
- **Most of the default saving comes from OpenType features, not characters.** With the Latin set, keeping `calt` in JetBrains Mono (its code ligatures) adds 14.6 KB to a 14.7 KB file, and keeping the numeral features (`tnum`, `lnum`, `pnum`, `frac`, `numr`, `dnom`) in Cormorant Garamond adds 4.2 KB. They are dropped only because the default keeps `kern`, `liga` and `locl`. If the site uses `font-variant-numeric` or the monospace ligatures, keep them: `--features +calt,+tnum`. The report lists every dropped feature for that reason.
- **The page files hold the characters of all three pages, for every font** (93 or 94, whatever each font has of the 96), so any page can use any font for any of its text. web-font-audit's page-only number assigns each character to the one face that renders it on /en/ alone (6 characters for the italic); it is a ceiling, not something to deploy site-wide.
- **Findings on the site:** ✓ and ⤢ are in none of the fonts and render in a system font (web-font-audit found the same on /en/). One of the two local web-design pages also renders a superscript ¹ that Instrument Sans lacks.
- With `--split`, a visitor whose page uses only those 94 characters downloads 59.3 KB instead of 138.4 KB. A page that uses one character outside them also downloads that font's `rest` file, so the worst case is 111.6 KB, still less than today.

Politeness for this demonstration: 11 page loads in total (one to capture the fonts, three runs of three pages while developing, one web-font-audit run), at least 1 s apart, robots.txt checked, GET only.

Tests run offline against local HTTP servers, with fonts generated by fontTools (kern, liga, locl and smcp features, a variable `wght` axis):

```
$ python -m pytest -q
....................................                                     [100%]
36 passed in 9.99s
```

## Install

```
pip install ".[woff2]"                 # fontTools, Playwright and brotli
python -m playwright install chromium  # only needed for --url
```

Python 3.10+. Dependencies: fontTools (MIT) and Playwright (Apache-2.0); `brotli` (MIT) is optional. `python -m font_subsetter` works too.

**Without brotli** WOFF2 cannot be written: the tool says so (`pip install brotli`) and writes WOFF files (zlib, larger) with `format("woff")` in the CSS. WOFF2 files can still be *read* without brotli: the compressed stream is served from a loopback-only server with `Content-Encoding: br` and decoded by Chromium.

## Usage

```
# Pages rendered in Chromium, plus their hreflang alternates on the same site
font-subsetter fonts/*.woff2 --url https://example.com/en/ --follow-hreflang --split

# A built static site (no browser), Latin kept as a safety net
font-subsetter fonts/Inter.ttf --html "public/**/*.html" --split --preset latin --url-prefix /fonts/

# Just the Google Fonts ranges
font-subsetter fonts/*.ttf --preset latin,latin-ext

# Save the characters once, reuse them in CI without loading pages again
font-subsetter fonts/*.woff2 --url https://example.ca/ --dump-chars chars.txt
font-subsetter fonts/*.woff2 --chars chars.txt --json > report.json
```

Output: `OUT/<name>.subset.woff2` (or `.page.woff2` and `.rest.woff2` with `--split`) and `OUT/fonts.css`:

```css
/* cormorant-garamond-italic-latin.woff2: page, 94 characters */
@font-face {
  font-family: "Cormorant Garamond";
  font-style: italic;
  font-weight: 300 700;
  font-display: swap;
  src: url("/static/fonts/cormorant-garamond-italic-latin.page.woff2") format("woff2");
  unicode-range: U+20, U+24-29, U+2C-2E, U+30-34, U+36-37, U+39-3B, U+3F-5A, U+61-7A, U+A0, U+A9, U+B7, U+B9, U+C0, U+C7, U+C9-CA, U+D7, U+E0, U+E7-EA, U+EE, U+F4, U+F9, U+2014, U+2039-203A;
}
```

[examples/github-actions.yml](examples/github-actions.yml) rebuilds the subsets from a built site in GitHub Actions. From Python:

```python
from font_subsetter import process_font, preset

result = process_font("Inter.ttf", {ord(c) for c in "Hello"}, preset("latin"), "out", split=True)
[(o.role, o.size) for o in result.outputs]
```

## Options

```
font-subsetter FONT [FONT ...] [--url URL] [--html FILE] [--chars FILE] [--text TEXT]
               [--preset latin,latin-ext] [--unicodes RANGE] [--case-variants]
               [--split] [--out DIR] [--css FILE] [--url-prefix PREFIX] [--font-display swap]
               [--features LIST] [--axis TAG=VALUE] [--no-hinting] [--family F] [--weight W] [--style S]
               [--follow-hreflang] [--max-pages 10] [--delay 1] [--timeout 30] [--user-agent UA]
               [--json] [--dump-chars FILE]
```

- Text sources combine: the page set is everything from `--url`, `--html`, `--chars` and `--text`; `--preset` and `--unicodes` add a language set. `--case-variants` adds the other case of every letter (for text that is transformed later).
- `--split` needs a text source; the language set defaults to `latin`.
- `--features`: `kern,liga` replaces the defaults (`kern`, `liga`, `locl`); `+calt,-liga` edits them; `*` keeps every feature. `ccmp`, `mark`, `mkmk`, `rlig`, `rvrn` and `curs` are always kept (browsers apply them to render accents and required forms) unless removed with `-name`.
- `--axis wght=400:700` narrows a variable axis, `--axis wght=400` pins it (the file becomes static). Without it, variable fonts keep all their axes and the CSS gets the weight range.
- Globs (`*`, `**`) in font, `--html` and `--chars` arguments are expanded by the tool, so they work in PowerShell and CI.
- Only the URLs given are loaded, plus same-host hreflang alternates with `--follow-hreflang`, up to `--max-pages`. User-Agent: `font-subsetter/1.0 (+https://github.com/dreadmoreeee/font-subsetter)`.
- Exit codes: `0` ok, `2` bad input (no characters in common with a font, unreadable file, no page loaded).

## Presets

The `unicode-range` values Google Fonts uses for these subsets:

| Preset | Range | Covers |
|---|---|---|
| `latin` | U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD | English, French, Spanish, German, Portuguese, Italian, Nordic; punctuation, euro |
| `latin-ext` | U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF | Central/Eastern European, Turkish, Baltic and other extended Latin; more currency signs |

As published, they overlap on seven code points; `--split` still gives non-overlapping ranges because the `rest` file is the language set minus the page characters.

## How it works

1. **Collect characters.** Each URL is loaded in headless Chromium (images, media and fonts blocked, since only text is needed) and a script walks the DOM, open shadow roots included: all text nodes (hidden ones too, since menus and dialogs open later) with their `text-transform` applied, `::before`/`::after` content (strings, `attr()`, counters, quotes), `alt`, `title`, `aria-label`, `placeholder` and input values (not passwords). Local HTML is parsed with the standard library: text, the same attributes and `content:` strings from `<style>` blocks.
2. **Read the font.** TTF, OTF, WOFF and WOFF2. Family comes from name ID 16 (or ID 1 without the default instance's style words, for variable fonts like "Cormorant Garamond Light"), weight from the `wght` axis or `usWeightClass`, style from `fsSelection`, `ital`/`slnt` axes or the italic angle.
3. **Subset with fontTools.** The requested code points that the font has, with layout closure (so ligatures and localized forms reachable from them stay), the chosen features, hinting unless `--no-hinting`, and name records 0-6, 13 and 14 (plus whatever `fvar`/`STAT` reference, so variable fonts stay valid).
4. **Write** WOFF2 (brotli) or WOFF, then the CSS with `unicode-range` equal to the code points each file really covers, and the report.

## Limitations

- All fonts get the same character set; the tool does not work out which face renders which character (web-font-audit does). That is the safe choice, not the smallest.
- Static HTML is not rendered: CSS classes are not applied, so `text-transform` from a stylesheet is missed (use `--case-variants` or `--url`). Text inside iframes, closed shadow roots, and strings shown only after clicks or form submissions that change the DOM are not seen.
- Content from `::marker` and CSS `counter()` is approximated with digits; `font-variant` alternates other than small caps are not modelled.
- `unicode-range` protects against characters missing from a subset only when a `rest` file (or another `@font-face`) covers them; otherwise they render in a fallback font.
- Font collections (`.ttc`), color bitmap tables and CFF2 edge cases are passed to fontTools as they are and not specially tested.
- Font licenses: subsetting is a modification. OFL and most open licenses allow it (the OFL asks that a modified font not use a Reserved Font Name); check the license of commercial fonts.

## Author

Marvin Palencia, founder of [DeMark Studio](https://demarkstudio.ca), Miramichi, New Brunswick, Canada. Portfolio: [marvin.demarkstudio.ca](https://marvin.demarkstudio.ca)

MIT License.
