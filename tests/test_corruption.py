import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from core.config import load_settings
from ingestion.corruption import corrupt_clean_dataframe, repair_from_raw_snapshot


class CorruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.log_path = Path(self.temp.name) / "corruption_log.json"
        self.clean = pd.DataFrame([
            {
                "paper_id": f"10.1234/{index:02d}",
                "title": f"Long Research Title {index:02d}",
                "summary": f"A useful summary for paper {index:02d} with enough detail.",
                "authors_joined": f"Author {index:02d}",
                "categories_joined": "Research",
                "published": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
                "age_days": 200 - index,
                "summary_chars": 60,
                "text_for_embedding": f"Original context {index:02d}",
            }
            for index in range(24)
        ])

    def test_six_faults_are_logged_and_embedding_text_matches_rows(self):
        original = self.clean.copy(deep=True)
        corrupted = corrupt_clean_dataframe(self.clean, self.log_path)
        log = json.loads(self.log_path.read_text(encoding="utf-8"))

        assert_frame_equal(self.clean, original)
        self.assertEqual(len(corrupted), 21)
        self.assertEqual(corrupted.paper_id.nunique(), 19)
        self.assertEqual(log["scenario_counts"], {
            "drop_latest_records": 5,
            "blank_summary": 3,
            "inject_noise": 3,
            "truncate_title": 3,
            "stale_date": 8,
            "duplicate_rows": 2,
        })
        self.assertEqual(len(log["events"]), 24)
        dropped_ids = {
            event["paper_id"] for event in log["events"]
            if event["scenario"] == "drop_latest_records"
        }
        self.assertEqual(dropped_ids, {f"10.1234/{index:02d}" for index in range(19, 24)})
        self.assertEqual(int(corrupted.summary.eq("").sum()), 3)
        self.assertEqual(int(corrupted.summary.str.contains("ZXQ_NOISE_").sum()), 3)
        self.assertEqual(int(corrupted.title.str.len().lt(8).sum()), 3)
        self.assertEqual(corrupted.summary.str.len().tolist(), corrupted.summary_chars.tolist())
        stale_events = [event for event in log["events"] if event["scenario"] == "stale_date"]
        for event in stale_events:
            change = event["changes"]
            self.assertEqual(change["age_days"]["after"] - change["age_days"]["before"], 365)
            before = date.fromisoformat(change["published"]["before"])
            after = date.fromisoformat(change["published"]["after"])
            self.assertEqual((before - after).days, 365)
        for row in corrupted.itertuples():
            self.assertIn(f"Title: {row.title}\n", row.text_for_embedding)
            self.assertIn(f"Published: {row.published}\n", row.text_for_embedding)
            self.assertTrue(row.text_for_embedding.endswith(f"Summary: {row.summary}"))
        for event in log["events"]:
            self.assertIn("paper_id", event)
            self.assertIn("source_position", event)
            self.assertTrue(event["changes"])

        again = corrupt_clean_dataframe(self.clean, self.log_path)
        assert_frame_equal(corrupted, again)

    def test_requires_enough_clean_records(self):
        with self.assertRaisesRegex(ValueError, "At least 10"):
            corrupt_clean_dataframe(self.clean.head(9), self.log_path)
        self.assertFalse(self.log_path.exists())

    def test_repair_rebuilds_from_unchanged_raw_snapshot(self):
        root = Path(self.temp.name)
        raw_path = root / "crossref_response.json"
        raw_bytes = json.dumps({"message": {"items": [{
            "DOI": "10.1234/original",
            "title": ["Original title"],
            "abstract": "<jats:p>Original summary with more than thirty characters.</jats:p>",
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "subject": ["Computer Science"],
            "published": {"date-parts": [[2026, 5, 20]]},
        }]}}).encode("utf-8")
        raw_path.write_bytes(raw_bytes)
        settings = load_settings()
        paths = replace(
            settings.paths,
            raw_api_response=raw_path,
            repaired_clean_csv=root / "repaired.csv",
            repaired_clean_json=root / "repaired.json",
        )
        settings = replace(settings, paths=paths)
        run_date = datetime(2026, 9, 26, tzinfo=timezone.utc)

        first = repair_from_raw_snapshot(settings, run_date)
        second = repair_from_raw_snapshot(settings, run_date)

        assert_frame_equal(first, second)
        self.assertEqual(raw_path.read_bytes(), raw_bytes)
        self.assertEqual(first.paper_id.tolist(), ["10.1234/original"])
        self.assertEqual(first.summary.tolist(), ["Original summary with more than thirty characters."])
        self.assertTrue(paths.repaired_clean_csv.is_file())
        self.assertEqual(len(json.loads(paths.repaired_clean_json.read_text(encoding="utf-8"))), 1)


if __name__ == "__main__":
    unittest.main()
