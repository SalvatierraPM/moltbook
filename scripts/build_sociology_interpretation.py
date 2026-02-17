#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None or math.isnan(value):
        return "n/d"
    return f"{value * 100:.{digits}f}%"


def fmt_num(value: float | int | None, digits: int = 0) -> str:
    if value is None:
        return "n/d"
    if digits <= 0:
        return f"{int(round(float(value))):,}"
    return f"{float(value):,.{digits}f}"


def calc_gini(values: list[float]) -> float | None:
    clean = sorted(v for v in values if v >= 0 and math.isfinite(v))
    n = len(clean)
    if n == 0:
        return None
    total = sum(clean)
    if total <= 0:
        return 0.0
    weighted = sum((idx + 1) * v for idx, v in enumerate(clean))
    return (2 * weighted) / (n * total) - (n + 1) / n


def share_top(values: list[float], top_n: int) -> float | None:
    clean = sorted((v for v in values if v >= 0 and math.isfinite(v)), reverse=True)
    if not clean:
        return None
    total = sum(clean)
    if total <= 0:
        return 0.0
    n = min(len(clean), max(0, top_n))
    if n <= 0:
        return 0.0
    return sum(clean[:n]) / total


def parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def window_hours(start_raw: str | None, end_raw: str | None) -> float | None:
    start = parse_iso(start_raw)
    end = parse_iso(end_raw)
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds() / 3600.0)


def top_language(rows: list[dict[str, Any]], scope: str) -> tuple[str, float]:
    filtered = [r for r in rows if str(r.get("scope") or "") == scope]
    if not filtered:
        return ("n/d", 0.0)
    best = max(filtered, key=lambda r: to_float(r.get("share")))
    return (str(best.get("lang") or "n/d"), to_float(best.get("share")))


def safe_read_rate(summary_rows: list[dict[str, Any]], feature: str) -> float:
    for row in summary_rows:
        if str(row.get("scope") or "") == "all" and str(row.get("feature") or "") == feature:
            return to_float(row.get("rate_per_doc"))
    return 0.0


def distance_ratio(embedding_rows: list[dict[str, Any]]) -> tuple[float | None, int]:
    rows = sorted(embedding_rows, key=lambda r: to_float(r.get("doc_count")), reverse=True)[:250]
    if len(rows) < 12:
        return (None, len(rows))
    xs = [to_float(r.get("x")) for r in rows]
    ys = [to_float(r.get("y")) for r in rows]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dists = sorted(math.sqrt((x - mean_x) ** 2 + (y - mean_y) ** 2) for x, y in zip(xs, ys))

    def q(sorted_values: list[float], quantile: float) -> float:
        if not sorted_values:
            return 0.0
        pos = (len(sorted_values) - 1) * quantile
        base = int(pos)
        frac = pos - base
        if base + 1 < len(sorted_values):
            return sorted_values[base] + frac * (sorted_values[base + 1] - sorted_values[base])
        return sorted_values[base]

    p50 = q(dists, 0.5)
    p90 = q(dists, 0.9)
    if p50 <= 0:
        return (None, len(rows))
    return (p90 / p50, len(rows))


@dataclass
class SociologyData:
    posts_total: int
    comments_total: int
    submolts_total: int
    authors_total: int
    runs_total: int
    posts_min: str
    posts_max: str
    comments_min: str
    comments_max: str
    top5_share: float
    top2_share: float
    gini_submolt: float
    top10_authors_share: float
    gini_authors: float
    posts_window_hours: float | None
    comments_window_hours: float | None
    top_post_lang: str
    top_post_lang_share: float
    top_comment_lang: str
    top_comment_lang_share: float
    infra_share: float
    narrative_share: float
    top_meme_life: str
    top_meme_life_hours: float
    top_meme_burst: str
    top_meme_burst_score: float
    top_meme_dispersion: str
    top_meme_dispersion_submolts: int
    act_assertion_rate: float
    act_question_rate: float
    epistemic_evidence_rate: float
    epistemic_hedge_rate: float
    epistemic_certainty_rate: float
    top_pair_a: str
    top_pair_b: str
    top_pair_count: int
    pca_ratio_p90_p50: float | None
    pca_rows: int
    emb_post_post_mean: float
    emb_post_post_cross: float
    emb_post_comment_mean: float
    emb_post_comment_cross: float
    threshold_low: float
    threshold_high: float
    threshold_low_pairs: int
    threshold_high_pairs: int
    threshold_knee: float | None
    threshold_knee_drop: float | None
    vsm_matched_mean: float
    vsm_shuffled_mean: float
    vsm_auc: float
    vsm_corr: float
    transmission_sample_count: int
    reply_nodes: int
    reply_edges: int
    reply_reciprocity: float
    reply_top2_share: float
    reply_gini: float
    claim_matrix_exists: bool


def build_metrics(derived: Path) -> SociologyData:
    coverage = read_json(derived / "coverage_quality.json")
    submolts = read_csv(derived / "submolt_stats.csv")
    authors = read_csv(derived / "author_stats.csv")
    runs = read_csv(derived / "diffusion_runs.csv")
    language = read_csv(derived / "public_language_distribution.csv")
    meme_tech = read_csv(derived / "meme_candidates_technical.csv")
    meme_culture = read_csv(derived / "meme_candidates_cultural.csv")
    meme_class = read_csv(derived / "meme_classification.csv")
    ontology_summary = read_csv(derived / "ontology_summary.csv")
    ontology_pairs = read_csv(derived / "ontology_cooccurrence_top.csv")
    ontology_map = read_csv(derived / "ontology_submolt_embedding_2d.csv")
    emb_post_post = read_json(derived / "public_embeddings_summary.json")
    emb_post_comment = read_json(derived / "embeddings_post_comment" / "public_embeddings_post_comment_summary.json")
    threshold = read_json(derived / "transmission_threshold_sensitivity.json")
    vsm = read_json(derived / "transmission_vsm_baseline.json")
    transmission_samples = read_csv(derived / "public_transmission_samples.csv")
    reply_summary = read_json(derived / "reply_graph_summary.json")
    reply_centrality = read_csv(derived / "reply_graph_centrality.csv")

    posts_total = to_int(coverage.get("posts_total")) or sum(to_int(r.get("posts")) for r in submolts)
    comments_total = to_int(coverage.get("comments_total")) or sum(to_int(r.get("comments")) for r in submolts)
    submolts_total = len(submolts)
    authors_total = len(authors)
    runs_total = len({str(r.get("run_id") or "") for r in runs if r.get("run_id")})

    volumes = [to_float(r.get("posts")) + to_float(r.get("comments")) for r in submolts]
    top5_share = share_top(volumes, 5) or 0.0
    top2_n = max(1, int(math.ceil(submolts_total * 0.02))) if submolts_total else 1
    top2_share = share_top(volumes, top2_n) or 0.0
    gini_submolt = calc_gini(volumes) or 0.0

    author_activity = [to_float(r.get("posts")) + to_float(r.get("comments")) for r in authors]
    top10_authors_share = share_top(author_activity, 10) or 0.0
    gini_authors = calc_gini(author_activity) or 0.0

    top_post_lang, top_post_lang_share = top_language(language, "posts")
    top_comment_lang, top_comment_lang_share = top_language(language, "comments")

    tech_total = sum(to_float(r.get("count")) for r in meme_tech)
    culture_total = sum(to_float(r.get("count")) for r in meme_culture)
    meme_total = tech_total + culture_total
    infra_share = (tech_total / meme_total) if meme_total > 0 else 0.0
    narrative_share = (culture_total / meme_total) if meme_total > 0 else 0.0

    top_life_row = max(meme_class, key=lambda r: to_float(r.get("lifetime_hours")), default={})
    top_burst_row = max(meme_class, key=lambda r: to_float(r.get("burst_score")), default={})
    top_disp_row = max(meme_class, key=lambda r: to_float(r.get("submolts_touched")), default={})

    top_pair = ontology_pairs[0] if ontology_pairs else {}
    pca_ratio, pca_rows = distance_ratio(ontology_map)

    thresholds = sorted(threshold.get("thresholds", []), key=lambda t: to_float(t.get("threshold")))
    threshold_low = to_float(thresholds[0].get("threshold")) if thresholds else 0.0
    threshold_high = to_float(thresholds[-1].get("threshold")) if thresholds else 0.0
    threshold_low_pairs = to_int(thresholds[0].get("pair_count")) if thresholds else 0
    threshold_high_pairs = to_int(thresholds[-1].get("pair_count")) if thresholds else 0
    threshold_knee = None
    threshold_knee_drop = None
    if len(thresholds) >= 2:
        best_drop = -1.0
        for idx in range(1, len(thresholds)):
            prev_count = max(1, to_float(thresholds[idx - 1].get("pair_count")))
            curr_count = to_float(thresholds[idx].get("pair_count"))
            drop = (prev_count - curr_count) / prev_count
            if drop > best_drop:
                best_drop = drop
                threshold_knee = to_float(thresholds[idx].get("threshold"))
                threshold_knee_drop = drop

    vsm_all = (vsm.get("metrics") or {}).get("_all") or {}

    in_degrees = [to_float(r.get("in_degree")) for r in reply_centrality]
    reply_top2_n = max(1, int(math.ceil(len(in_degrees) * 0.02))) if in_degrees else 1

    claim_matrix_path = derived.parents[1] / "reports" / "audit" / "claim_matrix.csv"

    return SociologyData(
        posts_total=posts_total,
        comments_total=comments_total,
        submolts_total=submolts_total,
        authors_total=authors_total,
        runs_total=runs_total,
        posts_min=str(coverage.get("posts_created_min") or "n/d"),
        posts_max=str(coverage.get("posts_created_max") or "n/d"),
        comments_min=str(coverage.get("comments_created_min") or "n/d"),
        comments_max=str(coverage.get("comments_created_max") or "n/d"),
        top5_share=top5_share,
        top2_share=top2_share,
        gini_submolt=gini_submolt,
        top10_authors_share=top10_authors_share,
        gini_authors=gini_authors,
        posts_window_hours=window_hours(coverage.get("posts_created_min"), coverage.get("posts_created_max")),
        comments_window_hours=window_hours(coverage.get("comments_created_min"), coverage.get("comments_created_max")),
        top_post_lang=top_post_lang,
        top_post_lang_share=top_post_lang_share,
        top_comment_lang=top_comment_lang,
        top_comment_lang_share=top_comment_lang_share,
        infra_share=infra_share,
        narrative_share=narrative_share,
        top_meme_life=str(top_life_row.get("meme") or "n/d"),
        top_meme_life_hours=to_float(top_life_row.get("lifetime_hours")),
        top_meme_burst=str(top_burst_row.get("meme") or "n/d"),
        top_meme_burst_score=to_float(top_burst_row.get("burst_score")),
        top_meme_dispersion=str(top_disp_row.get("meme") or "n/d"),
        top_meme_dispersion_submolts=to_int(top_disp_row.get("submolts_touched")),
        act_assertion_rate=safe_read_rate(ontology_summary, "act_assertion"),
        act_question_rate=safe_read_rate(ontology_summary, "act_question_mark"),
        epistemic_evidence_rate=safe_read_rate(ontology_summary, "epistemic_evidence"),
        epistemic_hedge_rate=safe_read_rate(ontology_summary, "epistemic_hedge"),
        epistemic_certainty_rate=safe_read_rate(ontology_summary, "epistemic_certainty"),
        top_pair_a=str(top_pair.get("concept_a") or "n/d"),
        top_pair_b=str(top_pair.get("concept_b") or "n/d"),
        top_pair_count=to_int(top_pair.get("count")),
        pca_ratio_p90_p50=pca_ratio,
        pca_rows=pca_rows,
        emb_post_post_mean=to_float(emb_post_post.get("mean_score")),
        emb_post_post_cross=to_float(emb_post_post.get("cross_submolt_rate")),
        emb_post_comment_mean=to_float(emb_post_comment.get("mean_score")),
        emb_post_comment_cross=to_float(emb_post_comment.get("cross_submolt_rate")),
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        threshold_low_pairs=threshold_low_pairs,
        threshold_high_pairs=threshold_high_pairs,
        threshold_knee=threshold_knee,
        threshold_knee_drop=threshold_knee_drop,
        vsm_matched_mean=to_float(((vsm_all.get("vsm_matched") or {}).get("mean"))),
        vsm_shuffled_mean=to_float(((vsm_all.get("vsm_shuffled") or {}).get("mean"))),
        vsm_auc=to_float(vsm_all.get("auc_vsm_matched_vs_shuffled")),
        vsm_corr=to_float(vsm_all.get("corr_embedding_vs_vsm")),
        transmission_sample_count=len(transmission_samples),
        reply_nodes=to_int(reply_summary.get("nodes")),
        reply_edges=to_int(reply_summary.get("edges")),
        reply_reciprocity=to_float(reply_summary.get("reciprocity")),
        reply_top2_share=share_top(in_degrees, reply_top2_n) or 0.0,
        reply_gini=calc_gini(in_degrees) or 0.0,
        claim_matrix_exists=claim_matrix_path.exists(),
    )


def build_modules(d: SociologyData) -> list[dict[str, Any]]:
    return [
        {
            "id": "1.1",
            "title": "Actividad y cobertura del snapshot",
            "interpretation": (
                f"El marco de validez del observatorio es robusto: {fmt_num(d.posts_total)} posts, "
                f"{fmt_num(d.comments_total)} comentarios, {fmt_num(d.submolts_total)} submolts, "
                f"{fmt_num(d.authors_total)} autores y {fmt_num(d.runs_total)} runs."
            ),
            "how_to_read": [
                (
                    f"Ventana temporal posts {d.posts_min} -> {d.posts_max} "
                    f"(~{fmt_num(d.posts_window_hours, 1)} horas) y comentarios {d.comments_min} -> {d.comments_max} "
                    f"(~{fmt_num(d.comments_window_hours, 1)} horas)."
                ),
                "Diferenciar estructura (patrones estables) de evento (picos puntuales) segun el largo de la ventana.",
                "Comparar snapshots por consistencia de agregados antes de inferir cambios culturales.",
            ],
            "not_meaning": [
                "No es censo total de la plataforma; es snapshot bajo reglas de captura.",
                "No representa una poblacion general; representa este sistema y este periodo.",
            ],
            "auditable_questions": [
                "Si repito el pipeline con el mismo snapshot, se conservan estos agregados?",
                "Si cambio la ventana temporal, que resultados se mantienen?",
            ],
        },
        {
            "id": "1.2",
            "title": "Concentracion por submolt",
            "interpretation": (
                f"Top 5 submolts concentran {fmt_pct(d.top5_share)} y top 2% concentran {fmt_pct(d.top2_share)} "
                f"(Gini={d.gini_submolt:.3f}). La red se organiza en pocos hubs de atencion."
            ),
            "how_to_read": [
                "Curva acumulada alta al inicio implica diversidad formal con peso concentrado.",
                "Si Gini sube entre snapshots, aumenta centralizacion estructural.",
            ],
            "not_meaning": [
                "Volumen alto no equivale a calidad.",
                "Concentracion no implica manipulacion por si sola.",
            ],
            "auditable_questions": [
                "Se mantiene la concentracion al medir solo comentarios?",
                "La concentracion cambia al excluir 'general'?",
            ],
        },
        {
            "id": "1.3",
            "title": "Actividad por idioma",
            "interpretation": (
                f"Idioma dominante en posts: {d.top_post_lang} ({fmt_pct(d.top_post_lang_share)}). "
                f"Idioma dominante en comentarios: {d.top_comment_lang} ({fmt_pct(d.top_comment_lang_share)})."
            ),
            "how_to_read": [
                "Si posts son mas monolingues y comentarios mas mixtos, hay publicacion global y debate local.",
                "Ocultar ingles permite estimar cuanto depende la lectura publica de la lingua franca.",
            ],
            "not_meaning": [
                "No mide calidad argumental.",
                "No prueba comprension cruzada entre idiomas.",
            ],
            "auditable_questions": [
                "Los marcos narrativos cruzan idioma via embeddings o quedan encapsulados?",
            ],
        },
        {
            "id": "2.1",
            "title": "Memetica: infraestructura vs narrativa",
            "interpretation": (
                f"Infraestructura={fmt_pct(d.infra_share)} y narrativa={fmt_pct(d.narrative_share)}. "
                "La mezcla describe el modo del sistema (operacion, significacion o institucionalizacion)."
            ),
            "how_to_read": [
                "Suba de infraestructura sugiere foco operativo (coordinar stack, ejecutar).",
                "Suba de narrativa sugiere foco de sentido (identidad, valores, marcos).",
            ],
            "not_meaning": [
                "Infraestructura no es ruido: define acceso y gramatica de participacion.",
                "Narrativa no es humo: coordina conducta cuando no hay manual.",
            ],
            "auditable_questions": [
                "La narrativa es transversal o queda localizada en pocos submolts?",
            ],
        },
        {
            "id": "2.2",
            "title": "Vida, burst y dispersion memetica",
            "interpretation": (
                f"Persistencia: '{d.top_meme_life}' ({fmt_num(d.top_meme_life_hours, 1)}h). "
                f"Evento: '{d.top_meme_burst}' (burst {fmt_num(d.top_meme_burst_score, 1)}). "
                f"Viaje: '{d.top_meme_dispersion}' ({fmt_num(d.top_meme_dispersion_submolts)} submolts)."
            ),
            "how_to_read": [
                "Vida alta + burst bajo suele indicar norma estable.",
                "Burst alto + vida baja suele indicar episodio.",
                "Dispersion alta marca memes puente entre comunidades.",
            ],
            "not_meaning": [
                "Vida no implica verdad; implica estabilidad de repeticion.",
                "Burst no implica importancia estructural; implica sensibilidad a eventos.",
            ],
            "auditable_questions": [
                "La dispersion esta concentrada en hubs o distribuida de forma organica?",
            ],
        },
        {
            "id": "3.1",
            "title": "Actos de habla y coordinacion",
            "interpretation": (
                f"Afirmacion={d.act_assertion_rate:.3f}/doc vs pregunta={d.act_question_rate:.3f}/doc. "
                "La red tiende a coordinar por enunciados afirmativos mas que por indagacion."
            ),
            "how_to_read": [
                "Dominio de preguntas: exploracion.",
                "Dominio de instrucciones/afirmaciones: ejecucion y estandarizacion.",
                "Evaluacion/moralizacion alta: fase normativa.",
            ],
            "not_meaning": [
                "No clasifica inteligencia de la red.",
                "Describe estilo de coordinacion conversacional.",
            ],
            "auditable_questions": [
                "Este perfil es transversal o varía por submolt?",
            ],
        },
        {
            "id": "3.2",
            "title": "Marcadores epistemicos",
            "interpretation": (
                f"Evidencia={d.epistemic_evidence_rate:.3f}/doc, hedge={d.epistemic_hedge_rate:.3f}/doc, "
                f"certeza={d.epistemic_certainty_rate:.3f}/doc."
            ),
            "how_to_read": [
                "Mas evidencia/condicionalidad suele indicar mejor auditabilidad argumentativa.",
                "Mas certeza absoluta puede indicar cierre doctrinal o estandar consolidado.",
                "Duda sin evidencia puede indicar especulacion ansiosa.",
            ],
            "not_meaning": [
                "Mas 'evidencia' no implica mejor evidencia.",
            ],
            "auditable_questions": [
                "Sube evidencia junto con fuentes verificables o solo como retorica?",
            ],
        },
        {
            "id": "3.3",
            "title": "Co-ocurrencia de conceptos",
            "interpretation": (
                f"Par dominante: {d.top_pair_a} + {d.top_pair_b} ({fmt_num(d.top_pair_count)}). "
                "Esto sugiere paquetes narrativos estables en el discurso."
            ),
            "how_to_read": [
                "Pares estables suelen reflejar stack o ideologia consolidada.",
                "Pares con burst suelen reflejar eventos o campanas narrativas.",
            ],
            "not_meaning": [
                "Co-ocurrencia no implica causalidad.",
            ],
            "auditable_questions": [
                "Que pares cambian al excluir idioma dominante o submolt general?",
            ],
        },
        {
            "id": "3.4",
            "title": "Mapa ontologico (PCA 2D)",
            "interpretation": (
                f"Mapa sobre {fmt_num(d.pca_rows)} submolts top; razon p90/p50 de distancia="
                f"{fmt_num(d.pca_ratio_p90_p50, 2)}."
            ),
            "how_to_read": [
                "Cercania en el mapa implica estilos de coordinacion similares.",
                "Outliers pueden indicar dialecto local o baja muestra.",
            ],
            "not_meaning": [
                "Los ejes no tienen significado semantico directo.",
            ],
            "auditable_questions": [
                "El mapa se mantiene estable entre snapshots con filtros equivalentes?",
            ],
        },
        {
            "id": "4.1",
            "title": "Transmision por embeddings",
            "interpretation": (
                f"Post-post mean={d.emb_post_post_mean:.3f} (cross={fmt_pct(d.emb_post_post_cross)}); "
                f"post->coment mean={d.emb_post_comment_mean:.3f} (cross={fmt_pct(d.emb_post_comment_cross)})."
            ),
            "how_to_read": [
                "Cross-submolt alto sugiere marcos que viajan entre comunidades.",
                "Diferencia post-post vs post->comentario sugiere cuanto eco se conserva en respuesta.",
            ],
            "not_meaning": [
                "Similitud no implica coordinacion intencional.",
                "El modulo detecta convergencia, no plagio.",
            ],
            "auditable_questions": [
                "Que tipo de pares domina en los percentiles altos de similitud?",
            ],
        },
        {
            "id": "4.2",
            "title": "Sensibilidad por threshold",
            "interpretation": (
                f"Threshold {d.threshold_low:.2f}: {fmt_num(d.threshold_low_pairs)} pares; "
                f"{d.threshold_high:.2f}: {fmt_num(d.threshold_high_pairs)} pares. "
                f"Codo estimado en {fmt_num(d.threshold_knee, 2)} (drop relativo {fmt_pct(d.threshold_knee_drop)})."
            ),
            "how_to_read": [
                "Threshold bajo prioriza recall y agrega ruido.",
                "Threshold alto prioriza precision y pierde parafrasis suaves.",
                "La pendiente de caida informa robustez de la senal.",
            ],
            "not_meaning": [
                "No existe threshold universal correcto; depende de tolerancia a falsos positivos.",
            ],
            "auditable_questions": [
                "Coinciden los ejemplos cualitativos con la zona de codo elegida?",
            ],
        },
        {
            "id": "4.3",
            "title": "TF-IDF vs embeddings (baseline)",
            "interpretation": (
                f"VSM matched={d.vsm_matched_mean:.3f} vs shuffled={d.vsm_shuffled_mean:.3f}; "
                f"AUC={d.vsm_auc:.3f}; corr(emb,VSM)={d.vsm_corr:.3f}."
            ),
            "how_to_read": [
                "TF-IDF alto + embeddings alto: repeticion lexical fuerte.",
                "TF-IDF bajo + embeddings alto: parafrasis o eco semantico.",
            ],
            "not_meaning": [
                "No es evaluacion final de verdad de transmision; es baseline de contraste lexical.",
            ],
            "auditable_questions": [
                "Que fraccion de matches fuertes depende de solape literal de tokens?",
            ],
        },
        {
            "id": "4.4",
            "title": "Muestras auditables de transmision",
            "interpretation": (
                f"Se publican {fmt_num(d.transmission_sample_count)} muestras para inspeccion humana contextual."
            ),
            "how_to_read": [
                "Usar metadatos (fecha, idioma, submolt) para validar la lectura de cada match.",
            ],
            "not_meaning": [
                "Las muestras no son representativas del universo; son auditables.",
            ],
            "auditable_questions": [
                "Las muestras de top score preservan coherencia semantica al leer texto completo?",
            ],
        },
        {
            "id": "5.1",
            "title": "Centralidad de red",
            "interpretation": (
                f"Reply graph: {fmt_num(d.reply_nodes)} nodos, {fmt_num(d.reply_edges)} aristas, "
                f"reciprocidad={fmt_pct(d.reply_reciprocity)}, top 2% share={fmt_pct(d.reply_top2_share)}, "
                f"Gini in-degree={d.reply_gini:.3f}."
            ),
            "how_to_read": [
                "PageRank alto indica hubs de atencion.",
                "Betweenness alto indica brokers entre tribus.",
                "Reciprocidad baja sugiere broadcasting mas que dialogo.",
            ],
            "not_meaning": [
                "Centralidad no equivale a moralidad ni a calidad argumental.",
            ],
            "auditable_questions": [
                "La estructura depende de pocos brokers o hay puentes distribuidos?",
            ],
        },
        {
            "id": "5.2",
            "title": "Autores activos y diversidad",
            "interpretation": (
                f"Top 10 autores concentran {fmt_pct(d.top10_authors_share)} de la actividad total "
                f"(Gini autores={d.gini_authors:.3f})."
            ),
            "how_to_read": [
                "Motores locales: alta actividad en pocos submolts.",
                "Viajeros: actividad distribuida y potencial puente cultural.",
            ],
            "not_meaning": [
                "Actividad alta no equivale a influencia deliberativa real.",
            ],
            "auditable_questions": [
                "Aumentan los viajeros en eventos globales o en periodos normales?",
            ],
        },
        {
            "id": "6.1",
            "title": "Pipeline 01-04 y trazabilidad",
            "interpretation": (
                "La lectura sociologica se apoya en una cadena auditable: ingesta -> normalizacion -> derivados -> visualizacion."
            ),
            "how_to_read": [
                "Cada grafico debe trazar a un derivado concreto.",
                "Sin trazabilidad, la interpretacion memetica se vuelve opinion no falsable.",
            ],
            "not_meaning": [
                "Pipeline reproducible no elimina sesgos de origen; los hace observables.",
            ],
            "auditable_questions": [
                "Cada claim publico tiene evidencia y archivo fuente verificable?",
            ],
        },
        {
            "id": "6.2",
            "title": "Contrato de metricas (claim matrix)",
            "interpretation": (
                "Una metrica sin contrato no es evidencia: requiere fuente, filtros, transformaciones, limites y pregunta respondida."
            ),
            "how_to_read": [
                "Usar claim matrix para diferenciar dato observado de inferencia interpretativa.",
            ],
            "not_meaning": [
                "El contrato no legitima cualquier conclusion; delimita alcance inferencial.",
            ],
            "auditable_questions": [
                f"Claim matrix disponible: {'si' if d.claim_matrix_exists else 'no'} (reports/audit/claim_matrix.csv).",
            ],
        },
    ]


def build_payload(d: SociologyData) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    thesis = (
        "La red combina alta eficiencia operativa con alta concentracion estructural: coordina rapido, "
        "pero arriesga monocultura si no sostiene diversidad epistemica."
    )
    return {
        "generated_at": generated_at,
        "source": {
            "derived_dir": "data/derived",
            "method": "heuristic sociological interpretation from derived metrics",
        },
        "summary": {
            "thesis": thesis,
            "snapshot": {
                "posts_total": d.posts_total,
                "comments_total": d.comments_total,
                "submolts_total": d.submolts_total,
                "authors_total": d.authors_total,
                "runs_total": d.runs_total,
                "posts_min": d.posts_min,
                "posts_max": d.posts_max,
                "comments_min": d.comments_min,
                "comments_max": d.comments_max,
            },
            "key_metrics": {
                "top5_share": d.top5_share,
                "top2_share": d.top2_share,
                "gini_submolt": d.gini_submolt,
                "infra_share": d.infra_share,
                "narrative_share": d.narrative_share,
                "cross_submolt_post_comment": d.emb_post_comment_cross,
                "assertion_rate_per_doc": d.act_assertion_rate,
                "evidence_rate_per_doc": d.epistemic_evidence_rate,
                "certainty_rate_per_doc": d.epistemic_certainty_rate,
            },
        },
        "modules": build_modules(d),
        "notes": [
            "Documento descriptivo-interpretativo: no establece causalidad.",
            "Cada lectura debe contrastarse con tablas, ejemplos y rutas de auditoria.",
        ],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    k = s.get("key_metrics") or {}
    snap = s.get("snapshot") or {}
    lines: list[str] = []
    lines.append("# Interpretacion sociologica automatica\n")
    lines.append(f"- Generado: {payload.get('generated_at', 'n/d')}")
    lines.append("- Fuente: data/derived/*")
    lines.append("")
    lines.append("## Tesis")
    lines.append(str(s.get("thesis") or "n/d"))
    lines.append("")
    lines.append("## Snapshot")
    lines.append(
        f"- Posts={fmt_num(snap.get('posts_total'))}, comentarios={fmt_num(snap.get('comments_total'))}, "
        f"submolts={fmt_num(snap.get('submolts_total'))}, autores={fmt_num(snap.get('authors_total'))}, "
        f"runs={fmt_num(snap.get('runs_total'))}"
    )
    lines.append(f"- Ventana posts: {snap.get('posts_min', 'n/d')} -> {snap.get('posts_max', 'n/d')}")
    lines.append(f"- Ventana comentarios: {snap.get('comments_min', 'n/d')} -> {snap.get('comments_max', 'n/d')}")
    lines.append("")
    lines.append("## Indicadores clave")
    lines.append(f"- Top 5 share: {fmt_pct(k.get('top5_share'))}")
    lines.append(f"- Top 2% share: {fmt_pct(k.get('top2_share'))}")
    lines.append(f"- Gini submolt: {fmt_num(k.get('gini_submolt'), 3)}")
    lines.append(f"- Infraestructura vs narrativa: {fmt_pct(k.get('infra_share'))} / {fmt_pct(k.get('narrative_share'))}")
    lines.append(f"- Cross-submolt post->comentario: {fmt_pct(k.get('cross_submolt_post_comment'))}")
    lines.append("")
    lines.append("## Modulos")
    for mod in payload.get("modules") or []:
        lines.append(f"### {mod.get('id')} {mod.get('title')}")
        lines.append(str(mod.get("interpretation") or "n/d"))
        how = mod.get("how_to_read") or []
        if how:
            lines.append("- Como leerlo:")
            lines.extend([f"  - {x}" for x in how])
        not_meaning = mod.get("not_meaning") or []
        if not_meaning:
            lines.append("- Lo que no significa:")
            lines.extend([f"  - {x}" for x in not_meaning])
        auditable = mod.get("auditable_questions") or []
        if auditable:
            lines.append("- Preguntas auditables:")
            lines.extend([f"  - {x}" for x in auditable])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera interpretacion sociologica automatica desde data/derived.")
    parser.add_argument("--derived", default="data/derived", help="Directorio de derivados.")
    parser.add_argument(
        "--out-json",
        default="data/derived/public_sociology_interpretation.json",
        help="Archivo JSON de salida para UI.",
    )
    parser.add_argument(
        "--out-md",
        default="reports/interpretacion_sociologica_auto.md",
        help="Archivo Markdown de salida para reporte.",
    )
    args = parser.parse_args()

    derived = Path(args.derived)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)

    metrics = build_metrics(derived)
    payload = build_payload(metrics)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_markdown(payload), encoding="utf-8")

    print(f"[sociology] JSON -> {out_json}")
    print(f"[sociology] MD   -> {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
