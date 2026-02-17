from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moltbook_analysis.analyze.language_ontology import speech_act_features


class TestLanguageOntologyAcceptance(unittest.TestCase):
    def test_spanish_si_with_whitespace_counts_as_acceptance(self) -> None:
        feats = speech_act_features("si, totalmente de acuerdo.")
        self.assertGreaterEqual(int(feats.get("act_acceptance", 0)), 1)

    def test_conditional_si_does_not_count_as_acceptance(self) -> None:
        feats = speech_act_features("si no llegas, avisame por favor")
        self.assertEqual(int(feats.get("act_acceptance", 0)), 0)


if __name__ == "__main__":
    unittest.main()
