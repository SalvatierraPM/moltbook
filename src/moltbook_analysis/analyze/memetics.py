from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from moltbook_analysis.analyze.text import clean_text, tokenize


def extract_ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def build_ngram_series(df: pd.DataFrame, n: int = 2, weight_col: str | None = None) -> pd.DataFrame:
    """Return a long dataframe: columns = [date, ngram, count]."""
    rows = []
    for _, row in df.iterrows():
        text = clean_text(str(row.get("text", "")))
        if not text:
            continue
        weight = 1.0
        if weight_col and row.get(weight_col) is not None:
            try:
                weight = float(row.get(weight_col)) or 1.0
            except Exception:
                weight = 1.0
        tokens = tokenize(text)
        if len(tokens) < n:
            continue
        ngrams = extract_ngrams(tokens, n)
        counts = Counter(ngrams)
        date = pd.to_datetime(row.get("created_at"), errors="coerce")
        if pd.isna(date):
            continue
        day = date.floor("D")
        for ngram, count in counts.items():
            rows.append({"date": day, "ngram": " ".join(ngram), "count": count * weight})

    if not rows:
        return pd.DataFrame(columns=["date", "ngram", "count"])
    return pd.DataFrame(rows).groupby(["date", "ngram"], as_index=False)["count"].sum()


def burst_scores(series_df: pd.DataFrame) -> pd.DataFrame:
    """Compute burst scores per ngram using max z-score across days."""
    if series_df.empty:
        return pd.DataFrame(columns=["ngram", "burst", "mean", "std", "max_day"])

    pivot = series_df.pivot_table(index="date", columns="ngram", values="count", fill_value=0)
    means = pivot.mean(axis=0)
    stds = pivot.std(axis=0).replace(0, np.nan)
    z = (pivot - means) / stds
    z = z.replace([np.inf, -np.inf], np.nan)
    z_filled = z.fillna(0)
    max_z = z_filled.max(axis=0)
    max_day = z_filled.idxmax(axis=0)

    def _fmt_day(d):
        if pd.isna(d):
            return None
        return str(pd.to_datetime(d).date())

    out = pd.DataFrame(
        {
            "ngram": max_z.index,
            "burst": max_z.values,
            "mean": means.values,
            "std": stds.values,
            "max_day": [_fmt_day(d) for d in max_day.values],
        }
    ).sort_values("burst", ascending=False)
    return out
