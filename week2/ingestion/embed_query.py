import sys

from embedding_stage import (
    create_embedding,
)


def vector_to_string(
    vector: list[float],
) -> str:
    """
    Convert the Python embedding list into
    pgvector's textual vector representation.

    Example:

        Python:
            [0.1, 0.2, 0.3]

        pgvector:
            [0.1,0.2,0.3]
    """

    return (
        "["
        + ",".join(
            str(value)
            for value in vector
        )
        + "]"
    )


def embed_query(
    question: str,
) -> list[float]:
    """
    Convert a user's natural-language question
    into an embedding.

    IMPORTANT:
    We deliberately reuse create_embedding()
    from the ingestion pipeline.

    This guarantees that documents and queries
    use the same:
        - embedding model
        - dimensions
        - normalization settings
    """

    return create_embedding(
        question
    )


if __name__ == "__main__":

    # Example:
    #
    # python embed_query.py \
    #   "What is the cancellation policy?"
    #
    # sys.argv[1:] contains all words after
    # the Python filename.
    question = " ".join(
        sys.argv[1:]
    ).strip()

    if not question:
        raise ValueError(
            "Please provide a question."
        )

    embedding = embed_query(
        question
    )

    # Only print the vector.
    #
    # This is important because later Bash will do:
    #
    # QUERY_VECTOR=$(python embed_query.py "...")
    #
    # Any debug text here would corrupt the
    # query vector variable.
    print(
        vector_to_string(
            embedding
        )
    )