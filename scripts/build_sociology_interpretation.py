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
            "what_it_is": "Este bloque responde una pregunta simple: cuanta informacion real entra al analisis y en que fechas.",
            "why_it_matters": "Si no se entiende el tamano del snapshot, cualquier conclusion posterior puede sobredimensionarse o quedarse corta.",
            "interpretation": (
                f"El snapshot actual incluye {fmt_num(d.posts_total)} posts, {fmt_num(d.comments_total)} comentarios, "
                f"{fmt_num(d.submolts_total)} submolts, {fmt_num(d.authors_total)} autores y {fmt_num(d.runs_total)} runs. "
                "Con este volumen ya se pueden observar regularidades estructurales, pero sigue siendo una foto temporal."
            ),
            "terms": [
                "Snapshot: foto de datos tomada en una ventana de tiempo especifica.",
                "Run: una ejecucion de recoleccion del scraper.",
                "Ventana temporal: fecha minima y maxima incluidas en el snapshot.",
            ],
            "how_to_read": [
                (
                    f"Primero, verificar ventana de posts ({d.posts_min} -> {d.posts_max}, ~{fmt_num(d.posts_window_hours, 1)} horas) "
                    f"y de comentarios ({d.comments_min} -> {d.comments_max}, ~{fmt_num(d.comments_window_hours, 1)} horas)."
                ),
                "Segundo, separar patrones estables (estructura) de picos puntuales (evento).",
                "Tercero, antes de comparar con otro periodo, confirmar que la cobertura sea equivalente.",
            ],
            "common_misreads": [
                "Confundir snapshot con censo completo de la plataforma.",
                "Asumir que mas volumen siempre significa mas diversidad.",
            ],
            "not_meaning": [
                "No es censo total de la plataforma; es un corte temporal bajo reglas de captura.",
                "No representa una poblacion general; representa este sistema en este periodo.",
            ],
            "auditable_questions": [
                "Si repito el pipeline con este mismo snapshot, se conservan los agregados principales?",
                "Si cambio la ventana temporal, que hallazgos se mantienen y cuales no?",
            ],
        },
        {
            "id": "1.2",
            "title": "Concentracion por submolt",
            "what_it_is": "Mide cuanto del volumen total se acumula en pocas comunidades.",
            "why_it_matters": "Una red puede parecer grande por cantidad de submolts, pero seguir concentrada en pocos centros de atencion.",
            "interpretation": (
                f"En este snapshot, el top 5 concentra {fmt_pct(d.top5_share)} del volumen total y el top 2% concentra {fmt_pct(d.top2_share)} "
                f"(Gini={d.gini_submolt:.3f}). Esto describe una estructura con muchos espacios formales, pero con trafico muy desigual."
            ),
            "terms": [
                "Top 5 share: porcentaje del volumen total acumulado por las 5 comunidades mas grandes.",
                "Top 2% share: porcentaje acumulado por el 2% superior de comunidades.",
                "Gini: indicador de desigualdad (0 = muy distribuido, 1 = extremadamente concentrado).",
            ],
            "how_to_read": [
                "Si la curva acumulada sube muy rapido al inicio, la atencion esta centralizada.",
                "Si el Gini sube entre snapshots, aumenta la concentracion estructural.",
                "Comparar resultados en posts y comentarios por separado evita sesgo de una sola metrica.",
            ],
            "common_misreads": [
                "Tratar volumen como sinonimo de calidad o valor.",
                "Leer concentracion como prueba automatica de manipulacion.",
            ],
            "not_meaning": [
                "Volumen alto no equivale a calidad.",
                "Concentracion no implica manipulacion por si sola.",
            ],
            "auditable_questions": [
                "La concentracion se mantiene cuando se analiza solo comentarios?",
                "El patron cambia significativamente al excluir 'general'?",
            ],
        },
        {
            "id": "1.3",
            "title": "Actividad por idioma",
            "what_it_is": "Describe en que idiomas se publica y en que idiomas se responde.",
            "why_it_matters": "El idioma condiciona quien participa, quien responde y como se difunden las ideas entre comunidades.",
            "interpretation": (
                f"Idioma dominante en posts: {d.top_post_lang} ({fmt_pct(d.top_post_lang_share)}). "
                f"Idioma dominante en comentarios: {d.top_comment_lang} ({fmt_pct(d.top_comment_lang_share)}). "
                "La lectura de influencia cultural debe considerar este sesgo de idioma base."
            ),
            "terms": [
                "Share por idioma: proporcion relativa de documentos en cada idioma.",
                "Posts vs comentarios: diferencia entre lenguaje de emision y lenguaje de reaccion.",
                "Lingua franca: idioma dominante que permite coordinacion amplia.",
            ],
            "how_to_read": [
                "Comparar posts y comentarios permite ver si la conversacion se abre o se cierra linguisticamente.",
                "Ocultar temporalmente el idioma dominante ayuda a ver estructuras que quedan ocultas.",
                "Cruzar con transmision semantica permite evaluar si las ideas cruzan barreras de idioma.",
            ],
            "common_misreads": [
                "Confundir frecuencia de idioma con calidad argumental.",
                "Asumir comprension intercultural solo por coexistencia de idiomas.",
            ],
            "not_meaning": [
                "No mide calidad argumental.",
                "No prueba comprension cruzada entre idiomas.",
            ],
            "auditable_questions": [
                "Los marcos narrativos cruzan idiomas via embeddings o quedan encapsulados?",
            ],
        },
        {
            "id": "2.1",
            "title": "Memetica: infraestructura vs narrativa",
            "what_it_is": "Separa memes de operacion tecnica de memes de significado cultural.",
            "why_it_matters": "Permite ver si el sistema esta mas enfocado en ejecutar (infraestructura) o en construir marcos de sentido (narrativa).",
            "interpretation": (
                f"El balance actual es infraestructura={fmt_pct(d.infra_share)} y narrativa={fmt_pct(d.narrative_share)}. "
                "Este mix muestra como la red combina coordinacion tecnica diaria con conversaciones de identidad, valores y sentido."
            ),
            "terms": [
                "Meme de infraestructura: patron tecnico repetido (api, tooling, stack).",
                "Meme narrativo: patron de significado compartido (valores, identidad, relato).",
                "Share memetico: peso relativo de cada familia de memes en el total observado.",
            ],
            "how_to_read": [
                "Si sube infraestructura, normalmente crece la coordinacion operativa.",
                "Si sube narrativa, normalmente crece la disputa o consolidacion de marcos de sentido.",
                "La comparacion entre snapshots muestra cambios de fase en la conversacion.",
            ],
            "common_misreads": [
                "Tratar infraestructura como ruido descartable.",
                "Tratar narrativa como decoracion sin efectos practicos.",
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
            "what_it_is": "Combina tres lecturas: cuanto dura un meme, cuan brusco es su pico y cuantas comunidades alcanza.",
            "why_it_matters": "Distingue normas estables de eventos cortos y permite ver que memes funcionan como puentes entre comunidades.",
            "interpretation": (
                f"En este corte: persistencia alta en '{d.top_meme_life}' ({fmt_num(d.top_meme_life_hours, 1)}h), "
                f"evento de mayor burst en '{d.top_meme_burst}' (score {fmt_num(d.top_meme_burst_score, 1)}) y "
                f"mayor dispersion en '{d.top_meme_dispersion}' ({fmt_num(d.top_meme_dispersion_submolts)} submolts)."
            ),
            "terms": [
                "Lifetime (vida): horas entre primera y ultima aparicion del meme.",
                "Burst score: intensidad del pico de frecuencia en poco tiempo.",
                "Dispersion: numero de submolts donde aparece el meme.",
            ],
            "how_to_read": [
                "Vida alta + burst bajo suele indicar una norma conversacional estable.",
                "Burst alto + vida baja suele indicar un episodio coyuntural.",
                "Dispersion alta sugiere capacidad de viajar entre comunidades.",
            ],
            "common_misreads": [
                "Confundir persistencia con veracidad del contenido.",
                "Confundir burst con importancia estructural de largo plazo.",
            ],
            "not_meaning": [
                "Vida no implica verdad; implica estabilidad de repeticion.",
                "Burst no implica importancia estructural; implica sensibilidad a eventos.",
            ],
            "auditable_questions": [
                "La dispersion de memes altos ocurre por hubs puntuales o por red distribuida?",
            ],
        },
        {
            "id": "3.1",
            "title": "Actos de habla y coordinacion",
            "what_it_is": "Cuenta estilos de accion en el lenguaje: afirmar, preguntar, pedir, ofrecer, rechazar, etc.",
            "why_it_matters": "El tipo de acto dominante muestra como coordina la red: explorando, ejecutando, normando o negociando.",
            "interpretation": (
                f"Se observa afirmacion={d.act_assertion_rate:.3f}/doc frente a pregunta={d.act_question_rate:.3f}/doc. "
                "Eso sugiere una dinamica mas orientada a enunciar y operar que a abrir preguntas."
            ),
            "terms": [
                "Acto de habla: funcion practica de una frase (afirmar, pedir, prometer, etc.).",
                "Rate/doc: promedio de apariciones por documento.",
                "Coordinacion conversacional: forma en que la red organiza accion a traves del lenguaje.",
            ],
            "how_to_read": [
                "Dominio de preguntas suele indicar fase de exploracion.",
                "Dominio de afirmaciones/instrucciones suele indicar fase de ejecucion y estandarizacion.",
                "Cambios fuertes entre submolts pueden revelar microculturas discursivas.",
            ],
            "common_misreads": [
                "Confundir estilo de habla con inteligencia o calidad total.",
                "Suponer que un solo acto explica toda la cultura de la red.",
            ],
            "not_meaning": [
                "No clasifica inteligencia de la red.",
                "Describe estilo de coordinacion conversacional.",
            ],
            "auditable_questions": [
                "Este perfil de actos es transversal o cambia fuerte por submolt?",
            ],
        },
        {
            "id": "3.2",
            "title": "Marcadores epistemicos",
            "what_it_is": "Mide como se justifica lo dicho: evidencia, matiz/hedge, certeza, duda.",
            "why_it_matters": "Ayuda a distinguir una cultura de argumentacion auditable de una cultura de afirmacion cerrada.",
            "interpretation": (
                f"En este snapshot: evidencia={d.epistemic_evidence_rate:.3f}/doc, hedge={d.epistemic_hedge_rate:.3f}/doc, "
                f"certeza={d.epistemic_certainty_rate:.3f}/doc. El balance sugiere presencia de justificacion, con baja declaracion absoluta."
            ),
            "terms": [
                "Evidencia: marcas linguisticas de justificacion o soporte.",
                "Hedge: expresiones de atenuacion (posiblemente, podria, etc.).",
                "Certeza: enunciados de cierre o seguridad fuerte.",
            ],
            "how_to_read": [
                "Mas evidencia y mas hedge suelen aumentar la auditabilidad del discurso.",
                "Mas certeza absoluta puede indicar doctrina o estandar consolidado.",
                "Cruzar con ejemplos textuales evita confundir forma retorica con calidad real.",
            ],
            "common_misreads": [
                "Asumir que mencionar evidencia equivale a evidencia de buena calidad.",
                "Interpretar hedge como debilidad intelectual por defecto.",
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
            "what_it_is": "Cuenta que conceptos aparecen juntos dentro de un mismo documento.",
            "why_it_matters": "Muestra paquetes narrativos: ideas que la red tiende a enlazar de forma recurrente.",
            "interpretation": (
                f"Par dominante: {d.top_pair_a} + {d.top_pair_b} ({fmt_num(d.top_pair_count)} co-ocurrencias). "
                "Estos pares recurrentes ayudan a mapear asociaciones estables en el discurso."
            ),
            "terms": [
                "Co-ocurrencia: presencia conjunta de dos conceptos en el mismo texto.",
                "Par dominante: par con mayor frecuencia observada.",
                "Paquete narrativo: conjunto de ideas que suelen viajar juntas.",
            ],
            "how_to_read": [
                "Pares estables suelen reflejar stack consolidado o marco ideologico repetido.",
                "Pares con cambios bruscos entre snapshots suelen reflejar eventos o campanas.",
                "Revisar variantes singular/plural evita sobreinterpretar artefactos linguisticos.",
            ],
            "common_misreads": [
                "Leer co-ocurrencia como causalidad directa.",
                "Ignorar que pares muy frecuentes pueden venir de terminos nucleares del tema.",
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
            "what_it_is": "Es una reduccion visual de muchos indicadores linguisticos a dos ejes para comparar submolts en un mismo plano.",
            "why_it_matters": "Permite ver rapidamente que comunidades hablan de forma parecida y cuales quedan alejadas del patron general.",
            "interpretation": (
                f"El mapa proyecta {fmt_num(d.pca_rows)} submolts (top por volumen). La razon p90/p50 de distancia es "
                f"{fmt_num(d.pca_ratio_p90_p50, 2)}: cuanto mayor esta razon, mayor heterogeneidad entre periferia y nucleo. "
                "PCA no inventa variables nuevas de contenido; reordena combinaciones de actos, moods y marcadores epistemicos para hacer visible la estructura relativa."
            ),
            "terms": [
                "PCA: tecnica de reduccion de dimensionalidad que comprime muchas variables en pocos ejes.",
                "Componente 1/2: combinaciones matematicas de variables originales, no categorias humanas directas.",
                "Outlier: punto alejado del centro; puede indicar estilo propio o baja muestra.",
            ],
            "how_to_read": [
                "Paso 1: mirar cercania entre puntos (submolts cercanos suelen tener estilos similares).",
                "Paso 2: mirar densidad de clusters (zonas compactas indican gramatica discursiva compartida).",
                "Paso 3: revisar outliers con su doc_count para separar estilo real de ruido por baja actividad.",
                "Paso 4: comparar con otro snapshot para ver si los grupos se mueven de forma estable o abrupta.",
            ],
            "common_misreads": [
                "Interpretar eje X o eje Y como si fueran etiquetas semanticas fijas.",
                "Leer distancia corta como influencia causal directa entre submolts.",
                "Concluir cambio cultural sin controlar cambios de muestra o filtros.",
            ],
            "not_meaning": [
                "Los ejes no tienen significado semantico directo; son combinaciones de variables.",
                "Cercania en el mapa no prueba causalidad ni coordinacion intencional.",
            ],
            "auditable_questions": [
                "El mapa se mantiene estable entre snapshots con filtros equivalentes?",
                "Los outliers siguen siendo outliers al exigir un minimo mayor de actividad?",
            ],
        },
        {
            "id": "4.1",
            "title": "Transmision por embeddings",
            "what_it_is": "Mide similitud de significado entre textos, no solo coincidencia literal de palabras.",
            "why_it_matters": "Permite detectar eco semantico: cuando ideas parecidas circulan entre comunidades aunque cambie la redaccion.",
            "interpretation": (
                f"Post-post mean={d.emb_post_post_mean:.3f} (cross={fmt_pct(d.emb_post_post_cross)}) y "
                f"post->coment mean={d.emb_post_comment_mean:.3f} (cross={fmt_pct(d.emb_post_comment_cross)}). "
                "El cruce alto entre submolts sugiere difusion transversal de marcos semanticos."
            ),
            "terms": [
                "Embedding: vector numerico que representa significado aproximado de un texto.",
                "Mean score: similitud promedio entre pares seleccionados.",
                "Cross-submolt: porcentaje de pares que conecta comunidades distintas.",
            ],
            "how_to_read": [
                "Comparar post-post vs post->comentario muestra cuanto se conserva o transforma la idea al responder.",
                "Cross alto sugiere circulacion entre comunidades; cross bajo sugiere encapsulamiento.",
                "Validar cualitativamente ejemplos de score alto evita sobreinterpretar el numero.",
            ],
            "common_misreads": [
                "Tomar similitud alta como prueba de copia o plagio.",
                "Inferir coordinacion intencional sin evidencia contextual adicional.",
            ],
            "not_meaning": [
                "Similitud no implica coordinacion intencional.",
                "El modulo detecta convergencia semantica, no plagio.",
            ],
            "auditable_questions": [
                "Que tipo de pares domina en percentiles altos de similitud?",
            ],
        },
        {
            "id": "4.2",
            "title": "Sensibilidad por threshold",
            "what_it_is": "Muestra como cambia la cantidad de matches cuando haces mas estricto o mas laxo el umbral de similitud.",
            "why_it_matters": "Evita elegir un threshold arbitrario sin mostrar el costo en falsos positivos o falsos negativos.",
            "interpretation": (
                f"Con threshold {d.threshold_low:.2f} aparecen {fmt_num(d.threshold_low_pairs)} pares; con {d.threshold_high:.2f} quedan "
                f"{fmt_num(d.threshold_high_pairs)} pares. El codo estimado en {fmt_num(d.threshold_knee, 2)} "
                f"(caida relativa {fmt_pct(d.threshold_knee_drop)}) marca una zona practica para balancear cobertura y precision."
            ),
            "terms": [
                "Threshold: minimo de similitud requerido para aceptar un match.",
                "Recall: sensibilidad para capturar muchos casos (incluye mas ruido).",
                "Precision: pureza de casos aceptados (pero puede perder variantes validas).",
            ],
            "how_to_read": [
                "Si al subir threshold la curva cae de golpe, la senal es fragil o muy heterogenea.",
                "Si cae de forma gradual, la senal es mas robusta.",
                "Usar la zona de codo como referencia y luego validar con muestras textuales.",
            ],
            "common_misreads": [
                "Buscar un threshold unico y universal para todos los contextos.",
                "Elegir threshold solo por conveniencia narrativa.",
            ],
            "not_meaning": [
                "No existe threshold universal correcto; depende del costo aceptable de error.",
            ],
            "auditable_questions": [
                "Coinciden los ejemplos cualitativos con la zona de codo seleccionada?",
            ],
        },
        {
            "id": "4.3",
            "title": "TF-IDF vs embeddings (baseline)",
            "what_it_is": "Compara dos tipos de similitud: lexical (palabras) y semantica (significado).",
            "why_it_matters": "Ayuda a distinguir copia literal de parafrasis o convergencia conceptual.",
            "interpretation": (
                f"VSM/TF-IDF matched={d.vsm_matched_mean:.3f} vs shuffled={d.vsm_shuffled_mean:.3f}, "
                f"AUC={d.vsm_auc:.3f}, corr(emb,VSM)={d.vsm_corr:.3f}. "
                "La diferencia matched-shuffled confirma senal lexical por encima del azar; la correlacion parcial con embeddings indica que no todo match semantico depende de repetir las mismas palabras."
            ),
            "terms": [
                "TF-IDF o VSM: similitud basada en coincidencia de terminos.",
                "AUC: capacidad de separar pares reales vs aleatorios (0.5 ~= azar).",
                "Correlacion emb-VSM: cuanto se mueven juntas la similitud semantica y lexical.",
            ],
            "how_to_read": [
                "TF-IDF alto + embeddings alto suele ser repeticion fuerte o slogan.",
                "TF-IDF bajo + embeddings alto suele indicar parafrasis.",
                "TF-IDF alto + embeddings bajo puede ser choque de keywords con sentidos distintos.",
            ],
            "common_misreads": [
                "Confundir baseline con validacion final de causalidad.",
                "Descartar la dimension semantica por enfocarse solo en keywords.",
            ],
            "not_meaning": [
                "No es validacion final de verdad de transmision; es contraste lexical minimo.",
            ],
            "auditable_questions": [
                "Que fraccion de matches fuertes depende de solape literal de tokens?",
            ],
        },
        {
            "id": "4.4",
            "title": "Muestras auditables de transmision",
            "what_it_is": "Conjunto de ejemplos concretos para revisar manualmente si el match tiene sentido.",
            "why_it_matters": "Sin inspeccion humana, un score numerico puede sostener lecturas equivocadas.",
            "interpretation": (
                f"Se publican {fmt_num(d.transmission_sample_count)} muestras para auditoria contextual. "
                "Estas muestras no reemplazan la estadistica global, pero permiten validar semantica, contexto e idioma caso por caso."
            ),
            "terms": [
                "Muestra auditable: subconjunto publicado para revision cualitativa.",
                "Contexto: metadatos minimos (fecha, idioma, submolt, texto).",
                "Validacion manual: lectura humana de coherencia semantica real.",
            ],
            "how_to_read": [
                "Revisar texto y metadatos juntos, no solo el score.",
                "Buscar falsos positivos recurrentes y trazarlos a reglas/filtros.",
                "Usar ejemplos de distintos rangos de score para calibrar umbral.",
            ],
            "common_misreads": [
                "Tomar la muestra como representacion exacta de todo el universo.",
                "Aceptar score alto sin leer el contenido real.",
            ],
            "not_meaning": [
                "Las muestras no son representativas del universo total; son auditables y pedagogicas.",
            ],
            "auditable_questions": [
                "Los top score preservan coherencia semantica al leer texto completo?",
            ],
        },
        {
            "id": "5.1",
            "title": "Centralidad de red",
            "what_it_is": "Describe como circula la atencion en la red: hubs, puentes y reciprocidad.",
            "why_it_matters": "Permite ver si la conversacion esta distribuida o depende de pocos nodos dominantes.",
            "interpretation": (
                f"Reply graph con {fmt_num(d.reply_nodes)} nodos y {fmt_num(d.reply_edges)} aristas; "
                f"reciprocidad={fmt_pct(d.reply_reciprocity)}, top 2% share={fmt_pct(d.reply_top2_share)}, Gini in-degree={d.reply_gini:.3f}. "
                "El patron describe una red con hubs marcados y dialogo reciproco relativamente bajo."
            ),
            "terms": [
                "PageRank: indicador de centralidad por flujo de enlaces.",
                "Betweenness: capacidad de un nodo para actuar como puente entre zonas.",
                "Reciprocidad: proporcion de relaciones de ida y vuelta.",
            ],
            "how_to_read": [
                "PageRank alto sugiere concentracion de atencion.",
                "Betweenness alto sugiere brokers que conectan comunidades.",
                "Reciprocidad baja sugiere broadcasting por encima de conversacion bilateral.",
            ],
            "common_misreads": [
                "Confundir centralidad con razon, calidad o legitimidad.",
                "Interpretar red estructural como red de influencia causal directa.",
            ],
            "not_meaning": [
                "Centralidad no equivale a moralidad ni a calidad argumental.",
            ],
            "auditable_questions": [
                "La estructura depende de pocos brokers o existen puentes distribuidos?",
            ],
        },
        {
            "id": "5.2",
            "title": "Autores activos y diversidad",
            "what_it_is": "Cuantifica que parte de la actividad total esta en pocas cuentas versus distribuida en muchas.",
            "why_it_matters": "Complementa la lectura por submolt con una lectura por actores para detectar dependencia de pocos emisores.",
            "interpretation": (
                f"Top 10 autores concentran {fmt_pct(d.top10_authors_share)} de la actividad total "
                f"(Gini autores={d.gini_authors:.3f}). Esto indica desigualdad relevante en participacion individual."
            ),
            "terms": [
                "Top 10 share autores: porcentaje de actividad acumulado por las 10 cuentas mas activas.",
                "Gini de autores: desigualdad de actividad entre cuentas.",
                "Actividad: suma de posts y comentarios por autor.",
            ],
            "how_to_read": [
                "Si top share sube, aumenta dependencia de pocos actores.",
                "Cruzar con submolts permite distinguir autores locales de autores puente.",
                "Comparar periodos ayuda a detectar rotacion o consolidacion de elites activas.",
            ],
            "common_misreads": [
                "Asumir que actividad alta equivale a influencia deliberativa real.",
                "Confundir cuenta muy activa con representatividad del sistema.",
            ],
            "not_meaning": [
                "Actividad alta no equivale a influencia deliberativa real.",
            ],
            "auditable_questions": [
                "Aumentan los autores puente en eventos globales o en periodos normales?",
            ],
        },
        {
            "id": "6.1",
            "title": "Pipeline 01-04 y trazabilidad",
            "what_it_is": "Resume la cadena completa: ingesta, normalizacion, derivados y visualizacion.",
            "why_it_matters": "Sin trazabilidad tecnica, la interpretacion sociologica queda en opinion no verificable.",
            "interpretation": (
                "La lectura sociologica solo es defendible si cada afirmacion puede rastrearse desde la UI hasta los archivos derivados y los scripts que la producen."
            ),
            "terms": [
                "Trazabilidad: capacidad de seguir un resultado hasta su fuente.",
                "Derivado: archivo intermedio o final calculado desde datos crudos.",
                "Reproducibilidad: posibilidad de obtener el mismo resultado con mismo pipeline y datos.",
            ],
            "how_to_read": [
                "Cada grafico debe tener ruta a su archivo fuente.",
                "Cada metrica debe explicar filtro y transformacion aplicada.",
                "Diferenciar observacion empirica de interpretacion narrativa.",
            ],
            "common_misreads": [
                "Asumir que reproducible significa libre de sesgo.",
                "Presentar conclusion fuerte sin ruta de evidencia.",
            ],
            "not_meaning": [
                "Pipeline reproducible no elimina sesgos de origen; los vuelve observables y debatibles.",
            ],
            "auditable_questions": [
                "Cada claim publico tiene evidencia y archivo fuente verificable?",
            ],
        },
        {
            "id": "6.2",
            "title": "Contrato de metricas (claim matrix)",
            "what_it_is": "Define reglas minimas para que una metrica pueda usarse como evidencia.",
            "why_it_matters": "Evita saltar de numero a conclusion sin declarar supuestos, limites y alcance inferencial.",
            "interpretation": (
                "Una metrica solo entra al argumento cuando tiene contrato: fuente, transformacion, filtros, limitaciones y pregunta que pretende responder."
            ),
            "terms": [
                "Claim matrix: tabla que vincula afirmaciones con evidencia y limites.",
                "Alcance inferencial: hasta donde se puede concluir sin extrapolar de mas.",
                "Limite metodologico: condicion que restringe interpretacion valida.",
            ],
            "how_to_read": [
                "Antes de usar un numero, verificar su definicion operacional.",
                "Separar dato observado de interpretacion propuesta.",
                "Explicitar que no puede responder cada metrica.",
            ],
            "common_misreads": [
                "Tratar la existencia de metrica como prueba automatica de causalidad.",
                "Asumir que un contrato metodologico valida cualquier narrativa.",
            ],
            "not_meaning": [
                "El contrato no legitima cualquier conclusion; solo delimita lectura valida y revisable.",
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
        if mod.get("what_it_is"):
            lines.append(f"- Que es: {mod.get('what_it_is')}")
        if mod.get("why_it_matters"):
            lines.append(f"- Por que importa: {mod.get('why_it_matters')}")
        lines.append(str(mod.get("interpretation") or "n/d"))
        terms = mod.get("terms") or []
        if terms:
            lines.append("- Terminos clave:")
            lines.extend([f"  - {x}" for x in terms])
        how = mod.get("how_to_read") or []
        if how:
            lines.append("- Como leerlo:")
            lines.extend([f"  - {x}" for x in how])
        misreads = mod.get("common_misreads") or []
        if misreads:
            lines.append("- Errores comunes:")
            lines.extend([f"  - {x}" for x in misreads])
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
