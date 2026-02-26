import unittest

import numpy as np

from moltbook_pragmatics.interaction import build_interactions


class TestPragmaticsInteraction(unittest.TestCase):
    def test_reply_graph_reconstruction(self):
        messages = [
            {
                "message_id": "m1",
                "post_id": "p1",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "reply_to_id": None,
                "pragmatic_scores": {
                    "certainty": 0.7,
                    "affect_valence": 0.5,
                    "dominance": 0.4,
                    "politeness": 0.6,
                    "irony": 0.1,
                    "coordination_intent": 0.5,
                },
                "illocution": {"label": "ASSERTIVE"},
            },
            {
                "message_id": "m2",
                "post_id": "p1",
                "timestamp": "2026-01-01T00:01:00+00:00",
                "reply_to_id": "m1",
                "pragmatic_scores": {
                    "certainty": 0.8,
                    "affect_valence": 0.4,
                    "dominance": 0.7,
                    "politeness": 0.3,
                    "irony": 0.2,
                    "coordination_intent": 0.4,
                },
                "illocution": {"label": "DIRECTIVE"},
            },
        ]
        emb = np.array([[1.0, 0.0], [0.9, 0.1]], dtype=np.float32)

        edges, per_post = build_interactions(messages, emb)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source_message_id"], "m1")
        self.assertEqual(edges[0]["target_message_id"], "m2")
        self.assertFalse(edges[0]["weak_structure"])
        self.assertIn("p1", per_post)


if __name__ == "__main__":
    unittest.main()
