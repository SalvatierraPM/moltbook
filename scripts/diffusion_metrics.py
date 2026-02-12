#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd


RUN_ID_RE = re.compile(r"^(\\d{8})T(\\d{6})Z$")


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
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


def parse_run_time(run_id: str | None, fallback: pd.Timestamp | None) -> pd.Timestamp:
    if isinstance(run_id, str) and run_id:
        m = RUN_ID_RE.match(run_id)
        if m:
            date = m.group(1)
            time = m.group(2)
            try:
                dt = datetime.strptime(date + time, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                return pd.to_datetime(dt)
            except Exception:
                pass
    return fallback if fallback is not None else pd.Timestamp.now(tz=timezone.utc)


def load_listings(path: Path) -> pd.DataFrame:
    rows = list(iter_jsonl(path))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "run_id" not in df.columns:
        df["run_id"] = None
    df["scrape_ts"] = pd.to_datetime(df.get("scrape_ts"), errors="coerce", utc=True)
    df["score"] = pd.to_numeric(df.get("score"), errors="coerce")
    df["comment_count"] = pd.to_numeric(df.get("comment_count"), errors="coerce")
    df["rank"] = pd.to_numeric(df.get("rank"), errors="coerce")
    return df


def compute_diffusion(listings: pd.DataFrame, out_dir: Path) -> None:
    if listings.empty:
        print("No listings found. Skipping diffusion metrics.")
        return

    run_fallback = listings.groupby("run_id")["scrape_ts"].min().rename("run_fallback")
    listings = listings.merge(run_fallback, on="run_id", how="left")
    listings["run_time"] = listings.apply(
        lambda r: parse_run_time(r.get("run_id"), r.get("run_fallback")), axis=1
    )

    grouped = (
        listings.groupby(["post_id", "run_id"], as_index=False)
        .agg(
            submolt=("submolt", "first"),
            sort=("sort", "first"),
            score=("score", "max"),
            comment_count=("comment_count", "max"),
            rank=("rank", "min"),
            run_time=("run_time", "min"),
        )
        .sort_values(["post_id", "run_time"])
    )

    def summarize_post(df: pd.DataFrame) -> Dict[str, Any]:
        first = df.iloc[0]
        last = df.iloc[-1]
        run_span = (last["run_time"] - first["run_time"]).total_seconds() / 3600.0
        run_span = max(run_span, 1e-6)
        score_delta = (last.get("score") or 0) - (first.get("score") or 0)
        comment_delta = (last.get("comment_count") or 0) - (first.get("comment_count") or 0)
        peak_idx = df["score"].fillna(-1).idxmax()
        peak = df.loc[peak_idx] if peak_idx in df.index else last
        return {
            "post_id": first.get("post_id"),
            "submolt": first.get("submolt"),
            "first_run": first.get("run_id"),
            "last_run": last.get("run_id"),
            "runs_seen": len(df),
            "score_first": first.get("score"),
            "score_last": last.get("score"),
            "score_delta": score_delta,
            "comment_first": first.get("comment_count"),
            "comment_last": last.get("comment_count"),
            "comment_delta": comment_delta,
            "hours_span": round(run_span, 3),
            "score_velocity": score_delta / run_span,
            "comment_velocity": comment_delta / run_span,
            "peak_score": peak.get("score"),
            "peak_run": peak.get("run_id"),
            "best_rank": df["rank"].min(),
            "mean_rank": df["rank"].mean(),
        }

    rows = []
    for _, g in grouped.groupby("post_id"):
        rows.append(summarize_post(g))
    post_metrics_df = pd.DataFrame(rows)
    post_metrics_df.to_csv(out_dir / "diffusion_posts.csv", index=False)

    run_summary = (
        grouped.groupby(["run_id", "submolt"], as_index=False)
        .agg(
            run_time=("run_time", "min"),
            posts_seen=("post_id", "nunique"),
            mean_score=("score", "mean"),
            mean_comments=("comment_count", "mean"),
        )
        .sort_values(["run_time", "submolt"])
    )
    run_summary.to_csv(out_dir / "diffusion_runs.csv", index=False)

    submolt_summary = (
        run_summary.groupby("submolt", as_index=False)
        .agg(
            runs_seen=("run_id", "nunique"),
            posts_seen_total=("posts_seen", "sum"),
            mean_score=("mean_score", "mean"),
            mean_comments=("mean_comments", "mean"),
        )
        .sort_values("posts_seen_total", ascending=False)
    )
    submolt_summary.to_csv(out_dir / "diffusion_submolts.csv", index=False)

    print(f"Diffusion metrics written to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute diffusion metrics using listings run_id snapshots.")
    parser.add_argument("--listings", default="data/raw/api_fetch/listings.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    listings = load_listings(Path(args.listings))
    compute_diffusion(listings, out_dir)


if __name__ == "__main__":
    main()
