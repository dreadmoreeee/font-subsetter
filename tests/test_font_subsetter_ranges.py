import pytest

from font_subsetter import ranges


def test_parse_and_format_round_trip():
    cps = ranges.parse_unicode_range("U+0041-0043, U+E9,U+2013")
    assert cps == {0x41, 0x42, 0x43, 0xE9, 0x2013}
    assert ranges.format_unicode_range(cps) == "U+41-43, U+E9, U+2013"
    assert ranges.parse_unicode_range(ranges.format_unicode_range(cps)) == cps


def test_wildcard_and_errors():
    assert ranges.parse_unicode_range("U+4??") == set(range(0x400, 0x500))
    for bad in ("U+ZZ", "U+50-40", "0041", "U+110000"):
        with pytest.raises(ValueError):
            ranges.parse_unicode_range(bad)


def test_latin_preset_matches_google_fonts():
    latin = ranges.preset("latin")
    for ch in "Aa\u00e9\u00e0\u00e7\u00c9\u0153\u0152\u20ac\u2013\u2014\u2019\u201c\u2122":
        assert ord(ch) in latin, ch
    assert 0x0142 not in latin  # l with stroke (Polish) is latin-ext
    assert len(latin) == 256 + 1 + 2 + 2 + 1 + 1 + 1 + 3 + 0x70 + 1 + 1 + 2 + 2 + 2


def test_latin_ext_preset_and_overlap():
    latin, ext = ranges.preset("latin"), ranges.preset("latin-ext")
    assert {0x0142, 0x0151, 0x1E9E, 0x20BA} <= ext
    # Google's two ranges overlap on these code points; kept as published.
    assert latin & ext == {0x0131, 0x0152, 0x0153, 0x0304, 0x0308, 0x0329, 0x2020}
    assert ranges.preset("latin,latin-ext") == latin | ext
    with pytest.raises(ValueError):
        ranges.preset("klingon")


def test_to_ranges_merges():
    assert ranges.to_ranges([5, 1, 2, 3, 9, 10]) == [(1, 3), (5, 5), (9, 10)]


def test_describe_shows_marks_and_spaces_as_code_points():
    assert ranges.describe({0x41, 0x301, 0xA0}) == "A U+00A0 U+0301"
    assert ranges.describe(range(0x41, 0x41 + 5), limit=2) == "A B ... (+3)"
