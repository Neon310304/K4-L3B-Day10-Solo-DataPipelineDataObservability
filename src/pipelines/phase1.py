from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the baseline pipeline from preserved Crossref records through reporting."""
    source_refreshed = settings.refresh_source or not settings.paths.raw_records_json.is_file()
    records = (
        fetch_source_records(settings)
        if source_refreshed
        else load_raw_records(settings.paths.raw_records_json)
    )
    df = build_clean_dataframe(records, datetime.now(timezone.utc))
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    quality = run_data_quality_checks(df, settings, "baseline")
    if not quality["success"]:
        raise RuntimeError(f"Baseline quality gate failed: {settings.paths.baseline_quality_report}")

    index = LocalEmbeddingIndex.build(df, settings, settings.paths.embeddings_json)
    paper_ids = set(df["paper_id"])
    if settings.refresh_test_set or source_refreshed or not settings.paths.eval_testset.is_file():
        test_set = build_test_set(df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
        if len(test_set) != 10 or any(
            doc_id not in paper_ids
            for question in test_set
            for doc_id in question.get("ground_truth_doc_ids", [])
        ):
            test_set = build_test_set(df, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    source_summary = {
        "source_api": settings.source_api,
        "source_mode": "fetch or offline fallback" if source_refreshed else "saved raw records",
        "source_query": settings.source_query,
        "raw_records": len(records),
        "clean_records": len(df),
        "indexed_records": index.collection.count(),
        "benchmark_questions": len(test_set),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        quality["freshness"],
        answers=evaluation.answers,
    )
    return {
        "source": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "report_path": str(settings.paths.baseline_report),
    }


def main() -> None:
    """Run Phase 1 with project settings and print the baseline metrics."""
    result = run_phase1_pipeline(load_settings())
    metrics = result["metrics"]
    print(f"Phase 1 complete: {result['source']['clean_records']} clean papers indexed")
    print(f"Retrieval Hit Rate: {metrics['retrieval_hit_rate']:.1%}")
    print(f"Mean Token F1: {metrics['mean_token_f1']:.3f}")
    print(f"Report: {result['report_path']}")
