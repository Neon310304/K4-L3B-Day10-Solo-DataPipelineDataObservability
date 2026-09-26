from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Flag data when more than a quarter of records are stale or lack an age."""
    total_rows = len(df)
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df else pd.Series(dtype=float)
    stale_rows = int((ages.isna() | ages.gt(settings.freshness_threshold_days)).sum())
    if "age_days" not in df:
        stale_rows = total_rows
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "is_fresh": bool(total_rows and stale_ratio <= 0.25),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the clean data with GX 1.x and enforce the freshness SLA."""
    required_columns = {"paper_id", "title", "text_for_embedding", "summary"}
    missing_columns = sorted(required_columns.difference(df.columns))
    checks: list[dict[str, Any]] = []

    if not missing_columns:
        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name="papers_source")
        data_asset = data_source.add_dataframe_asset(name="papers_asset")
        batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
        batch = batch_def.get_batch(batch_parameters={"dataframe": df})

        expectations = [
            ("row_count", gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)),
            *(
                (f"{column}_not_null", gx.expectations.ExpectColumnValuesToNotBeNull(column=column))
                for column in ("paper_id", "title", "text_for_embedding")
            ),
            ("paper_id_unique", gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")),
            ("summary_length", gx.expectations.ExpectColumnValueLengthsToBeBetween(
                column="summary", min_value=30
            )),
        ]
        for name, expectation in expectations:
            result = batch.validate(expectation)
            checks.append({"name": name, "success": bool(result.success)})

    empty_values = {
        column: int(df[column].map(lambda value: isinstance(value, str) and not value.strip()).sum())
        for column in ("paper_id", "title", "text_for_embedding")
        if column in df
    }
    freshness = evaluate_freshness_sla(df, settings)
    freshness_report = build_freshness_report(
        df, settings, settings.paths.freshness_report, freshness=freshness
    )
    gx_success = not missing_columns and all(check["success"] for check in checks)
    report = {
        "stage": report_name,
        "success": bool(gx_success and not any(empty_values.values()) and freshness["is_fresh"]),
        "gx_success": bool(gx_success),
        "row_count": len(df),
        "checks": checks,
        "missing_columns": missing_columns,
        "empty_values": empty_values,
        "freshness": freshness_report,
    }
    write_json(settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json", report)
    return report


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path: Path,
    freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist freshness counts and the oldest/newest publication dates."""
    report = dict(freshness if freshness is not None else evaluate_freshness_sla(df, settings))
    dates = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna() if "published" in df else []
    report["latest_published"] = dates.max().strftime("%Y-%m-%d") if len(dates) else None
    report["oldest_published"] = dates.min().strftime("%Y-%m-%d") if len(dates) else None
    write_json(report_path, report)
    return report
