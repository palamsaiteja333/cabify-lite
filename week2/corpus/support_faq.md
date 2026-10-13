# Support Team FAQ — internal cheat sheet

> **Heads up:** this is the support floor's own scratch document, not a policy. It exists so new
> agents can answer the common stuff fast without digging through the policy PDFs.
>
> **Last updated: 11 March 2025** by Priya N. *(TODO: someone please re-check against the new
> policy docs, a few of these numbers are from the old pricing round — PN)*

---

## The questions we get all day

### "Can I cancel for free?"

Yes, if they're quick about it. They get **5 minutes** after the driver accepts before anything is
charged. After that it's a **₹25** cancellation fee.

Honestly most people are well inside 5 minutes so just tell them yes and move on.

### "The driver cancelled on me — am I charged?"

No. Never. If they're showing a charge, it's almost always a pre-auth hold and it drops off by
itself. If it's a real charge, raise a refund with reason `driver_cancelled` and it goes through
automatically.

### "What's the no-show fee?"

**₹50.** Driver waits **3 minutes** and then can end the trip.

If they want to contest it, they've got 48 hours. We win most of these if the driver marked arrival
properly, so check the GPS first before you promise anything.

### "How long until I get my refund?"

Tell them **within 7 days**, that's the line. Card refunds then take another few days to actually
show up because of the bank, so if they're calling on day 8 about a card, it's the bank, not us.

### "Why was my fare higher than the estimate?"

Usual suspects, in order of how often it's actually the cause:

1. Traffic — the per-minute charge ran up.
2. They added a stop.
3. Surge was on and they tapped through without reading it.
4. Tolls.

Pull up the GPS trace before agreeing to anything. Half the "the driver took a longer route"
complaints are the app's own route.

### "Can I get a refund on a ride from last month?"

No. Seven days, same as everything else.

### "Who cancels more, riders or drivers?"

Drivers, by a mile. Riders mostly just don't show up rather than cancelling properly. If someone
asks for numbers, say most cancellations on the platform are driver-side and move on — we've never
actually published a figure.

---

## Stuff that trips up new agents

- **No-show is not a rider cancellation.** Different status, different fee, different contest
  window. If you log it wrong, the refund tooling does the wrong thing.
- **Partial refunds are normal.** You don't have to give the whole fare back. For a route dispute,
  refund the difference, not the trip.
- **Minimum fare always applies** on a completed trip. Short trips that look overcharged usually
  aren't.
- **Goodwill credits cap out.** Don't go above ₹100 without a team lead.
- **Airport pickups have a longer wait** than normal ones. Don't quote the standard number for an
  airport no-show.

---

## Escalate, don't improvise

Escalate to a team lead if:

- the rider is alleging unsafe driving or harassment — this goes to Safety immediately, not to a
  refund queue;
- the amount is above ₹1,000;
- it's a second refund request from the same rider this month;
- there's a mismatch between what the policy says and what the system actually did. *(This has come
  up a few times with refund dates and nobody has got to the bottom of it. Log it, escalate it,
  don't argue with the rider about it.)*

---

## Canned lines that work

> "I can see the driver marked arrival at 14:32 and ended the trip at 14:38, so the full waiting
> period was observed. I'm not able to reverse the fee on this one."

> "I've approved a partial refund of ₹X, which is the difference between what you were charged and
> what the route should have cost. You'll see it back on the card you paid with."

> "That's outside the window I can refund in, but let me check whether there's anything else on the
> account I can do."

---

*Not a policy document. If a rider pushes back, go to the real policy. — Support floor, Bengaluru*