#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_CANDIDATES=(
  "$ROOT_DIR/data/derived"
  "$ROOT_DIR/tmp/netlify_publish/data/derived"
  "$ROOT_DIR/reports/audit"
)
DST_DIR="$ROOT_DIR/site/derived"

REQUIRED_FILES=(
  "submolt_stats.csv"
  "diffusion_runs.csv"
  "diffusion_submolts.csv"
  "meme_candidates.csv"
  "meme_candidates_technical.csv"
  "meme_candidates_cultural.csv"
  "meme_classification.csv"
  "meme_bursts.csv"
  "public_language_distribution.csv"
  "reply_graph_centrality.csv"
  "reply_graph_summary.json"
  "mention_graph_centrality.csv"
  "mention_graph_summary.json"
  "reply_graph_communities.csv"
  "mention_graph_communities.csv"
  "public_transmission_samples.csv"
  "author_stats.csv"
  "coverage_quality.json"
  "ontology_summary.csv"
  "ontology_concepts_top.csv"
  "ontology_cooccurrence_top.csv"
  "ontology_submolt_embedding_2d.csv"
  "ontology_submolt_full.csv"
  "interference_summary.csv"
  "public_embeddings_summary.json"
  "public_doc_lookup.json"
  "public_submolt_examples.csv"
  "transmission_vsm_baseline.json"
  "embeddings_post_comment/public_embeddings_post_comment_summary.json"
)

OPTIONAL_FILES=(
  "public_sociology_interpretation.json"
  "claim_matrix.csv"
  "ontology_benchmark_metrics.json"
)

rm -rf "$DST_DIR"
mkdir -p "$DST_DIR"

resolve_source() {
  local rel="$1"
  local candidate
  for candidate in "${SRC_CANDIDATES[@]}"; do
    if [[ -f "$candidate/$rel" ]]; then
      printf "%s\n" "$candidate/$rel"
      return 0
    fi
  done
  return 1
}

copied_required=0
copied_optional=0
for rel in "${REQUIRED_FILES[@]}"; do
  if ! src="$(resolve_source "$rel")"; then
    echo "Missing required derived file in all sources: $rel" >&2
    exit 1
  fi
  dst="$DST_DIR/$rel"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  copied_required=$((copied_required + 1))
done

for rel in "${OPTIONAL_FILES[@]}"; do
  if src="$(resolve_source "$rel")"; then
    dst="$DST_DIR/$rel"
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    copied_optional=$((copied_optional + 1))
  elif git cat-file -e "HEAD:data/derived/$rel" 2>/dev/null; then
    dst="$DST_DIR/$rel"
    mkdir -p "$(dirname "$dst")"
    git show "HEAD:data/derived/$rel" > "$dst"
    copied_optional=$((copied_optional + 1))
  elif git cat-file -e "HEAD:reports/audit/$rel" 2>/dev/null; then
    dst="$DST_DIR/$rel"
    mkdir -p "$(dirname "$dst")"
    git show "HEAD:reports/audit/$rel" > "$dst"
    copied_optional=$((copied_optional + 1))
  fi
done

echo "Synced $copied_required required and $copied_optional optional files into $DST_DIR"
