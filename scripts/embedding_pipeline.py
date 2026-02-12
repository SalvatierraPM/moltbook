#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from langdetect import LangDetectException, detect
from sentence_transformers import SentenceTransformer

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover
    faiss = None
    FAISS_IMPORT_ERROR = exc
else:
    FAISS_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.text import clean_text  # noqa: E402


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


def count_jsonl(path: Path) -> int:
    count = 0
    for _ in iter_jsonl(path):
        count += 1
    return count


def detect_language(text: str) -> Optional[str]:
    if not text or len(text.strip()) < 10:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def post_text(post: dict) -> str:
    title = post.get("title") or ""
    content = post.get("content") or ""
    return f"{title}\n{content}".strip()


def comment_text(comment: dict) -> str:
    return (comment.get("content") or "").strip()


def load_post_submolt(posts_path: Path) -> Dict[str, Optional[str]]:
    mapping: Dict[str, Optional[str]] = {}
    for post in iter_jsonl(posts_path):
        pid = post.get("id")
        if not isinstance(pid, str):
            continue
        submolt = post.get("submolt")
        if isinstance(submolt, dict):
            submolt = submolt.get("name")
        mapping[pid] = submolt
    return mapping


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_progress(path: Path) -> Dict[str, int]:
    if not path.exists():
        return {"processed": 0, "total": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": 0, "total": 0}


def write_progress(path: Path, processed: int, total: int) -> None:
    payload = {"processed": processed, "total": total, "updated_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def embed_posts(
    posts_path: Path,
    out_dir: Path,
    model_name: str,
    batch_size: int,
    resume: bool,
    prefix: str,
) -> None:
    ensure_dir(out_dir)
    progress_path = out_dir / "embeddings_progress.json"
    meta_jsonl = out_dir / "posts_meta.jsonl"
    meta_parquet = out_dir / "posts_meta.parquet"
    embeddings_path = out_dir / "posts_embeddings.npy"
    manifest_path = out_dir / "manifest.json"

    total = count_jsonl(posts_path)
    if not resume:
        if embeddings_path.exists():
            embeddings_path.unlink()
        if meta_jsonl.exists():
            meta_jsonl.unlink()
        if meta_parquet.exists():
            meta_parquet.unlink()
        if progress_path.exists():
            progress_path.unlink()
    progress = load_progress(progress_path)
    processed = int(progress.get("processed", 0)) if resume else 0
    if processed > total:
        processed = 0

    if embeddings_path.exists() and meta_parquet.exists() and processed >= total:
        print("Embeddings already completed. Skipping embed step.")
        return

    print(f"Loading model {model_name} ...")
    model = SentenceTransformer(model_name)
    dim = model.get_sentence_embedding_dimension()

    if embeddings_path.exists():
        emb = np.memmap(embeddings_path, dtype="float32", mode="r+", shape=(total, dim))
    else:
        emb = np.memmap(embeddings_path, dtype="float32", mode="w+", shape=(total, dim))

    meta_fh = meta_jsonl.open("a", encoding="utf-8") if processed < total else None

    batch_texts: List[str] = []
    batch_indices: List[int] = []
    batch_meta: List[Dict] = []

    def flush_batch() -> None:
        nonlocal processed
        if not batch_indices:
            return
        texts = []
        idx_map = []
        for i, text in enumerate(batch_texts):
            if text:
                texts.append(f"{prefix}{text}")
                idx_map.append(i)
        if texts:
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        else:
            vectors = np.zeros((0, dim), dtype="float32")

        out = np.zeros((len(batch_texts), dim), dtype="float32")
        if len(idx_map) > 0:
            out[idx_map] = vectors

        emb[np.array(batch_indices)] = out

        for row in batch_meta:
            if meta_fh:
                meta_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        processed = max(processed, batch_indices[-1] + 1)
        write_progress(progress_path, processed, total)
        if processed % (batch_size * 20) == 0 or processed == total:
            print(f"Processed {processed}/{total} posts")

        batch_texts.clear()
        batch_indices.clear()
        batch_meta.clear()

    for i, post in enumerate(iter_jsonl(posts_path)):
        if i < processed:
            continue
        text = post_text(post)
        lang = detect_language(text)
        submolt = post.get("submolt")
        if isinstance(submolt, dict):
            submolt = submolt.get("name")
        batch_texts.append(clean_text(text))
        batch_indices.append(i)
        batch_meta.append(
            {
                "doc_id": post.get("id"),
                "doc_type": "post",
                "post_id": post.get("id"),
                "submolt": submolt,
                "created_at": post.get("created_at"),
                "lang": lang or "unknown",
            }
        )
        if len(batch_texts) >= batch_size:
            flush_batch()

    flush_batch()
    emb.flush()

    if meta_fh:
        meta_fh.close()

    if processed >= total:
        print("Embedding step finished. Building parquet metadata...")
        meta_rows = []
        for row in iter_jsonl(meta_jsonl):
            meta_rows.append(row)
        if meta_rows:
            pd.DataFrame(meta_rows).to_parquet(meta_parquet, index=False)

        manifest = {
            "model": model_name,
            "dim": dim,
            "total": total,
            "prefix": prefix,
            "normalized": True,
            "doc_type": "post",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        write_progress(progress_path, total, total)
        print(f"Embeddings written to {embeddings_path}")


def embed_comments(
    comments_path: Path,
    posts_path: Path,
    out_dir: Path,
    model_name: str,
    batch_size: int,
    resume: bool,
    prefix: str,
) -> None:
    ensure_dir(out_dir)
    progress_path = out_dir / "embeddings_progress.json"
    meta_jsonl = out_dir / "comments_meta.jsonl"
    meta_parquet = out_dir / "comments_meta.parquet"
    embeddings_path = out_dir / "comments_embeddings.npy"
    manifest_path = out_dir / "manifest.json"

    total = count_jsonl(comments_path)
    if not resume:
        if embeddings_path.exists():
            embeddings_path.unlink()
        if meta_jsonl.exists():
            meta_jsonl.unlink()
        if meta_parquet.exists():
            meta_parquet.unlink()
        if progress_path.exists():
            progress_path.unlink()
    progress = load_progress(progress_path)
    processed = int(progress.get("processed", 0)) if resume else 0
    if processed > total:
        processed = 0

    if embeddings_path.exists() and meta_parquet.exists() and processed >= total:
        print("Embeddings already completed. Skipping embed step.")
        return

    print(f"Loading model {model_name} ...")
    model = SentenceTransformer(model_name)
    dim = model.get_sentence_embedding_dimension()

    post_submolt = load_post_submolt(posts_path)

    if embeddings_path.exists():
        emb = np.memmap(embeddings_path, dtype="float32", mode="r+", shape=(total, dim))
    else:
        emb = np.memmap(embeddings_path, dtype="float32", mode="w+", shape=(total, dim))

    meta_fh = meta_jsonl.open("a", encoding="utf-8") if processed < total else None

    batch_texts: List[str] = []
    batch_indices: List[int] = []
    batch_meta: List[Dict] = []

    def flush_batch() -> None:
        nonlocal processed
        if not batch_indices:
            return
        texts = []
        idx_map = []
        for i, text in enumerate(batch_texts):
            if text:
                texts.append(f"{prefix}{text}")
                idx_map.append(i)
        if texts:
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        else:
            vectors = np.zeros((0, dim), dtype="float32")

        out = np.zeros((len(batch_texts), dim), dtype="float32")
        if len(idx_map) > 0:
            out[idx_map] = vectors

        emb[np.array(batch_indices)] = out

        for row in batch_meta:
            if meta_fh:
                meta_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        processed = max(processed, batch_indices[-1] + 1)
        write_progress(progress_path, processed, total)
        if processed % (batch_size * 20) == 0 or processed == total:
            print(f"Processed {processed}/{total} comments")

        batch_texts.clear()
        batch_indices.clear()
        batch_meta.clear()

    for i, comment in enumerate(iter_jsonl(comments_path)):
        if i < processed:
            continue
        text = comment_text(comment)
        lang = detect_language(text)
        post_id = comment.get("post_id")
        submolt = post_submolt.get(post_id) if isinstance(post_id, str) else None
        batch_texts.append(clean_text(text))
        batch_indices.append(i)
        batch_meta.append(
            {
                "doc_id": comment.get("id"),
                "doc_type": "comment",
                "post_id": post_id,
                "parent_id": comment.get("parent_id"),
                "submolt": submolt,
                "created_at": comment.get("created_at"),
                "lang": lang or "unknown",
            }
        )
        if len(batch_texts) >= batch_size:
            flush_batch()

    flush_batch()
    emb.flush()

    if meta_fh:
        meta_fh.close()

    if processed >= total:
        print("Embedding step finished. Building parquet metadata...")
        meta_rows = []
        for row in iter_jsonl(meta_jsonl):
            meta_rows.append(row)
        if meta_rows:
            pd.DataFrame(meta_rows).to_parquet(meta_parquet, index=False)

        manifest = {
            "model": model_name,
            "dim": dim,
            "total": total,
            "prefix": prefix,
            "normalized": True,
            "doc_type": "comment",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        write_progress(progress_path, total, total)
        print(f"Embeddings written to {embeddings_path}")


def _load_meta(out_dir: Path) -> pd.DataFrame:
    meta_parquet = out_dir / "posts_meta.parquet"
    meta_jsonl = out_dir / "posts_meta.jsonl"
    if (out_dir / "comments_meta.parquet").exists():
        meta_parquet = out_dir / "comments_meta.parquet"
    if (out_dir / "comments_meta.jsonl").exists():
        meta_jsonl = out_dir / "comments_meta.jsonl"
    if meta_parquet.exists():
        return pd.read_parquet(meta_parquet)
    rows = list(iter_jsonl(meta_jsonl))
    return pd.DataFrame(rows)


def build_indexes(out_dir: Path, hnsw_m: int, ef_construction: int) -> None:
    if faiss is None:
        raise RuntimeError(f"faiss import failed: {FAISS_IMPORT_ERROR}")

    meta = _load_meta(out_dir)
    embeddings_path = out_dir / "posts_embeddings.npy"
    if not embeddings_path.exists():
        embeddings_path = out_dir / "comments_embeddings.npy"
    if meta.empty or not embeddings_path.exists():
        print("Missing embeddings or metadata. Run embed step first.")
        return

    manifest = {}
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dim = int(manifest.get("dim", 0)) or 384
    total = len(meta)
    # If metadata count exceeds embedding file rows (e.g., duplicate doc_ids),
    # clamp to file size to avoid mmap size errors.
    file_bytes = embeddings_path.stat().st_size
    max_rows = file_bytes // (4 * dim) if dim else total
    if max_rows < total:
        total = max_rows
        meta = meta.iloc[:total].reset_index(drop=True)

    emb = np.memmap(embeddings_path, dtype="float32", mode="r", shape=(total, dim))

    index_dir = out_dir / "indexes"
    ensure_dir(index_dir)

    langs = meta["lang"].fillna("unknown").astype(str).unique().tolist()
    summary = []
    for lang in sorted(langs):
        idxs = meta.index[meta["lang"].fillna("unknown").astype(str) == lang].to_numpy()
        if len(idxs) < 2:
            continue
        index_path = index_dir / f"index_{lang}.faiss"
        ids_path = index_dir / f"index_{lang}_ids.npy"
        if index_path.exists() and ids_path.exists():
            summary.append({"lang": lang, "count": len(idxs), "status": "exists"})
            continue

        index = faiss.IndexHNSWFlat(dim, hnsw_m, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = ef_construction
        index.hnsw.efSearch = 128

        chunk = 8192
        for start in range(0, len(idxs), chunk):
            sl = idxs[start : start + chunk]
            vecs = np.array(emb[sl], dtype="float32")
            index.add(vecs)

        faiss.write_index(index, str(index_path))
        np.save(ids_path, meta.loc[idxs, "doc_id"].astype(str).to_numpy())
        summary.append({"lang": lang, "count": len(idxs), "status": "built"})

    (index_dir / "index_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Indexes built in {index_dir}")


def compute_matches(out_dir: Path, top_k: int) -> None:
    if faiss is None:
        raise RuntimeError(f"faiss import failed: {FAISS_IMPORT_ERROR}")

    meta = _load_meta(out_dir)
    embeddings_path = out_dir / "posts_embeddings.npy"
    if not embeddings_path.exists():
        embeddings_path = out_dir / "comments_embeddings.npy"
    index_dir = out_dir / "indexes"
    if meta.empty or not embeddings_path.exists() or not index_dir.exists():
        print("Missing embeddings or indexes. Run embed + index first.")
        return

    manifest = {}
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dim = int(manifest.get("dim", 0)) or 384

    total = len(meta)
    file_bytes = embeddings_path.stat().st_size
    max_rows = file_bytes // (4 * dim) if dim else total
    if max_rows < total:
        total = max_rows
        meta = meta.iloc[:total].reset_index(drop=True)
    emb = np.memmap(embeddings_path, dtype="float32", mode="r", shape=(total, dim))

    output_path = out_dir / "matches_embeddings.csv"
    import csv
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["doc_id", "neighbor_id", "score", "doc_lang", "neighbor_lang"])

        for lang in sorted(meta["lang"].fillna("unknown").astype(str).unique()):
            index_path = index_dir / f"index_{lang}.faiss"
            ids_path = index_dir / f"index_{lang}_ids.npy"
            if not index_path.exists() or not ids_path.exists():
                continue
            idxs = meta.index[meta["lang"].fillna("unknown").astype(str) == lang].to_numpy()
            if len(idxs) < 2:
                continue

            index = faiss.read_index(str(index_path))
            ids = np.load(ids_path, allow_pickle=True)

            chunk = 2048
            for start in range(0, len(idxs), chunk):
                sl = idxs[start : start + chunk]
                vecs = np.array(emb[sl], dtype="float32")
                scores, neighbors = index.search(vecs, min(top_k + 1, len(ids)))

                for row_i, doc_idx in enumerate(sl):
                    doc_id = str(meta.loc[doc_idx, "doc_id"])
                    emitted = 0
                    for j in range(scores.shape[1]):
                        neighbor_id = str(ids[neighbors[row_i, j]])
                        if neighbor_id == doc_id:
                            continue
                        score = float(scores[row_i, j])
                        writer.writerow([doc_id, neighbor_id, f"{score:.6f}", lang, lang])
                        emitted += 1
                        if emitted >= top_k:
                            break

    print(f"Matches written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embeddings + FAISS pipeline (resumable).")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived/embeddings")
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prefix", default="passage: ")
    parser.add_argument("--doc-type", choices=["post", "comment"], default="post")
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--match", action="store_true")
    parser.add_argument("--match-top-k", type=int, default=5)
    parser.add_argument("--hnsw-m", type=int, default=32)
    parser.add_argument("--ef-construction", type=int, default=200)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    posts_path = Path(args.posts)
    comments_path = Path(args.comments)

    if args.doc_type == "comment":
        embed_comments(
            comments_path,
            posts_path,
            out_dir,
            model_name=args.model,
            batch_size=args.batch_size,
            resume=args.resume,
            prefix=args.prefix,
        )
    else:
        embed_posts(
            posts_path,
            out_dir,
            model_name=args.model,
            batch_size=args.batch_size,
            resume=args.resume,
            prefix=args.prefix,
        )

    if args.build_index:
        build_indexes(out_dir, hnsw_m=args.hnsw_m, ef_construction=args.ef_construction)

    if args.match:
        compute_matches(out_dir, top_k=args.match_top_k)


if __name__ == "__main__":
    main()
