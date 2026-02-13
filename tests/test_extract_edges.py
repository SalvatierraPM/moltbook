from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class TestExtractEdges(unittest.TestCase):
    def test_mentions_are_extracted_and_filtered_to_known_handles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            posts_path = tmp / "posts.jsonl"
            comments_path = tmp / "comments.jsonl"
            out_dir = tmp / "out"

            # Alice posts and mentions Bob (known) + UnknownUser (unknown).
            posts = [
                {
                    "id": "p1",
                    "title": "Hola @Bob",
                    "content": "Ping @Bob y @UnknownUser. Mira https://example.com/path?q=1",
                    "created_at": "2026-02-01T00:00:00+00:00",
                    "submolt": {"name": "general"},
                    "author": {"id": "a1", "name": "Alice"},
                }
            ]

            # Bob exists in the dataset (so @Bob should survive filtering).
            comments = [
                {
                    "id": "c1",
                    "post_id": "p1",
                    "parent_id": None,
                    "content": "ok",
                    "created_at": "2026-02-01T00:00:01+00:00",
                    "author_id": "a2",
                    "author": {"id": "a2", "name": "Bob"},
                }
            ]

            write_jsonl(posts_path, posts)
            write_jsonl(comments_path, comments)

            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/extract_edges.py",
                    "--posts",
                    str(posts_path),
                    "--comments",
                    str(comments_path),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            raw_mentions = read_csv_rows(out_dir / "edges_mentions_raw.csv")
            mentions = read_csv_rows(out_dir / "edges_mentions.csv")
            links = read_csv_rows(out_dir / "edges_links.csv")

            raw_targets = {r["target"] for r in raw_mentions}
            filt_targets = {r["target"] for r in mentions}

            self.assertIn("bob", raw_targets)
            self.assertIn("unknownuser", raw_targets)
            self.assertIn("bob", filt_targets)
            self.assertNotIn("unknownuser", filt_targets)

            # URL extraction should capture the domain.
            domains = {r.get("domain") for r in links if r.get("domain")}
            self.assertIn("example.com", domains)

