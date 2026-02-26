from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

from .embeddings import EmbeddingBackend, cosine_sim

ILLOCUTION_LABELS = [
    "ASSERTIVE",
    "DIRECTIVE",
    "COMMISSIVE",
    "EXPRESSIVE",
    "DECLARATIVE",
    "OTHER",
]

PROTOTYPE_PROMPTS = {
    "ASSERTIVE": ["I state a fact", "this is true", "evidence shows"],
    "DIRECTIVE": ["please do this", "you should", "I ask you to"],
    "COMMISSIVE": ["I promise", "I will do", "we commit"],
    "EXPRESSIVE": ["I feel", "I am happy", "this hurts", "wow amazing"],
    "DECLARATIVE": ["I declare", "we announce", "it is officially"],
    "OTHER": ["random short text", "symbolic expression", "mixed utterance"],
}

PRAG_DIMS = [
    "certainty",
    "affect_valence",
    "dominance",
    "politeness",
    "irony",
    "coordination_intent",
]

# High/low anchors for directional scoring with embedding similarity.
ANCHORS = {
    "certainty": {
        "high": ["this is certain", "without doubt", "definitely true"],
        "low": ["maybe", "not sure", "uncertain"],
    },
    "affect_valence": {
        "high": ["great", "love this", "happy", "thank you"],
        "low": ["terrible", "hate this", "awful", "angry"],
    },
    "dominance": {
        "high": ["listen to me", "I command", "you must obey"],
        "low": ["I suggest", "if you want", "up to you"],
    },
    "politeness": {
        "high": ["please", "thank you", "would you kindly"],
        "low": ["shut up", "idiot", "nonsense"],
    },
    "irony": {
        "high": ["yeah right", "sure genius", "totally not"],
        "low": ["literally", "plainly", "directly"],
    },
    "coordination_intent": {
        "high": ["let us coordinate", "next steps", "we should organize"],
        "low": ["look at me", "identity flex", "just performance"],
    },
}


@dataclass
class ScoringConfig:
    seed: int = 42
    optional_llm: bool = False
    llm_cache_path: str | None = None


class OfflineBaselineScorer:
    def __init__(self, backend: EmbeddingBackend, config: ScoringConfig | None = None):
        self.backend = backend
        self.config = config or ScoringConfig()
        self._prepared = False

    def prepare(self) -> None:
        prompts: List[str] = []
        self._label_offsets: Dict[str, tuple[int, int]] = {}
        for label in ILLOCUTION_LABELS:
            start = len(prompts)
            prompts.extend(PROTOTYPE_PROMPTS[label])
            self._label_offsets[label] = (start, len(prompts))

        self._anchor_offsets: Dict[str, Dict[str, tuple[int, int]]] = {}
        for dim in PRAG_DIMS:
            self._anchor_offsets[dim] = {}
            for pole in ("high", "low"):
                start = len(prompts)
                prompts.extend(ANCHORS[dim][pole])
                self._anchor_offsets[dim][pole] = (start, len(prompts))

        self._prompt_vectors = self.backend.encode(prompts)
        self._prepared = True

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def score(self, messages: Sequence[Dict], embeddings: np.ndarray) -> List[Dict]:
        if not self._prepared:
            self.prepare()

        sims = cosine_sim(embeddings, self._prompt_vectors)
        scored: List[Dict] = []

        for i, msg in enumerate(messages):
            row = sims[i]

            # Illocution via prototype max-average similarity.
            label_scores: Dict[str, float] = {}
            for label in ILLOCUTION_LABELS:
                s, e = self._label_offsets[label]
                label_scores[label] = float(np.mean(row[s:e]))
            best_label = max(label_scores, key=label_scores.get)
            probs = self._softmax(np.array([label_scores[l] for l in ILLOCUTION_LABELS]))
            confidence = float(np.max(probs))

            prag_scores: Dict[str, float] = {}
            prag_conf: Dict[str, float] = {}
            for dim in PRAG_DIMS:
                hs, he = self._anchor_offsets[dim]["high"]
                ls, le = self._anchor_offsets[dim]["low"]
                hi = float(np.mean(row[hs:he]))
                lo = float(np.mean(row[ls:le]))
                raw = hi - lo
                score = float(self._sigmoid(np.array([raw * 5.0]))[0])
                conf = float(min(1.0, abs(raw) * 3.0))
                prag_scores[dim] = self._clip01(score)
                prag_conf[dim] = self._clip01(conf)

            scored.append(
                {
                    "illocution": {
                        "label": best_label,
                        "confidence": self._clip01(confidence),
                        "distribution": {lbl: float(probs[j]) for j, lbl in enumerate(ILLOCUTION_LABELS)},
                    },
                    "pragmatic_scores": prag_scores,
                    "pragmatic_confidence": prag_conf,
                }
            )
        return scored

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        z = x - np.max(x)
        e = np.exp(z)
        return e / np.sum(e)

    @staticmethod
    def _clip01(v: float) -> float:
        return float(max(0.0, min(1.0, v)))


class OptionalLLMScorer:
    """Optional backend with file cache. Disabled unless explicitly requested."""

    def __init__(self, cache_path: str):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        else:
            self.cache = {}

    def score(self, message: Dict) -> Dict:
        # Stub to keep reproducible offline default. External call intentionally omitted.
        key = hashlib.sha256(message.get("locution", {}).get("cleaned_text", "").encode("utf-8")).hexdigest()
        if key in self.cache:
            return self.cache[key]
        out = {
            "illocution": {"label": "OTHER", "confidence": 0.2, "distribution": {lbl: 1.0 / len(ILLOCUTION_LABELS) for lbl in ILLOCUTION_LABELS}},
            "pragmatic_scores": {k: 0.5 for k in PRAG_DIMS},
            "pragmatic_confidence": {k: 0.1 for k in PRAG_DIMS},
        }
        self.cache[key] = out
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return out


def select_scorer(backend_name: str, embedding_backend: EmbeddingBackend, seed: int = 42):
    key = (backend_name or "offline_baseline").lower()
    if key == "offline_baseline":
        return OfflineBaselineScorer(embedding_backend, ScoringConfig(seed=seed))
    if key == "optional_llm":
        raise ValueError("optional_llm requires explicit integration; use offline_baseline by default.")
    raise ValueError(f"Unknown scoring backend: {backend_name}")
