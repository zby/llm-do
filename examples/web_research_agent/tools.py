"""Project-level tools for web research agent.

Combines tools from all sub-workers so they can be used from main.worker.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import socket
import time
from html.parser import HTMLParser
from typing import Dict, List
from urllib import parse, request
from urllib.error import HTTPError, URLError


# =============================================================================
# Web Search (from orchestrator)
# =============================================================================

USER_AGENT_SEARCH = "llm-do-web-research/0.1"
MAX_HTTP_BYTES = 1_000_000


def search_web(query: str, num_results: int = 4) -> List[Dict[str, str | None]]:
    """
    Run a web search using SerpAPI.

    Requires SERPAPI_API_KEY environment variable to be set.
    Returns a list of {url, title, snippet} dicts with duplicates removed.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    limit = max(1, min(num_results, 8))
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        raise ValueError(
            "SERPAPI_API_KEY environment variable is required. "
            "Get a free API key at https://serpapi.com/"
        )

    try:
        return _search_serpapi(cleaned_query, api_key, limit)
    except RuntimeError as exc:
        if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
            raise ValueError(
                f"SERPAPI_API_KEY is invalid or expired (got {exc}). "
                "Please check your API key at https://serpapi.com/manage-api-key"
            ) from exc
        raise


def _http_get_json(url: str, timeout: float = 12.0) -> dict:
    req = request.Request(url, headers={"User-Agent": USER_AGENT_SEARCH})
    try:
        with request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            status = getattr(resp, "status", None)
            if status and status >= 400:
                raise HTTPError(url, status, resp.reason, resp.headers, None)

            content_length = resp.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_HTTP_BYTES:
                        raise ValueError(f"Response too large ({content_length} bytes) for {url}")
                except ValueError:
                    pass

            data = resp.read(MAX_HTTP_BYTES + 1)
            if len(data) > MAX_HTTP_BYTES:
                raise ValueError(f"Response exceeded {MAX_HTTP_BYTES} bytes for {url}")

            charset = resp.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc

    decoded = data.decode(charset, errors="replace")
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response from {url}") from exc


def generate_slug(topic: str) -> str:
    """Generate a file-safe slug for reports."""
    cleaned = re.sub(r"[ _]+", "-", (topic or "").lower())
    cleaned = re.sub(r"[^a-z0-9-]", "", cleaned)
    slug = cleaned.strip("-")[:60].strip("-")
    return slug or "report"


def _search_serpapi(query: str, api_key: str, limit: int) -> List[Dict[str, str | None]]:
    url = (
        "https://serpapi.com/search.json?"
        f"engine=google&q={parse.quote(query)}&num={limit}&api_key={parse.quote(api_key)}"
    )
    payload = _http_get_json(url)
    results: List[Dict[str, str | None]] = []
    seen: set[str] = set()

    for item in payload.get("organic_results", []):
        link = item.get("link") or item.get("url")
        if not link or link in seen:
            continue
        seen.add(link)
        title = (item.get("title") or "").strip() or None
        snippet = (item.get("snippet") or item.get("rich_snippet", {}).get("top", {}).get("snippet"))
        results.append({"url": link, "title": title, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


# =============================================================================
# Page Fetching (from extractor)
# =============================================================================

USER_AGENT_FETCH = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
        headers={"User-Agent": USER_AGENT_FETCH, "Accept-Language": "en;q=0.8"},
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
