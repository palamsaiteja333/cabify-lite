import os
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor


def setup_telemetry(app: FastAPI):
    resource = Resource.create({
        "service.name": "rides-api"
    })
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    collector = os.getenv("OTEL_COLLECTOR_URL", "http://otel-collector:4317")
    exporter = OTLPSpanExporter(endpoint=collector)
    span_processor=BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)

    
    FastAPIInstrumentor.instrument_app(app)
    PsycopgInstrumentor().instrument()
