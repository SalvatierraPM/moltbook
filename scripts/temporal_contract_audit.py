#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


RUN_ID_RE = re.compile(r"^(\d{8})T(\d{6})Z$")


@dataclass
class CheckResult:
    id: str
    status: str
    message: str
    details: dict[str, Any]


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_run_id(run_id: str | None) -> datetime | None:
    if not run_id:
        return None
    m = RUN_ID_RE.match(run_id.strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def hours(delta_seconds: float) -> float:
    return delta_seconds / 3600.0


def days(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return (end - start).total_seconds() / 86400.0


def safe_float(value: float | None, decimals: int = 4) -> float | None:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, decimals)


def load_coverage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError:
            return {}
    if isinstance(payload, dict):
        return payload
    return {}


def load_run_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def compute_created_window(coverage: dict[str, Any]) -> dict[str, Any]:
    post_min = parse_dt(coverage.get("posts_created_min"))
    post_max = parse_dt(coverage.get("posts_created_max"))
    comment_min = parse_dt(coverage.get("comments_created_min"))
    comment_max = parse_dt(coverage.get("comments_created_max"))

    mins = [dt for dt in [post_min, comment_min] if dt]
    maxs = [dt for dt in [post_max, comment_max] if dt]

    created_start = min(mins) if mins else None
    created_end = max(maxs) if maxs else None

    posts_total = int(coverage.get("posts_total") or 0)
    comments_total = int(coverage.get("comments_total") or 0)
    posts_missing = int(coverage.get("posts_missing_created_at") or 0)
    comments_missing = int(coverage.get("comments_missing_created_at") or 0)
    docs_total = posts_total + comments_total
    docs_missing = posts_missing + comments_missing
    missing_rate = (docs_missing / docs_total) if docs_total else None

    return {
        "start": created_start,
        "end": created_end,
        "days": days(created_start, created_end),
        "posts_total": posts_total,
        "comments_total": comments_total,
        "docs_total": docs_total,
        "posts_missing": posts_missing,
        "comments_missing": comments_missing,
        "docs_missing": docs_missing,
        "missing_rate": missing_rate,
    }


def compute_run_window(rows: list[dict[str, str]]) -> dict[str, Any]:
    run_times_by_id: dict[str, set[datetime]] = {}
    rows_with_parsed_time = 0
    run_id_without_time = 0
    rows_without_run_id = 0

    for row in rows:
        run_id = str(row.get("run_id") or "").strip()
        run_time = parse_dt(row.get("run_time"))
        if not run_id:
            rows_without_run_id += 1
            continue
        if run_time is None:
            run_id_without_time += 1
            continue
        rows_with_parsed_time += 1
        run_times_by_id.setdefault(run_id, set()).add(run_time)

    canonical_runs: list[tuple[str, datetime]] = []
    inconsistent_run_ids: list[str] = []
    for run_id, times in run_times_by_id.items():
        if len(times) > 1:
            inconsistent_run_ids.append(run_id)
        canonical_runs.append((run_id, min(times)))
    canonical_runs.sort(key=lambda x: x[1])

    run_start = canonical_runs[0][1] if canonical_runs else None
    run_end = canonical_runs[-1][1] if canonical_runs else None
    run_days = days(run_start, run_end)

    intervals_hours: list[float] = []
    if len(canonical_runs) >= 2:
        for idx in range(1, len(canonical_runs)):
            delta = canonical_runs[idx][1] - canonical_runs[idx - 1][1]
            intervals_hours.append(hours(delta.total_seconds()))

    drift_seconds: list[float] = []
    drift_without_run_id_ts = 0
    for run_id, run_time in canonical_runs:
        parsed = parse_run_id(run_id)
        if parsed is None:
            drift_without_run_id_ts += 1
            continue
        drift_seconds.append(abs((run_time - parsed).total_seconds()))

    return {
        "run_count": len(canonical_runs),
        "row_count": len(rows),
        "rows_with_parsed_time": rows_with_parsed_time,
        "rows_without_run_id": rows_without_run_id,
        "run_id_without_time": run_id_without_time,
        "start": run_start,
        "end": run_end,
        "days": run_days,
        "inconsistent_run_ids": sorted(inconsistent_run_ids),
        "interval_hours": intervals_hours,
        "drift_seconds": drift_seconds,
        "drift_without_run_id_ts": drift_without_run_id_ts,
    }


def parse_lineage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "found": False,
            "rows": 0,
            "axis_counts": {},
            "ambiguous_rows": 0,
            "indirect_rows": 0,
            "unknown_rows": 0,
        }

    axis_counts: Counter[str] = Counter()
    ambiguous_rows = 0
    indirect_rows = 0
    unknown_rows = 0
    rows = 0

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            raw_axis = str(row.get("time_axis") or "").strip()
            axis = raw_axis.lower()
            axis_counts[raw_axis or ""] += 1
            has_created = "created_at" in axis
            has_run = "run_time" in axis
            if has_created and has_run:
                ambiguous_rows += 1
            if "indirect" in axis or "indirecto" in axis:
                indirect_rows += 1
            if not has_created and not has_run:
                unknown_rows += 1

    return {
        "path": str(path),
        "found": True,
        "rows": rows,
        "axis_counts": dict(axis_counts),
        "ambiguous_rows": ambiguous_rows,
        "indirect_rows": indirect_rows,
        "unknown_rows": unknown_rows,
    }


def evaluate_checks(
    created: dict[str, Any],
    runs: dict[str, Any],
    lineage: dict[str, Any],
) -> list[CheckResult]:
    out: list[CheckResult] = []

    created_days = created["days"]
    run_days = runs["days"]
    missing_rate = created["missing_rate"]
    drift_seconds = runs["drift_seconds"]
    inconsistent_run_ids = runs["inconsistent_run_ids"]

    has_created_window = created["start"] is not None and created["end"] is not None and (created_days is None or created_days >= 0)
    out.append(
        CheckResult(
            id="CHK-001",
            status="PASS" if has_created_window else "FAIL",
            message="created_at window is parseable and ordered.",
            details={
                "created_start": to_iso(created["start"]),
                "created_end": to_iso(created["end"]),
                "created_window_days": safe_float(created_days, 4),
            },
        )
    )

    has_run_window = runs["start"] is not None and runs["end"] is not None and (run_days is None or run_days >= 0)
    out.append(
        CheckResult(
            id="CHK-002",
            status="PASS" if has_run_window else "FAIL",
            message="run_time window is parseable and ordered.",
            details={
                "run_start": to_iso(runs["start"]),
                "run_end": to_iso(runs["end"]),
                "run_window_days": safe_float(run_days, 4),
                "runs": runs["run_count"],
            },
        )
    )

    temporal_separation_ok = False
    if created_days is not None and run_days is not None:
        temporal_separation_ok = created_days >= run_days
    out.append(
        CheckResult(
            id="CHK-003",
            status="PASS" if temporal_separation_ok else "WARN",
            message="created_at window should usually be >= run_time window for scrape snapshots.",
            details={
                "created_window_days": safe_float(created_days, 4),
                "run_window_days": safe_float(run_days, 4),
                "ratio_created_over_run": (
                    safe_float((created_days / run_days), 4) if created_days and run_days and run_days > 0 else None
                ),
            },
        )
    )

    if missing_rate is None:
        missing_status = "WARN"
    elif missing_rate == 0:
        missing_status = "PASS"
    elif missing_rate <= 0.01:
        missing_status = "WARN"
    else:
        missing_status = "FAIL"
    out.append(
        CheckResult(
            id="CHK-004",
            status=missing_status,
            message="Missing created_at fields should remain near zero.",
            details={
                "docs_missing": created["docs_missing"],
                "docs_total": created["docs_total"],
                "missing_rate": safe_float(missing_rate, 6),
            },
        )
    )

    if inconsistent_run_ids:
        consistency_status = "FAIL"
    else:
        consistency_status = "PASS"
    out.append(
        CheckResult(
            id="CHK-005",
            status=consistency_status,
            message="Each run_id should map to a single run_time.",
            details={
                "inconsistent_run_ids": inconsistent_run_ids[:25],
                "inconsistent_count": len(inconsistent_run_ids),
            },
        )
    )

    if drift_seconds:
        drift_max = max(drift_seconds)
        drift_median = median(drift_seconds)
        if drift_max <= 300:
            drift_status = "PASS"
        elif drift_max <= 900:
            drift_status = "WARN"
        else:
            drift_status = "FAIL"
    else:
        drift_max = None
        drift_median = None
        drift_status = "WARN"
    out.append(
        CheckResult(
            id="CHK-006",
            status=drift_status,
            message="run_time should stay close to run_id timestamp.",
            details={
                "drift_median_seconds": safe_float(drift_median, 3),
                "drift_max_seconds": safe_float(drift_max, 3),
                "checked_runs": len(drift_seconds),
                "runs_without_parseable_run_id": runs["drift_without_run_id_ts"],
            },
        )
    )

    if lineage["found"]:
        if lineage["ambiguous_rows"] > 0 or lineage["unknown_rows"] > 0:
            lineage_status = "WARN"
        else:
            lineage_status = "PASS"
        details = {
            "lineage_rows": lineage["rows"],
            "ambiguous_rows": lineage["ambiguous_rows"],
            "unknown_rows": lineage["unknown_rows"],
            "indirect_rows": lineage["indirect_rows"],
        }
    else:
        lineage_status = "WARN"
        details = {"lineage_found": False}

    out.append(
        CheckResult(
            id="CHK-007",
            status=lineage_status,
            message="Metric lineage should declare a clear time_axis (created_at or run_time).",
            details=details,
        )
    )

    return out


def build_recommendations(checks: list[CheckResult]) -> list[str]:
    statuses = {c.id: c.status for c in checks}
    recs = [
        "Use created_at for publication-time questions (activity, seasonality, language shifts, meme birth/death).",
        "Use run_time only for capture-process questions (scraper cadence, coverage by run, snapshot comparability).",
        "Label every chart/table with its time axis to avoid mixing publication rhythm with capture rhythm.",
    ]
    if statuses.get("CHK-003") != "PASS":
        recs.append("Temporal windows suggest potential axis confusion; verify that created_at-based metrics are not fed with run_time.")
    if statuses.get("CHK-004") != "PASS":
        recs.append("Backfill or drop records with missing created_at before any real-time temporal analysis.")
    if statuses.get("CHK-005") != "PASS":
        recs.append("Fix run generation so each run_id has exactly one canonical run_time.")
    if statuses.get("CHK-006") != "PASS":
        recs.append("Align run_id generation and scrape timestamp capture to reduce drift and improve reproducibility.")
    if statuses.get("CHK-007") != "PASS":
        recs.append("Normalize lineage time_axis values to only: created_at, run_time, created_at_indirect.")
    return recs


def build_summary(created: dict[str, Any], runs: dict[str, Any]) -> dict[str, Any]:
    created_days = created["days"]
    run_days = runs["days"]
    interval_hours = runs["interval_hours"]

    return {
        "created_at_window": {
            "start": to_iso(created["start"]),
            "end": to_iso(created["end"]),
            "days": safe_float(created_days, 4),
        },
        "run_time_window": {
            "start": to_iso(runs["start"]),
            "end": to_iso(runs["end"]),
            "days": safe_float(run_days, 4),
            "runs": runs["run_count"],
        },
        "window_ratio_created_over_run": (
            safe_float(created_days / run_days, 4) if created_days and run_days and run_days > 0 else None
        ),
        "created_at_missing_rate": safe_float(created["missing_rate"], 6),
        "run_cadence_hours": {
            "median": safe_float(median(interval_hours), 3) if interval_hours else None,
            "max": safe_float(max(interval_hours), 3) if interval_hours else None,
            "min": safe_float(min(interval_hours), 3) if interval_hours else None,
        },
    }


def build_markdown_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = payload["summary"]
    checks = payload["checks"]

    lines.append("# Temporal Contract Audit")
    lines.append("")
    lines.append(f"- generated_at: {payload['generated_at']}")
    lines.append("- definitions:")
    lines.append("  - created_at: publication timestamp in the platform.")
    lines.append("  - run_time: scraper capture timestamp per run.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- created_at window: {summary['created_at_window']['start']} -> {summary['created_at_window']['end']} "
        f"({summary['created_at_window']['days']} days)"
    )
    lines.append(
        f"- run_time window: {summary['run_time_window']['start']} -> {summary['run_time_window']['end']} "
        f"({summary['run_time_window']['days']} days, runs={summary['run_time_window']['runs']})"
    )
    lines.append(f"- created/run window ratio: {summary['window_ratio_created_over_run']}")
    lines.append(f"- missing created_at rate: {summary['created_at_missing_rate']}")
    lines.append(
        f"- run cadence (hours): median={summary['run_cadence_hours']['median']} "
        f"min={summary['run_cadence_hours']['min']} max={summary['run_cadence_hours']['max']}"
    )
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| id | status | message |")
    lines.append("|---|---|---|")
    for check in checks:
        lines.append(f"| {check['id']} | {check['status']} | {check['message']} |")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    for rec in payload["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")
    if payload.get("lineage", {}).get("found"):
        lineage = payload["lineage"]
        lines.append("## Lineage Axis Counts")
        lines.append("")
        axis_counts = lineage.get("axis_counts", {})
        if axis_counts:
            for axis, count in sorted(axis_counts.items(), key=lambda x: x[0]):
                label = axis if axis else "<empty>"
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- No lineage rows found.")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit temporal semantics and consistency for created_at (publication) vs run_time (capture)."
    )
    parser.add_argument("--coverage", default="data/derived/coverage_quality.json")
    parser.add_argument("--diffusion-runs", default="data/derived/diffusion_runs.csv")
    parser.add_argument("--lineage", default="reports/audit/data_lineage.csv")
    parser.add_argument("--out-json", default="data/derived/temporal_contract_audit.json")
    parser.add_argument("--out-md", default="reports/temporal_contract_audit.md")
    args = parser.parse_args()

    coverage_path = Path(args.coverage)
    runs_path = Path(args.diffusion_runs)
    lineage_path = Path(args.lineage)

    coverage = load_coverage(coverage_path)
    runs_rows = load_run_rows(runs_path)
    created = compute_created_window(coverage)
    runs = compute_run_window(runs_rows)
    lineage = parse_lineage(lineage_path)
    checks = evaluate_checks(created, runs, lineage)

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "definitions": {
            "created_at": "Real publication timestamp in Moltbook.",
            "run_time": "Timestamp when scraper captured the snapshot/run.",
        },
        "inputs": {
            "coverage": str(coverage_path),
            "diffusion_runs": str(runs_path),
            "lineage": str(lineage_path),
        },
        "summary": build_summary(created, runs),
        "checks": [
            {
                "id": c.id,
                "status": c.status,
                "message": c.message,
                "details": c.details,
            }
            for c in checks
        ],
        "lineage": lineage,
        "recommendations": build_recommendations(checks),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_markdown_report(payload), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")

    for c in checks:
        print(f"{c.id} [{c.status}] {c.message}")


if __name__ == "__main__":
    main()
