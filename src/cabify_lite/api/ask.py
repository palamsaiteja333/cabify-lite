import logging
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from opentelemetry.trace import (
    SpanKind,
    Status,
    StatusCode,
)

from cabify_lite.ai.routing.chain import (
    RoutedResponse,
    answer_question_routed,
)
from cabify_lite.observability.tracing import get_tracer


router = APIRouter(tags=["AI"])

tracer = get_tracer("cabify_lite.api.ask")
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        description="Natural-language question.",
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


@router.post(
    "/ask",
    response_model=RoutedResponse,
)
def ask(
    request: AskRequest,
    response: Response,
) -> RoutedResponse:

    # FastAPI already creates the HTTP server span.
    # This is the nested AI operation span.
    with tracer.start_as_current_span(
        "ask_request",
        kind=SpanKind.INTERNAL,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:

        span.set_attribute("http.route", "/ask")
        span.set_attribute("rag.top_k", request.top_k)

        try:
            result = answer_question_routed(
                question=request.question,
                top_k=request.top_k,
            )

        except ValueError as exc:
            span.set_status(Status(StatusCode.ERROR))
            logger.exception("AI pipeline failed")
            raise HTTPException(
                status_code=500,
                detail="Unable to answer the question.",
                headers={"X-Trace-ID": format(span.get_span_context().trace_id, "032x")},
            ) from exc

        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR))
            logger.exception("AI pipeline failed")
            raise HTTPException(
                status_code=500,
                detail="Unable to answer the question.",
                headers={"X-Trace-ID": format(span.get_span_context().trace_id, "032x")},
            ) from exc

        span.set_attribute(
            "router.route",
            result.route,
        )

        response.headers["X-Trace-ID"] = format(
            span.get_span_context().trace_id,
            "032x",
        )

        return result
