/*
=========================================================
Cabify-Lite Week 2
Raw semantic retrieval using pgvector
=========================================================

Input:
    query_vector

Process:
    1. Compare the query vector against every
       stored document embedding.
    2. Calculate cosine distance.
    3. Rank nearest chunks first.
    4. Return top 5.

Important:

    <=>  = cosine distance

    Lower distance
        = more similar

    Higher similarity
        = more similar
=========================================================
*/


SELECT
    chunk_id,

    -- Citation / provenance metadata
    source_file,
    section_heading,
    chunk_index,

    -- Cosine distance:
    -- lower = more semantically similar
    ROUND(
        (
            embedding
            <=> :'query_vector'::vector
        )::numeric,
        4
    ) AS cosine_distance,

    -- Convert distance into a more intuitive
    -- similarity value for inspection.
    ROUND(
        (
            1 - (
                embedding
                <=> :'query_vector'::vector
            )
        )::numeric,
        4
    ) AS cosine_similarity,

    -- Small preview so terminal output
    -- remains readable.
    LEFT(
        content,
        300
    ) AS content_preview

FROM doc_chunks

-- Nearest vectors first.
ORDER BY
    embedding
    <=> :'query_vector'::vector

-- top-k retrieval
LIMIT 5;