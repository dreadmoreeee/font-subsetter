from font_subsetter import textsources as T

PAGE = """<!doctype html>
<html lang="fr"><head><title>Titre ignor\u00e9 \u00a7</title>
<style>.go::after { content: "\\2192"; } .q::before{content:'\u00ab '}</style>
<script>var s = "\u00a9 never shown";</script></head>
<body>
<h1>Caf\u00e9 &amp; cr\u00e8me</h1>
<img src="x.png" alt="Logo \u00d8">
<a title="Info \u00bf" aria-label="Menu \u00a1">x</a>
<input placeholder="Courriel \u00e0" value="Z\u00fc">
<input type="password" value="secret\u00b5">
<input type="submit" value="Envoyer \u00f1">
<p style="--x:1" class="go">Suite</p>
<noscript>\u00b6 no js</noscript>
<template><p>\u00be</p></template>
</body></html>"""


def test_html_text_collects_visible_text_and_attributes():
    text = T.html_text(PAGE)
    for s in ("Caf\u00e9", "&", "cr\u00e8me", "Logo \u00d8", "Info \u00bf", "Menu \u00a1",
              "Courriel \u00e0", "Z\u00fc", "Envoyer \u00f1", "Suite"):
        assert s in text, s


def test_html_text_skips_scripts_styles_head_and_passwords():
    text = T.html_text(PAGE)
    for ch in "\u00a9\u00a7\u00b6\u00be\u00b5":
        assert ch not in text, ch


def test_css_content_strings_are_included():
    text = T.html_text(PAGE)
    assert "\u2192" in text and "\u00ab" in text
    assert T.css_content_text('a::before { content: "\\201C" attr(x) "b\\"" }') == "\u201cb\""


def test_codepoints_drop_controls_and_keep_space():
    cps = T.codepoints_of("a\tb\nc\x85")
    assert cps == {ord("a"), ord("b"), ord("c"), 0x20}


def test_case_variants():
    cps = T.add_case_variants({ord("\u00e9"), ord("Q"), ord("1")})
    assert {ord("\u00c9"), ord("q"), ord("1")} <= cps
