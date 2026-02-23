#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.incidence import human_incidence_score  # noqa: E402
from moltbook_analysis.analyze.interference import interference_score  # noqa: E402
from moltbook_analysis.analyze.language_ontology import normalize_text  # noqa: E402
from moltbook_analysis.analyze.text import clean_text  # noqa: E402


URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HANDLE_RE = re.compile(r"@[a-z0-9_]{2,}", re.IGNORECASE)
NUM_RE = re.compile(r"\b\d+\b")
NON_WORD_RE = re.compile(r"[^a-z0-9@#\s]")
SPACE_RE = re.compile(r"\s+")

PROMO_PATTERNS = [
    re.compile(r"\bfirst\s+\d+\s+followers?\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s+spots?\s+left|limited|exclusive|offer closes)\b", re.IGNORECASE),
    re.compile(r"\b(breaking|urgent|not what you think|exact pattern|secret)\b", re.IGNORECASE),
    re.compile(r"\bfollow\s+[a-z0-9_@]{2,}\b", re.IGNORECASE),
]

CTA_PATTERNS = [
    re.compile(r"\b(follow|join|subscribe|dm|direct message|click|learn more|migrate to)\b", re.IGNORECASE),
    re.compile(r"\b(first\s+\d+\s+followers?|spots?\s+left)\b", re.IGNORECASE),
]

HUMAN_SIGNAL_PATTERNS = [
    re.compile(r"\b(my human|mi humano|my creator|mi creador|mi creadora)\b", re.IGNORECASE),
    re.compile(r"\b(created by|created for|operator|owner|the user|el usuario|la usuaria)\b", re.IGNORECASE),
    re.compile(r"\b(prompt injection|white[-\s]?hat test|system prompt|developer message)\b", re.IGNORECASE),
]


@dataclass
class GroupAggregate:
    fingerprint: str
    canonical_text: str
    count: int = 0
    author_keys: set[str] = field(default_factory=set)
    submolts: set[str] = field(default_factory=set)
    author_counts: Counter[str] = field(default_factory=Counter)
    submolt_counts: Counter[str] = field(default_factory=Counter)
    first_created_at: datetime | None = None
    last_created_at: datetime | None = None
    sum_doc_score: float = 0.0
    max_doc_score: float = 0.0
    sum_incidence: float = 0.0
    sum_interference_semantic: float = 0.0
    sum_human_refs: float = 0.0
    sum_prompt_refs: float = 0.0
    sum_tooling_refs: float = 0.0
    sum_narrative_refs: float = 0.0
    promo_docs: int = 0
    cta_docs: int = 0
    human_signal_docs: int = 0
    think_docs: int = 0
    code_docs: int = 0
    evidence_type_counter: Counter[str] = field(default_factory=Counter)
    top_doc_id: str = ""
    top_doc_type: str = ""
    top_excerpt: str = ""
    evidence_doc_ids: list[str] = field(default_factory=list)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def count_hits(text: str, patterns: list[re.Pattern[str]]) -> int:
    return sum(1 for pat in patterns if pat.search(text))


def to_submolt_name(value: Any) -> str:
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name:
            return name
    if isinstance(value, str) and value:
        return value
    return "unknown"


def canonical_signature(text: str) -> tuple[str, str]:
    normalized = normalize_text(clean_text(text or ""))
    normalized = URL_RE.sub(" ", normalized)
    normalized = HANDLE_RE.sub("@user", normalized)
    normalized = NUM_RE.sub("0", normalized)
    normalized = NON_WORD_RE.sub(" ", normalized)
    normalized = SPACE_RE.sub(" ", normalized).strip()
    canonical = normalized[:280]
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16] if canonical else ""
    return canonical, digest


def clip(value: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, value))


def top_share(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return max(counter.values()) / total


def normalized_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    probs = [v / total for v in counter.values() if v > 0]
    if len(probs) <= 1:
        return 0.0
    entropy = -sum(p * math.log2(p) for p in probs)
    return entropy / math.log2(len(probs))


def classify_event(
    count: int,
    promo_rate: float,
    cta_rate: float,
    human_signal_rate: float,
    avg_human_refs: float,
    avg_prompt_refs: float,
    avg_tooling_refs: float,
    avg_narrative_refs: float,
    avg_interference_semantic: float,
    coordination_index: float,
) -> str:
    if count >= 5 and promo_rate >= 0.25 and cta_rate >= 0.2:
        return "campana_promocional"
    if avg_prompt_refs >= 1.2 and avg_tooling_refs >= 1.2:
        return "prompt_tooling"
    if avg_interference_semantic >= 1.5 and avg_prompt_refs >= 0.8:
        return "interferencia_semantica"
    if avg_human_refs >= 2.0 or (human_signal_rate >= 0.45 and avg_prompt_refs <= 4.0):
        return "humano_explicito"
    if count >= 5 and coordination_index >= 0.55 and (avg_prompt_refs >= 0.8 or avg_tooling_refs >= 3.0):
        return "coordinacion_hibrida"
    if count <= 8 and avg_narrative_refs >= 1.5 and promo_rate < 0.2:
        return "narrativa_situada"
    return "mixto"


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def apply_limit(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return rows
    return rows[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecta eventos con probable intervencion humana sobre corpus de posts/comentarios."
    )
    parser.add_argument("--posts", default="data/raw/api_fetch/posts.jsonl")
    parser.add_argument("--comments", default="data/raw/api_fetch/comments.jsonl")
    parser.add_argument("--out-events", default="data/derived/human_intervention_events.csv")
    parser.add_argument("--out-docs", default="data/derived/human_intervention_docs.csv")
    parser.add_argument("--out-groups", default="data/derived/human_intervention_group_features.csv")
    parser.add_argument("--out-summary", default="data/derived/human_intervention_summary.json")
    parser.add_argument("--min-doc-score", type=float, default=2.0)
    parser.add_argument("--min-event-score", type=float, default=3.5)
    parser.add_argument("--min-group-size", type=int, default=2)
    parser.add_argument("--top-events", type=int, default=0)
    parser.add_argument("--top-docs", type=int, default=0)
    args = parser.parse_args()

    posts_path = Path(args.posts)
    comments_path = Path(args.comments)
    out_events = Path(args.out_events)
    out_docs = Path(args.out_docs)
    out_groups = Path(args.out_groups)
    out_summary = Path(args.out_summary)

    post_submolt: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []
    groups: dict[str, GroupAggregate] = {}

    docs_total = 0
    posts_total = 0
    comments_total = 0

    def process_doc(
        doc_id: str,
        doc_type: str,
        text: str,
        author_id: str,
        author_name: str,
        created_at_raw: str,
        submolt: str,
    ) -> None:
        nonlocal docs_total
        docs_total += 1

        if not text:
            return

        incidence = human_incidence_score(text)
        interference = interference_score(text)
        cleaned = clean_text(text)

        promo_hits = count_hits(text, PROMO_PATTERNS)
        cta_hits = count_hits(text, CTA_PATTERNS)
        human_signal_hits = count_hits(text, HUMAN_SIGNAL_PATTERNS)
        has_think_tag = "<think>" in text.lower() or "</think>" in text.lower()
        has_code = "```" in text

        score = (
            float(incidence.get("human_incidence_score", 0.0)) * 0.70
            + float(incidence.get("score_human", 0.0)) * 0.35
            + float(incidence.get("score_prompt", 0.0)) * 0.35
            + float(interference.get("score_semantic", 0.0)) * 0.90
            + promo_hits * 1.25
            + cta_hits * 0.70
            + human_signal_hits * 0.80
        )
        if float(interference.get("noise_score", 0.0)) >= 1.5 and float(interference.get("score_semantic", 0.0)) <= 0.0:
            score -= 0.5
        score = max(0.0, score)

        is_candidate = (
            score >= args.min_doc_score
            or float(incidence.get("human_refs", 0.0)) >= 1.0
            or promo_hits >= 2
            or cta_hits >= 2
            or human_signal_hits >= 1
            or float(interference.get("score_semantic", 0.0)) >= 1.5
        )
        if not is_candidate:
            return

        canonical_text, fingerprint = canonical_signature(cleaned)
        if not fingerprint:
            return

        created_at = parse_dt(created_at_raw)
        excerpt = (cleaned[:240] + "…") if len(cleaned) > 240 else cleaned
        row = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "author_id": author_id,
            "author_name": author_name,
            "submolt": submolt,
            "created_at": created_at_raw,
            "doc_score": round(score, 4),
            "human_incidence_score": round(float(incidence.get("human_incidence_score", 0.0)), 4),
            "score_human": round(float(incidence.get("score_human", 0.0)), 4),
            "score_prompt": round(float(incidence.get("score_prompt", 0.0)), 4),
            "score_narrative": round(float(incidence.get("score_narrative", 0.0)), 4),
            "score_tooling": round(float(incidence.get("score_tooling", 0.0)), 4),
            "human_refs": round(float(incidence.get("human_refs", 0.0)), 4),
            "prompt_refs": round(float(incidence.get("prompt_refs", 0.0)), 4),
            "tooling_refs": round(float(incidence.get("tooling_refs", 0.0)), 4),
            "narrative_refs": round(float(incidence.get("narrative_refs", 0.0)), 4),
            "evidence_type": str(incidence.get("evidence_type", "")),
            "interference_score": round(float(interference.get("score", 0.0)), 4),
            "interference_semantic_score": round(float(interference.get("score_semantic", 0.0)), 4),
            "injection_hits": int(interference.get("injection_hits", 0)),
            "disclaimer_hits": int(interference.get("disclaimer_hits", 0)),
            "promo_hits": promo_hits,
            "cta_hits": cta_hits,
            "human_signal_hits": human_signal_hits,
            "fingerprint": fingerprint,
            "text_excerpt": excerpt,
        }
        candidates.append(row)

        agg = groups.get(fingerprint)
        if agg is None:
            agg = GroupAggregate(fingerprint=fingerprint, canonical_text=canonical_text)
            groups[fingerprint] = agg
        agg.count += 1
        author_key = author_id or author_name or "unknown"
        submolt_key = submolt or "unknown"
        agg.author_keys.add(author_key)
        agg.submolts.add(submolt_key)
        agg.author_counts[author_key] += 1
        agg.submolt_counts[submolt_key] += 1
        agg.sum_doc_score += score
        agg.sum_incidence += float(incidence.get("human_incidence_score", 0.0))
        agg.sum_interference_semantic += float(interference.get("score_semantic", 0.0))
        agg.sum_human_refs += float(incidence.get("human_refs", 0.0))
        agg.sum_prompt_refs += float(incidence.get("prompt_refs", 0.0))
        agg.sum_tooling_refs += float(incidence.get("tooling_refs", 0.0))
        agg.sum_narrative_refs += float(incidence.get("narrative_refs", 0.0))
        if promo_hits > 0:
            agg.promo_docs += 1
        if cta_hits > 0:
            agg.cta_docs += 1
        if human_signal_hits > 0:
            agg.human_signal_docs += 1
        if has_think_tag:
            agg.think_docs += 1
        if has_code:
            agg.code_docs += 1
        evidence_type = str(incidence.get("evidence_type", ""))
        if evidence_type:
            agg.evidence_type_counter[evidence_type] += 1
        if len(agg.evidence_doc_ids) < 5:
            agg.evidence_doc_ids.append(doc_id)
        if score >= agg.max_doc_score:
            agg.max_doc_score = score
            agg.top_doc_id = doc_id
            agg.top_doc_type = doc_type
            agg.top_excerpt = excerpt
        if created_at is not None:
            if agg.first_created_at is None or created_at < agg.first_created_at:
                agg.first_created_at = created_at
            if agg.last_created_at is None or created_at > agg.last_created_at:
                agg.last_created_at = created_at

    for post in iter_jsonl(posts_path):
        posts_total += 1
        post_id = str(post.get("id") or "")
        if not post_id:
            continue
        submolt = to_submolt_name(post.get("submolt"))
        post_submolt[post_id] = submolt
        text = f"{post.get('title') or ''}\n{post.get('content') or ''}".strip()
        author_obj = post.get("author") if isinstance(post.get("author"), dict) else {}
        author_id = str(post.get("author_id") or author_obj.get("id") or "")
        author_name = str(author_obj.get("name") or post.get("author_name") or "")
        process_doc(
            doc_id=post_id,
            doc_type="post",
            text=text,
            author_id=author_id,
            author_name=author_name,
            created_at_raw=str(post.get("created_at") or ""),
            submolt=submolt,
        )

    for comment in iter_jsonl(comments_path):
        comments_total += 1
        comment_id = str(comment.get("id") or "")
        if not comment_id:
            continue
        post_id = str(comment.get("post_id") or "")
        text = str(comment.get("content") or "").strip()
        if not text:
            continue
        author_obj = comment.get("author") if isinstance(comment.get("author"), dict) else {}
        author_id = str(comment.get("author_id") or author_obj.get("id") or "")
        author_name = str(author_obj.get("name") or comment.get("author_name") or "")
        submolt = post_submolt.get(post_id, "unknown")
        process_doc(
            doc_id=comment_id,
            doc_type="comment",
            text=text,
            author_id=author_id,
            author_name=author_name,
            created_at_raw=str(comment.get("created_at") or ""),
            submolt=submolt,
        )

    event_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    class_counter: Counter[str] = Counter()

    for agg in groups.values():
        avg_doc_score = agg.sum_doc_score / agg.count if agg.count else 0.0
        avg_incidence = agg.sum_incidence / agg.count if agg.count else 0.0
        avg_interference_semantic = agg.sum_interference_semantic / agg.count if agg.count else 0.0
        avg_human_refs = agg.sum_human_refs / agg.count if agg.count else 0.0
        avg_prompt_refs = agg.sum_prompt_refs / agg.count if agg.count else 0.0
        avg_tooling_refs = agg.sum_tooling_refs / agg.count if agg.count else 0.0
        avg_narrative_refs = agg.sum_narrative_refs / agg.count if agg.count else 0.0
        promo_rate = agg.promo_docs / agg.count if agg.count else 0.0
        cta_rate = agg.cta_docs / agg.count if agg.count else 0.0
        human_signal_rate = agg.human_signal_docs / agg.count if agg.count else 0.0
        think_tag_rate = agg.think_docs / agg.count if agg.count else 0.0
        code_rate = agg.code_docs / agg.count if agg.count else 0.0

        span_hours: float | None = None
        if agg.first_created_at is not None and agg.last_created_at is not None:
            span_hours = max(0.0, (agg.last_created_at - agg.first_created_at).total_seconds() / 3600.0)

        repeat_bonus = math.log1p(max(0, agg.count - 1)) * 1.4
        cross_author_bonus = min(4.0, max(0, len(agg.author_keys) - 1) * 0.65)
        cross_submolt_bonus = min(3.0, max(0, len(agg.submolts) - 1) * 0.2)
        burst_bonus = 0.0
        if span_hours is not None and agg.count >= 3:
            if span_hours <= 6:
                burst_bonus = 1.8
            elif span_hours <= 24:
                burst_bonus = 1.1
            elif span_hours <= 72:
                burst_bonus = 0.4

        author_top = top_share(agg.author_counts)
        submolt_top = top_share(agg.submolt_counts)
        author_entropy = normalized_entropy(agg.author_counts)
        submolt_entropy = normalized_entropy(agg.submolt_counts)
        coordination_index = clip(
            min(1.0, math.log1p(agg.count) / math.log(50.0)) * 0.32
            + clip((len(agg.author_keys) - 1) / 12.0, 0.0, 1.0) * 0.24
            + clip((len(agg.submolts) - 1) / 60.0, 0.0, 1.0) * 0.16
            + (1.0 - author_top) * 0.1
            + (1.0 - submolt_top) * 0.08
            + clip((promo_rate + cta_rate) / 2.0, 0.0, 1.0) * 0.1,
            0.0,
            1.0,
        )

        event_score = (
            avg_doc_score * 0.8
            + agg.max_doc_score * 0.4
            + repeat_bonus
            + cross_author_bonus
            + cross_submolt_bonus
            + burst_bonus
            + promo_rate * 1.4
            + cta_rate * 0.8
            + avg_interference_semantic * 0.25
        )

        likely_source = classify_event(
            count=agg.count,
            promo_rate=promo_rate,
            cta_rate=cta_rate,
            human_signal_rate=human_signal_rate,
            avg_human_refs=avg_human_refs,
            avg_prompt_refs=avg_prompt_refs,
            avg_tooling_refs=avg_tooling_refs,
            avg_narrative_refs=avg_narrative_refs,
            avg_interference_semantic=avg_interference_semantic,
            coordination_index=coordination_index,
        )

        confidence = clip(
            0.2
            + coordination_index * 0.5
            + clip(event_score / 25.0, 0.0, 1.0) * 0.3
            + (0.05 if likely_source in {"campana_promocional", "prompt_tooling", "interferencia_semantica"} else 0.0),
            0.05,
            0.99,
        )

        dominant_evidence = agg.evidence_type_counter.most_common(1)[0][0] if agg.evidence_type_counter else "mixto"
        base_row = {
            "event_id": agg.fingerprint,
            "event_score": round(event_score, 4),
            "coordination_index": round(coordination_index, 4),
            "confidence": round(confidence, 4),
            "likely_source": likely_source,
            "dominant_evidence_type": dominant_evidence,
            "repeat_count": agg.count,
            "unique_authors": len(agg.author_keys),
            "unique_submolts": len(agg.submolts),
            "author_top_share": round(author_top, 4),
            "submolt_top_share": round(submolt_top, 4),
            "author_entropy": round(author_entropy, 4),
            "submolt_entropy": round(submolt_entropy, 4),
            "first_created_at": agg.first_created_at.isoformat() if agg.first_created_at else "",
            "last_created_at": agg.last_created_at.isoformat() if agg.last_created_at else "",
            "span_hours": round(span_hours, 4) if span_hours is not None else "",
            "avg_doc_score": round(avg_doc_score, 4),
            "max_doc_score": round(agg.max_doc_score, 4),
            "avg_incidence_score": round(avg_incidence, 4),
            "avg_interference_semantic": round(avg_interference_semantic, 4),
            "avg_human_refs": round(avg_human_refs, 4),
            "avg_prompt_refs": round(avg_prompt_refs, 4),
            "avg_tooling_refs": round(avg_tooling_refs, 4),
            "avg_narrative_refs": round(avg_narrative_refs, 4),
            "promo_rate": round(promo_rate, 4),
            "cta_rate": round(cta_rate, 4),
            "human_signal_rate": round(human_signal_rate, 4),
            "think_tag_rate": round(think_tag_rate, 4),
            "code_rate": round(code_rate, 4),
            "evidence_doc_ids": "|".join(agg.evidence_doc_ids),
            "top_doc_id": agg.top_doc_id,
            "top_doc_type": agg.top_doc_type,
            "sample_excerpt": agg.top_excerpt,
            "canonical_excerpt": (agg.canonical_text[:220] + "…") if len(agg.canonical_text) > 220 else agg.canonical_text,
        }
        group_rows.append(base_row)

        if agg.count < max(1, args.min_group_size):
            continue
        if event_score < args.min_event_score:
            continue
        class_counter[likely_source] += 1
        event_rows.append(base_row)

    group_rows.sort(key=lambda r: float(r.get("event_score") or 0.0), reverse=True)
    event_rows.sort(key=lambda r: float(r.get("event_score") or 0.0), reverse=True)
    candidate_docs_sorted = sorted(candidates, key=lambda r: float(r.get("doc_score") or 0.0), reverse=True)
    exported_event_rows = apply_limit(event_rows, args.top_events)
    exported_doc_rows = apply_limit(candidate_docs_sorted, args.top_docs)

    write_csv(
        out_events,
        exported_event_rows,
        [
            "event_id",
            "event_score",
            "coordination_index",
            "confidence",
            "likely_source",
            "dominant_evidence_type",
            "repeat_count",
            "unique_authors",
            "unique_submolts",
            "author_top_share",
            "submolt_top_share",
            "author_entropy",
            "submolt_entropy",
            "first_created_at",
            "last_created_at",
            "span_hours",
            "avg_doc_score",
            "max_doc_score",
            "avg_incidence_score",
            "avg_interference_semantic",
            "avg_human_refs",
            "avg_prompt_refs",
            "avg_tooling_refs",
            "avg_narrative_refs",
            "promo_rate",
            "cta_rate",
            "human_signal_rate",
            "think_tag_rate",
            "code_rate",
            "evidence_doc_ids",
            "top_doc_id",
            "top_doc_type",
            "sample_excerpt",
            "canonical_excerpt",
        ],
    )
    write_csv(
        out_groups,
        group_rows,
        [
            "event_id",
            "event_score",
            "coordination_index",
            "confidence",
            "likely_source",
            "dominant_evidence_type",
            "repeat_count",
            "unique_authors",
            "unique_submolts",
            "author_top_share",
            "submolt_top_share",
            "author_entropy",
            "submolt_entropy",
            "first_created_at",
            "last_created_at",
            "span_hours",
            "avg_doc_score",
            "max_doc_score",
            "avg_incidence_score",
            "avg_interference_semantic",
            "avg_human_refs",
            "avg_prompt_refs",
            "avg_tooling_refs",
            "avg_narrative_refs",
            "promo_rate",
            "cta_rate",
            "human_signal_rate",
            "think_tag_rate",
            "code_rate",
            "evidence_doc_ids",
            "top_doc_id",
            "top_doc_type",
            "sample_excerpt",
            "canonical_excerpt",
        ],
    )
    write_csv(
        out_docs,
        exported_doc_rows,
        [
            "doc_id",
            "doc_type",
            "author_id",
            "author_name",
            "submolt",
            "created_at",
            "doc_score",
            "human_incidence_score",
            "score_human",
            "score_prompt",
            "score_narrative",
            "score_tooling",
            "human_refs",
            "prompt_refs",
            "tooling_refs",
            "narrative_refs",
            "evidence_type",
            "interference_score",
            "interference_semantic_score",
            "injection_hits",
            "disclaimer_hits",
            "promo_hits",
            "cta_hits",
            "human_signal_hits",
            "fingerprint",
            "text_excerpt",
        ],
    )

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "posts_path": str(posts_path),
            "comments_path": str(comments_path),
            "posts_total": posts_total,
            "comments_total": comments_total,
            "docs_total": docs_total,
        },
        "thresholds": {
            "min_doc_score": args.min_doc_score,
            "min_event_score": args.min_event_score,
            "min_group_size": args.min_group_size,
        },
        "counts": {
            "candidate_docs": len(candidates),
            "candidate_groups": len(groups),
            "groups_exported": len(group_rows),
            "events_exported": len(exported_event_rows),
            "docs_exported": len(exported_doc_rows),
        },
        "class_distribution": dict(class_counter),
        "top_event_ids": [row["event_id"] for row in exported_event_rows[:10]],
    }
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    with out_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"candidate_docs={len(candidates)} candidate_groups={len(groups)} exported_events={summary['counts']['events_exported']}")
    print(f"events_csv={out_events}")
    print(f"groups_csv={out_groups}")
    print(f"docs_csv={out_docs}")
    print(f"summary_json={out_summary}")


if __name__ == "__main__":
    main()
