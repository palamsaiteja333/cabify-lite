import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from retriever import retrieve
from llm_stage import generate_text
from rag_stage import format_context


# =========================================================
# 1. PYDANTIC MODELS
# =========================================================

class ModelOutput(BaseModel):
    """
    Raw structured output expected directly
    from the LLM.

    We ask the model only for citation numbers.

    Example:
        citation_ids = [2, 3]

    We do NOT ask the model to invent filenames
    or metadata.
    """

    answer: str

    citation_ids: list[int] = Field(
        default_factory=list
    )

    confidence: Literal[
        "high",
        "medium",
        "low",
    ]


class Citation(BaseModel):
    """
    Citation metadata produced by our application
    after validating the model's citation IDs.
    """

    citation: int

    source_file: str

    section_heading: str | None

    chunk_index: int


class RAGResponse(BaseModel):
    """
    Final structured response returned by
    our RAG application.
    """

    answer: str

    citations: list[Citation]

    confidence: Literal[
        "high",
        "medium",
        "low",
    ]


# =========================================================
# 2. SYSTEM PROMPT
# =========================================================

STRUCTURED_SYSTEM_PROMPT = """
You are a grounded question-answering assistant for
the internal Cabify-Lite knowledge base.

Use ONLY the supplied retrieved context.

Do not use outside knowledge.

Do not invent missing information.

Carefully distinguish between:
- Rider
- Driver
- Cabify-Lite

Do not confuse:
- money charged to a Rider
- money refunded to a Rider
- money paid to a Driver

Never assume conditions that the user did not specify.

If the answer depends on different documented cases,
explain the relevant cases.

If multiple sources discuss the topic, compare them
before answering.

Every claim must be supported by the retrieved context.

If the context is insufficient, the answer MUST be:

"I don't know based on the provided documents."

When evidence is insufficient:
- citation_ids must be []
- confidence must be "low"


CONFIDENCE RULES

"high":
The answer is explicitly and directly supported by
retrieved evidence.

"medium":
The answer is supported, but requires combining
multiple pieces of evidence or explaining conditions.

"low":
The retrieved context is insufficient to answer.


OUTPUT FORMAT

Return ONLY valid JSON.

Do not use Markdown code fences.

Use exactly this structure:

{
  "answer": "your answer",
  "citation_ids": [1, 2],
  "confidence": "high"
}

citation_ids must contain only citation numbers that
actually support the answer.
""".strip()


# =========================================================
# 3. BUILD USER PROMPT
# =========================================================

def build_user_prompt(
    question: str,
    context: str,
) -> str:
    """
    Dynamic information goes into the user message:
        - retrieved context
        - user's question
    """

    return f"""
RETRIEVED CONTEXT

{context}


USER QUESTION

{question}
""".strip()


# =========================================================
# 4. CLEAN / PARSE MODEL JSON
# =========================================================

def parse_model_output(
    raw_output: str,
) -> ModelOutput:
    """
    Parse Nova's JSON response and validate it
    using Pydantic.

    The small regex cleanup handles the case where
    a model accidentally wraps JSON in ```json fences.
    """

    cleaned = raw_output.strip()

    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    data = json.loads(
        cleaned
    )

    return ModelOutput.model_validate(
        data
    )


# =========================================================
# 5. COMPLETE STRUCTURED RAG PIPELINE
# =========================================================

def answer_question_structured(
    question: str,
    top_k: int = 5,
) -> RAGResponse:
    """
    Complete structured RAG flow:

        question
          ↓
        retrieve Top-K
          ↓
        format context
          ↓
        Nova
          ↓
        JSON
          ↓
        Pydantic validation
          ↓
        validate citation IDs
          ↓
        attach trusted source metadata
          ↓
        RAGResponse
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )


    # -----------------------------------------------------
    # Step 1: Retrieve evidence
    # -----------------------------------------------------

    retrieved_chunks = retrieve(
        question=question,
        top_k=top_k,
    )


    # -----------------------------------------------------
    # Step 2: Format context
    # -----------------------------------------------------

    context = format_context(
        retrieved_chunks
    )


    # -----------------------------------------------------
    # Step 3: Build dynamic user prompt
    # -----------------------------------------------------

    user_prompt = build_user_prompt(
        question=question,
        context=context,
    )


    # -----------------------------------------------------
    # Step 4: Generate structured JSON with Nova
    # -----------------------------------------------------

    raw_output = generate_text(
        prompt=user_prompt,
        system_prompt=
            STRUCTURED_SYSTEM_PROMPT,
    )


    # -----------------------------------------------------
    # Step 5: Validate the JSON with Pydantic
    # -----------------------------------------------------

    model_output = parse_model_output(
        raw_output
    )


    # -----------------------------------------------------
    # Step 6: Validate citations
    # -----------------------------------------------------

    citations = []

    seen = set()

    for citation_id in (
        model_output.citation_ids
    ):

        # Ignore duplicate citations.
        if citation_id in seen:
            continue

        seen.add(
            citation_id
        )

        # Citation numbers are 1-based:
        #
        # [1] = retrieved_chunks[0]
        # [2] = retrieved_chunks[1]
        #
        if (
            citation_id < 1
            or citation_id
            > len(retrieved_chunks)
        ):
            raise ValueError(
                "Model returned invalid "
                f"citation ID: "
                f"{citation_id}"
            )

        chunk = retrieved_chunks[
            citation_id - 1
        ]

        citations.append(
            Citation(
                citation=citation_id,

                source_file=
                    chunk["source_file"],

                section_heading=
                    chunk[
                        "section_heading"
                    ],

                chunk_index=
                    chunk["chunk_index"],
            )
        )


    # -----------------------------------------------------
    # Step 7: Return trusted structured result
    # -----------------------------------------------------

    return RAGResponse(
        answer=model_output.answer,

        citations=citations,

        confidence=
            model_output.confidence,
    )


# =========================================================
# 6. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "How much do I have to pay "
        "if I call off my ride?"
    )

    result = answer_question_structured(
        question=question,
        top_k=5,
    )

    print()
    print("=" * 70)

    print("STRUCTURED RAG RESPONSE")

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )