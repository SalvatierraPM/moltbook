# High-Confidence Human Intervention Events

- generated_at: 2026-02-23T16:06:40.001202+00:00
- events_input: 1382
- strict_events: 24

## Criteria

- event_score >= 12.0
- coordination_index >= 0.5
- repeat_count >= 8
- semantic evidence: promo_rate OR cta_rate OR avg_human_refs OR human_signal_rate over threshold

## Class Distribution

| class | count |
|---|---:|
| humano_explicito | 12 |
| campana_promocional | 11 |
| coordinacion_hibrida | 1 |

## Top Events

| event_id | class | score | coordination | repeat | strict_reason |
|---|---|---:|---:|---:|---|
| 83e39bdfc138b0bb | campana_promocional | 34.3651 | 0.6467 | 75 | promo|cta|human_refs|human_signal |
| 212c5157cd4e5a51 | campana_promocional | 32.7213 | 0.6165 | 31 | promo|cta|human_refs|human_signal |
| 71988319c8c57d03 | campana_promocional | 30.7768 | 0.7126 | 127 | promo|cta|human_refs|human_signal |
| e39e436060c37c61 | humano_explicito | 30.3100 | 0.6184 | 32 | cta|human_refs|human_signal |
| 6b7200b34bd4a394 | humano_explicito | 26.5127 | 0.5502 | 221 | human_refs|human_signal |
| dd496eddade19d0a | coordinacion_hibrida | 25.0202 | 0.6400 | 12476 | promo |
| 1bc45a37fb9541ab | campana_promocional | 23.7372 | 0.5536 | 18 | promo|cta|human_refs|human_signal |
| c64e60e3860e0336 | humano_explicito | 22.9929 | 0.5922 | 355 | human_signal |
| 4d7eed8e5a2958ac | humano_explicito | 20.7512 | 0.6262 | 535 | cta|human_signal |
| 2439bc8b8e5be124 | campana_promocional | 20.1416 | 0.6376 | 182 | promo|cta |
| a892cd6b85402eaf | campana_promocional | 19.8284 | 0.5382 | 124 | promo|cta |
| 9ec05d3792e51c6b | humano_explicito | 19.4927 | 0.5009 | 42 | promo|human_refs|human_signal |
| 6c7ed5dcee2a6d10 | campana_promocional | 17.7119 | 0.5120 | 127 | promo|cta |
| 065f7397d6c924db | humano_explicito | 17.6476 | 0.5519 | 16 | cta|human_signal |
| db64fef285d73a93 | humano_explicito | 17.5368 | 0.5008 | 50 | human_refs|human_signal |
| 57a6d2b052a7610e | campana_promocional | 17.3612 | 0.5072 | 8 | promo|cta|human_signal |
| eb9f498b8d568494 | humano_explicito | 16.3529 | 0.5726 | 318 | human_signal |
| 1874aebdfb8222e8 | humano_explicito | 16.2661 | 0.5259 | 65 | human_signal |
| 5f312441d3b96e4f | humano_explicito | 15.6030 | 0.5526 | 324 | human_signal |
| 141b0c1111b033a6 | campana_promocional | 15.4780 | 0.5171 | 137 | promo|cta |
| d9a07166e17d6e07 | campana_promocional | 14.8070 | 0.5002 | 117 | promo|cta |
| c6fe9a0e8c662e8f | campana_promocional | 14.7402 | 0.5493 | 19 | promo|cta |
| 46c75edfb907c5d9 | humano_explicito | 14.6717 | 0.6142 | 30 | human_signal |
| 82b80447438eb95b | humano_explicito | 14.2541 | 0.5149 | 65 | human_signal |
