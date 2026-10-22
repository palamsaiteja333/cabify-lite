from typing import Any

from langchain_core.runnables import (
    RunnableBranch,
    RunnableLambda,
)

from pydantic import BaseModel

from router_classifier import (
    classify_question,
)

from lcel_rag import (
    answer_question_lcel,
)

from sql_route import (
    answer_data_question,
)

from hybrid_route import (
    answer_hybrid_question,
)


# =========================================================
# 1. FINAL ROUTED RESPONSE
# =========================================================

class RoutedResponse(BaseModel):
    """
    Common wrapper returned by the router.

    route:
        policy
        data
        hybrid

    result:
        actual response from the chosen path
    """

    route: str

    result: dict[str, Any]


# =========================================================
# 2. CLASSIFICATION STEP
# =========================================================

def classification_step(
    state: dict,
) -> dict:
    """
    Step 1:

        question
          ↓
        classifier
          ↓
        policy / data / hybrid

    We keep the route inside the LCEL state.
    """

    question = state[
        "question"
    ]

    decision = classify_question(
        question
    )

    return {
        **state,

        "route":
            decision.route,

        "route_reason":
            decision.reason,
    }


# =========================================================
# 3. POLICY ROUTE
# =========================================================

def policy_route(
    state: dict,
) -> RoutedResponse:
    """
    Policy questions use document RAG.
    """

    result = answer_question_lcel(
        question=state["question"],
        top_k=state.get(
            "top_k",
            5,
        ),
    )

    return RoutedResponse(
        route="policy",

        result=
            result.model_dump(),
    )


# =========================================================
# 4. DATA ROUTE
# =========================================================

def data_route(
    state: dict,
) -> RoutedResponse:
    """
    Structured-data questions use SQL.
    """

    result = answer_data_question(
        question=state["question"]
    )

    return RoutedResponse(
        route="data",

        result=
            result.model_dump(),
    )


# =========================================================
# 5. HYBRID ROUTE
# =========================================================

def hybrid_route(
    state: dict,
) -> RoutedResponse:
    """
    Hybrid questions use:

        decomposition
            ↓
        RAG + SQL
            ↓
        synthesis
    """

    result = answer_hybrid_question(
        question=state["question"]
    )

    return RoutedResponse(
        route="hybrid",

        result=
            result.model_dump(),
    )


# =========================================================
# 6. RUNNABLE BRANCH
# =========================================================

route_branch = RunnableBranch(

    # -----------------------------------------------------
    # If route == policy
    # -----------------------------------------------------

    (
        lambda state:
            state["route"]
            == "policy",

        RunnableLambda(
            policy_route
        ),
    ),


    # -----------------------------------------------------
    # If route == data
    # -----------------------------------------------------

    (
        lambda state:
            state["route"]
            == "data",

        RunnableLambda(
            data_route
        ),
    ),


    # -----------------------------------------------------
    # Default branch
    #
    # Since our Pydantic classifier only allows:
    # policy / data / hybrid,
    #
    # the remaining valid route is hybrid.
    # -----------------------------------------------------

    RunnableLambda(
        hybrid_route
    ),
)


# =========================================================
# 7. COMPLETE ROUTED CHAIN
# =========================================================

routed_chain = (

    RunnableLambda(
        classification_step
    )

    |

    route_branch
)


# =========================================================
# 8. PUBLIC FUNCTION
# =========================================================

def answer_question_routed(
    question: str,
    top_k: int = 5,
) -> RoutedResponse:
    """
    Main entry point for Week 2 routing.

    The caller does NOT decide whether the question
    needs RAG, SQL, or both.

    The system decides automatically.
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    result = routed_chain.invoke(
        {
            "question":
                question,

            "top_k":
                top_k,
        }
    )

    return result


# =========================================================
# 9. MANUAL TEST
# =========================================================

if __name__ == "__main__":

    questions = [

        # POLICY
        "What is the cancellation policy?",


        # DATA
        (
            "How many rides were "
            "cancelled in September?"
        ),


        # HYBRID
        (
            "What is the cancellation policy "
            "and how many rides were cancelled "
            "in September?"
        ),
    ]


    for question in questions:

        print()
        print("=" * 70)

        print(
            f"QUESTION: {question}"
        )

        result = answer_question_routed(
            question=question,
            top_k=5,
        )

        print()

        print(
            result.model_dump_json(
                indent=2
            )
        )