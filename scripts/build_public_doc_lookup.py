#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Set, Tuple


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def safe_get_id(obj: Dict[str, Any]) -> Optional[str]:
    for key in ("id", "post_id", "comment_id", "uuid"):
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def read_csv_ids(path: Path, id_fields: Tuple[str, ...]) -> Set[str]:
    if not path.exists():
        return set()
    out: Set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for field in id_fields:
                value = row.get(field)
                if isinstance(value, str) and value:
                    out.add(value)
    return out


def read_csv_typed_ids(path: Path, id_field: str, type_field: str) -> Set[Tuple[str, str]]:
    if not path.exists():
        return set()
    out: Set[Tuple[str, str]] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row.get(id_field)
            doc_type = row.get(type_field)
            if isinstance(doc_id, str) and doc_id and isinstance(doc_type, str) and doc_type:
                out.add((doc_id, doc_type))
    return out


def build_lookup(
    posts_path: Path,
    comments_path: Path,
    typed_ids: Set[Tuple[str, str]],
    unknown_ids: Set[str],
) -> Dict[str, Dict[str, Any]]:
    # Extract only the needed docs from the large JSONL dumps.
    need_posts: Set[str] = {doc_id for doc_id, typ in typed_ids if typ == "post"}
    need_comments: Set[str] = {doc_id for doc_id, typ in typed_ids if typ == "comment"}
    unknown: Set[str] = set(unknown_ids)

    docs: Dict[str, Dict[str, Any]] = {}

    if posts_path.exists() and (need_posts or unknown):
        for post in iter_jsonl(posts_path):
            pid = safe_get_id(post)
            if not pid:
                continue
            if pid not in need_posts and pid not in unknown:
                continue
            title = post.get("title") or ""
            content = post.get("content") or post.get("body") or ""
            text = f"{title}\n{content}".strip()
            docs[pid] = {"doc_type": "post", "text": text}
            need_posts.discard(pid)
            unknown.discard(pid)
            if not need_posts and not unknown:
                break

    if comments_path.exists() and (need_comments or unknown):
        for comment in iter_jsonl(comments_path):
            cid = safe_get_id(comment)
            if not cid:
                continue
            if cid not in need_comments and cid not in unknown:
                continue
            content = comment.get("content") or comment.get("body") or ""
            text = str(content).strip()
            docs[cid] = {"doc_type": "comment", "text": text}
            need_comments.discard(cid)
            unknown.discard(cid)
            if not need_comments and not unknown:
                break

    return docs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a small doc_id -> full text lookup for the public UI tables.",
    )
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--derived", default="data/derived")
    parser.add_argument("--out", default="data/derived/public_doc_lookup.json")
    args = parser.parse_args()

    derived = Path(args.derived)
    posts_path = Path(args.posts)
    comments_path = Path(args.comments)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    typed_ids: Set[Tuple[str, str]] = set()
    unknown_ids: Set[str] = set()

    typed_ids |= read_csv_typed_ids(derived / "interference_top.csv", "doc_id", "doc_type")
    typed_ids |= read_csv_typed_ids(derived / "human_incidence_top.csv", "doc_id", "doc_type")
    typed_ids |= read_csv_typed_ids(derived / "public_submolt_examples.csv", "doc_id", "doc_type")

    # Embeddings: doc_type is not present, so treat as unknown and resolve by scanning posts then comments.
    unknown_ids |= read_csv_ids(derived / "public_embeddings_pairs_top.csv", ("doc_id", "neighbor_id"))

    # Embeddings post->comment: ids are explicit.
    typed_ids |= {(pid, "post") for pid in read_csv_ids(derived / "embeddings_post_comment" / "public_embeddings_post_comment_pairs_top.csv", ("post_id",))}
    typed_ids |= {(cid, "comment") for cid in read_csv_ids(derived / "embeddings_post_comment" / "public_embeddings_post_comment_pairs_top.csv", ("comment_id",))}

    docs = build_lookup(posts_path, comments_path, typed_ids, unknown_ids)
    payload = {
        "generated_from": {
            "posts": str(posts_path),
            "comments": str(comments_path),
        },
        "counts": {
            "typed_ids": len(typed_ids),
            "unknown_ids": len(unknown_ids),
            "docs_written": len(docs),
        },
        "docs": docs,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(docs)} docs to {out_path}")


if __name__ == "__main__":
    main()

