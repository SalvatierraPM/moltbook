#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import scipy.optimize as opt
from scipy.special import gammaln
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans, DBSCAN

# Allow running this script directly without requiring editable installs.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.language_ontology import speech_act_features
from moltbook_analysis.analyze.text import clean_text


URL_RE = re.compile(r"https?://\\S+|www\\.\\S+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#([\\w\\-]{1,50})", re.UNICODE)
EMOJI_RE = re.compile(r"[\\U0001F300-\\U0001FAFF]")

HEX_TOKEN_RE = re.compile(r"^(?:0x)?[0-9a-f]{4,}$", re.IGNORECASE)
# gTLDs and common suffix tokens that often appear split as "<name> <tld>" after tokenization.
TLD_TOKENS = {"com", "net", "org", "xyz", "io", "app", "dev", "cloud"}
URL_TOKENS = {"http", "https", "www"}
CLI_TOKENS = {"curl", "wget", "jq", "pip", "npm", "brew", "sudo", "apt", "bash", "zsh", "powershell"}
API_TOKENS = {
    "api",
    "apis",
    "endpoint",
    "oauth",
    "bearer",
    "token",
    "json",
    "xml",
    "rss",
    "v1",
    "v2",
}
# "Infra" tokens that are weak alone, but strong when combined with API/CLI/campaign patterns.
INFRA_TOKENS = {"cloud", "sdk", "cli", "rss", "xml", "json"}
# High-frequency campaign/spam tokens observed in Moltbook; kept as signals rather than stopwords.
CAMPAIGN_TOKENS = {
    "agentmarket",
    "discover",
    "mbc",
    "mbc20",
    "clawhub",
    "openclaw",
    "mint",
    "tick",
    "amt",
    "op",
}


def classify_candidate_meme(phrase: str) -> Tuple[str, int, str]:
    """
    Classify a lexical meme candidate into a coarse bucket:
    - cultural_candidate: likely conversational idea-bearing phrase
    - technical_boilerplate: likely template/URL/CLI/API/campaign boilerplate

    This is intentionally conservative and produces *double rankings* in the outputs
    (cultural vs technical), to avoid confusing repetition of technical templates with
    "cultural dominance" in the memetics module.
    """
    raw = (phrase or "").strip().lower()
    if not raw:
        return ("cultural_candidate", 0, "")
    tokens = [t for t in raw.split() if t]

    score = 0
    reasons: List[str] = []

    has_url = any(t in URL_TOKENS for t in tokens)
    if has_url:
        score += 3
        reasons.append("url_token")

    # Domain-like tokenization often becomes "example com" or "moltbook com post" after tokenization.
    # Treat any presence of a TLD token combined with a word-ish token as domain boilerplate.
    has_tld = any(t in TLD_TOKENS for t in tokens) and any(len(t) >= 4 and t.isalpha() for t in tokens)
    if has_tld:
        score += 3
        reasons.append("tld_token")

    has_cli = any(t in CLI_TOKENS for t in tokens)
    if has_cli:
        score += 3
        reasons.append("cli_token")

    api_hits = sum(1 for t in tokens if t in API_TOKENS)
    if api_hits:
        score += min(6, api_hits * 2)
        reasons.append(f"api_token:{api_hits}")

    has_0x = any(t.startswith("0x") for t in tokens)
    if has_0x:
        score += 3
        reasons.append("0x_token")

    has_hex = any(HEX_TOKEN_RE.match(t) for t in tokens)
    if has_hex:
        score += 3
        reasons.append("hex_token")

    camp_hits = sum(1 for t in tokens if t in CAMPAIGN_TOKENS)
    if camp_hits:
        score += min(6, camp_hits * 2)
        reasons.append(f"campaign_token:{camp_hits}")

    infra_hits = sum(1 for t in tokens if t in INFRA_TOKENS)
    if infra_hits and (api_hits or camp_hits or has_cli):
        score += 2
        reasons.append(f"infra_token:{infra_hits}")

    has_digits = any(t.isdigit() and len(t) >= 2 for t in tokens)
    has_digits3 = any(t.isdigit() and len(t) >= 3 for t in tokens)
    # Numeric-heavy ngrams are frequently campaign IDs / airdrop boilerplate.
    if has_digits:
        score += 1
        reasons.append("digits")

    hard_boilerplate = has_url or has_tld or has_cli or has_hex or has_0x
    technical = hard_boilerplate or api_hits > 0 or camp_hits > 0 or has_digits3
    category = "technical_boilerplate" if technical or score >= 4 else "cultural_candidate"
    return (category, score, "|".join(reasons))


def iter_jsonl(path: Path) -> Iterable[dict]:
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


def safe_submolt_name(obj: dict) -> Optional[str]:
    submolt = obj.get("submolt")
    if isinstance(submolt, dict):
        return submolt.get("name")
    if isinstance(submolt, str):
        return submolt
    return None


def load_docs(posts_path: Path, comments_path: Path) -> pd.DataFrame:
    posts: List[dict] = []
    post_submolt: Dict[str, str] = {}
    for p in iter_jsonl(posts_path):
        author = p.get("author") or {}
        text = ((p.get("title") or "") + "\n" + (p.get("content") or "")).strip()
        pid = p.get("id")
        submolt = safe_submolt_name(p)
        if isinstance(pid, str) and submolt:
            post_submolt[pid] = submolt
        posts.append(
            {
                "doc_id": pid,
                "doc_type": "post",
                "post_id": pid,
                "author_id": author.get("id"),
                "author_name": author.get("name"),
                "submolt": submolt,
                "created_at": p.get("created_at"),
                "text": text,
            }
        )

    comments: List[dict] = []
    for c in iter_jsonl(comments_path):
        author = c.get("author") or {}
        text = (c.get("content") or "").strip()
        post_id = c.get("post_id")
        comments.append(
            {
                "doc_id": c.get("id"),
                "doc_type": "comment",
                "post_id": post_id,
                "author_id": c.get("author_id") or author.get("id"),
                "author_name": author.get("name"),
                "submolt": post_submolt.get(post_id),
                "created_at": c.get("created_at"),
                "text": text,
            }
        )

    df = pd.DataFrame(posts + comments)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["created_at"])
    df["hour"] = df["created_at"].dt.floor("H")
    df["text"] = df["text"].fillna("").astype(str)
    return df


def extract_hashtags(text: str) -> List[str]:
    return [f"#{m.group(1).lower()}" for m in HASHTAG_RE.finditer(text)]


def extract_emojis(text: str) -> List[str]:
    return EMOJI_RE.findall(text)


def kleinberg_bursts(counts: List[int], s: float = 2.0, gamma: float = 1.0) -> List[Tuple[int, int, int]]:
    # Returns list of (start_idx, end_idx, level)
    if not counts:
        return []
    n = len(counts)
    total = sum(counts)
    if total == 0:
        return []
    base_rate = total / n
    max_rate = max(counts) if max(counts) > 0 else base_rate
    k = max(1, int(math.log(max_rate / base_rate + 1e-9, s)) + 1)
    rates = [base_rate * (s ** i) for i in range(k + 1)]

    def cost(i: int, c: int) -> float:
        r = rates[i]
        return r - c * math.log(r + 1e-12) + gammaln(c + 1)

    dp = np.full((n, k + 1), np.inf)
    back = np.zeros((n, k + 1), dtype=int)
    for i in range(k + 1):
        dp[0, i] = cost(i, counts[0])

    for t in range(1, n):
        for i in range(k + 1):
            penalties = dp[t - 1] + gamma * np.abs(np.arange(k + 1) - i)
            j = int(np.argmin(penalties))
            dp[t, i] = penalties[j] + cost(i, counts[t])
            back[t, i] = j

    states = np.zeros(n, dtype=int)
    states[-1] = int(np.argmin(dp[-1]))
    for t in range(n - 2, -1, -1):
        states[t] = back[t + 1, states[t + 1]]

    bursts: List[Tuple[int, int, int]] = []
    in_burst = False
    start = 0
    level = 0
    for i, st in enumerate(states):
        if st > 0 and not in_burst:
            in_burst = True
            start = i
            level = st
        elif st == 0 and in_burst:
            bursts.append((start, i - 1, level))
            in_burst = False
    if in_burst:
        bursts.append((start, n - 1, level))
    return bursts


def entropy(counts: List[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return -sum(p * math.log(p + 1e-12) for p in probs)


def build_lexical_memes(
    df: pd.DataFrame,
    max_features: int,
    min_df: int,
    top_n: int,
    sample_docs: int,
) -> Tuple[List[str], np.ndarray, CountVectorizer, List[int]]:
    texts = df["text"].tolist()
    if sample_docs > 0 and len(texts) > sample_docs:
        texts = texts[:sample_docs]
    vectorizer = CountVectorizer(
        max_features=max_features,
        min_df=min_df,
        ngram_range=(2, 3),
        stop_words="english",
    )
    X = vectorizer.fit_transform(texts)
    counts = np.asarray(X.sum(axis=0)).ravel()
    top_idx = np.argsort(counts)[::-1][:top_n]
    terms = vectorizer.get_feature_names_out()
    top_terms = [terms[i] for i in top_idx]
    return top_terms, counts, vectorizer, top_idx.tolist()


def timeseries_for_terms(
    df: pd.DataFrame,
    vectorizer: CountVectorizer,
    term_idx: List[int],
    by_submolt: bool,
    max_docs: int,
) -> pd.DataFrame:
    if df.empty or not term_idx:
        return pd.DataFrame(columns=["hour", "meme", "count", "unique_authors", "scope", "submolt"])
    texts = df["text"].tolist()
    if max_docs > 0 and len(texts) > max_docs:
        df = df.iloc[:max_docs].copy()
        texts = df["text"].tolist()
    X = vectorizer.transform(texts)[:, term_idx]
    term_names = np.array(vectorizer.get_feature_names_out())[term_idx]
    hours = df["hour"].tolist()
    authors = df["author_id"].fillna("unknown").tolist()
    submolts = df["submolt"].fillna("unknown").tolist()

    counts = defaultdict(int)
    unique_authors = defaultdict(set)
    for row_idx in range(X.shape[0]):
        row = X[row_idx]
        if row.nnz == 0:
            continue
        hour = hours[row_idx]
        author = authors[row_idx]
        submolt = submolts[row_idx]
        for col_idx in row.indices:
            meme = term_names[col_idx]
            if by_submolt:
                key = (hour, meme, submolt)
            else:
                key = (hour, meme, None)
            counts[key] += 1
            unique_authors[key].add(author)

    rows = []
    for key, cnt in counts.items():
        hour, meme, submolt = key
        rows.append(
            {
                "hour": hour,
                "meme": meme,
                "meme_type": "ngram",
                "count": cnt,
                "unique_authors": len(unique_authors[key]),
                "scope": "submolt" if by_submolt else "global",
                "submolt": submolt,
            }
        )
    return pd.DataFrame(rows)


def timeseries_for_tokens(df: pd.DataFrame, token_fn, meme_type: str, by_submolt: bool) -> pd.DataFrame:
    counts = defaultdict(int)
    unique_authors = defaultdict(set)
    for _, row in df.iterrows():
        tokens = token_fn(row["text"])
        if not tokens:
            continue
        hour = row["hour"]
        author = row["author_id"] or "unknown"
        submolt = row["submolt"] or "unknown"
        for token in tokens:
            key = (hour, token, submolt if by_submolt else None)
            counts[key] += 1
            unique_authors[key].add(author)
    rows = []
    for key, cnt in counts.items():
        hour, meme, submolt = key
        rows.append(
            {
                "hour": hour,
                "meme": meme,
                "meme_type": meme_type,
                "count": cnt,
                "unique_authors": len(unique_authors[key]),
                "scope": "submolt" if by_submolt else "global",
                "submolt": submolt,
            }
        )
    return pd.DataFrame(rows)


def build_semantic_memes(
    df: pd.DataFrame,
    n_clusters: int,
    sample_docs: int,
    max_features: int,
    use_dbscan: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    texts = df["text"].tolist()
    if sample_docs > 0 and len(texts) > sample_docs:
        df = df.iloc[:sample_docs].copy()
        texts = df["text"].tolist()
    vectorizer = TfidfVectorizer(max_features=max_features, stop_words="english")
    X = vectorizer.fit_transform(texts)
    svd = TruncatedSVD(n_components=min(50, X.shape[1] - 1))
    Xr = svd.fit_transform(X)

    if use_dbscan:
        clusterer = DBSCAN(eps=0.8, min_samples=5)
        labels = clusterer.fit_predict(Xr)
    else:
        clusterer = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=2048)
        labels = clusterer.fit_predict(Xr)

    df = df.copy()
    df["semantic_cluster"] = labels
    # Label clusters by top terms
    centers = None
    if hasattr(clusterer, "cluster_centers_"):
        centers = clusterer.cluster_centers_
    top_terms = []
    if centers is not None:
        terms = np.array(vectorizer.get_feature_names_out())
        for cid, center in enumerate(centers):
            top_idx = np.argsort(center)[::-1][:8]
            top_terms.append({"cluster": cid, "top_terms": ", ".join(terms[top_idx])})
    labels_df = pd.DataFrame(top_terms)
    return df, labels_df


def build_ritual_memes(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        acts = speech_act_features(row["text"])
        # dominant act
        act_name = None
        act_score = 0
        for k, v in acts.items():
            if not k.startswith("act_"):
                continue
            if v > act_score:
                act_score = v
                act_name = k.replace("act_", "")
        if not act_name:
            continue
        rows.append(
            {
                "hour": row["hour"],
                "meme": act_name,
                "meme_type": "ritual_act",
                "count": 1,
                "unique_authors": 1,
                "scope": "global",
                "submolt": None,
                "author_id": row["author_id"] or "unknown",
            }
        )
    if not rows:
        return pd.DataFrame(columns=["hour", "meme", "meme_type", "count", "unique_authors", "scope", "submolt"])
    df_r = pd.DataFrame(rows)
    grouped = df_r.groupby(["hour", "meme"], as_index=False).agg(
        count=("count", "sum"),
        unique_authors=("author_id", "nunique"),
    )
    grouped["meme_type"] = "ritual_act"
    grouped["scope"] = "global"
    grouped["submolt"] = None
    return grouped[["hour", "meme", "meme_type", "count", "unique_authors", "scope", "submolt"]]


def classify_memes(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    out["class"] = "unknown"
    if out.empty:
        return out
    # Simple heuristics
    burst_q = out["burst_score"].quantile(0.8) if "burst_score" in out else 0
    for idx, row in out.iterrows():
        lifetime = row.get("lifetime_hours", 0) or 0
        burst = row.get("burst_score", 0) or 0
        ent = row.get("submolt_entropy", 0) or 0
        submolts = row.get("submolts_touched", 0) or 0
        if lifetime <= 48 and burst >= burst_q:
            out.at[idx, "class"] = "flash"
        elif lifetime >= 168 and burst < burst_q:
            out.at[idx, "class"] = "persistent"
        if submolts <= 2 or ent < 0.5:
            out.at[idx, "class"] = "local"
        elif submolts >= 5 and ent > 1.5:
            out.at[idx, "class"] = "cross_submolt"
    return out


def _series_for_meme(g: pd.DataFrame) -> pd.Series:
    g = g.sort_values("hour")
    idx = pd.date_range(g["hour"].min(), g["hour"].max(), freq="H", tz="UTC")
    s = g.set_index("hour")["count"].reindex(idx, fill_value=0)
    return s


def fit_discrete_hawkes(
    counts: np.ndarray,
    max_lag: int = 24,
    decay_grid: Optional[List[float]] = None,
) -> Dict[str, float]:
    if decay_grid is None:
        decay_grid = [0.2, 0.4, 0.6, 0.8, 0.9]
    best = {"loglik": -np.inf}
    T = len(counts)
    if T <= 2:
        return {"mu": 0.0, "alpha": 0.0, "decay": 0.0, "loglik": -np.inf, "branching_ratio": 0.0}

    counts = counts.astype(float)
    for decay in decay_grid:
        x = np.zeros(T)
        for t in range(1, T):
            s = 0.0
            for k in range(1, min(max_lag, t) + 1):
                s += (decay ** (k - 1)) * counts[t - k]
            x[t] = s

        # Non-negative least squares to fit mu, alpha
        A = np.vstack([np.ones(T), x]).T
        params, _ = opt.nnls(A, counts)
        mu, alpha = params[0], params[1]
        lam = np.maximum(mu + alpha * x, 1e-8)
        loglik = float(np.sum(counts * np.log(lam) - lam - gammaln(counts + 1)))
        if loglik > best["loglik"]:
            branching_ratio = float(alpha / max(1e-6, (1.0 - decay)))
            best = {
                "mu": float(mu),
                "alpha": float(alpha),
                "decay": float(decay),
                "loglik": loglik,
                "branching_ratio": branching_ratio,
            }
    return best


def compute_hawkes_metrics(
    lex_ts_global: pd.DataFrame,
    max_memes: int = 200,
) -> pd.DataFrame:
    if lex_ts_global.empty:
        return pd.DataFrame()
    memes = (
        lex_ts_global.groupby("meme")["count"]
        .sum()
        .sort_values(ascending=False)
        .head(max_memes)
        .index.tolist()
    )
    rows = []
    for meme in memes:
        g = lex_ts_global[lex_ts_global["meme"] == meme]
        series = _series_for_meme(g)
        result = fit_discrete_hawkes(series.values)
        rows.append(
            {
                "meme": meme,
                "mu": result["mu"],
                "alpha": result["alpha"],
                "decay": result["decay"],
                "branching_ratio": result["branching_ratio"],
                "loglik": result["loglik"],
                "hours": len(series),
                "total_events": int(series.sum()),
            }
        )
    return pd.DataFrame(rows)


def compute_sir_proxy(
    df: pd.DataFrame,
    vectorizer: CountVectorizer,
    term_idx: List[int],
    max_memes: int = 200,
) -> pd.DataFrame:
    term_names = np.array(vectorizer.get_feature_names_out())[term_idx]
    # Limit to top memes by global count
    term_counts = defaultdict(int)
    X = vectorizer.transform(df["text"].tolist())[:, term_idx]
    for idx, count in zip(term_names, np.asarray(X.sum(axis=0)).ravel()):
        term_counts[idx] = int(count)
    top_memes = [m for m, _ in sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:max_memes]]
    meme_to_col = {m: i for i, m in enumerate(term_names) if m in set(top_memes)}

    seen_authors: Dict[str, set] = {m: set() for m in top_memes}
    new_adopters = defaultdict(int)
    infected = defaultdict(set)

    df_sorted = df.sort_values("hour").reset_index(drop=True)
    X = vectorizer.transform(df_sorted["text"].tolist())[:, term_idx]
    for row_idx, row in df_sorted.iterrows():
        author = row["author_id"] or "unknown"
        hour = row["hour"]
        row_vec = X[row_idx]
        if row_vec.nnz == 0:
            continue
        for col in row_vec.indices:
            meme = term_names[col]
            if meme not in meme_to_col:
                continue
            infected[(meme, hour)].add(author)
            if author not in seen_authors[meme]:
                new_adopters[(meme, hour)] += 1
                seen_authors[meme].add(author)

    rows = []
    for meme in top_memes:
        hours = sorted({h for (m, h) in new_adopters.keys() if m == meme} | {h for (m, h) in infected.keys() if m == meme})
        if not hours:
            continue
        rt_values = []
        total_adopters = len(seen_authors[meme])
        for h in hours:
            inf = len(infected.get((meme, h), []))
            new = new_adopters.get((meme, h), 0)
            if inf > 0:
                rt_values.append(new / inf)
        rows.append(
            {
                "meme": meme,
                "mean_Rt": float(np.mean(rt_values)) if rt_values else 0.0,
                "peak_Rt": float(np.max(rt_values)) if rt_values else 0.0,
                "adopters_total": total_adopters,
                "hours_active": len(hours),
            }
        )
    return pd.DataFrame(rows)


def compute_survival_curves(metrics_df: pd.DataFrame, out_dir: Path) -> None:
    if metrics_df.empty or "lifetime_hours" not in metrics_df:
        return
    try:
        from lifelines import KaplanMeierFitter, NelsonAalenFitter
    except Exception:
        return
    durations = metrics_df["lifetime_hours"].fillna(0)
    durations = durations[durations > 0]
    if durations.empty:
        return
    kmf = KaplanMeierFitter()
    kmf.fit(durations)
    kmf.survival_function_.reset_index().rename(columns={"timeline": "hours", "KM_estimate": "survival"}).to_csv(
        out_dir / "meme_survival_curve.csv", index=False
    )
    naf = NelsonAalenFitter()
    naf.fit(durations)
    naf.cumulative_hazard_.reset_index().rename(columns={"timeline": "hours", "NA_estimate": "hazard"}).to_csv(
        out_dir / "meme_hazard_curve.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Memetic models: lexical, semantic, ritual, macro.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    parser.add_argument("--max-lexical-memes", type=int, default=500)
    parser.add_argument("--max-lexical-features", type=int, default=8000)
    parser.add_argument("--lexical-min-df", type=int, default=10)
    parser.add_argument("--lexical-sample-docs", type=int, default=0)
    parser.add_argument("--max-docs", type=int, default=0)
    parser.add_argument("--by-submolt", action=argparse.BooleanOptionalAction, default=True)

    parser.add_argument("--semantic", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--semantic-clusters", type=int, default=50)
    parser.add_argument("--semantic-sample-docs", type=int, default=50000)
    parser.add_argument("--semantic-max-features", type=int, default=5000)
    parser.add_argument("--semantic-dbscan", action=argparse.BooleanOptionalAction, default=False)

    parser.add_argument("--ritual", action=argparse.BooleanOptionalAction, default=True)

    parser.add_argument("--burst-s", type=float, default=2.0)
    parser.add_argument("--burst-gamma", type=float, default=1.0)
    parser.add_argument("--hawkes", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--hawkes-max-memes", type=int, default=200)
    parser.add_argument("--sir", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sir-max-memes", type=int, default=200)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_docs(Path(args.posts), Path(args.comments))
    if args.max_docs > 0 and len(df) > args.max_docs:
        df = df.iloc[: args.max_docs].copy()

    # Lexical memes (ngrams)
    top_terms, counts, vectorizer, top_idx = build_lexical_memes(
        df,
        max_features=args.max_lexical_features,
        min_df=args.lexical_min_df,
        top_n=args.max_lexical_memes,
        sample_docs=args.lexical_sample_docs,
    )
    lex_ts_global = timeseries_for_terms(df, vectorizer, top_idx, by_submolt=False, max_docs=args.max_docs)
    lex_ts_sub = timeseries_for_terms(df, vectorizer, top_idx, by_submolt=args.by_submolt, max_docs=args.max_docs)

    # Hashtags + emojis
    tag_global = timeseries_for_tokens(df, extract_hashtags, "hashtag", by_submolt=False)
    tag_sub = timeseries_for_tokens(df, extract_hashtags, "hashtag", by_submolt=args.by_submolt)
    emoji_global = timeseries_for_tokens(df, extract_emojis, "emoji", by_submolt=False)
    emoji_sub = timeseries_for_tokens(df, extract_emojis, "emoji", by_submolt=args.by_submolt)

    # Ritual memes
    ritual_ts = build_ritual_memes(df) if args.ritual else pd.DataFrame()

    # Semantic memes
    semantic_ts = pd.DataFrame()
    semantic_labels = pd.DataFrame()
    if args.semantic:
        sem_df, labels_df = build_semantic_memes(
            df,
            n_clusters=args.semantic_clusters,
            sample_docs=args.semantic_sample_docs,
            max_features=args.semantic_max_features,
            use_dbscan=args.semantic_dbscan,
        )
        semantic_labels = labels_df
        grouped = sem_df.groupby(["hour", "semantic_cluster"], as_index=False).agg(
            count=("doc_id", "count"),
            unique_authors=("author_id", "nunique"),
        )
        grouped["meme"] = grouped["semantic_cluster"].apply(lambda x: f"semantic_{x}")
        grouped["meme_type"] = "semantic_cluster"
        grouped["scope"] = "global"
        grouped["submolt"] = None
        semantic_ts = grouped[["hour", "meme", "meme_type", "count", "unique_authors", "scope", "submolt"]]

    # Macro memes (submolts)
    macro = (
        df.groupby(["hour", "submolt"], as_index=False)
        .agg(count=("doc_id", "count"), unique_authors=("author_id", "nunique"))
        .rename(columns={"submolt": "meme"})
    )
    macro["meme_type"] = "submolt"
    macro["scope"] = "global"
    macro["submolt"] = macro["meme"]
    macro = macro[["hour", "meme", "meme_type", "count", "unique_authors", "scope", "submolt"]]

    # Combine timeseries
    timeseries = pd.concat(
        [
            lex_ts_global,
            lex_ts_sub,
            tag_global,
            tag_sub,
            emoji_global,
            emoji_sub,
            ritual_ts,
            semantic_ts,
            macro,
        ],
        ignore_index=True,
    )
    timeseries.to_parquet(out_dir / "meme_timeseries_hourly.parquet", index=False)

    # Meme candidates list (lexical + hashtag + emoji)
    candidates = pd.DataFrame(
        [
            {"meme": term, "meme_type": "ngram", "count": int(counts[i])}
            for i, term in zip(top_idx, top_terms)
        ]
    )
    if not candidates.empty:
        categories = candidates["meme"].apply(classify_candidate_meme)
        candidates["candidate_category"] = categories.apply(lambda x: x[0])
        candidates["boilerplate_score"] = categories.apply(lambda x: x[1])
        candidates["boilerplate_reasons"] = categories.apply(lambda x: x[2])
    candidates.to_csv(out_dir / "meme_candidates.csv", index=False)
    # Double ranking for auditability: technical boilerplate vs cultural candidates.
    if not candidates.empty:
        cultural = candidates[candidates["candidate_category"] == "cultural_candidate"].copy()
        technical = candidates[candidates["candidate_category"] != "cultural_candidate"].copy()
        cultural.sort_values(["count", "boilerplate_score"], ascending=[False, True]).to_csv(
            out_dir / "meme_candidates_cultural.csv", index=False
        )
        technical.sort_values(["boilerplate_score", "count"], ascending=[False, False]).to_csv(
            out_dir / "meme_candidates_technical.csv", index=False
        )
    if not semantic_labels.empty:
        semantic_labels.to_csv(out_dir / "semantic_clusters.csv", index=False)

    # Bursts on global lexical memes
    bursts_rows = []
    burst_score_by_meme: Dict[str, float] = defaultdict(float)
    if not lex_ts_global.empty:
        lex_ts_global["hour"] = pd.to_datetime(lex_ts_global["hour"], utc=True)
        for meme, g in lex_ts_global.groupby("meme"):
            series = g.sort_values("hour")
            counts_list = series["count"].astype(int).tolist()
            bursts = kleinberg_bursts(counts_list, s=args.burst_s, gamma=args.burst_gamma)
            for start, end, level in bursts:
                # Burst score proxy: integrate level over duration (hours).
                duration = max(1, int(end - start + 1))
                burst_score_by_meme[meme] += float(level * duration)
                bursts_rows.append(
                    {
                        "meme": meme,
                        "meme_type": "ngram",
                        "burst_level": level,
                        "start_hour": str(series["hour"].iloc[start]),
                        "end_hour": str(series["hour"].iloc[end]),
                    }
                )
    pd.DataFrame(bursts_rows).to_csv(out_dir / "meme_bursts.csv", index=False)

    # Survival and entropy
    metrics_rows = []
    if not lex_ts_global.empty:
        for meme, g in lex_ts_global.groupby("meme"):
            series = g.sort_values("hour")
            lifetime = (series["hour"].iloc[-1] - series["hour"].iloc[0]).total_seconds() / 3600.0
            # submolt entropy
            sub_counts = lex_ts_sub[lex_ts_sub["meme"] == meme].groupby("submolt")["count"].sum().tolist()
            ent = entropy(sub_counts)
            metrics_rows.append(
                {
                    "meme": meme,
                    "meme_type": "ngram",
                    "lifetime_hours": lifetime,
                    "submolt_entropy": ent,
                    "submolts_touched": len(sub_counts),
                    "burst_score": burst_score_by_meme.get(meme, 0.0),
                }
            )
    metrics_df = pd.DataFrame(metrics_rows)
    classified = classify_memes(metrics_df)
    classified.to_csv(out_dir / "meme_classification.csv", index=False)
    metrics_df.to_csv(out_dir / "meme_survival.csv", index=False)

    if args.hawkes and not lex_ts_global.empty:
        hawkes_df = compute_hawkes_metrics(lex_ts_global, max_memes=args.hawkes_max_memes)
        hawkes_df.to_csv(out_dir / "meme_hawkes.csv", index=False)

    if args.sir and not lex_ts_global.empty:
        sir_df = compute_sir_proxy(df, vectorizer, top_idx, max_memes=args.sir_max_memes)
        sir_df.to_csv(out_dir / "meme_sir.csv", index=False)

    compute_survival_curves(metrics_df, out_dir)

    print(f"Memetic outputs written to {out_dir}")


if __name__ == "__main__":
    main()
