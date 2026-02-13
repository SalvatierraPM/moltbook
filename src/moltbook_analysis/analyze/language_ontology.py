from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable


def normalize_text(text: str) -> str:
    lowered = text.lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _count_patterns(text: str, patterns: Iterable[str]) -> int:
    return sum(len(re.findall(p, text)) for p in patterns)


SPEECH_ACT_PATTERNS: Dict[str, Iterable[str]] = {
    "request": [
        r"\b(can you|could you|would you|please|plz|por favor|podrias|puedes|quisiera|necesito|necesitamos|me gustaria|ayudame|ayuden|request)\b",
    ],
    "offer": [
        # Avoid overly-generic triggers like "puedo"/"podría" (often appear in requests).
        r"\b(happy to|me ofrezco|ofrezco|puedo ayudar|puedo hacerlo|puedo encargarme)\b",
        r"\b(i can help|i can do|i can run|i can build|i can take care)\b",
    ],
    "promise": [
        r"\b(i will|i'll|we will|we'll|prometo|me comprometo|voy a|vamos a|hare|haremos)\b",
    ],
    "declaration": [
        r"\b(i declare|declaro|announce|anuncio|proclamo|decreto|nombro|designo|queda)\b",
    ],
    "judgment": [
        r"\b(i think|i believe|i feel|creo que|pienso que|me parece|opino|imo|imho|should|must|deberia|debe|es mejor|es peor|good|bad|mejor|peor)\b",
    ],
    "assertion": [
        # NOTE: assertion is handled as the default when no other act is detected.
    ],
    "acceptance": [
        r"\b(ok|okay|deal|accepted|acepto|vale|de acuerdo|sounds good|yes|yep)\b",
        # Spanish "si/sí" is ambiguous (also conditional). Count only when it looks like an explicit "yes":
        r"(?:(?:^|\\s)si(?:\\s*[!.?,;:]|$))",
    ],
    "rejection": [
        r"\b(nope|cannot|can't|wont|won't|decline|rechazo|no puedo|no quiero|imposible)\b",
    ],
    "clarification": [
        r"\b(what do you mean|clarify|can you explain|explain|no entiendo|que quieres decir|aclara|clarifica)\b",
    ],
}


DECLARATION_PATTERNS: Dict[str, Iterable[str]] = {
    "decl_yes": [r"\b(yes|si|ok|okay|acepto|accepted|vale)\b"],
    "decl_no": [r"\b(no|nope|rechazo|decline)\b"],
    "decl_ignorance": [r"\b(i dont know|idk|no se|not sure|no estoy seguro)\b"],
    "decl_gratitude": [r"\b(thanks|thank you|gracias|muchas gracias|appreciate|agradezco)\b"],
    "decl_forgiveness": [r"\b(forgive|forgiveness|perdon|lo siento|sorry)\b"],
    "decl_love": [r"\b(love you|te quiero|te amo)\b"],
    "decl_resignation": [r"\b(i resign|resigned|me rindo|da igual|whatever|ya fue)\b"],
}


MOOD_PATTERNS: Dict[str, Iterable[str]] = {
    "ambition": [r"\b(ambition|aspire|goal|plan|quiero|me gustaria|aspirar|meta|objetivo)\b"],
    "resignation": [r"\b(resign|resigned|me rindo|da igual|whatever|no importa|sin remedio)\b"],
    "resentment": [r"\b(resent|unfair|injusto|me molesta|odio|hate|resentimiento)\b"],
    "gratitude": [r"\b(thanks|gracias|appreciate|agradezco)\b"],
    "wonder": [r"\b(wonder|asombro|wow|amazing|maravilla|increible)\b"],
    "fear": [r"\b(fear|afraid|miedo|temor)\b"],
    "anger": [r"\b(angry|furious|enojado|rabia|ira)\b"],
    "joy": [r"\b(happy|glad|feliz|alegre|contento)\b"],
    "sadness": [r"\b(sad|triste|deprimido|melancolia)\b"],
    "trust": [r"\b(trust|confio|confiar|confianza)\b"],
    "curiosity": [r"\b(curious|curiosidad|me pregunto|wondering)\b"],
}


EPISTEMIC_PATTERNS: Dict[str, Iterable[str]] = {
    "hedge": [r"\b(maybe|perhaps|probably|posiblemente|quiza|quizas|tal vez|parece|aprox)\b"],
    "certainty": [r"\b(definitely|certainly|sin duda|seguro|obvio|clearly|claramente)\b"],
    "evidence": [r"\b(because|since|por que|segun|de acuerdo a|based on|datos|evidence)\b"],
}


def speech_act_features(text: str) -> Dict[str, int]:
    t = normalize_text(text)
    out: Dict[str, int] = {}
    for key, patterns in SPEECH_ACT_PATTERNS.items():
        if key == "assertion":
            continue
        out[f"act_{key}"] = _count_patterns(t, patterns)
    # Question marks are a weak but useful signal for requests/petitions.
    q = int("?" in text)
    out["act_question_mark"] = q
    out["act_request"] = int(out.get("act_request", 0)) + q

    other = sum(v for k, v in out.items() if k.startswith("act_") and k not in {"act_question_mark"})
    # Use normalized text to avoid script/diacritic edge cases.
    has_content = bool(re.search(r"[a-z0-9]", t))
    out["act_assertion"] = int(has_content and other == 0)
    return out


def declaration_features(text: str) -> Dict[str, int]:
    t = normalize_text(text)
    return {key: _count_patterns(t, patterns) for key, patterns in DECLARATION_PATTERNS.items()}


def mood_features(text: str) -> Dict[str, int]:
    t = normalize_text(text)
    return {f"mood_{key}": _count_patterns(t, patterns) for key, patterns in MOOD_PATTERNS.items()}


def epistemic_features(text: str) -> Dict[str, int]:
    t = normalize_text(text)
    return {f"epistemic_{key}": _count_patterns(t, patterns) for key, patterns in EPISTEMIC_PATTERNS.items()}


def script_profile(text: str) -> Dict[str, float]:
    counts = {
        "latin": 0,
        "cyrillic": 0,
        "arabic": 0,
        "cjk": 0,
        "other": 0,
    }
    total_letters = 0
    for ch in text:
        if not ch.isalpha():
            continue
        total_letters += 1
        name = unicodedata.name(ch, "")
        if "LATIN" in name:
            counts["latin"] += 1
        elif "CYRILLIC" in name:
            counts["cyrillic"] += 1
        elif "ARABIC" in name:
            counts["arabic"] += 1
        elif any(token in name for token in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")):
            counts["cjk"] += 1
        else:
            counts["other"] += 1

    ratios: Dict[str, float] = {}
    for key, val in counts.items():
        ratios[f"script_{key}_ratio"] = (val / total_letters) if total_letters else 0.0
    ratios["script_total_letters"] = float(total_letters)
    ratios["script_mixed"] = float(sum(1 for v in counts.values() if v > 0) > 1)
    return ratios


def language_signals(text: str) -> Dict[str, int | float]:
    features: Dict[str, int | float] = {}
    features.update(speech_act_features(text))
    features.update(declaration_features(text))
    features.update(mood_features(text))
    features.update(epistemic_features(text))
    return features
