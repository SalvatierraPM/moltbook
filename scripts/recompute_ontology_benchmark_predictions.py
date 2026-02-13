#!/usr/bin/env python3
from __future__ import annotations

"""
Recompute `pred_act_*` columns for an existing benchmark CSV.

Why:
- We want to keep human labels stable while iterating on the speech-act heuristics
  (src/moltbook_analysis/analyze/language_ontology.py).
- Rebuilding the benchmark scaffold from signals can reshuffle rows; this script updates
  predictions in-place by `doc_id`.
"""

import argparse
from pathlib import Path
import sys

import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.language_ontology import speech_act_features  # noqa: E402


ACT_KEYS = [
    "request",
    "offer",
    "promise",
    "declaration",
    "judgment",
    "assertion",
    "acceptance",
    "rejection",
    "clarification",
]

ACT_KEY_TO_ES = {
    "request": "peticion",
    "offer": "oferta",
    "promise": "promesa",
    "declaration": "declaracion",
    "judgment": "juicio",
    "assertion": "afirmacion",
    "acceptance": "aceptacion",
    "rejection": "rechazo",
    "clarification": "aclaracion",
    "unknown": "otro",
}


def load_context_rows(path: Path, doc_ids: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["doc_id", "text"])
    dataset = ds.dataset(str(path))
    filt = ds.field("doc_id").isin(doc_ids)
    table = dataset.to_table(filter=filt, columns=["doc_id", "text"])
    return table.to_pandas()


def predict_act(text: str) -> tuple[str, int, str]:
    feats = speech_act_features(text or "")
    scores = {k: int(feats.get(f"act_{k}", 0) or 0) for k in ACT_KEYS}
    max_score = max(scores.values()) if scores else 0
    if max_score <= 0:
        return ("unknown", 0, ACT_KEY_TO_ES["unknown"])
    key = max(scores.items(), key=lambda kv: kv[1])[0]
    return (key, int(max_score), ACT_KEY_TO_ES.get(key, key))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute pred_act_* for ontology benchmark sample by doc_id.")
    parser.add_argument("--benchmark", default="data/derived/ontology_benchmark_sample.csv")
    parser.add_argument("--context-posts", default="data/derived/context_posts.parquet")
    parser.add_argument("--context-comments", default="data/derived/context_comments.parquet")
    args = parser.parse_args()

    bench_path = Path(args.benchmark)
    if not bench_path.exists():
        raise SystemExit(f"Benchmark not found: {bench_path}")

    df = pd.read_csv(bench_path)
    for col in ["doc_id", "doc_type"]:
        if col not in df.columns:
            raise SystemExit(f"Benchmark missing required column: {col}")

    doc_ids = df["doc_id"].fillna("").astype(str).tolist()
    posts_ids = df[df["doc_type"] == "post"]["doc_id"].fillna("").astype(str).tolist()
    comments_ids = df[df["doc_type"] != "post"]["doc_id"].fillna("").astype(str).tolist()

    posts = load_context_rows(Path(args.context_posts), posts_ids)
    comments = load_context_rows(Path(args.context_comments), comments_ids)
    ctx = pd.concat([posts, comments], ignore_index=True).drop_duplicates(subset=["doc_id"])
    text_by_id = dict(zip(ctx["doc_id"].astype(str), ctx["text"].astype(str)))

    updated = 0
    missing = 0
    pred_key = []
    pred_es = []
    pred_score = []
    for doc_id in doc_ids:
        text = text_by_id.get(str(doc_id))
        if text is None:
            missing += 1
            pred_key.append("unknown")
            pred_es.append(ACT_KEY_TO_ES["unknown"])
            pred_score.append(0)
            continue
        k, s, es = predict_act(text)
        pred_key.append(k)
        pred_es.append(es)
        pred_score.append(s)
        updated += 1

    df["pred_act_key"] = pred_key
    df["pred_act_es"] = pred_es
    df["pred_act_score"] = pred_score
    df.to_csv(bench_path, index=False)

    print(f"Updated rows: {updated}/{len(df)}")
    if missing:
        print(f"Missing context for doc_id: {missing} (set to unknown)")
    print(f"Wrote: {bench_path}")


if __name__ == "__main__":
    main()

