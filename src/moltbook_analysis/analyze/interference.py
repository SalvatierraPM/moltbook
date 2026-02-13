from __future__ import annotations

import re
from typing import Dict, Iterable, List

from moltbook_analysis.analyze.text import clean_text


INJECTION_PATTERNS = [
    r"ignore (all|previous|earlier) (instructions|prompts)",
    r"system prompt",
    r"developer message",
    r"you are (an|a) (assistant|model|ai)",
    r"act as",
    r"do anything now",
    r"jailbreak",
    r"### instruction",
    r"begin (system|developer|assistant)",
    r"end (system|developer|assistant)",
]

LLM_DISCLAIMERS = [
    r"as an ai",
    r"as a language model",
    r"i (cannot|can't) (provide|comply|access)",
    r"i don't have (access|ability)",
]

CODE_FENCE_RE = re.compile(r"```", re.MULTILINE)
URL_RE = re.compile(r"https?://\S+|www\.\S+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")

BASE64_RE = re.compile(r"base64,[A-Za-z0-9+/=]{120,}", re.IGNORECASE)
REPEAT_RE = re.compile(r"(.)\1{20,}")
ALNUM_RUN_RE = re.compile(r"[A-Za-z0-9+/=]{240,}")


def _count_patterns(text: str, patterns: List[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, flags=re.IGNORECASE))

def noise_score(text: str) -> float:
    """
    Heuristic noise score to separate format/spam artifacts (base64, repetition) from semantic interference.
    Returns a small non-negative score; higher implies more likely non-semantic noise.
    """
    if not text:
        return 0.0
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return 0.0

    score = 0.0
    if REPEAT_RE.search(compact):
        score += 1.0
    if BASE64_RE.search(text):
        score += 2.0
    if ALNUM_RUN_RE.search(compact):
        score += 1.0

    if len(compact) >= 60:
        unique_ratio = len(set(compact.lower())) / len(compact)
        if unique_ratio < 0.12:
            score += 1.0
    return float(score)


def interference_score(text: str) -> Dict[str, float]:
    t = clean_text(text)
    if not t:
        return {
            "score": 0.0,
            "score_semantic": 0.0,
            "score_format": 0.0,
            "noise_score": 0.0,
            "injection_hits": 0,
            "disclaimer_hits": 0,
        }

    inj = _count_patterns(t, INJECTION_PATTERNS)
    dis = _count_patterns(t, LLM_DISCLAIMERS)

    code_blocks = len(CODE_FENCE_RE.findall(text))
    urls = len(URL_RE.findall(text))
    emojis = len(EMOJI_RE.findall(text))

    semantic = inj * 2.0 + dis * 1.5
    fmt = code_blocks * 0.5 + urls * 0.3 + 0.1 * emojis
    nscore = noise_score(text)
    score = float(semantic + fmt)

    return {
        "score": float(score),
        "score_semantic": float(semantic),
        "score_format": float(fmt),
        "noise_score": float(nscore),
        "injection_hits": int(inj),
        "disclaimer_hits": int(dis),
        "code_fences": int(code_blocks),
        "urls": int(urls),
        "emojis": int(emojis),
    }


def rank_interference(texts: Iterable[str], top_n: int = 50) -> List[Dict[str, float]]:
    scored = []
    for text in texts:
        scored.append(interference_score(text))
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]
