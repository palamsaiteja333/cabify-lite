from fastapi import APIRouter, HTTPException, status
from app.db import create_ride, get_ride_by_id
from app.metrics import RIDES_CREATED
from app.models import RideCreate, RideResponse


router = APIRouter(
    prefix="/rides",
    tags=["rides"]
)


@router.post(
    "",
    response_model=RideResponse,
    status_code=status.HTTP_201_CREATED
)
def create_ride_endpoint(ride: RideCreate):
    created_ride = create_ride(
        pickup=ride.pickup,
        destination=ride.destination
    )

    RIDES_CREATED.inc()

    return created_ride


@router.get(
    "/{ride_id}",
    response_model=RideResponse
)
def get_ride_endpoint(ride_id: int):
    ride = get_ride_by_id(ride_id)

    if ride is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found"
        )

    return ride