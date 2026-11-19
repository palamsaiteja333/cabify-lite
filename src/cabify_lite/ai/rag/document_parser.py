from pathlib import Path

from pypdf import PdfReader

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


# =========================================================
# 1. CONFIGURATION
# =========================================================

# Directory containing the approved Week 2 corpus.
CORPUS_DIR = Path("week2/corpus")


# Explicitly list the documents we want to ingest.
#
# This is safer than recursively ingesting every file
# that happens to exist under week2/.
CORPUS_FILES = [
    "driver_handbook.md",
    "no_show_policy.md",
    "pricing_sheet.pdf",
    "refunds_and_cancellations.md",
    "support_faq.md",
    "terms_and_conditions.md",
]


# =========================================================
# 2. COMMON RECURSIVE TEXT SPLITTER
# =========================================================

# This splitter is used after document-specific parsing.
#
# Markdown:
#   headings -> logical sections -> recursive splitting
#
# PDF:
#   pages -> recursive splitting
#
# 1200 / 150 are our baseline values.
# We will evaluate them later rather than assuming
# they are permanently optimal.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150,
)


# =========================================================
# 3. MARKDOWN PARSING + CHUNKING
# =========================================================

def chunk_markdown(file_path: Path):
    """
    Parse a Markdown document while preserving its heading
    structure, then recursively split large sections.

    Output:
        List of LangChain Document objects.

    Each Document contains:
        page_content -> chunk text
        metadata     -> h1/h2/h3 information
    """

    # Read the Markdown source as plain text.
    text = file_path.read_text(
        encoding="utf-8"
    )

    # Define which Markdown headings should become metadata.
    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]

    # First stage:
    # split according to the logical Markdown structure.
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,

        # Keep the actual Markdown headings inside
        # the chunk text as well as metadata.
        strip_headers=False,
    )

    sections = markdown_splitter.split_text(
        text
    )

    # Second stage:
    # a logical section could still be very large,
    # so recursively split oversized sections.
    chunks = text_splitter.split_documents(
        sections
    )

    return chunks


# =========================================================
# 4. PDF PARSING + CHUNKING
# =========================================================

def chunk_pdf(file_path: Path):
    """
    Extract PDF text page-by-page.

    We preserve the page number as metadata so that
    retrieved chunks can later produce citations such as:

        pricing_sheet.pdf, Page 2

    Each page is then recursively split if needed.
    """

    reader = PdfReader(
        str(file_path)
    )

    all_chunks = []

    # start=1 makes page numbers human-friendly:
    # Page 1, Page 2, ...
    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):

        # pypdf may return None for a page with
        # no extractable text.
        page_text = (
            page.extract_text()
            or ""
        ).strip()

        # Ignore blank/unreadable pages.
        if not page_text:
            continue

        # create_documents() allows us to attach
        # metadata before recursive splitting.
        page_chunks = text_splitter.create_documents(
            texts=[page_text],

            metadatas=[
                {
                    "page": page_number
                }
            ],
        )

        all_chunks.extend(
            page_chunks
        )

    return all_chunks


# =========================================================
# 5. FILE-TYPE ROUTER
# =========================================================

def chunk_document(file_path: Path):
    """
    Route a document to the appropriate parsing strategy.

    .md  -> Markdown parser
    .pdf -> PDF parser
    """

    suffix = file_path.suffix.lower()

    if suffix == ".md":
        return chunk_markdown(
            file_path
        )

    if suffix == ".pdf":
        return chunk_pdf(
            file_path
        )

    raise ValueError(
        f"Unsupported file type: "
        f"{file_path.suffix}"
    )


# =========================================================
# 6. METADATA HELPER
# =========================================================

def get_location_metadata(
    metadata: dict
) -> str | None:
    """
    Convert parser-specific metadata into a useful
    human-readable location.

    Markdown:
        prefer h3 -> h2 -> h1

    PDF:
        return Page N
    """

    # For Markdown, use the most specific heading.
    heading = (
        metadata.get("h3")
        or metadata.get("h2")
        or metadata.get("h1")
    )

    if heading:
        return heading

    # For PDF, preserve page location.
    page_number = metadata.get(
        "page"
    )

    if page_number is not None:
        return f"Page {page_number}"

    return None


# =========================================================
# 7. TEST THE ENTIRE CORPUS
# =========================================================

def inspect_corpus():
    """
    Parse and chunk every approved document.

    This function does NOT call Bedrock and does NOT
    write anything to PostgreSQL.

    Its only purpose is to inspect the parsing/chunking
    stage before embedding.
    """

    total_chunks = 0

    for filename in CORPUS_FILES:

        file_path = (
            CORPUS_DIR
            / filename
        )

        # Fail immediately if an expected document
        # is missing.
        if not file_path.exists():
            raise FileNotFoundError(
                f"Could not find: "
                f"{file_path}"
            )

        chunks = chunk_document(
            file_path
        )

        total_chunks += len(
            chunks
        )

        print()
        print("=" * 60)

        print(
            f"Source: {file_path.name}"
        )

        print(
            f"Type: {file_path.suffix}"
        )

        print(
            f"Chunks: {len(chunks)}"
        )

        # Show only the first chunk so we can verify
        # metadata without dumping the full corpus.
        if chunks:

            first_chunk = chunks[0]

            print(
                "First chunk location:",
                get_location_metadata(
                    first_chunk.metadata
                ),
            )

            print(
                "First chunk metadata:",
                first_chunk.metadata,
            )

            # Only print a short preview.
            preview = (
                first_chunk.page_content
                .replace("\n", " ")
                [:200]
            )

            print(
                "Preview:",
                preview,
            )

    print()
    print("=" * 60)

    print(
        f"Total chunks: {total_chunks}"
    )


# =========================================================
# 8. ENTRY POINT
# =========================================================

if __name__ == "__main__":
    inspect_corpus()