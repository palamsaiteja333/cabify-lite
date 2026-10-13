# Week 2 datasets

Everything you need to start Week 2. Four datasets, three of them in this folder.

```
week2/
  corpus/          Dataset 1 — six policy documents (supplied)
  seed/            Dataset 2 — the rides database generator + CSVs (supplied, regenerable)
  evals/           Dataset 3 — the 20-question eval set (supplied; extend it, don't weaken it)
  facilitator/     Mentor's answer key — do not open until the review session
```

Dataset 4 is the `spans` table you built in Week 1. No new work; it just gets a second tenant.

---

## Dataset 1 — The policy corpus (`corpus/`)

Six documents written the way a real small company writes them: different owners, different
versions, inconsistent formatting, overlapping scope, one document that nobody has updated.

| File | What it is | Owner in-universe |
|---|---|---|
| `terms_and_conditions.md` | The legal T&Cs — eligibility, booking, fares, conduct, liability, disputes | Legal & Compliance |
| `refunds_and_cancellations.md` | The authoritative refund and cancellation policy | Customer Operations |
| `no_show_policy.md` | What a no-show is, waiting periods, the fee, how to contest it | Customer Operations |
| `pricing_sheet.pdf` | Every rate, mostly as tables — base fare, surcharges, surge bands, waiting charges | Revenue Operations |
| `driver_handbook.md` | The driver-side rules: allocation, cancellations, ratings, payouts | Driver Operations |
| `support_faq.md` | The support floor's informal cheat sheet | Support team |

**Read none of them closely before you build.** Ingest them, then let your system and your eval
set tell you what is in them. Reading ahead is how you end up tuning for answers you already know.

**There are four traps in here.** You are told that much deliberately — a real corpus has them and
nobody warns you, but on week two of learning this you get to know they exist. You are not told
what they are. If you finish the week having found two of the four, that is a good week.

The documents are internally consistent with the seeded data **except where they are not**, and
the exceptions are the point.

---

## Dataset 2 — The rides database (`seed/`)

```
seed/
  generate_data.py   deterministic generator, stdlib only
  schema.sql         tables, constraints, indexes
  load.sql           \copy the CSVs in
  Makefile.snippet   make seed / make seed-check targets
  data/*.csv         pre-generated, so you can start without running anything
```

**Shape:** 2,002 rides over the 90 days ending 2026-10-05, 420 riders, 95 drivers, 60 refunds.
Single currency (INR), single city (Bengaluru).

Run it:

```bash
python3 week2/seed/generate_data.py --anchor 2026-10-05 --outdir week2/seed/data
psql "$DATABASE_URL" -f week2/seed/schema.sql
cd week2/seed && psql "$DATABASE_URL" -v dir="$PWD/data" -f load.sql
```

Or copy `Makefile.snippet` into your root `Makefile` and run `make seed`.

**It is deterministic.** `seed = 20260101`. Re-run it as often as you like and you get byte-identical
CSVs, which is what makes the eval set's expected numbers meaningful and lets anyone reproduce your
demo. **If you change the seed or the anchor date, every expected number in `evals/questions.yaml`
becomes wrong** and you must regenerate them.

### What was made realistic on purpose

- **Status mix** reflecting a real marketplace: 75.2% completed, 12.9% rider-cancelled,
  6.8% driver-cancelled, 3.4% no-show, 1.6% disputed.
- **A demand curve, not a uniform distribution.** Morning and evening peaks on weekdays; later and
  heavier at weekends. 30% of rides fall on the 29% of days that are weekends.
- **One bad week.** 22–28 August 2026 has a 32.6% cancellation rate against an 18.5% baseline.
  Nothing in the data says "storm" — you have to see the shape.
- **Fares computed, not random.** Base ₹40 + ₹12/km + ₹1.50/min, ₹60 minimum, ₹75 airport
  surcharge — matching `corpus/pricing_sheet.pdf` exactly, so a fare you recompute from the
  document should match the stored one.
- **Refunds that are not uniform over rides.** A disputed ride is far likelier to be refunded than
  a completed one. 35 of 60 were issued automatically; the rest by named agents.
- **Partial refunds**, because not every refund is the full fare.

### What was made messy on purpose

Real data always has these, and your SQL has to either handle them or you have to know they exist:

- two rides where `completed_at` precedes `started_at`;
- two near-duplicate bookings seconds apart — someone double-tapped the button;
- 52 cancellations with a blank `cancellation_reason`;
- 95 rides with a null `driver_id`, cancelled before a driver was allocated.

Nobody will tell you these are there. Your averages will.

---

## Dataset 3 — The eval set (`evals/questions.yaml`)

20 questions: **8 policy, 6 data, 4 hybrid, 2 unanswerable**. Each one carries its expected answer,
its expected source document, and where relevant the exact number the SQL path must produce.

Normally you write this yourself and the mentor reviews it. It is supplied this week for one
reason: **so that it exists before you start tuning.** Writing your eval set after you have tuned
your retriever is the single easiest way to fool yourself in an AI project — you unconsciously
write the questions your system already answers, and the exercise becomes theatre.

Rules:

- **Extend it freely.** Add every question you think of while building. More coverage is better.
- **Do not weaken it.** If a question fails, fix the system, not the question. Edit a question only
  if it is genuinely ambiguous or wrong about the source material — and say so in the review.
- **Score retrieval and answers separately.** `retrieval_hit` asks whether the right chunk came
  back. `answer_correct` asks whether the answer is right. They fail independently and they have
  completely different fixes. One blended number hides both.
- **The two `unanswerable` questions are the most important in the set.** A system that invents a
  confident pet policy will invent a confident refund policy.

---

## Dataset 4 — The spans table

Already exists, from Week 1. Your Week 2 retrieval and generation telemetry lands in the same
table using the OpenTelemetry GenAI semantic conventions.

This is where you find out whether you *designed* that schema or just made it work. A schema's
first use case is free; the second one is the test. If you have to alter the table to fit this
week's spans, that is not a failure — but notice it, and be able to say what you would do
differently.

---

## Before you write a single line of code

1. `make seed` and confirm the row counts.
2. Open exactly one corpus document — `support_faq.md` — for two minutes, to get a feel for the
   register. Leave the other five alone.
3. Read `evals/questions.yaml` top to bottom. That file is your specification.