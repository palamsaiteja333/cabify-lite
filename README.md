# Cabify-Lite

**A containerized AI engineering project combining Retrieval-Augmented Generation (RAG), text-to-SQL, hybrid question answering, and distributed observability.**

Cabify-Lite demonstrates how a conventional FastAPI backend can evolve into a unified AI-enabled service that answers questions using both unstructured policy documents and structured PostgreSQL data.

The project focuses on grounded answers, modular architecture, SQL safety, evaluation, and production-style observability.

## Key capabilities

- **Policy RAG:** Retrieve relevant policy chunks from PostgreSQL/pgvector, generate answers using Amazon Bedrock, and return source citations.
- **Text-to-SQL:** Translate natural-language questions into SQL, validate generated queries, and execute them using a restricted read-only database role.
- **Hybrid question answering:** Classify and decompose questions requiring both policy and database information, then synthesize a combined answer.
- **Unified API:** Expose ride booking, pricing, health, metrics, and AI endpoints through one FastAPI application.
- **Observability:** Instrument HTTP requests, retrieval, embeddings, LLM generation, and SQL execution using OpenTelemetry.
- **Evaluation:** Measure answer correctness, retrieval hit rate, routing accuracy, and abstention using a fixed 20-question dataset.

## Architecture

```text
                         Client
                           |
                           v
                    FastAPI /ask
                           |
                           v
                    LCEL Classifier
                           |
              +------------+------------+
              |            |            |
            Policy        Data         Hybrid
              |            |            |
              v            v            v
             RAG        Text-to-SQL   Decomposition
              |            |            |
       +------+-----+      |       +----+----+
       |            |      |       |         |
    Bedrock      pgvector  |      RAG       SQL
       |            |      |       |         |
       +------------+      |       +----+----+
              |            |            |
              v            v            v
          Grounded      Database     Evidence
           Answer       Answer       Synthesis
              |            |            |
              +------------+------------+
                           |
                           v
                  Response + Citations

    OpenTelemetry -> Collector -> Tempo -> Grafana
    FastAPI Metrics -> Prometheus -> Grafana
```

## Technology stack

| Layer | Technologies |
|---|---|
| API | Python, FastAPI, Pydantic |
| AI orchestration | LangChain LCEL |
| LLM | Amazon Nova via AWS Bedrock |
| Embeddings | Amazon Titan Text Embeddings V2 |
| Vector retrieval | PostgreSQL, pgvector |
| Structured data | PostgreSQL, psycopg |
| Deployment | Docker, Docker Compose |
| Tracing | OpenTelemetry, Grafana Tempo |
| Metrics | Prometheus, Grafana |
| Evaluation | Python, YAML, LLM-based grading |

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service health |
| `GET /quote` | Ride pricing |
| `GET /rides/{ride_id}` | Retrieve a ride |
| `POST /rides` | Create a ride |
| `POST /ask` | Policy, data, and hybrid AI queries |
| `GET /metrics` | Prometheus metrics |

### Example: Hybrid AI request

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the cancellation policy, and how many rides were cancelled in September 2026?",
    "top_k": 5
  }'
```

The response includes a `hybrid` route, policy evidence and citations, a generated SQL query, and a synthesized answer.

In the seeded demonstration database, the verified September 2026 cancellation count is **140 rides**.

## Evaluation results

The same 20-question dataset was evaluated across three full runs.

| Metric | Initial | Post-fixes | Unified Docker |
|---|---:|---:|---:|
| Answer correctness | 70% | 85% | 85% |
| Retrieval hit rate | 12/12 | 12/12 | 12/12 |
| Routing accuracy | 17/18 | 18/18 | 18/18 |
| Abstention | 2/2 | 1/2 | 1/2 |
| Evaluation errors | 1 | 0 | 0 |

Answer correctness improved by **15 percentage points**, and the unified Docker deployment retained the improved score.

The latest run still fails three cases: `d03`, `d06`, and `u01`. These remain open quality-improvement tasks.

See [Evaluation History](docs/EVALUATION_HISTORY.md) for individual runs, limitations, and reproduction instructions.

## Project structure

```text
src/cabify_lite/
  api/             FastAPI routes
  ai/rag/          Retrieval and grounded answers
  ai/sql/          SQL generation and execution
  ai/hybrid/       Decomposition and synthesis
  ai/routing/      Classification and LCEL routing
  ai/providers/    Model integrations
  core/            Configuration and models
  db/              Database integration
  observability/   Metrics and tracing

week2/
  corpus/          Policy documents
  evals/           Evaluation questions and reports
  ingestion/       Original Week 2 implementation and tooling
  seed/            Demonstration data assets

docs/              Engineering documentation
```

The legacy Week 2 implementation is retained for reproducibility and migration reference. The deployed API uses the unified `src/cabify_lite` package.

## Local development

### Prerequisites

- Docker and Docker Compose
- Python 3.12
- PostgreSQL demonstration data and ingested policy documents
- AWS credentials with access to the configured Bedrock models

Create a local `.env` using `.env.example` as a starting point and configure the database, read-only SQL credentials, and AWS settings.

**Never commit `.env`, AWS credentials, or login-cache files.**

The current Compose configuration uses local AWS authentication mounts and assumes the database has been initialized. A fully automated first-run bootstrap remains future work.

### Start the application

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

The unified `rides-api` service is built using `Dockerfile.unified`.

### Run evaluations

After configuring AWS and populating PostgreSQL:

```bash
python week2/evals/run_evals_unified.py \
  --top-k 5 \
  --label your_unique_run
```

Use a unique label to preserve existing evaluation reports. Evaluations invoke Bedrock and can incur inference charges.

## Observability

Open the locally exposed tools:

- Grafana: `http://localhost:3000`
- Tempo API: `http://localhost:3200`
- Prometheus: `http://localhost:9090`
- FastAPI metrics: `http://localhost:8000/metrics`

A deployed hybrid request was verified in Tempo with **21 recorded spans**, covering routing, embedding, retrieval, LLM generation, SQL generation, SQL execution, and HTTP instrumentation.

The repository also contains an earlier incident investigation in [RCA.md](RCA.md).

## Security and production-readiness

This project is a **production-style engineering demonstration**, not a hardened public service.

Implemented safeguards include:

- Request validation using Pydantic.
- Restricted SQL tables and query validation.
- A read-only database account for AI-generated SQL.
- Database transaction-level read-only enforcement.
- Bounded SQL execution and result limits.
- Citation validation and grounded-answer rules.
- Internal error-detail suppression and trace identifiers.

Before a public production deployment, the project would need additional work on authentication, rate limiting, secrets management, network restrictions, CI/CD, SQL hardening, resilience testing, and evaluation reliability.

The current Docker configuration is intended for a controlled local environment.

## Engineering outcomes

- Consolidated separate backend and AI pipelines into a modular application.
- Preserved all baseline evaluation metrics during migration.
- Demonstrated policy RAG, structured SQL, and hybrid routing in live Docker requests.
- Verified end-to-end OpenTelemetry trace delivery.
- Identified unresolved SQL-answer and abstention cases for future improvement.

## Status

**Unified application deployed and regression-tested locally.**

Next priorities: reliability improvements, automated testing, clean bootstrap scripts, CI/CD, and production security hardening.
