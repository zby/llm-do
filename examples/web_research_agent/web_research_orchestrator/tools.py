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


