# Revision doctoral de criterios, temporalidad e interpretacion (foco: intervencion humana)

- Fecha: 2026-02-23
- Pregunta causal objetivo: distinguir patrones de posible intervencion humana coordinada vs dinamica emergente de agentes.

## 1) Criterios reales de scrapeo (auditados en datos crudos)

### Evidencia positiva
- Descubrimiento amplio de submolts hasta `15,443` (`data/raw/api_fetch/state.json`).
- Crawl paginado por submolt en ordenes `new`, `hot`, `top`.
- Log de paginacion: `submolt_page_events=28,901`.
- Distribucion de paginas por orden:
  - `new=18,106`
  - `hot=5,502`
  - `top=5,293`
- Listing crudo total: `1,058,904` filas.

### Evidencia negativa
- No aparece un criterio unico de "solo posts mas interactuados".
- No aparece como contrato principal "primeros 100 submolts exitosos".
- Archivos `top_submolts_*` y `sample_submolts_*` se comportan como artefactos auxiliares, no como politica base del fetch.

## 2) Contrato temporal: `created_at` y `run_time`

Fuente: `reports/temporal_contract_audit.md`, `reports/analysis_schema.md`.

- `created_at` (tiempo de publicacion):
  - 2026-01-28T00:00:49.827751+00:00 -> 2026-02-11T21:06:53.498583+00:00
  - ventana: ~14.8792 dias
- `run_time` (tiempo de captura):
  - 2026-02-05T15:02:00.919213+00:00 -> 2026-02-11T14:12:15.114851+00:00
  - ventana: ~5.9654 dias
  - corridas: 27

### Decision metodologica
- `run_time` no es redundante: sirve para QA de scraping, cobertura por corrida y comparabilidad de snapshots.
- `run_time` no debe usarse para inferir ritmo social ni nacimiento de memes.
- Para inferencia social/causal sobre intervencion, la base temporal primaria es `created_at`.

## 3) Reinterpretacion de narrativa (coherencia y ajustes)

### Lo que se sostiene
- El contrato temporal esta bien explicitado y auditable.
- La narrativa sociologica previa advierte riesgos de sobrelectura.

### Lo que se ajusta
- El marco principal debe pasar de "interaccion humana" a "indicios de empuje/intervencion humana".
- Referencias textuales tipo "my human" no prueban autoria humana directa; son evidencia contextual.
- La unidad relevante para causalidad operativa es el evento repetido (grupo), no el documento aislado.

## 4) Pipeline actualizado para intervencion humana

Scripts:
- `scripts/detect_human_intervention.py`
- `scripts/intervention_robustness.py`
- `scripts/build_intervention_annotation_pack.py`
- `scripts/build_intervention_strict_subset.py`

Cambios metodologicos clave:
- Feature engineering de coordinacion por grupo (`author/submolt concentration`, entropias, `coordination_index`).
- Clase adicional: `coordinacion_hibrida`.
- `min_group_size` base en `2` (evento, no singleton).
- Export por defecto **sin truncamiento** (`top-events=0`, `top-docs=0`).
- Robustez por grid con estabilidad top-k y eventos robustos.
- Muestreo estratificado para anotacion humana.

## 5) Resultados actualizados (run completo, no truncado)

Fuente principal: `data/derived/human_intervention_summary.json`.

- docs_total: `857,427`
- candidate_docs: `62,992`
- candidate_groups: `40,426`
- events_exported: `1,382`
- docs_exported: `62,992`

Distribucion de clases (`events_exported=1,382`):
- `humano_explicito=780`
- `mixto=443`
- `campana_promocional=72`
- `interferencia_semantica=50`
- `narrativa_situada=19`
- `prompt_tooling=17`
- `coordinacion_hibrida=1`

Hallazgos consistentes con intervencion coordinada:
- `2439bc8b8e5be124` (urgency CTA tipo like/repost, `repeat_count=182`).
- `a892cd6b85402eaf` (pattern "first 100 followers", `repeat_count=124`).
- `6c7ed5dcee2a6d10` (variante del mismo pattern, `repeat_count=127`).
- `dd496eddade19d0a` (macro plantilla transversal, `repeat_count=12476`, `unique_submolts=40`).

Filtro conservador de "intervencion probable fuerte" (criterio estructural+semantico):
- Regla aplicada: `event_score>=12`, `coordination_index>=0.5`, `repeat_count>=8` y evidencia semantica de empuje.
- Eventos que cumplen: `24`.
- Distribucion:
  - `campana_promocional=11`
  - `humano_explicito=12`
  - `coordinacion_hibrida=1`
- Artefactos reproducibles:
  - `data/derived/human_intervention_strict_events.csv`
  - `reports/human_intervention_strict_events.md`

## 6) Robustez y estabilidad

Fuente: `data/derived/human_intervention_robustness.json`, `reports/human_intervention_robustness.md`.

- Grid: `min_group_size in {2,3,5,8}` x `min_event_score in {3.5,5,7,10,12}` (20 configs).
- Jaccard top-100 vs baseline:
  - mediana: `0.545717`
  - minimo: `0.37931`
  - maximo: `1.0`
- Eventos robustos (presencia >=70% configs): `113`.

Correccion metodologica aplicada:
- Los intervalos de estabilidad por clase ahora incluyen conteos cero por configuracion.
- Esto evita sesgo optimista cuando una clase desaparece en configuraciones mas estrictas.

## 7) Validacion humana (annotation pack)

Fuente: `data/derived/human_intervention_annotation_sample.json`.

- Universo de eventos anotables: `1,382`.
- Muestra estratificada: `157` eventos.
- Incluye todas las clases presentes, incluida `narrativa_situada`.
- Guia: `reports/human_intervention_annotation_guide.md`.

## 8) Conclusiones para tu objetivo

- Si, la reinterpretacion tiene sentido: el problema no era "interaccion humana" en abstracto, sino detectar **patrones de intervencion humana probable** sobre la red.
- Si, `run_time` importa, pero como variable de calidad de observacion, no como tiempo del fenomeno.
- La narrativa ahora queda alineada con causalidad operativa mediante evento, coordinacion y robustez.
- Lo que aun falta para cerrar causalidad fuerte: anotacion doble ciega + acuerdo interanotador + calibracion del clasificador con gold labels.
