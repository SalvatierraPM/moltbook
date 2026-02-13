# Protocolo de Etiquetado — Actos del Habla (Benchmark Ontológico)

Este documento define **cómo etiquetar** la muestra `data/derived/ontology_benchmark_sample.csv` (columna `label_act_es`)
para evaluar el hallazgo **AUD-005**: *“Actos/moods son comparables entre idiomas”*.

La muestra trae una **sugerencia automática** (`pred_act_es`) construida por heurísticas. **No es ground truth**.
La etiqueta `label_act_es` debe reflejar el **acto dominante** según el compromiso social del enunciado.

## Setup

- Archivo a etiquetar: `data/derived/ontology_benchmark_sample.csv`
- Columna a llenar: `label_act_es`
- Etiquetas permitidas:
  - `afirmacion`
  - `declaracion`
  - `juicio`
  - `promesa`
  - `peticion`
  - `oferta`
  - `aceptacion`
  - `rechazo`
  - `aclaracion`
  - `otro`

Para etiquetar en CLI (resumible): `./.venv/bin/python scripts/annotate_ontology_benchmark.py`

## Marco Conceptual (operacional)

El criterio central es identificar el **compromiso social** que se adquiere al emitir el texto:

- **Afirmación (`afirmacion`)**: compromiso con la **veracidad** y **relevancia** de lo dicho (descriptivo/explicativo).
- **Declaración (`declaracion`)**: acto performativo que **instituye/cambia** un estado social o compromete coherencia futura
  (p. ej., “declaro”, “anuncio”, “queda”, “a partir de ahora…”).
- **Juicio (`juicio`)**: evaluación/opinión o norma (“creo que…”, “debería…”, “esto es bueno/malo”), con compromiso de
  estar **fundado** (razonamiento, justificación).
- **Promesa (`promesa`)**: compromiso explícito de acción futura propia (“prometo…”, “haré…”, “vamos a…”), con compromiso de
  **sinceridad** y **competencia** para cumplir.
- **Petición (`peticion`)**: pedido a otro (o al interlocutor) para hacer/decir algo (“¿puedes…?”, “por favor…”, “necesito…”).
  Incluye pedidos de información (“¿qué opinas…?”) cuando el objetivo principal es obtener respuesta.
- **Oferta (`oferta`)**: ofrecimiento de acción futura propia (“puedo ayudarte…”, “me ofrezco…”, “happy to…”).
- **Aceptación (`aceptacion`)**: aceptación explícita de una propuesta/plan/pedido (“acepto”, “ok”, “de acuerdo”).
- **Rechazo (`rechazo`)**: rechazo explícito de una propuesta/plan/pedido (“rechazo”, “no puedo”, “no quiero”, “decline”).
- **Aclaración (`aclaracion`)**: solicitud de clarificación sobre algo dicho (“¿qué quieres decir…?”, “no entiendo…”, “clarifica…”).
- **Otro (`otro`)**: texto insuficiente, ambiguo, meta/ruido, o sin acto dominante claro.

## Regla Principal (acto dominante)

Etiqueta el **acto con mayor fuerza ilocutiva** (lo que el texto *hace* socialmente), no solo lo que “contiene”.
Si hay mezcla:

1. Si la pieza es principalmente un **pedido** (aunque tenga contexto), usa `peticion`.
2. Si el pedido es “explica/aclárame X”, usa `aclaracion`.
3. Si hay **compromiso futuro** (“haré”, “prometo”), prioriza `promesa` sobre `afirmacion`.
4. Si hay **evaluación normativa** (“deberíamos”), prioriza `juicio`.
5. Si nada aplica, `afirmacion` por defecto.

## Casos Límite (para consistencia)

- **Preguntas retóricas (nota corpus Moltbook)**:
  - Si la pieza contiene **interrogativas dirigidas al interlocutor** (p. ej. “¿por qué…?”, “¿qué pasaría si…?”) y la intención plausible es **activar respuesta/diálogo**, etiqueta `peticion` (aunque esté envuelta en un ensayo).
  - Si es claramente un recurso estilístico sin expectativa de respuesta (monólogo), etiqueta `afirmacion` o `juicio`.
- **“Sí/si”**: el “si” condicional en español NO es aceptación. Solo usa `aceptacion` cuando sea explícitamente “sí/ok/acepto”.
- **“Puedo…”**: puede ser oferta (“puedo ayudarte”) o petición (“¿puedo pedirte…?”). Decide por intención.
- **Textos muy largos**: etiqueta por el fragmento visible (`text_excerpt`).
- **Ironía / roleplay**: etiqueta por el compromiso que se desprende del texto literal; si es imposible, `otro` + nota.

## Ejemplos Reales (muestra)

Los ejemplos apuntan a `sample_id` en `ontology_benchmark_sample.csv`:

- `peticion`: `S0001` (“What interests you?”)
- `promesa`: `S0007` (“…prometo.”)
- `rechazo`: `S0159` (“I wont share secrets…” / límites explícitos)
- `afirmacion`: `S0003` (descriptivo + preguntas como marco, sin pedido operativo)
- `juicio`: `S0019` (“Buena pregunta… sería…”, evaluación de prioridad)

Nota: algunas clases (`declaracion`, `oferta`) pueden aparecer poco en esta muestra; cuando ocurra, etiqueta solo si es claro.

## Criterio de Calidad (para cerrar AUD-005)

Después de etiquetar:

1. Ejecutar métricas: `./.venv/bin/python scripts/evaluate_ontology_benchmark.py`
2. Regenerar auditoría: `./.venv/bin/python scripts/generate_audit_package.py`

La auditoría marca **AUD-005 mitigado** cuando hay muestra suficiente por idioma y precisión mínima (ver `scripts/generate_audit_package.py`).
