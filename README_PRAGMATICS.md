# Moltbook Pragmatics

Diagnostic + descriptive cultural-ontological analysis over posts/comments to compare communities and detect temporal shifts.

## What the indices mean
- `conflict_index` (0-1): dominance + low politeness + negative affect + escalation.
- `coordination_index` (0-1): coordination intent + interaction uptake.
- `rigidity_score` (0-1): high certainty + dominance + low stance variance.
- `dominance_vs_reciprocity` (0-1): conversational asymmetry (dominance over reciprocity).
- `identity_vs_task_orientation` (0-1): performative/identity orientation vs task coordination.
- `diversity_of_inquietudes` (0-1): entropy over concern-at-stake distribution.
- `structural_entropy` (0-1): dispersion over illocution + stance + inquietud.

## Run full pipeline
```bash
python -m moltbook_pragmatics.run run \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --output_dir out/pragmatics \
  --window_days 30 \
  --step_days 7 \
  --embedding_backend sentence_transformers \
  --scoring_backend offline_baseline
```

One-command wrapper:
```bash
scripts/run_pragmatics_pipeline.sh
```

With human-labeled evaluation file:
```bash
scripts/run_pragmatics_pipeline.sh --labeling_csv out/pragmatics/labeling_sample_filled.csv
```

Mixed input mode:
```bash
python -m moltbook_pragmatics.run run --input data.jsonl --output_dir out/pragmatics
```

Outputs:
- `enriched_messages.jsonl`
- `interactions.jsonl`
- `enriched_memes.jsonl`
- `community_windows.jsonl`
- `diagnostics_report.json`

## Human labeling and evaluation
Create stratified labeling sample:
```bash
python -m moltbook_pragmatics.run sample \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --output_dir out/pragmatics_eval \
  --sample_size 400
```

Evaluate annotations (`human_*` columns filled):
```bash
python -m moltbook_pragmatics.run evaluate \
  --labeling_csv out/pragmatics_eval/labeling_sample.csv \
  --output_dir out/pragmatics_eval
```

## Interpretation quick guide
- Compare communities using `diagnostics_report.json > community_profiles`.
- Track evolution with `community_windows.jsonl` deltas and `alerts.has_change_point`.
- Use `enriched_memes.jsonl > explain` to inspect examples driving high conflict/rigidity.
