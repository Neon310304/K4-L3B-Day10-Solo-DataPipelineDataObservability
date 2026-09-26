import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload


PAYLOAD = {
    "message": {
        "items": [
            {
                "DOI": "10.1234/example",
                "title": ["<i>Example</i> paper"],
                "abstract": "<jats:p>Useful &amp; clean.</jats:p>",
                "author": [{"given": "Ada", "family": "Lovelace"}],
                "type": "journal-article",
                "published": {"date-parts": [[2026, 4]]},
            },
            {"title": ["Missing DOI"]},
        ]
    }
}


class CrossrefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.raw_path = root / "crossref_response.json"
        self.records_path = root / "crossref_records.json"
        self.settings = SimpleNamespace(
            source_query="example",
            source_filter="has-abstract:true",
            max_results=1,
            paths=SimpleNamespace(raw_api_response=self.raw_path, raw_records_json=self.records_path),
        )

    def test_parse_normalizes_fields_and_skips_invalid_items(self):
        records = parse_crossref_payload(PAYLOAD)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].title, "Example paper")
        self.assertEqual(records[0].summary, "Useful & clean.")
        self.assertEqual(records[0].authors, ["Ada Lovelace"])
        self.assertEqual(records[0].categories, ["journal-article"])
        self.assertEqual(records[0].published, "2026-04-01")

    @patch("ingestion.crossref.requests.get")
    def test_success_preserves_exact_response_bytes(self, get):
        raw_bytes = json.dumps(PAYLOAD, separators=(",", ":")).encode("utf-8")
        get.return_value = Mock(status_code=200, content=raw_bytes)

        records = fetch_source_records(self.settings)

        self.assertEqual(self.raw_path.read_bytes(), raw_bytes)
        self.assertEqual(load_raw_records(self.records_path), records)
        self.assertEqual(get.call_args.kwargs["params"]["rows"], 1)

    @patch("ingestion.crossref.time.sleep")
    @patch("ingestion.crossref.requests.get")
    def test_rate_limit_uses_snapshot_without_rewriting_it(self, get, sleep):
        raw_bytes = json.dumps(PAYLOAD).encode("utf-8")
        self.raw_path.write_bytes(raw_bytes)
        get.return_value = Mock(
            status_code=429,
            raise_for_status=Mock(side_effect=requests.HTTPError("rate limited")),
        )

        records = fetch_source_records(self.settings)

        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.raw_path.read_bytes(), raw_bytes)
        self.assertEqual(load_raw_records(self.records_path), records)


if __name__ == "__main__":
    unittest.main()
