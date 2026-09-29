"""Headless Chromium: rendered page text, and brotli decoding without brotli."""
from __future__ import annotations

import http.server
import itertools
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

from . import rfc9309

USER_AGENT = "font-subsetter/1.0 (+https://github.com/dreadmoreeee/font-subsetter)"
_SCRIPT = (Path(__file__).with_name("collect.js")).read_text(encoding="utf-8")


@dataclass
class Page:
    url: str
    status: int | None = None
    text: str = ""
    lang: str = ""
    skipped: str = ""
    alternates: list[dict] = field(default_factory=list)


def _sync_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise SystemExit("Reading URLs needs Playwright: pip install playwright && "
                         "python -m playwright install chromium") from e
    return sync_playwright


def fetch_pages(urls, *, delay: float = 1.0, timeout: float = 30.0, user_agent: str = USER_AGENT,
                follow_hreflang: bool = False, max_pages: int = 10, log=print) -> list[Page]:
    """Load each URL in headless Chromium (GET only, nothing clicked or
    submitted), one at a time and `delay` seconds apart, after checking
    robots.txt (RFC 9309). With follow_hreflang, same-host hreflang alternates
    of the given pages are added, up to max_pages loads in total."""
    queue = [urldefrag(u)[0] for u in urls]
    seen: set[str] = set()
    robots: dict[str, rfc9309.RobotsTxt] = {}
    pages: list[Page] = []
    loads = 0
    last = 0.0
    with _sync_playwright()() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(user_agent=user_agent)
            # Images, media and fonts are not needed to read text.
            context.route("**/*", lambda route: route.abort()
                          if route.request.resource_type in ("image", "media", "font")
                          else route.continue_())
            while queue:
                url = queue.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                parts = urlsplit(url)
                page_rec = Page(url)
                pages.append(page_rec)
                if parts.scheme not in ("http", "https"):
                    page_rec.skipped = "not an http(s) URL"
                    continue
                if "/cdn-cgi/" in parts.path:
                    page_rec.skipped = "/cdn-cgi/ path"
                    continue
                if loads >= max_pages:
                    page_rec.skipped = f"--max-pages {max_pages} reached"
                    continue
                origin = f"{parts.scheme}://{parts.netloc}"
                if origin not in robots:
                    robots[origin] = rfc9309.fetch(origin, user_agent=user_agent, timeout=timeout)
                if not robots[origin].can_fetch(user_agent, url):
                    page_rec.skipped = "disallowed by robots.txt"
                    log(f"skip {url}: disallowed by robots.txt")
                    continue
                wait = last + delay - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                log(f"reading {url}")
                page = context.new_page()
                loads += 1
                try:
                    resp = page.goto(url, wait_until="load", timeout=timeout * 1000)
                    page_rec.status = resp.status if resp else None
                    if resp is not None and resp.status >= 400:
                        page_rec.skipped = f"HTTP {resp.status}"
                        continue
                    page.wait_for_timeout(300)
                    data = page.evaluate(_SCRIPT)
                except Exception as e:  # timeouts, DNS errors, crashed pages
                    page_rec.skipped = f"error: {str(e).splitlines()[0]}"
                    log(f"skip {url}: {page_rec.skipped}")
                    continue
                finally:
                    last = time.monotonic()
                    page.close()
                page_rec.text = data["text"]
                page_rec.lang = data["lang"]
                page_rec.alternates = data["alternates"]
                if follow_hreflang:
                    for alt in data["alternates"]:
                        href = urldefrag(alt["href"])[0]
                        if urlsplit(href).netloc == parts.netloc and href not in seen:
                            queue.append(href)
        finally:
            browser.close()
    return pages


class _BlobHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        data = self.server.blobs.pop(self.path, None)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Encoding", "br")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class BrotliBridge:
    """Decompress brotli data without the brotli package: serve it from a
    loopback-only server with Content-Encoding: br and let Chromium's network
    stack decode it. Nothing leaves the machine. Use as a context manager."""

    def __enter__(self):
        self._pw = _sync_playwright()().start()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BlobHandler)
        self._server.blobs = {}
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self._request = self._pw.request.new_context()
        self._ids = itertools.count(1)
        return self

    def decompress(self, data: bytes) -> bytes:
        path = f"/blob/{next(self._ids)}"
        self._server.blobs[path] = bytes(data)
        response = self._request.get(f"http://127.0.0.1:{self._server.server_address[1]}{path}")
        if response.status != 200:
            raise ValueError("brotli decoding through Chromium failed")
        return response.body()

    def __exit__(self, *exc):
        try:
            self._request.dispose()
            self._pw.stop()
        finally:
            self._server.shutdown()
            self._server.server_close()
