from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.corruption import corrupt_clean_dataframe, repair_from_raw_snapshot
from observability.quality import run_data_quality_checks
from observability.reporting import format_three_state_table, generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Measure corruption and verify restoration from the preserved API snapshot."""
    required = (
        settings.paths.raw_api_response,
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
        settings.paths.baseline_quality_report,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Phase 1 artifacts are missing; run script/run_phase1.py first: " + ", ".join(missing)
        )

    baseline_df = pd.read_json(settings.paths.clean_json)
    test_set = read_json(settings.paths.eval_testset)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_answers = read_json(settings.paths.baseline_answers)
    baseline_quality = read_json(settings.paths.baseline_quality_report)
    if not baseline_quality["success"]:
        raise RuntimeError("Baseline quality gate did not pass")
    if not test_set or baseline_metrics["samples"] != len(test_set):
        raise ValueError("Baseline metrics and benchmark test set are inconsistent")
    source_ids = set(baseline_df["paper_id"])
    if any(
        doc_id not in source_ids
        for question in test_set
        for doc_id in question["ground_truth_doc_ids"]
    ):
        raise ValueError("Benchmark contains a DOI absent from the baseline clean data")

    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_evaluation = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    write_json(
        settings.paths.quality_dir / "corrupted_freshness_report.json",
        corrupted_quality["freshness"],
    )

    repaired_df = repair_from_raw_snapshot(settings)
    reference_columns = ["paper_id", "title", "summary", "published", "text_for_embedding"]
    pd.testing.assert_frame_equal(
        baseline_df[reference_columns].sort_values("paper_id").reset_index(drop=True),
        repaired_df[reference_columns].sort_values("paper_id").reset_index(drop=True),
        check_dtype=False,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    if not repaired_quality["success"]:
        raise RuntimeError("Repaired data did not pass the quality gate")
    write_json(
        settings.paths.quality_dir / "repaired_freshness_report.json",
        repaired_quality["freshness"],
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, settings.paths.repaired_embeddings_json
    )
    repaired_evaluation = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_quality["freshness"],
        repaired_quality["freshness"],
        baseline_quality=baseline_quality,
        corruption_log=read_json(settings.paths.corruption_log),
        baseline_answers=baseline_answers,
        corrupted_answers=corrupted_evaluation.answers,
        repaired_answers=repaired_evaluation.answers,
        benchmark_sha256=hashlib.sha256(settings.paths.eval_testset.read_bytes()).hexdigest(),
        repair_verified=True,
    )
    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_evaluation.summary,
        "repaired": repaired_evaluation.summary,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "report_path": str(settings.paths.comparison_report),
    }


def main() -> None:
    """Run the Phase 2 experiment and print the three-state comparison."""
    result = run_corruption_flow_pipeline(load_settings())
    print(format_three_state_table(result["baseline"], result["corrupted"], result["repaired"]))
    print(f"Corrupted quality gate: {'PASS' if result['corrupted_quality']['success'] else 'FAIL'}")
    print(f"Repaired quality gate: {'PASS' if result['repaired_quality']['success'] else 'FAIL'}")
    print(f"Report: {result['report_path']}")
