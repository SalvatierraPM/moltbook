# Moltbook Memetic & Ontology Analysis

This project builds a reproducible pipeline to collect public Moltbook data (subject to ToS/robots), normalize it, and produce an academic-style report on memetics, language ontology, and human interference signals.

## What this does
- Ingests posts/comments via API (preferred) or HTML (fallback).
- Normalizes and stores data in JSONL/Parquet.
- Computes memetic diffusion, topic/ontology structures, and interference signals.
- Generates a paper-style report in Markdown with charts.

## Acerca del proyecto (ES)
Hice este proyecto para construir un observatorio reproducible sobre cultura IA en Moltbook: memes, patrones de lenguaje, estructura social y señales de “interferencia/incidencia humana” como herramientas de exploracion (no como pruebas causales).

No soy experto en linguistica, sociologia o seguridad. El enfoque esta intencionalmente orientado a interpretabilidad y auditoria: reglas simples, datasets derivados verificables y limites explicitados.

Mi plan es que el repo sea open source (scraper + embeddings + UI + derivados). La redistribucion de datos crudos puede estar limitada por robots/ToS; incluso en ese caso, el pipeline permite reproducirlos localmente.

## Ethics & compliance
- Only collect data you are authorized to access.
- Respect `robots.txt` and Terms of Service.
- Rate-limit requests and avoid collecting private/PII data.

## Quick start
1. Create a virtualenv and install dependencies.
2. Configure `MOLTBOOK_BASE_URL` and optional `MOLTBOOK_API_TOKEN`.
3. Run the pipeline:

```bash
python -m moltbook_analysis.cli ingest --source api --since 2026-01-28
python -m moltbook_analysis.cli normalize
python -m moltbook_analysis.cli analyze
python -m moltbook_analysis.cli report
```

### HTML scraping (only if allowed by robots/ToS)
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

Note: the HTML ingestor checks `robots.txt`. If it cannot be fetched, it aborts.
To proceed when `robots.txt` is missing (404), use `--allow-no-robots` only if ToS permits it.

Debugging HTML parsing:
```bash
python -m moltbook_analysis.cli ingest --source html --dynamic --path / \\
  --allow-no-robots --dump-html data/raw/html --dump-screenshot data/raw/html
```

Parse a local HTML dump (no network):
```bash
python -m moltbook_analysis.cli ingest --local-html data/raw/html
```

Deep crawl (Playwright):
```bash
python mbk.py crawl --allow-no-robots --max-scrolls 20
```

If `python -m moltbook_analysis.cli` fails with `ModuleNotFoundError`, use `python mbk.py ...`

Stream progress while crawling:
```bash
python mbk.py crawl --allow-no-robots --stream-dir data/raw/stream
```

Log every post page visit (verbose):
```bash
python mbk.py crawl --allow-no-robots --log-post-pages
```

Full logging (URLs, metrics, errors, network):
```bash
python mbk.py crawl --allow-no-robots \\
  --stream-dir data/raw/stream \\
  --log-urls --log-file data/raw/crawl.log \\
  --metrics-csv data/raw/crawl_metrics.csv \\
  --errors-jsonl data/raw/crawl_errors.jsonl \\
  --netlog data/raw/netlog.jsonl --netlog-types xhr,fetch
```

If submolts seem capped, increase scrolls:
```bash
python mbk.py crawl --allow-no-robots --submolt-scrolls 30
```

## Configuration
Environment variables (optional):
- `MOLTBOOK_BASE_URL` (default: `https://www.moltbook.com`)
- `MOLTBOOK_API_TOKEN` (if API requires auth)
- `MOLTBOOK_RATE_LIMIT_RPS` (default: 1.0)
- `MOLTBOOK_USER_AGENT`

## Outputs
- Raw data: `data/raw/`
- Normalized data: `data/normalized/`
- Derived features: `data/derived/`
- Reports: `reports/`

## Web layers (site/)
- `site/index.html`: Capa 1 (Observatorio publico). Lectura curada para publico general.
- `site/analysis.html`: Capa 2 (Exploracion). Inspeccion interactiva con filtros y drill-down.
- `site/audit.html`: Capa 3 (Metodologia y Auditoria). Contrato de metricas, trazabilidad y coherencia.

## Interpretables and matchmaking
Derive ontologia del lenguaje signals, human incidence markers, and vector space matches:
```bash
python scripts/derive_signals.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Extract network edges (mentions, hashtags, links):
```bash
python scripts/extract_edges.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Build context-enriched datasets for VSM:
```bash
python scripts/build_context_dataset.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Compute diffusion metrics using run_id snapshots:
```bash
python scripts/diffusion_metrics.py \
  --listings data/raw/api_fetch/listings.jsonl \
  --out-dir data/derived
```

## Quantitative sociology metrics
Build submolt/author stats and interaction graphs:
```bash
python scripts/quant_sociology.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --edges-replies data/derived/edges_replies.csv \
  --edges-mentions data/derived/edges_mentions.csv \
  --out-dir data/derived
```

## Sociological interpretation (auto)
Generate an auditable narrative layer (JSON for UI + Markdown for reports) directly from `data/derived`:
```bash
python3 scripts/build_sociology_interpretation.py \
  --derived data/derived \
  --out-json data/derived/public_sociology_interpretation.json \
  --out-md reports/interpretacion_sociologica_auto.md
```

## Memetic modeling (multi-level)
Lexical, semantic, ritual, and macro memes with hourly time series:
```bash
python scripts/meme_models.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

Includes Hawkes (discrete approximation), SIR proxy, and survival curves if `lifelines` is installed.

## Faster scraping workflow (two-pass)
Pass 1: posts only (fast coverage).
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

Pass 2: comments only (uses existing posts.jsonl).
```bash
python scripts/fetch_moltbook_api.py \
  --out-dir data/raw/api_fetch \
  --rate-limit-rps 4 \
  --comments-only \
  --no-log-requests
```

## Notes
- HTML scraper is a fallback and may need tuning once the DOM is confirmed.
- If ToS prohibits scraping, use only official APIs.
