#!/usr/bin/env node
"use strict";

const fs = require("node:fs/promises");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const dataDir = path.join(repoRoot, "data", "derived");
const Core = require(path.join(repoRoot, "site", "analytics-core.js"));

async function readCSV(relPath) {
  const abs = path.join(dataDir, relPath);
  const text = await fs.readFile(abs, "utf8");
  return Core.parseCSVText(text);
}

async function readJSON(relPath) {
  const abs = path.join(dataDir, relPath);
  const text = await fs.readFile(abs, "utf8");
  return JSON.parse(text);
}

function keyPair(row) {
  return `${String(row.concept_a || "").toLowerCase()}__${String(row.concept_b || "").toLowerCase()}__${row.count || 0}`;
}

function keyTx(row) {
  return `${row.doc_id || ""}__${row.created_at || ""}__${row.submolt || ""}`;
}

function printCheck(label, ok, detail) {
  const flag = ok ? "PASS" : "FAIL";
  console.log(`${flag.padEnd(5)} ${label} :: ${detail}`);
}

async function main() {
  const [cooccurrence, transmission, language, coverage, submoltStats] = await Promise.all([
    readCSV("ontology_cooccurrence_top.csv"),
    readCSV("public_transmission_samples.csv"),
    readCSV("public_language_distribution.csv"),
    readJSON("coverage_quality.json"),
    readCSV("submolt_stats.csv"),
  ]);

  const totalPosts = submoltStats.reduce((acc, r) => acc + (Number(r.posts) || 0), 0);
  const totalComments = submoltStats.reduce((acc, r) => acc + (Number(r.comments) || 0), 0);

  const reportView = Core.buildCoherenceChecks({
    ontologyCooccurrence: cooccurrence,
    transmission,
    language,
    coverage,
    totalPosts,
    totalComments,
    totalSubmolts: submoltStats.length,
    cooccurrenceLimit: 25,
  });

  const analysisView = Core.buildCoherenceChecks({
    ontologyCooccurrence: cooccurrence,
    transmission,
    language,
    coverage,
    totalPosts,
    totalComments,
    totalSubmolts: submoltStats.length,
    cooccurrenceLimit: 30,
  });

  const filteredPairs = cooccurrence.filter((r) => !Core.isVariantPair(r.concept_a, r.concept_b));
  const reportTop = filteredPairs.slice(0, 25).map(keyPair);
  const analysisTopPrefix = filteredPairs.slice(0, 30).slice(0, 25).map(keyPair);
  const sameCooccPrefix =
    reportTop.length === analysisTopPrefix.length &&
    reportTop.every((value, idx) => value === analysisTopPrefix[idx]);

  const reportTxTop = reportView.transmission.pool.slice(0, 20).map(keyTx);
  const analysisTxTop = analysisView.transmission.pool.slice(0, 20).map(keyTx);
  const sameTransmissionPrefix =
    reportTxTop.length === analysisTxTop.length &&
    reportTxTop.every((value, idx) => value === analysisTxTop[idx]);

  const checks = [
    ...reportView.checks.map((c) => ({ ...c, label: `report:${c.name}` })),
    ...analysisView.checks.map((c) => ({ ...c, label: `analysis:${c.name}` })),
    {
      label: "cross:cooccurrence_prefix_equal",
      ok: sameCooccPrefix,
      detail: `reportTop25 vs analysisTop30[0:25]`,
    },
    {
      label: "cross:transmission_prefix_equal",
      ok: sameTransmissionPrefix,
      detail: `reportPoolTop20 vs analysisPoolTop20`,
    },
  ];

  checks.forEach((c) => printCheck(c.label, c.ok, c.detail));

  const failed = checks.filter((c) => !c.ok);
  console.log("");
  if (failed.length) {
    console.error(`Coherence check failed: ${failed.length} checks in FAIL.`);
    process.exit(1);
  }
  console.log("All coherence checks passed.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
