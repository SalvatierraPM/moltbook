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


ROOT = Path("/Users/pabli/Desktop/Coding/Moltbook")
WEB_ROOT = Path("/Users/pabli/Desktop/Coding/reporte-analisis-memetico-ontologico-moltbook-ui")
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
    memes_api_like_top20: int
    interference_noisy_top50: int
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
    memes = read_csv(DERIVED / "meme_candidates.csv")
    interference = read_csv(DERIVED / "interference_top.csv")
    incidence = read_csv(DERIVED / "human_incidence_top.csv")
    language = read_csv(DERIVED / "public_language_distribution.csv")

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

    memes_sorted = sorted(memes, key=lambda r: to_int(r.get("count")), reverse=True)
    api_like_pat = re.compile(r"(api|curl|agentmarket|jq|discover|v1|mbc20|xyz|0x)", re.IGNORECASE)
    memes_api_like_top20 = sum(
        1 for r in memes_sorted[:20] if api_like_pat.search((r.get("meme") or ""))
    )

    inter_top50 = sorted(interference, key=lambda r: to_float(r.get("score")), reverse=True)[:50]
    interference_noisy_top50 = sum(1 for r in inter_top50 if is_noisy_text(r.get("text_excerpt", "")))

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
        memes_api_like_top20=memes_api_like_top20,
        interference_noisy_top50=interference_noisy_top50,
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
        ("EVID-COVERAGE-001", DERIVED / "coverage_quality.json", "inspect coverage file", "Duplicados y ventanas temporales"),
        ("EVID-DIFFUSION-001", DERIVED / "diffusion_runs.csv", "inspect run timeline", "Serie temporal por captura"),
        ("EVID-ACTIVITY-001", DERIVED / "activity_daily.csv", "inspect activity timeline", "Serie temporal por created_at"),
        ("EVID-MEME-001", DERIVED / "meme_candidates.csv", "rank meme candidates", "Top memes lexicales"),
        ("EVID-MENTION-001", DERIVED / "mention_graph_centrality.csv", "inspect mention centrality", "Calidad del grafo de mentions"),
        ("EVID-INTERF-001", DERIVED / "interference_top.csv", "inspect top interference rows", "Top score de interferencia"),
        ("EVID-INCID-001", DERIVED / "human_incidence_top.csv", "inspect top incidence rows", "Top score de incidencia humana"),
        ("EVID-LANG-001", DERIVED / "public_language_distribution.csv", "inspect language sample", "Distribucion por muestra"),
        ("EVID-PYPROJECT-001", ROOT / "pyproject.toml", "inspect dependency constraints", "Riesgo de no fijar versiones"),
        ("EVID-TESTS-001", ROOT / "src", "find tests directories", "Cobertura de pruebas automatizadas"),
        ("EVID-CI-001", ROOT / ".github", "list CI workflows", "Automatizacion de validacion"),
        ("EVID-RANDOM-001", ROOT / "scripts" / "fetch_moltbook_api.py", "grep random.choice", "No determinismo de ingesta"),
        ("EVID-SECRETS-001", ROOT / ".secrets" / "github_token", "check local secret file", "Riesgo operativo de secretos locales"),
        ("EVID-NETLIFY-001", WEB_ROOT / ".netlify" / "state.json", "inspect netlify linkage", "Sitio Netlify linkeado localmente"),
        ("EVID-UI-TEMPORAL-001", ROOT / "site" / "analysis.html", "inspect temporal labels", "Separacion created_at vs run_time"),
    ]
    for evidence_ref, src, cmd, notes in sources:
        entry = {
            "evidence_ref": evidence_ref,
            "source_path": str(src),
            "command": cmd,
            "hash": sha256_file(src) if src.exists() and src.is_file() else "",
            "timestamp": now,
            "notes": notes,
        }
        entries.append(entry)
    return entries


def build_findings(m: Metrics) -> list[dict[str, str]]:
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
            "status": "open",
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
            "status": "open",
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
            "issue": f"{m.memes_api_like_top20}/20 memes top contienen patrones de API/tooling (boilerplate tecnico).",
            "evidence_ref": "EVID-MEME-001",
            "impact": "Alta probabilidad de confundir repeticion tecnica con meme cultural.",
            "recommendation": "Agregar filtro de boilerplate y doble ranking: tecnico vs cultural.",
            "owner": "NLP",
            "status": "open",
        },
        {
            "finding_id": "AUD-005",
            "severity": "P1",
            "domain": "Ontologia del lenguaje",
            "claim": "Actos/moods son comparables entre idiomas.",
            "issue": "No hay benchmark etiquetado ni error por idioma para validar reglas ontologicas.",
            "evidence_ref": "EVID-SCHEMA-001|EVID-LANG-001",
            "impact": "Riesgo alto de sesgo semantico en comparacion multilingue.",
            "recommendation": "Evaluar precision/recall con muestra etiquetada estratificada por idioma.",
            "owner": "Research",
            "status": "open",
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
            "status": "open",
        },
        {
            "finding_id": "AUD-007",
            "severity": "P1",
            "domain": "Interferencia",
            "claim": "Score alto identifica interferencia significativa.",
            "issue": f"{m.interference_noisy_top50}/50 top rows son texto ruidoso/base64/repetitivo.",
            "evidence_ref": "EVID-INTERF-001",
            "impact": "Muchos falsos positivos en top ranking; costo de revision manual elevado.",
            "recommendation": "Separar score tecnico (ruido/formato) de score semantico (injection/disclaimer).",
            "owner": "NLP",
            "status": "open",
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
            "issue": "Dependencias en pyproject usan rangos '>=' y no existe lockfile.",
            "evidence_ref": "EVID-PYPROJECT-001",
            "impact": "Resultados pueden variar entre entornos y fechas.",
            "recommendation": "Fijar lockfile (uv/pip-tools/poetry) y versionar entorno de ejecucion.",
            "owner": "Infra",
            "status": "open",
        },
        {
            "finding_id": "AUD-011",
            "severity": "P1",
            "domain": "Ingenieria y mantenibilidad",
            "claim": "Validacion automatizada cubre regresiones criticas.",
            "issue": "No hay suite de tests ni workflows CI en el repositorio.",
            "evidence_ref": "EVID-TESTS-001|EVID-CI-001",
            "impact": "Alto riesgo de regresion silenciosa en metrica y UI.",
            "recommendation": "Agregar smoke tests de datos + test unitarios clave + CI minima por PR.",
            "owner": "Engineering",
            "status": "open",
        },
        {
            "finding_id": "AUD-012",
            "severity": "P1",
            "domain": "Seguridad y compliance",
            "claim": "Operacion de publicacion no expone secretos.",
            "issue": "Existe archivo local de token en texto plano bajo .secrets.",
            "evidence_ref": "EVID-SECRETS-001",
            "impact": "Riesgo alto de fuga accidental por copia, backup o comando incorrecto.",
            "recommendation": "Mover secretos a keychain/env temporal y rotar token activo.",
            "owner": "Security",
            "status": "open",
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
            "- T3: Top memes sin boilerplate -> pendiente.",
            "- T4: Estabilidad ontologica multilengue -> pendiente benchmark.",
            "- T5: Mention graph sin ruido -> pendiente limpieza.",
            "- T6: Interferencia con separacion ruido/semantica -> pendiente.",
            "- T7: Sensibilidad embeddings -> pendiente.",
            "- T8: Rerun parcial reproducible -> bloqueado por lockfile/CI ausentes.",
            "- T9: Secretos fuera de repos operativos -> pendiente.",
            "- T10: Consistencia reporte/UI de definiciones -> parcialmente cumplido.",
            "",
            "## Riesgos residuales",
            "- Interpretacion academica aun sensible a sesgos de heuristicas.",
            "- Riesgo operativo por gestion manual de deploy y secretos.",
            "",
        ]
    )
    return "\n".join(lines)


def build_public_summary(now: str, findings: list[dict[str, str]], gates: dict[str, Any]) -> str:
    severity = counts_by_severity(findings)
    open_findings = [f for f in findings if f["status"] != "mitigated"]
    top_risks = [f for f in open_findings if f["severity"] in {"P0", "P1"}][:5]
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
    lines.extend(["", "## Riesgos prioritarios (P1)", ""])
    for f in top_risks:
        lines.append(f"- {f['finding_id']} ({f['domain']}): {f['issue']}")
    lines.extend(
        [
            "",
            "## Proximo hito",
            "- Cerrar hallazgos P1 de memetica, redes, interferencia, reproducibilidad y seguridad.",
        ]
    )
    return "\n".join(lines)


def build_public_summary_json(now: str, findings: list[dict[str, str]], gates: dict[str, Any]) -> dict[str, Any]:
    open_findings = [f for f in findings if f["status"] != "mitigated"]
    severity = counts_by_severity(findings)
    top = [
        {
            "finding_id": f["finding_id"],
            "severity": f["severity"],
            "domain": f["domain"],
            "issue": f["issue"],
        }
        for f in open_findings
        if f["severity"] in {"P0", "P1"}
    ][:6]
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
    evidence = build_evidence_index(now)
    findings = build_findings(m)
    gates = build_quality_gates(findings)
    backlog = build_backlog(findings)

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
