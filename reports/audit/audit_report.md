# Auditoria Integral v1

- Generado: 2026-02-13T19:18:36.997555+00:00
- Alcance: pipeline, datos derivados, reporte, UI, operacion/deploy.
- Modelo de severidad: P0-P3.

## Resumen ejecutivo
- Hallazgos abiertos: 6
- Severidad: P0=0, P1=2, P2=4, P3=0
- Gate G1_data_integrity: pass
- Gate G2_method_validity: fail
- Gate G3_reproducibility: pass
- Gate G4_public_safety: fail

## Scorecard de calidad de datos
- Posts: 152,980
- Comentarios: 704,450
- Duplicados comentarios: 502
- Ventana temporal real (created_at): 14.88 dias
- Ventana de captura (run_time): 5.97 dias
- Runs observados: 27

## Hallazgos por arista
### Claims e inferencia
- [P1] AUD-001: No hay matriz formal claim->evidencia->limite con nivel de confianza por claim.
  - Claim: El reporte presenta tesis fuertes de dominancia memetica/ontologica.
  - Impacto: Riesgo de sobregeneralizacion academica en conclusiones centrales.
  - Evidencia: EVID-REPORT-001|EVID-SCHEMA-001
  - Recomendacion: Publicar una tabla de claims con evidencia primaria y limites explicitos por claim.
  - Estado: mitigated

### Linaje de datos
- [P1] AUD-002: No existe artefacto formal de linaje campo-a-campo para metricas criticas.
  - Claim: Cada metrica del dashboard es auditable de punta a punta.
  - Impacto: Dificulta auditoria externa y trazabilidad reproducible.
  - Evidencia: EVID-SCHEMA-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001
  - Recomendacion: Crear data lineage table (metrica, fuente, transformacion, script, salida).
  - Estado: mitigated

### Cobertura temporal
- [P2] AUD-003: Ventana created_at=14.9 dias vs run_time=6.0 dias con 27 runs.
  - Claim: La actividad temporal esta correctamente interpretada.
  - Impacto: Riesgo medio de mezclar ritmo real y ritmo de captura en lecturas no expertas.
  - Evidencia: EVID-COVERAGE-001|EVID-DIFFUSION-001|EVID-ACTIVITY-001|EVID-UI-TEMPORAL-001
  - Recomendacion: Mantener toggle por defecto en actividad real y reforzar notas en tablas run-based.
  - Estado: open

### Memetica
- [P1] AUD-004: Raw top20: 18/20 con patrones API/tooling; vista cultural top20: 0/20.
  - Claim: Top memes reflejan ideas culturales dominantes.
  - Impacto: Alta probabilidad de confundir repeticion tecnica con meme cultural.
  - Evidencia: EVID-MEME-001|EVID-MEME-002|EVID-MEME-003
  - Recomendacion: Agregar filtro de boilerplate y doble ranking: tecnico vs cultural.
  - Estado: mitigated

### Ontologia del lenguaje
- [P1] AUD-005: Benchmark ontologico sin validacion suficiente: metrics=yes; labeled_total=0 (en=0, es=0).
  - Claim: Actos/moods son comparables entre idiomas.
  - Impacto: Riesgo alto de sesgo semantico en comparacion multilingue.
  - Evidencia: EVID-SCHEMA-001|EVID-LANG-001|EVID-ONTO-BENCH-001|EVID-ONTO-BENCH-002
  - Recomendacion: Evaluar precision/recall con muestra etiquetada estratificada por idioma.
  - Estado: open

### Sociologia y redes
- [P1] AUD-006: Top mention node='eudaemon_0' pagerank=0.007; nodos ruido en top10=0.
  - Claim: Centralidades del mention graph identifican actores reales.
  - Impacto: Centralidad contaminada por tokens basura; inferencia de influencia comprometida.
  - Evidencia: EVID-MENTION-001
  - Recomendacion: Normalizar/filtrar handles invalidos antes del calculo de grafos.
  - Estado: mitigated

### Interferencia
- [P1] AUD-007: 0/50 top rows son texto ruidoso/base64/repetitivo; split_scores=yes.
  - Claim: Score alto identifica interferencia significativa.
  - Impacto: Muchos falsos positivos en top ranking; costo de revision manual elevado.
  - Evidencia: EVID-INTERF-001
  - Recomendacion: Separar score tecnico (ruido/formato) de score semantico (injection/disclaimer).
  - Estado: mitigated

### Incidencia humana
- [P2] AUD-008: 34/50 top rows tienen tooling_refs>=10 (sesgo tecnico).
  - Claim: Score captura intervencion humana relevante.
  - Impacto: Score tiende a privilegiar textos tecnicos sobre evidencia humana contextual.
  - Evidencia: EVID-INCID-001
  - Recomendacion: Introducir subscore narrativo y etiqueta de tipo de evidencia.
  - Estado: open

### Transmision IA vs humana
- [P2] AUD-009: No se publica analisis de sensibilidad de thresholds ni baseline alternativo.
  - Claim: Comparacion IA vs humano es robusta y generalizable.
  - Impacto: Interpretaciones comparativas con incertidumbre no cuantificada.
  - Evidencia: EVID-REPORT-001|EVID-LANG-001
  - Recomendacion: Publicar sensibilidad por threshold y baseline VSM/embeddings comparado.
  - Estado: open

### Reproducibilidad
- [P1] AUD-010: Dependencias en pyproject usan rangos '>='; lockfile=yes.
  - Claim: Pipeline es totalmente reproducible.
  - Impacto: Resultados pueden variar entre entornos y fechas.
  - Evidencia: EVID-PYPROJECT-001|EVID-LOCK-001
  - Recomendacion: Fijar lockfile (uv/pip-tools/poetry) y versionar entorno de ejecucion.
  - Estado: mitigated

### Ingenieria y mantenibilidad
- [P1] AUD-011: Tests=yes; CI=yes.
  - Claim: Validacion automatizada cubre regresiones criticas.
  - Impacto: Alto riesgo de regresion silenciosa en metrica y UI.
  - Evidencia: EVID-TESTS-001|EVID-CI-001
  - Recomendacion: Agregar smoke tests de datos + test unitarios clave + CI minima por PR.
  - Estado: mitigated

### Seguridad y compliance
- [P1] AUD-012: Existe archivo local de token en texto plano bajo .secrets.
  - Claim: Operacion de publicacion no expone secretos.
  - Impacto: Riesgo alto de fuga accidental por copia, backup o comando incorrecto.
  - Evidencia: EVID-SECRETS-001
  - Recomendacion: Mover secretos a keychain/env temporal y rotar token activo.
  - Estado: open

### Operacion deploy
- [P2] AUD-013: Hay evidencia de sitio Netlify localmente linkeado, pero no evidencia en repo de integracion GitHub.
  - Claim: Deploy automatico GitHub->Netlify esta garantizado.
  - Impacto: Riesgo de creer que hay deploy automatico cuando depende de pasos manuales.
  - Evidencia: EVID-NETLIFY-001
  - Recomendacion: Documentar estado de integracion y enlace de repo en runbook operativo.
  - Estado: open

### Producto publico
- [P3] AUD-014: El riesgo misleading temporal esta mitigado en graficos principales y texto explicativo.
  - Claim: La UI distingue actividad real y captura.
  - Impacto: Sin impacto material actual; mantener como control continuo.
  - Evidencia: EVID-UI-TEMPORAL-001
  - Recomendacion: Conservar esta separacion en cada nueva visualizacion temporal.
  - Estado: mitigated

## Validaciones obligatorias (T1-T10)
- T1: Temporalidad UI (created_at vs run_time) -> mitigado parcialmente.
- T2: Cobertura de submolts -> requiere score de representatividad.
- T3: Top memes sin boilerplate -> mitigado.
- T4: Estabilidad ontologica multilengue -> pendiente benchmark.
- T5: Mention graph sin ruido -> pendiente limpieza.
- T6: Interferencia con separacion ruido/semantica -> pendiente.
- T7: Sensibilidad embeddings -> pendiente.
- T8: Rerun parcial reproducible -> bloqueado por lockfile/CI ausentes.
- T9: Secretos fuera de repos operativos -> pendiente.
- T10: Consistencia reporte/UI de definiciones -> parcialmente cumplido.

## Riesgos residuales
- Interpretacion academica aun sensible a sesgos de heuristicas.
- Riesgo operativo por gestion manual de deploy y secretos.
