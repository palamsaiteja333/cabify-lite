from langchain_core.runnables import RunnableLambda

from retriever import retrieve

from rag_stage import (
    format_context,
)

from llm_stage import (
    generate_text,
)

from structured_rag import (
    STRUCTURED_SYSTEM_PROMPT,
    build_user_prompt,
    parse_model_output,
    Citation,
    RAGResponse,
)


# =========================================================
# 1. RETRIEVAL STEP
# =========================================================

def retrieve_step(
    state: dict,
) -> dict:
    """
    LCEL Step 1

    Input:
        {
            "question": "...",
            "top_k": 5
        }

    Output:
        same state
        +
        retrieved_chunks
    """

    question = state["question"]

    top_k = state.get(
        "top_k",
        5,
    )

    retrieved_chunks = retrieve(
        question=question,
        top_k=top_k,
    )

    return {
        **state,
        "retrieved_chunks":
            retrieved_chunks,
    }


# =========================================================
# 2. CONTEXT FORMATTING STEP
# =========================================================

def context_step(
    state: dict,
) -> dict:
    """
    LCEL Step 2

    Convert retrieved chunks into
    LLM-readable context.
    """

    context = format_context(
        state["retrieved_chunks"]
    )

    return {
        **state,
        "context": context,
    }


# =========================================================
# 3. PROMPT BUILDING STEP
# =========================================================

def prompt_step(
    state: dict,
) -> dict:
    """
    LCEL Step 3

    Build the dynamic user message containing:
        - retrieved context
        - user question
    """

    user_prompt = build_user_prompt(
        question=state["question"],
        context=state["context"],
    )

    return {
        **state,
        "user_prompt":
            user_prompt,
    }


# =========================================================
# 4. LLM GENERATION STEP
# =========================================================

def llm_step(
    state: dict,
) -> dict:
    """
    LCEL Step 4

    Send:
        system grounding rules
        +
        user prompt

    to Nova through Bedrock.
    """

    raw_output = generate_text(
        prompt=state["user_prompt"],
        system_prompt=
            STRUCTURED_SYSTEM_PROMPT,
    )

    return {
        **state,
        "raw_output":
            raw_output,
    }


# =========================================================
# 5. STRUCTURED OUTPUT STEP
# =========================================================

def structured_output_step(
    state: dict,
) -> RAGResponse:
    """
    LCEL Step 5

    Parse Nova's JSON using Pydantic,
    validate citation IDs,
    and attach trusted metadata.
    """

    model_output = parse_model_output(
        state["raw_output"]
    )

    retrieved_chunks = (
        state["retrieved_chunks"]
    )

    citations = []

    seen = set()


    # -----------------------------------------------------
    # Validate citation IDs
    # -----------------------------------------------------

    for citation_id in (
        model_output.citation_ids
    ):

        # Avoid duplicate citations.
        if citation_id in seen:
            continue

        seen.add(
            citation_id
        )


        # Citation IDs are 1-based:
        #
        # [1] -> retrieved_chunks[0]
        # [2] -> retrieved_chunks[1]
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


        # Get trusted metadata from
        # our retriever result.
        chunk = retrieved_chunks[
            citation_id - 1
        ]


        citations.append(
            Citation(
                citation=
                    citation_id,

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
    # Build final validated response
    # -----------------------------------------------------

    return RAGResponse(
        answer=
            model_output.answer,

        citations=
            citations,

        confidence=
            model_output.confidence,
    )


# =========================================================
# 6. BUILD LCEL CHAIN
# =========================================================

rag_chain = (

    RunnableLambda(
        retrieve_step
    )

    |

    RunnableLambda(
        context_step
    )

    |

    RunnableLambda(
        prompt_step
    )

    |

    RunnableLambda(
        llm_step
    )

    |

    RunnableLambda(
        structured_output_step
    )
)


# =========================================================
# 7. PUBLIC RAG FUNCTION
# =========================================================

def answer_question_lcel(
    question: str,
    top_k: int = 5,
) -> RAGResponse:
    """
    Public interface for the LCEL RAG chain.
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    result = rag_chain.invoke(
        {
            "question":
                question,

            "top_k":
                top_k,
        }
    )

    return result


# =========================================================
# 8. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "How much do I have to pay "
        "if I call off my ride?"
    )

    result = answer_question_lcel(
        question=question,
        top_k=5,
    )

    print()
    print("=" * 70)

    print(
        "LCEL RAG RESPONSE"
    )

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )