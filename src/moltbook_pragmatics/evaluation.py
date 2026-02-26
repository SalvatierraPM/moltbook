from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import confusion_matrix, f1_score

from .message_scoring import ILLOCUTION_LABELS, PRAG_DIMS


@dataclass
class EvalReport:
    macro_f1: float
    confusion_matrix: List[List[int]]
    mae_by_dim: Dict[str, float]
    corr_by_dim: Dict[str, float]
    worst_examples: List[Dict]


def stratified_labeling_sample(messages: List[Dict], embeddings: np.ndarray, n: int = 300, seed: int = 42) -> List[Dict]:
    if not messages:
        return []
    n = min(n, len(messages))

    k = min(8, max(2, int(np.sqrt(len(messages) / 3))))
    km = MiniBatchKMeans(n_clusters=k, random_state=seed, n_init="auto")
    clusters = km.fit_predict(embeddings)

    rows = []
    for i, m in enumerate(messages):
        ts = (m.get("timestamp") or "")[:7]  # yyyy-mm bucket
        rows.append(
            {
                "ix": i,
                "community_id": m.get("community_id", "unknown"),
                "time_bin": ts,
                "topic_cluster": int(clusters[i]),
            }
        )

    strata = defaultdict(list)
    for r in rows:
        key = (r["community_id"], r["time_bin"], r["topic_cluster"])
        strata[key].append(r["ix"])

    rng = np.random.default_rng(seed)
    keys = list(strata.keys())
    rng.shuffle(keys)
    picked = []
    while len(picked) < n and keys:
        next_keys = []
        for k_ in keys:
            bucket = strata[k_]
            if bucket:
                picked.append(bucket.pop())
                if len(picked) >= n:
                    break
            if bucket:
                next_keys.append(k_)
        keys = next_keys

    picked_set = set(picked)
    sample = []
    for i, m in enumerate(messages):
        if i not in picked_set:
            continue
        sample.append(
            {
                "message_id": m.get("message_id"),
                "post_id": m.get("post_id"),
                "community_id": m.get("community_id"),
                "timestamp": m.get("timestamp"),
                "text": m.get("locution", {}).get("cleaned_text", m.get("text", "")),
                "pred_illocution": m.get("illocution", {}).get("label"),
                **{f"pred_{d}": m.get("pragmatic_scores", {}).get(d) for d in PRAG_DIMS},
                "human_illocution": "",
                **{f"human_{d}": "" for d in PRAG_DIMS},
            }
        )
    return sample


def write_labeling_sheet(sample: List[Dict], out_csv: str, out_json: str) -> None:
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    if sample:
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sample[0].keys()))
            w.writeheader()
            w.writerows(sample)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)


def _safe_float(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def evaluate_human_labels(labeling_csv: str) -> EvalReport:
    rows = []
    with open(labeling_csv, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    valid_ill = [r for r in rows if r.get("human_illocution") in ILLOCUTION_LABELS]
    y_true = [r["human_illocution"] for r in valid_ill]
    y_pred = [r.get("pred_illocution", "OTHER") for r in valid_ill]

    macro_f1 = float(f1_score(y_true, y_pred, labels=ILLOCUTION_LABELS, average="macro", zero_division=0)) if y_true else 0.0
    cm = confusion_matrix(y_true, y_pred, labels=ILLOCUTION_LABELS).tolist() if y_true else [[0] * len(ILLOCUTION_LABELS) for _ in ILLOCUTION_LABELS]

    mae_by_dim = {}
    corr_by_dim = {}
    for d in PRAG_DIMS:
        pairs = []
        for r in rows:
            hp = _safe_float(r.get(f"human_{d}"))
            pp = _safe_float(r.get(f"pred_{d}"))
            if hp is None or pp is None:
                continue
            pairs.append((hp, pp, r))
        if not pairs:
            mae_by_dim[d] = 0.0
            corr_by_dim[d] = 0.0
            continue
        h = np.array([p[0] for p in pairs], dtype=np.float64)
        p = np.array([p[1] for p in pairs], dtype=np.float64)
        mae_by_dim[d] = float(np.mean(np.abs(h - p)))
        corr_by_dim[d] = float(np.corrcoef(h, p)[0, 1]) if len(h) > 1 else 0.0

    worst = []
    for r in rows:
        diffs = []
        for d in PRAG_DIMS:
            hp = _safe_float(r.get(f"human_{d}"))
            pp = _safe_float(r.get(f"pred_{d}"))
            if hp is None or pp is None:
                continue
            diffs.append(abs(hp - pp))
        if diffs:
            worst.append((float(np.mean(diffs)), r))
    worst.sort(key=lambda x: x[0], reverse=True)

    return EvalReport(
        macro_f1=macro_f1,
        confusion_matrix=cm,
        mae_by_dim=mae_by_dim,
        corr_by_dim=corr_by_dim,
        worst_examples=[{"error": e, "message_id": r.get("message_id"), "text": r.get("text", "")[:240]} for e, r in worst[:20]],
    )


def eval_report_to_dict(r: EvalReport) -> Dict:
    return {
        "illocution_macro_f1": r.macro_f1,
        "confusion_matrix": r.confusion_matrix,
        "mae_by_dimension": r.mae_by_dim,
        "correlation_by_dimension": r.corr_by_dim,
        "worst_examples": r.worst_examples,
    }
