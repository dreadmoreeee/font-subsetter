from io import BytesIO

import pytest
from fontTools.ttLib import TTFont

from font_subsetter import css, fonts as F, ranges


def cps(text):
    return {ord(c) for c in text}


def gsub_features(font):
    tags = set()
    for tag in ("GSUB", "GPOS"):
        if tag in font:
            tags |= {r.FeatureTag for r in font[tag].table.FeatureList.FeatureRecord}
    return tags


def test_subset_keeps_only_requested_characters(tmp_path, test_font, fake_brotli):
    r = F.process_font(test_font, cps("Hello "), set(), tmp_path / "out")
    [out] = r.outputs
    assert out.path.name == "test-sans.subset.woff2" and out.fmt == "woff2"
    font = TTFont(str(out.path))
    assert font.flavor == "woff2"
    assert set(font.getBestCmap()) == cps("Helo ")
    assert out.size < r.source_size
    assert cps("Z\u20ac") <= r.removed and not (cps("Helo") & r.removed)


def test_default_features_kept_and_others_dropped(tmp_path, test_font, fake_brotli):
    # "fi" keeps the liga lookup alive, "AV"/"To" the kern pairs, "i" the locl one.
    r = F.process_font(test_font, cps("fi AV To a"), set(), tmp_path)
    font = TTFont(str(r.outputs[0].path))
    assert {"kern", "liga", "locl"} <= gsub_features(font)
    assert "smcp" not in gsub_features(font)
    assert r.features_dropped == {"smcp"}
    # .notdef + 8 characters + the f_i ligature and the Turkish i; no small cap a.
    assert len(font.getGlyphOrder()) == 11


def test_features_option(tmp_path, test_font, fake_brotli):
    r = F.process_font(test_font, cps("fi AV a"), set(), tmp_path / "a",
                       features=F.resolve_features("+smcp,-liga"))
    tags = gsub_features(TTFont(str(r.outputs[0].path)))
    assert "smcp" in tags and "liga" not in tags and "kern" in tags
    r = F.process_font(test_font, cps("fi AV a"), set(), tmp_path / "b", features=F.resolve_features("*"))
    assert {"smcp", "liga", "kern", "locl"} <= gsub_features(TTFont(str(r.outputs[0].path)))


def test_resolve_features():
    assert F.resolve_features(None)[-3:] == ["kern", "liga", "locl"]
    assert F.resolve_features("kern") == list(F.REQUIRED_FEATURES) + ["kern"]
    assert "liga" not in F.resolve_features("-liga")
    assert F.resolve_features("*") == ["*"]
    with pytest.raises(ValueError):
        F.resolve_features("toolong")


def test_name_table_minimal_but_valid(tmp_path, test_font, fake_brotli):
    r = F.process_font(test_font, cps("abc"), set(), tmp_path)
    font = TTFont(str(r.outputs[0].path))
    ids = {n.nameID for n in font["name"].names}
    assert ids <= set(F.NAME_IDS)
    assert {0, 1, 2, 13} <= ids  # copyright and license kept, designer/description gone
    assert font["name"].getDebugName(1) == "Test Sans"
    font.save(BytesIO())  # compiles


def test_font_info_reads_family_weight_style(italic_font, variable_font, test_font):
    info = F.font_info(TTFont(str(italic_font)))
    assert (info.family, info.weight, info.style) == ("Test Sans", "700", "italic")
    info = F.font_info(TTFont(str(variable_font)))
    assert info.weight == "100 900" and info.axes["wght"] == (100, 400, 900)
    assert F.font_info(TTFont(str(test_font))).style == "normal"


def test_variable_family_drops_default_instance_style(make_font):
    path = make_font("serif.ttf", family="Test Serif Light", variable=True,
                     instances=[(100, "Thin"), (400, "Light"), (900, "Black")])
    assert F.font_info(TTFont(str(path))).family == "Test Serif"


def test_variable_font_keeps_axes_or_pins_them(tmp_path, variable_font, fake_brotli):
    r = F.process_font(variable_font, cps("ABC"), set(), tmp_path / "full")
    font = TTFont(str(r.outputs[0].path))
    assert "fvar" in font and "gvar" in font
    assert "font-weight: 100 900;" in css.stylesheet([r])

    r = F.process_font(variable_font, cps("ABC"), set(), tmp_path / "narrow",
                       axis_limits=F.parse_axis_limits(["wght=400:700"]))
    assert "font-weight: 400 700;" in css.stylesheet([r])

    r = F.process_font(variable_font, cps("ABC"), set(), tmp_path / "pinned",
                       axis_limits=F.parse_axis_limits(["wght=700"]))
    font = TTFont(str(r.outputs[0].path))
    assert "fvar" not in font and "gvar" not in font
    assert font["OS/2"].usWeightClass == 700
    assert "font-weight: 700;" in css.stylesheet([r])


def test_split_ranges_do_not_overlap_and_cover_the_set(tmp_path, test_font, fake_brotli):
    page = cps("Caf\u00e9 fi ")
    latin = ranges.preset("latin")
    r = F.process_font(test_font, page, latin, tmp_path, split=True)
    page_out, rest_out = r.outputs
    assert (page_out.role, rest_out.role) == ("page", "rest")
    assert page_out.codepoints & rest_out.codepoints == set()
    assert page_out.codepoints | rest_out.codepoints == (page | latin) & r.info.codepoints
    sheet = css.stylesheet([r])
    got = [ranges.parse_unicode_range(line.split(":", 1)[1].rstrip(";"))
           for line in sheet.splitlines() if "unicode-range" in line]
    assert len(got) == 2 and not (got[0] & got[1])
    assert got[0] == page_out.codepoints
    # The euro sign is in the font and in latin but not on the page: rest file.
    assert 0x20AC in rest_out.codepoints
    assert set(TTFont(str(rest_out.path)).getBestCmap()) >= rest_out.codepoints


def test_missing_characters_are_reported(tmp_path, test_font, fake_brotli):
    r = F.process_font(test_font, cps("abc\u2713\u00df"), cps("\u0142"), tmp_path)
    assert r.missing_page == cps("\u2713\u00df")
    assert r.missing_preset == cps("\u0142")
    with pytest.raises(ValueError):
        F.process_font(test_font, cps("\u2713"), set(), tmp_path)


def test_woff_fallback_without_brotli(tmp_path, test_font, no_brotli):
    assert not F.have_brotli()
    r = F.process_font(test_font, cps("abc"), set(), tmp_path)
    [out] = r.outputs
    assert out.fmt == "woff" and out.path.suffix == ".woff"
    assert TTFont(str(out.path)).flavor == "woff"
    assert 'format("woff")' in css.stylesheet([r])


def test_reads_woff_input(tmp_path, test_font, fake_brotli):
    font = TTFont(str(test_font))
    font.flavor = "woff"
    src = tmp_path / "in.woff"
    font.save(str(src))
    r = F.process_font(src, cps("abc"), set(), tmp_path / "out")
    assert r.source_format == "woff" and r.outputs[0].fmt == "woff2"


def test_css_font_face(tmp_path, italic_font, fake_brotli):
    r = F.process_font(italic_font, cps(" ab"), set(), tmp_path, overrides={"family": 'My "Font"'})
    sheet = css.stylesheet([r], url_prefix="/fonts/")
    assert 'font-family: "My \\"Font\\"";' in sheet
    assert "font-style: italic;" in sheet and "font-weight: 700;" in sheet
    assert "font-display: swap;" in sheet
    assert 'src: url("/fonts/test-sans-italic.subset.woff2") format("woff2");' in sheet
    assert "unicode-range: U+20, U+61-62;" in sheet
