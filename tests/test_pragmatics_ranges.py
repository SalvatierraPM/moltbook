import unittest

import numpy as np

from moltbook_pragmatics.embeddings import TfidfEmbeddingBackend
from moltbook_pragmatics.message_scoring import OfflineBaselineScorer


class TestPragmaticsRanges(unittest.TestCase):
    def test_metrics_are_normalized(self):
        msgs = [
            {"locution": {"cleaned_text": "please help us coordinate"}},
            {"locution": {"cleaned_text": "you are wrong and this is awful"}},
            {"locution": {"cleaned_text": "I promise to do it"}},
        ]
        texts = [m["locution"]["cleaned_text"] for m in msgs]
        emb_backend = TfidfEmbeddingBackend()
        emb_backend.fit(texts)
        emb = emb_backend.encode(texts)

        scorer = OfflineBaselineScorer(emb_backend)
        scorer.prepare()
        scored = scorer.score(msgs, emb)

        for s in scored:
            self.assertGreaterEqual(s["illocution"]["confidence"], 0.0)
            self.assertLessEqual(s["illocution"]["confidence"], 1.0)
            for v in s["pragmatic_scores"].values():
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
            for v in s["pragmatic_confidence"].values():
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)


if __name__ == "__main__":
    unittest.main()
