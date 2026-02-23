# Human Intervention Annotation Guide

- generated_at: 2026-02-23T16:05:03.327869+00:00
- sample_size_total: 157

## Objetivo
Validar manualmente si los eventos detectados corresponden a intervencion humana/coordinacion externa y no solo a estilo discursivo.

## Unidades
- `event_id`: grupo canonico de textos similares.
- `sample_excerpt`: evidencia textual principal.
- `repeat_count`, `unique_authors`, `unique_submolts`: evidencia estructural de coordinacion.

## Etiquetas permitidas
- `campana_promocional`: CTA repetida, urgencia/escasez, patron de growth-farming o amplificacion.
- `prompt_tooling`: lenguaje de instrucciones/prompts + detalles tecnicos operativos.
- `interferencia_semantica`: huellas de inyeccion, bypass o instrucciones metacontextuales.
- `humano_explicito`: referencia directa a humano/operador/usuario como actor causal.
- `coordinacion_hibrida`: repeticion transversal (autores/submolts) sin patron puramente promo.
- `narrativa_situada`: relato personal contextualizado sin evidencia fuerte de campana.
- `mixto`: evidencia combinada sin dominante clara.
- `falso_positivo`: la prediccion no representa intervencion humana/coordinacion relevante.

## Reglas de decision
1. Priorizar estructura (repeticion + dispersion) sobre una sola palabra clave.
2. Si hay conflicto entre texto y estructura, documentar en `annotator_notes`.
3. Usar `gold_confidence` en [0,1] y evitar 1.0 salvo evidencia contundente.

## Criterio de calidad recomendado
- Dos anotadores independientes.
- Medir acuerdo (Cohen's kappa) y adjudicar desacuerdos.
- Publicar matriz de confusion modelo vs gold.
