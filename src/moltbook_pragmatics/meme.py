from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

import numpy as np

from .embeddings import EmbeddingBackend, cosine_sim
from .message_scoring import ILLOCUTION_LABELS, PRAG_DIMS

INQUIETUD_LABELS = [
    "recognition",
    "power",
    "belonging",
    "status",
    "truth",
    "justice",
    "coordination",
    "validation",
    "humor",
    "moral_positioning",
]

INQUIETUD_PROMPTS = {
    "recognition": ["notice me", "I want recognition", "acknowledge this"],
    "power": ["control", "authority", "who decides"],
    "belonging": ["our community", "we belong", "ingroup"],
    "status": ["prestige", "rank", "social status"],
    "truth": ["facts", "evidence", "truth matters"],
    "justice": ["fairness", "justice", "rights"],
    "coordination": ["organize together", "collective action", "next steps"],
    "validation": ["approve me", "please validate", "agree with me"],
    "humor": ["joke", "meme", "sarcasm", "funny"],
    "moral_positioning": ["good versus bad", "moral stance", "ethical"],
}


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _entropy(probs: np.ndarray) -> float:
    probs = probs[probs > 1e-12]
    if probs.size == 0:
        return 0.0
    return float(-np.sum(probs * np.log(probs)))


def _safe_mean(vals: List[float], default: float = 0.0) -> float:
    return float(np.mean(vals)) if vals else default


def infer_inquietud_distribution(post_embeddings: np.ndarray, backend: EmbeddingBackend) -> Dict[str, float]:
    if post_embeddings.shape[0] == 0:
        return {k: 1.0 / len(INQUIETUD_LABELS) for k in INQUIETUD_LABELS}

    prompts = []
    offsets = {}
    for label in INQUIETUD_LABELS:
        s = len(prompts)
        prompts.extend(INQUIETUD_PROMPTS[label])
        offsets[label] = (s, len(prompts))

    prompt_vec = backend.encode(prompts)
    sims = cosine_sim(post_embeddings, prompt_vec)

    scores = {}
    for label in INQUIETUD_LABELS:
        s, e = offsets[label]
        scores[label] = float(np.mean(sims[:, s:e]))

    x = np.array([scores[k] for k in INQUIETUD_LABELS], dtype=np.float32)
    x = x - np.max(x)
    p = np.exp(x) / np.sum(np.exp(x))
    return {label: float(p[i]) for i, label in enumerate(INQUIETUD_LABELS)}


def aggregate_memes(messages: List[Dict], interactions_by_post: Dict[str, List[Dict]], embedding_matrix: np.ndarray, backend: EmbeddingBackend) -> List[Dict]:
    by_post: Dict[str, List[Dict]] = defaultdict(list)
    id_to_ix = {m["message_id"]: i for i, m in enumerate(messages)}
    for m in messages:
        by_post[m["post_id"]].append(m)

    out: List[Dict] = []

    for post_id, items in by_post.items():
        n = len(items)
        if n == 0:
            continue

        ill = Counter(m.get("illocution", {}).get("label", "OTHER") for m in items)
        ill_dist = {label: ill.get(label, 0) / n for label in ILLOCUTION_LABELS}

        dim_vals: Dict[str, List[float]] = {d: [] for d in PRAG_DIMS}
        for m in items:
            p = m.get("pragmatic_scores", {})
            for d in PRAG_DIMS:
                dim_vals[d].append(float(p.get(d, 0.5)))

        means = {d: _safe_mean(vals, 0.5) for d, vals in dim_vals.items()}
        vars_ = {d: float(np.var(vals)) if vals else 0.0 for d, vals in dim_vals.items()}

        edges = interactions_by_post.get(post_id, [])
        mean_escal = _safe_mean([e["escalation_score"] for e in edges], 0.0)
        mean_uptake = _safe_mean([e["uptake_success"] for e in edges], 0.5)

        conflict_index = _clip01(
            0.35 * means["dominance"]
            + 0.25 * (1.0 - means["politeness"])
            + 0.2 * (1.0 - means["affect_valence"])
            + 0.2 * mean_escal
        )
        coordination_index = _clip01(0.6 * means["coordination_intent"] + 0.4 * mean_uptake)
        rigidity_score = _clip01(0.5 * means["certainty"] + 0.3 * means["dominance"] + 0.2 * (1.0 - np.mean(list(vars_.values())) * 4.0))
        irony_density = _clip01(means["irony"])

        dominance_vs_reciprocity = _clip01(0.5 + (means["dominance"] - means["politeness"]) * 0.5)
        identity_vs_task_orientation = _clip01(0.5 + ((1.0 - means["coordination_intent"]) + means["irony"] - means["certainty"]) * 0.25)

        emb_ix = [id_to_ix[m["message_id"]] for m in items if m["message_id"] in id_to_ix]
        post_emb = embedding_matrix[emb_ix] if emb_ix else np.zeros((0, embedding_matrix.shape[1]), dtype=np.float32)
        inqui = infer_inquietud_distribution(post_emb, backend)
        top3 = sorted(inqui.items(), key=lambda kv: kv[1], reverse=True)[:3]

        record_type_counts = Counter(m.get("record_type") for m in items)
        ts = sorted([m.get("timestamp") for m in items if m.get("timestamp")])

        out.append(
            {
                "post_id": post_id,
                "community_id": items[0].get("community_id", "unknown"),
                "window_anchor_timestamp": ts[0] if ts else None,
                "message_count": n,
                "record_type_counts": dict(record_type_counts),
                "illocution_distribution": ill_dist,
                "pragmatic_mean": means,
                "pragmatic_variance": vars_,
                "conflict_index": conflict_index,
                "coordination_index": coordination_index,
                "rigidity_score": rigidity_score,
                "irony_density": irony_density,
                "dominance_vs_reciprocity": dominance_vs_reciprocity,
                "identity_vs_task_orientation": identity_vs_task_orientation,
                "dominant_inquietud": {"top3": top3, "distribution": inqui},
                "explain": {
                    "high_conflict_drivers": sorted(
                        [{"message_id": m["message_id"], "score": float(m.get("pragmatic_scores", {}).get("dominance", 0.5) - m.get("pragmatic_scores", {}).get("politeness", 0.5))} for m in items],
                        key=lambda x: x["score"],
                        reverse=True,
                    )[:3],
                    "high_rigidity_drivers": sorted(
                        [{"message_id": m["message_id"], "score": float(m.get("pragmatic_scores", {}).get("certainty", 0.5))} for m in items],
                        key=lambda x: x["score"],
                        reverse=True,
                    )[:3],
                },
            }
        )

    return out
