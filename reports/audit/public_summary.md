# Resumen publico de auditoria

- Fecha: 2026-02-13T17:20:25.069770+00:00
- Hallazgos abiertos: 13
- P0: 0 | P1: 9 | P2: 4 | P3: 0

## Estado de gates
- G1_data_integrity: fail
- G2_method_validity: fail
- G3_reproducibility: fail
- G4_public_safety: fail

## Riesgos prioritarios (P1)

- AUD-001 (Claims e inferencia): No hay matriz formal claim->evidencia->limite con nivel de confianza por claim.
- AUD-002 (Linaje de datos): No existe artefacto formal de linaje campo-a-campo para metricas criticas.
- AUD-004 (Memetica): 18/20 memes top contienen patrones de API/tooling (boilerplate tecnico).
- AUD-005 (Ontologia del lenguaje): No hay benchmark etiquetado ni error por idioma para validar reglas ontologicas.
- AUD-006 (Sociologia y redes): Top mention node='w' pagerank=0.434; nodos ruido en top10=5.

## Proximo hito
- Cerrar hallazgos P1 de memetica, redes, interferencia, reproducibilidad y seguridad.