#!/usr/bin/env python3
from __future__ import annotations

"""
Interactive CLI annotator for the ontology speech-act benchmark.

Goal: produce a *human-labeled* column `label_act_es` on
`data/derived/ontology_benchmark_sample.csv` so we can evaluate whether
speech-act signals are comparable across languages (AUD-005).

Design constraints:
- No backend; labels live in the CSV (versionable, auditable).
- Resume-safe: we write after every decision.
"""

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd


ALLOWED = [
    "peticion",
    "oferta",
    "promesa",
    "declaracion",
    "juicio",
    "afirmacion",
    "aceptacion",
    "rechazo",
    "aclaracion",
    "otro",
]

NUM_TO_LABEL = {str(i + 1): lab for i, lab in enumerate(ALLOWED[:-1])}
NUM_TO_LABEL["0"] = "otro"


def normalize(raw: str) -> str:
    v = (raw or "").strip().lower()
    # Keep it simple and permissive (accents are handled by evaluation too).
    return v.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ü", "u").replace("ñ", "n")


def is_valid(label: str) -> bool:
    return normalize(label) in set(ALLOWED)


def safe_excerpt(text: str, max_chars: int = 520) -> str:
    t = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def backup_once(path: Path) -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    if bak.exists():
        return
    bak.write_bytes(path.read_bytes())


def print_help() -> None:
    print("")
    print("Etiquetado: escribe un numero y Enter.")
    for k in sorted(NUM_TO_LABEL, key=lambda x: int(x) if x.isdigit() else 999):
        print(f"  {k}: {NUM_TO_LABEL[k]}")
    print("Comandos:")
    print("  Enter: aceptar sugerencia (pred_act_es) si existe; si no, saltar")
    print("  s: saltar (dejar vacio)")
    print("  b: volver 1 fila")
    print("  q: guardar y salir")
    print("  ?: ver ayuda")
    print("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate ontology benchmark speech-acts (Spanish labels).")
    parser.add_argument("--csv", default="data/derived/ontology_benchmark_sample.csv")
    parser.add_argument("--resume", action="store_true", help="Resume from existing labels (default).")
    parser.add_argument(
        "--blind",
        action="store_true",
        help="Hide model suggestion (pred_act_es) to reduce anchoring bias during manual labeling.",
    )
    parser.add_argument("--max-chars", type=int, default=520)
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"Benchmark CSV not found: {path}")

    df = pd.read_csv(path)
    required = {"sample_id", "lang", "pred_act_es", "pred_act_score", "text_excerpt", "label_act_es"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Benchmark CSV missing columns: {missing}")

    backup_once(path)

    idx = 0
    total = len(df)
    print_help()

    while 0 <= idx < total:
        row = df.iloc[idx]
        current = str(row.get("label_act_es") or "").strip()
        if args.resume and current and is_valid(current):
            idx += 1
            continue

        sample_id = row.get("sample_id")
        lang = row.get("lang") or "unknown"
        submolt = row.get("submolt") if "submolt" in df.columns else ""
        pred = str(row.get("pred_act_es") or "").strip()
        pred_norm = normalize(pred)
        pred_ok = pred_norm in set(ALLOWED)
        suggestion = "" if args.blind else (pred_norm if pred_ok else "")
        score = row.get("pred_act_score")
        excerpt = safe_excerpt(str(row.get("text_excerpt") or ""), max_chars=int(args.max_chars))

        labeled_now = int(df["label_act_es"].fillna("").astype(str).map(is_valid).sum())
        remaining = total - labeled_now

        print("")
        pred_line = "pred=∅" if args.blind else f\"pred={pred_norm or 'n/a'} (score={score})\"
        print(f\"[{idx+1}/{total}] {sample_id} · lang={lang} · submolt={submolt} · {pred_line}\")
        print("-" * 90)
        print(excerpt)
        print("-" * 90)
        sug_txt = "oculta (--blind)" if args.blind else (suggestion or "∅")
        print(f"Actual: {normalize(current) if current else '∅'} | Sugerencia: {sug_txt} | Progreso: {labeled_now}/{total} (faltan {remaining})")
        raw = input("> ").strip()

        if raw == "?":
            print_help()
            continue
        if raw.lower() == "q":
            break
        if raw.lower() == "b":
            idx = max(0, idx - 1)
            continue
        if raw.lower() == "s":
            df.at[idx, "label_act_es"] = ""
            df.to_csv(path, index=False)
            idx += 1
            continue
        if raw == "":
            if suggestion:
                df.at[idx, "label_act_es"] = suggestion
                df.to_csv(path, index=False)
                idx += 1
                continue
            idx += 1
            continue
        if raw in NUM_TO_LABEL:
            df.at[idx, "label_act_es"] = NUM_TO_LABEL[raw]
            df.to_csv(path, index=False)
            idx += 1
            continue

        # Free-form label (allows copy/paste), but must be valid.
        free = normalize(raw)
        if free in set(ALLOWED):
            df.at[idx, "label_act_es"] = free
            df.to_csv(path, index=False)
            idx += 1
            continue

        print(f"Entrada invalida: '{raw}'. Usa '?' para ayuda.")

    df.to_csv(path, index=False)
    labeled_total = int(df["label_act_es"].fillna("").astype(str).map(is_valid).sum())
    print("")
    print(f"Guardado: {path}")
    print(f"Labeled (valid): {labeled_total}/{total}")


if __name__ == "__main__":
    main()
