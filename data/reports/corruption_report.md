# Data Corruption and Repair Report

Generated (UTC): 2026-09-26 05:08:42

The same benchmark questions were evaluated against three separate ChromaDB collections. The corrupted collection was indexed for this controlled experiment even though its quality gate failed.
Benchmark SHA-256: `c824d3937769c1df56a417e3d291a8604e1ba7d3f475b73a5196735f12ca1c4f`.
Repair was verified against the baseline DOI, title, summary, publication date, and embedding text.

## Performance comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Questions | 10 | 10 | 10 |
| Retrieval Hit Rate | 100.0% | 60.0% | 100.0% |
| Mean Token F1 | 1.000 | 0.600 | 1.000 |
| Judge accuracy | 100.0% | 60.0% | 100.0% |
| Mean judge score (1–5) | 5.00 | 3.40 | 5.00 |

Retrieval Hit Rate changed by -40.0% after corruption and +40.0% after repair. Mean Token F1 changed by -0.400 and +0.400, respectively.

## Quality and freshness

| Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Quality gate | PASS | FAIL | PASS |
| Indexed rows | 24 | 21 | 24 |
| Stale rows | 0 | 8 | 0 |
| Stale ratio | 0.0% | 38.1% | 0.0% |
| Freshness SLA | PASS | FAIL | PASS |

The quality gate fails when any GX expectation fails or the stale-row ratio exceeds 25%.

## Injected faults

| Fault | Affected rows |
| --- | ---: |
| drop_latest_records | 5 |
| blank_summary | 3 |
| inject_noise | 3 |
| truncate_title | 3 |
| stale_date | 8 |
| duplicate_rows | 2 |

The event log records 24 row-level changes, including the affected DOI and values before and after each change.

## Question-level results

Each cell shows retrieval hit and Token F1 for the fixed source DOI.

| Question | Type | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- | --- |
| eval_001 | summary | hit, 1.000 | hit, 0.000 | hit, 1.000 |
| eval_002 | authors | hit, 1.000 | hit, 1.000 | hit, 1.000 |
| eval_003 | date | hit, 1.000 | hit, 1.000 | hit, 1.000 |
| eval_004 | categories | hit, 1.000 | miss, 1.000 | hit, 1.000 |
| eval_005 | summary | hit, 1.000 | miss, 0.000 | hit, 1.000 |
| eval_006 | authors | hit, 1.000 | hit, 1.000 | hit, 1.000 |
| eval_007 | date | hit, 1.000 | miss, 0.000 | hit, 1.000 |
| eval_008 | categories | hit, 1.000 | hit, 1.000 | hit, 1.000 |
| eval_009 | summary | hit, 1.000 | hit, 1.000 | hit, 1.000 |
| eval_010 | authors | hit, 1.000 | miss, 0.000 | hit, 1.000 |

Source miss hidden by answer overlap: eval_004. The answer text matched the reference even though the required DOI was absent from retrieval, so Token F1 alone would miss this failure.

The benchmark includes exact paper titles. The QA path prioritizes title lookup and extracts answers from indexed metadata, so these metrics measure this lab's pipeline behavior rather than general performance on unseen questions. The judge uses a heuristic fallback when no LLM credential is configured.
