from __future__ import annotations

import json
import os
import ssl
import re
from typing import Dict, List
from urllib import parse, request
from urllib.error import HTTPError, URLError

USER_AGENT = "llm-do-web-research/0.1"
MAX_HTTP_BYTES = 1_000_000


def search_web(query: str, num_results: int = 4) -> List[Dict[str, str | None]]:
    """
    Run a lightweight web search.

    Prefers SerpAPI when SERPAPI_API_KEY is set; otherwise falls back to the
    DuckDuckGo JSON instant-answer API (coverage is limited; expect sparse
    results). Returns a list of {url, title, snippet} dicts with duplicates
    removed.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    limit = max(1, min(num_results, 8))
    api_key = os.getenv("SERPAPI_API_KEY")

    if api_key:
        try:
            serpapi_hits = _search_serpapi(cleaned_query, api_key, limit)
            if serpapi_hits:
                return serpapi_hits[:limit]
        except Exception:
            # Fall back silently; the model can see the empty list if everything fails.
            pass

    try:
        return _search_duckduckgo(cleaned_query, limit)
    except Exception:
        return []


def _http_get_json(url: str, timeout: float = 12.0) -> dict:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
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
                    # Ignore invalid headers; continue with streaming guard.
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


def _search_duckduckgo(query: str, limit: int) -> List[Dict[str, str | None]]:
    url = (
        "https://api.duckduckgo.com/?"
        f"q={parse.quote(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    )
    payload = _http_get_json(url)
    results: List[Dict[str, str | None]] = []
    seen: set[str] = set()

    def _add_result(link: str | None, text: str | None) -> None:
        if not link or link in seen:
            return
        seen.add(link)
        snippet = (text or "").strip() or None
        results.append({"url": link, "title": None, "snippet": snippet})

    for item in payload.get("Results", []):
        _add_result(item.get("FirstURL"), item.get("Text"))
        if len(results) >= limit:
            return results

    for topic in payload.get("RelatedTopics", []):
        if "FirstURL" in topic:
            _add_result(topic.get("FirstURL"), topic.get("Text"))
        elif topic.get("Topics"):
            for sub in topic["Topics"]:
                _add_result(sub.get("FirstURL"), sub.get("Text"))
                if len(results) >= limit:
                    return results
        if len(results) >= limit:
            break

    return results[:limit]
