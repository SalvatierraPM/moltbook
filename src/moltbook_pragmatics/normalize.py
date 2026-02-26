from __future__ import annotations

import re
import unicodedata
from typing import Dict

try:
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except Exception:
    _HAS_LANGDETECT = False


_WS_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def clean_text(text: str) -> str:
    t = text or ""
    t = unicodedata.normalize("NFKC", t)
    t = _URL_RE.sub(" <URL> ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def detect_language(text: str, provided: str | None = None) -> str:
    if provided:
        return str(provided).lower()
    t = (text or "").strip()
    if len(t) < 4:
        return "unknown"
    if not _HAS_LANGDETECT:
        return "unknown"
    try:
        lang = detect(t)
        return lang.lower()
    except Exception:
        return "unknown"


def enrich_locution(message: Dict) -> Dict:
    cleaned = clean_text(message.get("text", ""))
    language = detect_language(cleaned, message.get("language"))
    out = dict(message)
    out["locution"] = {
        "cleaned_text": cleaned,
        "detected_language": language,
        "text_length": len(cleaned),
    }
    return out
