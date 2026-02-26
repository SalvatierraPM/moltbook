from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import numpy as np


def build_diagnostics_report(community_windows: List[Dict], enriched_memes: List[Dict]) -> Dict:
    by_comm: Dict[str, List[Dict]] = defaultdict(list)
    for w in community_windows:
        by_comm[w["community_id"]].append(w)

    mem_by_comm: Dict[str, List[Dict]] = defaultdict(list)
    for m in enriched_memes:
        mem_by_comm[m["community_id"]].append(m)

    communities = []
    ranking_conflict = []
    ranking_coordination = []

    for comm, rows in by_comm.items():
        rows.sort(key=lambda x: x["window_start"])
        if not rows:
            continue

        latest = rows[-1]
        profile = {
            "conflict_vs_coordination": float(latest["mean_conflict_index"] - latest["mean_coordination_index"]),
            "rigidity_vs_plasticity": float(latest["mean_rigidity_score"] - (1.0 - latest["mean_rigidity_score"])),
            "dominance_vs_reciprocity": float(latest["dominance_vs_reciprocity"] - (1.0 - latest["dominance_vs_reciprocity"])),
            "identity_vs_task_orientation": float(latest["identity_vs_task_orientation"] - (1.0 - latest["identity_vs_task_orientation"])),
        }

        inq = defaultdict(float)
        memes = mem_by_comm.get(comm, [])
        if memes:
            for m in memes:
                for k, v in m["dominant_inquietud"]["distribution"].items():
                    inq[k] += v / len(memes)
        top_inq = sorted(inq.items(), key=lambda kv: kv[1], reverse=True)[:3]

        alerts = [r for r in rows if r.get("alerts", {}).get("has_change_point")]
        communities.append(
            {
                "community_id": comm,
                "discursive_profile": profile,
                "top_inquietudes": top_inq,
                "alerts": [
                    {
                        "window_start": a["window_start"],
                        "window_end": a["window_end"],
                        "triggered_metrics": a["alerts"]["triggered_metrics"],
                    }
                    for a in alerts
                ],
                "latest_metrics": {
                    "mean_conflict_index": latest["mean_conflict_index"],
                    "mean_coordination_index": latest["mean_coordination_index"],
                    "mean_rigidity_score": latest["mean_rigidity_score"],
                },
            }
        )

        ranking_conflict.append((comm, latest["mean_conflict_index"]))
        ranking_coordination.append((comm, latest["mean_coordination_index"]))

    ranking_conflict.sort(key=lambda x: x[1], reverse=True)
    ranking_coordination.sort(key=lambda x: x[1], reverse=True)

    return {
        "summary": {
            "community_count": len(communities),
            "alerts_count": int(sum(len(c["alerts"]) for c in communities)),
        },
        "community_profiles": communities,
        "rankings": {
            "highest_conflict": ranking_conflict,
            "highest_coordination": ranking_coordination,
        },
    }
