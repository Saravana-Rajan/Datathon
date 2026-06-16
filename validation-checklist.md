# Datathon 2026 — Week 0 Validation Checklist

**Window:** This week (3–5 days). Must complete BEFORE 11 Jun Catalyst workshop.

**Why this matters:** Our design doc (`design.md` Section 17) leaves 6 architectural decisions hanging on Zoho Catalyst platform behaviors we have not yet observed firsthand, plus a 7th critical bet on Gemini Live Kannada quality. If any of these come back negative on demo day, we lose hours rewriting orchestration, swapping models, or fighting quotas. We validate now — cheaply, in parallel, against the live platform — so we walk into the 11 Jun workshop with concrete questions and into build week with a locked architecture.

## Quick view (assignment matrix)

| # | Validation | Owner | Time budget | Status |
|---|---|---|---|---|
| 1 | Catalyst Zia AutoML forecasting | Person C | 4 h | [ ] |
| 2 | Catalyst SmartBrowz Kannada PDF | Person E | 2 h | [ ] |
| 3 | Catalyst Auth custom role claims | Person D | 3 h | [ ] |
| 4 | Catalyst Circuits parallel + retry + streaming | Person B | 4 h | [ ] |
| 5 | Catalyst free-tier quotas (NoSQL + Stratus) | Person A | 3 h | [ ] |
| 6 | Third-party allowance (organizer email) | Person E | 1 h | [ ] |
| 7 | Gemini Live Kannada 20-query eval | Person E | 4 h | [ ] |

**Total team effort:** ~21 hours across 5 people = comfortably parallel inside the week.

---

## Detailed Validation Tasks

### 1. Catalyst Zia AutoML — time-series forecasting

- **Owner:** Person C
- **Time budget:** 4 hours
- **Why this matters:** Our crime-trend prediction module assumes Zia AutoML can forecast incident counts per ward with confidence intervals. If it cannot, we fall back to Vertex AI — which adds a second cloud, a second auth flow, and a third-party-allowance question.
- **Steps:**
  1. Sign into Catalyst console → Zia → AutoML. Screenshot the model-type picker.
  2. Upload a 200-row synthetic CSV (`date, ward_id, incident_count`) covering 90 days, 5 wards.
  3. Train a forecasting model targeting `incident_count` with `ward_id` as a categorical feature.
  4. Inspect output: does it return point forecast only, or point + lower/upper bounds?
  5. Try adding a derived feature (rolling 7-day mean) — does AutoML accept custom engineered columns?
- **Acceptance criteria (PASS):**
  - Time-series / forecasting model type is selectable in the UI or API.
  - Output includes confidence intervals (or quantile forecasts) natively.
  - Custom numeric features are accepted alongside the date column.
- **Failure scenarios:**
  - No forecasting mode → mark Vertex AI as primary, file request to organizers for third-party allowance, update `design.md` §6.
  - Forecasting works but no CIs → wrap with bootstrap resampling in Circuits step, document the workaround.
  - No custom features → drop engineered features from v1, use raw counts only.
- **How to log results:** Add a row to `decisions.md` (`AutoML-001`) with PASS/FAIL, evidence screenshot path, and the chosen fallback. Update `design.md` §17 question 1 → resolved.

---

### 2. Catalyst SmartBrowz — Kannada PDF font rendering

- **Owner:** Person E
- **Time budget:** 2 hours
- **Why this matters:** The case-brief export is a judge-visible deliverable. Kannada glyphs that render as boxes or Latin transliteration will tank our demo. If SmartBrowz fails, we swap to a Puppeteer-on-Functions path with bundled Noto Sans Kannada — adds 3–4 hours of build time.
- **Steps:**
  1. Open Catalyst SmartBrowz console; create a "URL to PDF" job.
  2. Point it at a public Kannada Wikipedia article (e.g., `kn.wikipedia.org/wiki/ಬೆಂಗಳೂರು`).
  3. Repeat with a locally hosted HTML page containing mixed Kannada + English + numbers + a table.
  4. Open both PDFs in Acrobat and on mobile. Check: glyph fidelity, ligatures, conjuncts (ಕ್ಷ, ಜ್ಞ), and text-selectability.
- **Acceptance criteria (PASS):**
  - All Kannada conjuncts render correctly (no tofu boxes, no broken stacking).
  - Text is selectable and copy-pasteable as Kannada Unicode (not images).
  - Mixed-script lines wrap cleanly.
- **Failure scenarios:**
  - Glyphs broken → fall back to Puppeteer + Noto Sans Kannada on Catalyst Functions; budget 4 h extra in build week.
  - Text rendered as image only → acceptable for v1 demo, flag as risk for production.
- **How to log results:** Save both PDFs to `evidence/smartbrowz/`. Add `SmartBrowz-001` row to `decisions.md`. Update `design.md` §17 question 2.

---

### 3. Catalyst Authentication — custom role claims in JWT

- **Owner:** Person D
- **Time budget:** 3 hours
- **Why this matters:** Our RBAC model (officer / supervisor / analyst) and audit drawer depend on a `role` claim arriving in the JWT so the frontend and orchestrator can both gate features without an extra lookup per request. If Catalyst Auth only ships standard claims, we add a custom user-attribute table and a fetch step in every Circuit run.
- **Steps:**
  1. In Catalyst console → Authentication, create three test users with different custom attributes (`role=officer`, `role=supervisor`, `role=analyst`).
  2. Configure a custom claim mapping in the JWT (if the option exists).
  3. Log in via the SDK in a throwaway Next.js page; print the decoded JWT.
  4. Verify the `role` claim is present and matches the user attribute.
  5. Add a second claim (`department`) and confirm multi-claim support.
- **Acceptance criteria (PASS):**
  - Custom claims appear in the JWT payload, not just in a separate user profile API call.
  - At least two custom claims can coexist.
  - Claim values reflect updates to user attributes within one re-login.
- **Failure scenarios:**
  - No custom claims → introduce a `user_profile` lookup in the orchestrator's first step, cache 5 min in Stratus. Add a "trusted enrichment" note to audit log schema.
  - One claim only → pack role + department into a single JSON-encoded claim.
- **How to log results:** Paste decoded JWT (redacted) into `evidence/auth/jwt-sample.txt`. Log `Auth-001` in `decisions.md`. Update `design.md` §17 question 3 and §11 (security).

---

### 4. Catalyst Circuits — parallel branches, retry, streaming

- **Owner:** Person B
- **Time budget:** 4 hours
- **Why this matters:** The orchestrator design assumes (a) we can fan out SQL + Cypher generation in parallel, (b) failed LLM steps retry with backoff, and (c) we can stream tokens to the chat UI as steps progress. If any of these are missing, we either lose latency, lose resilience, or rebuild the orchestrator on Functions + a queue.
- **Steps:**
  1. Build a throwaway Circuit with two parallel branches both calling a mock HTTP endpoint that sleeps 2 s. Confirm wall-clock is ~2 s, not 4 s.
  2. Wire one branch to a flaky endpoint (returns 500 50% of the time). Configure retry-on-failure; confirm step retries with backoff.
  3. Build a 3-step Circuit where step 1 emits partial output. Subscribe from a Next.js page using the SDK or webhooks. Observe: do we see step-1 output before step-3 finishes?
- **Acceptance criteria (PASS):**
  - Parallel branches measurably overlap (wall-clock < sum of step times).
  - Retry semantics are configurable (count + backoff) per step.
  - Streaming or progressive callbacks are available so UI can show partial state.
- **Failure scenarios:**
  - No parallel → run SQL and Cypher sequentially; budget +800 ms p95 latency in `design.md` §10.
  - No retry → wrap each LLM call in a Functions retry shim.
  - No streaming → poll Circuit status every 500 ms from frontend; flag UX trade-off.
- **How to log results:** Export Circuit run trace as JSON to `evidence/circuits/`. Add `Circuits-001/002/003` rows to `decisions.md`. Update `design.md` §17 question 4 and §5 (orchestrator).

---

### 5. Catalyst free-tier quotas — NoSQL + Stratus + demo-day burst

- **Owner:** Person A
- **Time budget:** 3 hours
- **Why this matters:** Our entire architecture sits on the free tier. If NoSQL caps at, say, 10k writes/day and the synthetic generator alone needs 50k, we either pay, shard across multiple Catalyst projects, or rearchitect on Postgres. We need numbers before we provision.
- **Steps:**
  1. Open Catalyst billing/usage console. Screenshot every "free tier includes" line item for: Data Store, NoSQL, Stratus (object storage), Functions, Circuits.
  2. Cross-check against the Catalyst pricing page (capture URL + timestamp — pricing changes).
  3. Run a quick load test: 1,000 NoSQL writes via Functions, observe usage meter increment.
  4. Estimate demo-day burst: 5 concurrent users × 10 queries × 4 store ops = 200 ops/min peak. Compare to per-minute throttle (not just daily quota).
- **Acceptance criteria (PASS):**
  - Free-tier limits documented for all 5 services with screenshot evidence.
  - Daily write capacity ≥ 3× our synthetic-generator estimate (50k writes).
  - Per-minute throttle ≥ 4× projected demo-day peak.
- **Failure scenarios:**
  - NoSQL daily cap too low → move historical data to Stratus blobs + thin NoSQL index; or chunk ingest across 2–3 days.
  - Stratus cap too low → compress with gzip, drop debug logs.
  - Throttle too tight for demo → pre-warm cache before demo, queue non-critical writes async.
- **How to log results:** Screenshots to `evidence/quotas/`. Add `Quota-001` table to `decisions.md` listing each service + limit + headroom. Update `design.md` §17 question 5 and §13 (capacity).

---

### 6. Third-party allowance — written confirmation from organizers

- **Owner:** Person E
- **Time budget:** 1 hour
- **Why this matters:** Gemini Live, Google Maps, Vertex AI fallback, and Neo4j Aura are all non-Zoho. If the rules forbid third-party services, half our architecture is illegal. We need an email on file.
- **Steps:**
  1. Draft an email to the Datathon organizers listing every third-party service we intend to use, with purpose for each.
  2. Send by end of day Monday. CC all 5 teammates.
  3. Track reply; chase on Wednesday if no response.
- **Acceptance criteria (PASS):**
  - Written confirmation (email reply) explicitly approving each named service, or approving "third-party services with disclosure."
- **Failure scenarios:**
  - Denied for any service → swap that service for a Catalyst-native equivalent or remove the feature. Most-likely fallback: replace Gemini Live with Catalyst Zia ASR/TTS (lower quality, demoable).
  - No reply by Friday → raise as a live question at the 11 Jun workshop.
- **How to log results:** File the email thread in `evidence/organizer-comms/`. Add `Policy-001` to `decisions.md`. Update `design.md` §17 question 6.

---

### 7. Gemini Live API — Kannada bilingual eval

- **Owner:** Person E
- **Time budget:** 4 hours
- **Why this matters:** Voice-mode bilingual Kannada+English is our headline differentiator on demo day. If Gemini Live mishears Kannada below ~85% comprehension, the demo's "wow" moment becomes a "huh?" moment. Better to know now and pivot to typed-only bilingual.
- **Steps:**
  1. Compile a 20-query eval set: 10 pure Kannada, 5 code-mixed (Kannada + English nouns like "FIR", "Whitefield"), 5 English with Indian-accent phonetics. Save to `evidence/voice/eval-set.md`.
  2. Record each query (use 2 voices if possible — one native Kannada speaker, one L2).
  3. Send each through Gemini Live; capture transcript + intent classification.
  4. Score each: 1 if intent matches gold label and key entities (names, locations, dates) are preserved; 0 otherwise.
- **Acceptance criteria (PASS):**
  - ≥ 17/20 (≥85%) queries score 1.
  - No critical failures on entity extraction (place names, ward numbers).
- **Failure scenarios:**
  - Score 70–84% → keep voice mode but show a "review transcript" confirmation step before executing the query.
  - Score < 70% → demote voice to "stretch feature," lead demo with typed bilingual chat, keep voice as a 30-second cameo.
- **How to log results:** Save scored CSV to `evidence/voice/results.csv`. Add `Voice-001` to `decisions.md` with the score and chosen UX path. Update `design.md` §17 question 7 and §8 (voice mode).

---

## Workshop attendance (mandatory)

- **4 Jun — Problem Statement Explainer:** All 5 attend. Person B takes notes; circulate within 24 h.
- **11 Jun — Catalyst workshop:** All 5 attend. Bring open questions 1–5 as live questions for the ZOHO team — even if our tests passed, get confirmation in writing.
- **18 Jun — AMA session:** Person E + one other. Carry forward any decisions still unresolved.

## End-of-week deliverable

By Friday EOD, Person B posts a single status update in the team channel answering:

> **"Did all 7 validations PASS? If not, which architectural decisions need to change before we start building?"**

Format: one line per validation (PASS / PASS-with-workaround / FAIL → new plan), with a link to the row in `decisions.md`. If any FAIL, the next message is a 30-minute team huddle to ratify the revised architecture before any build work begins.
