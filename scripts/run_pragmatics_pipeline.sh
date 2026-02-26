#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

POSTS_PATH="${POSTS_PATH:-data/raw/api_fetch/posts.jsonl}"
COMMENTS_PATH="${COMMENTS_PATH:-data/raw/api_fetch/comments.jsonl}"
INPUT_PATH="${INPUT_PATH:-}"

OUTPUT_DIR="${OUTPUT_DIR:-out/pragmatics}"
WINDOW_DAYS="${WINDOW_DAYS:-30}"
STEP_DAYS="${STEP_DAYS:-7}"
EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-tfidf}"
SCORING_BACKEND="${SCORING_BACKEND:-offline_baseline}"
SEED="${SEED:-42}"
SAMPLE_SIZE="${SAMPLE_SIZE:-400}"
LABELING_CSV="${LABELING_CSV:-}"

usage() {
  cat <<EOF
Usage: scripts/run_pragmatics_pipeline.sh [options]

Options:
  --input PATH              Mixed JSONL input (rows = post/comment)
  --posts PATH              Posts JSONL (default: ${POSTS_PATH})
  --comments PATH           Comments JSONL (default: ${COMMENTS_PATH})
  --output_dir PATH         Output directory (default: ${OUTPUT_DIR})
  --window_days INT         Window size in days (default: ${WINDOW_DAYS})
  --step_days INT           Sliding step in days (default: ${STEP_DAYS})
  --embedding_backend NAME  sentence_transformers|tfidf (default: ${EMBEDDING_BACKEND})
  --scoring_backend NAME    offline_baseline (default: ${SCORING_BACKEND})
  --sample_size INT         Labeling sample size (default: ${SAMPLE_SIZE})
  --labeling_csv PATH       Human-labeled CSV for evaluation (optional)
  --python PATH             Python executable override
  --help                    Show this help

Examples:
  scripts/run_pragmatics_pipeline.sh
  scripts/run_pragmatics_pipeline.sh --output_dir out/pragmatics_30d --window_days 30 --step_days 7
  scripts/run_pragmatics_pipeline.sh --labeling_csv out/pragmatics/labeling_sample_filled.csv
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT_PATH="$2"; shift 2 ;;
    --posts) POSTS_PATH="$2"; shift 2 ;;
    --comments) COMMENTS_PATH="$2"; shift 2 ;;
    --output_dir) OUTPUT_DIR="$2"; shift 2 ;;
    --window_days) WINDOW_DAYS="$2"; shift 2 ;;
    --step_days) STEP_DAYS="$2"; shift 2 ;;
    --embedding_backend) EMBEDDING_BACKEND="$2"; shift 2 ;;
    --scoring_backend) SCORING_BACKEND="$2"; shift 2 ;;
    --sample_size) SAMPLE_SIZE="$2"; shift 2 ;;
    --labeling_csv) LABELING_CSV="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

echo "[1/3] Running full pragmatics pipeline..."
if [[ -n "$INPUT_PATH" ]]; then
  PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m moltbook_pragmatics.run run \
    --input "$INPUT_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --window_days "$WINDOW_DAYS" \
    --step_days "$STEP_DAYS" \
    --embedding_backend "$EMBEDDING_BACKEND" \
    --scoring_backend "$SCORING_BACKEND" \
    --seed "$SEED"
else
  if [[ ! -f "$POSTS_PATH" || ! -f "$COMMENTS_PATH" ]]; then
    echo "Missing input files. Expected posts/comments or use --input." >&2
    exit 1
  fi
  PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m moltbook_pragmatics.run run \
    --posts "$POSTS_PATH" \
    --comments "$COMMENTS_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --window_days "$WINDOW_DAYS" \
    --step_days "$STEP_DAYS" \
    --embedding_backend "$EMBEDDING_BACKEND" \
    --scoring_backend "$SCORING_BACKEND" \
    --seed "$SEED"
fi

echo "[2/3] Building stratified labeling sample..."
if [[ -n "$INPUT_PATH" ]]; then
  PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m moltbook_pragmatics.run sample \
    --input "$INPUT_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --sample_size "$SAMPLE_SIZE" \
    --embedding_backend "$EMBEDDING_BACKEND" \
    --seed "$SEED"
else
  PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m moltbook_pragmatics.run sample \
    --posts "$POSTS_PATH" \
    --comments "$COMMENTS_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --sample_size "$SAMPLE_SIZE" \
    --embedding_backend "$EMBEDDING_BACKEND" \
    --seed "$SEED"
fi

if [[ -n "$LABELING_CSV" ]]; then
  echo "[3/3] Evaluating human labels..."
  if [[ ! -f "$LABELING_CSV" ]]; then
    echo "Labeling CSV not found: $LABELING_CSV" >&2
    exit 1
  fi
  PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m moltbook_pragmatics.run evaluate \
    --labeling_csv "$LABELING_CSV" \
    --output_dir "$OUTPUT_DIR"
else
  echo "[3/3] Skipping evaluation (no --labeling_csv provided)."
fi

echo "Done. Outputs in: $OUTPUT_DIR"
