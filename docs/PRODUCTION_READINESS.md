# Cabify-Lite — Production Readiness

## Status

**Production-style engineering demonstration.**

The unified application is deployed and regression-tested
locally, but it is not yet approved for an
internet-facing production environment.

## 1. Verified capabilities

| Area | Evidence | Status |
|---|---|---|
| Unified API | Docker health and OpenAPI checks | Passed |
| Policy RAG | Live policy query with citations | Passed |
| Text-to-SQL | Live query and independent DB count | Passed |
| Hybrid workflow | Live policy + data request | Passed |
| Docker Compose | Unified service on port 8000 | Passed |
| Tracing | 21 spans retrieved from Tempo | Passed |
| Regression evaluation | 17/20 answers correct | Baseline retained |
| Error handling | Mocked internal failures return HTTP 500 | Passed |

## 2. Implemented safeguards

- Pydantic request validation.
- Structured application response models.
- Restricted SQL operations and allowed tables.
- Separate read-only database credentials for generated SQL.
- Read-only SQL transactions.
- SQL execution timeout and row limits.
- Citation validation.
- Internal error-detail suppression.
- Trace identifiers for successful and internal-error responses.

These safeguards reduce risk but do not replace
security review or adversarial testing.

## 3. Outstanding work before public deployment

### Critical — Security

- Add authentication and authorization.
- Enforce API rate limits and request-size limits.
- Restrict exposed PostgreSQL and observability ports.
- Replace local AWS credential mounts with workload identity.
- Use managed secrets and least-privilege IAM policies.
- Review query validation with a SQL parser and adversarial tests.
- Validate database roles and permissions in a fresh environment.

### High — Reliability

- Investigate intermittent AI processing failures.
- Improve malformed LLM-output handling without weakening validation.
- Add request deadlines and controlled retries.
- Introduce consistent structured application logs.
- Add automated error-rate and latency alerts.
- Establish performance, load, and failure-mode tests.

### High — Answer quality

- Resolve failing cases `d03`, `d06`, and `u01`.
- Strengthen abstention on unsupported questions.
- Review date, timezone and SQL aggregation semantics.
- Improve output formatting.
- Add deterministic checks alongside the LLM judge.
- Expand evaluation with adversarial and ambiguous questions.

### Medium — Delivery and maintainability

- Consolidate application dependencies.
- Automate clean database initialization and corpus ingestion.
- Add CI with linting, tests and security checks.
- Pin and regularly review container images.
- Add reproducible deployment and rollback instructions.
- Remove legacy runtime code only after dependency verification.
- Document retention and data-protection policies.

## 4. Evaluation limitations

Three full evaluations are documented in
[EVALUATION_HISTORY.md](EVALUATION_HISTORY.md).

The latest unified evaluation scored:

- Answer correctness: 17/20 (85%).
- Retrieval hit rate: 12/12 (100%).
- Routing accuracy: 18/18 (100%).
- Abstention: 1/2 (50%).
- Evaluation errors: 0.

The three failed cases were `d03`, `d06`, and `u01`.

The LLM judge introduces scoring variability.
A correct routing decision does not guarantee a
factually correct SQL answer or safe abstention.

## 5. Operational verification performed

The refactor was validated through:

1. Python import and API contract checks.
2. Live policy, data, and hybrid questions.
3. Independent PostgreSQL count verification.
4. Standalone Docker runtime tests.
5. Unified Docker Compose deployment.
6. Distributed trace retrieval from Tempo.
7. Full 20-question regression evaluation.

## 6. Recommended next milestone

Prioritize answer correctness and unsupported-question
handling, followed by deployment security, reproducible
bootstrap, CI and automated operational tests.

Do not claim production readiness solely because
Docker deployment and functional evaluations passed.
