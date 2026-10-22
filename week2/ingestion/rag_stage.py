from retriever import retrieve
from llm_stage import generate_text


# =========================================================
# 1. SYSTEM / GROUNDING INSTRUCTIONS
# =========================================================

SYSTEM_PROMPT = """
You are a grounded question-answering assistant for
the internal Cabify-Lite knowledge base.

Follow these rules strictly:

1. Use ONLY facts contained in the supplied context.

2. Never add facts from general knowledge.

3. Never assume a condition that the user did not provide.

4. Carefully distinguish between actors:
   - Rider
   - Driver
   - Cabify-Lite

5. Pay attention to the audience and source of a document.
   For example, instructions in a Driver Handbook directed
   to "you" refer to the Driver, not the Rider.

6. Never confuse:
   - money charged to a Rider
   - money refunded to a Rider
   - money paid to a Driver

7. When multiple retrieved sources discuss the same topic,
   compare them before answering.

8. If an answer depends on conditions that the user has
   not specified, list the documented cases instead of
   choosing one case.

9. When the user asks for an amount, deadline, rule, or
   condition, prefer the source that explicitly states
   that fact.

10. Cite claims using the supplied citation numbers
    such as [1] or [2].

11. Every factual claim must actually be supported by
    its cited context.

12. If the supplied context is insufficient, respond:

    "I don't know based on the provided documents."

13. Do not speculate about what a term "typically" means.

14. Keep the answer concise and directly answer
    the question.
""".strip()


# =========================================================
# 2. FORMAT RETRIEVED CONTEXT
# =========================================================

def format_context(
    retrieved_chunks: list[dict],
) -> str:
    """
    Convert retrieved chunks into context that includes
    both evidence and provenance.
    """

    context_parts = []

    for index, chunk in enumerate(
        retrieved_chunks,
        start=1,
    ):

        context_part = f"""
[{index}]
Source: {chunk['source_file']}
Location: {chunk['section_heading']}

Content:
{chunk['content']}
""".strip()

        context_parts.append(
            context_part
        )

    return "\n\n".join(
        context_parts
    )


# =========================================================
# 3. BUILD USER PROMPT
# =========================================================

def build_user_prompt(
    question: str,
    context: str,
) -> str:
    """
    Keep retrieved evidence and the user's question
    separate from the application's system rules.
    """

    return f"""
RETRIEVED CONTEXT

{context}


USER QUESTION

{question}


Answer the question using the retrieved context.
""".strip()


# =========================================================
# 4. COMPLETE RAG PIPELINE
# =========================================================

def answer_question(
    question: str,
    top_k: int = 5,
) -> dict:
    """
    Baseline RAG pipeline:

        question
          ↓
        retrieval
          ↓
        Top-K chunks
          ↓
        context formatting
          ↓
        system grounding instructions
          +
        user question/context
          ↓
        Nova
          ↓
        answer + sources
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
    # Step 3: Build user message
    # -----------------------------------------------------

    user_prompt = build_user_prompt(
        question=question,
        context=context,
    )


    # -----------------------------------------------------
    # Step 4: Generate grounded answer
    # -----------------------------------------------------

    answer = generate_text(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
    )


    # -----------------------------------------------------
    # Step 5: Return citation metadata
    # -----------------------------------------------------

    sources = []

    for index, chunk in enumerate(
        retrieved_chunks,
        start=1,
    ):

        sources.append(
            {
                "citation": index,

                "source_file":
                    chunk["source_file"],

                "section_heading":
                    chunk["section_heading"],

                "chunk_index":
                    chunk["chunk_index"],

                "cosine_similarity":
                    chunk["cosine_similarity"],
            }
        )

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }


# =========================================================
# 5. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    # question = (
    #     "How much do I have to pay "
    #     "if I call off my ride?"
    # )

    question = (
    "What dental insurance benefits "
    "do Cabify-Lite employees receive?"
)

    result = answer_question(
        question=question,
        top_k=5,
    )

    print()
    print("=" * 70)

    print("QUESTION")
    print()
    print(
        result["question"]
    )

    print()
    print("=" * 70)

    print("ANSWER")
    print()
    print(
        result["answer"]
    )

    print()
    print("=" * 70)

    print("RETRIEVED SOURCES")
    print()

    for source in result["sources"]:

        print(
            f"[{source['citation']}] "
            f"{source['source_file']} | "
            f"{source['section_heading']} | "
            f"similarity="
            f"{source['cosine_similarity']:.4f}"
        )   