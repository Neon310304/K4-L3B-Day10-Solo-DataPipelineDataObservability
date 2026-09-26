from __future__ import annotations

import json
from datetime import datetime, timezone
from math import ceil
from pathlib import Path

import pandas as pd

from core.config import Settings
from core.utils import write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import parse_crossref_payload


SCENARIOS = (
    "drop_latest_records",
    "blank_summary",
    "inject_noise",
    "truncate_title",
    "stale_date",
    "duplicate_rows",
)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Apply six reproducible faults and log every affected source row."""
    required = {
        "paper_id", "title", "summary", "published", "age_days",
        "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Clean dataframe is missing corruption columns: {', '.join(missing)}")
    if len(df) < 10:
        raise ValueError("At least 10 clean records are required to run all six corruption scenarios")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    corrupted["_source_position"] = range(len(corrupted))
    events: list[dict] = []
    counts = dict.fromkeys(SCENARIOS, 0)

    def log_change(scenario: str, row: pd.Series, changes: dict) -> None:
        events.append({
            "scenario": scenario,
            "paper_id": str(row["paper_id"]),
            "source_position": int(row["_source_position"]),
            "changes": changes,
        })
        counts[scenario] += 1

    def public_row(row: pd.Series) -> dict:
        return json.loads(row.drop(labels="_source_position").to_json())

    published = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    if published.isna().any():
        raise ValueError("All clean records need valid published dates before corruption")
    latest = corrupted.assign(_published_at=published).sort_values(
        ["_published_at", "paper_id"], ascending=[False, True], kind="stable"
    )
    drop_count = ceil(len(corrupted) * 0.20)
    dropped_positions = latest.index[:drop_count]
    for position in dropped_positions:
        row = corrupted.loc[position]
        before = public_row(row)
        log_change("drop_latest_records", row, {"row": {"before": before, "after": None}})
    corrupted = corrupted.drop(index=dropped_positions).reset_index(drop=True)

    ordered = corrupted.sort_values("paper_id", kind="stable").index.tolist()
    remaining = len(ordered)
    sizes = {
        "blank_summary": max(1, ceil(remaining * 0.15)),
        "inject_noise": max(1, ceil(remaining * 0.15)),
        "truncate_title": max(1, ceil(remaining * 0.15)),
        "stale_date": max(1, ceil(remaining * 0.40)),
        "duplicate_rows": max(1, ceil(remaining * 0.10)),
    }
    offset = 0

    def select(scenario: str) -> list[int]:
        nonlocal offset
        positions = [ordered[(offset + index) % remaining] for index in range(sizes[scenario])]
        offset += sizes[scenario]
        return positions

    for position in select("blank_summary"):
        row = corrupted.loc[position].copy()
        before = str(row["summary"])
        corrupted.at[position, "summary"] = ""
        log_change("blank_summary", row, {"summary": {"before": before, "after": ""}})

    for position in select("inject_noise"):
        row = corrupted.loc[position].copy()
        before = str(row["summary"])
        marker = f"ZXQ_NOISE_{int(row['_source_position']):03d} "
        after = marker * 12 + before
        corrupted.at[position, "summary"] = after
        log_change("inject_noise", row, {
            "summary": {"before": before, "after": after},
            "noise_token": marker.strip(),
        })

    for position in select("truncate_title"):
        row = corrupted.loc[position].copy()
        before = str(row["title"])
        after = before[:7].rstrip()
        corrupted.at[position, "title"] = after
        log_change("truncate_title", row, {"title": {"before": before, "after": after}})

    for position in select("stale_date"):
        row = corrupted.loc[position].copy()
        before = str(row["published"])
        after = (pd.Timestamp(before) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        old_age = int(row["age_days"])
        corrupted.at[position, "published"] = after
        corrupted.at[position, "age_days"] = old_age + 365
        log_change("stale_date", row, {
            "published": {"before": before, "after": after},
            "age_days": {"before": old_age, "after": old_age + 365},
        })

    duplicates = []
    for position in select("duplicate_rows"):
        row = corrupted.loc[position].copy()
        duplicates.append(row.to_dict())
        after = public_row(row)
        log_change("duplicate_rows", row, {"row": {"before": None, "after": after}})
    if duplicates:
        corrupted = pd.concat([corrupted, pd.DataFrame(duplicates)], ignore_index=True)

    corrupted["summary_chars"] = corrupted["summary"].map(lambda value: len(str(value)))
    corrupted["text_for_embedding"] = corrupted.apply(
        lambda row: "\n".join((
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        )),
        axis=1,
    )
    for event in events:
        if event["scenario"] == "drop_latest_records":
            continue
        source_position = event["source_position"]
        after_row = corrupted.loc[corrupted["_source_position"] == source_position].iloc[0]
        if event["scenario"] == "duplicate_rows":
            event["changes"]["row"]["after"] = public_row(after_row)
            continue
        before_row = df.iloc[source_position]
        for field in ("summary_chars", "text_for_embedding"):
            before = before_row[field]
            after = after_row[field]
            if before != after:
                event["changes"][field] = {
                    "before": int(before) if field == "summary_chars" else str(before),
                    "after": int(after) if field == "summary_chars" else str(after),
                }
    corrupted = corrupted.drop(columns="_source_position")

    write_json(Path(output_log_path), {
        "input_rows": len(df),
        "output_rows": len(corrupted),
        "scenario_counts": counts,
        "events": events,
    })
    return corrupted


def repair_from_raw_snapshot(
    settings: Settings, run_date: datetime | None = None
) -> pd.DataFrame:
    """Rebuild trusted clean data from the preserved Crossref API response."""
    snapshot_path = settings.paths.raw_api_response
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Crossref raw snapshot is missing: {snapshot_path}")
    payload = json.loads(snapshot_path.read_bytes())
    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError(f"No valid papers in Crossref raw snapshot: {snapshot_path}")
    repaired = build_clean_dataframe(records, run_date or datetime.now(timezone.utc))
    if repaired.empty:
        raise ValueError(f"No clean papers could be restored from: {snapshot_path}")
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict(orient="records"))
    return repaired
