from time import perf_counter
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)


HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)
)


RIDES_CREATED = Counter(
    "rides_created_total",
    "Total number of rides successfully created"
)


def setup_metrics(app: FastAPI):
    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        start_time = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = perf_counter() - start_time
            route = request.scope.get("route")
            endpoint = route.path if route else request.url.path

            HTTP_REQUESTS.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )