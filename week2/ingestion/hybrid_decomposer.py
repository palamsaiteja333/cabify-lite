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

Do not add unrelated information.

Preserve important details such as:
- month
- year
- ride status
- rider / driver distinction
- requested metric
- thresholds
- deadlines
- comparison conditions


COMPARISON / VALIDATION QUESTIONS

Some hybrid questions ask whether actual business data
matches or complies with a documented policy.

Examples include phrases such as:

- "Is that what actually happens?"
- "Is that true?"
- "Does the data match the policy?"
- "Are we following the policy?"
- "Does this happen in practice?"
- "Is the document accurate?"

For these questions, decomposition MUST preserve enough
information for the data branch to test BOTH compliance
and violations.

Do NOT create a data question that looks only for records
that satisfy the policy.

For example:

Original:

"Our refunds policy says every refund is issued within
7 days of the ride. Is that what actually happens?"

Incorrect data question:

"How many refunds are issued within 7 days of the ride?"

This is insufficient because it only measures compliant
records and cannot detect violations.

Better data question:

"How many refunds were issued within 7 days of the ride,
and how many were issued more than 7 days after the ride?"

or:

"Are there any refunds issued more than 7 days after the
ride, and how many?"

The data question must give the downstream synthesis step
enough evidence to determine whether the policy is actually
being followed.


ABSOLUTE POLICY CLAIMS

If the original question contains an absolute claim such as:

- every
- all
- no
- none
- never
- always
- must
- cannot

the data question should explicitly test for exceptions or
violations of that absolute claim.

Example:

Original:

"The FAQ says drivers cancel more often than riders.
Is that true?"

Return a data question that compares BOTH:

- driver cancellations
- rider cancellations

Do not ask only for driver cancellations.


STANDARD EXAMPLE

Original question:

"What is the cancellation policy and how many rides
were cancelled in September?"

Return:

{
  "policy_question": "What is the cancellation policy?",
  "data_question": "How many rides were cancelled in September?"
}


COMPARISON EXAMPLE

Original question:

"Our refunds policy says every refund is issued within
7 days of the ride. Is that what actually happens?"

Return:

{
  "policy_question": "What does the refunds policy require about how long after a ride a refund may be issued?",
  "data_question": "How many refunds were issued within 7 days of the ride, and how many were issued more than 7 days after the ride?"
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