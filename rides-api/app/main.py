from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.routers.quotes import router as quotes_router
from app.routers.rides import router as rides_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cabify-Lite Rides API",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(rides_router)
app.include_router(quotes_router)


@app.get("/health")
def health():
    return {"status": "ok"}