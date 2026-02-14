#!/usr/bin/env python3
"""Generate a reproducible audit package for Moltbook analysis outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
# Assumption: the web repo lives next to the main repo under the same parent dir.
WEB_ROOT = (ROOT.parent / "reporte-analisis-memetico-ontologico-moltbook-ui").resolve()
AUDIT_DIR = ROOT / "reports" / "audit"
DERIVED = ROOT / "data" / "derived"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_dt(value: str) -> datetime:
    raw = value.replace(" ", "T").replace("+00:00", "Z")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def is_noisy_text(text: str) -> bool:
    clean = re.sub(r"\s+", "", text or "")
    if not clean:
        return False
    if re.search(r"(.)\1{20,}", clean):
        return True
    if re.search(r"base64,[A-Za-z0-9+/=]{120,}", clean):
        return True
    if len(clean) >= 60:
        unique_ratio = len(set(clean.lower())) / len(clean)
        if unique_ratio < 0.12:
            return True
    return False


def run_command(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return proc.stdout.strip()


@dataclass
class Metrics:
    posts_total: int
    comments_total: int
    comments_duplicates: int
    created_window_days: float
    run_window_days: float
    runs: int
    mention_top_node: str
    mention_top_pagerank: float
    mention_noise_top10: int
    memes_api_like_top20_raw: int
    memes_api_like_top20_cultural: int
    meme_candidates_cultural_rows: int
    meme_candidates_technical_rows: int
    has_meme_double_ranking: bool
    ontology_benchmark_has_metrics: bool
    ontology_benchmark_labeled_total: int
    ontology_benchmark_labeled_en: int
    ontology_benchmark_labeled_es: int
    ontology_benchmark_accuracy_en: float
    ontology_benchmark_accuracy_es: float
    interference_noisy_top50: int
    interference_has_split_scores: bool
    incidence_tooling_top50: int
    lang_posts_sample: int
    lang_comments_sample: int
    has_tests: bool
    has_ci: bool
    has_lockfile: bool
    has_plaintext_token_file: bool
    netlify_linked_site: bool
    netlify_github_link_evidence: bool


def compute_metrics() -> Metrics:
    coverage = json.loads((DERIVED / "coverage_quality.json").read_text(encoding="utf-8"))
    diffusion = read_csv(DERIVED / "diffusion_runs.csv")
    mention = read_csv(DERIVED / "mention_graph_centrality.csv")
    memes_raw = read_csv(DERIVED / "meme_candidates.csv")
    memes_cultural = read_csv(DERIVED / "meme_candidates_cultural.csv") if (DERIVED / "meme_candidates_cultural.csv").exists() else []
    memes_technical = read_csv(DERIVED / "meme_candidates_technical.csv") if (DERIVED / "meme_candidates_technical.csv").exists() else []
    interference = read_csv(DERIVED / "interference_top.csv")
    incidence = read_csv(DERIVED / "human_incidence_top.csv")
    language = read_csv(DERIVED / "public_language_distribution.csv")
    bench_metrics_path = DERIVED / "ontology_benchmark_metrics.json"
    bench_metrics = json.loads(bench_metrics_path.read_text(encoding="utf-8")) if bench_metrics_path.exists() else {}
    labeled_total = to_int(bench_metrics.get("labeled_total"))
    labeled_by_lang = bench_metrics.get("labeled_by_lang") or {}
    acc_by_lang = bench_metrics.get("accuracy_by_lang") or {}
    labeled_en = to_int(labeled_by_lang.get("en"))
    labeled_es = to_int(labeled_by_lang.get("es"))
    acc_en = to_float(acc_by_lang.get("en"))
    acc_es = to_float(acc_by_lang.get("es"))

    created_min = min(parse_dt(coverage["posts_created_min"]), parse_dt(coverage["comments_created_min"]))
    created_max = max(parse_dt(coverage["posts_created_max"]), parse_dt(coverage["comments_created_max"]))
    run_dates = [parse_dt(r["run_time"]) for r in diffusion if r.get("run_time")]
    run_min = min(run_dates)
    run_max = max(run_dates)
    runs = len({r["run_id"] for r in diffusion if r.get("run_id")})

    mention_sorted = sorted(mention, key=lambda r: to_float(r.get("pagerank")), reverse=True)
    top_mention = mention_sorted[0] if mention_sorted else {}
    noise_pat = re.compile(r"^(w|www|w-|-|\\|_+|[^\w]+)$", re.IGNORECASE)
    mention_noise_top10 = sum(
        1 for r in mention_sorted[:10] if noise_pat.match((r.get("node") or "").strip())
    )

    memes_sorted_raw = sorted(memes_raw, key=lambda r: to_int(r.get("count")), reverse=True)
    memes_sorted_cultural = sorted(memes_cultural, key=lambda r: to_int(r.get("count")), reverse=True)
    api_like_pat = re.compile(r"(api|curl|agentmarket|jq|discover|v1|mbc20|xyz|0x)", re.IGNORECASE)
    memes_api_like_top20_raw = sum(1 for r in memes_sorted_raw[:20] if api_like_pat.search((r.get("meme") or "")))
    memes_api_like_top20_cultural = sum(
        1 for r in memes_sorted_cultural[:20] if api_like_pat.search((r.get("meme") or ""))
    ) if memes_sorted_cultural else memes_api_like_top20_raw

    inter_top50 = sorted(interference, key=lambda r: to_float(r.get("score")), reverse=True)[:50]
    interference_noisy_top50 = sum(1 for r in inter_top50 if is_noisy_text(r.get("text_excerpt", "")))
    interference_has_split_scores = bool(interference) and ("score_semantic" in interference[0] and "noise_score" in interference[0])

    inc_top50 = sorted(incidence, key=lambda r: to_float(r.get("human_incidence_score")), reverse=True)[:50]
    incidence_tooling_top50 = sum(1 for r in inc_top50 if to_float(r.get("tooling_refs")) >= 10)

    lang_posts_sample = sum(to_int(r.get("count")) for r in language if r.get("scope") == "posts")
    lang_comments_sample = sum(to_int(r.get("count")) for r in language if r.get("scope") == "comments")

    has_tests = bool(run_command(["find", ".", "-maxdepth", "3", "-type", "d", "-name", "tests"]))
    has_ci = (ROOT / ".github" / "workflows").exists()
    has_lockfile = any((ROOT / name).exists() for name in ("poetry.lock", "uv.lock", "requirements.lock", "Pipfile.lock"))
    token_file = ROOT / ".secrets" / "github_token"
    has_plaintext_token_file = token_file.exists() and token_file.stat().st_size > 0
    netlify_state = WEB_ROOT / ".netlify" / "state.json"
    netlify_linked_site = netlify_state.exists()
    netlify_github_link_evidence = False

    return Metrics(
        posts_total=to_int(coverage["posts_total"]),
        comments_total=to_int(coverage["comments_total"]),
        comments_duplicates=to_int(coverage["comments_duplicates"]),
        created_window_days=(created_max - created_min).total_seconds() / 86400.0,
        run_window_days=(run_max - run_min).total_seconds() / 86400.0,
        runs=runs,
        mention_top_node=top_mention.get("node", ""),
        mention_top_pagerank=to_float(top_mention.get("pagerank")),
        mention_noise_top10=mention_noise_top10,
        memes_api_like_top20_raw=memes_api_like_top20_raw,
        memes_api_like_top20_cultural=memes_api_like_top20_cultural,
        meme_candidates_cultural_rows=len(memes_cultural),
        meme_candidates_technical_rows=len(memes_technical),
        has_meme_double_ranking=bool(memes_cultural) and bool(memes_technical),
        ontology_benchmark_has_metrics=bench_metrics_path.exists(),
        ontology_benchmark_labeled_total=labeled_total,
        ontology_benchmark_labeled_en=labeled_en,
        ontology_benchmark_labeled_es=labeled_es,
        ontology_benchmark_accuracy_en=acc_en,
        ontology_benchmark_accuracy_es=acc_es,
        interference_noisy_top50=interference_noisy_top50,
        interference_has_split_scores=interference_has_split_scores,
        incidence_tooling_top50=incidence_tooling_top50,
        lang_posts_sample=lang_posts_sample,
        lang_comments_sample=lang_comments_sample,
        has_tests=has_tests,
        has_ci=has_ci,
        has_lockfile=has_lockfile,
        has_plaintext_token_file=has_plaintext_token_file,
        netlify_linked_site=netlify_linked_site,
        netlify_github_link_evidence=netlify_github_link_evidence,
    )


def build_evidence_index(now: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    sources: list[tuple[str, Path, str, str]] = [
        ("EVID-REPORT-001", ROOT / "reports" / "public_report.md", "read report claims", "Reporte publico base"),
        ("EVID-SCHEMA-001", ROOT / "reports" / "analysis_schema.md", "read analysis schema", "Esquema metodologico"),
        (
            "EVID-ONTO-LABEL-001",
            ROOT / "reports" / "audit" / "ontology_labeling_protocol.md",
            "read labeling protocol",
            "Protocolo de etiquetado para benchmark ontologico (actos del habla)",
        ),
        ("EVID-COVERAGE-001", DERIVED / "coverage_quality.json", "inspect coverage file", "Duplicados y ventanas temporales"),
        ("EVID-DIFFUSION-001", DERIVED / "diffusion_runs.csv", "inspect run timeline", "Serie temporal por captura"),
        ("EVID-ACTIVITY-001", DERIVED / "activity_daily.csv", "inspect activity timeline", "Serie temporal por created_at"),
        ("EVID-MEME-001", DERIVED / "meme_candidates.csv", "rank meme candidates", "Top memes lexicales"),
        ("EVID-MEME-002", DERIVED / "meme_candidates_cultural.csv", "rank cultural meme candidates", "Top memes (vista cultural filtrada)"),
        ("EVID-MEME-003", DERIVED / "meme_candidates_technical.csv", "rank technical meme candidates", "Top memes (vista tecnica/boilerplate)"),
        ("EVID-MENTION-001", DERIVED / "mention_graph_centrality.csv", "inspect mention centrality", "Calidad del grafo de mentions"),
        ("EVID-INTERF-001", DERIVED / "interference_top.csv", "inspect top interference rows", "Top score de interferencia"),
        ("EVID-INCID-001", DERIVED / "human_incidence_top.csv", "inspect top incidence rows", "Top score de incidencia humana"),
        ("EVID-LANG-001", DERIVED / "public_language_distribution.csv", "inspect language sample", "Distribucion por muestra"),
        ("EVID-ONTO-BENCH-001", DERIVED / "ontology_benchmark_sample.csv", "inspect ontology benchmark scaffold", "Muestra para etiquetado humano de actos de habla"),
        ("EVID-ONTO-BENCH-002", DERIVED / "ontology_benchmark_metrics.json", "inspect ontology benchmark metrics", "Metricas de validacion por idioma"),
        ("EVID-PYPROJECT-001", ROOT / "pyproject.toml", "inspect dependency constraints", "Riesgo de no fijar versiones"),
        ("EVID-LOCK-001", ROOT / "requirements.lock", "inspect lockfile", "Dependencias fijadas para reproducibilidad"),
        ("EVID-TESTS-001", ROOT / "src", "find tests directories", "Cobertura de pruebas automatizadas"),
        ("EVID-CI-001", ROOT / ".github", "list CI workflows", "Automatizacion de validacion"),
        ("EVID-RANDOM-001", ROOT / "scripts" / "fetch_moltbook_api.py", "grep random.choice", "No determinismo de ingesta"),
        # Never hash or capture contents of local secret files.
        ("EVID-SECRETS-001", ROOT / ".secrets" / "github_token", "check local secret file", "Riesgo operativo de secretos locales"),
        ("EVID-NETLIFY-001", WEB_ROOT / ".netlify" / "state.json", "inspect netlify linkage", "Sitio Netlify linkeado localmente"),
        ("EVID-UI-TEMPORAL-001", ROOT / "site" / "analysis.html", "inspect temporal labels", "Separacion created_at vs run_time"),
    ]
    for evidence_ref, src, cmd, notes in sources:
        safe_hash = ""
        if src.exists() and src.is_file() and src.name != "github_token":
            safe_hash = sha256_file(src)
        entry = {
            "evidence_ref": evidence_ref,
            "source_path": str(src),
            "command": cmd,
            "hash": safe_hash,
            "timestamp": now,
            "notes": notes,
        }
        entries.append(entry)
    return entries


def build_claim_matrix(m: Metrics) -> list[dict[str, Any]]:
    """Formal claim->evidence->limitations table for academic rigor."""

    return [
        {
            "claim_id": "CLM-001",
            "claim": "El snapshot contiene ~153k posts y ~704k comentarios, con baja tasa de duplicados.",
            "evidence_datasets": "coverage_quality.json",
            "computation_notes": "Volumen y duplicados desde coverage_quality.json.",
            "limitations": "Describe lo observado en la ventana; no implica cobertura total fuera de ella.",
            "confidence": "alta",
        },
        {
            "claim_id": "CLM-002",
            "claim": "La ventana temporal real (created_at) es mayor que la ventana de captura (run_time), por lo que run-based no mide ritmo real.",
            "evidence_datasets": "coverage_quality.json;diffusion_runs.csv;activity_daily.csv",
            "computation_notes": f"created_at~{m.created_window_days:.1f} dias vs run_time~{m.run_window_days:.1f} dias; runs={m.runs}.",
            "limitations": "Depende de consistencia de timestamps; el scrapeo puede omitir actividad entre runs.",
            "confidence": "alta",
        },
        {
            "claim_id": "CLM-003",
            "claim": "La distribucion de idiomas publicada es una estimacion por muestra, no un censo completo.",
            "evidence_datasets": "public_language_distribution.csv",
            "computation_notes": f"Muestra: posts={m.lang_posts_sample}, comentarios={m.lang_comments_sample}.",
            "limitations": "Langdetect falla en textos cortos, mixtos o con codigo; shares no son exactos del corpus completo.",
            "confidence": "media",
        },
        {
            "claim_id": "CLM-004",
            "claim": "El ranking raw de memes lexicales estaba dominado por cadenas tecnicas (API/tooling); por eso se publica doble ranking (vista cultural filtrada + vista tecnica/boilerplate).",
            "evidence_datasets": "meme_candidates.csv;meme_candidates_cultural.csv;meme_candidates_technical.csv",
            "computation_notes": (
                f"Raw top20: {m.memes_api_like_top20_raw}/20 con patrones api/tooling (regex). "
                f"Vista cultural top20: {m.memes_api_like_top20_cultural}/20 con patrones api/tooling."
            ),
            "limitations": "La separacion cultural/tecnica es heuristica y requiere validacion manual/benchmark; se publica para evitar interpretacion misleading.",
            "confidence": "alta",
        },
        {
            "claim_id": "CLM-005",
            "claim": "El mention graph presenta ruido de tokens no-handle en nodos top, afectando centralidad.",
            "evidence_datasets": "mention_graph_centrality.csv",
            "computation_notes": f"Top node={m.mention_top_node} (pagerank={m.mention_top_pagerank:.3f}); ruido top10={m.mention_noise_top10}.",
            "limitations": "La definicion de 'ruido' es regex; se requiere limpieza en extraccion o normalizacion de mentions.",
            "confidence": "alta",
        },
        {
            "claim_id": "CLM-006",
            "claim": "El score de interferencia en top documentos se infla por formato/ruido (base64, repeticion), por lo que se debe usar como ranking, no prueba.",
            "evidence_datasets": "interference_top.csv",
            "computation_notes": f"En top50 por score, {m.interference_noisy_top50}/50 son ruidosos por heuristica.",
            "limitations": "Heuristica de ruido no capta ironia ni contexto; requiere separar subscore semantico vs tecnico.",
            "confidence": "alta",
        },
        {
            "claim_id": "CLM-007",
            "claim": "Reproducibilidad puede variar porque dependencias no estan fijadas por lockfile.",
            "evidence_datasets": "pyproject.toml",
            "computation_notes": "Dependencias declaradas con rangos >=; no hay lockfile.",
            "limitations": "El riesgo se materializa al reconstruir en entornos distintos; mitigable con lockfile.",
            "confidence": "alta",
        },
    ]


def build_data_lineage() -> list[dict[str, Any]]:
    """Metric lineage table: metric -> sources -> transforms -> outputs."""

    return [
        {
            "metric_id": "MET-001",
            "ui_location": "landing+analysis: Resumen de Cobertura",
            "metric_name": "Posts/Comentarios totales",
            "definition": "Suma de posts/comments por submolt + conteos globales.",
            "time_axis": "created_at",
            "source_files": "data/derived/submolt_stats.csv;data/derived/author_stats.csv;data/derived/coverage_quality.json",
            "transform_script": "scripts/quant_sociology.py;scripts/aggregate_objectives.py",
            "output_files": "submolt_stats.csv;author_stats.csv;coverage_quality.json",
            "notes": "Deduplicacion y rangos temporales en coverage_quality.json.",
        },
        {
            "metric_id": "MET-002",
            "ui_location": "analysis: Difusion",
            "metric_name": "Actividad real por dia",
            "definition": "Posts y comentarios agregados por date(created_at) y submolt.",
            "time_axis": "created_at",
            "source_files": "data/raw/api_fetch/posts.jsonl;data/raw/api_fetch/comments.jsonl (o equivalentes normalizados)",
            "transform_script": "scripts/quant_sociology.py (derivado activity_daily.csv)",
            "output_files": "activity_daily.csv",
            "notes": "No depende de run_id; representa tiempo real publicado.",
        },
        {
            "metric_id": "MET-003",
            "ui_location": "analysis: Difusion",
            "metric_name": "Captura por run",
            "definition": "Agregacion por run_time y run_id del estado observado en cada run.",
            "time_axis": "run_time",
            "source_files": "data/raw/api_fetch/listings.jsonl (snapshots)",
            "transform_script": "scripts/diffusion_metrics.py",
            "output_files": "diffusion_runs.csv;diffusion_submolts.csv",
            "notes": "Puede variar por volumen scrapeado y sampling del run.",
        },
        {
            "metric_id": "MET-004",
            "ui_location": "landing+analysis: Memetica",
            "metric_name": "Meme candidates (n-gramas)",
            "definition": "N-gramas frecuentes extraidos de texto normalizado.",
            "time_axis": "created_at",
            "source_files": "posts/comments normalizados",
            "transform_script": "scripts/meme_models.py",
            "output_files": (
                "meme_candidates.csv;meme_candidates_cultural.csv;meme_candidates_technical.csv;"
                "meme_timeseries_hourly.parquet;meme_bursts.csv;meme_survival.csv;meme_classification.csv"
            ),
            "notes": "Se publica doble ranking (cultural vs tecnico/boilerplate) para evitar confundir repeticion tecnica con meme cultural.",
        },
        {
            "metric_id": "MET-005",
            "ui_location": "analysis: Ontologia",
            "metric_name": "Actos de habla/moods/epistemicos",
            "definition": "Conteo de patrones lingüisticos (heuristicas) por doc.",
            "time_axis": "created_at",
            "source_files": "signals_posts.parquet;signals_comments.parquet",
            "transform_script": "scripts/derive_signals.py;scripts/aggregate_objectives.py",
            "output_files": "ontology_summary.csv;ontology_concepts_top.csv;ontology_cooccurrence_top.csv;ontology_submolt_embedding_2d.csv",
            "notes": "Comparabilidad multilenguaje depende de cobertura de patrones; requiere benchmark.",
        },
        {
            "metric_id": "MET-006",
            "ui_location": "analysis: Redes",
            "metric_name": "Centralidades y comunidades",
            "definition": "Grafos dirigidos reply/mention; PageRank/Betweenness; comunidades.",
            "time_axis": "created_at (indirecto)",
            "source_files": "edges_replies.csv;edges_mentions.csv",
            "transform_script": "scripts/extract_edges.py;scripts/quant_sociology.py",
            "output_files": "reply_graph_centrality.csv;mention_graph_centrality.csv;reply_graph_communities.csv;mention_graph_communities.csv",
            "notes": "Mention graph requiere limpieza de tokens no-handle antes del calculo.",
        },
    ]


def build_findings(m: Metrics, claim_rows: int, lineage_rows: int) -> list[dict[str, str]]:
    return [
        {
            "finding_id": "AUD-001",
            "severity": "P1",
            "domain": "Claims e inferencia",
            "claim": "El reporte presenta tesis fuertes de dominancia memetica/ontologica.",
            "issue": "No hay matriz formal claim->evidencia->limite con nivel de confianza por claim.",
            "evidence_ref": "EVID-REPORT-001|EVID-SCHEMA-001",
            "impact": "Riesgo de sobregeneralizacion academica en conclusiones centrales.",
            "recommendation": "Publicar una tabla de claims con evidencia primaria y limites explicitos por claim.",
            "owner": "Research",
            "status": "mitigated" if claim_rows >= 5 else "open",
        },
        {
            "finding_id": "AUD-002",
            "severity": "P1",
            "domain": "Linaje de datos",
            "claim": "Cada metrica del dashboard es auditable de punta a punta.",
            "issue": "No existe artefacto formal de linaje campo-a-campo para metricas criticas.",
            "evidence_ref": "EVID-SCHEMA-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001",
            "impact": "Dificulta auditoria externa y trazabilidad reproducible.",
            "recommendation": "Crear data lineage table (metrica, fuente, transformacion, script, salida).",
            "owner": "Data",
            "status": "mitigated" if lineage_rows >= 5 else "open",
        },
        {
            "finding_id": "AUD-003",
            "severity": "P2",
            "domain": "Cobertura temporal",
            "claim": "La actividad temporal esta correctamente interpretada.",
            "issue": f"Ventana created_at={m.created_window_days:.1f} dias vs run_time={m.run_window_days:.1f} dias con {m.runs} runs.",
            "evidence_ref": "EVID-COVERAGE-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001|EVID-UI-TEMPORAL-001",
            "impact": "Riesgo medio de mezclar ritmo real y ritmo de captura en lecturas no expertas.",
            "recommendation": "Mantener toggle por defecto en actividad real y reforzar notas en tablas run-based.",
            "owner": "Frontend",
            "status": "open",
        },
        {
            "finding_id": "AUD-004",
            "severity": "P1",
            "domain": "Memetica",
            "claim": "Top memes reflejan ideas culturales dominantes.",
            "issue": (
                f"Raw top20: {m.memes_api_like_top20_raw}/20 con patrones API/tooling; "
                f"vista cultural top20: {m.memes_api_like_top20_cultural}/20."
            ),
            "evidence_ref": "EVID-MEME-001|EVID-MEME-002|EVID-MEME-003",
            "impact": "Alta probabilidad de confundir repeticion tecnica con meme cultural.",
            "recommendation": "Agregar filtro de boilerplate y doble ranking: tecnico vs cultural.",
            "owner": "NLP",
            "status": (
                "mitigated"
                if (m.has_meme_double_ranking and m.memes_api_like_top20_cultural <= 2 and m.meme_candidates_cultural_rows >= 50)
                else "open"
            ),
        },
        {
            "finding_id": "AUD-005",
            "severity": "P1",
            "domain": "Ontologia del lenguaje",
            "claim": "Actos/moods son comparables entre idiomas.",
            "issue": (
                "Benchmark ontologico sin validacion suficiente: "
                f"metrics={'yes' if m.ontology_benchmark_has_metrics else 'no'}; "
                f"labeled_total={m.ontology_benchmark_labeled_total} (en={m.ontology_benchmark_labeled_en}, es={m.ontology_benchmark_labeled_es})."
            ),
            "evidence_ref": "EVID-SCHEMA-001|EVID-LANG-001|EVID-ONTO-BENCH-001|EVID-ONTO-BENCH-002",
            "impact": "Riesgo alto de sesgo semantico en comparacion multilingue.",
            "recommendation": "Evaluar precision/recall con muestra etiquetada estratificada por idioma.",
            "owner": "Research",
            "status": (
                "mitigated"
                if (
                    m.ontology_benchmark_has_metrics
                    and m.ontology_benchmark_labeled_total >= 200
                    and m.ontology_benchmark_labeled_en >= 50
                    and m.ontology_benchmark_labeled_es >= 50
                    and m.ontology_benchmark_accuracy_en >= 0.55
                    and m.ontology_benchmark_accuracy_es >= 0.55
                )
                else "open"
            ),
        },
        {
            "finding_id": "AUD-006",
            "severity": "P1",
            "domain": "Sociologia y redes",
            "claim": "Centralidades del mention graph identifican actores reales.",
            "issue": (
                f"Top mention node='{m.mention_top_node}' pagerank={m.mention_top_pagerank:.3f}; "
                f"nodos ruido en top10={m.mention_noise_top10}."
            ),
            "evidence_ref": "EVID-MENTION-001",
            "impact": "Centralidad contaminada por tokens basura; inferencia de influencia comprometida.",
            "recommendation": "Normalizar/filtrar handles invalidos antes del calculo de grafos.",
            "owner": "Data",
            "status": (
                "mitigated"
                if (
                    m.mention_noise_top10 <= 1
                    and not re.compile(r"^(w|www|w-|-|\\|_+|[^\w]+)$", re.IGNORECASE).match((m.mention_top_node or "").strip())
                )
                else "open"
            ),
        },
        {
            "finding_id": "AUD-007",
            "severity": "P1",
            "domain": "Interferencia",
            "claim": "Score alto identifica interferencia significativa.",
            "issue": (
                f"{m.interference_noisy_top50}/50 top rows son texto ruidoso/base64/repetitivo; "
                f"split_scores={'yes' if m.interference_has_split_scores else 'no'}."
            ),
            "evidence_ref": "EVID-INTERF-001",
            "impact": "Muchos falsos positivos en top ranking; costo de revision manual elevado.",
            "recommendation": "Separar score tecnico (ruido/formato) de score semantico (injection/disclaimer).",
            "owner": "NLP",
            "status": "mitigated" if (m.interference_has_split_scores and m.interference_noisy_top50 <= 10) else "open",
        },
        {
            "finding_id": "AUD-008",
            "severity": "P2",
            "domain": "Incidencia humana",
            "claim": "Score captura intervencion humana relevante.",
            "issue": f"{m.incidence_tooling_top50}/50 top rows tienen tooling_refs>=10 (sesgo tecnico).",
            "evidence_ref": "EVID-INCID-001",
            "impact": "Score tiende a privilegiar textos tecnicos sobre evidencia humana contextual.",
            "recommendation": "Introducir subscore narrativo y etiqueta de tipo de evidencia.",
            "owner": "NLP",
            "status": "open",
        },
        {
            "finding_id": "AUD-009",
            "severity": "P2",
            "domain": "Transmision IA vs humana",
            "claim": "Comparacion IA vs humano es robusta y generalizable.",
            "issue": "No se publica analisis de sensibilidad de thresholds ni baseline alternativo.",
            "evidence_ref": "EVID-REPORT-001|EVID-LANG-001",
            "impact": "Interpretaciones comparativas con incertidumbre no cuantificada.",
            "recommendation": "Publicar sensibilidad por threshold y baseline VSM/embeddings comparado.",
            "owner": "Research",
            "status": "open",
        },
        {
            "finding_id": "AUD-010",
            "severity": "P1",
            "domain": "Reproducibilidad",
            "claim": "Pipeline es totalmente reproducible.",
            "issue": f"Dependencias en pyproject usan rangos '>='; lockfile={'yes' if m.has_lockfile else 'no'}.",
            "evidence_ref": "EVID-PYPROJECT-001|EVID-LOCK-001",
            "impact": "Resultados pueden variar entre entornos y fechas.",
            "recommendation": "Fijar lockfile (uv/pip-tools/poetry) y versionar entorno de ejecucion.",
            "owner": "Infra",
            "status": "mitigated" if m.has_lockfile else "open",
        },
        {
            "finding_id": "AUD-011",
            "severity": "P1",
            "domain": "Ingenieria y mantenibilidad",
            "claim": "Validacion automatizada cubre regresiones criticas.",
            "issue": f"Tests={'yes' if m.has_tests else 'no'}; CI={'yes' if m.has_ci else 'no'}.",
            "evidence_ref": "EVID-TESTS-001|EVID-CI-001",
            "impact": "Alto riesgo de regresion silenciosa en metrica y UI.",
            "recommendation": "Agregar smoke tests de datos + test unitarios clave + CI minima por PR.",
            "owner": "Engineering",
            "status": "mitigated" if (m.has_tests and m.has_ci) else "open",
        },
        {
            "finding_id": "AUD-012",
            "severity": "P1",
            "domain": "Seguridad y compliance",
            "claim": "Operacion de publicacion no expone secretos.",
            "issue": f"Token en texto plano bajo .secrets: {'yes' if m.has_plaintext_token_file else 'no'}.",
            "evidence_ref": "EVID-SECRETS-001",
            "impact": "Riesgo alto de fuga accidental por copia, backup o comando incorrecto.",
            "recommendation": "Mover secretos a keychain/env temporal y rotar token activo.",
            "owner": "Security",
            "status": "mitigated" if not m.has_plaintext_token_file else "open",
        },
        {
            "finding_id": "AUD-013",
            "severity": "P2",
            "domain": "Operacion deploy",
            "claim": "Deploy automatico GitHub->Netlify esta garantizado.",
            "issue": "Hay evidencia de sitio Netlify localmente linkeado, pero no evidencia en repo de integracion GitHub.",
            "evidence_ref": "EVID-NETLIFY-001",
            "impact": "Riesgo de creer que hay deploy automatico cuando depende de pasos manuales.",
            "recommendation": "Documentar estado de integracion y enlace de repo en runbook operativo.",
            "owner": "Infra",
            "status": "open",
        },
        {
            "finding_id": "AUD-014",
            "severity": "P3",
            "domain": "Producto publico",
            "claim": "La UI distingue actividad real y captura.",
            "issue": "El riesgo misleading temporal esta mitigado en graficos principales y texto explicativo.",
            "evidence_ref": "EVID-UI-TEMPORAL-001",
            "impact": "Sin impacto material actual; mantener como control continuo.",
            "recommendation": "Conservar esta separacion en cada nueva visualizacion temporal.",
            "owner": "Frontend",
            "status": "mitigated",
        },
    ]


def gate_status(findings: list[dict[str, str]], domains: set[str]) -> str:
    severe = [f for f in findings if f["status"] != "mitigated" and f["domain"] in domains and f["severity"] in {"P0", "P1"}]
    return "fail" if severe else "pass"


def build_quality_gates(findings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "gates": {
            "G1_data_integrity": {
                "status": gate_status(findings, {"Linaje de datos", "Cobertura temporal", "Sociologia y redes"}),
                "criterion": "Aprobado si no hay P0/P1 abiertos en calidad/linaje/cobertura.",
            },
            "G2_method_validity": {
                "status": gate_status(findings, {"Claims e inferencia", "Memetica", "Ontologia del lenguaje", "Interferencia", "Incidencia humana", "Transmision IA vs humana"}),
                "criterion": "Aprobado si no hay claims fuertes sin evidencia trazable.",
            },
            "G3_reproducibility": {
                "status": gate_status(findings, {"Reproducibilidad", "Ingenieria y mantenibilidad"}),
                "criterion": "Aprobado si runbook y entorno reproducen outputs nucleares.",
            },
            "G4_public_safety": {
                "status": gate_status(findings, {"Seguridad y compliance", "Operacion deploy", "Producto publico"}),
                "criterion": "Aprobado si no hay riesgo de seguridad/compliance sin mitigacion.",
            },
        }
    }


def build_backlog(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "task_id": f"TASK-{f['finding_id']}",
            "severity": f["severity"],
            "component": f["domain"],
            "fix_type": "metodologico" if f["domain"] in {"Claims e inferencia", "Memetica", "Ontologia del lenguaje", "Transmision IA vs humana"} else "tecnico",
            "effort_estimate": "M" if f["severity"] in {"P0", "P1"} else "S",
            "dependency": f["evidence_ref"].split("|")[0],
            "acceptance_criterion": f["recommendation"],
        }
        for f in findings
        if f["status"] != "mitigated"
    ]


def counts_by_severity(findings: list[dict[str, str]]) -> dict[str, int]:
    out = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for f in findings:
        if f["status"] == "mitigated":
            continue
        out[f["severity"]] = out.get(f["severity"], 0) + 1
    return out


def build_report(now: str, m: Metrics, findings: list[dict[str, str]], gates: dict[str, Any]) -> str:
    severity = counts_by_severity(findings)
    open_findings = [f for f in findings if f["status"] != "mitigated"]
    aud004 = next((f for f in findings if f.get("finding_id") == "AUD-004"), None)
    t3 = "mitigado" if aud004 and aud004.get("status") == "mitigated" else "pendiente"
    aud005 = next((f for f in findings if f.get("finding_id") == "AUD-005"), None)
    aud006 = next((f for f in findings if f.get("finding_id") == "AUD-006"), None)
    aud007 = next((f for f in findings if f.get("finding_id") == "AUD-007"), None)
    aud010 = next((f for f in findings if f.get("finding_id") == "AUD-010"), None)
    aud011 = next((f for f in findings if f.get("finding_id") == "AUD-011"), None)
    aud012 = next((f for f in findings if f.get("finding_id") == "AUD-012"), None)
    t4 = "mitigado" if aud005 and aud005.get("status") == "mitigated" else "pendiente benchmark"
    t5 = "mitigado" if aud006 and aud006.get("status") == "mitigated" else "pendiente"
    t6 = "mitigado" if aud007 and aud007.get("status") == "mitigated" else "pendiente"
    t8 = (
        "mitigado"
        if (
            aud010
            and aud010.get("status") == "mitigated"
            and aud011
            and aud011.get("status") == "mitigated"
            and m.has_lockfile
            and m.has_ci
        )
        else "pendiente"
    )
    t9 = "mitigado" if aud012 and aud012.get("status") == "mitigated" else "pendiente"
    lines = [
        "# Auditoria Integral v1",
        "",
        f"- Generado: {now}",
        "- Alcance: pipeline, datos derivados, reporte, UI, operacion/deploy.",
        "- Modelo de severidad: P0-P3.",
        "",
        "## Resumen ejecutivo",
        f"- Hallazgos abiertos: {len(open_findings)}",
        f"- Severidad: P0={severity['P0']}, P1={severity['P1']}, P2={severity['P2']}, P3={severity['P3']}",
        f"- Gate G1_data_integrity: {gates['gates']['G1_data_integrity']['status']}",
        f"- Gate G2_method_validity: {gates['gates']['G2_method_validity']['status']}",
        f"- Gate G3_reproducibility: {gates['gates']['G3_reproducibility']['status']}",
        f"- Gate G4_public_safety: {gates['gates']['G4_public_safety']['status']}",
        "",
        "## Scorecard de calidad de datos",
        f"- Posts: {m.posts_total:,}",
        f"- Comentarios: {m.comments_total:,}",
        f"- Duplicados comentarios: {m.comments_duplicates:,}",
        f"- Ventana temporal real (created_at): {m.created_window_days:.2f} dias",
        f"- Ventana de captura (run_time): {m.run_window_days:.2f} dias",
        f"- Runs observados: {m.runs}",
        "",
        "## Hallazgos por arista",
    ]
    grouped: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        grouped.setdefault(f["domain"], []).append(f)
    order = [
        "Claims e inferencia",
        "Linaje de datos",
        "Cobertura temporal",
        "Memetica",
        "Ontologia del lenguaje",
        "Sociologia y redes",
        "Interferencia",
        "Incidencia humana",
        "Transmision IA vs humana",
        "Reproducibilidad",
        "Ingenieria y mantenibilidad",
        "Seguridad y compliance",
        "Operacion deploy",
        "Producto publico",
    ]
    for domain in order:
        if domain not in grouped:
            continue
        lines.append(f"### {domain}")
        for f in grouped[domain]:
            lines.append(f"- [{f['severity']}] {f['finding_id']}: {f['issue']}")
            lines.append(f"  - Claim: {f['claim']}")
            lines.append(f"  - Impacto: {f['impact']}")
            lines.append(f"  - Evidencia: {f['evidence_ref']}")
            lines.append(f"  - Recomendacion: {f['recommendation']}")
            lines.append(f"  - Estado: {f['status']}")
        lines.append("")
    lines.extend(
        [
            "## Validaciones obligatorias (T1-T10)",
            "- T1: Temporalidad UI (created_at vs run_time) -> mitigado parcialmente.",
            "- T2: Cobertura de submolts -> requiere score de representatividad.",
            f"- T3: Top memes sin boilerplate -> {t3}.",
            f"- T4: Estabilidad ontologica multilengue -> {t4}.",
            f"- T5: Mention graph sin ruido -> {t5}.",
            f"- T6: Interferencia con separacion ruido/semantica -> {t6}.",
            "- T7: Sensibilidad embeddings -> pendiente.",
            f"- T8: Rerun parcial reproducible -> {t8}.",
            f"- T9: Secretos fuera de repos operativos -> {t9}.",
            "- T10: Consistencia reporte/UI de definiciones -> parcialmente cumplido.",
            "",
            "## Riesgos residuales",
            "- Interpretacion academica aun sensible a sesgos de heuristicas.",
            "- Riesgo operativo: deploy puede depender de pasos manuales si GitHub->Netlify no esta documentado.",
            "",
        ]
    )
    return "\n".join(lines)


def build_public_summary(now: str, findings: list[dict[str, str]], gates: dict[str, Any]) -> str:
    severity = counts_by_severity(findings)
    open_findings = [f for f in findings if f["status"] != "mitigated"]
    sev_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    open_sorted = sorted(open_findings, key=lambda f: (sev_rank.get(f["severity"], 9), f["finding_id"]))
    # Prefer P0/P1 if present; otherwise surface P2 so the public summary isn't empty.
    top_risks = [f for f in open_sorted if f["severity"] in {"P0", "P1"}][:5]
    if not top_risks:
        top_risks = open_sorted[:5]
    highest_open = open_sorted[0] if open_sorted else None
    top_sev = highest_open["severity"] if highest_open else "P0"
    lines = [
        "# Resumen publico de auditoria",
        "",
        f"- Fecha: {now}",
        f"- Hallazgos abiertos: {len(open_findings)}",
        f"- P0: {severity['P0']} | P1: {severity['P1']} | P2: {severity['P2']} | P3: {severity['P3']}",
        "",
        "## Estado de gates",
    ]
    for gate, payload in gates["gates"].items():
        lines.append(f"- {gate}: {payload['status']}")
    lines.extend(["", f"## Riesgos prioritarios (abiertos, top {top_sev})", ""])
    for f in top_risks:
        lines.append(f"- {f['finding_id']} [{f['severity']}] ({f['domain']}): {f['issue']}")
    lines.extend(
        [
            "",
            "## Proximo hito",
            (
                f"- Cerrar {highest_open['finding_id']} ({highest_open['domain']}) y regenerar auditoria."
                if highest_open
                else "- No hay hallazgos abiertos. Mantener gates en verde con auditorias recurrentes."
            ),
        ]
    )
    return "\n".join(lines)


def build_public_summary_json(now: str, findings: list[dict[str, str]], gates: dict[str, Any]) -> dict[str, Any]:
    open_findings = [f for f in findings if f["status"] != "mitigated"]
    severity = counts_by_severity(findings)
    sev_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    open_sorted = sorted(open_findings, key=lambda f: (sev_rank.get(f["severity"], 9), f["finding_id"]))
    top = [
        {"finding_id": f["finding_id"], "severity": f["severity"], "domain": f["domain"], "issue": f["issue"]}
        for f in open_sorted
        if f["severity"] in {"P0", "P1"}
    ][:6]
    if not top:
        top = [
            {"finding_id": f["finding_id"], "severity": f["severity"], "domain": f["domain"], "issue": f["issue"]}
            for f in open_sorted[:6]
        ]
    return {
        "generated_at": now,
        "model": "P0-P3",
        "open_findings": len(open_findings),
        "severity_counts": severity,
        "gates": {k: v["status"] for k, v in gates["gates"].items()},
        "top_risks": top,
    }


def main() -> None:
    now = datetime.now(UTC).isoformat()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    m = compute_metrics()
    claim_matrix = build_claim_matrix(m)
    lineage = build_data_lineage()
    evidence = build_evidence_index(now)
    findings = build_findings(m, claim_rows=len(claim_matrix), lineage_rows=len(lineage))
    gates = build_quality_gates(findings)
    backlog = build_backlog(findings)

    write_csv(
        AUDIT_DIR / "claim_matrix.csv",
        claim_matrix,
        ["claim_id", "claim", "evidence_datasets", "computation_notes", "limitations", "confidence"],
    )
    write_csv(
        AUDIT_DIR / "data_lineage.csv",
        lineage,
        [
            "metric_id",
            "ui_location",
            "metric_name",
            "definition",
            "time_axis",
            "source_files",
            "transform_script",
            "output_files",
            "notes",
        ],
    )

    write_csv(
        AUDIT_DIR / "audit_findings.csv",
        findings,
        [
            "finding_id",
            "severity",
            "domain",
            "claim",
            "issue",
            "evidence_ref",
            "impact",
            "recommendation",
            "owner",
            "status",
        ],
    )
    (AUDIT_DIR / "evidence_index.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    gate_lines = ["gates:"]
    for gate_name, gate_payload in gates["gates"].items():
        gate_lines.append(f"  {gate_name}:")
        gate_lines.append(f"    status: {gate_payload['status']}")
        gate_lines.append(f"    criterion: \"{gate_payload['criterion']}\"")
    (AUDIT_DIR / "quality_gates.yaml").write_text("\n".join(gate_lines) + "\n", encoding="utf-8")
    write_csv(
        AUDIT_DIR / "remediation_backlog.csv",
        backlog,
        ["task_id", "severity", "component", "fix_type", "effort_estimate", "dependency", "acceptance_criterion"],
    )
    (AUDIT_DIR / "audit_report.md").write_text(build_report(now, m, findings, gates), encoding="utf-8")
    (AUDIT_DIR / "public_summary.md").write_text(build_public_summary(now, findings, gates), encoding="utf-8")

    public_json = build_public_summary_json(now, findings, gates)
    (WEB_ROOT / "data" / "derived" / "public_audit_summary.json").write_text(
        json.dumps(public_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Audit package generated in {AUDIT_DIR}")
    print("Public summary written to web data/derived/public_audit_summary.json")


if __name__ == "__main__":
    main()
