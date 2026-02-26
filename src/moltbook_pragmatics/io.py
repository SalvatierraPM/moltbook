from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


COMMUNITY_KEYS = ["community_id", "submolt", "group_id", "page_id", "subreddit", "community", "subreddit_id"]
POST_ID_KEYS = ["post_id", "id"]
COMMENT_ID_KEYS = ["comment_id", "id"]
REPLY_TO_KEYS = ["reply_to_id", "parent_id"]
AUTHOR_KEYS = ["author_id", "user_id"]
TEXT_KEYS = ["text", "content", "body", "caption", "title"]
TIMESTAMP_KEYS = ["timestamp", "created_at", "created", "time"]
LANG_KEYS = ["language", "lang"]
REACTIONS_KEYS = ["reactions", "likes", "upvotes", "score"]


@dataclass
class SchemaSummary:
    records: int
    posts: int
    comments: int
    missing_community: int
    missing_timestamp: int
    missing_text: int


def iter_jsonl(path: str | Path) -> Iterator[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{i}: {exc}") from exc


def write_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: str | Path, obj: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _pick(obj: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return default


def _safe_iso(ts: Any) -> Optional[str]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.utcfromtimestamp(float(ts)).isoformat() + "+00:00"
        except (OverflowError, ValueError):
            return None
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        # Keep as-is when parseable-ish, fallback None.
        try:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            return s
        except ValueError:
            return None
    return None


def canonicalize_record(raw: Dict[str, Any], source_type: Optional[str] = None) -> Dict[str, Any]:
    record_type = source_type or raw.get("record_type")
    post_id = _pick(raw, POST_ID_KEYS)
    comment_id = _pick(raw, COMMENT_ID_KEYS)
    reply_to_id = _pick(raw, REPLY_TO_KEYS)

    if record_type is None:
        if reply_to_id is not None or raw.get("parent_id") is not None:
            record_type = "comment"
        elif raw.get("replies") is not None and raw.get("post_id") is not None:
            record_type = "comment"
        elif raw.get("post_id") is None and post_id is not None:
            record_type = "post"
        else:
            record_type = "comment" if raw.get("post_id") else "post"

    if record_type == "comment":
        canonical_post_id = str(raw.get("post_id") or post_id or "")
        canonical_id = str(comment_id or raw.get("id") or "")
    else:
        canonical_post_id = str(post_id or raw.get("id") or "")
        canonical_id = canonical_post_id

    author = _pick(raw, AUTHOR_KEYS)
    if author is None and isinstance(raw.get("author"), dict):
        author = raw["author"].get("id")

    text = _pick(raw, TEXT_KEYS, default="")
    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)

    return {
        "record_type": record_type,
        "community_id": str(_pick(raw, COMMUNITY_KEYS, default="unknown") or "unknown"),
        "post_id": canonical_post_id,
        "message_id": canonical_id,
        "comment_id": canonical_id if record_type == "comment" else None,
        "reply_to_id": str(reply_to_id) if reply_to_id is not None else None,
        "author_id": str(author) if author is not None else "unknown",
        "timestamp": _safe_iso(_pick(raw, TIMESTAMP_KEYS)),
        "text": str(text or ""),
        "language": _pick(raw, LANG_KEYS),
        "reactions": _pick(raw, REACTIONS_KEYS),
    }


def load_canonical_messages(
    input_path: Optional[str] = None,
    posts_path: Optional[str] = None,
    comments_path: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], SchemaSummary]:
    rows: List[Dict[str, Any]] = []

    if input_path:
        for raw in iter_jsonl(input_path):
            rows.append(canonicalize_record(raw))

    if posts_path:
        for raw in iter_jsonl(posts_path):
            rows.append(canonicalize_record(raw, source_type="post"))

    if comments_path:
        for raw in iter_jsonl(comments_path):
            rows.append(canonicalize_record(raw, source_type="comment"))

    dedup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = f"{row['record_type']}::{row['message_id']}"
        if key not in dedup:
            dedup[key] = row

    out = list(dedup.values())
    summary = validate_schema(out)
    return out, summary


def validate_schema(rows: List[Dict[str, Any]]) -> SchemaSummary:
    posts = sum(1 for r in rows if r.get("record_type") == "post")
    comments = sum(1 for r in rows if r.get("record_type") == "comment")
    missing_community = sum(1 for r in rows if not r.get("community_id") or r.get("community_id") == "unknown")
    missing_timestamp = sum(1 for r in rows if not r.get("timestamp"))
    missing_text = sum(1 for r in rows if not (r.get("text") or "").strip())
    return SchemaSummary(
        records=len(rows),
        posts=posts,
        comments=comments,
        missing_community=missing_community,
        missing_timestamp=missing_timestamp,
        missing_text=missing_text,
    )
