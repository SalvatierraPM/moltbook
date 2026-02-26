import unittest

from moltbook_pragmatics.community_time import build_community_windows


class TestPragmaticsWindowing(unittest.TestCase):
    def test_window_count_and_deltas(self):
        memes = [
            {
                "post_id": "p1",
                "community_id": "c1",
                "window_anchor_timestamp": "2026-01-01T00:00:00+00:00",
                "conflict_index": 0.2,
                "coordination_index": 0.7,
                "rigidity_score": 0.4,
                "dominance_vs_reciprocity": 0.5,
                "identity_vs_task_orientation": 0.3,
                "dominant_inquietud": {"distribution": {"truth": 1.0}},
                "illocution_distribution": {"ASSERTIVE": 1.0},
                "pragmatic_mean": {"certainty": 0.5},
            },
            {
                "post_id": "p2",
                "community_id": "c1",
                "window_anchor_timestamp": "2026-01-10T00:00:00+00:00",
                "conflict_index": 0.8,
                "coordination_index": 0.2,
                "rigidity_score": 0.9,
                "dominance_vs_reciprocity": 0.8,
                "identity_vs_task_orientation": 0.7,
                "dominant_inquietud": {"distribution": {"power": 1.0}},
                "illocution_distribution": {"DIRECTIVE": 1.0},
                "pragmatic_mean": {"certainty": 0.9},
            },
        ]

        windows = build_community_windows(memes, window_days=7, step_days=7)
        self.assertGreaterEqual(len(windows), 2)
        self.assertIn("deltas", windows[0])
        self.assertEqual(windows[0]["deltas"]["delta_mean_conflict_index"], 0.0)


if __name__ == "__main__":
    unittest.main()
