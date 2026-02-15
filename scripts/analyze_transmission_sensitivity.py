#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_THRESHOLDS = "0.70,0.75,0.80,0.85,0.90,0.93,0.95"


def parse_thresholds(raw: str) -> list[float]:
    out: list[float] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    # Keep stable order (high -> low) and unique
    seen = set()
    uniq: list[float] = []
    for t in sorted(out, reverse=True):
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def topk(counter: Counter[str], k: int) -> list[dict[str, object]]:
    items = counter.most_common(k)
    total = sum(counter.values()) or 1
    return [{"key": key, "count": int(count), "share": float(count) / float(total)} for key, count in items]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analisis de sensibilidad: cuantas parejas post→coment pasan distintos thresholds de similitud."
    )
    parser.add_argument(
        "--matches",
        default="data/derived/embeddings_post_comment/matches_post_comment.csv",
        help="CSV con pares (post_id, comment_id, score, lang, post_submolt, comment_submolt, ...).",
    )
    parser.add_argument(
        "--out",
        default="data/derived/transmission_threshold_sensitivity.json",
        help="Ruta JSON de salida.",
    )
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS, help="Lista separada por coma (ej: 0.8,0.85,0.9).")
    parser.add_argument("--topk", type=int, default=6, help="Top-K lenguajes/submolts por threshold.")
    args = parser.parse_args()

    matches_path = Path(args.matches)
    out_path = Path(args.out)
    thresholds = parse_thresholds(args.thresholds)
    if not thresholds:
        raise SystemExit("No thresholds provided.")

    # Aggregates per threshold.
    counts = {t: 0 for t in thresholds}
    same_submolt = {t: 0 for t in thresholds}
    lang_counts = {t: Counter() for t in thresholds}
    post_submolt_counts = {t: Counter() for t in thresholds}
    comment_submolt_counts = {t: Counter() for t in thresholds}

    # Score histogram (0.00-0.99 in 0.01 bins; 1.00 collapses into last bin).
    hist_bins = [0] * 100
    n_rows = 0
    min_score = 1.0
    max_score = 0.0

    print(f"[transmission] Reading {matches_path} ...")
    with matches_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_rows += 1
            if n_rows % 200_000 == 0:
                print(f"[transmission] Processed {n_rows:,} rows ...")
            try:
                score = float(row.get("score") or 0.0)
            except Exception:
                continue

            if score < min_score:
                min_score = score
            if score > max_score:
                max_score = score
            idx = int(score * 100)
            if idx < 0:
                idx = 0
            if idx > 99:
                idx = 99
            hist_bins[idx] += 1

            lang = (row.get("lang") or "unknown").strip() or "unknown"
            post_sub = (row.get("post_submolt") or "unknown").strip() or "unknown"
            comment_sub = (row.get("comment_submolt") or "unknown").strip() or "unknown"
            is_same_sub = post_sub == comment_sub

            for t in thresholds:
                if score < t:
                    continue
                counts[t] += 1
                lang_counts[t][lang] += 1
                post_submolt_counts[t][post_sub] += 1
                comment_submolt_counts[t][comment_sub] += 1
                if is_same_sub:
                    same_submolt[t] += 1

    thresholds_out: list[dict[str, object]] = []
    for t in sorted(thresholds):
        c = counts[t]
        thresholds_out.append(
            {
                "threshold": t,
                "pair_count": int(c),
                "share_same_submolt": (float(same_submolt[t]) / float(c)) if c else 0.0,
                "top_lang": topk(lang_counts[t], args.topk),
                "top_post_submolt": topk(post_submolt_counts[t], args.topk),
                "top_comment_submolt": topk(comment_submolt_counts[t], args.topk),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_matches": str(matches_path),
        "n_rows": int(n_rows),
        "score_range": {"min": float(min_score if n_rows else 0.0), "max": float(max_score if n_rows else 0.0)},
        "score_histogram": {"bin_step": 0.01, "bins": hist_bins},
        "thresholds": thresholds_out,
        "notes": [
            "Este analisis es sensibilidad de conteos por threshold: no prueba causalidad ni 'transmision real'.",
            "Los thresholds se aplican sobre el score de similitud (coseno) entre embeddings (same-lang).",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[transmission] Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

