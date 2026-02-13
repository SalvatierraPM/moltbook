#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


ACT_KEY_TO_ES = {
    "request": "peticion",
    "offer": "oferta",
    "promise": "promesa",
    "declaration": "declaracion",
    "judgment": "juicio",
    "assertion": "afirmacion",
    "acceptance": "aceptacion",
    "rejection": "rechazo",
    "clarification": "aclaracion",
    "unknown": "otro",
}
ACT_ES_TO_KEY = {v: k for k, v in ACT_KEY_TO_ES.items()}


def normalize_label(raw: str) -> str:
    v = (raw or "").strip().lower()
    return v.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ü", "u").replace("ñ", "n")


def to_key(label: str) -> str | None:
    if not label:
        return None
    v = normalize_label(label)
    if v in ACT_ES_TO_KEY:
        return ACT_ES_TO_KEY[v]
    if v in ACT_KEY_TO_ES:
        return v
    if v in {"otro", "unknown", "other", "none", "n/a"}:
        return "unknown"
    return None


def classification_report(y_true: list[str], y_pred: list[str]) -> dict:
    labels = sorted(set(y_true) | set(y_pred))
    tp = Counter()
    fp = Counter()
    fn = Counter()
    for t, p in zip(y_true, y_pred):
        if t == p:
            tp[t] += 1
        else:
            fp[p] += 1
            fn[t] += 1

    by_label = {}
    for lab in labels:
        precision = tp[lab] / (tp[lab] + fp[lab]) if (tp[lab] + fp[lab]) else 0.0
        recall = tp[lab] / (tp[lab] + fn[lab]) if (tp[lab] + fn[lab]) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        by_label[lab] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(tp[lab] + fn[lab]),
        }

    acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true) if y_true else 0.0
    macro_f1 = sum(v["f1"] for v in by_label.values()) / len(by_label) if by_label else 0.0
    return {"accuracy": acc, "macro_f1": macro_f1, "by_label": by_label, "labels": labels}


def confusion_matrix(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, int]]:
    labels = sorted(set(y_true) | set(y_pred))
    mat: dict[str, dict[str, int]] = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        mat[t][p] += 1
    return mat


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ontology speech-act benchmark against human labels.")
    parser.add_argument("--benchmark", default="data/derived/ontology_benchmark_sample.csv")
    parser.add_argument("--out-json", default="data/derived/ontology_benchmark_metrics.json")
    parser.add_argument("--out-confusion", default="data/derived/ontology_benchmark_confusion.csv")
    args = parser.parse_args()

    bench_path = Path(args.benchmark)
    if not bench_path.exists():
        raise SystemExit(f"Benchmark not found: {bench_path}")

    df = pd.read_csv(bench_path)
    if "pred_act_key" not in df.columns:
        raise SystemExit("Benchmark missing pred_act_key column.")
    if "label_act_es" not in df.columns and "label_act_key" not in df.columns:
        raise SystemExit("Benchmark missing label_act_es/label_act_key columns.")

    labels_raw = df["label_act_key"] if "label_act_key" in df.columns else df.get("label_act_es")
    df["label_key"] = labels_raw.fillna("").astype(str).map(to_key)
    df["pred_key"] = df["pred_act_key"].fillna("").astype(str).map(to_key)

    labeled = df[df["label_key"].notna() & df["pred_key"].notna()].copy()
    if labeled.empty:
        print("No labeled rows yet. Fill label_act_es (or label_act_key) and re-run.")
        metrics = {
            "labeled_total": 0,
            "accuracy_overall": 0.0,
            "accuracy_by_lang": {},
            "macro_f1_overall": 0.0,
            "note": "No labeled rows found; metrics not computed.",
        }
        Path(args.out_json).write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    y_true = labeled["label_key"].tolist()
    y_pred = labeled["pred_key"].tolist()
    rep = classification_report(y_true, y_pred)

    # Per-language accuracy
    acc_by_lang: dict[str, float] = {}
    n_by_lang: dict[str, int] = {}
    for lang, g in labeled.groupby("lang"):
        yt = g["label_key"].tolist()
        yp = g["pred_key"].tolist()
        acc_by_lang[str(lang)] = sum(1 for t, p in zip(yt, yp) if t == p) / len(yt) if yt else 0.0
        n_by_lang[str(lang)] = int(len(g))

    metrics = {
        "labeled_total": int(len(labeled)),
        "accuracy_overall": float(rep["accuracy"]),
        "macro_f1_overall": float(rep["macro_f1"]),
        "accuracy_by_lang": acc_by_lang,
        "labeled_by_lang": n_by_lang,
        "by_label": rep["by_label"],
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # Confusion matrix as CSV
    mat = confusion_matrix(y_true, y_pred)
    labels = rep["labels"]
    rows = []
    for t in labels:
        row = {"true": t}
        for p in labels:
            row[p] = mat[t][p]
        rows.append(row)
    pd.DataFrame(rows).to_csv(Path(args.out_confusion), index=False)

    print(f"Labeled rows: {len(labeled)}")
    print(f"Accuracy: {rep['accuracy']:.3f} | Macro-F1: {rep['macro_f1']:.3f}")
    print(f"Wrote: {out_json}")


if __name__ == "__main__":
    main()
