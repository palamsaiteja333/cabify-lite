import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)

SERVICE_NAME = "cabify-grounded-answers"

OTEL_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://localhost:4317",
)

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "week2",
    "deployment.environment": "local",
})

provider = TracerProvider(resource=resource)

exporter = OTLPSpanExporter(
    endpoint=OTEL_ENDPOINT,
    insecure=True,
)

provider.add_span_processor(
    BatchSpanProcessor(exporter)
)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer("cabify-lite.week2")


def flush_telemetry() -> bool:
    return provider.force_flush()
