from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from pathlib import Path

import requests

from core.config import Settings


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"<[^>]*>", " ", unescape(value)).split())


def _date_string(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list):
        try:
            year, *rest = parts[0]
            return date(int(year), int(rest[0]) if rest else 1, int(rest[1]) if len(rest) > 1 else 1).isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
    timestamp = value.get("date-time")
    return timestamp[:10] if isinstance(timestamp, str) else ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Extract valid papers from a Crossref works response."""
    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    items = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain message.items as a list")

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doi = _clean_text(item.get("DOI"))
        titles = item.get("title")
        title = _clean_text(titles[0] if isinstance(titles, list) and titles else titles)
        if not doi or not title:
            continue

        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = _clean_text(author.get("name")) or " ".join(
                    part for part in (_clean_text(author.get("given")), _clean_text(author.get("family"))) if part
                )
                if name:
                    authors.append(name)
        categories = [text for subject in item.get("subject") or [] if (text := _clean_text(subject))]
        if not categories and (publication_type := _clean_text(item.get("type"))):
            categories = [publication_type]
        published = next(
            (value for key in ("published", "published-online", "published-print", "issued", "created")
             if (value := _date_string(item.get(key)))),
            "",
        )
        updated = _date_string(item.get("deposited")) or _date_string(item.get("created")) or published
        abs_url = _clean_text(item.get("URL")) or f"https://doi.org/{doi}"
        links = item.get("link", [])
        pdf_url = next(
            (_clean_text(link.get("URL")) for link in links
             if isinstance(link, dict) and link.get("content-type") == "application/pdf"),
            abs_url,
        ) if isinstance(links, list) else abs_url
        records.append(PaperRecord(
            paper_id=doi,
            title=title,
            summary=_clean_text(item.get("abstract")),
            authors=authors,
            categories=categories,
            primary_category=categories[0] if categories else "",
            published=published,
            updated=updated,
            abs_url=abs_url,
            pdf_url=pdf_url,
            comment=f"Crossref record {doi}",
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref works, preserving the response or using the local snapshot on failure."""
    raw_path = settings.paths.raw_api_response
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    try:
        for attempt in range(3):
            response = requests.get(CROSSREF_WORKS_URL, params=params, timeout=15)
            if response.status_code in RETRYABLE_STATUSES and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            raw_bytes = response.content
            records = parse_crossref_payload(json.loads(raw_bytes))
            if not records:
                raise ValueError("Crossref returned no valid records")
            raw_path.write_bytes(raw_bytes)
            break
    except (requests.RequestException, ValueError):
        if not raw_path.is_file():
            raise
        records = parse_crossref_payload(json.loads(raw_path.read_bytes()))
        if not records:
            raise ValueError(f"No valid records in fallback snapshot: {raw_path}")

    records_path = settings.paths.raw_records_json
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(
        json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the preserved, normalized records without calling Crossref."""
    return [PaperRecord(**record) for record in json.loads(path.read_text(encoding="utf-8"))]
