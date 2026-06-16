# `bias_review_queue` — Schema & Workflow

This document describes the **bias-review queue** that the audit-logger
function writes to whenever an officer flags an AI answer as wrong. It is
the human-in-the-loop counterpart to the immutable audit chain
(design.md §5.8 + §11.3) and the operational backbone of KSP Saathi's
trust / compliance story.

---

## 1. Where it lives

| Property | Value |
|---|---|
| Catalyst service | NoSQL |
| Table name | `bias_review_queue` (override via env `CATALYST_BIAS_REVIEW_TABLE`) |
| Region | Catalyst India DC (`asia-south1` adjacent) — IT Act 2008 |
| Write path | `POST /flag` on the `audit-logger` Function |
| Read path | Internal review console (Person D — frontend) |

A single flag also appends a `user_flag` step to the matching audit
chain in the `audit_logs` table, so the chain itself records that a
human disagreed with the AI. The queue is the **source of truth for
review status**; the audit chain remains immutable evidence.

---

## 2. Schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Unique flag id — `flag-{uuid4 hex}` |
| `request_id` | string | yes | Foreign key into `audit_logs` partition |
| `reason` | string | yes | Free-text officer explanation (≤ 2000 chars) |
| `user_id` | string | yes | The flagging officer (Catalyst Auth subject) |
| `ts` | ISO 8601 string | yes | UTC timestamp of the flag |
| `ts_ms` | int (epoch ms) | yes | For range queries / SLA dashboards |
| `status` | enum | yes | `pending` → `assigned` → `resolved` / `dismissed` |
| `reviewer_id` | string \| null | no | Catalyst Auth subject of the assigned reviewer |
| `reviewer_notes` | string \| null | no | Resolution rationale (visible to flagging officer) |
| `resolved_at` | ISO 8601 \| null | no | When status moved to `resolved` or `dismissed` |

### Status state machine

```
   ┌─────────┐   assign    ┌──────────┐   resolve    ┌──────────┐
   │ pending │ ──────────► │ assigned │ ───────────► │ resolved │
   └─────────┘             └──────────┘              └──────────┘
        │                        │
        │                        │ dismiss
        │                        ▼
        │                  ┌──────────┐
        └─────────────────►│dismissed │
              dismiss      └──────────┘
```

Transitions are advisory at the data layer (no DB constraint) and
enforced by the review console. The queue table never deletes rows —
status `resolved` and `dismissed` remain queryable for trend analysis
("how often does the AI mis-cite cross-district stations?").

### Indexes (logical)

* **Primary** — `id` (uuid).
* **Partition / lookup** — `request_id` (join into `audit_logs`).
* **Analytics** — `user_id`, `ts_ms`, `status`. These three are what the
  review dashboard slices on (top-flaggers, weekly volume, SLA
  breaches). Catalyst NoSQL secondary indexes are configured via the
  Catalyst console; the function does not assume they exist (falls back
  to a table scan).

---

## 3. Workflow

### 3.1 Officer flags an answer
1. Officer opens the "Why?" drawer in the chat UI and clicks **Flag**.
2. UI calls `POST /flag` on `audit-logger` with `request_id`, `reason`,
   `user_id` (Auth-supplied; the officer cannot impersonate).
3. Function writes a row with `status = pending` to `bias_review_queue`
   and appends a `user_flag` step to the audit chain.
4. UI gets the `flag_id` back and shows "Submitted for review".

### 3.2 Reviewer (DCP / SCRB analyst) triages
1. Review console pulls `status = pending` rows ordered by `ts_ms`.
2. Reviewer clicks **Assign to me** → status `assigned`, `reviewer_id` set.
3. Reviewer opens the full audit chain via `GET ?request_id=...` —
   they see every step (input → language detect → route → tool calls →
   synthesis → output) and can reproduce the AI's reasoning end-to-end.

### 3.3 Resolution
The reviewer's verdict is one of:

* **Resolved — AI was wrong.** Writes `reviewer_notes` explaining the
  fault (e.g. "SQL filtered on `district = Bengaluru` but officer asked
  for `Bengaluru Urban` — fix the route prompt"). Status → `resolved`.
  The flagging officer gets a Catalyst Mail notification.
* **Resolved — AI was right but unclear.** Notes capture the
  clarification; the answer was correct but the explanation is added to
  a "answer-clarity backlog" for prompt tuning.
* **Dismissed — out of scope / duplicate.** Notes explain why.

### 3.4 Feedback loop into the model
On a weekly cadence (Catalyst Cron) we aggregate all `status = resolved
AI-wrong` flags into the **bias regression set**. This set:

* feeds the LLM eval harness (design.md §10.4),
* informs prompt updates for the router and synthesizer,
* and is reported in the monthly KSP review meeting as "AI errors
  caught and fixed".

---

## 4. Why this matters — trust & compliance

* **IT Act 2008 evidentiary value.** Karnataka Police can show a court
  that every AI-assisted decision is traceable end-to-end *and* that
  human officers can flag and override it. The audit chain is
  immutable; the review queue is the human override layer.
* **DPDP Act 2023 accountability.** Subjects have a right to know how
  automated decisions about them were made. The chain + queue provide
  that record on demand.
* **Bias safety net.** Predictive features explicitly exclude caste,
  religion, and community (design.md §5.7). The bias review queue is
  the *empirical* check: if predictions or synthesis show bias in
  practice — even via proxies — flags will surface it. Trends in the
  queue are reviewed monthly by the SCRB analyst.
* **Trust building with investigators.** Officers know AI answers can
  be wrong. Giving them a one-click way to flag — and *seeing* the
  flag travel to review and back to a fix — is what converts
  scepticism into adoption. Without this, the tool is a black box
  shouting confident guesses.
* **Demo-day defensibility.** When judges ask *"What if the AI is
  wrong?"*, we open the "Why?" drawer, hit Flag, and show the queue
  row appearing live. That is the answer to the bias question, and it
  is built in — not bolted on.

---

## 5. Operational guarantees

* **Immutability of the audit chain.** The audit-logger function
  exposes only append and read APIs for `audit_logs`. There is no
  update or delete endpoint. Even when an officer flags an answer the
  original chain is unchanged — the flag is a *new* step plus a *new*
  row in the queue.
* **Queue status is mutable.** The review console updates `status`,
  `reviewer_id`, `reviewer_notes`, `resolved_at` in-place on
  `bias_review_queue`. This is intentional: the queue is operational
  state, not evidence. The audit chain is evidence.
* **Independence of stores.** A failure to write to
  `bias_review_queue` returns `503 bias_review_store_unavailable`
  *before* writing the `user_flag` step. This prevents a partially-
  recorded flag where the chain says "user flagged" but the queue has
  no row to action.
* **No PII leakage to logs.** Function logs record `request_id`,
  `flag_id`, and `user_id` only — never `reason` text (which may
  contain case details).
