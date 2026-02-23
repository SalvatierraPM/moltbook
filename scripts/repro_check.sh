#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[repro] Running unit tests..."
$PYTHON_BIN -m unittest discover -s tests -p "test_*.py"

if command -v node >/dev/null 2>&1; then
  REQUIRED_DERIVED=(
    "data/derived/ontology_cooccurrence_top.csv"
    "data/derived/public_transmission_samples.csv"
    "data/derived/public_language_distribution.csv"
    "data/derived/coverage_quality.json"
    "data/derived/submolt_stats.csv"
  )

  MISSING=0
  for f in "${REQUIRED_DERIVED[@]}"; do
    if [[ ! -f "$f" ]]; then
      MISSING=1
      break
    fi
  done

  if [[ $MISSING -eq 0 ]]; then
    echo "[repro] Running UI coherence checks..."
    node scripts/check_ui_coherence.js
  else
    echo "[repro] Skipping UI coherence checks (missing data/derived artifacts)."
  fi
else
  echo "[repro] Node.js not found; skipping UI coherence checks."
fi

echo "[repro] OK"
