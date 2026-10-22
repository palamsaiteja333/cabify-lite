import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from document_parser import (
    CORPUS_DIR,
    CORPUS_FILES,
    chunk_document,
    get_location_metadata,
)

from embedding_stage import (
    create_embedding,
    make_content_hash,
)


# =========================================================
# 1. CONFIGURATION
# =========================================================

# Load database configuration from .env.
load_dotenv()


# Build the PostgreSQL connection string.
DATABASE_URL = (
    f"postgresql://"
    f"{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@"
    f"localhost:5432/"
    f"{os.environ['POSTGRES_DB']}"
)


# =========================================================
# 2. PGVECTOR CONVERSION
# =========================================================

def vector_to_string(
    vector: list[float],
) -> str:
    """
    Convert a Python list of floats into
    pgvector's text representation.

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
# 3. CHECK WHETHER CHUNK ALREADY EXISTS
# =========================================================

def chunk_exists(
    cursor,
    source_file: str,
    content_hash: str,
) -> bool:
    """
    Check whether this exact chunk has already
    been ingested for this source document.

    This check happens BEFORE calling Bedrock.

    Why?
        Avoid generating the same embedding twice.
    """

    cursor.execute(
        """
        SELECT 1
        FROM doc_chunks
        WHERE source_file = %s
          AND content_hash = %s
        LIMIT 1;
        """,
        (
            source_file,
            content_hash,
        ),
    )

    return (
        cursor.fetchone()
        is not None
    )


# =========================================================
# 4. INSERT ONE CHUNK
# =========================================================

def insert_chunk(
    cursor,
    source_file: str,
    section_heading: str | None,
    chunk_index: int,
    content: str,
    content_hash: str,
    embedding: list[float],
) -> bool:
    """
    Insert one embedded chunk into PostgreSQL.

    Returns:
        True  -> row inserted
        False -> duplicate/conflict skipped
    """

    embedding_string = vector_to_string(
        embedding
    )

    cursor.execute(
        """
        INSERT INTO doc_chunks (
            source_file,
            section_heading,
            chunk_index,
            content,
            content_hash,
            embedding
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s::vector
        )

        ON CONFLICT (
            source_file,
            content_hash
        )
        DO NOTHING

        RETURNING chunk_id;
        """,
        (
            source_file,
            section_heading,
            chunk_index,
            content,
            content_hash,
            embedding_string,
        ),
    )

    return (
        cursor.fetchone()
        is not None
    )


# =========================================================
# 5. INGEST ONE DOCUMENT
# =========================================================

def ingest_file(
    file_path: Path,
):
    """
    Complete ingestion pipeline for one document.

    document
        ↓
    parse / chunk
        ↓
    metadata
        ↓
    SHA-256
        ↓
    duplicate check
        ↓
    Titan embedding
        ↓
    PostgreSQL + pgvector
    """

    chunks = chunk_document(
        file_path
    )

    inserted_count = 0
    skipped_count = 0

    print()
    print("=" * 60)

    print(
        f"Source: {file_path.name}"
    )

    print(
        f"Chunks found: {len(chunks)}"
    )

    # One database connection per document.
    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cursor:

            for chunk_index, chunk in enumerate(
                chunks
            ):

                # -----------------------------------------
                # Extract chunk text
                # -----------------------------------------

                content = (
                    chunk.page_content
                    .strip()
                )

                if not content:
                    continue


                # -----------------------------------------
                # Preserve useful citation metadata
                # -----------------------------------------

                section_heading = (
                    get_location_metadata(
                        chunk.metadata
                    )
                )


                # -----------------------------------------
                # Create deterministic fingerprint
                # -----------------------------------------

                content_hash = (
                    make_content_hash(
                        content
                    )
                )


                # -----------------------------------------
                # Avoid duplicate embedding calls
                # -----------------------------------------

                if chunk_exists(
                    cursor,
                    file_path.name,
                    content_hash,
                ):

                    skipped_count += 1

                    print(
                        f"Skipping existing "
                        f"chunk "
                        f"{chunk_index + 1}/"
                        f"{len(chunks)}"
                    )

                    continue


                # -----------------------------------------
                # Generate embedding only for new chunks
                # -----------------------------------------

                print(
                    f"Embedding "
                    f"chunk "
                    f"{chunk_index + 1}/"
                    f"{len(chunks)}..."
                )

                embedding = (
                    create_embedding(
                        content
                    )
                )


                # -----------------------------------------
                # Validate model output
                # -----------------------------------------

                if len(embedding) != 1024:

                    raise ValueError(
                        "Unexpected embedding "
                        f"dimension: "
                        f"{len(embedding)}"
                    )


                # -----------------------------------------
                # Persist into PostgreSQL
                # -----------------------------------------

                inserted = insert_chunk(
                    cursor=cursor,
                    source_file=file_path.name,
                    section_heading=section_heading,
                    chunk_index=chunk_index,
                    content=content,
                    content_hash=content_hash,
                    embedding=embedding,
                )

                if inserted:
                    inserted_count += 1
                else:
                    skipped_count += 1


        # Commit the document transaction.
        conn.commit()


    print(
        f"Inserted: {inserted_count}"
    )

    print(
        f"Skipped existing: "
        f"{skipped_count}"
    )


# =========================================================
# 6. INGEST ENTIRE CORPUS
# =========================================================

def ingest_corpus():
    """
    Ingest the explicitly approved corpus.

    Only files listed in CORPUS_FILES are processed.
    """

    total_inserted = 0

    for filename in CORPUS_FILES:

        file_path = (
            CORPUS_DIR
            / filename
        )

        if not file_path.exists():

            raise FileNotFoundError(
                f"Could not find: "
                f"{file_path}"
            )

        ingest_file(
            file_path
        )


# =========================================================
# 7. ENTRY POINT
# =========================================================

if __name__ == "__main__":
    ingest_corpus()