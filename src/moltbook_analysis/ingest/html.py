from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from moltbook_analysis.http_client import HttpClient


def _text(el) -> str | None:
    if not el:
        return None
    return " ".join(el.get_text(" ", strip=True).split())


def _looks_like_post(obj: Dict[str, Any]) -> bool:
    keys = set(obj.keys())
    score = 0
    for k in ("title", "name"):
        if k in keys:
            score += 1
    for k in ("body", "content", "text"):
        if k in keys:
            score += 1
    for k in ("author", "author_name", "authorId", "author_id"):
        if k in keys:
            score += 1
    for k in ("created_at", "createdAt", "created"):
        if k in keys:
            score += 1
    return score >= 2


def _extract_post_lists(obj: Any) -> List[List[Dict[str, Any]]]:
    found: List[List[Dict[str, Any]]] = []
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            # Heuristic: at least half look like posts
            looks = sum(1 for x in obj if _looks_like_post(x))
            if looks >= max(1, len(obj) // 2):
                found.append(obj)
        for x in obj:
            found.extend(_extract_post_lists(x))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_extract_post_lists(v))
    return found


def _dedupe_posts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in rows:
        key = r.get("id") or (r.get("title"), r.get("body"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _parse_embedded_json(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    posts: List[Dict[str, Any]] = []

    script_selectors = [
        ("script", {"id": "__NEXT_DATA__"}),
        ("script", {"id": "__NUXT__"}),
        ("script", {"id": "__APP_DATA__"}),
    ]

    scripts = []
    for name, attrs in script_selectors:
        scripts.extend(soup.find_all(name, attrs=attrs))
    scripts.extend(soup.find_all("script", attrs={"type": "application/json"}))

    for s in scripts:
        raw = s.string or s.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        lists = _extract_post_lists(data)
        for lst in lists:
            posts.extend(lst)

    return posts


REL_TIME_RE = re.compile(r"(\d+)\s*(m|h|d|w|mo|y)\s*ago", re.IGNORECASE)


def _parse_relative_time(text: str, now: Optional[datetime] = None) -> Optional[str]:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in {"just now", "now"}:
        return (now or datetime.now(timezone.utc)).isoformat()

    m = REL_TIME_RE.search(t.replace("mins", "m").replace("min", "m"))
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        delta = timedelta(minutes=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "mo":
        delta = timedelta(days=30 * value)
    elif unit == "y":
        delta = timedelta(days=365 * value)
    else:
        return None

    ts = (now or datetime.now(timezone.utc)) - delta
    return ts.isoformat()


def _parse_posts_from_anchors(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    anchors = soup.find_all("a", href=re.compile(r"^/post/"))
    for a in anchors:
        if not isinstance(a, Tag):
            continue
        href = a.get("href") or ""
        post_id = href.split("/post/")[-1] if "/post/" in href else None

        title_el = a.find("h3")
        body_el = a.find("p")

        # submolt like "m/general"
        submolt = None
        for span in a.find_all("span"):
            t = _text(span)
            if t and t.startswith("m/"):
                submolt = t
                break

        # relative time like "14h ago"
        created_at_raw = None
        created_at = None
        for span in a.find_all("span"):
            t = _text(span)
            if t and "ago" in t:
                created_at_raw = t
                created_at = _parse_relative_time(t, now=now)
                break

        # score from left vote column (first direct child div)
        score = None
        children = [c for c in a.find_all(recursive=False) if isinstance(c, Tag)]
        if children:
            vote_col = children[0]
            for span in vote_col.find_all("span"):
                t = _text(span)
                if t and t.isdigit():
                    score = int(t)
                    break

        # comment count
        comment_count = None
        for span in a.find_all("span"):
            t = _text(span)
            if t and t.lower().startswith("comment"):
                prev = span.find_previous_sibling("span")
                if prev and (_text(prev) or "").isdigit():
                    comment_count = int(_text(prev))
                break

        posts.append(
            {
                "id": post_id,
                "title": _text(title_el),
                "body": _text(body_el),
                "submolt": submolt,
                "created_at": created_at,
                "created_at_raw": created_at_raw,
                "score": score,
                "comment_count": comment_count,
                "url": href,
                "raw_html": str(a)[:5000],
            }
        )
    return posts


def parse_posts_from_html(html: str) -> List[Dict[str, Any]]:
    # 1) Try embedded JSON payloads (Next.js, Nuxt, etc.)
    embedded = _parse_embedded_json(html)
    if embedded:
        return _dedupe_posts(embedded)

    # 2) Try anchors pointing to /post/<id>
    soup = BeautifulSoup(html, "lxml")
    anchor_posts = _parse_posts_from_anchors(soup)
    if anchor_posts:
        return _dedupe_posts(anchor_posts)

    # 3) Fallback to DOM heuristics
    posts: List[Dict[str, Any]] = []

    candidates = soup.find_all(["article", "div"], attrs={"data-post-id": True})
    if not candidates:
        candidates = soup.find_all("article")

    for el in candidates:
        post_id = el.get("data-post-id") or el.get("id")
        title_el = el.find(["h1", "h2", "h3"])
        body_el = el.find("div", class_=lambda c: c and "content" in c) or el.find("p")
        author_el = el.find("a", class_=lambda c: c and "author" in c) or el.find(
            "span", class_=lambda c: c and "author" in c
        )

        posts.append(
            {
                "id": post_id,
                "title": _text(title_el),
                "body": _text(body_el),
                "author_name": _text(author_el),
                "raw_html": str(el)[:5000],
            }
        )
    return posts


def fetch_posts_html(
    client: HttpClient,
    path: str = "/",
    max_pages: int = 10,
    dump_dir: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    for page in range(1, max_pages + 1):
        resp = client.get(path, params={"page": page})
        if dump_dir:
            from pathlib import Path

            Path(dump_dir).mkdir(parents=True, exist_ok=True)
            (Path(dump_dir) / f"page_{page}.html").write_text(resp.text, encoding="utf-8")
        rows = parse_posts_from_html(resp.text)
        if not rows:
            break
        for row in rows:
            yield row


def fetch_posts_html_dynamic(
    base_url: str,
    path: str = "/",
    max_scrolls: int = 8,
    wait_ms: int = 1200,
    user_agent: Optional[str] = None,
    dump_dir: Optional[str] = None,
    screenshot_dir: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    """
    Render JS-heavy pages using Playwright, then parse posts with BeautifulSoup.
    Requires `playwright` installed and browsers set up.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Playwright is not installed. Install with: pip install playwright && playwright install"
        ) from exc

    url = base_url.rstrip("/") + "/" + path.lstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent) if user_agent else browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        for _ in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(wait_ms)

        html = page.content()
        if dump_dir:
            from pathlib import Path

            Path(dump_dir).mkdir(parents=True, exist_ok=True)
            (Path(dump_dir) / "page_dynamic.html").write_text(html, encoding="utf-8")
        if screenshot_dir:
            from pathlib import Path

            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(screenshot_dir) / "page_dynamic.png"), full_page=True)
        browser.close()

    for row in parse_posts_from_html(html):
        yield row
