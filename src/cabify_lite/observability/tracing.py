from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

from cabify_lite.core.config import get_settings


SERVICE_NAME = "cabify-lite-api"


def setup_telemetry(app: FastAPI) -> None:
    """Configure a shared tracer provider for the application."""

    if getattr(app.state, "telemetry_configured", False):
        return

    provider = trace.get_tracer_provider()

    # Create a provider only when one has not been
    # installed in this Python process.
    if not isinstance(provider, TracerProvider):
        settings = get_settings()

        resource = Resource.create({
            "service.name": SERVICE_NAME,
        })

        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(
            endpoint=settings.otel_endpoint,
            insecure=True,
        )

        provider.add_span_processor(
            BatchSpanProcessor(exporter)
        )

        trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    PsycopgInstrumentor().instrument()

    app.state.telemetry_configured = True


def get_tracer(name: str):
    """Return a tracer using the shared global provider."""
    return trace.get_tracer(name)


def flush_telemetry() -> bool:
    provider = trace.get_tracer_provider()

    if isinstance(provider, TracerProvider):
        return provider.force_flush()

    return False
