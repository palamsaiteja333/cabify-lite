# Cabify-Lite — Evaluation History

## Objective

Measure answer correctness, retrieval relevance, routing accuracy,
and abstention across the fixed 20-question evaluation dataset.

The dataset contains 8 policy, 6 data, 4 hybrid,
and 2 unanswerable questions.

## Run comparison

| Metric | Initial | Post-fixes | Unified Docker |
|---|---|---|---|
| Answer correctness | 14/20 (70.0%) | 17/20 (85.0%) | 17/20 (85.0%) |
| Retrieval hit rate | 12/12 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| Routing accuracy | 17/18 (94.4%) | 18/18 (100.0%) | 18/18 (100.0%) |
| Abstention | 2/2 (100.0%) | 1/2 (50.0%) | 1/2 (50.0%) |
| Questions with errors | 1 | 0 | 0 |

## Individual runs

### Run 1 — Initial baseline

- Run date (UTC): 2026-10-23T21:08:34.274968+00:00
- Questions evaluated: 20
- Top-K: 5
- Answer correctness: 14/20 (70.0%)
- Failed question IDs: d02, d03, d05, d06, h02, h04
- JSON: [Results](../week2/evals/results_smoke.json)
- Markdown: [Report](../week2/evals/results_smoke.md)

### Run 2 — Post-fixes

- Run date (UTC): 2026-10-28T19:13:40.248802+00:00
- Questions evaluated: 20
- Top-K: 5
- Answer correctness: 17/20 (85.0%)
- Failed question IDs: d03, d06, u01
- JSON: [Results](../week2/evals/results_post_fixes.json)
- Markdown: [Report](../week2/evals/results_post_fixes.md)

### Run 3 — Unified Docker

- Run date (UTC): 2026-11-18T23:39:28.692461+00:00
- Questions evaluated: 20
- Top-K: 5
- Answer correctness: 17/20 (85.0%)
- Failed question IDs: d03, d06, u01
- JSON: [Results](../week2/evals/results_unified_compose_full1.json)
- Markdown: [Report](../week2/evals/results_unified_compose_full1.md)

## Key findings

- Answer correctness improved from 70% to 85% after fixes.
- The unified Docker deployment retained the 85% baseline.
- Retrieval reached 12/12 in all three runs.
- Routing improved from 17/18 to 18/18.
- Abstention remains an open issue at 1/2 in the latest run.

## Evaluation methodology

- The question dataset is stored in `week2/evals/questions.yaml`.
- Responses are graded for semantic correctness using an LLM judge.
- Retrieval accuracy measures whether the expected source appears in Top-K.
- Routing accuracy compares predicted routes against expected routes.
- Unsupported questions are checked for explicit abstention.
- Unified application answers are obtained through the deployed `/ask` API.
- The unified evaluator also performs its own retrieval and judging calls.

## Limitations

LLM-generated answers and LLM-based judgments may vary between runs.
The results are regression evidence, not a production SLA or
a substitute for human evaluation and adversarial security testing.

## Reproduction

From the repository root, after configuring dependencies, AWS
credentials, PostgreSQL and Docker Compose:

```bash
python week2/evals/run_evals_unified.py \
  --top-k 5 \
  --label new_unique_run
```

Use a new label for each execution to preserve prior results.
