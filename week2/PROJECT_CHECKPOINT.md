# Cabify-Lite Week 2 — Project Checkpoint
**Checkpoint date:** 2026-11-02  
**Repository:** https://github.com/palamsaiteja333/cabify-lite  
**Working branch:** `week2-grounded-answers` (do not merge to `main` yet)  
**Ubuntu repo:** `~/projects/cabify-lite`; Python virtualenv `.venv` on Ubuntu 24.04.  
**Current pause:** Interview notes on tracing, routing, Collector, and Docker port security have been provided in ChatGPT. User is taking the free LangChain Academy *Introduction to LangGraph — Python* course before returning to implement the LangGraph stretch router. **Do not start LangGraph changes until the user returns.**

## Safety and work boundaries
- **NEVER open or read** `week2/facilitator/trap_key.md`.
- Do not weaken or silently edit `week2/evals/questions.yaml` to force passing results.
- Do not expose credentials, `.env`, AWS secrets, database passwords, prompts, retrieved full text, or SQL result payloads in traces or commits.
- Do not automatically stage all untracked files; there were local `.bak` backups and uncommitted evaluation output files. Inspect `git status --short` first.
- Traces must go **Week 2 Python → OTel Collector → Grafana Tempo**, **not PostgreSQL**. Prometheus metrics migration is explicitly deferred.
- Preserve read-only SQL safety boundaries and existing Week 2 functionality.
- Prefer incremental changes, backed by focused tests; do not merge to main.

## What is built
1. **Week 1 infrastructure:** `rides-api`, PostgreSQL, OTel Collector, Tempo, Grafana, Prometheus, and legacy `trace-ingest` Compose service. The legacy trace-ingest service still has a Compose definition but is **not in the Collector traces export pipeline**.
2. **Week 2 data:** deterministic seed (~420 riders, 95 drivers, 2,002 rides, 60 refunds; anchor 2026-10-05).
3. **Document RAG:** six corpus docs; chunking, Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`), 1024-dimensional vectors, PostgreSQL/pgvector HNSW cosine index; roughly 69 chunks. LCEL grounded responses, citations, Pydantic validation, abstention/conflict handling.
4. **Structured SQL route:** Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`, AWS region `us-east-2`) generates SQL. Validator restricts to read-only `SELECT` and analytical `WITH...SELECT`, approved physical tables, no mutation/DDL, and one statement. Dedicated `READONLY_DATABASE_URL`, `SET TRANSACTION READ ONLY`, 5-second timeout, max 100 rows. SQL results synthesized into natural language.
5. **Routing:** `router_classifier.py` validates LLM route `policy | data | hybrid` via Pydantic. `routed_chain.py` uses LangChain `RunnableLambda` + `RunnableBranch`: policy → `answer_question_lcel`; data → `answer_data_question`; hybrid → decompose then policy RAG + SQL + final synthesis in `hybrid_route.py`.
6. **FastAPI:** `week2/ingestion/api.py` `POST /ask` accepts `question` and `top_k`, calls `answer_question_routed()`, responds with `RoutedResponse {route,result}`, and sets `X-Trace-ID` header; `GET /health` exists. **The Week 2 endpoint was tested by starting Uvicorn directly on host port 18082; deployment in the existing Week 1 `rides-api` container on port 8000 has not been verified.** Old flat API response changed to nested `route/result`.
7. **Observability:** `telemetry.py` configures OpenTelemetry `TracerProvider`, resource service name `cabify-grounded-answers`, `BatchSpanProcessor`, OTLP/gRPC exporter at host `http://localhost:4317`. Manual spans: `classify` (router route), `embed_query` (model, dimensions), `retrieve` (top_k, count), `llm_generate` (provider/model/input-output tokens), `sql_generate` (generated flag), `sql_execute` (db system/row count); `ask_request` wraps HTTP handler. Collector `otel-collector/config.yaml` forwards trace pipeline via `otlp/tempo` to `tempo:4317`, plus debug exporter. No trace-to-Postgres exporter. `docker-compose.yml` host port publish is `127.0.0.1:4317:4317`, whereas Collector receiver inside Docker listens `0.0.0.0:4317` for container connectivity.

## Verified test evidence (from Ubuntu outputs)
- Installed OpenTelemetry Python API/SDK and OTLP gRPC exporter (1.45.1).
- Basic test span `week2_observability_test` exported and queried in Tempo, HTTP 200.
- `llm_generate` Bedrock test: response `OK`, provider/model and 53 input / 4 output tokens recorded; about 1.08s.
- Classifier returned `policy` and produced nested `classify` + `llm_generate` spans.
- RAG retrieval test returned 5 chunks; `embed_query` reported 1024 dimensions; `retrieve` reported `top_k=5`, `retrieved_chunks=5`.
- SQL data test answered 140 cancelled rides in September, one SQL result row; `sql_generate`, `sql_execute`, and two LLM spans captured. This was an application result, not a fresh independent SQL audit.
- Hybrid CLI test classified `hybrid` and answered cancellation fee ₹30 and no-show fees ₹4,080.
- Hybrid CLI trace (ID `665d36656450d0df119bba5f7aff8138`): 12 spans; all six required stages present, zero orphan parent references.
- FastAPI HTTP test after AWS reauthentication: `GET /health` OK; `POST /ask` HTTP 200 with `route=hybrid`, `X-Trace-ID` `16d53540e5b68ebec5e1f14f39a62f95`.
- That HTTP trace contained **16 spans**, all seven span types including `ask_request`, and **no disconnected application spans**. `ask_request` has an upstream `fastapi.endpoint` parent span; it is not the absolute trace root.
- Python syntax compilation passed for six edited Python modules and `git diff --cached --check` passed.
- GitHub remote branch was checked on 2026-11-02; observability files and host-local Collector binding are pushed.

## Significant debugging stories to remember
- HTTP /ask returned 500 because Boto3 threw `LoginRefreshRequired` during AWS credentials refresh; not a routing bug. Reauthenticated, reran direct handler and HTTP tests successfully.
- First HTTP trace verification script incorrectly required `ask_request` to have no parent; the actual parent was `fastapi.endpoint`. Corrected verification to check all relevant spans descend from `ask_request`.
- RAG/SQL evaluation issues: refund reporting windows must use business event-time semantics; `WITH...SELECT` valid CTEs needed validator support; Kolkata business timezone changed weekly aggregations; cancellation metrics require `cancelled_at` not just `requested_at`; conflicting FAQ vs authoritative cancellation policy required source hierarchy; refund-policy compliance required checking both compliant and violating records.

## Latest committed evaluation baseline
`week2/evals/results_post_fixes.md`:
- Retrieval: **12/12 = 100%**
- Routing: **18/18 = 100%**
- Answer correctness: **17/20 = 85%**
- Abstention: **1/2 = 50%**
- Pending cases: `d03` (format/precision judge concern around 29.59% vs 29.6% week of Aug 24), `d06` (possible false-negative judgment over Whitefield 118 rides vs close runner-up), `u01` (real abstention regression, dog/pet policy unsupported). **Do not start these until the higher-priority tasks are addressed.**

## Agreed next work order
1. **Current pause:** User completes https://academy.langchain.com/courses/intro-to-langgraph; interview notes for completed observability work already supplied.
2. **NEXT WHEN USER RETURNS: LangGraph stretch — Stateful router.** Keep existing LCEL implementation as baseline. Implement new `StateGraph` with explicit shared state, `classify` node, conditional routing to policy/data/hybrid (or equivalent router nodes), answer collection, preservation of Pydantic response contracts and manual OTel spans. For the original lesson, think classify → retrieve-or-sql → answer; hybrid uses both. Avoid adding unrelated features, side effects, or modifying evaluation benchmarks. Test one example each for policy, data, hybrid; compare with LCEL, verify Tempo tracing; commit separately on Week 2 branch.
3. **Part 8:** one-page customer proposal for Cabify-Lite VP of Support: problem, plain-language RAG-vs-SQL approach, scope/exclusions, assumptions, risks/mitigations, rough timeline.
4. **Part 5:** evaluate `d03`, `d06`, `u01` honestly (differentiate evaluator false negatives from system bugs); maintain evidence and expected-answer integrity.
5. **Part 7:** model/provider swap drill, compare evaluation outcomes, p95 latency, and cost; do not swap embedding model without reindexing.
6. **Final acceptance:** original Part 6 rubric still asks for cost per question, retrieval quality attributes, three SQL/p95/cost analyses, Grafana stage-latency panel, and a five-minute demo. Current deliberate Tempo-only trace architecture means original SQL-spans requirement needs an agreed alternative analytics path; these are **not yet completed**. Verify packaging of `/ask` into desired Docker deployment and run cold-start regression.
7. Keep Prometheus-to-Collector metrics migration **deferred** until explicitly prioritized.

## When resuming
- Start by reviewing this checkpoint and latest GitHub `week2-grounded-answers` state.
- On Ubuntu: `cd ~/projects/cabify-lite && source .venv/bin/activate && git status --short && git branch --show-current`. Inspect uncommitted files before any pull or staging. Do not overwrite local eval outputs or `.bak` backups.
- **Do not read `week2/facilitator/trap_key.md`.**
- User's requested immediate task on return: **build the LangGraph stateful router using the course knowledge**, explain the transition from LCEL, preserve tracing, and run incremental verification.
