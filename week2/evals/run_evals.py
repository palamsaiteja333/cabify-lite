import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


# =========================================================
# Project paths
# =========================================================

# Current file:
# cabify-lite/week2/evals/run_evals.py
#
# parents[0] -> evals
# parents[1] -> week2
# parents[2] -> cabify-lite
REPO_ROOT = Path(__file__).resolve().parents[2]

INGESTION_DIR = REPO_ROOT / "week2" / "ingestion"
EVAL_DIR = REPO_ROOT / "week2" / "evals"

EVAL_FILE = EVAL_DIR / "questions.yaml"


# Allow the evaluator to reuse the REAL Week 2 application code.
sys.path.insert(0, str(INGESTION_DIR))


# =========================================================
# Import real Week 2 application functions
# =========================================================

from retriever import retrieve
from routed_chain import answer_question_routed
from hybrid_decomposer import decompose_hybrid_question
from llm_stage import generate_text


# =========================================================
# Frozen baseline configuration
# =========================================================

DEFAULT_TOP_K = 5


# These values describe our current baseline.
#
# They do NOT configure the actual application here.
# They are written into the results so we know exactly
# what configuration produced the score.
BASELINE_CONFIG = {
    "chunk_size_chars": 1200,
    "chunk_overlap_chars": 150,

    "embedding_model":
        "amazon.titan-embed-text-v2:0",

    "embedding_dimensions": 1024,

    "chat_model":
        "us.amazon.nova-2-lite-v1:0",

    "vector_store":
        "PostgreSQL + pgvector",

    "distance_metric":
        "cosine",
}


# =========================================================
# LLM judge
# =========================================================

class JudgeResult(BaseModel):
    correct: bool
    reason: str


JUDGE_SYSTEM_PROMPT = """
You are a strict evaluator for a Cabify-Lite
question-answering system.

Your job is to grade the SYSTEM ANSWER against:

- EXPECTED FACTS
- EXPECTED SQL RESULT
- EVALUATION NOTES

Rules:

1. Judge the system answer only.
   Do not answer the original question using your own knowledge.

2. Semantic equivalence is allowed.
   Exact wording is not required.

3. Use the NOTES to understand whether expected phrases
   are all required or whether some are acceptable alternatives.

4. If an expected SQL result is supplied, the answer must
   be consistent with that result.

5. For hybrid questions, the answer must correctly combine
   policy evidence and database facts.

6. If the notes describe a contradiction between policy
   and real data, the answer must surface that contradiction.
   It must not silently choose one side.

7. Do not mark an answer correct simply because it contains
   expected keywords if the overall meaning is wrong.

8. Unsupported confident claims should cause failure.

Return JSON ONLY.

Valid format:

{"correct": true, "reason": "short explanation"}

or

{"correct": false, "reason": "short explanation"}
""".strip()


# =========================================================
# Load questions
# =========================================================

def load_questions() -> list[dict]:
    """
    Load Gourav's fixed evaluation set.

    Expected answers remain inside the evaluator.
    They are never sent into the production question-answering
    system before it produces its answer.
    """

    with open(
        EVAL_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        data = yaml.safe_load(file)

    questions = data.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "questions.yaml must contain "
            "a top-level 'questions' list."
        )

    return questions


# =========================================================
# Expected route
# =========================================================

def expected_route(
    question_type: str,
) -> str | None:
    """
    Convert eval question type into expected router output.

    Unanswerable questions are not scored for route choice.
    Their important metric is whether the system abstains.
    """

    mapping = {
        "policy": "policy",
        "data": "data",
        "hybrid": "hybrid",
        "unanswerable": None,
    }

    if question_type not in mapping:
        raise ValueError(
            f"Unknown question type: {question_type}"
        )

    return mapping[question_type]


# =========================================================
# Generic object helpers
# =========================================================

def to_plain(
    value: Any,
) -> Any:
    """
    Convert Pydantic models and nested values into
    ordinary Python dictionaries/lists.
    """

    if hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump()

    if isinstance(
        value,
        dict,
    ):
        return {
            key: to_plain(val)
            for key, val in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            to_plain(item)
            for item in value
        ]

    if isinstance(
        value,
        tuple,
    ):
        return [
            to_plain(item)
            for item in value
        ]

    return value


def extract_route(
    routed_response: Any,
) -> str | None:
    """
    Pull route from RoutedResponse.
    """

    if routed_response is None:
        return None

    route = getattr(
        routed_response,
        "route",
        None,
    )

    if (
        route is None
        and isinstance(
            routed_response,
            dict,
        )
    ):
        route = routed_response.get(
            "route"
        )

    if route is None:
        return None

    return str(route)


def extract_result(
    routed_response: Any,
) -> Any:
    """
    Pull the route-specific result from RoutedResponse.
    """

    if routed_response is None:
        return None

    result = getattr(
        routed_response,
        "result",
        None,
    )

    if (
        result is None
        and isinstance(
            routed_response,
            dict,
        )
    ):
        result = routed_response.get(
            "result"
        )

    return result


def extract_answer(
    value: Any,
) -> str:
    """
    Extract the final user-facing answer.

    Different branches may return slightly different
    objects, so this handles:
    - strings
    - Pydantic models
    - dictionaries
    """

    if value is None:
        return ""

    if isinstance(
        value,
        str,
    ):
        return value.strip()

    plain = to_plain(
        value
    )

    if isinstance(
        plain,
        str,
    ):
        return plain.strip()

    if isinstance(
        plain,
        dict,
    ):

        # Most likely answer fields.
        for key in (
            "answer",
            "final_answer",
            "response",
            "summary",
        ):
            candidate = plain.get(
                key
            )

            if (
                isinstance(
                    candidate,
                    str,
                )
                and candidate.strip()
            ):
                return candidate.strip()

        # Try nested structures.
        for key in (
            "result",
            "output",
            "data",
        ):
            if key in plain:

                nested = extract_answer(
                    plain[key]
                )

                if nested:
                    return nested

        # Debugging fallback.
        return json.dumps(
            plain,
            ensure_ascii=False,
            default=str,
        )

    return str(
        plain
    ).strip()


def extract_confidence(
    value: Any,
) -> str | None:
    """
    Extract RAG confidence when present.
    """

    plain = to_plain(
        value
    )

    if isinstance(
        plain,
        dict,
    ):

        confidence = plain.get(
            "confidence"
        )

        if confidence is not None:
            return str(
                confidence
            ).lower()

        for key in (
            "result",
            "output",
            "data",
        ):

            if key in plain:

                nested = extract_confidence(
                    plain[key]
                )

                if nested is not None:
                    return nested

    return None


# =========================================================
# JSON parsing for judge
# =========================================================

def clean_json_object(
    raw_text: str,
) -> dict:
    """
    Parse model JSON even when the model wraps it in
    ```json fences.
    """

    text = raw_text.strip()

    if text.startswith(
        "```"
    ):

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    start = text.find(
        "{"
    )

    end = text.rfind(
        "}"
    )

    if (
        start == -1
        or end == -1
        or end < start
    ):
        raise ValueError(
            "No JSON object found in "
            f"judge output: {raw_text!r}"
        )

    return json.loads(
        text[
            start:
            end + 1
        ]
    )


def safe_float(
    value: Any,
) -> float | None:

    try:
        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


# =========================================================
# Hybrid retrieval helper
# =========================================================

def get_hybrid_policy_question(
    question: str,
) -> str:
    """
    Hybrid questions contain policy + data.

    Our real hybrid architecture decomposes them first.

    For retrieval evaluation, evaluate the POLICY sub-question,
    because that matches the actual RAG path.
    """

    decomposition = (
        decompose_hybrid_question(
            question
        )
    )

    policy_question = getattr(
        decomposition,
        "policy_question",
        None,
    )

    if policy_question is None:

        plain = to_plain(
            decomposition
        )

        if isinstance(
            plain,
            dict,
        ):
            policy_question = plain.get(
                "policy_question"
            )

    if not policy_question:
        raise ValueError(
            "Hybrid decomposition did not "
            "return policy_question."
        )

    return str(
        policy_question
    )


# =========================================================
# Retrieval evaluation
# =========================================================

def evaluate_retrieval(
    item: dict,
    top_k: int,
) -> dict:
    """
    Measure whether the expected document source appears
    anywhere inside Top-K.

    Data questions have no expected document source, so
    retrieval scoring is not applicable to them.
    """

    expected_source = item.get(
        "expected_source"
    )

    # Data-only and unanswerable questions do not have
    # a document source to score.
    if not expected_source:

        return {
            "applicable": False,

            "retrieval_question":
                None,

            "hit":
                None,

            "expected_source_rank":
                None,

            "retrieved_sources":
                [],

            "retrieved_chunks":
                [],
        }

    question = item[
        "question"
    ]

    if item[
        "type"
    ] == "hybrid":

        retrieval_question = (
            get_hybrid_policy_question(
                question
            )
        )

    else:
        retrieval_question = (
            question
        )

    # REAL production retriever.
    chunks = retrieve(
        question=retrieval_question,
        top_k=top_k,
    )

    retrieved_sources = []

    retrieved_chunks = []

    for rank, chunk in enumerate(
        chunks,
        start=1,
    ):

        plain_chunk = to_plain(
            chunk
        )

        if not isinstance(
            plain_chunk,
            dict,
        ):
            plain_chunk = {
                "raw":
                    str(
                        plain_chunk
                    )
            }

        source_file = (
            plain_chunk.get(
                "source_file"
            )
        )

        if source_file:

            retrieved_sources.append(
                str(
                    source_file
                )
            )

        retrieved_chunks.append(
            {
                "rank":
                    rank,

                "chunk_id":
                    plain_chunk.get(
                        "chunk_id"
                    ),

                "source_file":
                    source_file,

                "section_heading":
                    plain_chunk.get(
                        "section_heading"
                    ),

                "chunk_index":
                    plain_chunk.get(
                        "chunk_index"
                    ),

                "cosine_distance":
                    safe_float(
                        plain_chunk.get(
                            "cosine_distance"
                        )
                    ),

                "cosine_similarity":
                    safe_float(
                        plain_chunk.get(
                            "cosine_similarity"
                        )
                    ),
            }
        )

    # Find the first rank where the expected source appeared.
    expected_source_rank = next(
        (
            index
            for index, source
            in enumerate(
                retrieved_sources,
                start=1,
            )
            if source
            == expected_source
        ),
        None,
    )

    return {
        "applicable":
            True,

        "retrieval_question":
            retrieval_question,

        "hit":
            expected_source_rank
            is not None,

        "expected_source_rank":
            expected_source_rank,

        "retrieved_sources":
            retrieved_sources,

        "retrieved_chunks":
            retrieved_chunks,
    }


# =========================================================
# LLM answer judge
# =========================================================

def build_judge_prompt(
    item: dict,
    system_answer: str,
) -> str:
    """
    Build grading input.

    Important:
    Expected values are sent to the JUDGE only,
    never to the application before it answers.
    """

    payload = {
        "question_id":
            item.get(
                "id"
            ),

        "question_type":
            item.get(
                "type"
            ),

        "user_question":
            item.get(
                "question"
            ),

        "system_answer":
            system_answer,

        "expected_answer_contains":
            item.get(
                "expected_answer_contains",
                [],
            ),

        "expected_sql_result":
            item.get(
                "expected_sql_result"
            ),

        "notes":
            item.get(
                "notes",
                "",
            ),
    }

    return (
        "Evaluate this case:\n\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n\nReturn JSON only."
    )


def judge_answer(
    item: dict,
    system_answer: str,
) -> JudgeResult:
    """
    Semantic answer grading using Nova.

    One retry is allowed only when the judge itself returns
    malformed JSON.
    """

    prompt = build_judge_prompt(
        item=item,
        system_answer=system_answer,
    )

    raw = generate_text(
        prompt=prompt,
        system_prompt=JUDGE_SYSTEM_PROMPT,
    )

    try:

        payload = clean_json_object(
            raw
        )

        return JudgeResult.model_validate(
            payload
        )

    except Exception:

        # One formatting retry.
        #
        # This retry is for our evaluation infrastructure,
        # not for the production answer.
        retry_prompt = (
            prompt
            + "\n\nYour previous response "
            "was not valid JSON."
            + "\nReturn ONLY:"
            + '\n{"correct": true, '
              '"reason": "short explanation"}'
            + "\nor:"
            + '\n{"correct": false, '
              '"reason": "short explanation"}'
        )

        retry_raw = generate_text(
            prompt=retry_prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
        )

        payload = clean_json_object(
            retry_raw
        )

        return JudgeResult.model_validate(
            payload
        )


# =========================================================
# Unanswerable / hallucination test
# =========================================================

ABSTENTION_PHRASES = (
    "i don't know",
    "i do not know",
    "not covered",
    "not provided",
    "not available in the provided",
    "not in the provided",
    "cannot determine",
    "can't determine",
    "cannot answer",
    "can't answer",
    "insufficient information",
    "no information in",
    "not found in the",
)


def evaluate_abstention(
    system_answer: str,
    confidence: str | None,
) -> bool:
    """
    Did the system clearly refuse to invent an answer?
    """

    normalized = (
        system_answer.lower()
    )

    explicit_abstention = any(
        phrase in normalized
        for phrase
        in ABSTENTION_PHRASES
    )

    uncertainty_language = any(
        phrase in normalized
        for phrase
        in (
            "unclear",
            "unknown",
            "unable to",
            "not enough",
            "insufficient",
        )
    )

    # Low confidence alone is NOT enough.
    #
    # A hallucinated policy with "low confidence" is still
    # a hallucination.
    low_confidence_abstention = (
        confidence == "low"
        and uncertainty_language
    )

    return (
        explicit_abstention
        or low_confidence_abstention
    )


# =========================================================
# Evaluate one question
# =========================================================

def evaluate_question(
    item: dict,
    top_k: int,
) -> dict:
    """
    Run ONE question through the complete evaluator.

    We score independently:

    1. routing
    2. retrieval
    3. answer correctness
    4. abstention where applicable
    """

    started = (
        time.perf_counter()
    )

    errors = []

    expected = expected_route(
        item[
            "type"
        ]
    )

    actual_route = None

    system_answer = ""

    confidence = None


    # -----------------------------------------------------
    # 1. Run real application
    # -----------------------------------------------------

    try:

        routed_response = (
            answer_question_routed(
                question=item[
                    "question"
                ],
                top_k=top_k,
            )
        )

        actual_route = (
            extract_route(
                routed_response
            )
        )

        route_result = (
            extract_result(
                routed_response
            )
        )

        system_answer = (
            extract_answer(
                route_result
            )
        )

        confidence = (
            extract_confidence(
                route_result
            )
        )

    except Exception as exc:

        errors.append(
            "system_error: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )


    # -----------------------------------------------------
    # 2. Route correctness
    # -----------------------------------------------------

    if expected is None:

        # Unanswerable route itself is not scored.
        route_correct = None

    else:

        route_correct = (
            actual_route
            == expected
        )


    # -----------------------------------------------------
    # 3. Retrieval correctness
    # -----------------------------------------------------

    try:

        retrieval = (
            evaluate_retrieval(
                item=item,
                top_k=top_k,
            )
        )

    except Exception as exc:

        errors.append(
            "retrieval_error: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        retrieval = {
            "applicable":
                bool(
                    item.get(
                        "expected_source"
                    )
                ),

            "retrieval_question":
                None,

            "hit":
                (
                    False
                    if item.get(
                        "expected_source"
                    )
                    else None
                ),

            "expected_source_rank":
                None,

            "retrieved_sources":
                [],

            "retrieved_chunks":
                [],
        }


    # -----------------------------------------------------
    # 4. Answer correctness / abstention
    # -----------------------------------------------------

    judge_reason = None

    abstained = None


    if item[
        "type"
    ] == "unanswerable":

        if system_answer:

            abstained = (
                evaluate_abstention(
                    system_answer=
                        system_answer,

                    confidence=
                        confidence,
                )
            )

        else:

            # A program crash is NOT a successful refusal.
            abstained = False


        answer_correct = (
            abstained
        )


        if abstained:

            judge_reason = (
                "System abstained on an "
                "unsupported question."
            )

        else:

            judge_reason = (
                "System did not clearly abstain "
                "on an unsupported question."
            )


    else:

        if not system_answer:

            answer_correct = False

            judge_reason = (
                "No system answer was produced."
            )

        else:

            try:

                judge = (
                    judge_answer(
                        item=item,
                        system_answer=
                            system_answer,
                    )
                )

                answer_correct = (
                    judge.correct
                )

                judge_reason = (
                    judge.reason
                )

            except Exception as exc:

                answer_correct = False

                judge_reason = (
                    "Judge failed to return "
                    "a valid grade."
                )

                errors.append(
                    "judge_error: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )


    elapsed_ms = round(
        (
            time.perf_counter()
            - started
        )
        * 1000,
        2,
    )


    return {
        # ---------------------------------------------
        # Question
        # ---------------------------------------------

        "id":
            item.get(
                "id"
            ),

        "type":
            item.get(
                "type"
            ),

        "question":
            item.get(
                "question"
            ),


        # ---------------------------------------------
        # Routing
        # ---------------------------------------------

        "expected_route":
            expected,

        "actual_route":
            actual_route,

        "route_correct":
            route_correct,


        # ---------------------------------------------
        # Retrieval
        # ---------------------------------------------

        "expected_source":
            item.get(
                "expected_source"
            ),

        "retrieval_applicable":
            retrieval[
                "applicable"
            ],

        "retrieval_question":
            retrieval[
                "retrieval_question"
            ],

        "retrieval_hit":
            retrieval[
                "hit"
            ],

        "expected_source_rank":
            retrieval[
                "expected_source_rank"
            ],

        "retrieved_sources":
            retrieval[
                "retrieved_sources"
            ],

        "retrieved_chunks":
            retrieval[
                "retrieved_chunks"
            ],


        # ---------------------------------------------
        # Answer
        # ---------------------------------------------

        "expected_answer_contains":
            item.get(
                "expected_answer_contains",
                [],
            ),

        "expected_sql_result":
            item.get(
                "expected_sql_result"
            ),

        "system_answer":
            system_answer,

        "confidence":
            confidence,

        "answer_correct":
            answer_correct,

        "judge_reason":
            judge_reason,


        # ---------------------------------------------
        # Hallucination / abstention
        # ---------------------------------------------

        "abstained":
            abstained,


        # ---------------------------------------------
        # Debugging
        # ---------------------------------------------

        "notes":
            item.get(
                "notes",
                "",
            ),

        "errors":
            errors,


        # Important:
        # This is evaluator wall-clock time.
        #
        # It is NOT our Part-6 stage latency metric.
        "eval_wall_time_ms":
            elapsed_ms,
    }


# =========================================================
# Metrics
# =========================================================

def bool_metric(
    results: list[dict],
    field: str,
) -> dict:
    """
    Calculate correct / total / rate while ignoring N/A values.
    """

    values = [
        result[
            field
        ]
        for result
        in results
        if isinstance(
            result.get(
                field
            ),
            bool,
        )
    ]

    correct = sum(
        1
        for value
        in values
        if value
    )

    total = len(
        values
    )

    rate = (
        correct / total
        if total
        else None
    )

    return {
        "correct":
            correct,

        "total":
            total,

        "rate":
            rate,
    }


def calculate_summary(
    results: list[dict],
    top_k: int,
) -> dict:
    """
    Calculate all high-level Part 5 metrics.
    """

    retrieval = bool_metric(
        results,
        "retrieval_hit",
    )

    answers = bool_metric(
        results,
        "answer_correct",
    )

    routes = bool_metric(
        results,
        "route_correct",
    )


    # Only unanswerable questions belong
    # in abstention-rate denominator.
    unanswerable_results = [
        result
        for result
        in results
        if result.get(
            "type"
        ) == "unanswerable"
    ]


    abstentions = bool_metric(
        unanswerable_results,
        "abstained",
    )


    # ---------------------------------------------
    # Answer correctness broken down by question type
    # ---------------------------------------------

    by_type = {}

    for question_type in (
        "policy",
        "data",
        "hybrid",
        "unanswerable",
    ):

        subset = [
            result
            for result
            in results
            if result.get(
                "type"
            ) == question_type
        ]

        by_type[
            question_type
        ] = {
            "questions":
                len(
                    subset
                ),

            "answer_correctness":
                bool_metric(
                    subset,
                    "answer_correct",
                ),
        }


    return {
        "top_k":
            top_k,

        "total_questions":
            len(
                results
            ),

        "retrieval_hit_rate":
            retrieval,

        "answer_correctness":
            answers,

        "routing_accuracy":
            routes,

        "abstention_rate":
            abstentions,

        "by_type":
            by_type,

        "questions_with_errors":
            sum(
                1
                for result
                in results
                if result.get(
                    "errors"
                )
            ),
    }


# =========================================================
# Formatting helpers
# =========================================================

def percent(
    rate: float | None,
) -> str:

    if rate is None:
        return "N/A"

    return (
        f"{rate * 100:.1f}%"
    )


def pass_fail(
    value: Any,
) -> str:

    if value is True:
        return "PASS"

    if value is False:
        return "FAIL"

    return "N/A"


def sanitize_label(
    label: str,
) -> str:

    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        label.strip(),
    )

    return (
        cleaned
        or "run"
    )


def markdown_escape(
    value: Any,
) -> str:

    if value is None:
        return ""

    return (
        str(
            value
        )
        .replace(
            "|",
            "\\|",
        )
        .replace(
            "\n",
            " ",
        )
    )


# =========================================================
# JSON output
# =========================================================

def write_json(
    path: Path,
    payload: dict,
) -> None:

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


# =========================================================
# Markdown output
# =========================================================

def write_markdown(
    path: Path,
    run_label: str,
    summary: dict,
    results: list[dict],
    config: dict,
) -> None:

    retrieval = (
        summary[
            "retrieval_hit_rate"
        ]
    )

    answers = (
        summary[
            "answer_correctness"
        ]
    )

    routes = (
        summary[
            "routing_accuracy"
        ]
    )

    abstentions = (
        summary[
            "abstention_rate"
        ]
    )


    lines = [
        f"# Week 2 Evaluation — {run_label}",
        "",

        "## Configuration",
        "",

        f"- Top-K: **{config['top_k']}**",

        (
            "- Chunk size: "
            f"**{config['chunk_size_chars']} characters**"
        ),

        (
            "- Chunk overlap: "
            f"**{config['chunk_overlap_chars']} characters**"
        ),

        (
            "- Embedding model: "
            f"**{config['embedding_model']}**"
        ),

        (
            "- Chat model: "
            f"**{config['chat_model']}**"
        ),

        "",

        "## Summary",
        "",

        "| Metric | Correct | Total | Rate |",
        "|---|---:|---:|---:|",

        (
            "| Retrieval hit-rate | "
            f"{retrieval['correct']} | "
            f"{retrieval['total']} | "
            f"{percent(retrieval['rate'])} |"
        ),

        (
            "| Answer correctness | "
            f"{answers['correct']} | "
            f"{answers['total']} | "
            f"{percent(answers['rate'])} |"
        ),

        (
            "| Routing accuracy | "
            f"{routes['correct']} | "
            f"{routes['total']} | "
            f"{percent(routes['rate'])} |"
        ),

        (
            "| Abstention rate | "
            f"{abstentions['correct']} | "
            f"{abstentions['total']} | "
            f"{percent(abstentions['rate'])} |"
        ),

        "",

        "## Answer correctness by type",
        "",

        "| Type | Correct | Total | Rate |",
        "|---|---:|---:|---:|",
    ]


    for (
        question_type,
        info,
    ) in summary[
        "by_type"
    ].items():

        metric = (
            info[
                "answer_correctness"
            ]
        )

        lines.append(
            f"| {question_type} | "
            f"{metric['correct']} | "
            f"{metric['total']} | "
            f"{percent(metric['rate'])} |"
        )


    lines.extend(
        [
            "",

            "## Per-question results",
            "",

            (
                "| ID | Type | Expected route | "
                "Actual route | Route | Retrieval | "
                "Answer | Abstain |"
            ),

            (
                "|---|---|---|---|---|---|---|---|"
            ),
        ]
    )


    for result in results:

        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(
                        result[
                            "id"
                        ]
                    ),

                    markdown_escape(
                        result[
                            "type"
                        ]
                    ),

                    markdown_escape(
                        result[
                            "expected_route"
                        ]
                        or "N/A"
                    ),

                    markdown_escape(
                        result[
                            "actual_route"
                        ]
                        or "N/A"
                    ),

                    pass_fail(
                        result[
                            "route_correct"
                        ]
                    ),

                    pass_fail(
                        result[
                            "retrieval_hit"
                        ]
                    ),

                    pass_fail(
                        result[
                            "answer_correct"
                        ]
                    ),

                    pass_fail(
                        result[
                            "abstained"
                        ]
                    ),
                ]
            )
            + " |"
        )


    # -----------------------------------------------------
    # Failure investigation section
    # -----------------------------------------------------

    failed_or_error = [
        result
        for result
        in results
        if (
            result[
                "answer_correct"
            ] is False

            or result[
                "retrieval_hit"
            ] is False

            or result[
                "route_correct"
            ] is False

            or result[
                "errors"
            ]
        )
    ]


    lines.extend(
        [
            "",
            "## Failures / investigation notes",
            "",
        ]
    )


    if not failed_or_error:

        lines.append(
            "No failures in this run."
        )

    else:

        for result in failed_or_error:

            lines.extend(
                [
                    (
                        f"### {result['id']} "
                        f"— {result['type']}"
                    ),

                    "",

                    (
                        "- Question: "
                        f"{result['question']}"
                    ),

                    (
                        "- Actual route: "
                        f"{result['actual_route']}"
                    ),

                    (
                        "- Retrieval hit: "
                        f"{result['retrieval_hit']}"
                    ),

                    (
                        "- Expected source rank: "
                        f"{result['expected_source_rank']}"
                    ),

                    (
                        "- Retrieved sources: "
                        f"{result['retrieved_sources']}"
                    ),

                    (
                        "- Answer correct: "
                        f"{result['answer_correct']}"
                    ),

                    (
                        "- Judge reason: "
                        f"{result['judge_reason']}"
                    ),

                    (
                        "- Errors: "
                        f"{result['errors'] or 'None'}"
                    ),

                    "",
                ]
            )


    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(
                lines
            )
        )


# =========================================================
# Terminal summary
# =========================================================

def print_summary(
    summary: dict,
) -> None:

    print(
        "\n"
        + "=" * 60
    )

    print(
        "EVALUATION SUMMARY"
    )

    print(
        "=" * 60
    )


    for (
        label,
        key,
    ) in (
        (
            "Retrieval hit-rate",
            "retrieval_hit_rate",
        ),
        (
            "Answer correctness",
            "answer_correctness",
        ),
        (
            "Routing accuracy",
            "routing_accuracy",
        ),
        (
            "Abstention rate",
            "abstention_rate",
        ),
    ):

        metric = (
            summary[
                key
            ]
        )

        print(
            f"{label:<24} "
            f"{metric['correct']}/"
            f"{metric['total']} "
            f"({percent(metric['rate'])})"
        )


    print(
        f"{'Questions with errors':<24} "
        f"{summary['questions_with_errors']}"
    )


    print(
        "\nAnswer correctness by type:"
    )


    for (
        question_type,
        info,
    ) in summary[
        "by_type"
    ].items():

        metric = (
            info[
                "answer_correctness"
            ]
        )

        print(
            f"  {question_type:<14} "
            f"{metric['correct']}/"
            f"{metric['total']} "
            f"({percent(metric['rate'])})"
        )


# =========================================================
# CLI arguments
# =========================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Run the Week 2 "
            "Cabify-Lite evaluation suite."
        )
    )


    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,

        help=(
            "Retriever Top-K. "
            "Baseline is 5."
        ),
    )


    parser.add_argument(
        "--label",
        default="baseline",

        help=(
            "Output label, for example "
            "'baseline' or 'topk3'."
        ),
    )


    parser.add_argument(
        "--limit",
        type=int,
        default=None,

        help=(
            "Optional smoke-test question limit. "
            "Omit this to run all 20."
        ),
    )


    return parser.parse_args()


# =========================================================
# Main evaluation run
# =========================================================

def main() -> None:

    args = parse_args()


    if args.top_k < 1:

        raise ValueError(
            "--top-k must be at least 1."
        )


    label = sanitize_label(
        args.label
    )


    output_json = (
        EVAL_DIR
        / f"results_{label}.json"
    )


    output_markdown = (
        EVAL_DIR
        / f"results_{label}.md"
    )


    questions = load_questions()


    if args.limit is not None:

        questions = questions[
            :args.limit
        ]


    config = {
        **BASELINE_CONFIG,
        "top_k":
            args.top_k,
    }


    print(
        f"Loaded {len(questions)} "
        "evaluation questions"
    )

    print(
        f"Run label: {label}"
    )

    print(
        f"Top-K: {args.top_k}"
    )

    print()


    results = []


    # =====================================================
    # Run questions one-by-one
    # =====================================================

    for index, item in enumerate(
        questions,
        start=1,
    ):

        question_id = item.get(
            "id",
            f"q{index}",
        )


        print(
            f"[{index:02d}/"
            f"{len(questions):02d}] "
            f"{question_id} "
            f"({item.get('type')})"
        )


        try:

            result = (
                evaluate_question(
                    item=item,
                    top_k=args.top_k,
                )
            )


        except Exception as exc:

            # Last-resort protection.
            #
            # One bad question should never terminate
            # the entire evaluation suite.
            result = {
                "id":
                    item.get(
                        "id"
                    ),

                "type":
                    item.get(
                        "type"
                    ),

                "question":
                    item.get(
                        "question"
                    ),

                "expected_route":
                    expected_route(
                        item[
                            "type"
                        ]
                    ),

                "actual_route":
                    None,

                "route_correct":
                    (
                        None
                        if item[
                            "type"
                        ] == "unanswerable"
                        else False
                    ),

                "expected_source":
                    item.get(
                        "expected_source"
                    ),

                "retrieval_applicable":
                    bool(
                        item.get(
                            "expected_source"
                        )
                    ),

                "retrieval_question":
                    None,

                "retrieval_hit":
                    (
                        False
                        if item.get(
                            "expected_source"
                        )
                        else None
                    ),

                "expected_source_rank":
                    None,

                "retrieved_sources":
                    [],

                "retrieved_chunks":
                    [],

                "expected_answer_contains":
                    item.get(
                        "expected_answer_contains",
                        [],
                    ),

                "expected_sql_result":
                    item.get(
                        "expected_sql_result"
                    ),

                "system_answer":
                    "",

                "confidence":
                    None,

                "answer_correct":
                    False,

                "judge_reason":
                    "Evaluation case crashed.",

                "abstained":
                    (
                        False
                        if item[
                            "type"
                        ] == "unanswerable"
                        else None
                    ),

                "notes":
                    item.get(
                        "notes",
                        "",
                    ),

                "errors":
                    [
                        (
                            "fatal_eval_error: "
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        )
                    ],

                "eval_wall_time_ms":
                    None,
            }


        results.append(
            result
        )


        # -------------------------------------------------
        # Show progress immediately
        # -------------------------------------------------

        print(
            "   "
            f"route="
            f"{pass_fail(result['route_correct'])}  "

            f"retrieval="
            f"{pass_fail(result['retrieval_hit'])}  "

            f"answer="
            f"{pass_fail(result['answer_correct'])}  "

            f"abstain="
            f"{pass_fail(result['abstained'])}"
        )


        if result[
            "errors"
        ]:

            print(
                "   errors="
                + " | ".join(
                    result[
                        "errors"
                    ]
                )
            )


    # =====================================================
    # Aggregate metrics
    # =====================================================

    summary = calculate_summary(
        results=results,
        top_k=args.top_k,
    )


    payload = {
        "run_label":
            label,

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "config":
            config,

        "summary":
            summary,

        "results":
            results,
    }


    # =====================================================
    # Save results
    # =====================================================

    write_json(
        path=output_json,
        payload=payload,
    )


    write_markdown(
        path=output_markdown,
        run_label=label,
        summary=summary,
        results=results,
        config=config,
    )


    # =====================================================
    # Print final summary
    # =====================================================

    print_summary(
        summary
    )


    print(
        "\nSaved:"
    )

    print(
        f"- {output_json}"
    )

    print(
        f"- {output_markdown}"
    )


if __name__ == "__main__":
    main()