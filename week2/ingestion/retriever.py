import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from embedding_stage import create_embedding


# =========================================================
# 1. CONFIGURATION
# =========================================================

load_dotenv()

DATABASE_URL = (
    f"postgresql://"
    f"{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@"
    f"localhost:5432/"
    f"{os.environ['POSTGRES_DB']}"
)

EMBEDDING_DIMENSIONS = 1024


# =========================================================
# 2. PGVECTOR CONVERSION
# =========================================================

def vector_to_string(
    vector: list[float],
) -> str:
    """
    Convert a Python list of floats into the text
    representation accepted by pgvector.

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


# =========================================================
# 3. RETRIEVAL
# =========================================================

def retrieve(
    question: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve the Top-K chunks that are most
    semantically similar to the user's question.

    Flow:

        question
          ↓
        Titan embedding
          ↓
        pgvector cosine search
          ↓
        Top-K chunks
    """

    # -----------------------------------------------------
    # Step 1: Validate input
    # -----------------------------------------------------

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0."
        )


    # -----------------------------------------------------
    # Step 2: Embed the user question
    # -----------------------------------------------------

    query_embedding = create_embedding(
        question
    )

    # Defensive check:
    # documents and queries must have the same
    # embedding dimensionality.
    if len(query_embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            "Unexpected query embedding dimension: "
            f"{len(query_embedding)}"
        )

    query_vector = vector_to_string(
        query_embedding
    )


    # -----------------------------------------------------
    # Step 3: Search PostgreSQL / pgvector
    # -----------------------------------------------------

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    chunk_id,
                    source_file,
                    section_heading,
                    chunk_index,
                    content,

                    embedding
                        <=> %s::vector
                        AS cosine_distance

                FROM doc_chunks

                ORDER BY
                    embedding
                    <=> %s::vector

                LIMIT %s;
                """,
                (
                    query_vector,
                    query_vector,
                    top_k,
                ),
            )

            rows = cursor.fetchall()


    # -----------------------------------------------------
    # Step 4: Convert results into application objects
    # -----------------------------------------------------

    results = []

    for row in rows:

        cosine_distance = float(
            row["cosine_distance"]
        )

        results.append(
            {
                "chunk_id":
                    row["chunk_id"],

                "source_file":
                    row["source_file"],

                "section_heading":
                    row["section_heading"],

                "chunk_index":
                    row["chunk_index"],

                "content":
                    row["content"],

                "cosine_distance":
                    cosine_distance,

                "cosine_similarity":
                    1 - cosine_distance,
            }
        )

    return results


# =========================================================
# 4. SIMPLE MANUAL TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "How much do I have to pay "
        "if I call off my ride?"
    )

    results = retrieve(
        question,
        top_k=5,
    )

    print()
    print(
        f"Question: {question}"
    )

    print()

    for rank, result in enumerate(
        results,
        start=1,
    ):

        print("=" * 60)

        print(
            f"Rank: {rank}"
        )

        print(
            f"Source: "
            f"{result['source_file']}"
        )

        print(
            f"Location: "
            f"{result['section_heading']}"
        )

        print(
            f"Chunk index: "
            f"{result['chunk_index']}"
        )

        print(
            f"Cosine distance: "
            f"{result['cosine_distance']:.4f}"
        )

        print(
            f"Cosine similarity: "
            f"{result['cosine_similarity']:.4f}"
        )

        print()
        print("Content preview:")

        print(
            result["content"][:400]
        )

        print()