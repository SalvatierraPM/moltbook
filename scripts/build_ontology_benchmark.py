#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from langdetect import detect, DetectorFactory, LangDetectException


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


def collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def detect_lang(text: str, min_len: int = 20) -> str | None:
    t = (text or "").strip()
    if len(t) < min_len:
        return None
    try:
        return detect(t)
    except LangDetectException:
        return None


def load_signals(path: Path, columns: list[str]) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema.names)
    cols = [c for c in columns if c in available]
    df = pd.read_parquet(path, engine="pyarrow", columns=cols)
    # Ensure expected columns exist even if future schema changes.
    for col in ["doc_id", "doc_type", "created_at", "lang", "submolt", "title", "text"]:
        if col not in df.columns:
            df[col] = None
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a small labeled benchmark scaffold for ontology speech acts (multilingual)."
    )
    parser.add_argument("--signals-posts", default="data/derived/signals_posts.parquet")
    parser.add_argument("--signals-comments", default="data/derived/signals_comments.parquet")
    parser.add_argument("--out", default="data/derived/ontology_benchmark_sample.csv")
    parser.add_argument("--langs", default="en,es,pt")
    parser.add_argument("--per-lang", type=int, default=80)
    parser.add_argument("--min-tokens", type=int, default=6)
    parser.add_argument("--excerpt-chars", type=int, default=520)
    parser.add_argument("--pool-size", type=int, default=24000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    DetectorFactory.seed = int(args.seed)

    posts_path = Path(args.signals_posts)
    comments_path = Path(args.signals_comments)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    act_cols = [f"act_{k}" for k in ACT_KEYS]
    base_cols = [
        "doc_id",
        "doc_type",
        "created_at",
        "lang",
        "submolt",
        "title",
        "text",
        "token_count",
    ]
    cols = list(dict.fromkeys(base_cols + act_cols))

    df_posts = load_signals(posts_path, columns=cols) if posts_path.exists() else pd.DataFrame()
    df_comments = load_signals(comments_path, columns=cols) if comments_path.exists() else pd.DataFrame()

    rows = []
    for df in [df_posts, df_comments]:
        if df.empty:
            continue
        df = df.copy()
        if "token_count" in df.columns:
            df = df[df["token_count"].fillna(0) >= args.min_tokens]
        # If the lang column exists but is empty/null (common when signals were generated with --skip-lang-detect),
        # we'll detect language on a sampled pool later.
        if "lang" in df.columns and df["lang"].notna().any():
            df = df[df["lang"].notna() & (df["lang"].astype(str).str.len() >= 2)]

        for c in act_cols:
            if c not in df.columns:
                df[c] = 0
        acts = df[act_cols].fillna(0).astype(int)
        max_score = acts.max(axis=1).astype(int)
        pred_key = acts.idxmax(axis=1).str.replace("act_", "", regex=False)
        df["pred_act_key"] = pred_key.where(max_score > 0, "unknown")
        df["pred_act_score"] = max_score
        df["pred_act_es"] = df["pred_act_key"].map(ACT_KEY_TO_ES).fillna(df["pred_act_key"])

        keep_cols = [
            "doc_id",
            "doc_type",
            "created_at",
            "lang",
            "submolt",
            "title",
            "text",
            "pred_act_key",
            "pred_act_es",
            "pred_act_score",
        ]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = None
        rows.append(df[keep_cols])

    if not rows:
        raise SystemExit("No signals data found; run scripts/derive_signals.py first.")

    all_df = pd.concat(rows, ignore_index=True)

    langs = [l.strip() for l in str(args.langs).split(",") if l.strip()]

    # Build a pool for lang detection if necessary (avoid full-corpus langdetect).
    pool_n = min(int(args.pool_size), len(all_df))
    pool = all_df.sample(n=pool_n, random_state=int(args.seed)).reset_index(drop=True)

    if "lang" not in pool.columns or not pool["lang"].notna().any():
        # Detect language on the pool using the sampled excerpt (fast, reproducible enough).
        post_mask = pool["doc_type"] == "post"
        full_text = pd.Series([""] * len(pool))
        if post_mask.any():
            full_text.loc[post_mask] = (
                pool.loc[post_mask, "title"].fillna("").astype(str)
                + "\n"
                + pool.loc[post_mask, "text"].fillna("").astype(str)
            ).str.strip()
        if (~post_mask).any():
            full_text.loc[~post_mask] = pool.loc[~post_mask, "text"].fillna("").astype(str)
        pool["lang"] = full_text.map(collapse_ws).map(detect_lang)

    sampled = []
    for lang in langs:
        block = pool[pool["lang"] == lang].copy()
        if block.empty:
            continue
        n = min(int(args.per_lang), len(block))
        sampled.append(block.sample(n=n, random_state=int(args.seed)))

    if not sampled:
        raise SystemExit("No rows matched requested langs; check --langs or signals lang coverage.")

    out_df = pd.concat(sampled, ignore_index=True).drop_duplicates(subset=["doc_id"])
    out_df = out_df.sample(frac=1.0, random_state=int(args.seed)).reset_index(drop=True)
    out_df.insert(0, "sample_id", [f"S{idx+1:04d}" for idx in range(len(out_df))])
    # Build excerpt only for sampled rows to keep generation fast.
    post_mask = out_df["doc_type"] == "post"
    full_text = pd.Series([""] * len(out_df))
    if post_mask.any():
        full_text.loc[post_mask] = (
            out_df.loc[post_mask, "title"].fillna("").astype(str)
            + "\n"
            + out_df.loc[post_mask, "text"].fillna("").astype(str)
        ).str.strip()
    if (~post_mask).any():
        full_text.loc[~post_mask] = out_df.loc[~post_mask, "text"].fillna("").astype(str)
    out_df["text_excerpt"] = full_text.map(collapse_ws).str.slice(0, int(args.excerpt_chars))
    out_df = out_df.drop(columns=["title", "text"], errors="ignore")
    out_df["label_act_es"] = ""
    out_df["label_notes"] = ""

    out_df.to_csv(out_path, index=False)
    print(f"Wrote benchmark scaffold: {out_path} (rows={len(out_df)})")


if __name__ == "__main__":
    main()
