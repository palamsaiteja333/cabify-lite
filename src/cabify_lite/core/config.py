import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    readonly_database_url: str | None
    otel_endpoint: str
    aws_region: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],

        readonly_database_url=os.getenv(
            "READONLY_DATABASE_URL"
        ),

        otel_endpoint=(
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            or os.getenv("OTEL_COLLECTOR_URL")
            or "http://localhost:4317"
        ),

        aws_region=os.getenv(
            "AWS_REGION", "us-east-2"
        ),
    )
