import re

from pydantic import BaseModel

from llm_stage import generate_text


# =========================================================
# 1. STRUCTURED DECOMPOSITION MODEL
# =========================================================

class HybridDecomposition(BaseModel):
    """
    A hybrid question is split into two independent
    questions:

    1. policy_question
       -> answered using document RAG

    2. data_question
       -> answered using structured SQL
    """

    policy_question: str

    data_question: str


# =========================================================
# 2. DECOMPOSITION PROMPT
# =========================================================

DECOMPOSITION_SYSTEM_PROMPT = """
You decompose hybrid Cabify-Lite questions.

A hybrid question contains BOTH:

1. A policy/document question
2. A structured-data question


Your job is to rewrite the original question into:

- policy_question
- data_question


The policy_question should contain ONLY the part that
needs information from documents, policies, rules,
procedures, terms, pricing rules, refunds, cancellations,
or driver/rider guidance.

The data_question should contain ONLY the part that
requires database records, counts, totals, averages,
dates, trends, rides, refunds, riders, or drivers.


Do not answer the questions.

Do not add information that was not in the user's
original question.

Preserve important details such as:
- month
- year
- ride status
- rider / driver distinction
- requested metric


EXAMPLE

Original question:

"What is the cancellation policy and how many rides
were cancelled in September?"


Return:

{
  "policy_question": "What is the cancellation policy?",
  "data_question": "How many rides were cancelled in September?"
}


Return ONLY valid JSON.

Do not use Markdown code fences.

Use exactly this structure:

{
  "policy_question": "...",
  "data_question": "..."
}
""".strip()


# =========================================================
# 3. CLEAN MODEL OUTPUT
# =========================================================

def clean_json_output(
    raw_output: str,
) -> str:
    """
    Remove accidental Markdown fences around JSON.
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
# 4. DECOMPOSE HYBRID QUESTION
# =========================================================

def decompose_hybrid_question(
    question: str,
) -> HybridDecomposition:
    """
    Split one hybrid question into:

        policy_question
        data_question
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    prompt = f"""
ORIGINAL USER QUESTION

{question}
""".strip()

    raw_output = generate_text(
        prompt=prompt,
        system_prompt=
            DECOMPOSITION_SYSTEM_PROMPT,
    )

    cleaned_output = clean_json_output(
        raw_output
    )

    result = (
        HybridDecomposition
        .model_validate_json(
            cleaned_output
        )
    )


    # -----------------------------------------------------
    # Defensive validation
    # -----------------------------------------------------

    result.policy_question = (
        result.policy_question.strip()
    )

    result.data_question = (
        result.data_question.strip()
    )

    if not result.policy_question:
        raise ValueError(
            "Decomposer returned an empty "
            "policy question."
        )

    if not result.data_question:
        raise ValueError(
            "Decomposer returned an empty "
            "data question."
        )

    return result


# =========================================================
# 5. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "What is the cancellation policy "
        "and how many rides were cancelled "
        "in September?"
    )

    result = decompose_hybrid_question(
        question
    )

    print()
    print("=" * 70)

    print(
        "HYBRID DECOMPOSITION"
    )

    print()

    print(
        result.model_dump_json(
            indent=2
        )
    )