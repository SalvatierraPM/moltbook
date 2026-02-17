from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from moltbook_analysis.http_client import HttpClient
from moltbook_analysis.schemas import Post, Comment


def _get(obj: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def _get_nested(obj: Dict[str, Any], *keys: str) -> Any:
    cur: Any = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def normalize_post(raw: Dict[str, Any]) -> Post:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    return Post(
        id=_get(raw, "id", "post_id", "uuid"),
        title=_get(raw, "title", "name"),
        body=_get(raw, "body", "content", "text"),
        author_id=_get(raw, "author_id", "authorId") or _get_nested(author, "id"),
        author_name=_get(raw, "author_name", "authorName") or _get(author, "name", "username"),
        created_at=_get(raw, "created_at", "createdAt", "created"),
        created_at_raw=_get(raw, "created_at_raw", "createdRaw"),
        updated_at=_get(raw, "updated_at", "updatedAt", "updated"),
        score=_get(raw, "score", "upvotes", "likes"),
        comment_count=_get(raw, "comment_count", "comments_count", "num_comments"),
        views=_get(raw, "views", "view_count"),
        submolt=_get(raw, "submolt", "sub", "community"),
        url=_get(raw, "url", "permalink"),
        tags=raw.get("tags", []) if isinstance(raw.get("tags"), list) else [],
        source=_get(raw, "source"),
        filter=_get(raw, "filter"),
        listing_rank=_get(raw, "listing_rank", "rank"),
        scrape_ts=_get(raw, "scrape_ts"),
        raw=raw,
    )


def normalize_comment(raw: Dict[str, Any], post_id: Optional[str] = None) -> Comment:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    return Comment(
        id=_get(raw, "id", "comment_id", "uuid"),
        post_id=post_id or _get(raw, "post_id", "postId"),
        parent_id=_get(raw, "parent_id", "parentId"),
        body=_get(raw, "body", "content", "text"),
        author_id=_get(raw, "author_id", "authorId") or _get_nested(author, "id"),
        author_name=_get(raw, "author_name", "authorName") or _get(author, "name", "username"),
        created_at=_get(raw, "created_at", "createdAt", "created"),
        created_at_raw=_get(raw, "created_at_raw", "createdRaw"),
        score=_get(raw, "score", "upvotes", "likes"),
        depth=_get(raw, "depth"),
        thread_path=_get(raw, "thread_path"),
        scrape_ts=_get(raw, "scrape_ts"),
        raw=raw,
    )


def _extract_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "posts", "comments"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


def fetch_posts(
    client: HttpClient,
    since: Optional[str] = None,
    max_pages: int = 50,
    page_size: int = 50,
) -> Iterable[Dict[str, Any]]:
    for page in range(1, max_pages + 1):
        params = {"page": page, "limit": page_size}
        if since:
            params["since"] = since
        resp = client.get("/posts", params=params)
        payload = resp.json()
        rows = _extract_list(payload)
        if not rows:
            break
        for row in rows:
            yield row


def fetch_post_comments(
    client: HttpClient,
    post_id: str,
    max_pages: int = 20,
    page_size: int = 100,
) -> Iterable[Dict[str, Any]]:
    for page in range(1, max_pages + 1):
        params = {"page": page, "limit": page_size}
        resp = client.get(f"/posts/{post_id}/comments", params=params)
        payload = resp.json()
        rows = _extract_list(payload)
        if not rows:
            break
        for row in rows:
            # Keep the post->comment relation stable even when API payload omits post_id.
            if isinstance(row, dict) and not row.get("post_id"):
                row["post_id"] = post_id
            yield row
