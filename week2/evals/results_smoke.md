# Week 2 Evaluation — smoke

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
| Answer correctness | 14 | 20 | 70.0% |
| Routing accuracy | 17 | 18 | 94.4% |
| Abstention rate | 2 | 2 | 100.0% |

## Answer correctness by type

| Type | Correct | Total | Rate |
|---|---:|---:|---:|
| policy | 8 | 8 | 100.0% |
| data | 2 | 6 | 33.3% |
| hybrid | 2 | 4 | 50.0% |
| unanswerable | 2 | 2 | 100.0% |

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
| d02 | data | data | data | PASS | N/A | FAIL | N/A |
| d03 | data | data | N/A | FAIL | N/A | FAIL | N/A |
| d04 | data | data | data | PASS | N/A | PASS | N/A |
| d05 | data | data | data | PASS | N/A | FAIL | N/A |
| d06 | data | data | data | PASS | N/A | FAIL | N/A |
| h01 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| h02 | hybrid | hybrid | hybrid | PASS | PASS | FAIL | N/A |
| h03 | hybrid | hybrid | hybrid | PASS | PASS | PASS | N/A |
| h04 | hybrid | hybrid | hybrid | PASS | PASS | FAIL | N/A |
| u01 | unanswerable | N/A | policy | N/A | N/A | PASS | PASS |
| u02 | unanswerable | N/A | policy | N/A | N/A | PASS | PASS |

## Failures / investigation notes

### d02 — data

- Question: How many refunds did we issue over the last 90 days, and what did they total?
- Actual route: data
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: The system answer reports 49 refunds totaling $5,027.99, which contradicts the expected SQL result of 60 refunds totaling INR 6,029.00. The expected answer must match the database result of 60 refunds and the total amount of 6029 (or 6,029.00).
- Errors: None

### d03 — data

- Question: Which week had the highest cancellation rate, and what was it?
- Actual route: None
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: No system answer was produced.
- Errors: ['system_error: ValueError: Only SELECT statements are allowed.']

### d05 — data

- Question: How many rides did drivers cancel in the last 30 days?
- Actual route: data
- Retrieval hit: None
- Expected source rank: None
- Retrieved sources: []
- Answer correct: False
- Judge reason: The system answer states 20 rides were cancelled, but the expected SQL result is 48. The answer does not match the expected fact.
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

### h02 — hybrid

- Question: Our refunds policy says every refund is issued within 7 days of the ride. Is that what actually happens?
- Actual route: hybrid
- Retrieval hit: True
- Expected source rank: 1
- Retrieved sources: ['refunds_and_cancellations.md', 'refunds_and_cancellations.md', 'refunds_and_cancellations.md', 'support_faq.md', 'terms_and_conditions.md']
- Answer correct: False
- Judge reason: The system answer incorrectly claims alignment between policy and data, stating 'This aligns with the policy' and 'the majority of refunds are processed within the specified timeframe'. However, the notes explicitly describe a planted contradiction: policy says no refund issued >7 days, but database shows 7 refunds issued 15-38 days later. A correct answer must surface this disagreement, not claim alignment. The answer fails to meet the requirement to present the contradiction.
- Errors: None

### h04 — hybrid

- Question: What is the cancellation fee, and how much have we collected in no-show fees over the last 90 days?
- Actual route: hybrid
- Retrieval hit: True
- Expected source rank: 3
- Retrieved sources: ['driver_handbook.md', 'support_faq.md', 'refunds_and_cancellations.md', 'refunds_and_cancellations.md', 'terms_and_conditions.md']
- Answer correct: False
- Judge reason: The system answer incorrectly states the total collected in no-show fees as $3,120.00, while the expected SQL result and notes indicate the correct amount should be ₹4,080 (68 no-shows x ₹60). The answer must surface the contradiction between policy-stated fees and actual collected data, but here it silently uses an incorrect figure.
- Errors: None
