# Reproducibility Guide

This repository is intended to be reproducible end-to-end from source code, dependency lockfile, and auditable scripts.

## 1) Environment

Use Python 3.11+ and a fresh virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -e .
```

Optional (for UI coherence checks): Node.js 18+.

## 2) Baseline validation

Run the reproducibility smoke checks:

```bash
PYTHON_BIN=python scripts/repro_check.sh
```

What it validates:
- Python unit tests (`tests/test_*.py`).
- UI coherence checks (`scripts/check_ui_coherence.js`) when required `data/derived` artifacts are present.

## 3) Rebuild the study artifacts

Fetch public data (respecting robots/ToS):

```bash
python scripts/fetch_moltbook_api.py \
  --out-dir data/raw/api_fetch \
  --rate-limit-rps 4 \
  --submolt-sorts new \
  --requeue-submolts
```

Run the analysis pipeline:

```bash
python -m moltbook_analysis.cli normalize
python -m moltbook_analysis.cli analyze
python -m moltbook_analysis.cli report
```

Rebuild public derived layers used by the UI:

```bash
python scripts/derive_signals.py \
  --posts data/raw/api_fetch/posts.jsonl \
  --comments data/raw/api_fetch/comments.jsonl \
  --out-dir data/derived
```

## 4) Provenance and audit trail

Capture environment and run provenance before publishing results:

```bash
python --version
python -m pip freeze | sort > reports/env_freeze.txt
git rev-parse HEAD > reports/source_commit.txt
```

Use existing audit scripts/reports in `reports/audit/` to attach interpretation claims to data lineage evidence.

## 5) Data and publication scope

- Large/raw artifacts are intentionally ignored from Git to keep the repository source-first.
- Reproducibility is achieved by scripts + lockfile + documented commands, not by shipping all raw captures.
