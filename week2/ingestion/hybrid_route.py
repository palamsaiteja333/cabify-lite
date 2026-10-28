from pydantic import BaseModel

from hybrid_decomposer import (
    decompose_hybrid_question,
)

from lcel_rag import (
    answer_question_lcel,
)

from sql_route import (
    answer_data_question,
)

from llm_stage import (
    generate_text,
)


# =========================================================
# 1. RESPONSE MODEL
# =========================================================

class HybridResponse(BaseModel):
    """
    Final response for questions requiring both:

    - document / policy knowledge
    - structured database data
    """

    answer: str

    policy_question: str

    data_question: str

    policy_answer: str

    data_answer: str

    citations: list[dict]

    sql: str


# =========================================================
# 2. FINAL HYBRID SYNTHESIS PROMPT
# =========================================================

HYBRID_SYSTEM_PROMPT = """
You are a grounded answer synthesis assistant.

You will receive:

1. The original user question.
2. A policy answer produced from retrieved documents.
3. A structured-data answer produced from PostgreSQL.

Use ONLY the supplied policy and structured-data results.

Do not use outside knowledge.

Do not invent facts or numbers.

Do not change the meaning of the policy answer.

Do not change the meaning of the database result.

Combine the two results into one concise and clear
response to the original question.

If the policy answer contains important conditions or
exceptions, preserve them.

If the data answer contains a number, reproduce the
number exactly.

Prefer information directly relevant to the user's
original question.

Do not add unrelated policy details merely because they
appear in the policy answer.


POLICY VS DATA COMPARISON RULES

When the original question asks whether actual data follows,
matches, complies with, or agrees with a policy:

1. Explicitly compare the policy requirement with the
   observed structured-data result.

2. Distinguish absolute policy requirements from targets,
   averages, trends, or recommendations.

3. Treat words and meanings such as:

   - every
   - all
   - no
   - none
   - never
   - must
   - always
   - cannot

   as absolute requirements unless the supplied policy
   answer itself gives an exception.

4. If an absolute policy requirement is violated by even
   one observed record, do NOT describe the data as fully
   aligned with or compliant with the policy.

5. A majority of records following an absolute policy does
   not mean the observed data complies with that policy.

6. When the policy and data disagree, clearly state:

   - what the policy requires
   - what the observed data shows
   - that the two are inconsistent

7. Do not hide or soften a contradiction merely because
   most records comply.

8. Do not invent a reason for the discrepancy unless that
   reason is explicitly present in the supplied results.

9. If the data fully satisfies the supplied policy
   requirement, you may state that the observed data aligns
   with the policy.

10. If the available results are insufficient to determine
    whether the policy is being followed, say that clearly
    instead of guessing.


Do not mention internal implementation details such as:
- RAG
- vector search
- SQL generation
- PostgreSQL

Answer as if you are directly responding to the user.
""".strip()


# =========================================================
# 3. HYBRID QUESTION FUNCTION
# =========================================================

def answer_hybrid_question(
    question: str,
) -> HybridResponse:
    """
    Complete hybrid flow:

        original question
              ↓
        decompose question
              ↓
        ┌──────────────┬──────────────┐
        │              │              │
        policy         data
        question       question
        │              │
        RAG            SQL
        │              │
        └───────┬──────┘
                ↓
            synthesis
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )


    # -----------------------------------------------------
    # Step 1: Decompose original hybrid question
    # -----------------------------------------------------

    decomposition = (
        decompose_hybrid_question(
            question
        )
    )

    policy_question = (
        decomposition.policy_question
    )

    data_question = (
        decomposition.data_question
    )


    # -----------------------------------------------------
    # Step 2: Answer policy sub-question using RAG
    # -----------------------------------------------------

    policy_result = answer_question_lcel(
        question=policy_question,
        top_k=5,
    )


    # -----------------------------------------------------
    # Step 3: Answer data sub-question using SQL
    # -----------------------------------------------------

    data_result = answer_data_question(
        question=data_question,
    )


    # -----------------------------------------------------
    # Step 4: Convert trusted citations to dictionaries
    # -----------------------------------------------------

    citation_dicts = [
        citation.model_dump()
        for citation
        in policy_result.citations
    ]


    # -----------------------------------------------------
    # Step 5: Build final synthesis prompt
    # -----------------------------------------------------

    prompt = f"""
ORIGINAL USER QUESTION

{question}


POLICY SUB-QUESTION

{policy_question}


POLICY ANSWER

{policy_result.answer}


DATA SUB-QUESTION

{data_question}


STRUCTURED DATA ANSWER

{data_result.answer}
""".strip()


    # -----------------------------------------------------
    # Step 6: Synthesize final grounded answer
    # -----------------------------------------------------

    final_answer = generate_text(
        prompt=prompt,
        system_prompt=
            HYBRID_SYSTEM_PROMPT,
    ).strip()


    # -----------------------------------------------------
    # Step 7: Return structured hybrid response
    # -----------------------------------------------------

    return HybridResponse(
        answer=final_answer,

        policy_question=
            policy_question,

        data_question=
            data_question,

        policy_answer=
            policy_result.answer,

        data_answer=
            data_result.answer,

        citations=
            citation_dicts,

        sql=
            data_result.sql,
    )


# =========================================================
# 4. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "What is the cancellation policy "
        "and how many rides were cancelled "
        "in September?"
    )

    result = answer_hybrid_question(
        question
    )

    print()
    print("=" * 70)

    print(
        "HYBRID ROUTE RESPONSE"
    )

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )