"""Deterministic Cabify-Lite dataset generator (Week 2).

Pure stdlib so it runs anywhere. Writes four CSVs and prints a distribution report.
This same file is committed to the mentorship repo as week2/seed/generate_data.py.
"""

import argparse
import collections
import csv
import io
import random
from datetime import datetime, timedelta

SEED = 20260101
N_RIDES = 2000
N_RIDERS = 420
N_DRIVERS = 95
DAYS = 90
CURRENCY = "INR"

# Pricing, mirrored from corpus/pricing_sheet.pdf. Keep these in sync with the document.
BASE_FARE = 40.0
PER_KM = 12.0
PER_MIN = 1.5
MIN_FARE = 60.0
AIRPORT_SURCHARGE = 75.0

LOCALITIES = [
    "Indiranagar", "Koramangala", "HSR Layout", "Whitefield", "Jayanagar",
    "Electronic City", "MG Road", "Hebbal", "Marathahalli", "Yelahanka",
    "Banashankari", "BTM Layout", "Rajajinagar", "JP Nagar", "Bellandur",
    "Sarjapur Road", "Malleshwaram", "Domlur", "Kalyan Nagar", "Basavanagudi",
]
AIRPORT = "Kempegowda International Airport"

FIRST = [
    "Aarav", "Diya", "Rohan", "Ananya", "Kabir", "Meera", "Arjun", "Ishita",
    "Vikram", "Sneha", "Nikhil", "Pooja", "Rahul", "Divya", "Karthik", "Nisha",
    "Siddharth", "Priya", "Manish", "Shruti", "Aditya", "Tanvi", "Varun", "Lakshmi",
    "Imran", "Fatima", "Joseph", "Grace", "Tenzin", "Ritu",
]
LAST = [
    "Sharma", "Reddy", "Iyer", "Nair", "Gupta", "Shetty", "Rao", "Menon",
    "Kulkarni", "Desai", "Bhat", "Pillai", "Verma", "Joshi", "Mehta", "Khan",
    "Dsouza", "Chandran", "Patil", "Hegde",
]

CANCEL_REASONS_RIDER = [
    "changed plans", "booked by mistake", "driver too far", "found another ride",
    "waiting too long", "", "price too high", "meeting got cancelled",
]
CANCEL_REASONS_DRIVER = [
    "vehicle breakdown", "rider unreachable", "traffic blocked", "end of shift",
    "", "wrong pickup location", "personal emergency",
]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30") if dt else ""


def pick_hour(rng, is_weekend):
    """Demand curve: morning and evening peaks, heavier and later at weekends."""
    if is_weekend:
        weights = [3, 2, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 7, 6, 6, 6, 7, 9, 11, 13, 14, 13, 10, 6]
    else:
        weights = [1, 1, 1, 1, 1, 2, 5, 9, 14, 13, 8, 6, 6, 6, 6, 7, 9, 13, 15, 12, 8, 5, 3, 2]
    return rng.choices(range(24), weights=weights, k=1)[0]


def make_people(rng, anchor):
    riders, drivers = [], []
    for i in range(1, N_RIDERS + 1):
        riders.append({
            "rider_id": i,
            "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "joined_at": iso(anchor - timedelta(days=rng.randint(91, 1400), minutes=rng.randint(0, 1439))),
            "city": "Bengaluru",
            "rating": round(rng.uniform(4.1, 5.0), 2),
        })
    for i in range(1, N_DRIVERS + 1):
        drivers.append({
            "driver_id": i,
            "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "joined_at": iso(anchor - timedelta(days=rng.randint(95, 1800), minutes=rng.randint(0, 1439))),
            "city": "Bengaluru",
            "rating": round(rng.uniform(3.8, 5.0), 2),
            "vehicle_type": rng.choices(["hatchback", "sedan", "suv"], weights=[5, 4, 2], k=1)[0],
        })
    return riders, drivers


def choose_status(rng, bad_weather):
    if bad_weather:
        # Storm week: drivers bail, riders give up waiting.
        return rng.choices(
            ["completed", "cancelled_by_rider", "cancelled_by_driver", "no_show", "disputed"],
            weights=[52, 22, 18, 5, 3], k=1)[0]
    return rng.choices(
        ["completed", "cancelled_by_rider", "cancelled_by_driver", "no_show", "disputed"],
        weights=[77, 11, 6, 4, 2], k=1)[0]


def fare_for(distance_km, duration_min, airport):
    fare = BASE_FARE + PER_KM * distance_km + PER_MIN * duration_min
    if airport:
        fare += AIRPORT_SURCHARGE
    return round(max(fare, MIN_FARE), 2)


def generate(anchor):
    rng = random.Random(SEED)
    riders, drivers = make_people(rng, anchor)

    # One week of bad weather, 38-44 days before the anchor.
    bad_start = anchor - timedelta(days=44)
    bad_end = anchor - timedelta(days=38)

    rides = []
    for n in range(1, N_RIDES + 1):
        day_offset = rng.randint(0, DAYS - 1)
        day = anchor - timedelta(days=day_offset)
        is_weekend = day.weekday() >= 5
        hour = pick_hour(rng, is_weekend)
        requested_at = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)

        bad_weather = bad_start <= requested_at <= bad_end
        status = choose_status(rng, bad_weather)

        pickup = rng.choice(LOCALITIES)
        dropoff = rng.choice([x for x in LOCALITIES if x != pickup])
        airport = rng.random() < 0.06
        if airport:
            if rng.random() < 0.5:
                dropoff = AIRPORT
            else:
                pickup = AIRPORT

        distance_km = round(rng.uniform(22.0, 38.0) if airport else rng.uniform(1.2, 18.0), 2)
        # Bengaluru traffic: ~16-26 km/h effective.
        duration_min = int(distance_km / rng.uniform(0.27, 0.45))
        fare = fare_for(distance_km, duration_min, airport)

        driver_id = rng.randint(1, N_DRIVERS)
        started_at = completed_at = cancelled_at = None
        cancellation_reason = ""

        if status == "completed":
            started_at = requested_at + timedelta(minutes=rng.randint(2, 11))
            completed_at = started_at + timedelta(minutes=duration_min)
        elif status == "disputed":
            started_at = requested_at + timedelta(minutes=rng.randint(2, 11))
            completed_at = started_at + timedelta(minutes=duration_min)
        elif status == "cancelled_by_rider":
            cancelled_at = requested_at + timedelta(seconds=rng.randint(20, 1500))
            cancellation_reason = rng.choice(CANCEL_REASONS_RIDER)
            fare = 0.0
            if rng.random() < 0.35:
                driver_id = None  # cancelled before anyone was assigned
        elif status == "cancelled_by_driver":
            cancelled_at = requested_at + timedelta(seconds=rng.randint(40, 1200))
            cancellation_reason = rng.choice(CANCEL_REASONS_DRIVER)
            fare = 0.0
        elif status == "no_show":
            # Driver arrived, waited, charged the no-show fee.
            started_at = None
            cancelled_at = requested_at + timedelta(minutes=rng.randint(9, 20))
            cancellation_reason = "rider did not arrive"
            fare = 60.0

        rides.append({
            "ride_id": n,
            "rider_id": rng.randint(1, N_RIDERS),
            "driver_id": driver_id if driver_id else "",
            "requested_at": iso(requested_at),
            "started_at": iso(started_at),
            "completed_at": iso(completed_at),
            "pickup": pickup,
            "dropoff": dropoff,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "fare_amount": fare,
            "currency": CURRENCY,
            "status": status,
            "cancelled_at": iso(cancelled_at),
            "cancellation_reason": cancellation_reason,
            "_requested_dt": requested_at,
        })

    # ---- deliberate mess (see week2/facilitator/trap_key.md) ----
    completed = [r for r in rides if r["status"] == "completed"]

    # (a) two rides where completed_at precedes started_at
    for r in rng.sample(completed, 2):
        s = datetime.strptime(r["started_at"][:19], "%Y-%m-%dT%H:%M:%S")
        r["completed_at"] = iso(s - timedelta(minutes=rng.randint(3, 14)))

    # (b) two near-duplicate pairs, seconds apart (double-tap on the book button)
    dupes = []
    for r in rng.sample(completed, 2):
        d = dict(r)
        d["ride_id"] = N_RIDES + len(dupes) + 1
        shift = timedelta(seconds=rng.randint(4, 19))
        d["requested_at"] = iso(r["_requested_dt"] + shift)
        d["_requested_dt"] = r["_requested_dt"] + shift
        d["status"] = "cancelled_by_rider"
        d["started_at"] = ""
        d["completed_at"] = ""
        d["cancelled_at"] = iso(r["_requested_dt"] + shift + timedelta(seconds=31))
        d["cancellation_reason"] = "booked by mistake"
        d["fare_amount"] = 0.0
        dupes.append(d)
    rides.extend(dupes)

    # (c) blank out cancellation_reason on a handful of cancellations
    cancels = [r for r in rides if r["status"].startswith("cancelled")]
    for r in rng.sample(cancels, min(9, len(cancels))):
        r["cancellation_reason"] = ""

    # ---- refunds: ~3% of rides, stratified so each reason actually occurs ----
    # Refunds are not uniform over rides: a disputed ride is far likelier to be
    # refunded than a completed one. Sample per status, then merge.
    by_status = collections.defaultdict(list)
    for r in rides:
        by_status[r["status"]].append(r)

    refunds = []
    n_refunds = int(round(len(rides) * 0.03))
    plan = [
        ("disputed", 0.55),             # most disputes end in a refund
        ("cancelled_by_driver", 0.12),  # driver bailed -> goodwill refund
        ("no_show", 0.22),              # rider contested the no-show charge
        ("completed", 0.012),           # service complaints on completed rides
    ]
    chosen = []
    for status_name, rate in plan:
        pool = by_status.get(status_name, [])
        k = min(len(pool), int(round(len(pool) * rate)))
        chosen.extend(rng.sample(pool, k))
    # trim or top up to land on ~3%
    rng.shuffle(chosen)
    if len(chosen) > n_refunds:
        chosen = chosen[:n_refunds]
    else:
        spare = [r for r in by_status["completed"] if r not in chosen]
        chosen.extend(rng.sample(spare, n_refunds - len(chosen)))

    # 7 of them land outside the 7-day window the refunds policy claims is mandatory.
    late_ids = set(r["ride_id"] for r in rng.sample(chosen, 7))

    for i, r in enumerate(sorted(chosen, key=lambda x: x["ride_id"]), start=1):
        if r["status"] == "cancelled_by_driver":
            reason = "driver_cancelled"
        elif r["status"] == "no_show":
            reason = "no_show_contested"
        elif r["status"] == "disputed":
            reason = "service_issue"
        else:
            reason = rng.choices(["service_issue", "goodwill"], weights=[3, 2], k=1)[0]

        base = float(r["fare_amount"]) or 60.0
        amount = round(base if rng.random() < 0.55 else base * rng.uniform(0.3, 0.7), 2)

        if r["ride_id"] in late_ids:
            delay = timedelta(days=rng.randint(14, 45), hours=rng.randint(0, 23))
        else:
            delay = timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 23))

        refunds.append({
            "refund_id": i,
            "ride_id": r["ride_id"],
            "amount": amount,
            "reason": reason,
            "issued_at": iso(r["_requested_dt"] + delay),
            "issued_by": rng.choices(
                ["auto", "agent:priya.n", "agent:rahul.m", "agent:fatima.k"],
                weights=[5, 2, 2, 1], k=1)[0],
        })

    for r in rides:
        r.pop("_requested_dt", None)

    return riders, drivers, rides, refunds


def to_csv(rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


RIDER_FIELDS = ["rider_id", "name", "joined_at", "city", "rating"]
DRIVER_FIELDS = ["driver_id", "name", "joined_at", "city", "rating", "vehicle_type"]
RIDE_FIELDS = ["ride_id", "rider_id", "driver_id", "requested_at", "started_at", "completed_at",
               "pickup", "dropoff", "distance_km", "duration_min", "fare_amount", "currency",
               "status", "cancelled_at", "cancellation_reason"]
REFUND_FIELDS = ["refund_id", "ride_id", "amount", "reason", "issued_at", "issued_by"]


def build(anchor_str="2026-10-05"):
    anchor = datetime.strptime(anchor_str, "%Y-%m-%d").replace(hour=23, minute=59, second=0)
    riders, drivers, rides, refunds = generate(anchor)
    return {
        "riders.csv": to_csv(riders, RIDER_FIELDS),
        "drivers.csv": to_csv(drivers, DRIVER_FIELDS),
        "rides.csv": to_csv(rides, RIDE_FIELDS),
        "refunds.csv": to_csv(refunds, REFUND_FIELDS),
    }, (riders, drivers, rides, refunds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor", default="2026-10-05")
    parser.add_argument("--outdir", default="data")
    args = parser.parse_args()
    files, _ = build(args.anchor)
    import os
    os.makedirs(args.outdir, exist_ok=True)
    for name, content in files.items():
        with open(os.path.join(args.outdir, name), "w") as f:
            f.write(content)
        print(f"wrote {args.outdir}/{name} ({len(content)} bytes)")


if __name__ == "__main__":
    main()