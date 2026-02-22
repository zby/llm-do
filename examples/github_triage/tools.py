"""GitHub triage tools.

Provides GitHub notification fetching, local knowledge base search,
and a general-purpose snapshot tool for capturing external sources.

Requires: gh CLI (authenticated), qmd CLI (with indexed collections).
Optional: trafilatura (HTML extraction), pymupdf (PDF extraction).
Configure via environment variables (see .env.example).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallContext
from llm_do.toolsets.approval import set_toolset_approval_config


# =============================================================================
# Config
# =============================================================================

KB_PATH = os.getenv("TRIAGE_KB_PATH", "docs/notes")
KB_COLLECTION = os.getenv("TRIAGE_KB_COLLECTION", "notes")
SNAPSHOT_DIR = os.getenv("TRIAGE_SNAPSHOT_DIR", ".cache/snapshots")
GITHUB_REPOS = os.getenv("TRIAGE_GITHUB_REPOS", "")  # comma-separated, empty = all


# =============================================================================
# Snapshot tool
# =============================================================================

def _slugify(text: str, max_len: int = 60) -> str:
    """Turn text into a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def _detect_content_type(url: str, headers: dict[str, str]) -> str:
    """Detect content type from URL and HTTP headers."""
    ct = headers.get("content-type", "").lower()
    if "application/json" in ct or "api.github.com" in url:
        return "json"
    if "application/pdf" in ct or url.lower().endswith(".pdf"):
        return "pdf"
    if "text/plain" in ct:
        return "text"
    return "html"


def _extract_html_to_markdown(html: str, url: str) -> str:
    """Convert HTML to readable markdown."""
    try:
        import trafilatura
        result = trafilatura.extract(html, include_links=True, include_formatting=True,
                                     output_format="txt", url=url)
        if result:
            return result
    except ImportError:
        pass

    # Minimal fallback: strip tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10000]


def _extract_pdf_to_markdown(pdf_bytes: bytes) -> str:
    """Convert PDF to readable text."""
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        return "\n\n---\n\n".join(pages)[:15000]
    except ImportError:
        return "(PDF extraction requires pymupdf: pip install pymupdf)"


def _render_github_json_to_markdown(data: dict[str, Any]) -> str:
    """Render GitHub API JSON to readable markdown."""
    lines = []

    title = data.get("title", "Untitled")
    number = data.get("number", "")
    state = data.get("state", "")
    user = data.get("user", {}).get("login", "") if isinstance(data.get("user"), dict) else ""
    labels = [l["name"] for l in data.get("labels", [])] if data.get("labels") else []

    header = f"# {title}"
    if number:
        header += f" (#{number})"
    lines.append(header)
    lines.append("")

    meta = []
    if state:
        meta.append(f"**State:** {state}")
    if user:
        meta.append(f"**Author:** {user}")
    if labels:
        meta.append(f"**Labels:** {', '.join(labels)}")
    if meta:
        lines.append(" | ".join(meta))
        lines.append("")

    body = data.get("body") or ""
    if body:
        lines.append(body[:3000])
        lines.append("")

    return "\n".join(lines)


def snapshot(url: str, title: str = "") -> str:
    """Fetch a URL and store it as a timestamped snapshot with markdown view.

    Stores two files: the original source (JSON/HTML/PDF) and a rendered
    markdown view with frontmatter. The markdown is indexed by qmd for
    knowledge base search.

    Skips fetching if a snapshot of the same URL exists from today.

    Args:
        url: The URL to snapshot. Supports web pages (HTML), GitHub API URLs,
             PDFs, and plain text.
        title: Optional title for the snapshot. Auto-detected if empty.

    Returns:
        Path to the markdown snapshot file, plus a brief content summary.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    timestamp = now.isoformat()

    # Determine output directory
    day_dir = Path(SNAPSHOT_DIR) / date_str
    day_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing snapshot of same URL today
    for existing in day_dir.glob("*.md"):
        try:
            text = existing.read_text(encoding="utf-8")
            if f"source: {url}" in text[:500]:
                return f"Already snapshotted today: {existing}\n\nContent available at: {existing}"
        except OSError:
            continue

    # Fetch the content
    if "api.github.com" in url:
        # Use gh CLI for authenticated GitHub API access
        raw_text = _gh("api", url)
        raw_bytes = raw_text.encode("utf-8")
        content_type = "json"
    else:
        req = request.Request(url, headers={
            "User-Agent": "llm-do-snapshot/0.1",
            "Accept": "text/html,application/pdf,application/json,*/*",
        })
        try:
            with request.urlopen(req, timeout=20) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                content_type = _detect_content_type(url, headers)
                raw_bytes = resp.read(2_000_000)
        except (HTTPError, URLError) as exc:
            return f"Failed to fetch {url}: {exc}"

    # Generate slug from title or URL
    if not title:
        if content_type == "json":
            try:
                data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
                title = data.get("title", "") or data.get("name", "")
            except json.JSONDecodeError:
                pass
        if not title:
            # Extract from URL path
            title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")

    slug = _slugify(title)

    # Determine source file extension
    ext_map = {"json": ".json", "html": ".html", "pdf": ".pdf", "text": ".txt"}
    source_ext = ext_map.get(content_type, ".bin")

    # Write source file
    source_path = day_dir / f"{slug}{source_ext}"
    source_path.write_bytes(raw_bytes)

    # Convert to markdown
    raw_text = raw_bytes.decode("utf-8", errors="replace") if content_type != "pdf" else ""

    if content_type == "json":
        try:
            data = json.loads(raw_text)
            if "api.github.com" in url:
                md_body = _render_github_json_to_markdown(data)
            else:
                md_body = f"```json\n{json.dumps(data, indent=2)[:5000]}\n```"
        except json.JSONDecodeError:
            md_body = raw_text[:5000]
    elif content_type == "pdf":
        md_body = _extract_pdf_to_markdown(raw_bytes)
    elif content_type == "html":
        md_body = _extract_html_to_markdown(raw_text, url)
    else:
        md_body = raw_text[:10000]

    # Write markdown with frontmatter
    md_path = day_dir / f"{slug}.md"
    md_content = f"""---
source: {url}
fetched: {timestamp}
type: {content_type}
---

{md_body}
"""
    md_path.write_text(md_content, encoding="utf-8")

    # Brief summary for the agent
    preview = md_body[:200].replace("\n", " ").strip()
    return f"Snapshot saved: {md_path}\nSource: {source_path}\n\nPreview: {preview}..."


# =============================================================================
# GitHub tools
# =============================================================================

def _gh(*args: str, max_bytes: int = 500_000) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout[:max_bytes]


def fetch_notifications(reason_filter: str = "") -> str:
    """Fetch unread GitHub notifications.

    Args:
        reason_filter: Optional filter by reason (e.g. "review_requested", "mention").
                      Empty string returns all unread notifications.

    Returns:
        JSON array of notifications with fields: id, reason, subject_title,
        subject_type, subject_url, repo, updated_at.
    """
    raw = _gh("api", "notifications", "--paginate", "-q",
              '.[] | {id, reason, subject_title: .subject.title, '
              'subject_type: .subject.type, subject_url: .subject.url, '
              'repo: .repository.full_name, updated_at}')

    if not raw.strip():
        return "[]"

    # gh -q with jq produces newline-delimited JSON objects
    items = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line:
            try:
                item = json.loads(line)
                if reason_filter and item.get("reason") != reason_filter:
                    continue
                if GITHUB_REPOS:
                    repos = {r.strip() for r in GITHUB_REPOS.split(",")}
                    if item.get("repo") not in repos:
                        continue
                items.append(item)
            except json.JSONDecodeError:
                continue

    return json.dumps(items, indent=2)


# =============================================================================
# Knowledge base tools
# =============================================================================

def kb_search(query: str, limit: int = 10) -> str:
    """Search the knowledge base using semantic search (qmd).

    Falls back to ripgrep description search if qmd is unavailable.

    Args:
        query: Natural language search query.
        limit: Maximum number of results (default 10).

    Returns:
        Search results with file paths, scores, and snippets.
    """
    # Try qmd first (semantic search)
    try:
        result = subprocess.run(
            ["qmd", "query", query, "-c", KB_COLLECTION, "-n", str(limit), "--files"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: ripgrep over descriptions
    try:
        terms = query.lower().split()[:5]
        pattern = "|".join(terms)
        result = subprocess.run(
            ["rg", "-i", f"^description:.*({pattern})", KB_PATH, "-l", "--max-count", "1"],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            return f"rg matches (description scan):\n{result.stdout.strip()}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "No results found."


def kb_read(path: str) -> str:
    """Read a knowledge base note by path.

    Args:
        path: Path to the note file, relative to KB_PATH or absolute.

    Returns:
        The note content (truncated to 3000 chars).
    """
    p = Path(path)
    if not p.is_absolute():
        p = Path(KB_PATH) / p

    if not p.exists():
        return f"Note not found: {p}"
    if not p.suffix == ".md":
        return f"Not a markdown file: {p}"

    content = p.read_text(encoding="utf-8")
    if len(content) > 3000:
        return content[:3000] + f"\n\n... (truncated, {len(content)} chars total)"
    return content


# =============================================================================
# Registration
# =============================================================================

def build_github_tools(_ctx: RunContext[CallContext]):
    ts = FunctionToolset()
    ts.tool(fetch_notifications)
    set_toolset_approval_config(ts, {
        "fetch_notifications": {"pre_approved": True},
    })
    return ts


def build_kb_tools(_ctx: RunContext[CallContext]):
    ts = FunctionToolset()
    ts.tool(kb_search)
    ts.tool(kb_read)
    set_toolset_approval_config(ts, {
        "kb_search": {"pre_approved": True},
        "kb_read": {"pre_approved": True},
    })
    return ts


def build_snapshot_tools(_ctx: RunContext[CallContext]):
    ts = FunctionToolset()
    ts.tool(snapshot)
    set_toolset_approval_config(ts, {
        "snapshot": {"pre_approved": True},
    })
    return ts


TOOLSETS = {
    "github_tools": build_github_tools,
    "kb_tools": build_kb_tools,
    "snapshot_tools": build_snapshot_tools,
}
