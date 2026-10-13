# Week 2 — Ask the Right Source: RAG Over Policy Docs and the Rides Database

Week 2 takes the running Cabify-Lite system and teaches it to answer questions - and then proves the answers are good with numbers instead of vibes. A system is only useful when it knows the difference between a rule and a fact. Documents answer "what is the rule?", databases answer "what actually happened?" - confusing the two is the most common and most expensive mistake in AI projects. You will ingest a policy corpus into pgvector, build an LCEL chain that answers with citations, add a router that sends policy questions to retrieval and data questions to SQL, write an eval set before you tune anything, and carry the Week 1 tracing forward so every retrieval and generation shows up as a span.

---

# Week 2 Problem Statement — "Grounded Answers": Make the System Answer Questions, and Prove the Answers Are Good

**Theme:** Your Week-1 system *runs* and is *observable*. Now make it *answer questions* — about policy documents it has never seen before, and about the ride data already in your database — and then prove the answers are good with **numbers instead of vibes**.

The week's core insight, and the single most useful sentence you will ever say to a customer:

> **RAG is for unstructured text. SQL is for facts. A real system needs both, and something in front that decides which one to use.**

Everything below grows on the Week-1 repo. Same `docker-compose.yml`, same Postgres, same OTel Collector, same Tempo/Prometheus/Grafana. Nothing is thrown away.

---

## In plain words — what you're actually building

Forget the jargon for a minute. Here is the whole week in ordinary language.

Last week you built a small ride-booking backend and made it observable. This week you bolt a **question-answering endpoint** onto it.

Somebody sends a question as plain English. Your system has to work out where the answer lives, go and get it, and write the answer back — with a pointer to where it came from.

There are only ever **two places an answer can live**:

1. **In a document.** "What's our cancellation policy?" The answer is a paragraph someone wrote in a PDF. No database query will ever produce it.
2. **In the database.** "How many refunds did we issue last month?" The answer is a number nobody has written down anywhere — it has to be *calculated* from rows.

Some questions need both at once: *"What's our no-show policy, and how many no-show charges did we apply in September?"* First half is a document. Second half is a `SELECT`.

So your system needs three pieces:

- **A way to search documents by meaning, not keywords.** You can't use `LIKE '%cancel%'` — someone asking "do I get my money back if I call off the ride?" never uses the word "cancel". So you convert every chunk of every document into a list of numbers (an **embedding**) that represents its meaning, store those numbers in Postgres, and at question time convert the question into numbers the same way and find the closest chunks. That's all "vector search" means: *find the text whose meaning-numbers are nearest to my question's meaning-numbers.*
- **A way to answer from the database.** Ordinary SQL — except the query is chosen or written by the model instead of by you.
- **A traffic cop in front of both,** which reads the question and decides: documents, database, or both. This is the **router**.

Then — and this is the part most people skip — you have to **prove it works**. "I tried five questions and they looked fine" is not proof. You write down 20 questions with their correct answers *before* you start tuning, run them all automatically, and get a score. Then when you change something, you re-run and see whether the score went up or down. That's the difference between engineering and guessing.

Finally: every step gets **traced**, exactly like last week. How long did the search take? How long did the model take? How many tokens did it cost? Those go into the same spans table you built in Week 1, and you answer questions about your own system with SQL.

**Two sentences to remember for the rest of your career:**

> Documents answer "what is the rule?". Databases answer "what actually happened?". Confusing the two is the most common and most expensive mistake in AI projects.

---

## Tech stack to learn before starting

Same rule as Week 1: you don't need mastery, you need enough to build and to look things up fast.

**Must know (blockers if missing):**

| Tech | What to learn | Depth needed |
|------|---------------|--------------|
| **Embeddings & vector search** | What an embedding is, cosine vs L2 distance, why similar text lands near similar text, what "top-k" means | Read one explainer + the Pinecone/Weaviate "what are embeddings" primer. No maths required, but you must be able to explain it to a non-technical customer in 60 seconds |
| **pgvector** | Install the extension, `vector(N)` column type, `<=>` cosine operator, creating an HNSW or IVFFlat index | Postgres docs + the pgvector README. Run one query by hand in `psql` before writing any Python |
| **Chunking** | Fixed-size vs recursive vs structure-aware splitting, overlap, why chunk size changes answer quality | LangChain's text-splitter docs. Understand *why* 500 tokens with 50 overlap is a default, not a law |
| **RAG as a pattern** | retrieve → augment prompt → generate; where it fails (missing docs, bad chunks, contradiction, hallucination) | One good overview article. You should be able to draw the pipeline on a whiteboard |
| **LangChain LCEL** | `Runnable`, the `\|` pipe, `RunnablePassthrough`, `RunnableBranch`, prompt templates, output parsers, `.invoke()` vs `.stream()` | LangChain "LCEL" docs + one tutorial. This is the *only* framework you need this week |
| **Structured output** | Pydantic models + `with_structured_output()`, and what to do when a model returns malformed JSON | LangChain structured-output docs |
| **Prompting basics** | System vs user message, few-shot, instructing a model to say "I don't know", citation instructions | One read-through of any decent prompting guide |
| **Ollama** (or an API key) | Pull a model, run it, call the OpenAI-compatible endpoint, pull an embedding model | 30 minutes. See "LLM provider" below |

**Concepts to arrive with (you'll apply them during the build):**

| Tech | What to learn | Depth needed |
|------|---------------|--------------|
| **Evaluation of LLM systems** | Retrieval hit-rate vs answer correctness; why "it looked right" is not a measurement | One article on RAG evaluation |
| **OTel GenAI semantic conventions** | The standard attribute names for LLM spans (`gen_ai.system`, `gen_ai.request.model`, token counts) | Skim the spec — you'll use a handful of attribute names |
| **LangGraph** (teaser only) | `StateGraph`, state, nodes, edges — what a graph is, conceptually | A 20-minute skim. You only need it for the stretch task; Week 3 is where it gets real |

If more than three "must know" items feel shaky, fix those first. Budget a weekend.

---

## LLM provider: your choice, but the code must not care

Everything this week must run behind a single config switch:

```
LLM_PROVIDER=ollama | openai | anthropic
```

One `llm.py` factory returns the chat model and the embedding model; nothing downstream knows or cares which provider is active.

| Provider | Chat model | Embedding model | Cost |
|---|---|---|---|
| `ollama` (baseline) | `qwen2.5:7b-instruct` or `llama3.1:8b` | `nomic-embed-text` | Free. Needs ~16GB RAM |
| `openai` | `gpt-4o-mini` | `text-embedding-3-small` | A few dollars for the week |
| `anthropic` | any Claude model | **Ollama's `nomic-embed-text`** — Anthropic has no embeddings API | A few dollars for the week |

**Grading baseline is Ollama**, so cost is never a blocker and no deliverable depends on a budget. A hosted key is an optional accelerant, not a requirement.

Two things to internalise while building this:

1. **A local 7B model will occasionally produce a malformed tool call or ignore your JSON schema, and it will be slower.** Do not "fix" this by switching to a hosted API. Handling bad model output, retries, and timeouts *is* the lesson — it is exactly what breaks at customer sites.
2. **The embedding model is not hot-swappable.** Change it and every vector in your database becomes meaningless — you must re-index. Find this out deliberately (see Planted Failures), not in front of a customer.

---

## The scenario (read this like a customer brief)

> Cabify-Lite is back, and this time it's the support team. They're drowning. The same questions arrive all day:
>
> - *"What's your cancellation policy?"*
> - *"Am I charged if the driver cancels?"*
> - *"What counts as a no-show?"*
> - *"How many refunds did we issue last month?"*
> - *"What's our no-show policy, and how many no-show charges did we actually apply in September?"*
>
> They hand you a folder of policy documents — terms & conditions, a refunds policy, a driver handbook, a pricing sheet, an internal support FAQ — and say: *"Can your system just answer these?"*
>
> They do **not** know that some of those questions are about documents and some are about data. That's your job to figure out — and to explain back to them.

Your deliverable is an `/ask` endpoint on the Week-1 `rides-api` that answers all of the above, with citations, and that you can *prove* is good.

---

## Datasets you need

You need **four** datasets this week. **Three of them are already in the repo** — you don't generate anything or wait for anything. The fourth is the spans table you built in Week 1.

```
week2/
  corpus/          Dataset 1 — six policy documents
  seed/            Dataset 2 — the rides database: generator, schema, loader, CSVs
  evals/           Dataset 3 — the 20-question eval set
  facilitator/     the answer key — don't open it
```

Get all four in place before you write a line of code. A missing dataset is the most common reason this week stalls on day one.

### Dataset 1 — The policy document corpus (unstructured) — *in `week2/corpus/`*

Six documents, written as a real small company writes them: different owners, different version numbers, inconsistent formatting, overlapping scope, and one document nobody has updated since 2025.

| File | What's in it | Approx size |
|---|---|---|
| `terms_and_conditions.md` | The legal T&Cs — rider obligations, liability, payment terms, dispute process | ~6 pages |
| `refunds_and_cancellations.md` | The refund policy: cancellation windows, who pays what, refund timelines, exceptions | ~4 pages |
| `no_show_policy.md` | What counts as a no-show, waiting times, the charge, how to contest it | ~2 pages |
| `pricing_sheet.pdf` | Base fares, per-km rates, surge bands, waiting charges — **mostly tables** | ~2 pages |
| `driver_handbook.md` | Driver-side rules: cancellations, ratings, conduct, payouts | ~5 pages |
| `support_faq.md` | The internal support team's own cheat-sheet, written informally | ~3 pages |

**Traps deliberately planted in this corpus** (don't go looking for them in advance — find them through the build):
- One policy statement that **contradicts what the database actually shows**.
- A **pricing table that naive fixed-size chunking will cut in half**, producing half-right answers.
- At least one question in your eval set whose answer is **genuinely not in any document** — the system must say so rather than invent one.
- Two documents that **partially overlap and slightly disagree** (the FAQ is out of date relative to the policy doc). Which one should win, and how would you know?

**Read none of them closely before you build.** Ingest them and let your system and the eval set tell you what's inside. Reading ahead is how you end up tuning for answers you already know. The one exception: open `support_faq.md` for two minutes to get a feel for the register, then leave the other five alone.

You're told the four traps exist — in a real engagement nobody tells you that — but you're not told which document holds which. Find two of the four and it's been a good week.

### Dataset 2 — The rides database (structured) — *in `week2/seed/`*

Extends your Week-1 schema. **2,002 rides over the 90 days ending 2026-10-05**, 420 riders, 95 drivers, 60 refunds. Single currency (INR), single city (Bengaluru).

```
seed/
  generate_data.py   deterministic generator, stdlib only
  schema.sql         tables, constraints, indexes
  load.sql           \copy the CSVs in
  Makefile.snippet   make seed / make seed-check
  data/*.csv         pre-generated, so you can start without running anything
```

```bash
python3 week2/seed/generate_data.py --anchor 2026-10-05 --outdir week2/seed/data
psql "$DATABASE_URL" -f week2/seed/schema.sql
cd week2/seed && psql "$DATABASE_URL" -v dir="$PWD/data" -f load.sql
```

**`rides`** (extend your Week-1 table)

| Column | Type | Notes |
|---|---|---|
| `ride_id` | uuid / serial | |
| `rider_id` | int | FK to `riders` |
| `driver_id` | int | nullable — no driver assigned on some cancellations |
| `requested_at` | timestamptz | |
| `started_at` | timestamptz | null if never started |
| `completed_at` | timestamptz | null unless completed |
| `pickup`, `dropoff` | text | |
| `distance_km` | numeric | |
| `fare_amount` | numeric | |
| `currency` | text | keep it single-currency this week; mixed currency is a Week-3 trap |
| `status` | text | `completed`, `cancelled_by_rider`, `cancelled_by_driver`, `no_show`, `disputed` |
| `cancelled_at` | timestamptz | null unless cancelled |
| `cancellation_reason` | text | nullable, free text — some rows blank |

**`refunds`** (new)

| Column | Type | Notes |
|---|---|---|
| `refund_id` | uuid / serial | |
| `ride_id` | FK | |
| `amount` | numeric | sometimes partial, not always the full fare |
| `reason` | text | `driver_cancelled`, `service_issue`, `no_show_contested`, `goodwill` |
| `issued_at` | timestamptz | |
| `issued_by` | text | `auto` or an agent name |

**`riders`** and **`drivers`** — minimal: id, name, joined_at, city, rating.

**What's realistic about it, on purpose:**
- **Status mix of a real marketplace:** 75.2% completed, 12.9% rider-cancelled, 6.8% driver-cancelled, 3.4% no-show, 1.6% disputed.
- **A demand curve, not a uniform distribution.** Morning and evening peaks on weekdays, later and heavier at weekends — 30% of rides on the 29% of days that are weekends.
- **One bad week.** 22–28 August 2026 runs a 32.6% cancellation rate against an 18.5% baseline. Nothing in the data says "storm". You have to see the shape.
- **Fares are computed, not random.** ₹40 base + ₹12/km + ₹1.50/min, ₹60 minimum, ₹75 airport surcharge — matching `corpus/pricing_sheet.pdf` exactly. A fare you recompute from the document should match the stored one. When it doesn't, that's a finding.
- **Refunds aren't uniform over rides.** A disputed ride is far likelier to be refunded than a completed one. 35 of 60 were issued automatically, the rest by three named agents, and plenty are partial rather than full.
- **Some refunds deliberately fall outside the window the policy document states.** That's the planted contradiction, and your system has to handle the clash rather than picking a side.

**What's messy, on purpose:** two rides where `completed_at` precedes `started_at`; two near-duplicate bookings seconds apart (someone double-tapped the button); 52 cancellations with a blank `cancellation_reason`; 95 rides with a null `driver_id`, cancelled before allocation. Nobody will tell you these are there — your averages will. Handle them or know they're there; discovering them live in the demo is the failure mode.

**It is deterministic.** `seed = 20260101`, anchor date `2026-10-05`. Re-run it as often as you like and you get byte-identical CSVs — that's what makes the eval set's expected numbers meaningful and lets anyone reproduce your demo. **Change the seed or the anchor and every expected number in `evals/questions.yaml` becomes wrong**, and you own regenerating them.

### Dataset 3 — The eval set (20 Q/A pairs) — *in `week2/evals/questions.yaml`*

A `evals/questions.yaml` file. Each entry:

```yaml
- id: q07
  question: "What's our no-show policy, and how many no-show charges did we apply in September?"
  type: hybrid            # policy | data | hybrid | unanswerable
  expected_answer: "..."   # the correct answer in plain English
  expected_source: no_show_policy.md     # for policy/hybrid
  expected_sql_result: 47                # for data/hybrid
```

Composition: **8 policy, 6 data, 4 hybrid, 2 unanswerable**. Every `expected_sql_result` is the real number from the seeded database, computed before you build anything.

Normally you write this yourself and I review it. It's supplied this week for exactly one reason: **so that it exists before you start tuning.** Write an eval set after tuning your retriever and you unconsciously write the questions your system already answers — the whole exercise becomes theatre. This is the single easiest way to fool yourself in an AI project, and it happens constantly in the real world.

Three rules:
- **Extend it freely.** Add every question you think of while building. More coverage is strictly better.
- **Don't weaken it.** If a question fails, fix the system, not the question. Edit a question only if it's genuinely ambiguous or wrong about the source material — and say so at review.
- **The two `unanswerable` questions are the most important in the set.** A system that invents a confident pet policy will invent a confident refund policy.

### Dataset 4 — The spans table (already exists from Week 1)

No new work — your Week-2 telemetry lands in the **same** table. But note: it is about to meet its second use case, and that's where you find out whether you designed it or just made it work. See Part 6.

---

## Step 0 — The regression gate (do this first, 20 minutes)

Before you add a single new thing:

- Cold `docker compose up` from a clean clone.
- `curl` the Week-1 endpoints. Make a `/quote` request.
- Confirm the trace still lands in **Tempo** *and* in your Week-1 **spans table**.

If anything rotted in the week off, fix it before building. This is not busywork — returning to a stack after a week away and finding it broken is one of the most common real moments in an engagement, and "it worked when I left" is not an acceptable answer to a customer.

Then, still before building: run `make seed`, confirm the row counts against the ones above, and read `evals/questions.yaml` top to bottom. That file is your specification for the week.

---

## Part 1 — Make the data real (seeding)

Your Week-1 `rides` table has a handful of rows you created by hand. That is not enough to answer "how many refunds last month?"

*In simple words: you need enough believable fake data that questions about it have real answers. Twelve hand-typed rows won't do — "how many refunds last month" has to actually mean something.*

**Build:**
- A seeder script that generates **~2,000 rides spread across the last 90 days**, with a realistic mix of outcomes: completed, rider-cancelled, driver-cancelled, no-show, refunded, disputed.
- Include the fields the policy questions will need: timestamps, fare, cancellation reason, refund amount, refund reason, who cancelled.
- Make the distribution plausible, not uniform — more rides on weekends, more cancellations in bad-weather weeks, a small refund rate (~3%).
- It must be **idempotent and re-runnable**: `make seed` wipes and regenerates, so anyone can reproduce your numbers.

**Real-life learnings baked in:**
- Every engagement starts with "we can't give you production data yet" — writing credible synthetic data is a standard FDE move, and bad synthetic data (uniform, too clean, no edge cases) produces demos that collapse on real data.
- You'll need to decide what "last month" means (calendar month? trailing 30 days?). Pick one, write it down, and be ready to defend it — ambiguous time windows are the #1 source of "your number is wrong" in customer demos.

**Acceptance check:** `SELECT` the refund count for September and for the trailing 30 days. They should differ, and you should be able to say which one a customer means.

---

## Part 2 — Ingestion: documents into pgvector

*In simple words: chop the policy documents into bite-sized pieces, turn each piece into a list of numbers that captures its meaning, and store those numbers in a Postgres column. Later, when a question arrives, you turn the question into numbers the same way and ask Postgres "which pieces are closest to this?" That's the whole trick.*

**Build:**
- Enable the **pgvector** extension in the Week-1 Postgres. No new database, no new service.
- An ingestion script: load the policy documents → chunk them → embed each chunk → store in a `doc_chunks` table with the text, the embedding vector, and metadata (source file, section heading, chunk index).
- Add a vector index and be able to explain which one you chose and why.
- Make ingestion **re-runnable** without duplicating chunks (content hash, or truncate-and-reload — your call, defend it).

**Real-life learnings baked in:**
- A vector store is a table with an index. Every vendor selling you one is selling convenience, not magic — and knowing this is how you answer "why not Pinecone?" in a customer meeting.
- Metadata is what makes citations possible. If you don't store the source file and section at ingestion time, you cannot cite, and an answer without a citation is unusable in a regulated business.

**Acceptance check:** a raw SQL query in `psql` that takes a question's embedding and returns the top 5 chunks by cosine distance — with no Python in the loop. You must see the mechanism before you let a framework hide it.

---

## Part 3 — The RAG chain (LangChain LCEL)

*In simple words: wire it end to end. Question comes in → find the closest document chunks → paste them into the prompt → ask the model to answer using only those chunks → return the answer plus which document it came from. "RAG" is just those four arrows; don't let the acronym make it sound bigger than it is.*

**Build:**
- `POST /ask` on `rides-api`, taking a question and returning an answer **plus citations** (source file + section for every claim).
- Implement the chain in **LCEL**: retriever → prompt → LLM → parsed output. Composed with pipes, not a pile of imperative glue code.
- The prompt must instruct the model to answer **only** from the retrieved context and to say *"I don't know, this isn't covered in the policy documents"* when the context doesn't contain the answer.
- Return structured output (Pydantic): `answer`, `citations[]`, `confidence`.

**Real-life learnings baked in:**
- LCEL's point is that each joint is swappable — retriever, prompt, model, parser. You'll feel the payoff in Part 6 when you change the model and nothing else moves.
- "Answer only from context" is a prompt instruction, not a guarantee. You will watch a model ignore it. That gap between *instructed* and *enforced* behaviour is the whole reason guardrails exist (Week 4).

**Acceptance check:** three policy questions answered correctly with citations you can click through to the source document.

---

## Part 4 — The router: RAG for text, SQL for facts

This is the heart of the week.

*In simple words: a traffic cop. Read the question, decide whether the answer lives in a document, in the database, or both, and send it down the right path. Customers don't sort their questions for you — they just ask. This layer is what makes the system feel like it understands them.*

**Build:**
- A **classifier** step in front of the chain that decides what the question needs: `policy` (retrieval), `data` (SQL), or `hybrid` (both).
- A SQL path: for `data` questions, generate or select a query against the Week-1 `rides` tables and answer from the result. **Read-only** — the DB user for this path must not have write permission, and you should prove that it doesn't.
- A hybrid path: for a question like *"what's our no-show policy, and how many no-show charges did we apply in September?"*, retrieve the policy text **and** run the SQL, then compose one coherent answer that cites both the document and the query.
- Implement the branch with **`RunnableBranch`**. Note what you've just built: a chain with conditional routing is a graph with two nodes — hold on to that thought, it's Week 3.

**Real-life learnings baked in:**
- Customers do not pre-sort their questions into "document questions" and "data questions". They just ask. The routing layer is the thing that makes the system feel intelligent, and it is almost always undersold in proposals.
- Letting an LLM write SQL against a production database is a decision with consequences. Read-only credentials, a row limit, and a timeout are not optional. Say this out loud in your demo.
- The hybrid answer is the demo moment. One question, two retrieval modes, one answer, both cited. If you only polish one thing this week, polish this.

**Acceptance check:** one question of each type (`policy`, `data`, `hybrid`) answered correctly, and you can show in the trace which path each one took.

---

## Part 5 — Evaluation: numbers, not vibes

*In simple words: a test suite for something that doesn't give the same answer twice. You can't assert `answer == "..."`, so instead you write 20 questions with their correct answers, run them all, and score two separate things: did we fetch the right document, and did we give the right answer. Then you change one setting and run it again. If the score didn't move, the change didn't matter — no matter how clever it felt.*

**Build:**
- An eval set of **20 question/expected-answer pairs**, written before you tune anything: a mix of policy, data, and hybrid questions, plus at least two questions whose answers are **not** in the corpus at all.
- An eval script that scores two things separately:
  1. **Retrieval hit-rate** — did the correct chunk appear in the top-k? (This is objective. Measure it first.)
  2. **Answer correctness** — graded against the expected answer. LLM-as-judge is fine; say so, and spot-check a sample by hand.
- Run the suite, record a baseline, then **tune one variable at a time** — chunk size, overlap, top-k, prompt — and re-run.
- The deliverable is a **before/after table** showing what each change did.

**Real-life learnings baked in:**
- Separating retrieval quality from generation quality is the difference between debugging a RAG system and guessing at it. If retrieval hit-rate is 40%, no prompt engineering will save you.
- You will make a change that *feels* better and *measures* worse. That moment is the entire point of this part.
- The two unanswerable questions are your hallucination detector. A system that confidently answers them is worse than useless — it is actively dangerous in a business context.

**Acceptance check:** a committed `evals/` directory with the question set, the script, and a results table with at least two tuning rounds.

---

## Part 6 — Observability, carried forward

No new tooling. Everything flows through the Week-1 OTel Collector into the Week-1 spans table.

*In simple words: last week you made every HTTP request explainable. Do the same for every question. When someone says "the assistant is slow", you should be able to say "no — retrieval takes 40ms, the model takes 3.2 seconds, here's the trace" within thirty seconds. And because every answer costs money in tokens, you track that too.*

**Build:**
- Manual spans around each stage: `embed_query`, `retrieve`, `classify`, `sql_generate`, `sql_execute`, `llm_generate`.
- Attributes on the LLM spans following the **GenAI semantic conventions**: model name, provider, prompt tokens, completion tokens, and a computed cost.
- Attributes on the retrieval spans: `top_k`, the retrieved chunk IDs, the best and worst distance scores.
- Answer these three questions **in SQL** against your spans table:
  1. p95 latency per stage — which stage dominates?
  2. Cost per question, and the 10 most expensive questions.
  3. Which questions retrieved nothing useful (no chunk above your distance threshold)?
- Add one Grafana panel: answer latency broken down by stage.

**Real-life learnings baked in:**
- Your Week-1 spans schema is now being judged by its *second* use case. If you put everything in one unindexed JSONB blob, these queries will be slow and ugly, and you will have to migrate the table. That is the lesson: **schemas are judged by the second use case, not the first.** Write down what you'd change if you were starting over.
- You now have two completely different latency fingerprints in the same dashboard: the Week-1 planted `/quote` sleep (flat, random, ~20% of requests) and LLM generation (varies with output length, dominated by one stage). "It's slow" is never a diagnosis.

**Acceptance check:** the three SQL queries, committed with their output, plus the Grafana panel.

---

## Part 7 — The provider swap drill (30 minutes)

*In simple words: change one environment variable, run your tests again, and see what a different model does to quality, speed and cost. Half an hour of work that lets you answer "can we use our own model instead?" with a table rather than a shrug.*

**Build:**
- Run the full eval suite under two providers (Ollama baseline plus one other, or two different Ollama models if you have no key).
- Report a table: retrieval hit-rate, answer correctness, p95 latency, cost per question, and any failures (malformed JSON, ignored instructions).

**Real-life learnings baked in:**
- Model choice is a *measured* decision, not a preference. You now have the apparatus to make it, which is more than most teams have.
- Customers will mandate a model you didn't choose — often an on-prem or compliance-approved one. The right response is "let's measure it", and this drill is the rehearsal.

---

## Part 8 — Proposal (the commercial artifact)

*In simple words: explain what you built, and what you did not build, to someone who will never read your code and is deciding whether to pay for more of it.*

**One page.** Written for the Cabify-Lite VP of Support, not for an engineer.

- The problem, in their words.
- The approach, in plain language — including the RAG-vs-SQL distinction, explained without jargon.
- What's in scope and, explicitly, what isn't.
- Assumptions (document quality, data access, model availability).
- Risks, with a mitigation for each.
- A rough timeline.

**Real-life learnings baked in:**
- The hardest part of this page is the scope boundary. Writing "this system does not make refund decisions, it explains the policy" is the sentence that saves the engagement in week six.
- If you cannot explain retrieval-vs-SQL to a non-technical reader in three sentences, you don't understand it well enough yet.

---

## Planted failures (find them yourself)

These are deliberately in the corpus and the build. Do not come to the session having not noticed them.

1. **A document that contradicts the database.** The policy doc states one refund window; the data shows refunds issued outside it. The model will confidently pick one. What should the system do — and what should it *say*?
2. **A chunk boundary that splits a pricing table in half.** Naive fixed-size chunking will cut it; the answer will be half-right, which is worse than wrong because it looks right.
3. **A question with no answer in the corpus.** Does the system say "I don't know", or does it invent a plausible-sounding policy?
4. **The embedding-swap trap.** Change the embedding model *without* re-indexing and watch retrieval quality collapse into nonsense. Do this deliberately, once, and write down the symptom — because when it happens accidentally at a customer it looks like "the AI got dumber overnight".

---

## Deliverables

1. **The repo** — cold `docker compose up` + `make seed` + `make ingest` → a working `/ask` endpoint. Same repo as Week 1.
2. **`evals/`** — question set, eval script, and the before/after results table.
3. **The three SQL analysis queries** with their output, committed.
4. **The 1-page proposal.**
5. **A 5-minute demo**, run as if I'm the VP of Support: the story is *"your team can stop answering these by hand, and here's how we know the answers are right"* — not a tour of your code.

---

## Scoring (1–5 each)

- **Works** — cold start to a correct hybrid answer with citations, traced end-to-end, with eval numbers to back it.
- **Understanding** — you can answer: *"why did this question go down the SQL path?"*, *"what happens if I change the embedding model?"*, and *"your retrieval hit-rate is 70% — what do you do next?"*
- **Communication** — the demo lands the RAG-vs-SQL distinction in the first 90 seconds, in language the VP of Support understands, and the proposal's scope boundary is unambiguous.

---

## Cutline & stretch

- **Core (must):** Step 0 + Parts 1, 2, 3 and a working `policy` path with citations.
- **Full (target):** Parts 4, 5, 6 — the router, the eval suite with one tuning round, and the three SQL queries.
- **Stretch:**
  - Part 7 (provider swap) and Part 8 (proposal).
  - **LangGraph teaser (~90 min):** rebuild the Part-4 router — and *only* the router — as a 3-node `StateGraph`: classify → retrieve-or-sql → answer. Same behaviour, zero new capability. The entire point is to feel the difference between *chaining* and *state + edges*, so that Week 3 opens with you extending something you've already built rather than meeting `StateGraph` cold. If you run out of time, skipping this costs you nothing.
  - Streaming responses from `/ask`.
  - Re-ranking the retrieved chunks before they hit the prompt, measured against the baseline.

If you land at "core" only, we run a working session on the router and evals together before moving to Week 3 — per the progression rule.
