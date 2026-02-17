from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.ingest.api import fetch_post_comments


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _DummyClient:
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self._idx = 0

    def get(self, path: str, params=None):  # noqa: ANN001
        payload = self._payloads[self._idx]
        self._idx += 1
        return _DummyResponse(payload)


class TestFetchPostComments(unittest.TestCase):
    def test_missing_post_id_is_backfilled_from_context(self) -> None:
        client = _DummyClient(
            [
                {"data": [{"id": "c1", "content": "hola"}, {"id": "c2", "post_id": "p1"}]},
                {"data": []},
            ]
        )

        rows = list(fetch_post_comments(client, "p1", max_pages=5, page_size=2))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].get("post_id"), "p1")
        self.assertEqual(rows[1].get("post_id"), "p1")


if __name__ == "__main__":
    unittest.main()
