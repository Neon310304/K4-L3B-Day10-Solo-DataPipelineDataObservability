from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from html import unescape

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize valid papers and prepare one five-part embedding text per DOI."""

    def clean_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(re.sub(r"<[^>]*>", " ", unescape(value)).split())

    run_at = pd.Timestamp(run_date)
    run_at = run_at.tz_localize("UTC") if run_at.tzinfo is None else run_at.tz_convert("UTC")
    rows = []
    seen_ids = set()

    for record in records:
        row = asdict(record)
        row["paper_id"] = clean_text(row["paper_id"])
        row["title"] = clean_text(row["title"])
        row["summary"] = clean_text(row["summary"])
        published = pd.to_datetime(row["published"], errors="coerce", utc=True)
        if not all((row["paper_id"], row["title"], row["summary"])) or pd.isna(published):
            continue
        doi_key = row["paper_id"].casefold()
        if doi_key in seen_ids:
            continue
        seen_ids.add(doi_key)

        row["authors"] = [text for value in row["authors"] if (text := clean_text(value))]
        row["categories"] = [text for value in row["categories"] if (text := clean_text(value))]
        row["primary_category"] = clean_text(row["primary_category"]) or (
            row["categories"][0] if row["categories"] else ""
        )
        for field in ("abs_url", "pdf_url", "comment"):
            row[field] = clean_text(row[field])

        updated = pd.to_datetime(row["updated"], errors="coerce", utc=True)
        row["published"] = published.strftime("%Y-%m-%d")
        row["updated"] = (published if pd.isna(updated) else updated).strftime("%Y-%m-%d")
        row["age_days"] = int((run_at - published).days)
        row["authors_joined"] = ", ".join(row["authors"])
        row["categories_joined"] = ", ".join(row["categories"])
        row["summary_chars"] = len(row["summary"])
        row["text_for_embedding"] = "\n".join(
            (
                f"Title: {row['title']}",
                f"Authors: {row['authors_joined']}",
                f"Published: {row['published']}",
                f"Categories: {row['categories_joined']}",
                f"Summary: {row['summary']}",
            )
        )
        rows.append(row)

    columns = [
        *PaperRecord.__dataclass_fields__,
        "age_days", "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    return pd.DataFrame(rows, columns=columns).sort_values("paper_id").reset_index(drop=True)
