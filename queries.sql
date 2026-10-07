-- ============================================================
-- Cabify-Lite
-- Part 4: Trace Analysis Queries
-- ============================================================


-- ============================================================
-- Query 1: Slowest 10 traces today
-- ============================================================

SELECT
    trace_id,
    ROUND(
        (
            EXTRACT(
                EPOCH FROM (
                    MAX(
                        start_time
                        + duration_ms * INTERVAL '1 millisecond'
                    )
                    - MIN(start_time)
                )
            ) * 1000
        )::numeric,
        2
    ) AS trace_duration_ms,
    COUNT(*) AS span_count
FROM spans
WHERE start_time >= CURRENT_DATE
GROUP BY trace_id
ORDER BY trace_duration_ms DESC
LIMIT 10;



-- ============================================================
-- Query 2: Error rate by endpoint
-- ============================================================

SELECT
    attributes ->> 'http.route' AS endpoint,

    COUNT(*) AS total_requests,

    COUNT(*) FILTER (
        WHERE (attributes ->> 'http.status_code')::int >= 500
    ) AS error_requests,

    ROUND(
        (
            100.0
            * COUNT(*) FILTER (
                WHERE (attributes ->> 'http.status_code')::int >= 500
            )
            / NULLIF(COUNT(*), 0)
        ),
        2
    ) AS error_rate_percent

FROM spans

WHERE attributes ? 'http.route'
  AND attributes ? 'http.status_code'
  AND attributes ->> 'http.route' <> '/metrics'

GROUP BY attributes ->> 'http.route'

ORDER BY
    error_rate_percent DESC,
    total_requests DESC;



-- ============================================================
-- Query 3: p95 duration by span_name
-- ============================================================

SELECT
    span_name,

    ROUND(
        percentile_cont(0.95)
        WITHIN GROUP (ORDER BY duration_ms)::numeric,
        2
    ) AS p95_duration_ms,

    COUNT(*) AS span_count

FROM spans

WHERE span_name NOT LIKE 'GET /metrics%'

GROUP BY span_name

ORDER BY p95_duration_ms DESC;



-- ============================================================
-- Query 4: Full span breakdown for one trace_id
--
-- Replace PASTE_TRACE_ID_HERE with an actual trace ID
-- from Tempo or from Query 1.
-- ============================================================

SELECT
    trace_id,
    span_id,
    parent_span_id,
    service,
    span_name,
    start_time,
    ROUND(duration_ms::numeric, 2) AS duration_ms,
    status,
    attributes

FROM spans

WHERE trace_id = 'b35903c655599fa757f5c2e1c52e8cd7'

ORDER BY
    start_time ASC,
    duration_ms DESC;



-- ============================================================
-- Query 5:
-- Which span dominates slow /quote traces?
--
-- We define the slowest ~20% of /quote requests as
-- "slow quote traces", then inspect their child spans.
-- ============================================================

WITH quote_traces AS (

    SELECT
        trace_id,
        duration_ms AS trace_duration_ms

    FROM spans

    WHERE span_name = 'GET /quote'
      AND attributes ->> 'http.route' = '/quote'
),

slow_threshold AS (

    SELECT
        percentile_cont(0.80)
        WITHIN GROUP (ORDER BY trace_duration_ms)
        AS threshold_ms

    FROM quote_traces
),

slow_quote_traces AS (

    SELECT
        q.trace_id,
        q.trace_duration_ms

    FROM quote_traces q
    CROSS JOIN slow_threshold t

    WHERE q.trace_duration_ms >= t.threshold_ms
),

span_contribution AS (

    SELECT
        s.span_name,

        COUNT(*) AS occurrences,

        AVG(s.duration_ms) AS avg_span_duration_ms,

        MAX(s.duration_ms) AS max_span_duration_ms,

        AVG(
            100.0 * s.duration_ms
            / NULLIF(q.trace_duration_ms, 0)
        ) AS avg_percent_of_trace

    FROM spans s

    JOIN slow_quote_traces q
        ON s.trace_id = q.trace_id

    WHERE s.span_name <> 'GET /quote'
      AND s.span_name NOT LIKE 'GET /quote http %'

    GROUP BY s.span_name
)

SELECT
    span_name,
    occurrences,

    ROUND(
        avg_span_duration_ms::numeric,
        2
    ) AS avg_span_duration_ms,

    ROUND(
        max_span_duration_ms::numeric,
        2
    ) AS max_span_duration_ms,

    ROUND(
        avg_percent_of_trace::numeric,
        2
    ) AS avg_percent_of_trace

FROM span_contribution

ORDER BY avg_span_duration_ms DESC;