#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def safe_text(value: Any) -> str:
    return str(value) if value is not None else ""


def clamp_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def build_post_text(post: Dict[str, Any]) -> str:
    title = safe_text(post.get("title")).strip()
    content = safe_text(post.get("content")).strip()
    if title and content:
        return f"{title}\n{content}"
    return title or content


def build_comment_text(comment: Dict[str, Any]) -> str:
    return safe_text(comment.get("content")).strip()


def load_posts(posts_path: Path) -> Dict[str, Dict[str, Any]]:
    posts: Dict[str, Dict[str, Any]] = {}
    for p in iter_jsonl(posts_path):
        pid = p.get("id")
        if not isinstance(pid, str):
            continue
        posts[pid] = p
    return posts


def load_comments(comments_path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    comments_by_id: Dict[str, Dict[str, Any]] = {}
    comments_by_post: Dict[str, List[str]] = {}
    for c in iter_jsonl(comments_path):
        cid = c.get("id")
        post_id = c.get("post_id")
        if not isinstance(cid, str):
            continue
        if not isinstance(post_id, str):
            post_id = ""
        comments_by_id[cid] = c
        comments_by_post.setdefault(post_id, []).append(cid)
    return comments_by_id, comments_by_post


def build_post_context(
    post: Dict[str, Any],
    comment_ids: List[str],
    comments_by_id: Dict[str, Dict[str, Any]],
    max_comments: int,
    max_post_chars: int,
    max_comment_chars: int,
) -> str:
    base = clamp_text(build_post_text(post), max_post_chars)
    if not comment_ids or max_comments <= 0:
        return base
    scored: List[Tuple[float, str]] = []
    for cid in comment_ids:
        c = comments_by_id.get(cid)
        if not c:
            continue
        score = c.get("upvotes") or 0
        try:
            score = float(score)
        except Exception:
            score = 0.0
        scored.append((score, cid))
    scored.sort(key=lambda x: x[0], reverse=True)
    picks = [cid for _, cid in scored[:max_comments]]
    chunks = [base, "\n\n[TOP_COMMENTS]"]
    for cid in picks:
        c = comments_by_id.get(cid)
        if not c:
            continue
        text = clamp_text(build_comment_text(c), max_comment_chars)
        if not text:
            continue
        chunks.append(f"- {text}")
    return "\n".join([c for c in chunks if c])


def ancestor_chain(
    comment: Dict[str, Any],
    comments_by_id: Dict[str, Dict[str, Any]],
    max_ancestors: int,
) -> List[str]:
    chain: List[str] = []
    cur = comment.get("parent_id")
    while cur and len(chain) < max_ancestors:
        parent = comments_by_id.get(cur)
        if not parent:
            break
        text = build_comment_text(parent)
        if text:
            chain.append(text)
        cur = parent.get("parent_id")
    return chain


def build_comment_context(
    comment: Dict[str, Any],
    post: Optional[Dict[str, Any]],
    comments_by_id: Dict[str, Dict[str, Any]],
    max_post_chars: int,
    max_comment_chars: int,
    max_ancestors: int,
) -> str:
    parts: List[str] = []
    if post:
        post_text = clamp_text(build_post_text(post), max_post_chars)
        if post_text:
            parts.append(f"[POST]\n{post_text}")
    parents = ancestor_chain(comment, comments_by_id, max_ancestors=max_ancestors)
    if parents:
        parts.append("[PARENTS]")
        for i, text in enumerate(reversed(parents), start=1):
            parts.append(f"{i}. {clamp_text(text, max_comment_chars)}")
    comment_text = clamp_text(build_comment_text(comment), max_comment_chars)
    if comment_text:
        parts.append(f"[COMMENT]\n{comment_text}")
    return "\n\n".join(parts)


def build_context_dataset(
    posts_path: Path,
    comments_path: Path,
    out_dir: Path,
    max_comments: int,
    max_post_chars: int,
    max_comment_chars: int,
    max_ancestors: int,
) -> None:
    posts = load_posts(posts_path)
    comments_by_id, comments_by_post = load_comments(comments_path)

    post_rows: List[Dict[str, Any]] = []
    for pid, post in posts.items():
        context_text = build_post_context(
            post,
            comments_by_post.get(pid, []),
            comments_by_id,
            max_comments=max_comments,
            max_post_chars=max_post_chars,
            max_comment_chars=max_comment_chars,
        )
        post_rows.append(
            {
                "doc_id": pid,
                "doc_type": "post",
                "post_id": pid,
                "title": post.get("title"),
                "text": build_post_text(post),
                "context_text": context_text,
                "created_at": post.get("created_at"),
                "submolt": (post.get("submolt") or {}).get("name")
                if isinstance(post.get("submolt"), dict)
                else post.get("submolt"),
                "author_id": (post.get("author") or {}).get("id"),
                "author_name": (post.get("author") or {}).get("name"),
                "run_id": post.get("_run_id"),
            }
        )

    comment_rows: List[Dict[str, Any]] = []
    for cid, comment in comments_by_id.items():
        post = posts.get(comment.get("post_id"))
        context_text = build_comment_context(
            comment,
            post,
            comments_by_id,
            max_post_chars=max_post_chars,
            max_comment_chars=max_comment_chars,
            max_ancestors=max_ancestors,
        )
        comment_rows.append(
            {
                "doc_id": cid,
                "doc_type": "comment",
                "post_id": comment.get("post_id"),
                "parent_id": comment.get("parent_id"),
                "text": build_comment_text(comment),
                "context_text": context_text,
                "created_at": comment.get("created_at"),
                "author_id": comment.get("author_id"),
                "author_name": (comment.get("author") or {}).get("name"),
                "depth": comment.get("depth"),
                "thread_path": comment.get("thread_path"),
                "run_id": comment.get("_run_id"),
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    posts_df = pd.DataFrame(post_rows)
    comments_df = pd.DataFrame(comment_rows)
    posts_df.to_json(out_dir / "context_posts.jsonl", orient="records", lines=True, force_ascii=False)
    comments_df.to_json(out_dir / "context_comments.jsonl", orient="records", lines=True, force_ascii=False)
    posts_df.to_parquet(out_dir / "context_posts.parquet", index=False)
    comments_df.to_parquet(out_dir / "context_comments.parquet", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build context-enriched datasets for VSM.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    parser.add_argument("--max-comments", type=int, default=8)
    parser.add_argument("--max-post-chars", type=int, default=2000)
    parser.add_argument("--max-comment-chars", type=int, default=800)
    parser.add_argument("--max-ancestors", type=int, default=3)
    args = parser.parse_args()

    build_context_dataset(
        Path(args.posts),
        Path(args.comments),
        Path(args.out_dir),
        max_comments=args.max_comments,
        max_post_chars=args.max_post_chars,
        max_comment_chars=args.max_comment_chars,
        max_ancestors=args.max_ancestors,
    )
    print(f"Context datasets written to {args.out_dir}")


if __name__ == "__main__":
    main()
