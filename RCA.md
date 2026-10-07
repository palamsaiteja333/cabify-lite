## Dependency Failure Test

Tempo was intentionally stopped with:

docker compose stop tempo

Observed behavior:

- rides-api remained available.
- /quote continued returning HTTP 200.
- the OpenTelemetry Collector remained running.
- trace-ingest continued receiving telemetry.
- Postgres continued storing spans while Tempo was unavailable.

No matching Collector error/retry messages were observed in the filtered logs during the test, so this experiment does not prove whether Tempo-bound spans were buffered or dropped.

After Tempo was restarted, normal tracing functionality was restored.

The important result is that failure of the tracing backend did not impact the business API.
