from contextlib import asynccontextmanager
from fastapi import FastAPI
from cabify_lite.db.connection import init_db
from cabify_lite.observability.metrics import setup_metrics
from cabify_lite.api.quotes import router as quotes_router
from cabify_lite.api.ask import router as ask_router
from cabify_lite.api.rides import router as rides_router
from cabify_lite.observability.tracing import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cabify-Lite Rides API",
    version="0.1.0",
    lifespan=lifespan
)

setup_telemetry(app)
setup_metrics(app)

app.include_router(rides_router)
app.include_router(quotes_router)
app.include_router(ask_router)


@app.get("/health")
def health():
    return {"status": "ok"}