import hashlib
import json
import os

import boto3
from dotenv import load_dotenv

from document_parser import (
    CORPUS_DIR,
    chunk_document,
    get_location_metadata,
)


# =========================================================
# 1. CONFIGURATION
# =========================================================

# Load environment variables from the project's .env file.
load_dotenv()

# AWS region where Amazon Bedrock is available.
AWS_REGION = os.getenv(
    "AWS_REGION",
    "us-east-2",
)

# Embedding model used for both:
#   1. document chunks
#   2. user queries later during retrieval
EMBEDDING_MODEL = (
    "amazon.titan-embed-text-v2:0"
)

# We explicitly request 1024 dimensions.
EMBEDDING_DIMENSIONS = 1024


# =========================================================
# 2. BEDROCK CLIENT
# =========================================================

# Create the AWS Bedrock Runtime client.
#
# boto3 uses the AWS credentials from the
# current authenticated AWS session.
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
)


# =========================================================
# 3. CONTENT HASHING
# =========================================================

def make_content_hash(
    content: str,
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint
    for a chunk.

    Same content:
        -> same hash

    Changed content:
        -> different hash
    """

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


# =========================================================
# 4. EMBEDDING GENERATION
# =========================================================

def create_embedding(
    text: str,
) -> list[float]:
    """
    Convert text into a normalized
    1024-dimensional embedding using
    Amazon Titan Text Embeddings V2.
    """

    # Request body expected by Titan.
    request_body = {
        "inputText": text,
        "dimensions": EMBEDDING_DIMENSIONS,
        "normalize": True,
    }

    # Invoke the embedding model through Bedrock.
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            request_body
        ),
    )

    # Bedrock returns a streaming response body.
    # Read the bytes and decode the JSON.
    response_body = json.loads(
        response["body"].read()
    )

    # Return only the numerical vector.
    return response_body["embedding"]


# =========================================================
# 5. TEST ONE REAL DOCUMENT CHUNK
# =========================================================

def test_embedding_stage():
    """
    Parse one real corpus document,
    take its first chunk,
    hash it,
    generate an embedding,
    and inspect the result.

    No PostgreSQL writes happen here.
    """

    file_path = (
        CORPUS_DIR
        / "support_faq.md"
    )

    # Reuse the parser created in Step 1.
    chunks = chunk_document(
        file_path
    )

    if not chunks:
        raise RuntimeError(
            f"No chunks created for "
            f"{file_path}"
        )

    # Use only the first chunk for this learning test.
    chunk = chunks[0]

    content = (
        chunk.page_content.strip()
    )

    location = get_location_metadata(
        chunk.metadata
    )

    # Create deterministic fingerprint.
    content_hash = make_content_hash(
        content
    )

    # Send the chunk to Titan.
    embedding = create_embedding(
        content
    )

    # =====================================================
    # 6. OUTPUT / VALIDATION
    # =====================================================

    print(
        f"Source: {file_path.name}"
    )

    print(
        f"Location: {location}"
    )

    print(
        f"Content length: "
        f"{len(content)} characters"
    )

    print(
        f"SHA-256: {content_hash}"
    )

    print(
        f"Embedding dimensions: "
        f"{len(embedding)}"
    )

    print(
        "First 5 embedding values:"
    )

    print(
        embedding[:5]
    )

    # Defensive validation:
    # fail immediately if the embedding model returns
    # an unexpected dimensionality.
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            "Unexpected embedding dimension: "
            f"{len(embedding)}"
        )

    print()
    print(
        "Embedding stage passed."
    )


# =========================================================
# 7. ENTRY POINT
# =========================================================

if __name__ == "__main__":
    test_embedding_stage()