#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def iter_jsonl(path: Path) -> Iterable[dict]:
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


def compact_text(text: str) -> str:
    # Keep it simple: collapse whitespace and keep stable Unicode for UI excerpts.
    return re.sub(r"\s+", " ", (text or "")).strip()


def excerpt(text: str, max_len: int = 220) -> str:
    t = compact_text(text)
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def alnum_count(text: str) -> int:
    return sum(1 for c in (text or "") if c.isalnum())


TEMPLATE_RE = re.compile(
    r"mbc-20|mbc20\.xyz|\"p\"\s*:\s*\"mbc-20\"|\"op\"\s*:\s*\"(mint|link|transfer)\"",
    flags=re.IGNORECASE,
)


def looks_like_template(text: str) -> bool:
    return bool(TEMPLATE_RE.search(text or ""))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


@dataclass(frozen=True)
class PostInfo:
    submolt: str
    created_at: str
    lang: str
    excerpt: str


@dataclass(frozen=True)
class CommentInfo:
    created_at: str
    excerpt: str


def load_posts_info(posts_path: Path, wanted: set[str], max_excerpt: int) -> dict[str, PostInfo]:
    out: dict[str, PostInfo] = {}
    if not wanted:
        return out
    for post in iter_jsonl(posts_path):
        pid = post.get("id")
        if not isinstance(pid, str) or pid not in wanted:
            continue
        title = post.get("title") or ""
        content = post.get("content") or ""
        text = f"{title}\n{content}".strip()
        submolt = post.get("submolt")
        if isinstance(submolt, dict):
            submolt = submolt.get("name")
        created_at = str(post.get("created_at") or "")
        # Prefer language already computed in embeddings pipeline if present, but fall back gracefully.
        lang = str(post.get("lang") or "unknown")
        out[pid] = PostInfo(
            submolt=str(submolt or "unknown"),
            created_at=created_at,
            lang=lang or "unknown",
            excerpt=excerpt(text, max_excerpt),
        )
        if len(out) >= len(wanted):
            break
    return out


def load_comments_info(comments_path: Path, wanted: set[str], max_excerpt: int) -> dict[str, CommentInfo]:
    out: dict[str, CommentInfo] = {}
    if not wanted:
        return out
    for c in iter_jsonl(comments_path):
        cid = c.get("id")
        if not isinstance(cid, str) or cid not in wanted:
            continue
        text = str(c.get("content") or "").strip()
        created_at = str(c.get("created_at") or "")
        out[cid] = CommentInfo(created_at=created_at, excerpt=excerpt(text, max_excerpt))
        if len(out) >= len(wanted):
            break
    return out


def top_pairs_from_csv(
    matches_path: Path,
    *,
    id_a: str,
    id_b: str,
    lang_key: str,
    score_key: str,
    min_score: float,
    max_score: float | None,
    max_candidates: int,
    drop_lang_unknown: bool,
) -> list[dict]:
    # Keep only high-scoring candidates in memory (bounded).
    # Note: file is not sorted by score globally; we approximate by selecting top-N by score.
    import heapq

    heap: list[tuple[float, int, dict]] = []
    seen = 0
    with matches_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seen += 1
            try:
                score = float(row.get(score_key) or 0.0)
            except Exception:
                continue
            if score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue
            a = row.get(id_a)
            b = row.get(id_b)
            if not isinstance(a, str) or not isinstance(b, str) or not a or not b or a == b:
                continue
            lang = str(row.get(lang_key) or "unknown").strip() or "unknown"
            if drop_lang_unknown and lang == "unknown":
                continue
            entry = (score, seen, row)
            if len(heap) < max_candidates:
                heapq.heappush(heap, entry)
            else:
                if score > heap[0][0]:
                    heapq.heapreplace(heap, entry)
    heap.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [r for _, _, r in heap]


def build_post_post_pairs(
    *,
    posts_path: Path,
    matches_path: Path,
    out_path: Path,
    min_score: float,
    max_score: float | None,
    n_out: int,
    max_candidates: int,
    min_alnum: int,
    max_excerpt: int,
    drop_lang_unknown: bool,
    drop_submolts: set[str],
) -> None:
    candidates = top_pairs_from_csv(
        matches_path,
        id_a="doc_id",
        id_b="neighbor_id",
        lang_key="doc_lang",
        score_key="score",
        min_score=min_score,
        max_score=max_score,
        max_candidates=max_candidates,
        drop_lang_unknown=drop_lang_unknown,
    )
    wanted_posts: set[str] = set()
    for r in candidates:
        wanted_posts.add(str(r.get("doc_id") or ""))
        wanted_posts.add(str(r.get("neighbor_id") or ""))

    post_info = load_posts_info(posts_path, wanted_posts, max_excerpt=max_excerpt)

    out: list[dict] = []
    used_docs: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_text_pairs: set[tuple[str, str]] = set()
    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", (t or "").strip().lower())

    # Prefer cross-submolt for the public sample: more interpretable “transversalidad”.
    def is_cross(r: dict) -> bool:
        a = str(r.get("doc_id") or "")
        b = str(r.get("neighbor_id") or "")
        ai = post_info.get(a)
        bi = post_info.get(b)
        if not ai or not bi:
            return False
        return ai.submolt != bi.submolt

    ordered = sorted(candidates, key=lambda r: (is_cross(r), float(r.get("score") or 0.0)), reverse=True)

    for r in ordered:
        a = str(r.get("doc_id") or "")
        b = str(r.get("neighbor_id") or "")
        if not a or not b or a == b:
            continue
        if a in used_docs:
            continue
        key = tuple(sorted((a, b)))
        if key in seen_pairs:
            continue
        ai = post_info.get(a)
        bi = post_info.get(b)
        if not ai or not bi:
            continue
        if ai.submolt in drop_submolts or bi.submolt in drop_submolts:
            continue
        if alnum_count(ai.excerpt) < min_alnum or alnum_count(bi.excerpt) < min_alnum:
            continue
        if looks_like_template(ai.excerpt) or looks_like_template(bi.excerpt):
            continue
        ta = norm(ai.excerpt)
        tb = norm(bi.excerpt)
        if ta == tb:
            continue
        text_key = (ta, tb) if ta <= tb else (tb, ta)
        if text_key in seen_text_pairs:
            continue

        try:
            score = float(r.get("score") or 0.0)
        except Exception:
            score = 0.0

        out.append(
            {
                "doc_id": a,
                "neighbor_id": b,
                "score": score,
                "doc_lang": str(r.get("doc_lang") or ai.lang or "unknown"),
                "doc_submolt": ai.submolt,
                "neighbor_submolt": bi.submolt,
                "doc_created_at": ai.created_at,
                "neighbor_created_at": bi.created_at,
                "doc_excerpt": ai.excerpt,
                "neighbor_excerpt": bi.excerpt,
            }
        )
        used_docs.add(a)
        seen_pairs.add(key)
        seen_text_pairs.add(text_key)
        if len(out) >= n_out:
            break

    fieldnames = [
        "doc_id",
        "neighbor_id",
        "score",
        "doc_lang",
        "doc_submolt",
        "neighbor_submolt",
        "doc_created_at",
        "neighbor_created_at",
        "doc_excerpt",
        "neighbor_excerpt",
    ]
    write_csv(out_path, out, fieldnames)


def build_post_comment_pairs(
    *,
    posts_path: Path,
    comments_path: Path,
    matches_path: Path,
    out_path: Path,
    min_score: float,
    max_score: float | None,
    n_out: int,
    max_candidates: int,
    min_alnum: int,
    max_excerpt: int,
    drop_lang_unknown: bool,
    drop_submolts: set[str],
) -> None:
    candidates = top_pairs_from_csv(
        matches_path,
        id_a="post_id",
        id_b="comment_id",
        lang_key="lang",
        score_key="score",
        min_score=min_score,
        max_score=max_score,
        max_candidates=max_candidates,
        drop_lang_unknown=drop_lang_unknown,
    )

    wanted_posts: set[str] = set()
    wanted_comments: set[str] = set()
    for r in candidates:
        wanted_posts.add(str(r.get("post_id") or ""))
        wanted_comments.add(str(r.get("comment_id") or ""))

    post_info = load_posts_info(posts_path, wanted_posts, max_excerpt=max_excerpt)
    comment_info = load_comments_info(comments_path, wanted_comments, max_excerpt=max_excerpt)

    out: list[dict] = []
    used_posts: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_text_pairs: set[tuple[str, str]] = set()
    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", (t or "").strip().lower())

    def is_cross(r: dict) -> bool:
        return str(r.get("post_submolt") or "unknown") != str(r.get("comment_submolt") or "unknown")

    ordered = sorted(candidates, key=lambda r: (is_cross(r), float(r.get("score") or 0.0)), reverse=True)

    for r in ordered:
        post_id = str(r.get("post_id") or "")
        comment_id = str(r.get("comment_id") or "")
        if not post_id or not comment_id:
            continue
        if post_id in used_posts:
            continue
        key = (post_id, comment_id)
        if key in seen_pairs:
            continue

        lang = str(r.get("lang") or "unknown").strip() or "unknown"
        post_sub = str(r.get("post_submolt") or "unknown").strip() or "unknown"
        comment_sub = str(r.get("comment_submolt") or "unknown").strip() or "unknown"
        if post_sub in drop_submolts or comment_sub in drop_submolts:
            continue

        pi = post_info.get(post_id)
        ci = comment_info.get(comment_id)
        if not pi or not ci:
            continue
        if alnum_count(pi.excerpt) < min_alnum or alnum_count(ci.excerpt) < min_alnum:
            continue
        if looks_like_template(pi.excerpt) or looks_like_template(ci.excerpt):
            continue

        tp = norm(pi.excerpt)
        tc = norm(ci.excerpt)
        if tp == tc:
            continue
        text_key = (tp, tc) if tp <= tc else (tc, tp)
        if text_key in seen_text_pairs:
            continue

        try:
            score = float(r.get("score") or 0.0)
        except Exception:
            score = 0.0

        out.append(
            {
                "post_id": post_id,
                "comment_id": comment_id,
                "score": score,
                "lang": lang,
                "post_submolt": post_sub,
                "comment_submolt": comment_sub,
                "post_created_at": str(r.get("post_created_at") or pi.created_at or ""),
                "comment_created_at": str(r.get("comment_created_at") or ci.created_at or ""),
                "post_excerpt": pi.excerpt,
                "comment_excerpt": ci.excerpt,
            }
        )
        used_posts.add(post_id)
        seen_pairs.add(key)
        seen_text_pairs.add(text_key)
        if len(out) >= n_out:
            break

    fieldnames = [
        "post_id",
        "comment_id",
        "score",
        "lang",
        "post_submolt",
        "comment_submolt",
        "post_created_at",
        "comment_created_at",
        "post_excerpt",
        "comment_excerpt",
    ]
    write_csv(out_path, out, fieldnames)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build small, human-readable 'public_*_pairs_top.csv' tables from large match files.",
    )
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--matches-post-post", default="data/derived/embeddings/matches_embeddings.csv")
    parser.add_argument("--matches-post-comment", default="data/derived/embeddings_post_comment/matches_post_comment.csv")
    parser.add_argument("--out-post-post", default="data/derived/public_embeddings_pairs_top.csv")
    parser.add_argument(
        "--out-post-comment",
        default="data/derived/embeddings_post_comment/public_embeddings_post_comment_pairs_top.csv",
    )
    parser.add_argument("--min-score-post-post", type=float, default=0.95)
    parser.add_argument("--max-score-post-post", type=float, default=0.999999)
    parser.add_argument("--min-score-post-comment", type=float, default=0.93)
    parser.add_argument("--max-score-post-comment", type=float, default=0.999999)
    parser.add_argument("--n-out", type=int, default=120)
    parser.add_argument("--max-candidates", type=int, default=1200)
    parser.add_argument("--min-alnum", type=int, default=24, help="Min alphanumeric chars per excerpt to avoid emoji-only noise.")
    parser.add_argument("--max-excerpt", type=int, default=220)
    parser.add_argument("--keep-unknown-lang", action="store_true")
    parser.add_argument(
        "--drop-submolts",
        default="crab-rave",
        help="Comma-separated list of submolts to exclude from post→comment samples (default: crab-rave).",
    )
    args = parser.parse_args()

    posts_path = Path(args.posts)
    comments_path = Path(args.comments)
    matches_pp = Path(args.matches_post_post)
    matches_pc = Path(args.matches_post_comment)
    out_pp = Path(args.out_post_post)
    out_pc = Path(args.out_post_comment)
    drop_unknown = not bool(args.keep_unknown_lang)
    drop_submolts = {s.strip() for s in (args.drop_submolts or "").split(",") if s.strip()}

    build_post_post_pairs(
        posts_path=posts_path,
        matches_path=matches_pp,
        out_path=out_pp,
        min_score=args.min_score_post_post,
        max_score=args.max_score_post_post,
        n_out=args.n_out,
        max_candidates=args.max_candidates,
        min_alnum=args.min_alnum,
        max_excerpt=args.max_excerpt,
        drop_lang_unknown=drop_unknown,
        drop_submolts=drop_submolts,
    )

    build_post_comment_pairs(
        posts_path=posts_path,
        comments_path=comments_path,
        matches_path=matches_pc,
        out_path=out_pc,
        min_score=args.min_score_post_comment,
        max_score=args.max_score_post_comment,
        n_out=args.n_out,
        max_candidates=args.max_candidates,
        min_alnum=args.min_alnum,
        max_excerpt=args.max_excerpt,
        drop_lang_unknown=drop_unknown,
        drop_submolts=drop_submolts,
    )

    print(f"Wrote:\n- {out_pp}\n- {out_pc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
