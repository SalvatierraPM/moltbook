from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from moltbook_analysis.config import get_settings
from moltbook_analysis.analyze.memetics import build_ngram_series, burst_scores
from moltbook_analysis.analyze.ontology import build_cooccurrence_graph, top_concepts
from moltbook_analysis.analyze.interference import interference_score


def _load_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def load_posts() -> pd.DataFrame:
    s = get_settings()
    parquet = s.normalized_dir / "posts.parquet"
    jsonl = s.normalized_dir / "posts.jsonl"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if jsonl.exists():
        return _load_jsonl(jsonl)
    return pd.DataFrame()


def build_report() -> Path:
    s = get_settings()
    df = load_posts()
    s.reports_dir.mkdir(parents=True, exist_ok=True)

    if df.empty:
        out = s.reports_dir / "paper.md"
        out.write_text("# Moltbook Analysis\n\nNo data found. Run ingest + normalize first.\n", encoding="utf-8")
        return out

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["text"] = (df.get("title", "").fillna("") + "\n" + df.get("body", "").fillna("")).astype(str)

    total_posts = len(df)
    date_min = df["created_at"].min()
    date_max = df["created_at"].max()

    # Memetics (weighted by popularity signals)
    df["score"] = pd.to_numeric(df.get("score"), errors="coerce").fillna(0)
    df["comment_count"] = pd.to_numeric(df.get("comment_count"), errors="coerce").fillna(0)
    df["popularity_weight"] = 1.0 + df["score"] + 0.3 * df["comment_count"]
    series_df = build_ngram_series(df[["created_at", "text", "popularity_weight"]].dropna(), weight_col="popularity_weight")
    bursts = burst_scores(series_df).head(15)

    # Ontology
    texts = df["text"].dropna().tolist()
    G = build_cooccurrence_graph(texts)
    concepts = top_concepts(G, top_n=15)

    # Interference
    df["interference"] = df["text"].apply(lambda t: interference_score(t)["score"])
    top_interf = df.sort_values("interference", ascending=False).head(10)

    # Engagement
    df["engagement"] = df["score"] + df["comment_count"]
    top_engagement = df.sort_values("engagement", ascending=False).head(10)

    out = s.reports_dir / "paper.md"
    out.write_text(
        _render_markdown(
            total_posts=total_posts,
            date_min=date_min,
            date_max=date_max,
            bursts=bursts,
            concepts=concepts,
            top_interf=top_interf,
            top_engagement=top_engagement,
        ),
        encoding="utf-8",
    )
    return out


def _render_markdown(**ctx: Any) -> str:
    total_posts = ctx["total_posts"]
    date_min = ctx["date_min"]
    date_max = ctx["date_max"]
    bursts = ctx["bursts"]
    concepts = ctx["concepts"]
    top_interf = ctx["top_interf"]
    top_engagement = ctx["top_engagement"]

    lines = []
    lines.append("# Moltbook: Memetics, Ontology, and Interference\n")
    lines.append("## Abstract")
    lines.append(
        f"We analyze {total_posts} posts from {date_min.date()} to {date_max.date()} to map memetic dynamics, language ontology, and indicators of human interference/prompt injection."
    )
    lines.append("\n## Data")
    lines.append("- Source: Moltbook public posts (API/HTML).")
    lines.append("- Window: from launch to present (configurable).")

    lines.append("\n## Methods")
    lines.append("- N-gram burst analysis for memetic spikes (weighted by score and comment count).")
    lines.append("- Co-occurrence graph of concepts for ontology extraction.")
    lines.append("- Heuristic interference scoring (prompt injection & LLM disclaimers).")

    lines.append("\n## Results: Memetics")
    if bursts.empty:
        lines.append("- No bursty n-grams detected.")
    else:
        lines.append("Top bursty n-grams:")
        for _, row in bursts.iterrows():
            lines.append(f"- {row['ngram']} (burst={row['burst']:.2f}, peak={row['max_day']})")

    lines.append("\n## Results: Ontology")
    if concepts.empty:
        lines.append("- No concepts extracted.")
    else:
        lines.append("Top concepts by weighted degree:")
        for _, row in concepts.iterrows():
            lines.append(f"- {row['term']} (degree={row['degree']:.1f})")

    lines.append("\n## Results: Interference Signals")
    if top_interf.empty:
        lines.append("- No interference signals detected.")
    else:
        lines.append("Top posts by interference score:")
        for _, row in top_interf.iterrows():
            pid = row.get("id")
            score = row.get("interference")
            title = str(row.get("title", ""))[:80].replace("\n", " ")
            lines.append(f"- id={pid} score={score:.2f} title={title}")

    lines.append("\n## Results: Engagement")
    if top_engagement.empty:
        lines.append("- No engagement signals available.")
    else:
        lines.append("Top posts by (score + comment_count):")
        for _, row in top_engagement.iterrows():
            pid = row.get("id")
            eng = row.get("engagement")
            title = str(row.get("title", ""))[:80].replace("\n", " ")
            lines.append(f"- id={pid} engagement={eng:.0f} title={title}")

    lines.append("\n## Discussion")
    lines.append("- Interpret bursts as memetic amplification or coordinated activity.")
    lines.append("- Ontology clusters reveal persistent narrative frames.")
    lines.append("- Interference signals are heuristic; validate with manual review.")

    lines.append("\n## Limitations")
    lines.append("- Potential sampling bias; access constrained by API/robots/ToS.")
    lines.append("- Heuristics are noisy and not ground-truth labels.")

    lines.append("\n## Ethics")
    lines.append("- Avoid collecting private data; respect platform rules.")
    lines.append("- Report aggregate findings; minimize identification risks.")

    return "\n".join(lines) + "\n"
