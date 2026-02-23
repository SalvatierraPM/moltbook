#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from statistics import median
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def parse_grid_int(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return sorted(set(out))


def parse_grid_float(raw: str) -> list[float]:
    out: list[float] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return sorted(set(out))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a and b:
        return 0.0
    if a and not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    if union == 0:
        return 0.0
    return inter / union


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analisis de robustez para deteccion de eventos de intervencion humana."
    )
    parser.add_argument("--groups", default="data/derived/human_intervention_group_features.csv")
    parser.add_argument("--summary", default="data/derived/human_intervention_summary.json")
    parser.add_argument("--out-json", default="data/derived/human_intervention_robustness.json")
    parser.add_argument("--out-md", default="reports/human_intervention_robustness.md")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--min-group-size-grid", default="2,3,5,8")
    parser.add_argument("--min-event-score-grid", default="3.5,5,7,10,12")
    parser.add_argument("--robust-min-share", type=float, default=0.7)
    args = parser.parse_args()

    groups_path = Path(args.groups)
    summary_path = Path(args.summary)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)

    groups = read_csv(groups_path)
    if not groups:
        raise SystemExit(f"No se encontro dataset de grupos: {groups_path}")

    groups_sorted = sorted(groups, key=lambda r: to_float(r.get("event_score")), reverse=True)
    group_by_id = {str(r.get("event_id") or ""): r for r in groups_sorted if r.get("event_id")}

    baseline_group_size = 2
    baseline_event_score = 3.5
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            baseline_group_size = to_int((summary.get("thresholds") or {}).get("min_group_size"), 2)
            baseline_event_score = to_float((summary.get("thresholds") or {}).get("min_event_score"), 3.5)
        except Exception:
            pass

    group_sizes = parse_grid_int(args.min_group_size_grid)
    event_scores = parse_grid_float(args.min_event_score_grid)
    if baseline_group_size not in group_sizes:
        group_sizes.append(baseline_group_size)
    if baseline_event_score not in event_scores:
        event_scores.append(baseline_event_score)
    group_sizes = sorted(set(group_sizes))
    event_scores = sorted(set(event_scores))

    configs: list[dict[str, Any]] = []
    event_presence: defaultdict[str, set[str]] = defaultdict(set)
    class_count_by_config: defaultdict[str, list[int]] = defaultdict(list)
    all_labels = sorted({str(r.get("likely_source") or "unknown") for r in groups_sorted})

    def select(min_group_size: int, min_event_score: float) -> list[dict[str, str]]:
        rows = []
        for row in groups_sorted:
            repeat = to_int(row.get("repeat_count"))
            score = to_float(row.get("event_score"))
            if repeat < min_group_size:
                continue
            if score < min_event_score:
                continue
            rows.append(row)
        return rows

    baseline_rows = select(baseline_group_size, baseline_event_score)
    baseline_top = baseline_rows[: max(1, args.top_k)]
    baseline_top_ids = {str(r.get("event_id")) for r in baseline_top}

    for min_group_size, min_event_score in product(group_sizes, event_scores):
        config_id = f"g{min_group_size}_s{min_event_score}"
        selected = select(min_group_size, min_event_score)
        top_rows = selected[: max(1, args.top_k)]
        top_ids = {str(r.get("event_id")) for r in top_rows}
        class_counts = Counter(str(r.get("likely_source") or "unknown") for r in selected)
        for label in all_labels:
            class_count_by_config[label].append(int(class_counts.get(label, 0)))
        for row in selected:
            eid = str(row.get("event_id") or "")
            if eid:
                event_presence[eid].add(config_id)
        configs.append(
            {
                "config_id": config_id,
                "min_group_size": min_group_size,
                "min_event_score": min_event_score,
                "event_count": len(selected),
                "top_k_size": len(top_rows),
                "jaccard_top_k_vs_baseline": round(jaccard(top_ids, baseline_top_ids), 6),
                "class_counts": dict(class_counts),
                "top_event_ids": [str(r.get("event_id")) for r in top_rows[:20]],
            }
        )

    total_configs = len(configs)
    robust_events: list[dict[str, Any]] = []
    for event_id, presence in event_presence.items():
        share = len(presence) / total_configs if total_configs else 0.0
        if share < args.robust_min_share:
            continue
        base = group_by_id.get(event_id, {})
        robust_events.append(
            {
                "event_id": event_id,
                "presence_configs": len(presence),
                "presence_share": round(share, 6),
                "event_score": round(to_float(base.get("event_score")), 4),
                "coordination_index": round(to_float(base.get("coordination_index")), 4),
                "likely_source": str(base.get("likely_source") or ""),
                "repeat_count": to_int(base.get("repeat_count")),
                "unique_authors": to_int(base.get("unique_authors")),
                "unique_submolts": to_int(base.get("unique_submolts")),
                "sample_excerpt": str(base.get("sample_excerpt") or "")[:240],
            }
        )
    robust_events.sort(
        key=lambda r: (to_float(r.get("presence_share")), to_float(r.get("event_score"))),
        reverse=True,
    )

    jaccards = [to_float(cfg.get("jaccard_top_k_vs_baseline")) for cfg in configs]
    class_stability: dict[str, dict[str, float]] = {}
    for label, values in class_count_by_config.items():
        if not values:
            continue
        vals = sorted(values)
        low_idx = int(0.05 * (len(vals) - 1))
        high_idx = int(0.95 * (len(vals) - 1))
        class_stability[label] = {
            "median": float(median(vals)),
            "p05": float(vals[low_idx]),
            "p95": float(vals[high_idx]),
        }

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "groups_path": str(groups_path),
            "summary_path": str(summary_path),
            "groups_total": len(groups_sorted),
        },
        "baseline": {
            "min_group_size": baseline_group_size,
            "min_event_score": baseline_event_score,
            "top_k": args.top_k,
            "event_count": len(baseline_rows),
            "top_event_ids": [str(r.get("event_id")) for r in baseline_top[:20]],
        },
        "grid": {
            "min_group_sizes": group_sizes,
            "min_event_scores": event_scores,
            "configs_total": total_configs,
        },
        "stability": {
            "jaccard_top_k_vs_baseline_median": round(median(jaccards), 6) if jaccards else 0.0,
            "jaccard_top_k_vs_baseline_min": round(min(jaccards), 6) if jaccards else 0.0,
            "jaccard_top_k_vs_baseline_max": round(max(jaccards), 6) if jaccards else 0.0,
            "class_count_intervals": class_stability,
        },
        "robust_events": robust_events[:500],
        "configs": configs,
    }
    write_json(out_json, payload)

    lines: list[str] = []
    lines.append("# Human Intervention Robustness")
    lines.append("")
    lines.append(f"- generated_at: {payload['generated_at']}")
    lines.append(f"- groups_total: {len(groups_sorted)}")
    lines.append(
        f"- baseline: min_group_size={baseline_group_size}, min_event_score={baseline_event_score}, events={len(baseline_rows)}"
    )
    lines.append(
        f"- jaccard(top-{args.top_k}) vs baseline: median={payload['stability']['jaccard_top_k_vs_baseline_median']}, "
        f"min={payload['stability']['jaccard_top_k_vs_baseline_min']}, "
        f"max={payload['stability']['jaccard_top_k_vs_baseline_max']}"
    )
    lines.append("")
    lines.append("## Config Grid")
    lines.append("")
    lines.append("| config_id | min_group_size | min_event_score | event_count | jaccard_top_k_vs_baseline |")
    lines.append("|---|---:|---:|---:|---:|")
    for cfg in configs:
        lines.append(
            f"| {cfg['config_id']} | {cfg['min_group_size']} | {cfg['min_event_score']} | "
            f"{cfg['event_count']} | {cfg['jaccard_top_k_vs_baseline']} |"
        )
    lines.append("")
    lines.append("## Class Stability")
    lines.append("")
    lines.append("| class | median_count | p05 | p95 |")
    lines.append("|---|---:|---:|---:|")
    for label in sorted(class_stability.keys()):
        stats = class_stability[label]
        lines.append(
            f"| {label} | {stats['median']} | {stats['p05']} | {stats['p95']} |"
        )
    lines.append("")
    lines.append("## Robust Events")
    lines.append("")
    lines.append(
        f"Definicion: evento presente en >= {int(round(args.robust_min_share * 100))}% de configuraciones del grid."
    )
    lines.append("")
    lines.append("| event_id | share | score | class | repeat | authors | submolts |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    for row in robust_events[:60]:
        lines.append(
            f"| {row['event_id']} | {row['presence_share']} | {row['event_score']} | "
            f"{row['likely_source']} | {row['repeat_count']} | {row['unique_authors']} | {row['unique_submolts']} |"
        )
    write_md(out_md, lines)

    print(f"groups={len(groups_sorted)} configs={total_configs} robust_events={len(robust_events)}")
    print(f"robustness_json={out_json}")
    print(f"robustness_md={out_md}")


if __name__ == "__main__":
    main()
