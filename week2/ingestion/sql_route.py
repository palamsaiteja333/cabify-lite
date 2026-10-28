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


# IMPORTANT:
#
# The SQL route must use a dedicated read-only PostgreSQL user.
#
# We intentionally do NOT fall back to DATABASE_URL here.
# The database permission boundary is one of our main
# protections against unsafe LLM-generated SQL.
READONLY_DATABASE_URL = os.getenv(
    "READONLY_DATABASE_URL"
)


if not READONLY_DATABASE_URL:
    raise RuntimeError(
        "READONLY_DATABASE_URL is required "
        "for the SQL route."
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
You generate read-only PostgreSQL queries for Cabify-Lite.

Use ONLY the database schema below.

{DATABASE_SCHEMA}


RULES

1. Generate exactly one read-only query.

   The query may begin with:

   SELECT

   or:

   WITH ... SELECT

   CTEs are allowed when they make an analytical query
   clearer or easier to calculate.

2. The final operation must always be SELECT.

3. Never generate:

   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   CREATE
   TRUNCATE
   GRANT
   REVOKE
   COPY
   CALL
   DO

4. Do not query tables outside:

   rides
   riders
   drivers
   refunds

5. Do not query:

   doc_chunks
   spans
   system catalogs

6. Do not use Markdown code fences.

7. If the user asks how many rides were "cancelled"
   without specifying who cancelled them, include BOTH:

   cancelled_by_rider
   cancelled_by_driver

8. If a month is mentioned without a year in this
   Week 2 exercise, interpret it as 2026.

9. For date filtering, prefer half-open intervals.

Example:

requested_at >= '2026-09-01'
AND requested_at < '2026-10-01'

10. For ride activity by month, use requested_at unless
    the question specifically asks about cancellation time,
    completion time, or another timestamp.

11. Keep queries simple and readable.

12. For non-aggregate queries, return at most 100 rows.

13. Cabify-Lite business timestamps must be interpreted
    using the Asia/Kolkata timezone.

    For calendar-based calculations such as day, week,
    month, or year on TIMESTAMPTZ columns, convert the
    timestamp to Asia/Kolkata before grouping or truncating.

    Example:

    DATE_TRUNC(
        'week',
        requested_at AT TIME ZONE 'Asia/Kolkata'
    )

    When using explicit calendar boundaries, treat those
    boundaries as Asia/Kolkata business time rather than UTC.

    14. For this Week 2 evaluation, the reporting/as-of date is
    2026-10-05.

    Interpret relative periods such as:

    "last 30 days"
    "last 90 days"
    "today"
    "recent"

    relative to the end of the 2026-10-05 business day in
    Asia/Kolkata.

    Use this reporting boundary:

    TIMESTAMPTZ '2026-10-06 00:00:00 Asia/Kolkata'

    IMPORTANT:
    Do NOT manually calculate the beginning date of a relative
    window.

    Let PostgreSQL calculate it.

    Example for "last 90 days":

    timestamp_column >=
        TIMESTAMPTZ '2026-10-06 00:00:00 Asia/Kolkata'
        - INTERVAL '90 days'

    AND timestamp_column <
        TIMESTAMPTZ '2026-10-06 00:00:00 Asia/Kolkata'

    This avoids date-arithmetic and off-by-one errors.


15. Cabify-Lite reporting convention for refund metrics:

    When a question asks for the number or total value of
    refunds "over the last N days", attribute the refund to
    the reporting period of its associated ride.

    Join:

    refunds.ride_id = rides.ride_id

    and apply the reporting window to:

    rides.requested_at

    This applies even when conversational wording says:

    "How many refunds did we issue over the last 90 days?"

    because the business reporting metric groups refunds by
    the ride activity period.

    Example:

    SELECT
        COUNT(*) AS refund_count,
        SUM(refunds.amount) AS total_refund_amount
    FROM refunds
    JOIN rides
      ON refunds.ride_id = rides.ride_id
    WHERE rides.requested_at >=
        TIMESTAMPTZ '2026-10-06 00:00:00 Asia/Kolkata'
        - INTERVAL '90 days'
      AND rides.requested_at <
        TIMESTAMPTZ '2026-10-06 00:00:00 Asia/Kolkata';


16. Use refunds.issued_at only when the question explicitly
    asks about refund processing or issuance timing.

    Examples:

    - "When was this refund issued?"
    - "How many refunds were issued after October 1?"
    - "How long after the ride were refunds issued?"
    - "What was the average refund processing time?"

    For those questions, refunds.issued_at is the relevant
    business timestamp.

    For general refund count/value reporting over a ride
    activity period, follow Rule 15 instead.

    17. Timestamp selection has strict precedence based on the
    business event named in the question.

    If the question asks when rides were cancelled or asks
    for cancellations during a time period:

    MUST use rides.cancelled_at for the time filter.

    Examples:

    "How many rides did drivers cancel in the last 30 days?"
      → filter status = 'cancelled_by_driver'
      → filter rides.cancelled_at

    "How many cancellations happened in September?"
      → filter rides.cancelled_at

    Do NOT use rides.requested_at for cancellation-period
    questions, even though requested_at represents the ride's
    original activity date.

    Similarly:

    ride requested/booked → requested_at
    ride cancelled        → cancelled_at
    ride completed        → completed_at
    refund processing     → refunds.issued_at

    REFUND TIMING SEMANTICS

When a question compares when a refund was issued relative
to the Ride:

- refunds.issued_at is the refund issuance timestamp.

- Use rides.requested_at as the Ride timestamp when the
  question says things such as:
  "after the ride",
  "within N days of the ride",
  or "more than N days after the ride",
  unless the user explicitly asks about completion time.

- Do NOT use rides.completed_at for general refund timing
  relative to a Ride unless the question explicitly refers
  to ride completion.

- Do NOT restrict refund timing analysis to
  rides.status = 'completed'.

- Refunds may belong to cancelled, no-show, or other
  non-completed rides.

- When testing whether refunds comply with a time threshold,
  evaluate the complete applicable refund population.

- If the question asks for both sides of a threshold,
  calculate both:
    1. refunds within the threshold
    2. refunds beyond the threshold

For example, for:
"How many refunds were issued within 7 days of the ride,
and how many were issued more than 7 days after the ride?"

the comparison should be based on:

refunds.issued_at - rides.requested_at

and should not filter only completed rides.


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
        system_prompt=SQL_SYSTEM_PROMPT,
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

    This validator allows:

        SELECT ...

    and analytical CTE queries:

        WITH something AS (...)
        SELECT ...

    It enforces:

    - exactly one SQL statement
    - SELECT / WITH...SELECT only
    - no SQL comments
    - no mutation or DDL keywords
    - no internal/system data sources
    - approved physical business tables only

    CTE names are allowed because they are temporary
    query-local result sets rather than physical tables.
    """

    cleaned = sql.strip()

    # -----------------------------------------------------
    # Allow one optional trailing semicolon
    # -----------------------------------------------------

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
    # Query must begin with SELECT or WITH
    # -----------------------------------------------------

    if not re.match(
        r"^\s*(SELECT|WITH)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "Only read-only SELECT queries are allowed."
        )


    lower_sql = cleaned.lower()


    # -----------------------------------------------------
    # Reject dangerous keywords
    # -----------------------------------------------------

    for keyword in FORBIDDEN_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            lower_sql,
        ):
            raise ValueError(
                f"Forbidden SQL keyword: {keyword}"
            )


    # -----------------------------------------------------
    # Reject internal/system data sources
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
    # Extract CTE names
    # -----------------------------------------------------

    # Example:
    #
    # WITH weekly_cancellations AS (
    #     SELECT ...
    # )
    # SELECT ...
    # FROM weekly_cancellations
    #
    # weekly_cancellations is NOT a physical database table.
    #
    # We collect it here so the normal FROM/JOIN allowlist
    # check does not incorrectly reject it.

    cte_names = set(
        match.lower()
        for match in re.findall(
            r"(?:\bWITH\b|,)\s*"
            r"([a-zA-Z_][a-zA-Z0-9_]*)"
            r"\s+AS\s*\(",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


    # -----------------------------------------------------
    # Extract FROM / JOIN references
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
    # Check physical tables against allowlist
    # -----------------------------------------------------

    physical_table_found = False

    for table_reference in table_references:

        table_name = (
            table_reference
            .split(".")[-1]
            .lower()
        )


        # A CTE is a temporary query-local result,
        # not a physical database table.
        if table_name in cte_names:
            continue


        if table_name not in ALLOWED_TABLES:
            raise ValueError(
                "Table is not allowed: "
                f"{table_name}"
            )


        physical_table_found = True


    # A query cannot simply reference arbitrary CTE names.
    #
    # At least one real approved business table must appear
    # somewhere in the SQL.
    if not physical_table_found:
        raise ValueError(
            "SQL must ultimately query an approved "
            "business table."
        )


    return cleaned


# =========================================================
# 8. EXECUTE SQL
# =========================================================

def execute_read_only_sql(
    sql: str,
) -> list[dict]:
    """
    Execute validated SQL using the dedicated
    PostgreSQL read-only account.

    Defense in depth:

    1. Application SQL validator
    2. Dedicated DB role with SELECT-only privileges
    3. PostgreSQL READ ONLY transaction
    4. 5-second statement timeout
    5. Maximum 100 returned rows
    """

    validated_sql = validate_read_only_sql(
        sql
    )


    with psycopg.connect(
        READONLY_DATABASE_URL,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:


            # -------------------------------------------------
            # Database-level read-only transaction
            # -------------------------------------------------

            cursor.execute(
                "SET TRANSACTION READ ONLY"
            )


            # -------------------------------------------------
            # Prevent runaway generated queries
            # -------------------------------------------------

            cursor.execute(
                "SET LOCAL statement_timeout = '5s'"
            )


            # -------------------------------------------------
            # Execute the validated query
            # -------------------------------------------------

            cursor.execute(
                validated_sql
            )


            # -------------------------------------------------
            # Read at most 101 rows
            #
            # 101 lets us detect that the query exceeded
            # our permitted 100-row result limit.
            # -------------------------------------------------

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
        system_prompt=DATA_SUMMARY_SYSTEM_PROMPT,
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
        PostgreSQL read-only user
          ↓
        READ ONLY transaction
          ↓
        rows
          ↓
        grounded summary
    """

    # -----------------------------------------------------
    # Step 1: Natural language -> SQL
    # -----------------------------------------------------

    generated = generate_sql(
        question
    )


    # -----------------------------------------------------
    # Step 2: Application safety validation
    # -----------------------------------------------------

    validated_sql = validate_read_only_sql(
        generated.sql
    )


    # -----------------------------------------------------
    # Step 3: Execute using read-only DB connection
    # -----------------------------------------------------

    rows = execute_read_only_sql(
        validated_sql
    )


    # -----------------------------------------------------
    # Step 4: Convert DB result to user-facing answer
    # -----------------------------------------------------

    answer = summarize_sql_result(
        question=question,
        sql=validated_sql,
        rows=rows,
    )


    # -----------------------------------------------------
    # Step 5: Structured response
    # -----------------------------------------------------

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

    print(
        "=" * 70
    )

    print(
        "DATA ROUTE RESPONSE"
    )

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )