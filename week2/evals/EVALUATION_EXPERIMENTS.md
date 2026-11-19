# Week 2 — Evaluation Experiments and Engineering Lessons

> **Status:** Retrospective of two *committed* evaluation runs, not a new run.  
> **Project:** Cabify-Lite — Grounded Answers  
> **Branch:** `week2-grounded-answers`  
> **Evaluation corpus:** `week2/evals/questions.yaml` (20 questions: 8 policy, 6 data, 4 hybrid, 2 unanswerable)  
> **Change evidence:** [Evaluation improvements commit](https://github.com/palamsaiteja333/cabify-lite/commit/a421d73e30dbf1291846ccc89eb66f3addf06a42)

## 1. Purpose and evidence boundaries

This document records **what the two saved evaluation runs measured**, which implementation changes were committed around the second run, what improved, what regressed, and which questions remain open.

Sources in this repository:

- [Initial run summary](results_smoke.md) and [full JSON](results_smoke.json) — generated **2026-10-23 21:08:34 UTC**.
- [Post-fixes summary](results_post_fixes.md) and [full JSON](results_post_fixes.json) — generated **2026-10-28 18:37:41 UTC**.
- [Evaluator implementation](run_evals.py) and [fixed question specification](questions.yaml).
- [Fix commit `a421d73e`](https://github.com/palamsaiteja333/cabify-lite/commit/a421d73e30dbf1291846ccc89eb66f3addf06a42) — code changes and both saved runs were committed together.
- [Project checkpoint](../PROJECT_CHECKPOINT.md) — summarizes debugging lessons and work still outstanding.

**Evidence boundary:** The repository proves that the code was changed and that the saved scores differ. It does **not** contain a separately measured ablation for every individual fix. Therefore, the changes below are plausible explanations supported by the diff and question outcomes, **not isolated causal measurements**.

The current Ubuntu working tree was previously reported to contain **uncommitted modifications** to the post-fixes JSON and Markdown results. Those local changes have **not** been reviewed here; this document uses the GitHub-committed versions only. No original results or answer key were modified to prepare this retrospective.

## 2. Controlled configuration (same in both saved runs)

| Parameter | Value |
|---|---|
| Top-K | 5 |
| Chunk size | 1,200 characters |
| Chunk overlap | 150 characters |
| Embedding model | `amazon.titan-embed-text-v2:0` |
| Embedding dimensions | 1,024 |
| Chat model | `us.amazon.nova-2-lite-v1:0` |
| Vector store | PostgreSQL + pgvector |
| Distance metric | Cosine |
| Question set | 20 fixed questions |

These recorded settings were held constant. The **application logic, prompts, SQL generation/validation behavior, and other implementation details were changed** between runs.

## 3. Before / after scoreboard

| Metric | Run 1: smoke | Run 2: post_fixes | Difference |
|---|---:|---:|---:|
| Retrieval hit-rate | 12/12 = **100%** | 12/12 = **100%** | 0 percentage points |
| Routing accuracy | 17/18 = **94.4%** | 18/18 = **100%** | +1 passing question |
| Answer correctness | 14/20 = **70%** | 17/20 = **85%** | **+3 passing questions; +15 percentage points** |
| Abstention | 2/2 = **100%** | 1/2 = **50%** | **-1 passing question; -50 percentage points** |
| Questions with execution errors | 1 | 0 | -1 |

**By question type:**

| Type | Initial | Post-fixes |
|---|---:|---:|
| Policy | 8/8 | 8/8 |
| Data | 2/6 | 4/6 |
| Hybrid | 2/4 | 4/4 |
| Unanswerable | 2/2 | 1/2 |

The retrieval rate denominator is **12 applicable retrieval evaluations**, not all 20 questions. Routing excludes the two unanswerable questions.

**Interpretation:** Structured-data and hybrid results improved substantially while document retrieval was already strong. However, the regression on unsupported questions means the system's reliability cannot be summarized by answer correctness alone.

## 4. Question-level movement

| Case | Initial | Post-fixes | What the recorded evidence shows |
|---|---|---|---|
| `d02` — last-90-days refunds | **FAIL** | **PASS** | Initial output counted 49 refunds and used the wrong reporting interpretation/currency against expected **60 refunds, ₹6,029**. |
| `d03` — highest-cancellation week | **FAIL + execution error** | **FAIL, answer produced** | Initial SQL was rejected (`Only SELECT statements are allowed`); post-fixes answered but the judge disputed ISO-week/rounding presentation (`2026-W35`, 29.6% versus about 29.59%). Route classification also became correct. |
| `d05` — driver cancellations in last 30 days | **FAIL** | **PASS** | Initial output stated **20** versus expected **48**; later run passed after time-window/event-time clarifications. |
| `d06` — most frequent pickup locality | **FAIL** | **FAIL** | Whitefield was identified with **118** rides, but the judge objected to a claim of a *decisive* lead over **116** and **115**. Needs fact and wording review, not benchmark weakening. |
| `h02` — refund-policy compliance | **FAIL** | **PASS** | Initial response called the data compliant despite refunds outside the documented seven-day window. Post-fixes passed after changes designed to check both compliant and noncompliant records. |
| `h04` — cancellation fee and no-show collections | **FAIL** | **PASS** | Initial no-show total was **3,120** in the wrong currency; expected result was **₹4,080** (68 no-shows × ₹60). |
| `u01` — dog/pet policy | **PASS** | **FAIL** | Regression: post-fixes output did not clearly abstain where the policy documents lacked support. |
| All other questions | **PASS** | **PASS** | No pass/fail change reported. |

**Net correctness calculation:** 4 cases moved FAIL → PASS (`d02`, `d05`, `h02`, `h04`); 1 case moved PASS → FAIL (`u01`), producing a net gain of **3/20**. The `d03` execution error was removed but its answer correctness remained FAIL.

## 5. What changed in the implementation

The following changes are **verified in the fix commit diff**. Their effect on specific questions is an engineering interpretation, not separately isolated experimental proof.

### 5.1 SQL generation: correct business time and event semantics

**File:** `week2/ingestion/sql_route.py`

The SQL prompt added/clarified:

- **Asia/Kolkata** business-time handling for calendar reporting rather than implicitly relying on UTC.
- A fixed **2026-10-05 reporting/as-of date** for relative periods in this seeded exercise, with PostgreSQL calculating the lookback interval.
- A distinction between **ride-period refund counts** (`rides.requested_at` under the exercise's reporting convention) and **actual refund issuance timing** (`refunds.issued_at`).
- Event-specific timestamps: use `cancelled_at` for cancellation-period questions, `completed_at` for completion events, and `issued_at` for refund processing.
- Refund-policy comparisons that include **both records within a deadline and records beyond it**, rather than counting only compliant records.

**Associated observations:** `d02` and `d05` changed to PASS; `h02` changed to PASS. The full batch included other changes, so one cannot claim each rule independently caused a specific pass.

### 5.2 SQL validation: allow safe analytical CTEs, keep security boundaries

**File:** `week2/ingestion/sql_route.py`

- Added support for analytical `WITH ... SELECT` queries; the prior validator allowed only statements starting with `SELECT`.
- Extracted CTE names so the physical-table allowlist does not mistake a CTE for an unauthorized table.
- Required that queries ultimately reference approved business tables.
- Required `READONLY_DATABASE_URL`, rather than falling back to a general database URL.
- Retained read-only transactions, a five-second statement timeout, and a 100-row return limit.

**Associated observation:** `d03` no longer raised the initial query-validation error, but the final answer still failed judging. **This is an error-resolution improvement, not a correctness pass.**

**Important:** Presence of these safeguards in code is not a substitute for independently testing that the database role lacks write privileges.

### 5.3 Hybrid decomposition: preserve the condition being tested

**File:** `week2/ingestion/hybrid_decomposer.py`

The prompt now preserves thresholds, deadlines, and comparison conditions when splitting a hybrid question.

For example, asking whether **every** refund was issued within seven days requires a data sub-question about both sides of the threshold. Counting only refunds issued within seven days cannot establish policy compliance.

### 5.4 Hybrid synthesis: expose a policy/data contradiction

**File:** `week2/ingestion/hybrid_route.py`

The synthesis instructions now require the final answer to distinguish absolute requirements from averages, explicitly state disagreements between policy and observed data, and avoid treating a majority of compliant records as proof that **all** records comply.

**Associated observation:** `h02` and `h04` were marked PASS in the second run.

### 5.5 RAG grounding: source authority and citation fidelity

**File:** `week2/ingestion/structured_rag.py`

The prompt now defines a source hierarchy for cancellation and refund policy, places `refunds_and_cancellations.md` above conflicting support FAQ/handbook guidance, and restricts citation IDs to sources that support the final answer. It also clarified low-confidence abstention instructions and improved handling of fenced JSON.

**Associated observation:** All eight policy questions passed in both runs; these changes improve the intended design, but the two saved scores **do not demonstrate a measured improvement in policy-case pass rate**.

## 6. What we learned

1. **Retrieval success is not answer success.** Retrieval stayed 12/12 while answer correctness moved from 14/20 to 17/20.
2. **Business-event semantics determine SQL correctness.** `requested_at`, `cancelled_at`, and `issued_at` cannot be used interchangeably.
3. **Read-only SQL protection needs layers.** A prompt is not a security control; application validation and database-enforced limits serve different purposes.
4. **Hybrid questions require falsification, not confirmation bias.** To determine whether a rule is always followed, query the violations as well as the compliant records.
5. **A better aggregate score can hide a safety regression.** The loss of `u01` means stronger data/hybrid performance did not automatically improve abstention.
6. **Evaluation scores need honest attribution.** Several prompt and SQL changes were made together, so this is a before/after comparison—not a controlled one-variable experiment.

## 7. Open investigation items (not yet fixed)

### `u01`: unsupported pet policy — priority reliability issue

- Reproduce the question using the existing evaluator; inspect the answer, confidence, cited source IDs, and retrieval evidence.
- Distinguish genuinely unsupported content from a response that merely sounds tentative.
- Fix grounding/abstention without forcing a stock response for a single benchmark question.
- Re-run **both** unanswerable questions and the complete evaluation suite to catch regressions.

### `d03`: highest cancellation-rate week

- Independently compute the expected week/rate in PostgreSQL, including ISO week and business timezone.
- Check whether 29.59% versus 29.6% and week-start date versus `2026-W35` are substantively equivalent.
- If it is purely an evaluator-format issue, document the evidence and review the judging rule transparently; **do not silently weaken `questions.yaml`**.

### `d06`: pickup locality lead

- Independently confirm the top locality and count.
- Inspect whether the answer overstates the margin of leadership despite naming the correct locality.
- Prefer precise claims supported by rows rather than rhetorical phrases such as "decisive lead."

## 8. Next experimental protocol

For the next meaningful run:

1. Preserve the original question set and original run artifacts; use a **new run label**.
2. Record the exact code commit, model, embedding configuration, `top_k`, chunking settings, database seed/anchor, and run timestamp.
3. Fix **one hypothesis at a time** where possible (for example, abstention gating), run targeted cases, then run the full 20-question suite.
4. Compare retrieval, routing, answer correctness, **and abstention**; manually inspect disputed cases and note model-judge limitations.
5. Save both machine-readable and Markdown results, plus a short rationale for the change.
6. Review diffs before committing. Do not overwrite prior results, modify expected answers to manufacture passes, or stage untracked `.bak` files.

The fixed benchmark specification is `week2/evals/questions.yaml`. The objective is more **defensible, reliable behavior**, not merely a higher headline percentage.

## 9. Project architecture boundary

This evaluation retrospective concerns response quality. **Week 2 observability remains OpenTelemetry Collector → Grafana Tempo**, as documented in `../PROJECT_CHECKPOINT.md`. PostgreSQL trace ingestion and Prometheus metrics migration are out of scope for this work. No observability configuration changes were made in preparing this document.
