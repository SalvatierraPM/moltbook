from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _entropy(dist: Dict[str, float]) -> float:
    p = np.array([v for v in dist.values() if v > 1e-12], dtype=np.float64)
    if p.size == 0:
        return 0.0
    return float(-np.sum(p * np.log(p)))


def _mad_alert(values: List[float], threshold: float = 3.5) -> List[bool]:
    arr = np.array(values, dtype=np.float64)
    out = [False] * len(values)
    for i in range(1, len(arr)):
        prev = arr[:i]
        med = np.median(prev)
        mad = np.median(np.abs(prev - med))
        if mad < 1e-9:
            out[i] = False
        else:
            z = abs(arr[i] - med) / (1.4826 * mad)
            out[i] = bool(z >= threshold)
    return out


def _aggregate_window(memes: List[Dict]) -> Dict:
    if not memes:
        return {}
    n = len(memes)
    mean_conflict = float(np.mean([m["conflict_index"] for m in memes]))
    mean_coord = float(np.mean([m["coordination_index"] for m in memes]))
    mean_rigid = float(np.mean([m["rigidity_score"] for m in memes]))
    dom_rec = float(np.mean([m["dominance_vs_reciprocity"] for m in memes]))
    id_task = float(np.mean([m["identity_vs_task_orientation"] for m in memes]))

    inqui = defaultdict(float)
    illoc = defaultdict(float)
    all_stance = []
    for m in memes:
        for k, v in m["dominant_inquietud"]["distribution"].items():
            inqui[k] += float(v) / n
        for k, v in m["illocution_distribution"].items():
            illoc[k] += float(v) / n
        all_stance.extend(m["pragmatic_mean"].values())

    inq_entropy = _entropy(dict(inqui))
    ill_entropy = _entropy(dict(illoc))
    stance_std = float(np.std(all_stance)) if all_stance else 0.0
    structural_entropy = _clip01((ill_entropy / 2.0 + stance_std + inq_entropy / 2.5) / 3.0)

    return {
        "post_count": n,
        "mean_conflict_index": _clip01(mean_conflict),
        "mean_coordination_index": _clip01(mean_coord),
        "mean_rigidity_score": _clip01(mean_rigid),
        "dominance_vs_reciprocity": _clip01(dom_rec),
        "identity_vs_task_orientation": _clip01(id_task),
        "diversity_of_inquietudes": _clip01(min(1.0, inq_entropy / 2.5)),
        "structural_entropy": _clip01(structural_entropy),
        "mean_inquietud_distribution": dict(inqui),
    }


def build_community_windows(memes: List[Dict], window_days: int = 30, step_days: int = 7) -> List[Dict]:
    by_comm: Dict[str, List[Dict]] = defaultdict(list)
    for m in memes:
        ts = _parse_ts(m.get("window_anchor_timestamp"))
        if ts is None:
            continue
        row = dict(m)
        row["_dt"] = ts
        by_comm[m.get("community_id", "unknown")].append(row)

    outputs: List[Dict] = []

    for community, rows in by_comm.items():
        rows.sort(key=lambda x: x["_dt"])
        start = rows[0]["_dt"]
        end = rows[-1]["_dt"]

        windows: List[Dict] = []
        cur = start
        while cur <= end:
            w_end = cur + timedelta(days=window_days)
            members = [r for r in rows if cur <= r["_dt"] < w_end]
            agg = _aggregate_window(members)
            if agg:
                windows.append(
                    {
                        "community_id": community,
                        "window_start": cur.isoformat(),
                        "window_end": w_end.isoformat(),
                        **agg,
                    }
                )
            cur += timedelta(days=step_days)

        # Deltas + alerts within community timeline.
        metric_names = [
            "mean_conflict_index",
            "mean_coordination_index",
            "mean_rigidity_score",
            "diversity_of_inquietudes",
            "structural_entropy",
        ]

        alerts_by_metric = {m: _mad_alert([w[m] for w in windows]) for m in metric_names}

        for i, w in enumerate(windows):
            prev = windows[i - 1] if i > 0 else None
            deltas = {}
            for m in metric_names:
                deltas[f"delta_{m}"] = float(w[m] - prev[m]) if prev else 0.0
            triggered = [m for m in metric_names if alerts_by_metric[m][i]]
            w["deltas"] = deltas
            w["alerts"] = {
                "has_change_point": bool(triggered),
                "triggered_metrics": triggered,
            }
            outputs.append(w)

    outputs.sort(key=lambda x: (x["community_id"], x["window_start"]))
    return outputs
