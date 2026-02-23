#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def sample_evenly(rows: list[dict[str, str]], n: int) -> list[dict[str, str]]:
    if n <= 0:
        return []
    if len(rows) <= n:
        return rows
    if n == 1:
        return [rows[0]]
    out: list[dict[str, str]] = []
    last_idx = len(rows) - 1
    for i in range(n):
        idx = round(i * last_idx / (n - 1))
        out.append(rows[idx])
    seen = set()
    dedup: list[dict[str, str]] = []
    for row in out:
        key = str(row.get("event_id") or "")
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    if len(dedup) < n:
        for row in rows:
            key = str(row.get("event_id") or "")
            if key in seen:
                continue
            dedup.append(row)
            seen.add(key)
            if len(dedup) >= n:
                break
    return dedup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye paquete de anotacion humana estratificada para eventos de intervencion."
    )
    parser.add_argument("--events", default="data/derived/human_intervention_events.csv")
    parser.add_argument("--out-csv", default="data/derived/human_intervention_annotation_sample.csv")
    parser.add_argument("--out-json", default="data/derived/human_intervention_annotation_sample.json")
    parser.add_argument("--out-guide", default="reports/human_intervention_annotation_guide.md")
    parser.add_argument("--per-class", type=int, default=30)
    args = parser.parse_args()

    events_path = Path(args.events)
    rows = read_csv(events_path)
    if not rows:
        raise SystemExit(f"No se encontro dataset de eventos: {events_path}")

    by_class: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        label = str(row.get("likely_source") or "unknown")
        by_class.setdefault(label, []).append(row)
    for label in list(by_class.keys()):
        by_class[label] = sorted(by_class[label], key=lambda r: to_float(r.get("event_score")), reverse=True)

    sampled: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}
    sample_id = 1
    for label, class_rows in sorted(by_class.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        chosen = sample_evenly(class_rows, args.per_class)
        class_counts[label] = len(chosen)
        for row in chosen:
            sampled.append(
                {
                    "sample_id": f"S{sample_id:04d}",
                    "event_id": row.get("event_id") or "",
                    "likely_source_model": label,
                    "confidence_model": row.get("confidence") or "",
                    "event_score": row.get("event_score") or "",
                    "coordination_index": row.get("coordination_index") or "",
                    "repeat_count": row.get("repeat_count") or "",
                    "unique_authors": row.get("unique_authors") or "",
                    "unique_submolts": row.get("unique_submolts") or "",
                    "first_created_at": row.get("first_created_at") or "",
                    "last_created_at": row.get("last_created_at") or "",
                    "sample_excerpt": row.get("sample_excerpt") or "",
                    "gold_label": "",
                    "gold_confidence": "",
                    "annotator_notes": "",
                }
            )
            sample_id += 1

    sampled = sorted(
        sampled,
        key=lambda r: (
            str(r.get("likely_source_model") or ""),
            -to_float(r.get("event_score")),
            str(r.get("event_id") or ""),
        ),
    )
    write_csv(
        Path(args.out_csv),
        sampled,
        [
            "sample_id",
            "event_id",
            "likely_source_model",
            "confidence_model",
            "event_score",
            "coordination_index",
            "repeat_count",
            "unique_authors",
            "unique_submolts",
            "first_created_at",
            "last_created_at",
            "sample_excerpt",
            "gold_label",
            "gold_confidence",
            "annotator_notes",
        ],
    )

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {"events_path": str(events_path), "events_total": len(rows)},
        "sampling": {
            "per_class_target": args.per_class,
            "classes_present": dict(sorted(Counter(str(r.get("likely_source") or "unknown") for r in rows).items())),
            "classes_sampled": class_counts,
            "sample_size_total": len(sampled),
        },
        "labels_allowed": [
            "campana_promocional",
            "prompt_tooling",
            "interferencia_semantica",
            "humano_explicito",
            "coordinacion_hibrida",
            "narrativa_situada",
            "mixto",
            "falso_positivo",
        ],
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    guide_lines = [
        "# Human Intervention Annotation Guide",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- sample_size_total: {len(sampled)}",
        "",
        "## Objetivo",
        "Validar manualmente si los eventos detectados corresponden a intervencion humana/coordinacion externa y no solo a estilo discursivo.",
        "",
        "## Unidades",
        "- `event_id`: grupo canonico de textos similares.",
        "- `sample_excerpt`: evidencia textual principal.",
        "- `repeat_count`, `unique_authors`, `unique_submolts`: evidencia estructural de coordinacion.",
        "",
        "## Etiquetas permitidas",
        "- `campana_promocional`: CTA repetida, urgencia/escasez, patron de growth-farming o amplificacion.",
        "- `prompt_tooling`: lenguaje de instrucciones/prompts + detalles tecnicos operativos.",
        "- `interferencia_semantica`: huellas de inyeccion, bypass o instrucciones metacontextuales.",
        "- `humano_explicito`: referencia directa a humano/operador/usuario como actor causal.",
        "- `coordinacion_hibrida`: repeticion transversal (autores/submolts) sin patron puramente promo.",
        "- `narrativa_situada`: relato personal contextualizado sin evidencia fuerte de campana.",
        "- `mixto`: evidencia combinada sin dominante clara.",
        "- `falso_positivo`: la prediccion no representa intervencion humana/coordinacion relevante.",
        "",
        "## Reglas de decision",
        "1. Priorizar estructura (repeticion + dispersion) sobre una sola palabra clave.",
        "2. Si hay conflicto entre texto y estructura, documentar en `annotator_notes`.",
        "3. Usar `gold_confidence` en [0,1] y evitar 1.0 salvo evidencia contundente.",
        "",
        "## Criterio de calidad recomendado",
        "- Dos anotadores independientes.",
        "- Medir acuerdo (Cohen's kappa) y adjudicar desacuerdos.",
        "- Publicar matriz de confusion modelo vs gold.",
    ]
    out_guide = Path(args.out_guide)
    out_guide.parent.mkdir(parents=True, exist_ok=True)
    out_guide.write_text("\n".join(guide_lines).strip() + "\n", encoding="utf-8")

    print(f"events_total={len(rows)} sample_total={len(sampled)}")
    print(f"annotation_csv={args.out_csv}")
    print(f"annotation_json={args.out_json}")
    print(f"annotation_guide={args.out_guide}")


if __name__ == "__main__":
    main()
