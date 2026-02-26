import unittest

import numpy as np

from moltbook_pragmatics.embeddings import TfidfEmbeddingBackend
from moltbook_pragmatics.message_scoring import OfflineBaselineScorer


class TestPragmaticsDeterministic(unittest.TestCase):
    def test_deterministic_scores(self):
        msgs = [
            {"locution": {"cleaned_text": "this is certainly true"}},
            {"locution": {"cleaned_text": "maybe we should discuss"}},
            {"locution": {"cleaned_text": "haha sure genius"}},
        ]
        texts = [m["locution"]["cleaned_text"] for m in msgs]

        b1 = TfidfEmbeddingBackend()
        b1.fit(texts)
        e1 = b1.encode(texts)
        s1 = OfflineBaselineScorer(b1)
        s1.prepare()
        r1 = s1.score(msgs, e1)

        b2 = TfidfEmbeddingBackend()
        b2.fit(texts)
        e2 = b2.encode(texts)
        s2 = OfflineBaselineScorer(b2)
        s2.prepare()
        r2 = s2.score(msgs, e2)

        self.assertEqual(r1[0]["illocution"]["label"], r2[0]["illocution"]["label"])
        self.assertAlmostEqual(r1[1]["pragmatic_scores"]["certainty"], r2[1]["pragmatic_scores"]["certainty"], places=6)
        self.assertAlmostEqual(r1[2]["pragmatic_scores"]["irony"], r2[2]["pragmatic_scores"]["irony"], places=6)


if __name__ == "__main__":
    unittest.main()
