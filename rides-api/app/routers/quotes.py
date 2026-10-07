import asyncio
import random
from fastapi import APIRouter, Query
from pydantic import BaseModel
from opentelemetry import trace
from app.db import get_ride_count


tracer = trace.get_tracer(__name__)


router = APIRouter(
    prefix="/quote",
    tags=["quotes"]
)


class QuoteResponse(BaseModel):
    pickup: str
    destination: str
    price: float


@router.get(
    "",
    response_model=QuoteResponse
)
async def get_quote(
    from_: str = Query(alias="from"),
    to: str = Query()
):
    # if random.random() < 0.20:
    #     delay_seconds = random.uniform(0, 2)
    #     await asyncio.sleep(delay_seconds)

    if random.random() < 0.20:
        delay_seconds = random.uniform(0, 2)

        with tracer.start_as_current_span("simulate_pricing_delay") as span:
            span.set_attribute("delay.seconds", delay_seconds)
            await asyncio.sleep(delay_seconds)

    with tracer.start_as_current_span("calculate_quote_price") as span:
        ride_count = get_ride_count()

        price = round(
            10 + len(from_) * 0.75 + len(to) * 0.75,
            2
        )

        span.set_attribute("quote.price", price)
        span.set_attribute("rides.count", ride_count)

    # price = round(
    #     10 + len(from_) * 0.75 + len(to) * 0.75,
    #     2
    # )

    return {
        "pickup": from_,
        "destination": to,
        "price": price
    }