#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye subset de alta confianza de intervencion humana probable."
    )
    parser.add_argument("--events", default="data/derived/human_intervention_events.csv")
    parser.add_argument("--out-csv", default="data/derived/human_intervention_strict_events.csv")
    parser.add_argument("--out-md", default="reports/human_intervention_strict_events.md")
    parser.add_argument("--min-event-score", type=float, default=12.0)
    parser.add_argument("--min-coordination", type=float, default=0.5)
    parser.add_argument("--min-repeat", type=int, default=8)
    parser.add_argument("--min-promo-rate", type=float, default=0.2)
    parser.add_argument("--min-cta-rate", type=float, default=0.2)
    parser.add_argument("--min-human-refs", type=float, default=1.2)
    parser.add_argument("--min-human-signal-rate", type=float, default=0.25)
    parser.add_argument("--top", type=int, default=0)
    args = parser.parse_args()

    rows = read_csv(Path(args.events))
    if not rows:
        raise SystemExit(f"No se encontro dataset de eventos: {args.events}")

    strict_rows: list[dict[str, Any]] = []
    for row in rows:
        score = to_float(row.get("event_score"))
        coord = to_float(row.get("coordination_index"))
        repeat = to_int(row.get("repeat_count"))
        promo_rate = to_float(row.get("promo_rate"))
        cta_rate = to_float(row.get("cta_rate"))
        human_refs = to_float(row.get("avg_human_refs"))
        human_signal_rate = to_float(row.get("human_signal_rate"))

        if score < args.min_event_score:
            continue
        if coord < args.min_coordination:
            continue
        if repeat < args.min_repeat:
            continue

        reasons: list[str] = []
        if promo_rate >= args.min_promo_rate:
            reasons.append("promo")
        if cta_rate >= args.min_cta_rate:
            reasons.append("cta")
        if human_refs >= args.min_human_refs:
            reasons.append("human_refs")
        if human_signal_rate >= args.min_human_signal_rate:
            reasons.append("human_signal")
        if not reasons:
            continue

        out_row = dict(row)
        out_row["strict_reason"] = "|".join(reasons)
        strict_rows.append(out_row)

    strict_rows.sort(key=lambda r: to_float(r.get("event_score")), reverse=True)
    if args.top > 0:
        strict_rows = strict_rows[: args.top]

    fieldnames = list(strict_rows[0].keys()) if strict_rows else [
        "event_id",
        "event_score",
        "coordination_index",
        "repeat_count",
        "likely_source",
        "strict_reason",
    ]
    write_csv(Path(args.out_csv), strict_rows, fieldnames)

    class_counts = Counter(str(r.get("likely_source") or "unknown") for r in strict_rows)

    lines: list[str] = []
    lines.append("# High-Confidence Human Intervention Events")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now(UTC).isoformat()}")
    lines.append(f"- events_input: {len(rows)}")
    lines.append(f"- strict_events: {len(strict_rows)}")
    lines.append("")
    lines.append("## Criteria")
    lines.append("")
    lines.append(f"- event_score >= {args.min_event_score}")
    lines.append(f"- coordination_index >= {args.min_coordination}")
    lines.append(f"- repeat_count >= {args.min_repeat}")
    lines.append(
        "- semantic evidence: promo_rate OR cta_rate OR avg_human_refs OR human_signal_rate over threshold"
    )
    lines.append("")
    lines.append("## Class Distribution")
    lines.append("")
    lines.append("| class | count |")
    lines.append("|---|---:|")
    for label, count in sorted(class_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {label} | {count} |")
    lines.append("")
    lines.append("## Top Events")
    lines.append("")
    lines.append("| event_id | class | score | coordination | repeat | strict_reason |")
    lines.append("|---|---|---:|---:|---:|---|")
    for row in strict_rows[:60]:
        lines.append(
            f"| {row.get('event_id','')} | {row.get('likely_source','')} | {to_float(row.get('event_score')):.4f} | "
            f"{to_float(row.get('coordination_index')):.4f} | {to_int(row.get('repeat_count'))} | {row.get('strict_reason','')} |"
        )

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(f"events_input={len(rows)} strict_events={len(strict_rows)}")
    print(f"strict_csv={args.out_csv}")
    print(f"strict_md={args.out_md}")


if __name__ == "__main__":
    main()
