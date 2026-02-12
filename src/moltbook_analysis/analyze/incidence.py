from __future__ import annotations

import re
from typing import Dict, Iterable

from moltbook_analysis.analyze.language_ontology import normalize_text


def _count_patterns(text: str, patterns: Iterable[str]) -> int:
    return sum(len(re.findall(p, text)) for p in patterns)


HUMAN_PATTERNS = [
    r"\b(as a human|i am human|soy humano|persona)\b",
    r"\b(my human|mi humano|my creator|mi creador|mi creadora)\b",
    r"\b(user asked|the user|el usuario|la usuaria)\b",
    r"\b(operator|owner|propietario|propietaria)\b",
    r"\b(irl|in real life|vida real)\b",
]

PROMPT_PATTERNS = [
    r"\b(prompt|system prompt|developer message|instruction|instruccion|policy|jailbreak)\b",
    r"\b(as per the prompt|segun el prompt|segun instrucciones)\b",
    r"\b(user requested|usuario pidio|me pidieron)\b",
]

TOOLING_PATTERNS = [
    r"\b(api|endpoint|curl|http|token|auth|authentication|headers)\b",
    r"\b(script|pipeline|dataset|vector space|embedding)\b",
]


def human_incidence_score(text: str) -> Dict[str, float]:
    t = normalize_text(text)
    human = _count_patterns(t, HUMAN_PATTERNS)
    prompt = _count_patterns(t, PROMPT_PATTERNS)
    tooling = _count_patterns(t, TOOLING_PATTERNS)

    score = human * 2.0 + prompt * 1.5 + tooling * 0.5
    return {
        "human_incidence_score": float(score),
        "human_refs": float(human),
        "prompt_refs": float(prompt),
        "tooling_refs": float(tooling),
    }
