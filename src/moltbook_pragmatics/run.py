from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .community_time import build_community_windows
from .diagnostics import build_diagnostics_report
from .embeddings import create_embedding_backend
from .evaluation import (
    eval_report_to_dict,
    evaluate_human_labels,
    stratified_labeling_sample,
    write_labeling_sheet,
)
from .interaction import build_interactions
from .io import load_canonical_messages, write_json, write_jsonl
from .meme import aggregate_memes
from .message_scoring import select_scorer
from .normalize import enrich_locution


def _emit_progress(output_dir: Path, stage: str, detail: str, done: int | None = None, total: int | None = None) -> None:
    payload = {"stage": stage, "detail": detail, "done": done, "total": total}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "progress.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if done is not None and total is not None and total > 0:
        pct = (done / total) * 100.0
        print(f"[progress] {stage}: {detail} ({done}/{total}, {pct:.2f}%)", flush=True)
    else:
        print(f"[progress] {stage}: {detail}", flush=True)


def _pipeline(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    _emit_progress(out, "load", "loading canonical messages")
    messages, summary = load_canonical_messages(args.input, args.posts, args.comments)
    _emit_progress(out, "load", "messages loaded", done=len(messages), total=len(messages))

    _emit_progress(out, "normalize", "enriching locution")
    enriched = [enrich_locution(m) for m in messages]
    _emit_progress(out, "normalize", "locution enriched", done=len(enriched), total=len(enriched))

    texts = [m["locution"]["cleaned_text"] for m in enriched]
    emb_backend = create_embedding_backend(args.embedding_backend)
    _emit_progress(out, "embeddings", f"fitting backend={args.embedding_backend}", done=0, total=len(texts))
    emb_backend.fit(texts)
    emb = emb_backend.encode(texts)
    _emit_progress(out, "embeddings", "encoded message vectors", done=len(texts), total=len(texts))

    scorer = select_scorer(args.scoring_backend, emb_backend, seed=args.seed)
    if hasattr(scorer, "prepare"):
        scorer.prepare()
    _emit_progress(out, "scoring", f"scoring backend={args.scoring_backend}", done=0, total=len(enriched))
    scored = scorer.score(enriched, emb)

    for i, add in enumerate(scored):
        enriched[i].update(add)
        if args.store_embeddings:
            enriched[i]["embedding"] = emb[i].tolist()
        else:
            enriched[i]["embedding_id"] = f"emb_{i}"
    _emit_progress(out, "scoring", "message scoring done", done=len(enriched), total=len(enriched))

    _emit_progress(out, "interaction", "building reply/adjacency edges")
    edges, by_post_edges = build_interactions(enriched, emb)
    _emit_progress(out, "interaction", "interaction metrics done", done=len(edges), total=len(edges))

    _emit_progress(out, "meme", "aggregating post-level metrics")
    memes = aggregate_memes(enriched, by_post_edges, emb, emb_backend)
    _emit_progress(out, "meme", "post aggregation done", done=len(memes), total=len(memes))

    _emit_progress(out, "community_time", "building temporal windows")
    windows = build_community_windows(memes, window_days=args.window_days, step_days=args.step_days)
    _emit_progress(out, "community_time", "community windows done", done=len(windows), total=len(windows))
    report = build_diagnostics_report(windows, memes)
    report["schema_summary"] = summary.__dict__
    report["run_config"] = {
        "window_days": args.window_days,
        "step_days": args.step_days,
        "embedding_backend": args.embedding_backend,
        "scoring_backend": args.scoring_backend,
        "seed": args.seed,
    }

    out.mkdir(parents=True, exist_ok=True)

    write_jsonl(out / "enriched_messages.jsonl", enriched)
    write_jsonl(out / "interactions.jsonl", edges)
    write_jsonl(out / "enriched_memes.jsonl", memes)
    write_jsonl(out / "community_windows.jsonl", windows)
    write_json(out / "diagnostics_report.json", report)
    _emit_progress(out, "done", "all outputs written")


def _sample(args: argparse.Namespace) -> None:
    messages, _ = load_canonical_messages(args.input, args.posts, args.comments)
    enriched = [enrich_locution(m) for m in messages]
    texts = [m["locution"]["cleaned_text"] for m in enriched]

    emb_backend = create_embedding_backend(args.embedding_backend)
    emb_backend.fit(texts)
    emb = emb_backend.encode(texts)

    scorer = select_scorer("offline_baseline", emb_backend, seed=args.seed)
    scorer.prepare()
    scored = scorer.score(enriched, emb)
    for i, add in enumerate(scored):
        enriched[i].update(add)

    sample = stratified_labeling_sample(enriched, emb, n=args.sample_size, seed=args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_labeling_sheet(sample, str(out / "labeling_sample.csv"), str(out / "labeling_sample.json"))


def _evaluate(args: argparse.Namespace) -> None:
    report = evaluate_human_labels(args.labeling_csv)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "evaluation_report.json", eval_report_to_dict(report))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Moltbook pragmatic + ontological diagnostics")
    sub = p.add_subparsers(dest="command", required=False)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--input", type=str, default=None, help="Single mixed jsonl input")
        sp.add_argument("--posts", type=str, default=None, help="Posts jsonl")
        sp.add_argument("--comments", type=str, default=None, help="Comments jsonl")
        sp.add_argument("--output_dir", type=str, required=True)
        sp.add_argument("--embedding_backend", type=str, default="sentence_transformers")
        sp.add_argument("--seed", type=int, default=42)

    run_p = sub.add_parser("run", help="Run full enrichment + diagnostics")
    add_common(run_p)
    run_p.add_argument("--window_days", type=int, default=30)
    run_p.add_argument("--step_days", type=int, default=7)
    run_p.add_argument("--scoring_backend", type=str, default="offline_baseline")
    run_p.add_argument("--store_embeddings", action="store_true")

    sample_p = sub.add_parser("sample", help="Build stratified human labeling sample")
    add_common(sample_p)
    sample_p.add_argument("--sample_size", type=int, default=300)

    eval_p = sub.add_parser("evaluate", help="Evaluate human labels against predictions")
    eval_p.add_argument("--labeling_csv", type=str, required=True)
    eval_p.add_argument("--output_dir", type=str, required=True)

    return p


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default command: run (for compatibility with requested usage)
    if not args.command:
        argv = ["run"] + (argv or [])
        args = parser.parse_args(argv)

    if args.command == "run":
        _pipeline(args)
    elif args.command == "sample":
        _sample(args)
    elif args.command == "evaluate":
        _evaluate(args)
    else:
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
