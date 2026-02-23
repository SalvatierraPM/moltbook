# Temporal Contract Audit

- generated_at: 2026-02-23T13:55:47.223787+00:00
- definitions:
  - created_at: publication timestamp in the platform.
  - run_time: scraper capture timestamp per run.

## Summary

- created_at window: 2026-01-28T00:00:49.827751+00:00 -> 2026-02-11T21:06:53.498583+00:00 (14.8792 days)
- run_time window: 2026-02-05T15:02:00.919213+00:00 -> 2026-02-11T14:12:15.114851+00:00 (5.9654 days, runs=27)
- created/run window ratio: 2.4942
- missing created_at rate: 0.0
- run cadence (hours): median=1.765 min=0.043 max=41.095

## Checks

| id | status | message |
|---|---|---|
| CHK-001 | PASS | created_at window is parseable and ordered. |
| CHK-002 | PASS | run_time window is parseable and ordered. |
| CHK-003 | PASS | created_at window should usually be >= run_time window for scrape snapshots. |
| CHK-004 | PASS | Missing created_at fields should remain near zero. |
| CHK-005 | PASS | Each run_id should map to a single run_time. |
| CHK-006 | WARN | run_time should stay close to run_id timestamp. |
| CHK-007 | PASS | Metric lineage should declare a clear time_axis (created_at or run_time). |

## Recommendations

- Use created_at for publication-time questions (activity, seasonality, language shifts, meme birth/death).
- Use run_time only for capture-process questions (scraper cadence, coverage by run, snapshot comparability).
- Label every chart/table with its time axis to avoid mixing publication rhythm with capture rhythm.
- Align run_id generation and scrape timestamp capture to reduce drift and improve reproducibility.

## Lineage Axis Counts

- created_at: 4
- created_at (indirecto): 1
- run_time: 1

