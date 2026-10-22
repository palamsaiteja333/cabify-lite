import re
from typing import Literal

from pydantic import BaseModel

from llm_stage import generate_text


# =========================================================
# 1. STRUCTURED ROUTE MODEL
# =========================================================

class RouteDecision(BaseModel):
    """
    Structured output returned by the routing classifier.

    The router is allowed to choose exactly one route:

        policy
        data
        hybrid
    """

    route: Literal[
        "policy",
        "data",
        "hybrid",
    ]

    reason: str


# =========================================================
# 2. CLASSIFIER SYSTEM PROMPT
# =========================================================

CLASSIFIER_SYSTEM_PROMPT = """
You are a routing classifier for Cabify-Lite.

Your job is to decide which data source should answer
the user's question.

Classify every question into exactly ONE of these routes:

1. policy

Use "policy" when the question asks about information
contained in unstructured documents.

Examples include:
- policies
- rules
- procedures
- terms and conditions
- cancellation rules
- refund rules
- pricing rules
- driver guidance
- rider guidance
- support documentation


2. data

Use "data" when the question requires structured
database information.

Examples include:
- counts
- totals
- averages
- ride records
- rider records
- driver records
- refund records
- dates
- trends
- aggregations
- database statistics


3. hybrid

Use "hybrid" when the question requires BOTH:

- information from policy/documents

AND

- information from structured database data


EXAMPLES

Question:
"What is the cancellation policy?"

Answer:
{
  "route": "policy",
  "reason": "The question asks about documented cancellation rules."
}


Question:
"How many rides were cancelled in September?"

Answer:
{
  "route": "data",
  "reason": "The question requires counting structured ride records."
}


Question:
"What is the cancellation policy and how many rides
were cancelled in September?"

Answer:
{
  "route": "hybrid",
  "reason": "The question requires both policy information and structured ride data."
}


IMPORTANT OUTPUT RULES

Return ONLY valid JSON.

Do not include explanations outside the JSON.

Do not use Markdown code fences.

Use exactly this structure:

{
  "route": "policy",
  "reason": "brief explanation"
}
""".strip()


# =========================================================
# 3. CLEAN MODEL OUTPUT
# =========================================================

def clean_json_output(
    raw_output: str,
) -> str:
    """
    Models sometimes wrap JSON in Markdown fences even
    when explicitly instructed not to.

    Example:

        ```json
        {
          "route": "policy",
          "reason": "..."
        }
        ```

    This function removes those fences before sending
    the result to Pydantic.
    """

    cleaned = raw_output.strip()

    # Remove opening ```json or ```JSON fence.
    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Also handle a generic opening ``` fence.
    cleaned = re.sub(
        r"^```\s*",
        "",
        cleaned,
    )

    # Remove closing ``` fence.
    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    return cleaned.strip()


# =========================================================
# 4. CLASSIFY QUESTION
# =========================================================

def classify_question(
    question: str,
) -> RouteDecision:
    """
    Classify a user question into:

        policy
        data
        hybrid

    Flow:

        question
          ↓
        Nova 2 Lite
          ↓
        JSON response
          ↓
        clean predictable formatting noise
          ↓
        Pydantic validation
          ↓
        RouteDecision
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    # -----------------------------------------------------
    # Dynamic user prompt
    # -----------------------------------------------------

    prompt = f"""
USER QUESTION

{question}
""".strip()


    # -----------------------------------------------------
    # Ask Nova to classify the question
    # -----------------------------------------------------

    raw_output = generate_text(
        prompt=prompt,
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
    )


    # -----------------------------------------------------
    # Clean accidental Markdown code fences
    # -----------------------------------------------------

    cleaned_output = clean_json_output(
        raw_output
    )


    # -----------------------------------------------------
    # Validate model output using Pydantic
    # -----------------------------------------------------

    return RouteDecision.model_validate_json(
        cleaned_output
    )


# =========================================================
# 5. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    questions = [
        "What is the cancellation policy?",

        (
            "How many rides were "
            "cancelled in September?"
        ),

        (
            "What is the cancellation policy "
            "and how many rides were cancelled "
            "in September?"
        ),
    ]


    for question in questions:

        result = classify_question(
            question
        )

        print()
        print("=" * 70)

        print(
            f"QUESTION: {question}"
        )

        print(
            f"ROUTE: {result.route}"
        )

        print(
            f"REASON: {result.reason}"
        )