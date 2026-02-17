from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestSiteIntegrity(unittest.TestCase):
    def test_audit_download_link_points_to_existing_analysis_page(self) -> None:
        html = (ROOT / "site" / "audit.html").read_text(encoding="utf-8")
        self.assertIn('href="analysis.html#downloads"', html)
        self.assertNotIn('href="../analysis#downloads"', html)

    def test_landing_has_visible_runtime_error_message(self) -> None:
        js = (ROOT / "site" / "landing.js").read_text(encoding="utf-8")
        self.assertIn("No se pudieron cargar los datos.", js)


if __name__ == "__main__":
    unittest.main()
