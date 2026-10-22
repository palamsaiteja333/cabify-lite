import os

import boto3
from dotenv import load_dotenv


# =========================================================
# 1. CONFIGURATION
# =========================================================

load_dotenv()

AWS_REGION = os.getenv(
    "AWS_REGION",
    "us-east-2",
)

# US inference profile for Amazon Nova Micro.
# CHAT_MODEL = (
#     "us.amazon.nova-micro-v1:0"
# )
CHAT_MODEL = (
    "us.amazon.nova-2-lite-v1:0"
)


# =========================================================
# 2. BEDROCK RUNTIME CLIENT
# =========================================================

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
)


# =========================================================
# 3. GENERATE TEXT
# =========================================================

def generate_text(
    prompt: str,
    system_prompt: str | None = None,
) -> str:
    """
    Generate text using Amazon Nova through
    the AWS Bedrock Converse API.

    prompt:
        Dynamic user content such as:
        - retrieved context
        - user question

    system_prompt:
        Stable application-level instructions such as:
        - grounding rules
        - citation requirements
        - abstention behavior
    """

    # -----------------------------------------------------
    # Build the Bedrock Converse request
    # -----------------------------------------------------

    request = {
        "modelId": CHAT_MODEL,

        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ],
            }
        ],

        "inferenceConfig": {
            # Low temperature for stable enterprise QA.
            "temperature": 0.0,

            # Maximum number of generated tokens.
            "maxTokens": 500,
        },
    }


    # -----------------------------------------------------
    # Add system instructions when provided
    # -----------------------------------------------------

    if system_prompt:

        request["system"] = [
            {
                "text": system_prompt
            }
        ]


    # -----------------------------------------------------
    # Call Amazon Nova through Bedrock
    # -----------------------------------------------------

    response = bedrock.converse(
        **request
    )


    # -----------------------------------------------------
    # Extract generated text from Bedrock response
    # -----------------------------------------------------

    answer = (
        response["output"]
        ["message"]
        ["content"][0]
        ["text"]
    )

    return answer


# =========================================================
# 4. SIMPLE MANUAL TEST
# =========================================================

if __name__ == "__main__":

    system_prompt = """
You are a concise technical assistant.

Use only the information supplied in the
provided context.

Do not invent missing information.
""".strip()

    prompt = """
CONTEXT:

RAG means Retrieval-Augmented Generation.


QUESTION:

What does RAG mean?
""".strip()

    answer = generate_text(
        prompt=prompt,
        system_prompt=system_prompt,
    )

    print()
    print("Nova response:")
    print()
    print(answer)