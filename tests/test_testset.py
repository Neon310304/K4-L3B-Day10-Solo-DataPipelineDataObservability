import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

from evaluation.testset import build_test_set


class TestSetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.output_path = Path(self.temp.name) / "test_set.json"
        self.df = pd.DataFrame([
            {
                "paper_id": f"10.1234/{index:02d}",
                "title": f"Research Paper {index:02d}",
                "summary": f"Paper {index:02d} studies a useful research topic. It reports more findings.",
                "authors_joined": f"Author {index:02d}",
                "published": "2026-05-20",
                "categories_joined": "Research",
            }
            for index in range(12)
        ])

    def test_builds_balanced_grounded_questions_and_writes_json(self):
        questions = build_test_set(self.df.sample(frac=1, random_state=7), self.output_path)

        self.assertEqual(len(questions), 10)
        self.assertEqual(
            Counter(question["question_type"] for question in questions),
            {"summary": 3, "authors": 3, "date": 2, "categories": 2},
        )
        self.assertEqual([question["id"] for question in questions],
                         [f"eval_{index:03d}" for index in range(1, 11)])
        self.assertEqual(len({question["ground_truth_doc_ids"][0] for question in questions}), 10)
        self.assertEqual(json.loads(self.output_path.read_text(encoding="utf-8")), questions)
        self.assertEqual(build_test_set(self.df, self.output_path), questions)

        papers = self.df.set_index("paper_id")
        for question in questions:
            row = papers.loc[question["ground_truth_doc_ids"][0]]
            self.assertIn(row["title"], question["question"])
            expected = {
                "summary": row["summary"].split(". ")[0] + ".",
                "authors": row["authors_joined"],
                "date": row["published"],
                "categories": row["categories_joined"],
            }
            self.assertEqual(question["ground_truth"], expected[question["question_type"]])

    def test_requires_ten_complete_distinct_papers(self):
        with self.assertRaisesRegex(ValueError, "At least 10 distinct papers"):
            build_test_set(self.df.head(9), self.output_path)
        self.assertFalse(self.output_path.exists())


if __name__ == "__main__":
    unittest.main()
