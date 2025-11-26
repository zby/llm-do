from __future__ import annotations

import ssl
from html.parser import HTMLParser
import socket
import time
from typing import List
from urllib import request
from urllib.error import HTTPError, URLError

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_FETCH_BYTES = 1_000_000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def fetch_page(url: str, max_chars: int = 4000) -> str:
    """
    Fetch a URL and return cleaned text content.

    Uses a small HTML parser to drop script/style blocks and collapses
    whitespace. The result is truncated to keep token counts manageable.
    Common fetch failures (403/404/429/connection errors) are swallowed,
    returning an empty string so the workflow can continue with other URLs.
    """
    sanitized = (url or "").strip()
    if not sanitized:
        raise ValueError("URL is required")
    if not sanitized.startswith(("http://", "https://")):
        raise ValueError("Only http/https URLs are allowed")

    req = request.Request(
        sanitized,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.8"},
    )
    attempts = 2
    raw = b""
    charset = "utf-8"
    for attempt in range(attempts):
        try:
            with request.urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
                content_length = resp.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > MAX_FETCH_BYTES:
                            return ""
                    except ValueError:
                        # Ignore bad headers; enforce streaming limit below.
                        pass

                charset = resp.headers.get_content_charset() or "utf-8"
                raw = resp.read(MAX_FETCH_BYTES + 1)
                break
        except HTTPError as exc:
            if exc.code in {403, 404, 429}:
                return ""
            raise
        except (URLError, socket.timeout) as exc:
            is_timeout = isinstance(exc, socket.timeout) or isinstance(getattr(exc, "reason", None), socket.timeout)
            if is_timeout and attempt + 1 < attempts:
                time.sleep(0.5)
                continue
            return ""

    if len(raw) > MAX_FETCH_BYTES:
        return ""

    text = raw.decode(charset, errors="replace")
    parser = _TextExtractor()
    parser.feed(text)
    cleaned = " ".join(parser.get_text().split())

    if max_chars > 0:
        return cleaned[:max_chars]
    return cleaned
