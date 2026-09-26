from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> None:
    """Write a reviewable baseline report with source, metrics, and gate results."""
    lines = [
        "# Phase 1 Baseline Report",
        "",
        f"Generated (UTC): {now_utc().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Source and corpus",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Source | {source_summary['source_api']} |",
        f"| Source mode | {source_summary.get('source_mode', 'unspecified')} |",
        f"| Query | {source_summary['source_query']} |",
        f"| Raw records | {source_summary['raw_records']} |",
        f"| Clean records | {source_summary['clean_records']} |",
        f"| Indexed records | {source_summary['indexed_records']} |",
        f"| Benchmark questions | {source_summary['benchmark_questions']} |",
        "",
        "## Baseline evaluation",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Retrieval Hit Rate | {metrics['retrieval_hit_rate']:.1%} |",
        f"| Mean Token F1 | {metrics['mean_token_f1']:.3f} |",
        f"| Judge accuracy | {metrics['judge_accuracy']:.1%} |",
        f"| Mean judge score (1–5) | {metrics['mean_judge_score']:.2f} |",
        "",
        "The benchmark names each paper in its question. The baseline QA path prioritizes exact title lookup "
        "and extracts answers from indexed metadata; these scores check pipeline wiring and metadata consistency "
        "rather than performance on unseen questions.",
    ]
    if answers:
        heuristic = any(
            "Fallback heuristic judge" in item.get("judge", {}).get("reasoning", "")
            for item in answers
        )
        lines.extend([
            "",
            f"Judge mode: {'heuristic fallback' if heuristic else 'configured LLM'}.",
            "",
            "| Question | Type | Source DOI | Retrieval hit | Token F1 | Judge score |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ])
        for item in answers:
            source_ids = ", ".join(item["ground_truth_doc_ids"])
            lines.append(
                f"| {item['id']} | {item['question_type']} | {source_ids} | "
                f"{'Yes' if item['retrieval_hit'] else 'No'} | {item['token_f1']:.3f} | "
                f"{item['judge']['score']} |"
            )

    lines.extend([
        "",
        "## Data quality gate",
        "",
        f"Overall: **{'PASS' if quality['success'] else 'FAIL'}**",
        "",
        "| GX check | Result |",
        "| --- | --- |",
    ])
    for check in quality["checks"]:
        lines.append(f"| {check['name']} | {'PASS' if check['success'] else 'FAIL'} |")
    lines.extend([
        "",
        "## Freshness SLA",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Age threshold | {freshness['threshold_days']} days |",
        f"| Stale papers | {freshness['stale_rows']} / {freshness['total_rows']} |",
        f"| Stale ratio | {freshness['stale_ratio']:.1%} |",
        f"| Maximum allowed ratio | {freshness['max_stale_ratio']:.1%} |",
        f"| Freshness status | {'PASS' if freshness['is_fresh'] else 'FAIL'} |",
        f"| Oldest published | {freshness['oldest_published'] or 'N/A'} |",
        f"| Latest published | {freshness['latest_published'] or 'N/A'} |",
        "",
    ])
    write_text(report_path, "\n".join(lines))


def format_three_state_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> str:
    """Format the same measured metrics for console and Markdown reports."""
    return "\n".join([
        "| Metric | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
        f"| Questions | {baseline_metrics['samples']} | {corrupted_metrics['samples']} | {repaired_metrics['samples']} |",
        f"| Retrieval Hit Rate | {baseline_metrics['retrieval_hit_rate']:.1%} | "
        f"{corrupted_metrics['retrieval_hit_rate']:.1%} | {repaired_metrics['retrieval_hit_rate']:.1%} |",
        f"| Mean Token F1 | {baseline_metrics['mean_token_f1']:.3f} | "
        f"{corrupted_metrics['mean_token_f1']:.3f} | {repaired_metrics['mean_token_f1']:.3f} |",
        f"| Judge accuracy | {baseline_metrics['judge_accuracy']:.1%} | "
        f"{corrupted_metrics['judge_accuracy']:.1%} | {repaired_metrics['judge_accuracy']:.1%} |",
        f"| Mean judge score (1–5) | {baseline_metrics['mean_judge_score']:.2f} | "
        f"{corrupted_metrics['mean_judge_score']:.2f} | {repaired_metrics['mean_judge_score']:.2f} |",
    ])


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    baseline_answers: list[dict[str, Any]] | None = None,
    corrupted_answers: list[dict[str, Any]] | None = None,
    repaired_answers: list[dict[str, Any]] | None = None,
    benchmark_sha256: str | None = None,
    repair_verified: bool = False,
) -> None:
    """Write measured baseline, corrupted, and repaired results side by side."""
    lines = [
        "# Data Corruption and Repair Report",
        "",
        f"Generated (UTC): {now_utc().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "The same benchmark questions were evaluated against three separate ChromaDB collections. "
        "The corrupted collection was indexed for this controlled experiment even though its quality gate failed.",
        f"Benchmark SHA-256: `{benchmark_sha256}`." if benchmark_sha256 else "",
        "Repair was verified against the baseline DOI, title, summary, publication date, and embedding text."
        if repair_verified else "",
        "",
        "## Performance comparison",
        "",
        *format_three_state_table(baseline_metrics, corrupted_metrics, repaired_metrics).splitlines(),
        "",
        f"Retrieval Hit Rate changed by "
        f"{(corrupted_metrics['retrieval_hit_rate'] - baseline_metrics['retrieval_hit_rate']):+.1%} "
        "after corruption and "
        f"{(repaired_metrics['retrieval_hit_rate'] - corrupted_metrics['retrieval_hit_rate']):+.1%} "
        "after repair. Mean Token F1 changed by "
        f"{(corrupted_metrics['mean_token_f1'] - baseline_metrics['mean_token_f1']):+.3f} "
        "and "
        f"{(repaired_metrics['mean_token_f1'] - corrupted_metrics['mean_token_f1']):+.3f}, respectively.",
        "",
        "## Quality and freshness",
        "",
        "| Signal | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
        f"| Quality gate | {'PASS' if baseline_quality and baseline_quality['success'] else 'N/A'} | "
        f"{'PASS' if corrupted_quality['success'] else 'FAIL'} | "
        f"{'PASS' if repaired_quality['success'] else 'FAIL'} |",
        f"| Indexed rows | {baseline_quality['row_count'] if baseline_quality else 'N/A'} | "
        f"{corrupted_quality['row_count']} | {repaired_quality['row_count']} |",
        f"| Stale rows | {baseline_quality['freshness']['stale_rows'] if baseline_quality else 'N/A'} | "
        f"{corrupted_freshness['stale_rows']} | {repaired_freshness['stale_rows']} |",
        f"| Stale ratio | {baseline_quality['freshness']['stale_ratio']:.1%} | "
        f"{corrupted_freshness['stale_ratio']:.1%} | {repaired_freshness['stale_ratio']:.1%} |"
        if baseline_quality else
        f"| Stale ratio | N/A | {corrupted_freshness['stale_ratio']:.1%} | "
        f"{repaired_freshness['stale_ratio']:.1%} |",
        f"| Freshness SLA | {'PASS' if baseline_quality and baseline_quality['freshness']['is_fresh'] else 'N/A'} | "
        f"{'PASS' if corrupted_freshness['is_fresh'] else 'FAIL'} | "
        f"{'PASS' if repaired_freshness['is_fresh'] else 'FAIL'} |",
        "",
        "The quality gate fails when any GX expectation fails or the stale-row ratio exceeds 25%.",
    ]

    if corruption_log:
        lines.extend([
            "",
            "## Injected faults",
            "",
            "| Fault | Affected rows |",
            "| --- | ---: |",
        ])
        for scenario, count in corruption_log["scenario_counts"].items():
            lines.append(f"| {scenario} | {count} |")
        lines.extend([
            "",
            f"The event log records {len(corruption_log['events'])} row-level changes, "
            "including the affected DOI and values before and after each change.",
        ])

    if baseline_answers and corrupted_answers and repaired_answers:
        corrupted_by_id = {item["id"]: item for item in corrupted_answers}
        repaired_by_id = {item["id"]: item for item in repaired_answers}
        lines.extend([
            "",
            "## Question-level results",
            "",
            "Each cell shows retrieval hit and Token F1 for the fixed source DOI.",
            "",
            "| Question | Type | Baseline | Corrupted | Repaired |",
            "| --- | --- | --- | --- | --- |",
        ])
        for baseline in baseline_answers:
            corrupted = corrupted_by_id[baseline["id"]]
            repaired = repaired_by_id[baseline["id"]]
            cells = [
                f"{'hit' if item['retrieval_hit'] else 'miss'}, {item['token_f1']:.3f}"
                for item in (baseline, corrupted, repaired)
            ]
            lines.append(
                f"| {baseline['id']} | {baseline['question_type']} | "
                f"{cells[0]} | {cells[1]} | {cells[2]} |"
            )
        misleading = [
            item["id"] for item in corrupted_answers
            if not item["retrieval_hit"] and item["token_f1"] >= 0.95
        ]
        if misleading:
            lines.extend([
                "",
                "Source miss hidden by answer overlap: " + ", ".join(misleading) + ". "
                "The answer text matched the reference even though the required DOI was absent "
                "from retrieval, so Token F1 alone would miss this failure.",
            ])

    lines.extend([
        "",
        "The benchmark includes exact paper titles. The QA path prioritizes title lookup and extracts "
        "answers from indexed metadata, so these metrics measure this lab's pipeline behavior rather "
        "than general performance on unseen questions. The judge uses a heuristic fallback when no "
        "LLM credential is configured.",
        "",
    ])
    write_text(report_path, "\n".join(lines))
