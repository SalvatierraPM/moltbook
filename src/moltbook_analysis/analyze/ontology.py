from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd
import networkx as nx
from sklearn.feature_extraction.text import CountVectorizer

from moltbook_analysis.analyze.text import clean_text


def build_cooccurrence_graph(
    texts: List[str],
    max_features: int = 200,
    min_df: int = 5,
) -> nx.Graph:
    clean = [clean_text(t) for t in texts if t]
    if not clean:
        return nx.Graph()

    vectorizer = CountVectorizer(
        max_features=max_features,
        min_df=min_df,
        ngram_range=(1, 2),
        stop_words="english",
    )
    X = vectorizer.fit_transform(clean)
    terms = vectorizer.get_feature_names_out()

    # Co-occurrence matrix
    cooc = (X.T @ X).toarray().astype(float)
    np.fill_diagonal(cooc, 0)

    G = nx.Graph()
    for i, term in enumerate(terms):
        G.add_node(term)
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            weight = cooc[i, j]
            if weight > 0:
                G.add_edge(terms[i], terms[j], weight=weight)
    return G


def top_concepts(G: nx.Graph, top_n: int = 20) -> pd.DataFrame:
    if G.number_of_nodes() == 0:
        return pd.DataFrame(columns=["term", "degree"])
    degrees = sorted(G.degree(weight="weight"), key=lambda x: x[1], reverse=True)
    return pd.DataFrame(degrees[:top_n], columns=["term", "degree"])


def communities(G: nx.Graph) -> List[Tuple[str, int]]:
    if G.number_of_nodes() == 0:
        return []
    # Simple greedy modularity
    import networkx.algorithms.community as nx_comm

    comms = list(nx_comm.greedy_modularity_communities(G))
    out = []
    for idx, c in enumerate(comms):
        for term in c:
            out.append((term, idx))
    return out
