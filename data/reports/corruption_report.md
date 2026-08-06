# Corruption and Repair Comparison

## Evaluation comparison

| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repair delta | Recovery |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 1.0000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 1.0000 | 1.0000 |
| `judge_accuracy` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 1.0000 | 1.0000 |
| `mean_judge_score` | 5.0000 | 1.0000 | 5.0000 | -4.0000 | 4.0000 | 1.0000 |

## Quality and freshness signals

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Quality status | **PASS** | **FAIL** | **PASS** |
| Failed checks | 0 | 6 | 0 |
| Warning checks | 1 | 1 | 1 |
| Freshness status | **FRESH** | **STALE** | **FRESH** |
| Stale rows | 0 | 3 | 0 |
| Invalid date rows | 0 | 0 | 0 |

### Failed or warning checks

- Corrupted: `paper_id_unique`, `title_min_length`, `summary_not_null`, `summary_min_length`, `summary_noise_markers`, `freshness_threshold`, `categories_not_null`
- Repaired: `categories_not_null`

## Evidence-based conclusion

Corruption reduced the following recorded metrics: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.
Repair improved the following metrics relative to the corrupted state: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.
The repaired dataset passes the supplied quality and freshness checks.
