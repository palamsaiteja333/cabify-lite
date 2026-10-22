from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from lcel_rag import (
    answer_question_lcel,
)

from structured_rag import (
    RAGResponse,
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
    response_model=RAGResponse,
)
def ask(
    request: AskRequest,
) -> RAGResponse:
    """
    Grounded RAG endpoint.

    Flow:

        HTTP request
            ↓
        validated Pydantic request
            ↓
        LCEL RAG chain
            ↓
        Titan query embedding
            ↓
        pgvector retrieval
            ↓
        Nova 2 Lite generation
            ↓
        Pydantic output validation
            ↓
        structured API response
    """

    try:

        return answer_question_lcel(
            question=request.question,
            top_k=request.top_k,
        )

    except ValueError as exc:

        # Known validation / application error.
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        # Do not expose internal stack traces
        # through the API response.
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to answer the question."
            ),
        ) from exc