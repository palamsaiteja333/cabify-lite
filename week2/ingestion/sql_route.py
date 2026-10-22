import json
import os
import re
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from pydantic import BaseModel

from llm_stage import generate_text


# =========================================================
# 1. ENVIRONMENT / DATABASE
# =========================================================

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:

    postgres_user = os.getenv(
        "POSTGRES_USER"
    )

    postgres_password = os.getenv(
        "POSTGRES_PASSWORD"
    )

    postgres_db = os.getenv(
        "POSTGRES_DB"
    )

    if not all(
        [
            postgres_user,
            postgres_password,
            postgres_db,
        ]
    ):
        raise RuntimeError(
            "DATABASE_URL or PostgreSQL "
            "environment variables are missing."
        )

    DATABASE_URL = (
        f"postgresql://"
        f"{postgres_user}:"
        f"{postgres_password}"
        f"@localhost:5432/"
        f"{postgres_db}"
    )


# =========================================================
# 2. PYDANTIC MODELS
# =========================================================

class SQLGeneration(BaseModel):
    """
    Structured output produced by Nova
    during text-to-SQL generation.
    """

    sql: str
    reason: str


class DataRouteResponse(BaseModel):
    """
    Final response from the structured-data route.
    """

    answer: str

    sql: str

    rows: list[
        dict[str, Any]
    ]


# =========================================================
# 3. DATABASE SCHEMA FOR THE LLM
# =========================================================

DATABASE_SCHEMA = """
TABLE: rides

Columns:
- ride_id INTEGER PRIMARY KEY
- rider_id INTEGER NOT NULL
- driver_id INTEGER
- requested_at TIMESTAMPTZ NOT NULL
- started_at TIMESTAMPTZ
- completed_at TIMESTAMPTZ
- pickup TEXT NOT NULL
- dropoff TEXT NOT NULL
- distance_km NUMERIC(6,2)
- duration_min INTEGER
- fare_amount NUMERIC(10,2) NOT NULL
- currency CHAR(3) NOT NULL
- status TEXT NOT NULL
- cancelled_at TIMESTAMPTZ
- cancellation_reason TEXT

Allowed ride status values:
- completed
- cancelled_by_rider
- cancelled_by_driver
- no_show
- disputed


TABLE: riders

Columns:
- rider_id INTEGER PRIMARY KEY
- name TEXT NOT NULL
- joined_at TIMESTAMPTZ NOT NULL
- city TEXT NOT NULL
- rating NUMERIC(3,2)


TABLE: drivers

Columns:
- driver_id INTEGER PRIMARY KEY
- name TEXT NOT NULL
- joined_at TIMESTAMPTZ NOT NULL
- city TEXT NOT NULL
- rating NUMERIC(3,2)
- vehicle_type TEXT NOT NULL


TABLE: refunds

Columns:
- refund_id INTEGER PRIMARY KEY
- ride_id INTEGER NOT NULL
- amount NUMERIC(10,2) NOT NULL
- reason TEXT NOT NULL
- issued_at TIMESTAMPTZ NOT NULL
- issued_by TEXT NOT NULL

Allowed refund reasons:
- driver_cancelled
- service_issue
- no_show_contested
- goodwill


RELATIONSHIPS

rides.rider_id
    -> riders.rider_id

rides.driver_id
    -> drivers.driver_id

refunds.ride_id
    -> rides.ride_id
""".strip()


# =========================================================
# 4. SQL GENERATION PROMPT
# =========================================================

SQL_SYSTEM_PROMPT = f"""
You generate PostgreSQL SELECT queries for Cabify-Lite.

Use ONLY the database schema below.

{DATABASE_SCHEMA}


RULES

1. Generate exactly one SELECT statement.

2. Never generate:
   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   CREATE
   TRUNCATE
   GRANT
   REVOKE

3. Do not query tables outside:
   rides
   riders
   drivers
   refunds

4. Do not query:
   doc_chunks
   spans
   system catalogs

5. Do not use Markdown code fences.

6. If the user asks how many rides were "cancelled"
   without specifying who cancelled them, include BOTH:

   cancelled_by_rider
   cancelled_by_driver

7. If a month is mentioned without a year in this
   Week 2 exercise, interpret it as 2026.

8. For date filtering, prefer half-open intervals.

Example:

requested_at >= '2026-09-01'
AND requested_at < '2026-10-01'

9. For ride activity by month, use requested_at unless
   the question specifically asks about cancellation time,
   completion time, or another timestamp.

10. Keep queries simple and readable.

11. For non-aggregate queries, return at most 100 rows.


Return ONLY valid JSON:

{{
  "sql": "SELECT ...",
  "reason": "brief explanation"
}}
""".strip()


# =========================================================
# 5. CLEAN MODEL JSON
# =========================================================

def clean_json_output(
    raw_output: str,
) -> str:
    """
    Remove predictable Markdown fences if
    the model adds them despite instructions.
    """

    cleaned = raw_output.strip()

    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^```\s*",
        "",
        cleaned,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    return cleaned.strip()


# =========================================================
# 6. GENERATE SQL
# =========================================================

def generate_sql(
    question: str,
) -> SQLGeneration:
    """
    Convert a natural-language data question
    into PostgreSQL.
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    prompt = f"""
USER QUESTION

{question}
""".strip()

    raw_output = generate_text(
        prompt=prompt,
        system_prompt=
            SQL_SYSTEM_PROMPT,
    )

    cleaned_output = clean_json_output(
        raw_output
    )

    return SQLGeneration.model_validate_json(
        cleaned_output
    )


# =========================================================
# 7. SQL SAFETY VALIDATION
# =========================================================

ALLOWED_TABLES = {
    "rides",
    "riders",
    "drivers",
    "refunds",
}


FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "call",
    "do",
    "vacuum",
    "analyze",
    "reindex",
    "cluster",
}


def validate_read_only_sql(
    sql: str,
) -> str:
    """
    Application-level SQL safety check.

    The LLM prompt is NOT considered a security boundary.

    This validator enforces:
    - one statement only
    - SELECT only
    - no SQL comments
    - no mutation / DDL keywords
    - approved business tables only
    """

    cleaned = sql.strip()

    # Allow one optional trailing semicolon.
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    if not cleaned:
        raise ValueError(
            "Generated SQL is empty."
        )


    # -----------------------------------------------------
    # Only one SQL statement
    # -----------------------------------------------------

    if ";" in cleaned:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )


    # -----------------------------------------------------
    # No SQL comments
    # -----------------------------------------------------

    if (
        "--" in cleaned
        or "/*" in cleaned
        or "*/" in cleaned
    ):
        raise ValueError(
            "SQL comments are not allowed."
        )


    # -----------------------------------------------------
    # SELECT only
    # -----------------------------------------------------

    if not re.match(
        r"^\s*SELECT\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "Only SELECT statements are allowed."
        )


    # -----------------------------------------------------
    # Reject dangerous keywords
    # -----------------------------------------------------

    lower_sql = cleaned.lower()

    for keyword in FORBIDDEN_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            lower_sql,
        ):
            raise ValueError(
                f"Forbidden SQL keyword: {keyword}"
            )


    # -----------------------------------------------------
    # Reject internal/system tables
    # -----------------------------------------------------

    forbidden_sources = [
        "doc_chunks",
        "spans",
        "pg_catalog",
        "information_schema",
    ]

    for source in forbidden_sources:

        if re.search(
            rf"\b{re.escape(source)}\b",
            lower_sql,
        ):
            raise ValueError(
                f"Forbidden data source: {source}"
            )


    # -----------------------------------------------------
    # Extract FROM / JOIN table names
    # -----------------------------------------------------

    table_references = re.findall(
        r"\b(?:FROM|JOIN)\s+"
        r"([a-zA-Z_][a-zA-Z0-9_\.]*)",
        cleaned,
        flags=re.IGNORECASE,
    )

    if not table_references:
        raise ValueError(
            "SQL must query an approved table."
        )


    # -----------------------------------------------------
    # Check table allowlist
    # -----------------------------------------------------

    for table_reference in table_references:

        table_name = (
            table_reference
            .split(".")[-1]
            .lower()
        )

        if table_name not in ALLOWED_TABLES:

            raise ValueError(
                "Table is not allowed: "
                f"{table_name}"
            )


    return cleaned


# =========================================================
# 8. EXECUTE SQL
# =========================================================

def execute_read_only_sql(
    sql: str,
) -> list[dict]:
    """
    Execute validated SQL using a PostgreSQL
    read-only transaction.

    We also apply a 5-second statement timeout.
    """

    validated_sql = validate_read_only_sql(
        sql
    )

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            # Second security layer:
            # PostgreSQL itself treats this transaction
            # as READ ONLY.
            cursor.execute(
                "SET TRANSACTION READ ONLY"
            )

            # Prevent runaway generated queries.
            cursor.execute(
                "SET LOCAL statement_timeout = '5s'"
            )

            cursor.execute(
                validated_sql
            )

            # Read at most 101 rows so we can detect
            # unexpectedly large results.
            rows = cursor.fetchmany(
                101
            )

            if len(rows) > 100:
                raise ValueError(
                    "Query returned more than "
                    "100 rows."
                )

            return [
                dict(row)
                for row in rows
            ]


# =========================================================
# 9. SUMMARIZE SQL RESULT
# =========================================================

DATA_SUMMARY_SYSTEM_PROMPT = """
You answer questions using ONLY the supplied SQL result.

Do not use outside knowledge.

Do not invent numbers.

Do not change the meaning of the SQL result.

Answer concisely and directly.

If the SQL result is empty, clearly state that no matching
records were found.

Do not include SQL unless the user specifically asks for it.
""".strip()


def summarize_sql_result(
    question: str,
    sql: str,
    rows: list[dict],
) -> str:
    """
    Convert raw database rows into a natural-language answer.
    """

    rows_json = json.dumps(
        rows,
        indent=2,
        default=str,
    )

    prompt = f"""
USER QUESTION

{question}


SQL EXECUTED

{sql}


SQL RESULT

{rows_json}
""".strip()

    return generate_text(
        prompt=prompt,
        system_prompt=
            DATA_SUMMARY_SYSTEM_PROMPT,
    ).strip()


# =========================================================
# 10. COMPLETE DATA ROUTE
# =========================================================

def answer_data_question(
    question: str,
) -> DataRouteResponse:
    """
    Complete structured-data flow:

        question
          ↓
        generate SQL
          ↓
        validate SQL
          ↓
        PostgreSQL READ ONLY
          ↓
        rows
          ↓
        grounded summary
    """

    # Step 1
    generated = generate_sql(
        question
    )

    # Step 2
    validated_sql = validate_read_only_sql(
        generated.sql
    )

    # Step 3
    rows = execute_read_only_sql(
        validated_sql
    )

    # Step 4
    answer = summarize_sql_result(
        question=question,
        sql=validated_sql,
        rows=rows,
    )

    # Step 5
    return DataRouteResponse(
        answer=answer,
        sql=validated_sql,
        rows=rows,
    )


# =========================================================
# 11. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "How many rides were "
        "cancelled in September?"
    )

    result = answer_data_question(
        question
    )

    print()
    print("=" * 70)

    print(
        "DATA ROUTE RESPONSE"
    )

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )