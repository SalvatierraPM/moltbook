#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional
from urllib.parse import urlparse


# NOTE: use single backslashes inside the raw regex; double escaping would match literal "\w" etc.
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
# Require >=2 chars to avoid obvious noise like "@w" / "@-".
MENTION_RE = re.compile(r"@([\w][\w\-]{1,49})", re.UNICODE)
HASHTAG_RE = re.compile(r"#([\w\-]{1,50})", re.UNICODE)


def iter_jsonl(path: Path) -> Iterator[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def norm_url(raw: str) -> str:
    clean = raw.strip().rstrip(").,;!?:\"]'")
    if clean.startswith("www."):
        clean = "http://" + clean
    return clean


def domain_for(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def iter_docs(posts: Path, comments: Path) -> Iterator[Dict]:
    for p in iter_jsonl(posts):
        title = p.get("title") or ""
        content = p.get("content") or ""
        text = f"{title}\\n{content}".strip()
        author = p.get("author") or {}
        submolt = p.get("submolt") or {}
        yield {
            "doc_id": p.get("id"),
            "doc_type": "post",
            "post_id": p.get("id"),
            "parent_id": None,
            "text": text,
            "author_id": author.get("id"),
            "author_name": author.get("name"),
            "submolt": submolt.get("name") if isinstance(submolt, dict) else submolt,
            "created_at": p.get("created_at"),
        }
    for c in iter_jsonl(comments):
        author = c.get("author") or {}
        yield {
            "doc_id": c.get("id"),
            "doc_type": "comment",
            "post_id": c.get("post_id"),
            "parent_id": c.get("parent_id"),
            "text": c.get("content") or "",
            "author_id": c.get("author_id") or author.get("id"),
            "author_name": author.get("name"),
            "submolt": None,
            "created_at": c.get("created_at"),
        }


def write_csv(path: Path, rows: Iterable[Dict], header: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(header))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def extract_edges(posts: Path, comments: Path, out_dir: Path) -> None:
    mention_rows = []
    mention_rows_raw = []
    hashtag_rows = []
    link_rows = []
    reply_rows = []
    author_rows = []

    post_submolt: Dict[str, str] = {}
    known_handles: set[str] = set()

    for p in iter_jsonl(posts):
        pid = p.get("id")
        submolt = p.get("submolt")
        if isinstance(submolt, dict):
            submolt = submolt.get("name")
        if isinstance(pid, str) and isinstance(submolt, str):
            post_submolt[pid] = submolt
        author = p.get("author") or {}
        author_name = author.get("name")
        if isinstance(author_name, str) and author_name.strip():
            known_handles.add(author_name.strip().lower())
        author_id = author.get("id")
        if author_id and pid:
            author_rows.append(
                {
                    "author_id": author_id,
                    "doc_id": pid,
                    "doc_type": "post",
                    "post_id": pid,
                    "created_at": p.get("created_at"),
                    "submolt": submolt,
                }
            )

    comment_author: Dict[str, str] = {}
    comment_post: Dict[str, str] = {}
    comment_parent: Dict[str, str] = {}
    comment_meta: Dict[str, Dict[str, str]] = {}

    for c in iter_jsonl(comments):
        cid = c.get("id")
        if not isinstance(cid, str):
            continue
        author = c.get("author") or {}
        author_name = author.get("name")
        if isinstance(author_name, str) and author_name.strip():
            known_handles.add(author_name.strip().lower())
        author_id = c.get("author_id") or author.get("id")
        comment_author[cid] = author_id
        post_id = c.get("post_id")
        if isinstance(post_id, str):
            comment_post[cid] = post_id
        parent_id = c.get("parent_id")
        if isinstance(parent_id, str):
            comment_parent[cid] = parent_id
        comment_meta[cid] = {
            "created_at": c.get("created_at"),
            "depth": c.get("depth"),
            "thread_path": c.get("thread_path"),
        }
        if author_id and post_id:
            author_rows.append(
                {
                    "author_id": author_id,
                    "doc_id": cid,
                    "doc_type": "comment",
                    "post_id": post_id,
                    "created_at": c.get("created_at"),
                    "submolt": post_submolt.get(post_id),
                }
            )

    for doc in iter_docs(posts, comments):
        text = doc.get("text") or ""
        base = {
            "src_id": doc.get("doc_id"),
            "src_type": doc.get("doc_type"),
            "post_id": doc.get("post_id"),
            "parent_id": doc.get("parent_id"),
            "author_id": doc.get("author_id"),
            "author_name": doc.get("author_name"),
            "submolt": doc.get("submolt"),
            "created_at": doc.get("created_at"),
        }

        for m in MENTION_RE.finditer(text):
            target = m.group(1)
            target_norm = target.strip().lower()
            row = {
                **base,
                "edge_type": "mention",
                "target": target_norm,
                "target_raw": target,
                "position": m.start(),
            }
            mention_rows_raw.append(row)
            # Keep only likely-internal handles to avoid noise dominating centrality.
            if not target_norm or target_norm not in known_handles:
                continue
            mention_rows.append(
                {
                    **row,
                }
            )

        for h in HASHTAG_RE.finditer(text):
            target = h.group(1)
            hashtag_rows.append(
                {
                    **base,
                    "edge_type": "hashtag",
                    "target": target.lower(),
                    "target_raw": target,
                    "position": h.start(),
                }
            )

        for u in URL_RE.finditer(text):
            raw = u.group(1)
            norm = norm_url(raw)
            dom = domain_for(norm)
            link_rows.append(
                {
                    **base,
                    "edge_type": "link",
                    "target": dom,
                    "target_raw": raw,
                    "url": norm,
                    "domain": dom,
                    "position": u.start(),
                }
            )

    # Reply edges (comment -> parent)
    for cid, meta in comment_meta.items():
        parent_id = comment_parent.get(cid)
        if not parent_id:
            continue
        post_id = comment_post.get(cid)
        reply_rows.append(
            {
                "comment_id": cid,
                "parent_id": parent_id,
                "post_id": post_id,
                "author_id": comment_author.get(cid),
                "parent_author_id": comment_author.get(parent_id),
                "created_at": meta.get("created_at"),
                "depth": meta.get("depth"),
                "thread_path": meta.get("thread_path"),
                "submolt": post_submolt.get(post_id),
            }
        )

    mention_header = [
        "src_id",
        "src_type",
        "post_id",
        "parent_id",
        "author_id",
        "author_name",
        "submolt",
        "created_at",
        "edge_type",
        "target",
        "target_raw",
        "position",
    ]
    link_header = [
        "src_id",
        "src_type",
        "post_id",
        "parent_id",
        "author_id",
        "author_name",
        "submolt",
        "created_at",
        "edge_type",
        "target",
        "target_raw",
        "url",
        "domain",
        "position",
    ]

    write_csv(out_dir / "edges_mentions.csv", mention_rows, mention_header)
    write_csv(out_dir / "edges_mentions_raw.csv", mention_rows_raw, mention_header)
    write_csv(out_dir / "edges_hashtags.csv", hashtag_rows, mention_header)
    write_csv(out_dir / "edges_links.csv", link_rows, link_header)
    write_csv(
        out_dir / "edges_replies.csv",
        reply_rows,
        [
            "comment_id",
            "parent_id",
            "post_id",
            "author_id",
            "parent_author_id",
            "created_at",
            "depth",
            "thread_path",
            "submolt",
        ],
    )
    write_csv(
        out_dir / "edges_authorship.csv",
        author_rows,
        ["author_id", "doc_id", "doc_type", "post_id", "created_at", "submolt"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract mention/link/hashtag edges from Moltbook JSONL.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    args = parser.parse_args()

    extract_edges(Path(args.posts), Path(args.comments), Path(args.out_dir))
    print(f"Edges written to {args.out_dir}")


if __name__ == "__main__":
    main()
