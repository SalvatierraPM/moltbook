# Auditoría Integral v1

- Generado: 2026-02-14T23:49:51.607822+00:00
- Alcance: pipeline, datos derivados, reporte, UI, operacion/deploy.
- Modelo de severidad: P0-P3.

## Resumen ejecutivo
- Hallazgos abiertos: 0
- Severidad: P0=0, P1=0, P2=0, P3=0
- Gate G1_data_integrity: pass
- Gate G2_method_validity: pass
- Gate G3_reproducibility: pass
- Gate G4_public_safety: pass

## Scorecard de calidad de datos
- Posts: 152,980
- Comentarios: 704,450
- Duplicados comentarios: 502
- Ventana temporal real (created_at): 14.88 dias
- Ventana de captura (run_time): 5.97 dias
- Runs observados: 27

## Hallazgos por arista
### Claims e inferencia
- [P1] AUD-001: No hay matriz formal claim->evidencia->límite con nivel de confianza por claim.
  - Claim: El reporte presenta tesis fuertes de dominancia memética/ontologica.
  - Impacto: Riesgo de sobregeneralizacion academica en conclusiones centrales.
  - Evidencia: EVID-REPORT-001|EVID-SCHEMA-001
  - Recomendación: Publicar una tabla de claims con evidencia primaria y límites explícitos por claim.
  - Estado: mitigated

### Linaje de datos
- [P1] AUD-002: No existe artefacto formal de linaje campo-a-campo para métricas criticas.
  - Claim: Cada métrica del dashboard es auditable de punta a punta.
  - Impacto: Dificulta auditoría externa y trazabilidad reproducible.
  - Evidencia: EVID-SCHEMA-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001
  - Recomendación: Crear data lineage table (métrica, fuente, transformación, script, salida).
  - Estado: mitigated

### Cobertura temporal
- [P2] AUD-003: Ventana created_at=14.9 dias vs run_time=6.0 dias con 27 runs.
  - Claim: La actividad temporal está correctamente interpretada.
  - Impacto: Riesgo medio de mezclar ritmo real y ritmo de captura en lecturas no expertas.
  - Evidencia: EVID-COVERAGE-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001|EVID-UI-TEMPORAL-001
  - Recomendación: Mantener toggle por defecto en actividad real y reforzar notas en tablas run-based.
  - Estado: mitigated

### Memética
- [P1] AUD-004: Raw top20: 18/20 con patrones API/tooling; vista cultural top20: 0/20.
  - Claim: Top memes reflejan ideas culturales dominantes.
  - Impacto: Alta probabilidad de confundir repetición técnica con meme cultural.
  - Evidencia: EVID-MEME-001|EVID-MEME-002|EVID-MEME-003
  - Recomendación: Agregar filtro de boilerplate y doble ranking: técnico vs cultural.
  - Estado: mitigated

### Ontología del lenguaje
- [P1] AUD-005: Benchmark ontológico sin validación suficiente: metrics=yes; labeled_total=240 (en=80, es=80).
  - Claim: Actos/moods son comparables entre idiomas.
  - Impacto: Riesgo alto de sesgo semántico en comparación multilingüe.
  - Evidencia: EVID-SCHEMA-001|EVID-LANG-001|EVID-ONTO-BENCH-001|EVID-ONTO-BENCH-002
  - Recomendación: Evaluar precisión/recall con muestra etiquetada estratificada por idioma.
  - Estado: mitigated

### Sociologia y redes
- [P1] AUD-006: Top mention node='eudaemon_0' pagerank=0.007; nodos ruido en top10=0.
  - Claim: Centralidades del mention graph identifican actores reales.
  - Impacto: Centralidad contaminada por tokens basura; inferencia de influencia comprometida.
  - Evidencia: EVID-MENTION-001
  - Recomendación: Normalizar/filtrar handles inválidos antes del cálculo de grafos.
  - Estado: mitigated

### Interferencia
- [P1] AUD-007: 0/50 top rows son texto ruidoso/base64/repetitivo; split_scores=yes.
  - Claim: Score alto identifica interferencia significativa.
  - Impacto: Muchos falsos positivos en top ranking; costo de revisión manual elevado.
  - Evidencia: EVID-INTERF-001
  - Recomendación: Separar score técnico (ruido/formato) de score semántico (injection/disclaimer).
  - Estado: mitigated

### Incidencia humana
- [P2] AUD-008: 10/50 top rows tienen tooling_refs>=10 (sesgo técnico).
  - Claim: Score captura intervención humana relevante.
  - Impacto: Score tiende a privilegiar textos técnicos sobre evidencia humana contextual.
  - Evidencia: EVID-INCID-001
  - Recomendación: Introducir subscore narrativo y etiqueta de tipo de evidencia.
  - Estado: mitigated

### Transmisión IA vs humana
- [P2] AUD-009: No se pública análisis de sensibilidad de thresholds ni baseline alternativo.
  - Claim: Comparación IA vs humano es robusta y generalizable.
  - Impacto: Interpretaciones comparativas con incertidumbre no cuantificada.
  - Evidencia: EVID-TRANS-SENS-001|EVID-TRANS-VSM-001|EVID-LANG-001
  - Recomendación: Publicar sensibilidad por threshold y baseline VSM/embeddings comparado.
  - Estado: mitigated

### Reproducibilidad
- [P1] AUD-010: Dependencias en pyproject usan rangos '>='; lockfile=yes.
  - Claim: Pipeline es totalmente reproducible.
  - Impacto: Resultados pueden variar entre entornos y fechas.
  - Evidencia: EVID-PYPROJECT-001|EVID-LOCK-001
  - Recomendación: Fijar lockfile (uv/pip-tools/poetry) y versionar entorno de ejecución.
  - Estado: mitigated

### Ingenieria y mantenibilidad
- [P1] AUD-011: Tests=yes; CI=yes.
  - Claim: Validación automatizada cubre regresiones criticas.
  - Impacto: Alto riesgo de regresion silenciosa en métrica y UI.
  - Evidencia: EVID-TESTS-001|EVID-CI-001
  - Recomendación: Agregar smoke tests de datos + test unitarios clave + CI mínima por PR.
  - Estado: mitigated

### Seguridad y compliance
- [P1] AUD-012: Token en texto plano bajo .secrets: no.
  - Claim: Operacion de publicación no expone secretos.
  - Impacto: Riesgo alto de fuga accidental por copia, backup o comando incorrecto.
  - Evidencia: EVID-SECRETS-001
  - Recomendación: Mover secretos a keychain/env temporal y rotar token activo.
  - Estado: mitigated

### Operacion deploy
- [P2] AUD-013: Hay evidencia de sitio Netlify localmente linkeado, pero no evidencia en repo de integración GitHub.
  - Claim: Deploy automático GitHub->Netlify está garantizado.
  - Impacto: Riesgo de creer que hay deploy automático cuando depende de pasos manuales.
  - Evidencia: EVID-NETLIFY-002
  - Recomendación: Documentar estado de integración y enlace de repo en runbook operativo.
  - Estado: mitigated

### Producto público
- [P3] AUD-014: El riesgo misleading temporal está mitigado en gráficos principales y texto explicativo.
  - Claim: La UI distingue actividad real y captura.
  - Impacto: Sin impacto material actual; mantener como control continuo.
  - Evidencia: EVID-UI-TEMPORAL-001
  - Recomendación: Conservar esta separación en cada nueva visualización temporal.
  - Estado: mitigated

## Validaciones obligatorias (T1-T10)
- T1: Temporalidad UI (created_at vs run_time) -> mitigado parcialmente.
- T2: Cobertura de submolts -> requiere score de representatividad.
- T3: Top memes sin boilerplate -> mitigado.
- T4: Estabilidad ontologica multilingüe -> mitigado.
- T5: Mention graph sin ruido -> mitigado.
- T6: Interferencia con separación ruido/semántica -> mitigado.
- T7: Sensibilidad embeddings -> pendiente.
- T8: Rerun parcial reproducible -> mitigado.
- T9: Secretos fuera de repos operativos -> mitigado.
- T10: Consistencia reporte/UI de definiciones -> parcialmente cumplido.

## Riesgos residuales
- Interpretacion academica aun sensible a sesgos de heuristicas.
- Riesgo operativo: deploy puede depender de pasos manuales si GitHub->Netlify no está documentado.
