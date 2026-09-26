import unittest
from dataclasses import replace
from datetime import datetime, timezone

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord


PAPER = PaperRecord(
    paper_id=" 10.1234/Example ",
    title="  A  <i>useful</i>   paper ",
    summary="<jats:p> A clean   summary &amp; result. </jats:p>",
    authors=[" Ada   Lovelace ", " Alan  Turing "],
    categories=[" Artificial   Intelligence "],
    primary_category="",
    published="2026-04-01",
    updated="invalid",
    abs_url=" https://doi.org/10.1234/Example ",
    pdf_url="",
    comment="",
)


class CleaningTests(unittest.TestCase):
    def test_normalizes_text_dates_and_embedding_context(self):
        df = build_clean_dataframe([PAPER], datetime(2026, 5, 1, 12, tzinfo=timezone.utc))

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["title"], "A useful paper")
        self.assertEqual(row["summary"], "A clean summary & result.")
        self.assertEqual(row["authors_joined"], "Ada Lovelace, Alan Turing")
        self.assertEqual(row["categories_joined"], "Artificial Intelligence")
        self.assertEqual(row["primary_category"], "Artificial Intelligence")
        self.assertEqual(row["updated"], "2026-04-01")
        self.assertEqual(row["age_days"], 30)
        self.assertEqual(row["summary_chars"], len(row["summary"]))
        self.assertEqual(
            row["text_for_embedding"],
            "Title: A useful paper\n"
            "Authors: Ada Lovelace, Alan Turing\n"
            "Published: 2026-04-01\n"
            "Categories: Artificial Intelligence\n"
            "Summary: A clean summary & result.",
        )

    def test_discards_duplicate_doi_and_unusable_records(self):
        duplicate = replace(PAPER, paper_id="10.1234/example", title="Duplicate")
        invalid = replace(PAPER, paper_id="10.1234/invalid", published="not-a-date")
        df = build_clean_dataframe([PAPER, duplicate, invalid], datetime(2026, 5, 1))

        self.assertEqual(df["paper_id"].tolist(), ["10.1234/Example"])
        self.assertEqual(df["title"].tolist(), ["A useful paper"])


if __name__ == "__main__":
    unittest.main()
