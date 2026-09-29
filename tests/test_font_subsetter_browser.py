"""Tests that run headless Chromium against a local http.server (no internet)."""
import json

from fontTools.ttLib import TTFont

from font_subsetter import fonts as F
from font_subsetter.browser import BrotliBridge, fetch_pages
from font_subsetter.cli import main

EN = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<link rel="alternate" hreflang="fr" href="/fr/">
<link rel="alternate" hreflang="en" href="/en/">
<link rel="alternate" hreflang="x-default" href="https://elsewhere.example.com/">
<style>
  .up { text-transform: uppercase; }
  .next::after { content: " \\2192"; }
  .quote::before { content: "\\201C" attr(data-who); }
  .hidden { display: none; }
</style></head>
<body>
<h1 class="up">shout</h1>
<a class="next" href="#">Next</a>
<blockquote class="quote" data-who="Kim\u00e9"></blockquote>
<input placeholder="Search \u00f1">
<img alt="Logo \u00d8" src="missing.png">
<div class="hidden">Menu \u00df</div>
<p id="late"></p>
<script>document.getElementById("late").textContent = "Added by script \u00a7";</script>
</body></html>"""

FR = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<link rel="alternate" hreflang="en" href="/en/"></head>
<body><p>Conception web \u00e0 Miramichi \u2014 \u00e7a marche</p></body></html>"""


def make_site(site, robots=None):
    (site.root / "en").mkdir()
    (site.root / "fr").mkdir()
    (site.root / "en" / "index.html").write_text(EN, encoding="utf-8")
    (site.root / "fr" / "index.html").write_text(FR, encoding="utf-8")
    (site.root / "private").mkdir()
    (site.root / "private" / "index.html").write_text("<meta charset=utf-8><p>secret \u00b5</p>", encoding="utf-8")
    if robots:
        (site.root / "robots.txt").write_text(robots, encoding="utf-8")


def test_rendered_text_includes_pseudo_content_transforms_and_attributes(site):
    make_site(site)
    [page] = fetch_pages([site.url + "/en/"], delay=0, log=lambda m: None)
    assert page.status == 200 and page.lang == "en"
    for s in ("SHOUT", "\u2192", "\u201cKim\u00e9", "Search \u00f1", "Logo \u00d8",
              "Menu \u00df", "Added by script \u00a7"):
        assert s in page.text, s
    assert {"hreflang": "fr", "href": site.url + "/fr/"} in page.alternates


def test_follow_hreflang_same_host_only_and_robots(site):
    make_site(site, robots="User-agent: *\nAllow: /\nDisallow: /private/\n")
    pages = fetch_pages([site.url + "/en/", site.url + "/private/", site.url + "/cdn-cgi/x"],
                        delay=0, follow_hreflang=True, log=lambda m: None)
    by_url = {p.url: p for p in pages}
    assert by_url[site.url + "/private/"].skipped == "disallowed by robots.txt"
    assert by_url[site.url + "/cdn-cgi/x"].skipped == "/cdn-cgi/ path"
    assert "\u00e7a marche" in by_url[site.url + "/fr/"].text
    assert not any("elsewhere" in u for u in by_url)
    assert "secret" not in "".join(p.text for p in pages)


def test_max_pages_and_http_errors(site):
    make_site(site)
    pages = fetch_pages([site.url + "/nope/", site.url + "/en/", site.url + "/fr/"],
                        delay=0, max_pages=2, log=lambda m: None)
    assert [p.skipped for p in pages] == ["HTTP 404", "", "--max-pages 2 reached"]


def test_cli_with_url(site, tmp_path, test_font, fake_brotli, capsys):
    make_site(site)
    code = main([str(test_font), "--url", site.url + "/fr/", "--delay", "0",
                 "--out", str(tmp_path / "out"), "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pages"][0]["lang"] == "fr"
    # The test font has the accents but no em dash.
    assert data["fonts"][0]["missing_page_characters"] == "\u2014"


def test_woff2_input_read_without_brotli(tmp_path, test_font, fake_brotli, monkeypatch):
    # Write a real WOFF2 file (stored brotli blocks), then read it with brotli "uninstalled".
    font = TTFont(str(test_font))
    font.flavor = "woff2"
    src = tmp_path / "in.woff2"
    font.save(str(src))
    with BrotliBridge() as bridge:
        assert bridge.decompress(fake_brotli.compress(b"hello" * 1000)) == b"hello" * 1000
    monkeypatch.setattr(F.woff2, "haveBrotli", False)
    monkeypatch.setattr(F.woff2, "brotli", None)
    r = F.process_font(src, {ord(c) for c in " abc"}, set(), tmp_path / "out")
    assert r.source_format == "woff2" and len(r.info.codepoints) == len(TTFont(str(test_font)).getBestCmap())
    assert r.outputs[0].fmt == "woff"
