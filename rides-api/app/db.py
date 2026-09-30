import os

import psycopg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://cabify:cabify123@localhost:5432/cabify"
)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rides (
                    id SERIAL PRIMARY KEY,
                    pickup TEXT NOT NULL,
                    destination TEXT NOT NULL
                );
                """
            )


def get_ride_by_id(ride_id: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, pickup, destination
                FROM rides
                WHERE id = %s;
                """,
                (ride_id,)
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "pickup": row[1],
        "destination": row[2]
    }

def create_ride(pickup: str, destination: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rides (pickup, destination)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (pickup, destination)
            )

            ride_id = cursor.fetchone()[0]

    return {
        "id": ride_id,
        "pickup": pickup,
        "destination": destination
    }