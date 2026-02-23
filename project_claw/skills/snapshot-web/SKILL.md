---
name: snapshot-web
description: Snapshot a web page into project_claw/sources/. Fetches the URL, extracts content as clean markdown, saves with frontmatter for the ingestion pipeline. Triggers on "/snapshot-web", "/snapshot-web [url]".
user-invocable: true
allowed-tools: Read, Write, Grep, Glob, WebFetch
context: fork
model: sonnet
argument-hint: "[url] — URL of a web page to snapshot"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

If no URL provided, ask the user for one.

If URL provided, start Step 1 immediately.

**START NOW.**

---

## Step 1: Check for Duplicates

Scan `project_claw/sources/` for an existing snapshot of this URL:

```bash
grep -l "source: <url>" project_claw/sources/*.md 2>/dev/null
```

Use Grep to search for the URL in existing `.md` files. If found, tell the user and stop:

> Already snapshotted: project_claw/sources/{filename}

## Step 2: Fetch the Page

Use WebFetch with this prompt:

> Extract the main article/post content from this page as clean markdown.
> Return ONLY the content — no navigation, sidebars, ads, cookie banners, or boilerplate.
> Preserve: headings, block quotes, code blocks, links, lists, emphasis.
> For blog posts: include the author name, publication date, and tags if visible.
> If the page has no extractable content (login wall, JS-only, error page), say "NO_CONTENT:" followed by a brief reason.

## Step 3: Handle Failures

If WebFetch returns a NO_CONTENT signal or fails:
- Tell the user what happened
- Suggest they paste the content manually: "You can paste the text and I'll save it as a snapshot"
- Stop

## Step 4: Determine Metadata

From the fetched content and URL, determine:

- **title**: The article/post title. Use the first H1 if present, otherwise derive from content.
- **author**: If identifiable from the content or URL (e.g. simonwillison.net → Simon Willison)
- **type**: One of: `blog-post`, `documentation`, `forum-thread`, `news-article`, `web-page` (default)
- **slug**: Lowercase, hyphenated, max 70 chars. Derived from title. Example: `simon-willison-karpathy-claws`

## Step 5: Write the Snapshot

Save to `project_claw/sources/{slug}.md` with this format:

```markdown
---
source: {url}
captured: {YYYY-MM-DD}
capture: web-fetch
type: {type}
---

# {title}

Author: {author}
Source: {url}
Date: {publication date if known}

{extracted content}
```

Also tell the user where it was saved and show a 1-2 line preview.

## Critical Constraints

**Never:**
- Fabricate or hallucinate content not on the page
- Add analysis or commentary — this is capture, not ingestion
- Modify the extracted content beyond cleaning HTML artifacts
- Save to any directory other than `project_claw/sources/`

**Always:**
- Preserve the author's structure (headings, quotes, lists)
- Include the source URL in frontmatter
- Use today's date for `captured`
- Check for duplicates before fetching
