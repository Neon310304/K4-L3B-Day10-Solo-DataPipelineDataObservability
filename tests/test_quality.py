import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.config import load_settings
from observability.quality import evaluate_freshness_sla, run_data_quality_checks


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        settings = load_settings()
        self.settings = replace(
            settings,
            paths=replace(settings.paths, quality_dir=root, freshness_report=root / "freshness.json"),
        )
        self.df = pd.DataFrame({
            "paper_id": [f"10.1234/{index}" for index in range(5)],
            "title": [f"Paper {index}" for index in range(5)],
            "summary": ["A useful research summary with enough detail."] * 5,
            "text_for_embedding": ["Title: Example\nSummary: A useful research summary."] * 5,
            "age_days": [10] * 5,
            "published": ["2026-09-01"] * 5,
        })

    def test_freshness_boundary_and_missing_age(self):
        fresh = self.df.iloc[:4].copy()
        fresh.loc[fresh.index[0], "age_days"] = 181
        self.assertTrue(evaluate_freshness_sla(fresh, self.settings)["is_fresh"])
        fresh.loc[fresh.index[1], "age_days"] = None
        report = evaluate_freshness_sla(fresh, self.settings)
        self.assertFalse(report["is_fresh"])
        self.assertEqual(report["stale_rows"], 2)

    def test_gx_and_freshness_reject_bad_data(self):
        bad = self.df.copy()
        bad.loc[1, "paper_id"] = bad.loc[0, "paper_id"]
        bad.loc[2, "summary"] = "short"
        bad.loc[3, "title"] = "  "
        bad.loc[:1, "age_days"] = 181

        report = run_data_quality_checks(bad, self.settings, "bad")

        self.assertFalse(report["success"])
        self.assertFalse(report["gx_success"])
        self.assertFalse(report["freshness"]["is_fresh"])
        self.assertEqual(report["empty_values"]["title"], 1)
        failed = {check["name"] for check in report["checks"] if not check["success"]}
        self.assertEqual(failed, {"paper_id_unique", "summary_length"})
        self.assertTrue((self.settings.paths.quality_dir / "bad_quality_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
