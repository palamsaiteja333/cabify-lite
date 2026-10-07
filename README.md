# Cabify-Lite

Cabify-Lite is a small ride-booking API built as a Week 1 systems and observability project.

The goal of the project is to run a multi-service application locally and be able to investigate questions such as:

> Why was this request slow or why did it fail?

using metrics, distributed traces, and SQL.

## Architecture

```text
Client
  |
  v
rides-api
  |
  +------> PostgreSQL
  |
  +------> OpenTelemetry Collector
               |
               +------> Tempo ------> Grafana
               |
               +------> trace-ingest ------> PostgreSQL

rides-api /metrics ------> Prometheus ------> Grafana
```

## Services

The Docker Compose stack contains:

- `rides-api` - FastAPI application
- `postgres` - application database and trace storage
- `otel-collector` - receives and exports OpenTelemetry traces
- `tempo` - distributed tracing backend
- `trace-ingest` - receives OTLP traces and stores spans in PostgreSQL
- `prometheus` - collects application metrics
- `grafana` - metrics and trace visualization

## Prerequisites

Install:

- Docker
- Docker Compose
- Git
- curl

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/palamsaiteja333/cabify-lite.git
cd cabify-lite
```

### 2. Create the environment file

```bash
cp .env.example .env
```

### 3. Start the stack

```bash
docker compose up -d --build
```

Check the containers:

```bash
docker compose ps
```

### 4. Verify the API

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## API Usage

### Create a ride

```bash
curl -X POST "http://localhost:8000/rides" \
  -H "Content-Type: application/json" \
  -d '{
    "pickup": "Union Station",
    "destination": "CN Tower"
  }'
```

### Get a ride

```bash
curl http://localhost:8000/rides/1
```

### Get a quote

```bash
curl -G "http://localhost:8000/quote" \
  --data-urlencode "from=Union Station" \
  --data-urlencode "to=CN Tower"
```

The quote flow contains instrumented business logic, including a simulated pricing delay that makes it possible to investigate slow requests.

## Observability

### Grafana

Open:

```text
http://localhost:3000
```

Grafana is used to explore Prometheus metrics and Tempo traces.

### Prometheus

Open:

```text
http://localhost:9090
```

The API exposes Prometheus metrics at:

```text
http://localhost:8000/metrics
```

Metrics include:

- HTTP request count
- HTTP request latency histogram
- rides created counter

The Grafana dashboard includes latency percentiles and HTTP error-rate monitoring.

### Tempo

Tempo stores distributed traces exported through the OpenTelemetry Collector.

A quote request produces application spans such as:

```text
GET /quote
  |
  +-- simulate_pricing_delay
  |
  +-- calculate_quote_price
```

Automatic instrumentation is also enabled for FastAPI and PostgreSQL operations.

## Trace Storage in PostgreSQL

The OpenTelemetry Collector exports traces to both Tempo and the custom `trace-ingest` service.

`trace-ingest` converts OTLP spans into rows in the PostgreSQL `spans` table.

The table contains fields including:

```text
trace_id
span_id
parent_span_id
service
span_name
start_time
duration_ms
status
attributes
```

Span attributes are stored as JSONB.

## SQL Trace Analysis

The required analysis queries are available in:

```text
queries.sql
```

They cover:

1. Slowest 10 traces today
2. Error rate by endpoint
3. p95 duration grouped by span name
4. Full span breakdown for a trace ID
5. Finding the span responsible for slow quote requests

The slow-request analysis identified `simulate_pricing_delay` as the primary contributor to slow quote traces.

To open PostgreSQL manually:

```bash
docker compose exec postgres sh -lc \
'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Failure Investigation

As part of the observability exercise, a controlled failure was introduced into the ride lookup endpoint and mixed traffic was generated.

The failure was investigated using:

- Grafana metrics
- Tempo traces
- PostgreSQL span queries

The root cause and investigation are documented in:

```text
RCA.md
```

The deliberate application failure has been removed after completing the investigation.

## Observability Dependency Test

Tempo was intentionally stopped to test whether an observability dependency could affect application availability.

```bash
docker compose stop tempo
```

During the test:

- `rides-api` continued serving requests
- `/quote` continued returning HTTP 200
- the OpenTelemetry Collector remained running
- trace ingestion into PostgreSQL continued

This demonstrated that failure of the tracing backend does not bring down the business API.

Tempo can be restarted with:

```bash
docker compose start tempo
```

## Generate Test Traffic

A simple traffic-generation script is included:

```bash
./load_test.sh
```

It sends a mixture of ride and quote requests that can be inspected through metrics, traces, and SQL.

## Useful Commands

Check container status:

```bash
docker compose ps
```

View API logs:

```bash
docker compose logs rides-api
```

View OpenTelemetry Collector logs:

```bash
docker compose logs otel-collector
```

View trace ingestion logs:

```bash
docker compose logs trace-ingest
```

Stop the environment:

```bash
docker compose down
```

Start it again:

```bash
docker compose up -d
```

## Project Deliverables

- Docker Compose application stack
- FastAPI ride service
- PostgreSQL persistence
- OpenTelemetry instrumentation
- Tempo distributed tracing
- Prometheus metrics
- Grafana observability
- PostgreSQL trace storage
- `queries.sql` for trace analysis
- `RCA.md` for the failure investigation