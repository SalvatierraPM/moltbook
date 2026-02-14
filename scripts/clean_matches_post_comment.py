#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import pandas as pd


def utc_ts() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def load_comments_lookup(comments_dir: Path) -> dict[str, tuple[str, str]]:
    """
    Build a stable doc_id -> (submolt, created_at) lookup.

    Why: comments_meta can contain duplicate doc_id rows (typically from resumed runs).
    When we later do `.set_index("doc_id").loc[doc_id]`, pandas returns a DataFrame and
    its `.get(...)` becomes a Series, which stringifies into multi-line garbage in CSV.
    """

    meta_path = comments_dir / "comments_meta.parquet"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")

    meta = pd.read_parquet(meta_path)

    progress_path = comments_dir / "embeddings_progress.json"
    if progress_path.exists():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            total = int(progress.get("total", 0) or 0)
            if total > 0 and len(meta) > total:
                meta = meta.iloc[:total].reset_index(drop=True)
        except Exception:
            pass

    meta = meta.drop_duplicates(subset=["doc_id"], keep="first")
    meta["doc_id"] = meta["doc_id"].astype(str)
    meta["submolt"] = meta.get("submolt").fillna("").astype(str)
    meta["created_at"] = meta.get("created_at").fillna("").astype(str)

    return dict(zip(meta["doc_id"], zip(meta["submolt"], meta["created_at"])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean matches_post_comment.csv to remove multi-line fields.")
    parser.add_argument("--matches", default="data/derived/embeddings_post_comment/matches_post_comment.csv")
    parser.add_argument("--comments-dir", default="data/derived/embeddings_comments")
    parser.add_argument("--backup-dir", default="output/backups")
    parser.add_argument("--in-place", action="store_true", help="Rewrite the file in place (default).")
    args = parser.parse_args()

    matches_path = Path(args.matches)
    comments_dir = Path(args.comments_dir)
    backup_dir = Path(args.backup_dir)

    if not matches_path.exists():
        raise FileNotFoundError(f"Missing {matches_path}")

    lookup = load_comments_lookup(comments_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{matches_path.name}.bak.{utc_ts()}"

    tmp_path = matches_path.with_suffix(matches_path.suffix + ".tmp")

    csv.field_size_limit(50_000_000)

    total = 0
    fixed = 0
    with matches_path.open("r", encoding="utf-8", newline="") as fin, tmp_path.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)

        header = next(reader)
        writer.writerow(header)

        idx_comment_id = header.index("comment_id")
        idx_comment_submolt = header.index("comment_submolt")
        idx_comment_created = header.index("comment_created_at")

        for row in reader:
            total += 1
            cid = row[idx_comment_id]
            submolt, created_at = lookup.get(cid, ("", ""))

            old_submolt = row[idx_comment_submolt]
            old_created = row[idx_comment_created]
            if ("\n" in old_submolt) or ("\r" in old_submolt) or ("\n" in old_created) or ("\r" in old_created):
                fixed += 1

            if submolt:
                row[idx_comment_submolt] = submolt
            if created_at:
                row[idx_comment_created] = created_at

            writer.writerow(row)

            if total % 200_000 == 0:
                print(f"Cleaned {total} rows (fixed so far: {fixed})", flush=True)

    # Preserve the original for forensic reproducibility.
    matches_path.replace(backup_path)
    tmp_path.replace(matches_path)

    print(f"Done. Rows: {total}. Rows with multiline fields fixed: {fixed}.")
    print(f"Backup: {backup_path}")
    print(f"Output: {matches_path}")


if __name__ == "__main__":
    main()

