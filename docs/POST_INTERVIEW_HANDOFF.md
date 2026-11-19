# Cabify-Lite — Post-Interview Development Handoff

**Status:** Development paused for interview preparation  
**Checkpoint date:** November 18, 2026  
**Repository:** https://github.com/palamsaiteja333/cabify-lite  
**Working branch:** `refactor/unified-app`  
**Verified pre-handoff commit:** `4be8b77`  
**Local development:** Ubuntu, `~/projects/cabify-lite`

## 1. Project objective

Build a production-style AI backend combining:

- FastAPI ride-booking services
- Policy RAG with Amazon Bedrock and pgvector
- Secure, read-only text-to-SQL
- Hybrid policy-and-data question answering
- LangChain LCEL routing and orchestration
- Docker Compose deployment
- OpenTelemetry, Tempo, Prometheus and Grafana
- Automated evaluation and measurable quality improvements

**Current outcome:** The unified application is implemented, containerized, deployed locally and regression-tested.

Future work should improve repository quality, reproducibility, observability and reliability without unnecessarily changing the verified application behavior.

---

## 2. Completed work — Do not rebuild

### Unified application

The application was migrated into:

`src/cabify_lite/`

Implemented modules include API endpoints, routing, RAG, text-to-SQL, hybrid orchestration, model integration, database connectivity and observability.

The unified Docker application is deployed through `Dockerfile.unified` and `docker-compose.yml`, exposing the API on port `8000`.

### Verified functionality

- Policy RAG answered questions with source citations.
- Text-to-SQL generated and executed a read-only query.
- September 2026 cancellations were independently verified: **140 rides**, comprising 90 rider cancellations and 50 driver cancellations.
- Hybrid routing correctly combined policy and database evidence.
- Deployed hybrid requests produced 21 spans retrievable from Grafana Tempo.
- Internal AI failures were tested for safe HTTP error handling and trace identifiers.

### Evaluation history

| Metric | Initial | Post-fixes | Unified |
|---|---:|---:|---:|
| Answer correctness | 70% | 85% | 85% |
| Retrieval | 12/12 | 12/12 | 12/12 |
| Routing | 17/18 | 18/18 | 18/18 |
| Abstention | 2/2 | 1/2 | 1/2 |
| Evaluation errors | 1 | 0 | 0 |

The unified application preserved the previous **85% answer-correctness baseline**.

Existing evaluation evidence:

- `docs/EVALUATION_HISTORY.md`
- `week2/evals/EVALUATION_EXPERIMENTS.md`
- `week2/evals/questions.yaml`
- `week2/evals/results_unified_compose_full1.json`

Do not overwrite historical evaluation results or weaken the original evaluation questions.

---

## 3. Where to resume after the interview

### Priority 1 — Clean up repository structure

**Goal:** Remove redundant runtime implementations without breaking ingestion, evaluation or Docker deployment.

Tasks:

- Preserve `src/cabify_lite/` as the canonical application.
- Consolidate dependencies into a root-level requirements configuration.
- Update `Dockerfile.unified` to use the new dependency configuration.
- Migrate `week2/ingestion/ingest.py` to use the canonical package.
- Retain the policy corpus, seed data and complete evaluation reports.
- Remove duplicated legacy runtime files only after checking imports and dependencies.
- Preserve useful scripts, including load testing and database initialization.
- Improve `.env.example`, documentation and fresh-clone setup instructions.

**Important:** `week2/ingestion/` still includes necessary ingestion logic. Do not delete the entire directory without replacing that functionality.

**Acceptance criteria:** The cleaned repository builds successfully, all three AI routes work, and regression results remain consistent with the verified baseline.

### Priority 2 — Centralize metrics using OpenTelemetry Collector

**Goal:** Stop scraping application metrics directly from `rides-api`. Instead, send application metrics through OpenTelemetry and let Prometheus scrape the Collector.

Target architecture:

```text
Unified FastAPI
      |
      | OTLP traces + metrics
      v
OpenTelemetry Collector
      |
      +---- Traces ----> Tempo
      |
      +---- Metrics ---> Prometheus exporter :8889
                              |
                              v
                         Prometheus
                              |
                              v
                           Grafana
```

Tasks:

1. Add OpenTelemetry metrics instrumentation to the FastAPI application.
2. Preserve HTTP request counts, durations and rides-created metrics.
3. Add a metrics pipeline and Prometheus exporter to the Collector.
4. Update Prometheus to scrape `otel-collector:8889`.
5. Validate metric names, labels, counters and histograms.
6. Update Grafana dashboards.
7. Verify metrics and traces together.
8. Remove the direct API scrape only after the replacement is proven.

**Important:** The existing Collector currently exports traces to Tempo. Preserve that working trace pipeline throughout the migration.

Consider the `spanmetrics` connector separately for metrics derived from trace spans.

### Priority 3 — Complete Gourav's Week 2 observability requirements

The core Week 2 RAG, SQL, hybrid-routing and evaluation work is implemented. However, Part 6 still requires additional evidence.

Outstanding tasks:

- Capture computed LLM cost per request.
- Add retrieved chunk identifiers and best/worst cosine distances to retrieval spans.
- Calculate p95 latency for each AI stage.
- Identify the 10 most expensive questions.
- Identify requests with no sufficiently relevant retrieved chunks.
- Produce three required analytical SQL queries with recorded outputs.
- Build a Grafana panel showing AI-stage latency.

**Architecture gap:** The Collector currently exports traces to Tempo, but Gourav's assignment requires SQL analysis against the PostgreSQL `spans` table.

Evaluate restoring a trace analytics ingestion path or an equivalent documented SQL-analysis workflow. Do not remove `trace-ingest` until this requirement is resolved.

### Priority 4 — Improve the three failing evaluation cases

Current failures:

- `d03`: Highest cancellation-rate week; review ISO-week formatting, timezone and percentage precision.
- `d06`: Pickup locality; avoid overstating the margin between nearly equal counts.
- `u01`: Unsupported pet/dog policy; improve abstention rather than inventing policy information.

Investigate the actual application answer and independent ground truth before changing prompts.

Run targeted tests first, followed by all 20 evaluation questions under a new result label.

**Goal:** Improve correctness and abstention without introducing regressions.

### Priority 5 — Finish remaining Week 2 deliverables

- Verify clean-clone bootstrap with `docker compose`, `make seed` and `make ingest`.
- Perform the model/provider comparison drill, including correctness, p95 latency and cost.
- Prepare the one-page VP of Support customer proposal.
- Prepare the five-minute nontechnical product demonstration.
- Consider the optional LangGraph `StateGraph` router implementation after core requirements are complete.

For LangGraph, preserve LCEL as the tested baseline and compare behavior before replacing anything.

---

## 4. Safety rules for future development

1. Never modify or weaken `week2/evals/questions.yaml` merely to improve the score.
2. Do not access `week2/facilitator/trap_key.md`.
3. Never commit `.env`, AWS credentials or local authentication caches.
4. Do not delete PostgreSQL Docker volumes or reset the database during cleanup.
5. Preserve the read-only SQL role and its security restrictions.
6. Do not use destructive Git operations on uncommitted work.
7. Make incremental changes, validate each step and commit logical units separately.
8. Keep the three historical evaluation runs and their documentation.
9. Re-run relevant tests after changes to AI routing, SQL, RAG or deployment.
10. Maintain a clear distinction between verified behavior and future production-readiness goals.

---

## 5. First actions when development resumes

Start by reading this document and reviewing the current GitHub branch.

On Ubuntu:

```bash
cd ~/projects/cabify-lite
source .venv/bin/activate

git status --short
git branch --show-current
git log -1 --oneline
```

Check for local uncommitted changes before pulling or switching branches. Earlier work included local modifications to legacy files.

Confirm the Docker deployment:

```bash
docker compose ps
docker compose config -q
curl http://127.0.0.1:8000/health
```

Then inspect repository dependencies and build a safe cleanup plan.

**Begin with Priority 1: Repository cleanup.**

Do not immediately start refactoring, change monitoring infrastructure or remove legacy files until the working-tree state has been reviewed.

---

## 6. Development strategy

Use separate commits for distinct work:

- Repository cleanup and dependency consolidation
- OpenTelemetry metrics migration
- Week 2 observability improvements
- Evaluation quality improvements
- Remaining Gourav deliverables

Preserve a working reference commit for rollback.

For major architectural changes, run the full evaluation suite and compare results against the 17/20 unified baseline.

---

## 7. Interview context and lessons worth retaining

This project demonstrates:

- Choosing a routed workflow over unnecessary autonomous-agent complexity.
- Combining unstructured policy knowledge with structured business data.
- Treating LLM-generated SQL as untrusted.
- Using citations, SQL permissions and validation as layered safeguards.
- Measuring retrieval and answer correctness independently.
- Investigating errors with distributed traces.
- Understanding why an aggregate quality improvement may conceal an abstention regression.
- Migrating an application into a modular monolith without reducing evaluated accuracy.

These engineering decisions should remain central to the project documentation and future system-design discussions.

---

## 8. Definition of completion

The next phase is complete when:

- The repository contains only necessary runtime components and reproducibility assets.
- A new developer can set up the system from documented instructions.
- FastAPI exports application traces and metrics through the Collector.
- Prometheus scrapes metrics from the Collector.
- Tempo tracing remains functional.
- Gourav's required GenAI observability analyses are documented and reproducible.
- Evaluation quality is maintained or improved, particularly abstention.
- Remaining Week 2 deliverables are completed or explicitly documented as deferred.

**Next task after the interview: Priority 1 — Safe repository cleanup and dependency consolidation.**
