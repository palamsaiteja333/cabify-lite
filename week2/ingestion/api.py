from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from routed_chain import (
    answer_question_routed,
    RoutedResponse,
)

from telemetry import tracer

from opentelemetry.trace import (
    SpanKind,
    Status,
    StatusCode,
)


# =========================================================
# 1. FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Cabify-Lite Grounded Answers API",
    version="1.0.0",
)


# =========================================================
# 2. REQUEST MODEL
# =========================================================

class AskRequest(BaseModel):
    """
    Request contract for POST /ask.
    """

    question: str = Field(
        min_length=1,
        description=(
            "Natural-language question "
            "for the Cabify-Lite knowledge base."
        ),
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description=(
            "Number of document chunks "
            "to retrieve."
        ),
    )


# =========================================================
# 3. HEALTH ENDPOINT
# =========================================================

@app.get("/health")
def health():
    """
    Lightweight application health check.

    This does NOT call Bedrock or PostgreSQL.
    """

    return {
        "status": "ok"
    }


# =========================================================
# 4. RAG QUESTION ENDPOINT
# =========================================================

@app.post(
    "/ask",
    response_model=RoutedResponse,
)
def ask(
    request: AskRequest,
    response: Response,
) -> RoutedResponse:
    """Trace and route policy, data and hybrid questions."""

    with tracer.start_as_current_span(
        "ask_request",
        kind=SpanKind.SERVER,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:

        span.set_attribute("http.request.method", "POST")
        span.set_attribute("http.route", "/ask")
        span.set_attribute("rag.top_k", request.top_k)

        try:
            result = answer_question_routed(
                question=request.question,
                top_k=request.top_k,
            )

        except ValueError as exc:
            span.set_status(Status(StatusCode.ERROR))
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR))
            raise HTTPException(
                status_code=500,
                detail="Unable to answer the question.",
            ) from exc

        span.set_attribute("router.route", result.route)

        response.headers["X-Trace-ID"] = format(
            span.get_span_context().trace_id,
            "032x",
        )

        return result
