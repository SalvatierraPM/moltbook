#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score

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


def post_text(post: dict) -> str:
    title = post.get("title") or ""
    content = post.get("content") or ""
    return f"{title}\n{content}".strip()


def comment_text(comment: dict) -> str:
    return (comment.get("content") or "").strip()


@dataclass
class Reservoir:
    k: int
    seen: int = 0
    items: list[dict] = field(default_factory=list)

    def add(self, item: dict, rng: random.Random) -> None:
        self.seen += 1
        if len(self.items) < self.k:
            self.items.append(item)
            return
        j = rng.randrange(self.seen)
        if j < self.k:
            self.items[j] = item


def percentile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.quantile(values, q))


def load_posts(posts_path: Path, wanted: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    scanned = 0
    for post in iter_jsonl(posts_path):
        scanned += 1
        if scanned % 50_000 == 0:
            print(f"[vsm] scanned posts {scanned:,} (found {len(out):,}/{len(wanted):,})")
        pid = post.get("id")
        if not isinstance(pid, str) or pid not in wanted:
            continue
        out[pid] = clean_text(post_text(post))
        if len(out) >= len(wanted):
            break
    return out


def load_comments(comments_path: Path, wanted: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    scanned = 0
    for comment in iter_jsonl(comments_path):
        scanned += 1
        if scanned % 200_000 == 0:
            print(f"[vsm] scanned comments {scanned:,} (found {len(out):,}/{len(wanted):,})")
        cid = comment.get("id")
        if not isinstance(cid, str) or cid not in wanted:
            continue
        out[cid] = clean_text(comment_text(comment))
        if len(out) >= len(wanted):
            break
    return out


def rowwise_cosine(a, b) -> np.ndarray:
    # a and b are sparse matrices with same shape (n, d); TF-IDF vectors are L2-normalized by default.
    return np.asarray(a.multiply(b).sum(axis=1)).reshape(-1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baseline VSM (TF-IDF) para comparar con embeddings en transmision post→comentario."
    )
    parser.add_argument(
        "--matches",
        default="data/derived/embeddings_post_comment/matches_post_comment.csv",
        help="CSV de matches post→comentario (con score y lang).",
    )
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl", help="Posts raw (API fetch).")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl", help="Comentarios raw (API fetch).")
    parser.add_argument("--out", default="data/derived/transmission_vsm_baseline.json", help="JSON de salida.")
    parser.add_argument("--seed", type=int, default=42, help="Seed reproducible.")
    parser.add_argument("--per-bin", type=int, default=400, help="Reservoir size por bin de score.")
    parser.add_argument("--min-lang-pairs", type=int, default=200, help="Min pares por idioma para reporte separado.")
    args = parser.parse_args()

    matches_path = Path(args.matches)
    posts_path = Path(args.posts)
    comments_path = Path(args.comments)
    out_path = Path(args.out)

    rng = random.Random(args.seed)

    bins = [
        {"name": "0.95-1.00", "lo": 0.95, "hi": 1.00001},
        {"name": "0.90-0.95", "lo": 0.90, "hi": 0.95},
        {"name": "0.85-0.90", "lo": 0.85, "hi": 0.90},
        {"name": "0.80-0.85", "lo": 0.80, "hi": 0.85},
        {"name": "0.75-0.80", "lo": 0.75, "hi": 0.80},
    ]
    reservoirs = {b["name"]: Reservoir(args.per_bin) for b in bins}

    print(f"[vsm] Sampling pairs from {matches_path} ...")
    total_rows = 0
    for row in csv.DictReader(matches_path.open("r", encoding="utf-8", newline="")):
        total_rows += 1
        if total_rows % 250_000 == 0:
            kept = sum(len(r.items) for r in reservoirs.values())
            print(f"[vsm] processed {total_rows:,} rows (kept {kept:,} sample pairs)")
        try:
            score = float(row.get("score") or 0.0)
        except Exception:
            continue
        item = {
            "post_id": row.get("post_id"),
            "comment_id": row.get("comment_id"),
            "score": score,
            "lang": (row.get("lang") or "unknown").strip() or "unknown",
        }
        for b in bins:
            if score >= b["lo"] and score < b["hi"]:
                reservoirs[b["name"]].add(item, rng)
                break

    matched_pairs: list[dict] = []
    for b in bins:
        matched_pairs.extend(reservoirs[b["name"]].items)
    # Drop obviously broken rows.
    matched_pairs = [p for p in matched_pairs if isinstance(p.get("post_id"), str) and isinstance(p.get("comment_id"), str)]

    lang_counts = Counter(p.get("lang") or "unknown" for p in matched_pairs)
    print(f"[vsm] Matched sample pairs: {len(matched_pairs):,} across {len(lang_counts):,} languages.")
    print("[vsm] Top langs:", ", ".join([f"{k}:{v}" for k, v in lang_counts.most_common(6)]))

    # Build shuffled baseline (same-lang, same pool) by permuting comment_ids within each language.
    shuffled_pairs: list[dict] = []
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for p in matched_pairs:
        by_lang[p.get("lang") or "unknown"].append(p)
    for lang, pairs in by_lang.items():
        post_ids = [p["post_id"] for p in pairs]
        comment_ids = [p["comment_id"] for p in pairs]
        rng.shuffle(comment_ids)
        for post_id, comment_id in zip(post_ids, comment_ids, strict=True):
            shuffled_pairs.append({"post_id": post_id, "comment_id": comment_id, "lang": lang})

    wanted_posts = {p["post_id"] for p in matched_pairs}
    wanted_comments = {p["comment_id"] for p in matched_pairs}

    print(f"[vsm] Loading texts: posts={len(wanted_posts):,}, comments={len(wanted_comments):,}")
    post_texts = load_posts(posts_path, wanted_posts)
    comment_texts = load_comments(comments_path, wanted_comments)
    missing_posts = len(wanted_posts - set(post_texts))
    missing_comments = len(wanted_comments - set(comment_texts))
    if missing_posts or missing_comments:
        print(f"[vsm] Warning: missing texts posts={missing_posts:,} comments={missing_comments:,}")

    def build_arrays(pairs: list[dict]) -> tuple[list[str], list[str], list[str], Optional[list[float]]]:
        a_texts: list[str] = []
        b_texts: list[str] = []
        langs: list[str] = []
        emb_scores: Optional[list[float]] = [] if ("score" in (pairs[0] if pairs else {})) else None
        for p in pairs:
            post_id = p.get("post_id")
            comment_id = p.get("comment_id")
            if not isinstance(post_id, str) or not isinstance(comment_id, str):
                continue
            at = post_texts.get(post_id)
            bt = comment_texts.get(comment_id)
            if not at or not bt:
                continue
            a_texts.append(at)
            b_texts.append(bt)
            langs.append(p.get("lang") or "unknown")
            if emb_scores is not None:
                emb_scores.append(float(p.get("score") or 0.0))
        return a_texts, b_texts, langs, emb_scores

    m_a, m_b, m_langs, m_scores = build_arrays(matched_pairs)
    s_a, s_b, s_langs, _ = build_arrays(shuffled_pairs)
    print(f"[vsm] Usable pairs after text join: matched={len(m_a):,}, shuffled={len(s_a):,}")

    # Compute metrics per language (enough mass) + all.
    def compute_metrics_for_mask(name: str, mask: np.ndarray) -> dict[str, object]:
        a_text = [m_a[i] for i in range(len(m_a)) if mask[i]]
        b_text = [m_b[i] for i in range(len(m_b)) if mask[i]]
        emb = np.array([m_scores[i] for i in range(len(m_a)) if mask[i]], dtype=float) if m_scores else np.zeros(0)
        # Shuffled uses same mask by language over the shuffled arrays.
        s_mask = np.array([s_langs[i] == name for i in range(len(s_a))]) if name != "_all" else np.ones(len(s_a), dtype=bool)
        sa_text = [s_a[i] for i in range(len(s_a)) if s_mask[i]]
        sb_text = [s_b[i] for i in range(len(s_a)) if s_mask[i]]

        corpus = a_text + b_text + sa_text + sb_text
        if len(corpus) < 10 or len(a_text) < 10 or len(sa_text) < 10:
            return {"n_matched": len(a_text), "n_shuffled": len(sa_text), "skipped": True, "reason": "insufficient_samples"}

        vec = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            max_features=60_000,
        )
        vec.fit(corpus)

        Xp = vec.transform(a_text)
        Xc = vec.transform(b_text)
        Xp_s = vec.transform(sa_text)
        Xc_s = vec.transform(sb_text)

        sim_m = rowwise_cosine(Xp, Xc)
        sim_s = rowwise_cosine(Xp_s, Xc_s)

        # Some languages can yield all-zero vectors; guard.
        corr = 0.0
        if emb.size >= 10 and np.std(emb) > 1e-9 and np.std(sim_m) > 1e-9:
            corr = float(np.corrcoef(emb, sim_m)[0, 1])

        auc = 0.0
        try:
            y = np.concatenate([np.ones(sim_m.size), np.zeros(sim_s.size)])
            y_score = np.concatenate([sim_m, sim_s])
            if len(np.unique(y_score)) > 3:
                auc = float(roc_auc_score(y, y_score))
        except Exception:
            auc = 0.0

        return {
            "n_matched": int(sim_m.size),
            "n_shuffled": int(sim_s.size),
            "vsm_matched": {
                "mean": float(sim_m.mean()) if sim_m.size else 0.0,
                "p50": percentile(sim_m, 0.50),
                "p90": percentile(sim_m, 0.90),
            },
            "vsm_shuffled": {
                "mean": float(sim_s.mean()) if sim_s.size else 0.0,
                "p50": percentile(sim_s, 0.50),
                "p90": percentile(sim_s, 0.90),
            },
            "corr_embedding_vs_vsm": corr,
            "auc_vsm_matched_vs_shuffled": auc,
        }

    # Global mask.
    all_mask = np.ones(len(m_a), dtype=bool)
    metrics = {"_all": compute_metrics_for_mask("_all", all_mask)}

    # Per-language for those with enough usable pairs.
    usable_lang_counts = Counter(m_langs)
    for lang, n in usable_lang_counts.most_common():
        if lang == "unknown":
            continue
        if n < args.min_lang_pairs:
            continue
        mask = np.array([l == lang for l in m_langs])
        metrics[lang] = compute_metrics_for_mask(lang, mask)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_matches": str(matches_path),
        "text_source": {
            "posts": str(posts_path),
            "comments": str(comments_path),
            "representation": "post=(title+content), comment=(content), cleaned=clean_text()",
        },
        "sampling": {
            "seed": args.seed,
            "per_bin": args.per_bin,
            "bins": bins,
            "total_rows_seen": int(total_rows),
            "matched_pairs_sampled": int(len(matched_pairs)),
            "matched_pairs_usable": int(len(m_a)),
            "shuffled_pairs_usable": int(len(s_a)),
            "top_langs_sample": [{"lang": k, "count": int(v)} for k, v in lang_counts.most_common(10)],
        },
        "metrics": metrics,
        "notes": [
            "Esto NO es ground-truth de 'transmision': es un baseline de similitud lexical (TF-IDF) comparado con pares que embeddings consideran similares.",
            "El baseline shuffled permuta comment_id dentro del mismo idioma: aproxima pares 'no relacionados' manteniendo distribucion de longitud/idioma.",
            "Interpretacion sugerida: si AUC VSM es alto, una parte del match puede explicarse por solape de tokens; si es bajo, embeddings aporta señal no-lexical.",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[vsm] Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

