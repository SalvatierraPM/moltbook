# Resumen publico de auditoria

- Fecha: 2026-02-13T17:38:20.400670+00:00
- Hallazgos abiertos: 11
- P0: 0 | P1: 7 | P2: 4 | P3: 0

## Estado de gates
- G1_data_integrity: fail
- G2_method_validity: fail
- G3_reproducibility: fail
- G4_public_safety: fail

## Riesgos prioritarios (P1)

- AUD-004 (Memetica): 18/20 memes top contienen patrones de API/tooling (boilerplate tecnico).
- AUD-005 (Ontologia del lenguaje): No hay benchmark etiquetado ni error por idioma para validar reglas ontologicas.
- AUD-006 (Sociologia y redes): Top mention node='w' pagerank=0.434; nodos ruido en top10=5.
- AUD-007 (Interferencia): 42/50 top rows son texto ruidoso/base64/repetitivo.
- AUD-010 (Reproducibilidad): Dependencias en pyproject usan rangos '>=' y no existe lockfile.

## Proximo hito
- Cerrar hallazgos P1 de memetica, redes, interferencia, reproducibilidad y seguridad.