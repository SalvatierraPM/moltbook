#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAP_INQUIETUD = {
    "recognition": "reconocimiento",
    "power": "poder",
    "belonging": "pertenencia",
    "status": "estatus",
    "truth": "verdad",
    "justice": "justicia",
    "coordination": "coordinacion",
    "validation": "validacion",
    "humor": "humor",
    "moral_positioning": "posicion_moral",
}

MAP_METRICS = {
    "mean_conflict_index": "indice_conflicto_promedio",
    "mean_coordination_index": "indice_coordinacion_promedio",
    "mean_rigidity_score": "indice_rigidez_promedio",
    "dominance_vs_reciprocity": "dominancia_vs_reciprocidad",
    "identity_vs_task_orientation": "identidad_vs_orientacion_tarea",
    "diversity_of_inquietudes": "diversidad_inquietudes",
    "structural_entropy": "entropia_estructural",
}

MAP_PROFILE = {
    "conflict_vs_coordination": "conflicto_vs_coordinacion",
    "rigidity_vs_plasticity": "rigidez_vs_plasticidad",
    "dominance_vs_reciprocity": "dominancia_vs_reciprocidad",
    "identity_vs_task_orientation": "identidad_vs_orientacion_tarea",
}


def _map_inquietudes(items):
    out = []
    for k, v in items:
        out.append({"inquietud": MAP_INQUIETUD.get(k, k), "probabilidad": v})
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Exporta diagnostics de pragmatics en español para UI")
    p.add_argument("--input", default="out/pragmatics/diagnostics_report.json")
    p.add_argument("--output", default="out/pragmatics/diagnostics_report.es.json")
    args = p.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    es = {
        "resumen": {
            "cantidad_comunidades": data.get("summary", {}).get("community_count", 0),
            "cantidad_alertas": data.get("summary", {}).get("alerts_count", 0),
        },
        "perfiles_comunidad": [],
        "rankings": {
            "mayor_conflicto": data.get("rankings", {}).get("highest_conflict", []),
            "mayor_coordinacion": data.get("rankings", {}).get("highest_coordination", []),
        },
    }

    for c in data.get("community_profiles", []):
        perfil = c.get("discursive_profile", {})
        perfil_es = {MAP_PROFILE.get(k, k): v for k, v in perfil.items()}

        latest = c.get("latest_metrics", {})
        latest_es = {MAP_METRICS.get(k, k): v for k, v in latest.items()}

        alertas = []
        for a in c.get("alerts", []):
            alertas.append(
                {
                    "ventana_inicio": a.get("window_start"),
                    "ventana_fin": a.get("window_end"),
                    "metricas_disparadas": [MAP_METRICS.get(m, m) for m in a.get("triggered_metrics", [])],
                }
            )

        es["perfiles_comunidad"].append(
            {
                "comunidad_id": c.get("community_id"),
                "perfil_discursivo": perfil_es,
                "top_inquietudes": _map_inquietudes(c.get("top_inquietudes", [])),
                "alertas": alertas,
                "metricas_actuales": latest_es,
            }
        )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(es, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito: {args.output}")


if __name__ == "__main__":
    main()
