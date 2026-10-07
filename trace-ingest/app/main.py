from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from app.db import init_db, insert_span


def any_value_to_python(value):
    value_type = value.WhichOneof("value")

    if value_type == "string_value":
        return value.string_value

    if value_type == "bool_value":
        return value.bool_value

    if value_type == "int_value":
        return value.int_value

    if value_type == "double_value":
        return value.double_value

    if value_type == "bytes_value":
        return value.bytes_value.hex()

    if value_type == "array_value":
        return [
            any_value_to_python(item)
            for item in value.array_value.values
        ]

    if value_type == "kvlist_value":
        return {
            item.key: any_value_to_python(item.value)
            for item in value.kvlist_value.values
        }

    return None


def attributes_to_dict(attributes):
    return {
        attribute.key: any_value_to_python(attribute.value)
        for attribute in attributes
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cabify-Lite Trace Ingest",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/traces")
async def ingest_traces(request: Request):
    body = await request.body()

    export_request = ExportTraceServiceRequest()
    export_request.ParseFromString(body)

    inserted_count = 0

    for resource_spans in export_request.resource_spans:
        resource_attributes = attributes_to_dict(
            resource_spans.resource.attributes
        )

        service_name = resource_attributes.get(
            "service.name",
            "unknown-service",
        )

        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                trace_id = span.trace_id.hex()
                span_id = span.span_id.hex()

                parent_span_id = (
                    span.parent_span_id.hex()
                    if span.parent_span_id
                    else None
                )

                start_time = datetime.fromtimestamp(
                    span.start_time_unix_nano / 1_000_000_000,
                    tz=timezone.utc,
                )

                duration_ms = (
                    span.end_time_unix_nano
                    - span.start_time_unix_nano
                ) / 1_000_000

                status = str(span.status.code)

                attributes = attributes_to_dict(
                    span.attributes
                )

                insert_span(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    service=service_name,
                    span_name=span.name,
                    start_time=start_time,
                    duration_ms=duration_ms,
                    status=status,
                    attributes=attributes,
                )

                inserted_count += 1

    response = ExportTraceServiceResponse()

    return Response(
        content=response.SerializeToString(),
        media_type="application/x-protobuf",
        headers={
            "X-Spans-Processed": str(inserted_count)
        },
    )