import functools
import http.server
import string
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString  # noqa: E402
from fontTools.fontBuilder import FontBuilder  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.ttLib import woff2  # noqa: E402
from fontTools.ttLib.tables.TupleVariation import TupleVariation  # noqa: E402

CHARS = string.ascii_letters + string.digits + " .,-!?'\u00e9\u00e0\u00e7\u00c9\u20ac\u2013\u2019"
FEATURES = """
languagesystem DFLT dflt;
languagesystem latn dflt;
languagesystem latn TRK;
feature liga { sub uni0066 uni0069 by f_i; } liga;
feature locl { script latn; language TRK exclude_dflt; sub uni0069 by i.loclTRK; } locl;
feature smcp { sub uni0061 by a.sc; } smcp;
feature kern { pos uni0041 uni0056 -80; pos uni0054 uni006F -60; } kern;
"""


def build_font(path, family="Test Sans", weight=400, italic=False, variable=False, instances=()):
    """A small TrueType font generated with fontTools (no third-party font
    files needed): rectangles as glyphs, kern/liga/locl/smcp features."""
    fb = FontBuilder(1000, isTTF=True)
    cmap = {ord(c): f"uni{ord(c):04X}" for c in CHARS}
    names = [".notdef"] + list(cmap.values()) + ["f_i", "i.loclTRK", "a.sc"]
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    glyphs, metrics = {}, {}
    for i, name in enumerate(names):
        pen = TTGlyphPen(None)
        width = 500 + (i % 5) * 20
        if name != "uni0020":
            pen.moveTo((50, 0))
            pen.lineTo((50, 600 + i))
            pen.lineTo((width - 50, 600 + i))
            pen.lineTo((width - 50, 0))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (width, 50)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    style = "Italic" if italic else "Regular"
    fb.setupNameTable({"familyName": family, "styleName": style,
                       "copyright": "Copyright 2026 Example Type Co.",
                       "licenseDescription": "SIL Open Font License 1.1",
                       "designer": "Jane Example", "description": "Test font"})
    fb.setupOS2(usWeightClass=weight, fsSelection=0x01 if italic else 0x40,
                sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(italicAngle=-10 if italic else 0)
    if italic:
        fb.font["head"].macStyle = 2
    if variable:
        fb.setupFvar(axes=[("wght", 100, 400, 900, "Weight")],
                     instances=[{"location": {"wght": w}, "stylename": n} for w, n in instances])
        fb.setupGvar({"uni0041": [TupleVariation({"wght": (0, 1, 1)}, [(30, 0)] * 8)]})
    addOpenTypeFeaturesFromString(fb.font, FEATURES)
    fb.save(str(path))
    return Path(path)


@pytest.fixture
def test_font(tmp_path):
    return build_font(tmp_path / "test-sans.ttf")


@pytest.fixture
def italic_font(tmp_path):
    return build_font(tmp_path / "test-sans-italic.ttf", italic=True, weight=700)


@pytest.fixture
def make_font(tmp_path):
    return lambda name, **kw: build_font(tmp_path / name, **kw)


@pytest.fixture
def variable_font(tmp_path):
    return build_font(tmp_path / "test-sans-var.ttf", variable=True)


# --- brotli stand-ins -------------------------------------------------------

def stored_brotli(data: bytes) -> bytes:
    """A valid brotli stream made only of uncompressed meta-blocks (RFC 7932
    9.2). Lets tests write real WOFF2 files without the brotli package."""
    out = bytearray()
    acc = nbits = 0

    def put(value, n):
        nonlocal acc, nbits
        acc |= value << nbits
        nbits += n
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8

    def align():
        if nbits % 8:
            put(0, 8 - nbits % 8)

    put(0, 1)                       # WBITS = 16
    for i in range(0, len(data), 65536):
        chunk = data[i:i + 65536]
        put(0, 1)                   # ISLAST = 0
        put(0, 2)                   # MNIBBLES = 4
        put(len(chunk) - 1, 16)     # MLEN - 1
        put(1, 1)                   # ISUNCOMPRESSED
        align()
        out += chunk
    put(1, 1)                       # ISLAST
    put(1, 1)                       # ISLASTEMPTY
    align()
    return bytes(out)


def stored_unbrotli(data: bytes) -> bytes:
    """Decoder for stored_brotli output only."""
    bits = int.from_bytes(data, "little")
    bitpos = 1
    out = bytearray()
    while True:
        islast = (bits >> bitpos) & 1
        if islast:
            return bytes(out)
        mlen = ((bits >> (bitpos + 3)) & 0xFFFF) + 1
        bitpos += 1 + 2 + 16 + 1
        pos = (bitpos + 7) // 8
        out += data[pos:pos + mlen]
        bitpos = (pos + mlen) * 8


@pytest.fixture
def fake_brotli(monkeypatch):
    """Pretend brotli is installed, with stored (uncompressed) streams."""
    module = SimpleNamespace(compress=lambda d, mode=0, **kw: stored_brotli(d),
                             decompress=stored_unbrotli, MODE_GENERIC=0, MODE_TEXT=1, MODE_FONT=2)
    monkeypatch.setattr(woff2, "haveBrotli", True)
    monkeypatch.setattr(woff2, "brotli", module, raising=False)
    return module


@pytest.fixture
def no_brotli(monkeypatch):
    monkeypatch.setattr(woff2, "haveBrotli", False)
    monkeypatch.setattr(woff2, "brotli", None, raising=False)


# --- local web server -------------------------------------------------------

FORBIDDEN_PORTS = {8765, 8737, 8787}


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path):
    """Serve tmp_path/site on 127.0.0.1 at a random free port."""
    root = tmp_path / "site"
    root.mkdir()
    handler = functools.partial(_QuietHandler, directory=str(root))
    while True:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        if server.server_address[1] not in FORBIDDEN_PORTS:
            break
        server.server_close()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(root=root, url=f"http://127.0.0.1:{server.server_address[1]}")
    server.shutdown()
    server.server_close()

