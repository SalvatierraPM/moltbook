#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import numpy as np
import pandas as pd

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover
    faiss = None
    FAISS_IMPORT_ERROR = exc
else:
    FAISS_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]


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


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_meta(dir_path: Path, doc_type: str) -> pd.DataFrame:
    parquet = dir_path / f"{doc_type}_meta.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    jsonl = dir_path / f"{doc_type}_meta.jsonl"
    return pd.DataFrame(list(iter_jsonl(jsonl)))


def load_manifest(dir_path: Path) -> dict:
    manifest_path = dir_path / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {}


def get_embeddings_path(dir_path: Path, doc_type: str) -> Path:
    if doc_type == "post":
        return dir_path / "posts_embeddings.npy"
    return dir_path / "comments_embeddings.npy"


def build_indexes(meta: pd.DataFrame, embeddings_path: Path, out_dir: Path, dim: int, hnsw_m: int, ef: int) -> None:
    if faiss is None:
        raise RuntimeError(f"faiss import failed: {FAISS_IMPORT_ERROR}")
    ensure_dir(out_dir)
    emb = np.memmap(embeddings_path, dtype="float32", mode="r", shape=(len(meta), dim))
    langs = meta["lang"].fillna("unknown").astype(str).unique().tolist()
    summary = []
    for lang in sorted(langs):
        idxs = meta.index[meta["lang"].fillna("unknown").astype(str) == lang].to_numpy()
        if len(idxs) < 2:
            continue
        index_path = out_dir / f"index_{lang}.faiss"
        ids_path = out_dir / f"index_{lang}_ids.npy"
        if index_path.exists() and ids_path.exists():
            summary.append({"lang": lang, "count": len(idxs), "status": "exists"})
            continue
        index = faiss.IndexHNSWFlat(dim, hnsw_m, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = ef
        index.hnsw.efSearch = 128
        chunk = 8192
        for start in range(0, len(idxs), chunk):
            sl = idxs[start : start + chunk]
            vecs = np.array(emb[sl], dtype="float32")
            index.add(vecs)
        faiss.write_index(index, str(index_path))
        np.save(ids_path, meta.loc[idxs, "doc_id"].astype(str).to_numpy())
        summary.append({"lang": lang, "count": len(idxs), "status": "built"})

    (out_dir / "index_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"https?://\\S+|www\\.\\S+", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def truncate(text: str, max_len: int = 160) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def build_excerpt_map(path: Path, ids: Set[str], is_post: bool) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in iter_jsonl(path):
        doc_id = row.get("id")
        if doc_id not in ids:
            continue
        if is_post:
            title = row.get("title") or ""
            content = row.get("content") or ""
            text = f"{title}\\n{content}".strip()
        else:
            text = row.get("content") or ""
        out[doc_id] = truncate(clean_text(text), 180)
        if len(out) >= len(ids):
            break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute post-to-comment embedding matches (same-lang).")
    parser.add_argument("--posts-dir", default="data/derived/embeddings")
    parser.add_argument("--comments-dir", default="data/derived/embeddings_comments")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived/embeddings_post_comment")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--hnsw-m", type=int, default=32)
    parser.add_argument("--ef-construction", type=int, default=200)
    parser.add_argument("--resume", action="store_true", help="Resume from existing output file if present.")
    args = parser.parse_args()

    posts_dir = Path(args.posts_dir)
    comments_dir = Path(args.comments_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    meta_posts = load_meta(posts_dir, "posts")
    meta_comments = load_meta(comments_dir, "comments")
    if meta_posts.empty or meta_comments.empty:
        raise RuntimeError("Missing metadata for posts or comments.")

    manifest_posts = load_manifest(posts_dir)
    manifest_comments = load_manifest(comments_dir)
    dim = int(manifest_posts.get("dim", 0) or manifest_comments.get("dim", 0) or 384)

    posts_path = get_embeddings_path(posts_dir, "post")
    comments_path = get_embeddings_path(comments_dir, "comment")
    posts_rows = posts_path.stat().st_size // (4 * dim)
    comments_rows = comments_path.stat().st_size // (4 * dim)
    if len(meta_posts) > posts_rows:
        meta_posts = meta_posts.iloc[:posts_rows].reset_index(drop=True)
    if len(meta_comments) > comments_rows:
        meta_comments = meta_comments.iloc[:comments_rows].reset_index(drop=True)
    emb_posts = np.memmap(posts_path, dtype="float32", mode="r", shape=(len(meta_posts), dim))
    emb_comments = np.memmap(comments_path, dtype="float32", mode="r", shape=(len(meta_comments), dim))

    comment_index_dir = comments_dir / "indexes"
    if not comment_index_dir.exists() or not any(comment_index_dir.glob("index_*.faiss")):
        build_indexes(meta_comments, get_embeddings_path(comments_dir, "comment"), comment_index_dir, dim, args.hnsw_m, args.ef_construction)

    comment_lookup = meta_comments.set_index("doc_id")
    output_matches = out_dir / "matches_post_comment.csv"
    progress_path = out_dir / "matches_post_comment.progress.json"

    def load_progress_fallback() -> Tuple[str | None, int]:
        if not output_matches.exists():
            return None, 0
        try:
            csv.field_size_limit(10 * 1024 * 1024)
        except Exception:
            pass
        last_lang = None
        count_last = 0
        with output_matches.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lang = row.get("lang") or "unknown"
                if lang != last_lang:
                    last_lang = lang
                    count_last = 0
                count_last += 1
        if not last_lang:
            return None, 0
        ids_path = comment_index_dir / f"index_{last_lang}_ids.npy"
        if not ids_path.exists():
            return None, 0
        per_post_k = min(args.top_k, len(np.load(ids_path, allow_pickle=True)))
        if per_post_k <= 0:
            return None, 0
        remainder = count_last % per_post_k
        if remainder:
            # Trim partial rows for the last post to avoid duplicates on resume.
            lines = output_matches.read_text(encoding="utf-8").splitlines()
            keep = lines[:-remainder] if remainder < len(lines) else lines[:1]
            output_matches.write_text("\n".join(keep) + "\n", encoding="utf-8")
            count_last -= remainder
        return last_lang, count_last // per_post_k

    resume_lang = None
    resume_offset = 0
    if args.resume:
        if progress_path.exists():
            try:
                progress = json.loads(progress_path.read_text(encoding="utf-8"))
                resume_lang = progress.get("lang")
                resume_offset = int(progress.get("post_offset", 0) or 0)
            except Exception:
                resume_lang, resume_offset = load_progress_fallback()
        else:
            resume_lang, resume_offset = load_progress_fallback()

    file_exists = output_matches.exists()
    mode = "a" if args.resume and file_exists else "w"
    with output_matches.open(mode, encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if mode == "w":
            writer.writerow([
                "post_id",
                "comment_id",
                "score",
                "lang",
                "post_submolt",
                "comment_submolt",
                "post_created_at",
                "comment_created_at",
            ])

        post_langs = meta_posts["lang"].fillna("unknown").astype(str).unique().tolist()
        for lang in sorted(post_langs):
            if resume_lang and lang < resume_lang:
                continue
            index_path = comment_index_dir / f"index_{lang}.faiss"
            ids_path = comment_index_dir / f"index_{lang}_ids.npy"
            if not index_path.exists() or not ids_path.exists():
                continue

            post_idxs = meta_posts.index[meta_posts["lang"].fillna("unknown").astype(str) == lang].to_numpy()
            if len(post_idxs) == 0:
                continue

            index = faiss.read_index(str(index_path))
            comment_ids = np.load(ids_path, allow_pickle=True)

            chunk = 2048
            start_offset = 0
            if resume_lang == lang:
                start_offset = max(0, min(resume_offset, len(post_idxs)))
                resume_lang = None
                resume_offset = 0
            for start in range(start_offset, len(post_idxs), chunk):
                sl = post_idxs[start : start + chunk]
                vecs = np.array(emb_posts[sl], dtype="float32")
                scores, neighbors = index.search(vecs, min(args.top_k, len(comment_ids)))

                for row_i, post_idx in enumerate(sl):
                    post_id = str(meta_posts.loc[post_idx, "doc_id"])
                    post_submolt = meta_posts.loc[post_idx, "submolt"]
                    post_created = meta_posts.loc[post_idx, "created_at"]
                    for j in range(scores.shape[1]):
                        comment_id = str(comment_ids[neighbors[row_i, j]])
                        if comment_id not in comment_lookup.index:
                            continue
                        comment_row = comment_lookup.loc[comment_id]
                        writer.writerow([
                            post_id,
                            comment_id,
                            f"{float(scores[row_i, j]):.6f}",
                            lang,
                            post_submolt,
                            comment_row.get("submolt"),
                            post_created,
                            comment_row.get("created_at"),
                        ])
                progress_path.write_text(
                    json.dumps(
                        {
                            "lang": lang,
                            "post_offset": int(start + len(sl)),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    # Summary + public samples
    matches = pd.read_csv(output_matches)
    summary = {
        "model": manifest_posts.get("model") or manifest_comments.get("model"),
        "total_posts": int(len(meta_posts)),
        "total_comments": int(len(meta_comments)),
        "total_matches": int(len(matches)),
        "mean_score": float(matches["score"].mean()) if not matches.empty else 0.0,
        "median_score": float(matches["score"].median()) if not matches.empty else 0.0,
        "langs_indexed": int(matches["lang"].nunique()) if not matches.empty else 0,
        "same_submolt_rate": float((matches["post_submolt"] == matches["comment_submolt"]).mean()) if not matches.empty else 0.0,
        "cross_submolt_rate": float((matches["post_submolt"] != matches["comment_submolt"]).mean()) if not matches.empty else 0.0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "public_embeddings_post_comment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lang_df = (
        matches.groupby("lang")
        .agg(matches=("post_id", "count"), mean_score=("score", "mean"))
        .reset_index()
        .sort_values("matches", ascending=False)
        .head(12)
    )
    lang_df.to_csv(out_dir / "public_embeddings_post_comment_lang_top.csv", index=False)

    top_pairs = matches.sort_values("score", ascending=False).head(12)
    needed_posts: Set[str] = set(top_pairs["post_id"])
    needed_comments: Set[str] = set(top_pairs["comment_id"])
    post_excerpt = build_excerpt_map(Path(args.posts), needed_posts, is_post=True)
    comment_excerpt = build_excerpt_map(Path(args.comments), needed_comments, is_post=False)

    top_pairs = top_pairs.copy()
    top_pairs["post_excerpt"] = top_pairs["post_id"].map(post_excerpt).fillna("")
    top_pairs["comment_excerpt"] = top_pairs["comment_id"].map(comment_excerpt).fillna("")
    top_pairs.to_csv(out_dir / "public_embeddings_post_comment_pairs_top.csv", index=False)

    if progress_path.exists():
        progress_path.unlink()

    print("Post-comment matches and public summaries written to", out_dir)


if __name__ == "__main__":
    main()
