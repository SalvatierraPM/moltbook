from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return x / norms


class EmbeddingBackend(ABC):
    name: str

    @abstractmethod
    def fit(self, texts: Sequence[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError


class TfidfEmbeddingBackend(EmbeddingBackend):
    name = "tfidf"

    def __init__(self, max_features: int = 8000, ngram_range: tuple[int, int] = (1, 2), min_df: int = 5) -> None:
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=min_df,
            norm="l2",
            dtype=np.float32,
        )
        self._fitted = False

    def fit(self, texts: Sequence[str]) -> None:
        if not texts:
            texts = ["empty"]
        self.vectorizer.fit(texts)
        self._fitted = True

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not self._fitted:
            self.fit(texts)
        # Return sparse CSR to avoid OOM on large corpora.
        return self.vectorizer.transform(texts)


class SentenceTransformersEmbeddingBackend(EmbeddingBackend):
    name = "sentence_transformers"

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(model_name)

    def fit(self, texts: Sequence[str]) -> None:
        # No-op; encoder is pretrained.
        return None

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        vecs = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


def create_embedding_backend(name: str = "sentence_transformers") -> EmbeddingBackend:
    key = (name or "").lower()
    if key in {"sentence_transformers", "sbert", "st"}:
        try:
            return SentenceTransformersEmbeddingBackend()
        except Exception as exc:
            warnings.warn(
                f"sentence-transformers unavailable ({exc}); falling back to TF-IDF embeddings.",
                RuntimeWarning,
            )
            return TfidfEmbeddingBackend()
    if key in {"tfidf", "offline"}:
        return TfidfEmbeddingBackend()
    raise ValueError(f"Unknown embedding backend: {name}")


def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Supports dense/sparse; returns dense similarity matrix.
    return cosine_similarity(a, b, dense_output=True)
