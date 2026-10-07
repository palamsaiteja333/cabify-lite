import os

import psycopg
from psycopg.types.json import Jsonb


DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection():
    return psycopg.connect(DATABASE_URL)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    service TEXT NOT NULL,
                    span_name TEXT NOT NULL,
                    start_time TIMESTAMPTZ NOT NULL,
                    duration_ms DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL,
                    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,

                    PRIMARY KEY (trace_id, span_id)
                );
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_spans_trace_id
                ON spans(trace_id);
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_spans_start_time
                ON spans(start_time);
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_spans_span_name
                ON spans(span_name);
            """)


def insert_span(
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    service: str,
    span_name: str,
    start_time,
    duration_ms: float,
    status: str,
    attributes: dict,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO spans (
                    trace_id,
                    span_id,
                    parent_span_id,
                    service,
                    span_name,
                    start_time,
                    duration_ms,
                    status,
                    attributes
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (trace_id, span_id)
                DO NOTHING;
                """,
                (
                    trace_id,
                    span_id,
                    parent_span_id,
                    service,
                    span_name,
                    start_time,
                    duration_ms,
                    status,
                    Jsonb(attributes),
                ),
            )