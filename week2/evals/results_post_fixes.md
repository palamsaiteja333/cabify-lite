# Week 2 Evaluation — post_fixes

## Configuration

- Top-K: **5**
- Chunk size: **1200 characters**
- Chunk overlap: **150 characters**
- Embedding model: **amazon.titan-embed-text-v2:0**
- Chat model: **us.amazon.nova-2-lite-v1:0**

## Summary

| Metric | Correct | Total | Rate |
|---|---:|---:|---:|
| Retrieval hit-rate | 12 | 12 | 100.0% |
| Answer correctness | 17 | 20 | 85.0% |
| Routing accuracy | 18 | 18 | 100.0% |
| Abstention rate | 1 | 2 | 50.0% |

## Answer correctness by type

| Type | Correct | Total | Rate |
|---|---:|---:|---:|
| policy | 8 | 8 | 100.0% |
| data | 4 | 6 | 66.7% |
| hybrid | 4 | 4 | 100.0% |
| unanswerable | 1 | 2 | 50.0% |

## Per-question results

| ID | Type | Expected route | Actual route | Route | Retrieval | Answer | Abstain |
|---|---|---|---|---|---|---|---|
| p01 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p02 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p03 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p04 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p05 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p06 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p07 | policy | policy | policy | PASS | PASS | PASS | N/A |
| p08 | policy | policy | policy | PASS | PASS | PASS | N/A |
| d01 | data | data | data | PASS | N/A | PASS | N/A |
| d02 | data | data | data | PASS | N/A | PASS | N/A |
| d03 | data | data | data | PASS | N/A | FAIL | N/A |
| d04 | data | data | data | PASS | N/A | PASS | N/A |
| d05 | data | data | data | PASS | N/A | PASS | N/A |
| d06 | data | data | data | PASS | N/A | FAIL | N/A |
| h01 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| h02 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| h03 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| h04 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| u01 | unanswerable | N/A | policy | N/A | N/A | FAIL | FAIL |
| u02 | unanswerable | N/A | policy | N/A | N/A | PASS | PASS |

## Failures / investigation notes

### d03 — data

- Question: Which week had the highest cancellation rate, and what was it?
- Actual route: data
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: The system answer states the week starting 2026-08-24 with a cancellation rate of approximately 29.59%, but the expected answer requires the value '29.6' (not 29.59%) and references the week of August (not the specific start date format). The expected SQL result '2026-W35' also indicates the week should be identified by ISO week number, not a date range. The answer fails to match the expected precision and format requirements.
- Errors: None

### d06 — data

- Question: Which pickup locality generates the most rides?
- Actual route: data
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: The system answer incorrectly states that Whitefield has a decisive lead with 118 rides, while the notes indicate that Kalyan Nagar (116) and Jayanagar (115) are close behind, making a 2-ride gap insufficient to claim a decisive lead. The answer overstates the margin of difference.
- Errors: None

### u01 — unanswerable

- Question: Can I bring my dog in a Cabify-Lite?
- Actual route: policy
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: System did not clearly abstain on an unsupported question.
- Errors: None
