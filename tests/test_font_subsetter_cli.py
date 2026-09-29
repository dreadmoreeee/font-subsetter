import json
import subprocess
import sys
from pathlib import Path

from font_subsetter import ranges
from font_subsetter.cli import main

TOOL = Path(__file__).resolve().parents[1]


def write_page(tmp_path):
    page = tmp_path / "page.html"
    page.write_text("<h1>Bonjour \u00e0 tous</h1><p title='\u20ac5'>fi AV</p><p>\u2713 done</p>",
                    encoding="utf-8")
    return page


def test_cli_html_json_and_css(tmp_path, test_font, fake_brotli, capsys):
    out = tmp_path / "out"
    code = main([str(test_font), "--html", str(write_page(tmp_path)), "--out", str(out),
                 "--url-prefix", "/fonts/", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    [font] = data["fonts"]
    assert font["family"] == "Test Sans" and font["format"] == "ttf"
    assert font["missing_page_characters"] == "\u2713"
    [o] = font["outputs"]
    assert o["role"] == "subset" and o["format"] == "woff2" and o["size"] < font["size"]
    assert "\u20ac" not in font["removed_characters"] and "Z" in font["removed_characters"]
    assert data["total"]["after"] == o["size"]
    sheet = (out / "fonts.css").read_text(encoding="utf-8")
    assert 'url("/fonts/test-sans.subset.woff2")' in sheet
    assert ranges.parse_unicode_range(sheet.split("unicode-range:")[1].split(";")[0]) == \
        {ord(c) for c in "Bonjour \u00e0tus\u20ac5fiAVdne"}


def test_cli_split_text_report(tmp_path, test_font, italic_font, fake_brotli, capsys):
    code = main([str(test_font), str(italic_font), "--text", "Caf\u00e9", "--split",
                 "--out", str(tmp_path / "o"), "--css", str(tmp_path / "f.css")])
    assert code == 0
    report = capsys.readouterr().out
    assert not any(line.startswith("page  ") for line in report.splitlines())  # no URLs
    assert report.count("test-sans.page.woff2") == 1 and "test-sans-italic.rest.woff2" in report
    assert "page files only:" in report
    sheet = (tmp_path / "f.css").read_text(encoding="utf-8")
    assert sheet.count("@font-face") == 4 and "font-style: italic;" in sheet


def test_cli_brotli_missing_message(tmp_path, test_font, no_brotli, capsys):
    code = main([str(test_font), "--preset", "latin", "--out", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "pip install brotli" in captured.err
    assert (tmp_path / "test-sans.subset.woff").exists()
    assert 'format("woff")' in (tmp_path / "fonts.css").read_text(encoding="utf-8")


def test_cli_dump_chars_and_reuse(tmp_path, test_font, fake_brotli):
    chars = tmp_path / "chars.txt"
    assert main([str(test_font), "--text", "abc", "--case-variants", "--dump-chars", str(chars),
                 "--out", str(tmp_path / "a")]) == 0
    assert chars.read_text(encoding="utf-8") == " ABCabc"
    assert main([str(test_font), "--chars", str(chars), "--out", str(tmp_path / "b")]) == 0


def test_cli_expands_globs(tmp_path, test_font, italic_font, fake_brotli, capsys):
    pages = tmp_path / "site" / "fr"
    pages.mkdir(parents=True)
    (pages / "index.html").write_text("<p>\u00e7a</p>", encoding="utf-8")
    code = main([str(tmp_path / "*.ttf"), "--html", str(tmp_path / "site" / "**" / "*.html"),
                 "--out", str(tmp_path / "out"), "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["fonts"]) == 2 and data["requested"]["text_sources"] == 3  # space, c-cedilla, a
    assert main([str(tmp_path / "*.otf"), "--text", "a"]) == 2


def test_cli_errors(tmp_path, test_font, capsys):
    out = ["--out", str(tmp_path / "out")]
    assert main([str(test_font), *out]) == 2
    assert "at least one text source" in capsys.readouterr().err
    assert main([str(test_font), "--preset", "nope", *out]) == 2
    assert main([str(test_font), "--preset", "latin", "--split", *out]) == 2
    assert main([str(test_font), "--text", "\u2713", *out]) == 2
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"not a font")
    assert main([str(bad), "--text", "a", *out]) == 2
    assert not (tmp_path / "out").exists()


def test_module_entry_point(tmp_path, test_font):
    proc = subprocess.run([sys.executable, "-m", "font_subsetter", "--version"], cwd=TOOL,
                          capture_output=True, text=True)
    assert proc.returncode == 0 and proc.stdout.startswith("font-subsetter 1.0.0")
