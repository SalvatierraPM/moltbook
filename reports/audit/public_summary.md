# Resumen publico de auditoria

- Fecha: 2026-02-13T19:13:34.684605+00:00
- Hallazgos abiertos: 7
- P0: 0 | P1: 3 | P2: 4 | P3: 0

## Estado de gates
- G1_data_integrity: pass
- G2_method_validity: fail
- G3_reproducibility: fail
- G4_public_safety: fail

## Riesgos prioritarios (P1)

- AUD-005 (Ontologia del lenguaje): Benchmark ontologico sin validacion suficiente: metrics=yes; labeled_total=0 (en=0, es=0).
- AUD-011 (Ingenieria y mantenibilidad): No hay suite de tests ni workflows CI en el repositorio.
- AUD-012 (Seguridad y compliance): Existe archivo local de token en texto plano bajo .secrets.

## Proximo hito
- Cerrar hallazgos P1 de memetica, redes, interferencia, reproducibilidad y seguridad.