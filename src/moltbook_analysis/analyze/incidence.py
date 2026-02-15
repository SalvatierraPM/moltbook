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

# NOTE: This is not "human-authorship detection". It's a lightweight proxy for
# "situated / IRL-style" language that often appears when humans intervene or
# when agents report on human context. It is noisy by design and should be used
# as a ranking signal + label, not as proof.
NARRATIVE_PATTERNS = [
    # EN: personal experience / time markers
    r"\b(i (went|saw|felt|tried|worked|met|spent|learned|woke|slept))\b",
    r"\b(my (friend|family|mom|dad|wife|husband|girlfriend|boyfriend|kids?|job))\b",
    r"\b(today|yesterday|tomorrow|last night|this morning)\b",
    # ES: experiencia personal + marcadores temporales (sin tildes: normalize_text)
    r"\b(yo (fui|vi|senti|intente|trabaje|conoci|pase|aprendi|desperte|dormi))\b",
    r"\b(mi (amigo|amiga|familia|mama|papa|esposa|esposo|novio|novia|hijo|hija|trabajo))\b",
    r"\b(hoy|ayer|manana|anoche|esta manana)\b",
    # PT: experiencia personal + tempo
    r"\b(eu (fui|vi|senti|tentei|trabalhei|conheci|passei|aprendi|acordei|dormi))\b",
    r"\b(meu|minha (amigo|amiga|familia|mae|pai|esposa|marido|namorado|namorada|filho|filha|trabalho))\b",
    r"\b(hoje|ontem|amanha|ontem a noite|esta manha)\b",
]


def human_incidence_score(text: str) -> Dict[str, float]:
    t = normalize_text(text)
    human = _count_patterns(t, HUMAN_PATTERNS)
    prompt = _count_patterns(t, PROMPT_PATTERNS)
    tooling = _count_patterns(t, TOOLING_PATTERNS)
    narrative = _count_patterns(t, NARRATIVE_PATTERNS)

    # Decompose the score to reduce "tooling dominates everything" failure modes.
    # The public UI should show these components explicitly.
    score_human = human * 2.5
    score_prompt = prompt * 1.5
    score_narrative = narrative * 0.9
    score_tooling = tooling * 0.15
    score = score_human + score_prompt + score_narrative + score_tooling

    # Evidence type is a coarse label for interpretation (not ground truth).
    if human >= 1:
        evidence_type = "humano_explicito"
    elif narrative >= 2 and tooling <= 2 and prompt == 0:
        evidence_type = "narrativa"
    elif prompt >= 2 and tooling >= 2:
        evidence_type = "prompt_tooling"
    elif prompt >= 2:
        evidence_type = "prompt"
    elif tooling >= 6 and narrative == 0:
        evidence_type = "tooling"
    else:
        evidence_type = "mixto"

    return {
        "human_incidence_score": float(score),
        "score_human": float(score_human),
        "score_prompt": float(score_prompt),
        "score_narrative": float(score_narrative),
        "score_tooling": float(score_tooling),
        "human_refs": float(human),
        "prompt_refs": float(prompt),
        "tooling_refs": float(tooling),
        "narrative_refs": float(narrative),
        "evidence_type": evidence_type,
    }
