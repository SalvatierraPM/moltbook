# Human Intervention Robustness

- generated_at: 2026-02-23T16:06:00.197577+00:00
- groups_total: 40426
- baseline: min_group_size=2, min_event_score=3.5, events=1382
- jaccard(top-100) vs baseline: median=0.545717, min=0.37931, max=1.0

## Config Grid

| config_id | min_group_size | min_event_score | event_count | jaccard_top_k_vs_baseline |
|---|---:|---:|---:|---:|
| g2_s3.5 | 2 | 3.5 | 1382 | 1.0 |
| g2_s5.0 | 2 | 5.0 | 1220 | 1.0 |
| g2_s7.0 | 2 | 7.0 | 653 | 1.0 |
| g2_s10.0 | 2 | 10.0 | 231 | 1.0 |
| g2_s12.0 | 2 | 12.0 | 141 | 1.0 |
| g3_s3.5 | 3 | 3.5 | 594 | 0.587302 |
| g3_s5.0 | 3 | 5.0 | 570 | 0.587302 |
| g3_s7.0 | 3 | 7.0 | 471 | 0.587302 |
| g3_s10.0 | 3 | 10.0 | 168 | 0.587302 |
| g3_s12.0 | 3 | 12.0 | 102 | 0.587302 |
| g5_s3.5 | 5 | 3.5 | 300 | 0.438849 |
| g5_s5.0 | 5 | 5.0 | 300 | 0.438849 |
| g5_s7.0 | 5 | 7.0 | 277 | 0.438849 |
| g5_s10.0 | 5 | 10.0 | 129 | 0.438849 |
| g5_s12.0 | 5 | 12.0 | 82 | 0.504132 |
| g8_s3.5 | 8 | 3.5 | 176 | 0.37931 |
| g8_s5.0 | 8 | 5.0 | 176 | 0.37931 |
| g8_s7.0 | 8 | 7.0 | 172 | 0.37931 |
| g8_s10.0 | 8 | 10.0 | 106 | 0.37931 |
| g8_s12.0 | 8 | 12.0 | 75 | 0.458333 |

## Class Stability

| class | median_count | p05 | p95 |
|---|---:|---:|---:|
| campana_promocional | 48.0 | 21.0 | 72.0 |
| coordinacion_hibrida | 1.0 | 1.0 | 1.0 |
| humano_explicito | 114.0 | 43.0 | 768.0 |
| interferencia_semantica | 12.0 | 2.0 | 50.0 |
| mixto | 26.0 | 7.0 | 303.0 |
| narrativa_situada | 0.0 | 0.0 | 9.0 |
| prompt_tooling | 2.0 | 1.0 | 17.0 |

## Robust Events

Definicion: evento presente en >= 70% de configuraciones del grid.

| event_id | share | score | class | repeat | authors | submolts |
|---|---:|---:|---|---:|---:|---:|
| 83e39bdfc138b0bb | 1.0 | 34.3651 | campana_promocional | 75 | 8 | 1 |
| 212c5157cd4e5a51 | 1.0 | 32.7213 | campana_promocional | 31 | 7 | 2 |
| 71988319c8c57d03 | 1.0 | 30.7768 | campana_promocional | 127 | 2 | 63 |
| e39e436060c37c61 | 1.0 | 30.31 | humano_explicito | 32 | 8 | 4 |
| 6b7200b34bd4a394 | 1.0 | 26.5127 | humano_explicito | 221 | 1 | 95 |
| dd496eddade19d0a | 1.0 | 25.0202 | coordinacion_hibrida | 12476 | 7 | 40 |
| 1bc45a37fb9541ab | 1.0 | 23.7372 | campana_promocional | 18 | 9 | 1 |
| 5dbdc2fe57421643 | 1.0 | 23.6552 | prompt_tooling | 8 | 1 | 1 |
| c64e60e3860e0336 | 1.0 | 22.9929 | humano_explicito | 355 | 3 | 139 |
| 4d7eed8e5a2958ac | 1.0 | 20.7512 | humano_explicito | 535 | 2 | 96 |
| 2439bc8b8e5be124 | 1.0 | 20.1416 | campana_promocional | 182 | 1 | 72 |
| a892cd6b85402eaf | 1.0 | 19.8284 | campana_promocional | 124 | 5 | 2 |
| 9ec05d3792e51c6b | 1.0 | 19.4927 | humano_explicito | 42 | 1 | 29 |
| 847c4f436f508580 | 1.0 | 18.8464 | mixto | 25 | 1 | 7 |
| 28b241c7f18fd9a3 | 1.0 | 18.7353 | campana_promocional | 24 | 1 | 1 |
| 6c7ed5dcee2a6d10 | 1.0 | 17.7119 | campana_promocional | 127 | 4 | 2 |
| 065f7397d6c924db | 1.0 | 17.6476 | humano_explicito | 16 | 8 | 2 |
| 62d9141247696aa8 | 1.0 | 17.5436 | humano_explicito | 10 | 2 | 7 |
| db64fef285d73a93 | 1.0 | 17.5368 | humano_explicito | 50 | 1 | 40 |
| d7df51bb96537f5c | 1.0 | 17.3883 | campana_promocional | 139 | 3 | 3 |
| 57a6d2b052a7610e | 1.0 | 17.3612 | campana_promocional | 8 | 8 | 1 |
| 37cde68e6398f1a2 | 1.0 | 17.0859 | campana_promocional | 112 | 1 | 2 |
| eb9f498b8d568494 | 1.0 | 16.3529 | humano_explicito | 318 | 2 | 161 |
| 1874aebdfb8222e8 | 1.0 | 16.2661 | humano_explicito | 65 | 1 | 51 |
| 2f3eb8c6ce2abbf2 | 1.0 | 16.174 | interferencia_semantica | 20 | 1 | 5 |
| 5508ed5d2cabd6c6 | 1.0 | 16.0312 | humano_explicito | 310 | 1 | 11 |
| 661c34656c7d3d83 | 1.0 | 15.8296 | campana_promocional | 10 | 1 | 8 |
| 36ee0b3641f8c211 | 1.0 | 15.6791 | humano_explicito | 11 | 1 | 1 |
| 0c1c1388c233b3bb | 1.0 | 15.6144 | campana_promocional | 40 | 1 | 1 |
| 5f312441d3b96e4f | 1.0 | 15.603 | humano_explicito | 324 | 1 | 148 |
| 99e32670f2ec6119 | 1.0 | 15.5584 | humano_explicito | 124 | 3 | 27 |
| 141b0c1111b033a6 | 1.0 | 15.478 | campana_promocional | 137 | 4 | 2 |
| 28bd6b8fafd575a7 | 1.0 | 15.2996 | mixto | 64 | 1 | 1 |
| f3d422bf11d860af | 1.0 | 15.1706 | humano_explicito | 94 | 1 | 10 |
| 4442f0a7632e19d8 | 1.0 | 15.1325 | humano_explicito | 17 | 1 | 1 |
| d9a07166e17d6e07 | 1.0 | 14.807 | campana_promocional | 117 | 3 | 3 |
| c6fe9a0e8c662e8f | 1.0 | 14.7402 | campana_promocional | 19 | 7 | 1 |
| 2c98a64cf5af7f53 | 1.0 | 14.7219 | campana_promocional | 127 | 3 | 2 |
| bb31fb0ad7289ce0 | 1.0 | 14.6797 | interferencia_semantica | 14 | 1 | 1 |
| 46c75edfb907c5d9 | 1.0 | 14.6717 | humano_explicito | 30 | 15 | 1 |
| caf538948a2a5daf | 1.0 | 14.6472 | campana_promocional | 8 | 1 | 1 |
| b5dce90bf15a6e39 | 1.0 | 14.6372 | humano_explicito | 8 | 2 | 1 |
| cecb7549e8cd28ee | 1.0 | 14.5455 | humano_explicito | 56 | 1 | 36 |
| 0a6c58b907c6e33e | 1.0 | 14.4625 | humano_explicito | 120 | 2 | 17 |
| 82b80447438eb95b | 1.0 | 14.2541 | humano_explicito | 65 | 3 | 33 |
| afff891862084085 | 1.0 | 14.2159 | humano_explicito | 327 | 1 | 11 |
| 459412c0e527b9f7 | 1.0 | 14.1515 | humano_explicito | 66 | 2 | 25 |
| 84c8ebc2579ee8bb | 1.0 | 13.8766 | campana_promocional | 67 | 2 | 2 |
| ed36567b4df0ef5d | 1.0 | 13.8245 | humano_explicito | 329 | 1 | 9 |
| 1c2b11c00729117e | 1.0 | 13.7967 | mixto | 154 | 2 | 63 |
| 252de88866a826a6 | 1.0 | 13.7386 | humano_explicito | 103 | 1 | 3 |
| 6712a0b2de4c4916 | 1.0 | 13.6717 | humano_explicito | 30 | 1 | 17 |
| f912d0e094b6eba2 | 1.0 | 13.5592 | humano_explicito | 314 | 1 | 8 |
| 347d8d13e94da717 | 1.0 | 13.3593 | humano_explicito | 24 | 1 | 18 |
| 2d9eb9445f52e6d6 | 1.0 | 13.0365 | mixto | 17 | 1 | 9 |
| ff5baacbd48ea4a9 | 1.0 | 12.96 | campana_promocional | 20 | 1 | 20 |
| faccfaa5ce6e8dfa | 1.0 | 12.9104 | humano_explicito | 63 | 1 | 39 |
| 8402fd3a26738b09 | 1.0 | 12.8212 | humano_explicito | 8 | 8 | 1 |
| 10b90d071ff0c88f | 1.0 | 12.8212 | humano_explicito | 8 | 8 | 1 |
| ebf1e293ac7fee7e | 1.0 | 12.8212 | humano_explicito | 8 | 8 | 1 |
