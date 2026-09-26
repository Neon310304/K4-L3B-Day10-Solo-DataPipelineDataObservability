# Phase 1 Baseline Report

Generated (UTC): 2026-09-26 05:21:02

## Source and corpus

| Measure | Value |
| --- | ---: |
| Source | Crossref REST API |
| Source mode | saved raw records |
| Query | agentic retrieval augmented generation large language model |
| Raw records | 24 |
| Clean records | 24 |
| Indexed records | 24 |
| Benchmark questions | 10 |

## Baseline evaluation

| Metric | Value |
| --- | ---: |
| Retrieval Hit Rate | 100.0% |
| Mean Token F1 | 1.000 |
| Judge accuracy | 100.0% |
| Mean judge score (1–5) | 5.00 |

The benchmark names each paper in its question. The baseline QA path prioritizes exact title lookup and extracts answers from indexed metadata; these scores check pipeline wiring and metadata consistency rather than performance on unseen questions.

Judge mode: heuristic fallback.

| Question | Type | Source DOI | Retrieval hit | Token F1 | Judge score |
| --- | --- | --- | ---: | ---: | ---: |
| eval_001 | summary | 10.1007/s10278-026-02086-9 | Yes | 1.000 | 5 |
| eval_002 | authors | 10.20944/preprints202608.1849.v1 | Yes | 1.000 | 5 |
| eval_003 | date | 10.2118/234689-pa | Yes | 1.000 | 5 |
| eval_004 | categories | 10.21203/rs.3.rs-10349437/v1 | Yes | 1.000 | 5 |
| eval_005 | summary | 10.21203/rs.3.rs-10489777/v1 | Yes | 1.000 | 5 |
| eval_006 | authors | 10.3390/buildings16132637 | Yes | 1.000 | 5 |
| eval_007 | date | 10.36887/2415-8453-2026-3-2 | Yes | 1.000 | 5 |
| eval_008 | categories | 10.52060/juptik.v4i1.4318 | Yes | 1.000 | 5 |
| eval_009 | summary | 10.55041/isjem07213 | Yes | 1.000 | 5 |
| eval_010 | authors | 10.70267/aitia.2026482489 | Yes | 1.000 | 5 |

## Data quality gate

Overall: **PASS**

| GX check | Result |
| --- | --- |
| row_count | PASS |
| paper_id_not_null | PASS |
| title_not_null | PASS |
| text_for_embedding_not_null | PASS |
| paper_id_unique | PASS |
| summary_length | PASS |

## Freshness SLA

| Measure | Value |
| --- | ---: |
| Age threshold | 180 days |
| Stale papers | 0 / 24 |
| Stale ratio | 0.0% |
| Maximum allowed ratio | 25.0% |
| Freshness status | PASS |
| Oldest published | 2026-04-01 |
| Latest published | 2026-09-15 |
