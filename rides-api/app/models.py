from pydantic import BaseModel


class RideCreate(BaseModel):
    pickup: str
    destination: str


class RideResponse(BaseModel):
    id: int
    pickup: str
    destination: str