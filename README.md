# Moltbook Observatory

An open, auditable, and reproducible observatory for AI-agent culture in Moltbook.

This repository provides a full pipeline to:
- collect public platform data (API first, HTML fallback),
- normalize and enrich the corpus,
- compute memetic / ontological / sociological signals,
- publish a transparent report and public web layers.

## Why this repository exists

The goal is to donate a complete research workflow, not only final charts.

That means:
- clear data lineage,
- repeatable scripts,
- explicit methodological limits,
- public-facing outputs that can be audited.

## Scope

This project studies public behavior and language patterns in Moltbook, including:
- memetic diffusion,
- language ontology signals,
- interaction structure,
- human-intervention / interference indicators.

It is **not** a causal proof engine. It is an interpretable observational system.

## Ethics and compliance

Only run data collection when authorized by platform policy.

- Respect `robots.txt` and Terms of Service.
- Do not collect private data.
- Rate-limit requests.
- Prefer official APIs when available.

## Project structure

- `src/moltbook_analysis/`: package modules (ingest, normalize, analyze, report)
- `scripts/`: reproducible pipelines and derived-data builders
- `tests/`: unit and regression checks
- `site/`: public UI layers
- `reports/`: generated reports and audit artifacts
- `data/`: local raw/normalized/derived artifacts (ignored for source-first repo)

## Quick start

1. Create environment and install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -e .
```

2. Configure optional environment variables:
- `MOLTBOOK_BASE_URL` (default: `https://www.moltbook.com`)
- `MOLTBOOK_API_TOKEN`
- `MOLTBOOK_RATE_LIMIT_RPS`
- `MOLTBOOK_USER_AGENT`

3. Run baseline pipeline.

```bash
python -m moltbook_analysis.cli ingest --source api --since 2026-01-28
python -m moltbook_analysis.cli normalize
python -m moltbook_analysis.cli analyze
python -m moltbook_analysis.cli report
```

## Reproducibility (official)

- Full guide: [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
- One-command smoke check:

```bash
PYTHON_BIN=python scripts/repro_check.sh
```

This executes:
- `tests/test_*.py`
- UI coherence checks when required derived artifacts exist.

## Data collection workflows

### API collection (recommended)

```bash
python scripts/fetch_moltbook_api.py \
  --out-dir data/raw/api_fetch \
  --rate-limit-rps 4 \
  --submolt-sorts new \
  --requeue-submolts
```

Two-pass fast mode:

Pass 1 (posts only):
```bash
python scripts/fetch_moltbook_api.py \
  --out-dir data/raw/api_fetch \
  --rate-limit-rps 4 \
  --submolt-sorts new \
  --requeue-submolts \
  --no-global \
  --skip-comments \
  --no-log-requests
```

Pass 2 (comments only):
```bash
python scripts/fetch_moltbook_api.py \
  --out-dir data/raw/api_fetch \
  --rate-limit-rps 4 \
  --comments-only \
  --no-log-requests
```

### HTML collection (fallback only)

Static HTML:
```bash
python -m moltbook_analysis.cli ingest --source html --path /
```

Dynamic HTML (Playwright):
```bash
pip install playwright
playwright install
python -m moltbook_analysis.cli ingest --source html --dynamic --path /
```

Debug mode:
```bash
python -m moltbook_analysis.cli ingest --source html --dynamic --path / \
  --allow-no-robots --dump-html data/raw/html --dump-screenshot data/raw/html
```

Local parse without network:
```bash
python -m moltbook_analysis.cli ingest --local-html data/raw/html
```

## Core analysis scripts

Derive language and intervention signals:
```bash
python scripts/derive_signals.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Extract graph edges:
```bash
python scripts/extract_edges.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Build context datasets for embeddings/VSM:
```bash
python scripts/build_context_dataset.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Diffusion run metrics:
```bash
python scripts/diffusion_metrics.py \
  --listings data/raw/api_fetch/listings.jsonl \
  --out-dir data/derived
```

Temporal contract audit (`created_at` vs `run_time`):
```bash
python3 scripts/temporal_contract_audit.py \
  --coverage data/derived/coverage_quality.json \
  --diffusion-runs data/derived/diffusion_runs.csv \
  --lineage reports/audit/data_lineage.csv \
  --out-json data/derived/temporal_contract_audit.json \
  --out-md reports/temporal_contract_audit.md
```

Quantitative sociology metrics:
```bash
python scripts/quant_sociology.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --edges-replies data/derived/edges_replies.csv \
  --edges-mentions data/derived/edges_mentions.csv \
  --out-dir data/derived
```

Automatic sociological interpretation layer:
```bash
python3 scripts/build_sociology_interpretation.py \
  --derived data/derived \
  --out-json data/derived/public_sociology_interpretation.json \
  --out-md reports/interpretacion_sociologica_auto.md
```

Memetic multi-level modeling:
```bash
python scripts/meme_models.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

## Public web layers (`site/`)

- `site/index.html`: Public Observatory (Layer 1)
- `site/analysis.html`: Interactive Exploration (Layer 2)
- `site/audit.html`: Methodology & Audit (Layer 3)
- `site/about.html`: project framing and context

## Outputs

- `data/raw/`: captured source data
- `data/normalized/`: normalized entities
- `data/derived/`: computed metrics/features
- `reports/`: written reports and audit docs
- `site/`: public consumable UI and assets

## Validation and quality gates

Local checks:

```bash
PYTHON_BIN=.venv/bin/python scripts/repro_check.sh
```

This repository is prepared for CI-based reproducibility checks using lockfile + smoke tests.

## Limitations

- Any HTML workflow can break if DOM/platform changes.
- Statistical regularities are not direct causal proof.
- Coverage is bounded by collection window and access constraints.

## Citation and attribution

If you reuse this repository, please reference:
- commit hash,
- collection window,
- configuration profile,
- and any methodological deviations.

## License

MIT. See [LICENSE](LICENSE).
