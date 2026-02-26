from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    # Dense path
    if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    # Sparse path (scipy CSR rows)
    try:
        dot = float(a.multiply(b).sum())
        na = float(np.sqrt(a.multiply(a).sum()))
        nb = float(np.sqrt(b.multiply(b).sum()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(dot / (na * nb))
    except Exception:
        return 0.0


def _uptake(parent_label: str, child_label: str) -> float:
    expected = {
        "DIRECTIVE": {"ASSERTIVE", "COMMISSIVE", "DIRECTIVE"},
        "ASSERTIVE": {"ASSERTIVE", "EXPRESSIVE", "DIRECTIVE"},
        "COMMISSIVE": {"EXPRESSIVE", "ASSERTIVE"},
        "DECLARATIVE": {"ASSERTIVE", "EXPRESSIVE"},
        "EXPRESSIVE": {"EXPRESSIVE", "ASSERTIVE"},
        "OTHER": {"OTHER", "ASSERTIVE", "EXPRESSIVE"},
    }
    return 1.0 if child_label in expected.get(parent_label, {"OTHER"}) else 0.0


def build_interactions(messages: List[Dict], embedding_matrix: np.ndarray) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    by_id = {m["message_id"]: m for m in messages}
    idx = {m["message_id"]: i for i, m in enumerate(messages)}

    by_post: Dict[str, List[Dict]] = defaultdict(list)
    for m in messages:
        by_post[m["post_id"]].append(m)

    edges: List[Dict] = []
    per_post: Dict[str, List[Dict]] = defaultdict(list)

    for post_id, items in by_post.items():
        has_reply_structure = any(m.get("reply_to_id") for m in items)
        if has_reply_structure:
            candidates = []
            for child in items:
                pid = child.get("reply_to_id")
                if not pid:
                    continue
                parent = by_id.get(pid)
                if parent is None or parent.get("post_id") != post_id:
                    continue
                candidates.append((parent, child, False))
        else:
            sorted_items = sorted(items, key=lambda x: x.get("timestamp") or "")
            candidates = [(sorted_items[i], sorted_items[i + 1], True) for i in range(len(sorted_items) - 1)]

        for parent, child, weak in candidates:
            pa = parent.get("pragmatic_scores", {})
            ch = child.get("pragmatic_scores", {})

            stance_shift = {
                k: float(ch.get(k, 0.5) - pa.get(k, 0.5))
                for k in [
                    "certainty",
                    "affect_valence",
                    "dominance",
                    "politeness",
                    "irony",
                    "coordination_intent",
                ]
            }

            escalation = _clip01(
                0.5
                + 0.25 * max(0.0, stance_shift["dominance"])
                + 0.2 * max(0.0, -stance_shift["politeness"])
                + 0.2 * max(0.0, -stance_shift["affect_valence"])
                + 0.1 * max(0.0, stance_shift["certainty"])
            )

            i_parent = idx[parent["message_id"]]
            i_child = idx[child["message_id"]]
            sem_align = (_cos(embedding_matrix[i_parent], embedding_matrix[i_child]) + 1.0) / 2.0
            stance_dist = np.mean([abs(v) for v in stance_shift.values()])
            stance_align = _clip01(1.0 - stance_dist)
            alignment = _clip01(0.6 * sem_align + 0.4 * stance_align)

            uptake = _uptake(parent["illocution"]["label"], child["illocution"]["label"])

            edge = {
                "post_id": post_id,
                "source_message_id": parent["message_id"],
                "target_message_id": child["message_id"],
                "weak_structure": weak,
                "stance_shift": stance_shift,
                "escalation_score": escalation,
                "alignment_score": alignment,
                "uptake_success": uptake,
            }
            edges.append(edge)
            per_post[post_id].append(edge)

    return edges, per_post
