# Phase 1 Baseline Report

## Source and pipeline

| Field | Value |
| --- | --- |
| Source API | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-02-07,has-abstract:true |
| Raw records | 24 |
| Clean records | 24 |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Collection | papers-baseline |

## Evaluation metrics

| Metric | Value |
| --- | ---: |
| Samples | 6 |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 0.6667 |
| `judge_accuracy` | 0.6667 |
| `mean_judge_score` | 3.6667 |
| `ragas` | {"status": "not_run_for_reference_mode"} |

## Real agent evaluation

| Metric | Value |
| --- | ---: |
| Samples | 6 |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 0.3227 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5 |
| Judge provider/model | openrouter / o4-mini |
| Judge fallbacks | 0 / 6 |
| Ragas | {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "metrics": {"answer_relevancy": 0.6447051652776783, "context_precision": 0.6666666666, "context_recall": 0.6666666666666666, "faithfulness": 0.6962041226747109}, "model": "o4-mini", "provider": "openrouter", "samples": 6, "status": "passed"} |

## Data quality

- Overall status: **PASS**
- Rows checked: **24**
- Failed error checks: **0**
- Warning checks: **1**

| Check | Dimension | Severity | Status | Observed | Expected | Details |
| --- | --- | --- | --- | ---: | --- | --- |
| row_count | volume | error | PASS | 24 | >= 24 rows | - |
| required_columns | schema | error | PASS | [] | all required columns present: ['age_days', 'paper_id', 'published', 'summary', 'text_for_embedding', 'title'] | - |
| paper_id_not_null | completeness | error | PASS | 0 | 0 blank paper_id values | - |
| paper_id_unique | uniqueness | error | PASS | 0 | 0 rows with duplicate paper_id | - |
| title_not_null | completeness | error | PASS | 0 | 0 blank titles | - |
| title_min_length | validity | error | PASS | 0 | 0 titles shorter than 15 characters | - |
| summary_not_null | completeness | error | PASS | 0 | 0 blank summaries | - |
| summary_min_length | validity | error | PASS | 0 | 0 summaries shorter than 100 characters | - |
| summary_noise_markers | validity | error | PASS | 0 | 0 summaries containing known corruption markers | - |
| text_for_embedding_not_null | completeness | error | PASS | 0 | 0 blank text_for_embedding values | - |
| embedding_contains_title | consistency | error | PASS | 0 | 0 embedding texts missing their current title | - |
| embedding_contains_summary | consistency | error | PASS | 0 | 0 embedding texts missing their current non-blank summary | - |
| published_valid | validity | error | PASS | 0 | 0 invalid publication dates | - |
| age_days_valid | validity | error | PASS | 0 | 0 missing or negative age_days values | - |
| freshness_threshold | freshness | error | PASS | 0 | 0 rows older than 180 days | - |
| age_days_consistent_with_published | consistency | error | PASS | 0 | 0 rows where age_days differs from published by more than 1 day | - |
| categories_not_null | completeness | warning | FAIL | 24 | 0 blank categories_joined values | 10.1111/exsy.70341, 10.2118/234689-pa, 10.1007/s10278-026-02086-9, 10.21203/rs.3.rs-10178277/v1, 10.2196/preprints.106157, 10.3390/buildings16132637, 10.21079/11681/50309, 10.63646/kpqm1958, 10.21203/rs.3.rs-10012178/v1, 10.47576/2949-1894.2026.7.7.023 |

## Freshness

| Field | Value |
| --- | --- |
| Status | **FRESH** |
| Latest publication | 2026-08-01 |
| Oldest publication | 2026-02-12 |
| Stale rows | 0 |
| Invalid date rows | 0 |
| Threshold (days) | 180 |
| Maximum age (days) | 175 |

## Baseline conclusion

The baseline has unresolved quality signals: `categories_not_null`.
Evaluation conclusions should be interpreted from the recorded metrics and answer artifacts, not from pipeline exit status alone.
