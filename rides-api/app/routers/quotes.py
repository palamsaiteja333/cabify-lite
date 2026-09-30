import asyncio
import random
from fastapi import APIRouter, Query
from pydantic import BaseModel


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
    if random.random() < 0.20:
        delay_seconds = random.uniform(0, 2)
        await asyncio.sleep(delay_seconds)

    price = round(
        10 + len(from_) * 0.75 + len(to) * 0.75,
        2
    )

    return {
        "pickup": from_,
        "destination": to,
        "price": price
    }