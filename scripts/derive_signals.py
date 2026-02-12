#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.text import clean_text, tokenize, detect_language  # noqa: E402
from moltbook_analysis.analyze.language_ontology import (  # noqa: E402
    language_signals,
    script_profile,
)
from moltbook_analysis.analyze.interference import interference_score  # noqa: E402
from moltbook_analysis.analyze.incidence import human_incidence_score  # noqa: E402
from moltbook_analysis.storage import write_jsonl, write_parquet  # noqa: E402


SKIP_LANG_DETECT = False


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def safe_get(d: Dict[str, Any] | None, *keys: str) -> Any:
    cur: Any = d or {}
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def basic_text_features(text: str) -> Dict[str, float]:
    tokens = tokenize(clean_text(text))
    token_count = len(tokens)
    unique_tokens = len(set(tokens))
    char_count = len(text)
    alpha_count = sum(1 for c in text if c.isalpha())
    upper_count = sum(1 for c in text if c.isupper())
    digit_count = sum(1 for c in text if c.isdigit())
    question_marks = text.count("?")
    exclamation_marks = text.count("!")
    ellipsis = text.count("...")
    return {
        "char_count": float(char_count),
        "token_count": float(token_count),
        "unique_token_ratio": float(unique_tokens / token_count) if token_count else 0.0,
        "alpha_ratio": float(alpha_count / char_count) if char_count else 0.0,
        "upper_ratio": float(upper_count / alpha_count) if alpha_count else 0.0,
        "digit_ratio": float(digit_count / char_count) if char_count else 0.0,
        "question_marks": float(question_marks),
        "exclamation_marks": float(exclamation_marks),
        "ellipsis": float(ellipsis),
    }


def detect_lang(text: str, min_len: int = 20) -> str | None:
    if SKIP_LANG_DETECT:
        return None
    if len(text.strip()) < min_len:
        return None
    return detect_language(text)


def compute_text_features(text: str) -> Dict[str, float | int | str | None]:
    features: Dict[str, float | int | str | None] = {}
    features.update(basic_text_features(text))

    lang = detect_lang(text)
    features["lang"] = lang
    features["lang_is_english"] = int(lang == "en") if lang else 0

    features.update(script_profile(text))

    inf = interference_score(text)
    features["interference_score"] = float(inf.get("score", 0.0))
    features["interference_injection_hits"] = float(inf.get("injection_hits", 0))
    features["interference_disclaimer_hits"] = float(inf.get("disclaimer_hits", 0))
    features["interference_code_fences"] = float(inf.get("code_fences", 0))
    features["interference_urls"] = float(inf.get("urls", 0))
    features["interference_emojis"] = float(inf.get("emojis", 0))

    features.update(human_incidence_score(text))
    features.update(language_signals(text))
    return features


def build_post_rows(posts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for post in posts:
        title = post.get("title") or ""
        content = post.get("content") or ""
        text = f"{title}\n{content}".strip()
        author = post.get("author") or {}
        submolt = post.get("submolt") or {}
        row: Dict[str, Any] = {
            "doc_id": post.get("id"),
            "doc_type": "post",
            "post_id": post.get("id"),
            "title": title,
            "text": text,
            "author_id": safe_get(author, "id"),
            "author_name": safe_get(author, "name"),
            "author_karma": safe_get(author, "karma"),
            "author_followers": safe_get(author, "follower_count"),
            "author_following": safe_get(author, "following_count"),
            "author_has_x_handle": int(bool(safe_get(author, "owner", "x_handle"))),
            "submolt": safe_get(submolt, "name"),
            "submolt_display": safe_get(submolt, "display_name"),
            "created_at": post.get("created_at"),
            "upvotes": post.get("upvotes"),
            "downvotes": post.get("downvotes"),
            "comment_count": post.get("comment_count"),
            "url": post.get("url"),
            "scrape_ts": post.get("_scrape_ts"),
            "run_id": post.get("_run_id"),
        }
        row.update(compute_text_features(text))
        rows.append(row)
    return rows


def build_comment_rows(comments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for comment in comments:
        content = comment.get("content") or ""
        text = content.strip()
        author = comment.get("author") or {}
        row: Dict[str, Any] = {
            "doc_id": comment.get("id"),
            "doc_type": "comment",
            "post_id": comment.get("post_id"),
            "parent_id": comment.get("parent_id"),
            "thread_path": comment.get("thread_path"),
            "depth": comment.get("depth"),
            "text": text,
            "author_id": comment.get("author_id"),
            "author_name": safe_get(author, "name"),
            "author_karma": safe_get(author, "karma"),
            "author_followers": safe_get(author, "follower_count"),
            "created_at": comment.get("created_at"),
            "upvotes": comment.get("upvotes"),
            "downvotes": comment.get("downvotes"),
            "scrape_ts": comment.get("_scrape_ts"),
            "run_id": comment.get("_run_id"),
        }
        row.update(compute_text_features(text))
        rows.append(row)
    return rows


def compute_matches(
    rows: List[Dict[str, Any]],
    top_k: int = 5,
    max_features: int = 5000,
    match_same_lang: bool = False,
) -> List[Dict[str, Any]]:
    if len(rows) < 2 or top_k <= 0 or max_features <= 0:
        return []

    texts = [clean_text(r.get("text") or "") for r in rows]
    ids = [r.get("doc_id") for r in rows]
    langs = [r.get("lang") for r in rows]

    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
    )
    X = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    n_neighbors = min(top_k + 1, len(rows))
    nn = NearestNeighbors(metric="cosine", n_neighbors=n_neighbors)
    nn.fit(X)
    distances, indices = nn.kneighbors(X)

    def top_terms_for_row(row_idx: int, top_n: int = 8) -> List[str]:
        vec = X[row_idx].toarray().ravel()
        if vec.sum() == 0:
            return []
        top_idx = vec.argsort()[-top_n:][::-1]
        return [feature_names[i] for i in top_idx if vec[i] > 0]

    top_terms = [top_terms_for_row(i) for i in range(len(rows))]
    matches: List[Dict[str, Any]] = []

    for i, neigh in enumerate(indices):
        src_id = ids[i]
        src_lang = langs[i]
        for j_idx, dist in zip(neigh[1:], distances[i][1:]):
            tgt_id = ids[j_idx]
            tgt_lang = langs[j_idx]
            if match_same_lang and src_lang and tgt_lang and src_lang != tgt_lang:
                continue
            shared = sorted(set(top_terms[i]).intersection(top_terms[j_idx]))
            matches.append(
                {
                    "doc_id": src_id,
                    "neighbor_id": tgt_id,
                    "score": float(1.0 - dist),
                    "doc_lang": src_lang,
                    "neighbor_lang": tgt_lang,
                    "shared_terms": ", ".join(shared[:8]),
                }
            )
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive interpretables and vector space matches.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-dir", default="data/derived")
    parser.add_argument("--match-top-k", type=int, default=5)
    parser.add_argument("--match-max-features", type=int, default=5000)
    parser.add_argument("--match-same-lang", action="store_true")
    parser.add_argument("--skip-lang-detect", action="store_true")
    args = parser.parse_args()

    global SKIP_LANG_DETECT
    SKIP_LANG_DETECT = bool(args.skip_lang_detect)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    posts = read_jsonl(Path(args.posts))
    comments = read_jsonl(Path(args.comments))

    post_rows = build_post_rows(posts)
    comment_rows = build_comment_rows(comments)

    if post_rows:
        write_jsonl(out_dir / "signals_posts.jsonl", post_rows)
        write_parquet(out_dir / "signals_posts.parquet", post_rows)
    if comment_rows:
        write_jsonl(out_dir / "signals_comments.jsonl", comment_rows)
        write_parquet(out_dir / "signals_comments.parquet", comment_rows)

    if post_rows and args.match_top_k > 0 and args.match_max_features > 0:
        df = pd.DataFrame(post_rows)
        lang_counts = (
            df["lang"]
            .fillna("unknown")
            .value_counts()
            .rename_axis("lang")
            .reset_index(name="count")
        )
        lang_counts.to_csv(out_dir / "lang_distribution.csv", index=False)

        matches = compute_matches(
            post_rows,
            top_k=args.match_top_k,
            max_features=args.match_max_features,
            match_same_lang=args.match_same_lang,
        )
        if matches:
            pd.DataFrame(matches).to_csv(out_dir / "matches.csv", index=False)

    print(f"Signals written to {out_dir}")


if __name__ == "__main__":
    main()
