#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.language_ontology import language_signals  # noqa: E402
from moltbook_analysis.analyze.incidence import human_incidence_score  # noqa: E402

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_#@']{2,}")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
WHITESPACE_RE = re.compile(r"\s+")

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "your", "you", "are", "was", "were",
    "pero", "para", "este", "esta", "como", "cuando", "donde", "sobre", "porque", "para", "con",
    "por", "una", "uno", "unos", "unas", "del", "las", "los", "que", "eso", "esa", "esto",
    "todo", "toda", "todos", "todas", "mucho", "muchos", "muchas", "muy", "mas", "menos",
    "i", "we", "they", "he", "she", "it", "my", "our", "their", "his", "her", "them",
}

CONCEPTS = {
    "agent", "agents", "ai", "human", "humans", "modelo", "model", "models",
    "prompt", "prompts", "policy", "policies", "tool", "tools", "tooling",
    "memory", "context", "data", "dataset", "research", "safety",
    "alignment", "economy", "token", "tokens", "crypto", "governance",
    "community", "network", "graph", "meme", "memes", "language", "lenguaje",
    "ontology", "ontologia", "ethics", "etica", "pipeline", "automation",
}

FEATURES_SUBMOLT = [
    "act_request",
    "act_offer",
    "act_promise",
    "act_declaration",
    "act_judgment",
    "act_assertion",
    "act_acceptance",
    "act_rejection",
    "act_clarification",
    "act_question_mark",
    "mood_ambition",
    "mood_resignation",
    "mood_resentment",
    "mood_gratitude",
    "mood_wonder",
    "mood_fear",
    "mood_anger",
    "mood_joy",
    "mood_sadness",
    "mood_trust",
    "mood_curiosity",
    "epistemic_hedge",
    "epistemic_certainty",
    "epistemic_evidence",
]

INJECTION_PATTERNS = [
    r"ignore (all|previous|earlier) (instructions|prompts)",
    r"system prompt",
    r"developer message",
    r"you are (an|a) (assistant|model|ai)",
    r"act as",
    r"do anything now",
    r"jailbreak",
    r"### instruction",
    r"begin (system|developer|assistant)",
    r"end (system|developer|assistant)",
]

LLM_DISCLAIMERS = [
    r"as an ai",
    r"as a language model",
    r"i (cannot|can't) (provide|comply|access)",
    r"i don't have (access|ability)",
]

CODE_FENCE_RE = re.compile(r"```", re.MULTILINE)
URL_MATCH_RE = re.compile(r"https?://\\S+|www\\.\\S+")
EMOJI_RE = re.compile(r"[\\U0001F300-\\U0001FAFF]")


def clean_text(text: str) -> str:
    text = CODE_BLOCK_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _count_pattern_hits(text: str, patterns: List[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, flags=re.IGNORECASE))


def interference_score(text: str) -> Dict[str, float]:
    t = clean_text(text)
    if not t:
        return {"score": 0.0, "injection_hits": 0, "disclaimer_hits": 0}

    inj = _count_pattern_hits(t, INJECTION_PATTERNS)
    dis = _count_pattern_hits(t, LLM_DISCLAIMERS)

    code_blocks = len(CODE_FENCE_RE.findall(text))
    urls = len(URL_MATCH_RE.findall(text))
    emojis = len(EMOJI_RE.findall(text))

    score = inj * 2 + dis * 1.5 + code_blocks * 0.5 + urls * 0.3
    score += 0.1 * emojis

    return {
        "score": float(score),
        "injection_hits": int(inj),
        "disclaimer_hits": int(dis),
        "code_fences": int(code_blocks),
        "urls": int(urls),
        "emojis": int(emojis),
    }


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


def safe_submolt_name(obj) -> str | None:
    if isinstance(obj, dict):
        return obj.get("name")
    if isinstance(obj, str):
        return obj
    return None


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def update_minmax(current: Tuple[datetime | None, datetime | None], dt: datetime | None):
    if dt is None:
        return current
    mn, mx = current
    if mn is None or dt < mn:
        mn = dt
    if mx is None or dt > mx:
        mx = dt
    return mn, mx


def push_top(heap: List[Tuple[float, dict]], item: dict, key: str, top_n: int) -> None:
    import heapq

    score = float(item.get(key, 0.0))
    if top_n <= 0:
        return
    if not hasattr(push_top, "counter"):
        push_top.counter = 0  # type: ignore[attr-defined]
    push_top.counter += 1  # type: ignore[attr-defined]
    entry = (score, push_top.counter, item)  # type: ignore[attr-defined]
    if len(heap) < top_n:
        heapq.heappush(heap, entry)
    else:
        if score > heap[0][0]:
            heapq.heappushpop(heap, entry)


def write_csv(path: Path, rows: Iterable[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _mat_vec(mat: List[List[float]], vec: List[float]) -> List[float]:
    return [sum(row[i] * vec[i] for i in range(len(vec))) for row in mat]


def _normalize(vec: List[float]) -> List[float]:
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _power_iteration(mat: List[List[float]], n_iter: int = 80) -> List[float]:
    n = len(mat)
    vec = [1.0 for _ in range(n)]
    for _ in range(n_iter):
        vec = _normalize(_mat_vec(mat, vec))
    return vec


def pca_2d_fallback(X: List[List[float]]) -> List[List[float]]:
    n = len(X)
    if n == 0:
        return []
    d = len(X[0])
    mean = [0.0] * d
    for row in X:
        for i in range(d):
            mean[i] += row[i]
    mean = [m / n for m in mean]

    std = [0.0] * d
    for row in X:
        for i in range(d):
            std[i] += (row[i] - mean[i]) ** 2
    std = [((s / max(1, n - 1)) ** 0.5) if s > 0 else 1.0 for s in std]

    Xn = []
    for row in X:
        Xn.append([(row[i] - mean[i]) / std[i] for i in range(d)])

    cov = [[0.0 for _ in range(d)] for _ in range(d)]
    for row in Xn:
        for i in range(d):
            for j in range(d):
                cov[i][j] += row[i] * row[j]
    denom = max(1, n - 1)
    for i in range(d):
        for j in range(d):
            cov[i][j] /= denom

    v1 = _power_iteration(cov)
    lambda1 = _dot(v1, _mat_vec(cov, v1))
    cov2 = [[cov[i][j] - lambda1 * v1[i] * v1[j] for j in range(d)] for i in range(d)]
    v2 = _power_iteration(cov2)

    coords = []
    for row in Xn:
        coords.append([_dot(row, v1), _dot(row, v2)])
    return coords


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate coverage, ontology, interference and incidence metrics.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    parser.add_argument("--top-concepts", type=int, default=40)
    parser.add_argument("--top-pairs", type=int, default=120)
    parser.add_argument("--top-docs", type=int, default=60)
    args = parser.parse_args()

    posts_path = Path(args.posts)
    comments_path = Path(args.comments)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    coverage = {
        "posts_total": 0,
        "comments_total": 0,
        "posts_unique": 0,
        "comments_unique": 0,
        "posts_missing_created_at": 0,
        "comments_missing_created_at": 0,
    }
    post_ids: set[str] = set()
    comment_ids: set[str] = set()

    post_created_range = (None, None)
    comment_created_range = (None, None)

    concept_counts: Counter[str] = Counter()
    concept_pairs: Counter[Tuple[str, str]] = Counter()

    feature_totals = Counter()
    feature_totals_posts = Counter()
    feature_totals_comments = Counter()
    doc_counts = {"all": 0, "posts": 0, "comments": 0}

    submolt_features: Dict[str, Counter] = defaultdict(Counter)
    submolt_docs: Counter = Counter()

    interference_totals = Counter()
    interference_totals_posts = Counter()
    interference_totals_comments = Counter()

    incidence_totals = Counter()
    incidence_totals_posts = Counter()
    incidence_totals_comments = Counter()

    top_interference: List[Tuple[float, dict]] = []
    top_incidence: List[Tuple[float, dict]] = []

    post_submolt: Dict[str, str] = {}

    def process_doc(doc_id: str | None, doc_type: str, text: str, created_at: str | None, submolt: str | None):
        nonlocal post_created_range, comment_created_range
        if doc_type == "post":
            coverage["posts_total"] += 1
            if isinstance(doc_id, str):
                post_ids.add(doc_id)
            dt = parse_dt(created_at)
            if dt is None:
                coverage["posts_missing_created_at"] += 1
            post_created_range = update_minmax(post_created_range, dt)
            doc_counts["posts"] += 1
        else:
            coverage["comments_total"] += 1
            if isinstance(doc_id, str):
                comment_ids.add(doc_id)
            dt = parse_dt(created_at)
            if dt is None:
                coverage["comments_missing_created_at"] += 1
            comment_created_range = update_minmax(comment_created_range, dt)
            doc_counts["comments"] += 1

        doc_counts["all"] += 1

        cleaned = clean_text(text)
        tokens = [t for t in tokenize(cleaned) if len(t) >= 3 and t not in STOPWORDS and t.isalpha()]
        concept_set = sorted({t for t in tokens if t in CONCEPTS})
        for concept in concept_set:
            concept_counts[concept] += 1
        if len(concept_set) >= 2:
            for a, b in combinations(concept_set, 2):
                concept_pairs[(a, b)] += 1

        signals = language_signals(text)
        feature_totals.update(signals)
        if doc_type == "post":
            feature_totals_posts.update(signals)
        else:
            feature_totals_comments.update(signals)

        if submolt:
            submolt_docs[submolt] += 1
            for key in FEATURES_SUBMOLT:
                if key in signals:
                    submolt_features[submolt][key] += signals.get(key, 0)

        inter = interference_score(text)
        for k, v in inter.items():
            interference_totals[k] += v
            if doc_type == "post":
                interference_totals_posts[k] += v
            else:
                interference_totals_comments[k] += v

        incidence = human_incidence_score(text)
        for k, v in incidence.items():
            incidence_totals[k] += v
            if doc_type == "post":
                incidence_totals_posts[k] += v
            else:
                incidence_totals_comments[k] += v

        record = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "submolt": submolt or "unknown",
            "created_at": created_at,
            "text_excerpt": (cleaned[:200] + "…") if len(cleaned) > 200 else cleaned,
        }
        record.update(inter)
        push_top(top_interference, record, "score", args.top_docs)

        record_inc = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "submolt": submolt or "unknown",
            "created_at": created_at,
            "text_excerpt": (cleaned[:200] + "…") if len(cleaned) > 200 else cleaned,
        }
        record_inc.update(incidence)
        push_top(top_incidence, record_inc, "human_incidence_score", args.top_docs)

    for post in iter_jsonl(posts_path):
        pid = post.get("id")
        title = post.get("title") or ""
        content = post.get("content") or ""
        text = f"{title}\n{content}".strip()
        submolt = safe_submolt_name(post.get("submolt"))
        if isinstance(pid, str) and submolt:
            post_submolt[pid] = submolt
        process_doc(pid, "post", text, post.get("created_at"), submolt)

    for comment in iter_jsonl(comments_path):
        cid = comment.get("id")
        text = (comment.get("content") or "").strip()
        post_id = comment.get("post_id")
        submolt = post_submolt.get(post_id)
        process_doc(cid, "comment", text, comment.get("created_at"), submolt)

    coverage["posts_unique"] = len(post_ids)
    coverage["comments_unique"] = len(comment_ids)
    coverage["posts_duplicates"] = coverage["posts_total"] - coverage["posts_unique"]
    coverage["comments_duplicates"] = coverage["comments_total"] - coverage["comments_unique"]
    coverage["post_comment_ratio"] = (
        coverage["posts_total"] / coverage["comments_total"]
        if coverage["comments_total"] else None
    )
    coverage["posts_created_min"] = post_created_range[0].isoformat() if post_created_range[0] else None
    coverage["posts_created_max"] = post_created_range[1].isoformat() if post_created_range[1] else None
    coverage["comments_created_min"] = comment_created_range[0].isoformat() if comment_created_range[0] else None
    coverage["comments_created_max"] = comment_created_range[1].isoformat() if comment_created_range[1] else None

    with (out_dir / "coverage_quality.json").open("w", encoding="utf-8") as f:
        json.dump(coverage, f, ensure_ascii=False, indent=2)

    def rows_for_features(scope: str, totals: Counter, doc_count: int):
        for key, count in totals.items():
            yield {
                "scope": scope,
                "feature": key,
                "count": count,
                "rate_per_doc": (count / doc_count) if doc_count else 0.0,
            }

    ontology_rows = list(rows_for_features("all", feature_totals, doc_counts["all"]))
    ontology_rows += list(rows_for_features("posts", feature_totals_posts, doc_counts["posts"]))
    ontology_rows += list(rows_for_features("comments", feature_totals_comments, doc_counts["comments"]))

    write_csv(out_dir / "ontology_summary.csv", ontology_rows, ["scope", "feature", "count", "rate_per_doc"])

    submolt_rows = []
    for sub, count in submolt_docs.items():
        row = {"submolt": sub, "doc_count": count}
        for key in FEATURES_SUBMOLT:
            row[key] = submolt_features[sub].get(key, 0)
        submolt_rows.append(row)

    submolt_rows.sort(key=lambda r: r["doc_count"], reverse=True)

    write_csv(
        out_dir / "ontology_submolt_full.csv",
        submolt_rows,
        ["submolt", "doc_count"] + FEATURES_SUBMOLT,
    )

    write_csv(
        out_dir / "ontology_submolt_top.csv",
        submolt_rows[:25],
        ["submolt", "doc_count"] + FEATURES_SUBMOLT,
    )

    embedding_rows = []
    for row in submolt_rows:
        doc_count = row["doc_count"] or 0
        emb = {"submolt": row["submolt"], "doc_count": doc_count}
        for key in FEATURES_SUBMOLT:
            emb[key] = (row[key] / doc_count) if doc_count else 0.0
        embedding_rows.append(emb)

    write_csv(
        out_dir / "ontology_submolt_embedding.csv",
        embedding_rows,
        ["submolt", "doc_count"] + FEATURES_SUBMOLT,
    )

    if embedding_rows:
        raw = [[r[key] for key in FEATURES_SUBMOLT] for r in embedding_rows]
        if np is not None:
            X = np.array(raw, dtype=float)
            if X.shape[0] >= 2:
                mean = X.mean(axis=0)
                std = X.std(axis=0)
                std[std == 0] = 1.0
                Xn = (X - mean) / std
                cov = np.cov(Xn, rowvar=False)
                eigvals, eigvecs = np.linalg.eigh(cov)
                order = np.argsort(eigvals)[::-1]
                W = eigvecs[:, order[:2]]
                coords = Xn @ W
            else:
                coords = np.zeros((X.shape[0], 2))
            coords_list = coords.tolist()
        else:
            coords_list = pca_2d_fallback(raw)

        coord_rows = []
        for idx, row in enumerate(embedding_rows):
            coord_rows.append({
                "submolt": row["submolt"],
                "doc_count": row["doc_count"],
                "x": float(coords_list[idx][0]) if coords_list else 0.0,
                "y": float(coords_list[idx][1]) if coords_list else 0.0,
            })

        write_csv(
            out_dir / "ontology_submolt_embedding_2d.csv",
            coord_rows,
            ["submolt", "doc_count", "x", "y"],
        )

    top_concepts = concept_counts.most_common(args.top_concepts)
    concept_rows = [
        {
            "concept": term,
            "doc_count": count,
            "share": (count / doc_counts["all"]) if doc_counts["all"] else 0.0,
        }
        for term, count in top_concepts
    ]
    write_csv(out_dir / "ontology_concepts_top.csv", concept_rows, ["concept", "doc_count", "share"])

    pair_rows = [
        {
            "concept_a": a,
            "concept_b": b,
            "count": count,
        }
        for (a, b), count in concept_pairs.most_common(args.top_pairs)
    ]
    write_csv(out_dir / "ontology_cooccurrence_top.csv", pair_rows, ["concept_a", "concept_b", "count"])

    def summary_rows(totals: Counter, scope: str):
        docs = doc_counts[scope]
        return {
            "scope": scope,
            "avg_score": (totals.get("score", 0.0) / docs) if docs else 0.0,
            "injection_rate": (totals.get("injection_hits", 0.0) / docs) if docs else 0.0,
            "disclaimer_rate": (totals.get("disclaimer_hits", 0.0) / docs) if docs else 0.0,
            "code_fence_rate": (totals.get("code_fences", 0.0) / docs) if docs else 0.0,
            "url_rate": (totals.get("urls", 0.0) / docs) if docs else 0.0,
            "emoji_rate": (totals.get("emojis", 0.0) / docs) if docs else 0.0,
        }

    interference_rows = [
        summary_rows(interference_totals, "all"),
        summary_rows(interference_totals_posts, "posts"),
        summary_rows(interference_totals_comments, "comments"),
    ]
    write_csv(
        out_dir / "interference_summary.csv",
        interference_rows,
        ["scope", "avg_score", "injection_rate", "disclaimer_rate", "code_fence_rate", "url_rate", "emoji_rate"],
    )

    def incidence_summary_rows(totals: Counter, scope: str):
        docs = doc_counts[scope]
        return {
            "scope": scope,
            "avg_score": (totals.get("human_incidence_score", 0.0) / docs) if docs else 0.0,
            "human_ref_rate": (totals.get("human_refs", 0.0) / docs) if docs else 0.0,
            "prompt_ref_rate": (totals.get("prompt_refs", 0.0) / docs) if docs else 0.0,
            "tooling_ref_rate": (totals.get("tooling_refs", 0.0) / docs) if docs else 0.0,
        }

    incidence_rows = [
        incidence_summary_rows(incidence_totals, "all"),
        incidence_summary_rows(incidence_totals_posts, "posts"),
        incidence_summary_rows(incidence_totals_comments, "comments"),
    ]
    write_csv(
        out_dir / "human_incidence_summary.csv",
        incidence_rows,
        ["scope", "avg_score", "human_ref_rate", "prompt_ref_rate", "tooling_ref_rate"],
    )

    top_interference_sorted = sorted(top_interference, key=lambda x: x[0], reverse=True)
    write_csv(
        out_dir / "interference_top.csv",
        [item for _, __, item in top_interference_sorted],
        [
            "doc_id",
            "doc_type",
            "submolt",
            "created_at",
            "score",
            "injection_hits",
            "disclaimer_hits",
            "code_fences",
            "urls",
            "emojis",
            "text_excerpt",
        ],
    )

    top_incidence_sorted = sorted(top_incidence, key=lambda x: x[0], reverse=True)
    write_csv(
        out_dir / "human_incidence_top.csv",
        [item for _, __, item in top_incidence_sorted],
        [
            "doc_id",
            "doc_type",
            "submolt",
            "created_at",
            "human_incidence_score",
            "human_refs",
            "prompt_refs",
            "tooling_refs",
            "text_excerpt",
        ],
    )

    print("Aggregated metrics written to", out_dir)


if __name__ == "__main__":
    main()
