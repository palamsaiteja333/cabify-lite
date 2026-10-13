# No-Show Policy

**Document owner:** Customer Operations
**Version:** 2.1
**Effective date:** 1 August 2026

---

## 1. What a no-show is

A **no-show** is recorded when the Driver arrives at the pickup point, waits the full waiting
period, is unable to reach the Rider, and ends the Booking without the Rider having boarded.

A no-show is distinct from a Rider cancellation. In a cancellation the Rider acts; in a no-show the
Rider does not act and the Driver ends the Booking after waiting.

In our systems a no-show is stored with the ride status `no_show`. It is **not** stored as
`cancelled_by_rider`, and reports that group the two together will overstate rider cancellations.

---

## 2. The waiting period

| Pickup type | Driver must wait |
|---|---|
| Standard pickup | **5 minutes** from arrival |
| Airport pickup | **10 minutes** from arrival |

2.1 The waiting period begins when the Driver's recorded position is within 100 metres of the
pickup point and the Driver marks arrival in the application.

2.2 The application notifies the Rider on Driver arrival and again one minute before the waiting
period expires.

2.3 A Driver who ends a Booking before the waiting period has elapsed has not recorded a valid
no-show, and any charge raised is reversed on request.

---

## 3. The charge

3.1 Where a valid no-show is recorded, the Rider is charged a flat **no-show fee of ₹60**.

3.2 The fee is flat. It does not vary by distance, by vehicle type, by time of day, or by surge
multiplier. The same ₹60 is charged on a 2 km booking and on a 30 km airport booking.

3.3 Waiting charges from the Pricing Sheet do **not** apply in addition to the no-show fee. The
₹60 is the whole charge.

3.4 Of the no-show fee, the Driver receives a compensation share in accordance with the Driver
Handbook.

---

## 4. Contesting a no-show charge

4.1 A Rider may contest a no-show charge **within 48 hours** of the Ride.

4.2 Contest through **Help with this ride → I was charged a no-show fee**.

4.3 The assessment considers:

- whether the Driver marked arrival at the correct pickup point;
- whether the full waiting period elapsed between arrival and ending the Booking;
- whether the application successfully delivered the arrival notification;
- any evidence supplied by the Rider.

4.4 Where the contest succeeds, the full ₹60 is refunded under the Refunds & Cancellations Policy
with reason code `no_show_contested`.

4.5 Where it fails, the charge stands and the decision is final unless escalated under clause 10.5
of the Terms & Conditions.

---

## 5. Common situations

| Situation | Treatment |
|---|---|
| Rider at a different gate of a large building | No-show stands if the Driver waited at the pinned location |
| Rider's phone unreachable throughout | No-show stands |
| Driver pinned the wrong location | Charge reversed |
| Driver waited 3 minutes at a standard pickup and left | Not a valid no-show; charge reversed |
| Flight delayed; Rider did not arrive at the airport pickup | No-show stands — the 10-minute airport period is the whole allowance |

---

## 6. Related documents

- **Refunds & Cancellations Policy** — how an approved reversal is actually paid.
- **Pricing Sheet** — waiting charges that apply to Rides that do proceed.
- **Driver Handbook** — Driver obligations on waiting and marking arrival.

---

*End of document. Internal reference: OPS-NS-2.1.*