#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import networkx as nx


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


def load_posts(posts_path: Path) -> pd.DataFrame:
    rows: List[dict] = []
    for p in iter_jsonl(posts_path):
        author = p.get("author") or {}
        text = ((p.get("title") or "") + "\n" + (p.get("content") or "")).strip()
        rows.append(
            {
                "post_id": p.get("id"),
                "author_id": author.get("id"),
                "author_name": author.get("name"),
                "submolt": safe_submolt_name(p),
                "upvotes": p.get("upvotes"),
                "comment_count": p.get("comment_count"),
                "created_at": p.get("created_at"),
                "text_len": len(text),
            }
        )
    return pd.DataFrame(rows)


def load_comments(comments_path: Path, post_submolt: Dict[str, str]) -> pd.DataFrame:
    rows: List[dict] = []
    for c in iter_jsonl(comments_path):
        author = c.get("author") or {}
        content = (c.get("content") or "").strip()
        post_id = c.get("post_id")
        rows.append(
            {
                "comment_id": c.get("id"),
                "post_id": post_id,
                "author_id": c.get("author_id") or author.get("id"),
                "author_name": author.get("name"),
                "parent_id": c.get("parent_id"),
                "created_at": c.get("created_at"),
                "text_len": len(content),
                "submolt": post_submolt.get(post_id),
            }
        )
    return pd.DataFrame(rows)


def load_edges(path: Path, src_col: str, tgt_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=[src_col, tgt_col, "weight"])
    df = pd.read_csv(path)
    if src_col not in df.columns or tgt_col not in df.columns:
        return pd.DataFrame(columns=[src_col, tgt_col, "weight"])
    df = df[[src_col, tgt_col]].dropna()
    df["weight"] = 1
    agg = df.groupby([src_col, tgt_col], as_index=False)["weight"].sum()
    return agg


def build_graph(edges: pd.DataFrame, src_col: str, tgt_col: str, min_weight: int) -> nx.DiGraph:
    G = nx.DiGraph()
    if edges.empty:
        return G
    filtered = edges[edges["weight"] >= min_weight]
    for _, row in filtered.iterrows():
        G.add_edge(str(row[src_col]), str(row[tgt_col]), weight=float(row["weight"]))
    return G


def compute_graph_metrics(
    G: nx.DiGraph,
    out_dir: Path,
    name: str,
    betweenness_k: int,
    community_max_nodes: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if G.number_of_nodes() == 0:
        return

    in_deg = dict(G.in_degree(weight="weight"))
    out_deg = dict(G.out_degree(weight="weight"))
    pagerank = nx.pagerank(G, weight="weight")

    if betweenness_k > 0:
        k = min(betweenness_k, G.number_of_nodes())
        betw = nx.betweenness_centrality(G, k=k, weight="weight", seed=42)
    else:
        betw = {n: 0.0 for n in G.nodes()}

    metrics_rows = []
    for n in G.nodes():
        metrics_rows.append(
            {
                "node": n,
                "in_degree": in_deg.get(n, 0.0),
                "out_degree": out_deg.get(n, 0.0),
                "pagerank": pagerank.get(n, 0.0),
                "betweenness": betw.get(n, 0.0),
            }
        )
    pd.DataFrame(metrics_rows).to_csv(out_dir / f"{name}_centrality.csv", index=False)

    # Communities on top nodes only (avoid huge graphs)
    nodes_sorted = sorted(G.nodes(), key=lambda n: (in_deg.get(n, 0.0) + out_deg.get(n, 0.0)), reverse=True)
    if community_max_nodes > 0:
        nodes_subset = set(nodes_sorted[:community_max_nodes])
        H = G.subgraph(nodes_subset).to_undirected()
    else:
        H = G.to_undirected()

    communities = []
    if H.number_of_nodes() > 0:
        import networkx.algorithms.community as nx_comm

        comms = list(nx_comm.greedy_modularity_communities(H))
        for idx, c in enumerate(comms):
            for node in c:
                communities.append({"node": node, "community": idx})
    pd.DataFrame(communities).to_csv(out_dir / f"{name}_communities.csv", index=False)

    summary = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "reciprocity": nx.reciprocity(G),
    }
    (out_dir / f"{name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantitative sociology metrics for Moltbook.")
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--edges-replies", default="data/derived/edges_replies.csv")
    parser.add_argument("--edges-mentions", default="data/derived/edges_mentions.csv")
    parser.add_argument("--out-dir", default="data/derived")
    parser.add_argument("--min-edge-weight", type=int, default=1)
    parser.add_argument("--betweenness-k", type=int, default=200)
    parser.add_argument("--community-max-nodes", type=int, default=5000)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    posts_df = load_posts(Path(args.posts))
    post_submolt = {
        row["post_id"]: row["submolt"]
        for _, row in posts_df.dropna(subset=["post_id"]).iterrows()
        if row.get("post_id") is not None
    }
    comments_df = load_comments(Path(args.comments), post_submolt)

    # Submolt stats
    submolt_posts = (
        posts_df.groupby("submolt", dropna=False)
        .agg(posts=("post_id", "nunique"), post_authors=("author_id", "nunique"), mean_upvotes=("upvotes", "mean"))
        .reset_index()
    )
    submolt_comments = (
        comments_df.groupby("submolt", dropna=False)
        .agg(comments=("comment_id", "nunique"), comment_authors=("author_id", "nunique"))
        .reset_index()
    )
    submolt_stats = pd.merge(submolt_posts, submolt_comments, on="submolt", how="outer").fillna(0)
    submolt_stats.to_csv(out_dir / "submolt_stats.csv", index=False)

    # Author stats
    author_posts = (
        posts_df.groupby("author_id", dropna=False)
        .agg(posts=("post_id", "nunique"), post_submolts=("submolt", "nunique"))
        .reset_index()
    )
    author_comments = (
        comments_df.groupby("author_id", dropna=False)
        .agg(comments=("comment_id", "nunique"), comment_submolts=("submolt", "nunique"))
        .reset_index()
    )
    author_stats = pd.merge(author_posts, author_comments, on="author_id", how="outer").fillna(0)
    author_stats.to_csv(out_dir / "author_stats.csv", index=False)

    # Interaction graphs
    reply_edges = load_edges(Path(args.edges_replies), "author_id", "parent_author_id")
    reply_graph = build_graph(reply_edges, "author_id", "parent_author_id", args.min_edge_weight)
    compute_graph_metrics(reply_graph, out_dir, "reply_graph", args.betweenness_k, args.community_max_nodes)

    mention_edges = load_edges(Path(args.edges_mentions), "author_name", "target")
    mention_graph = build_graph(mention_edges, "author_name", "target", args.min_edge_weight)
    compute_graph_metrics(mention_graph, out_dir, "mention_graph", args.betweenness_k, args.community_max_nodes)

    print(f"Metrics written to {out_dir}")


if __name__ == "__main__":
    main()
