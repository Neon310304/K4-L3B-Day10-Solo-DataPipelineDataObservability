from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


QUESTION_TYPES = (
    "summary", "authors", "date", "categories",
    "summary", "authors", "date", "categories",
    "summary", "authors",
)


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build a deterministic, balanced benchmark from ten distinct clean papers."""
    required = {"paper_id", "title", "summary", "authors_joined", "published", "categories_joined"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Clean dataframe is missing benchmark columns: {', '.join(missing)}")

    papers = []
    seen_ids = set()
    seen_titles = set()
    for row in df.to_dict(orient="records"):
        fields = {
            key: normalize_whitespace(value) if isinstance(value, str) else ""
            for key, value in row.items() if key in required
        }
        paper_id = fields["paper_id"]
        title = fields["title"]
        summary = fields["summary"]
        authors = fields["authors_joined"]
        categories = fields["categories_joined"]
        published = pd.to_datetime(row["published"], errors="coerce", utc=True)
        if not all((paper_id, title, summary, authors, categories)) or pd.isna(published):
            continue
        if len(summary) < 30 or paper_id.casefold() in seen_ids or title.casefold() in seen_titles:
            continue
        seen_ids.add(paper_id.casefold())
        seen_titles.add(title.casefold())
        fields["published"] = published.strftime("%Y-%m-%d")
        papers.append(fields)

    papers.sort(key=lambda paper: paper["paper_id"].casefold())
    if len(papers) < len(QUESTION_TYPES):
        raise ValueError("At least 10 distinct papers with complete benchmark fields are required")

    positions = [round(index * (len(papers) - 1) / (len(QUESTION_TYPES) - 1))
                 for index in range(len(QUESTION_TYPES))]
    questions = []
    for index, (question_type, position) in enumerate(zip(QUESTION_TYPES, positions), start=1):
        paper = papers[position]
        title = paper["title"]
        if question_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(paper["summary"])
        elif question_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = paper["authors_joined"]
        elif question_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = paper["published"]
        else:
            question = f"What categories or publication types are recorded for the paper '{title}'?"
            ground_truth = paper["categories_joined"]
        questions.append({
            "id": f"eval_{index:03d}",
            "question_type": question_type,
            "question": question,
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [paper["paper_id"]],
        })

    write_json(Path(output_path), questions)
    return questions
