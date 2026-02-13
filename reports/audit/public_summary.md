# Resumen publico de auditoria

- Fecha: 2026-02-13T18:34:29.715632+00:00
- Hallazgos abiertos: 10
- P0: 0 | P1: 6 | P2: 4 | P3: 0

## Estado de gates
- G1_data_integrity: fail
- G2_method_validity: fail
- G3_reproducibility: fail
- G4_public_safety: fail

## Riesgos prioritarios (P1)

- AUD-005 (Ontologia del lenguaje): Benchmark ontologico sin validacion suficiente: metrics=yes; labeled_total=0 (en=0, es=0).
- AUD-006 (Sociologia y redes): Top mention node='w' pagerank=0.434; nodos ruido en top10=5.
- AUD-007 (Interferencia): 42/50 top rows son texto ruidoso/base64/repetitivo.
- AUD-010 (Reproducibilidad): Dependencias en pyproject usan rangos '>=' y no existe lockfile.
- AUD-011 (Ingenieria y mantenibilidad): No hay suite de tests ni workflows CI en el repositorio.

## Proximo hito
- Cerrar hallazgos P1 de memetica, redes, interferencia, reproducibilidad y seguridad.