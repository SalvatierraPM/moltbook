# Resumen publico de auditoria

- Fecha: 2026-02-14T18:23:56.456272+00:00
- Hallazgos abiertos: 4
- P0: 0 | P1: 0 | P2: 4 | P3: 0

## Estado de gates
- G1_data_integrity: pass
- G2_method_validity: pass
- G3_reproducibility: pass
- G4_public_safety: pass

## Riesgos prioritarios (abiertos, top P2)

- AUD-003 [P2] (Cobertura temporal): Ventana created_at=14.9 dias vs run_time=6.0 dias con 27 runs.
- AUD-008 [P2] (Incidencia humana): 34/50 top rows tienen tooling_refs>=10 (sesgo tecnico).
- AUD-009 [P2] (Transmision IA vs humana): No se publica analisis de sensibilidad de thresholds ni baseline alternativo.
- AUD-013 [P2] (Operacion deploy): Hay evidencia de sitio Netlify localmente linkeado, pero no evidencia en repo de integracion GitHub.

## Proximo hito
- Cerrar AUD-003 (Cobertura temporal) y regenerar auditoria.