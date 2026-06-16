# Datathon 2026 — Challenge 01 Design Document

**Product name:** **Yaksha** (ಯಕ್ಷ) — *"the guardian spirit for Karnataka Police data"*
**Internal codename:** `ksp-saathi` (used in code paths, folder names, function IDs)
**Challenge:** Intelligent Conversational AI for KSP Crime Database
**Team:** 5 members (mixed AI / data / frontend / design / voice)
**Deadlines:** Prototype 26 Jul 2026 · Initial shortlist 19 Aug · Final shortlist 9 Sep · Grand Finale 26 Sep
**Hackathon spend cap:** ~₹12,000 (Catalyst free credits + minimal Google)

> **Single-line summary:** A Catalyst-hosted, Kannada-first conversational AI that lets Karnataka Police investigators query, visualize, and forecast crime data — by voice or text — with full audit trails and India-only data residency.

---

## Section 1 — Problem Statement (Verbatim, locked)

> The **State Crime Records Bureau (SCRB)** manages a large and continuously expanding repository of crime-related data from **1100+ police stations across Karnataka**. Current systems rely on **static dashboards and manual queries**, limiting deep analysis and real-time insights.
>
> **The Challenge:** Build an intelligent conversational AI platform enabling investigators to query crime data using natural language and uncover patterns, relationships, and predictive insights.
>
> **Key Features (all 9 in scope):**
> 1. Natural language chatbot (English + Kannada)
> 2. Voice-enabled interaction
> 3. Context-aware conversations
> 4. PDF export of conversation history
> 5. Criminal network visualization
> 6. Crime trend & hotspot detection
> 7. Predictive analytics & early warnings
> 8. Explainable AI with audit trails
> 9. Role-based secure access

**Scope discipline:** We build **all 9 features**. No invented features outside the brief. No removed features. The win comes from depth of execution, not redefinition.

---

## Section 2 — Locked Decisions (from brainstorming)

| Decision | Choice | Why |
|---|---|---|
| **Challenge** | 01 — Conversational AI | Higher demo magic + Kannada moat |
| **Team profile** | 5 ppl, mixed AI/data/frontend/design/voice | Can attempt full vision |
| **Data sources** | Mix — public datasets + synthetic FIRs + news scrape | Real KSP data unavailable |
| **Headline features** | All 4 differentiators (Kannada chat, voice, network+hotspot viz, predictive+explainable) | Cover the full brief depth |
| **Primary platform** | **Zoho Catalyst** (mandatory per hackathon rules) | Submission validity + free credits + India residency |
| **Augmenting platform** | **Google Cloud (Gemini + Maps + Neo4j on GCE)** | Used intentionally where Catalyst has gaps |
| **Architecture pattern** | Approach C — Routed multi-modal RAG | Predictable, parallelizable across team, explainable |
| **Voice stack** | **Kannada:** Gemini Live API (primary, Catalyst gap) + Google fallback · **English/Hindi:** Catalyst Zia | Best-of-both with documented quality (Zia confirmed no Kannada) |
| **Region** | `asia-south1` (Mumbai) / Catalyst India DC | IT Act 2008 compliance built-in |

---

## Section 3 — Target Users (Investigator Personas)

> *Note: detailed personas refined from public-source research in `research-investigators.md`. Summary below.*

> *Personas grounded in `research-investigators.md` — Karnataka HC 2022 confirms PSI, PI, and DySP all have authority to investigate and file chargesheets.*

### Primary — **PSI (Police Sub-Inspector) in rural / semi-urban Karnataka**
- Age ~28, field-heavy, often lone investigator in remote station
- Job-to-be-done: *"Confirm suspect history + MO match while still at the scene."*
- Pain: CCTNS exact-match search misses fuzzy/transliterated names; rural connectivity slow; no time at desk
- AI win: voice query in Kannada from a mobile PWA — *"ಈ ಸಂಶಯಿತನ ಮೇಲೆ ಮೊದಲು ಎಷ್ಟು ಪ್ರಕರಣಗಳಿವೆ?"* → instant suspect history

### Secondary — **PI (Police Inspector) running urban Bengaluru station**
- Age ~38, manages 8–15 PSIs, juggles 20+ active cases
- Job-to-be-done: *"Find cross-station patterns my PSIs would miss."*
- Pain: PSIs in his station don't see patterns at neighbouring stations; CCTNS data quality ~80% IIF1-6 completion → searches return false negatives
- AI win: *"Show all chain snatchings near Indiranagar metro across all stations last 30 days, grouped by MO"* → cross-station picture

### Tertiary — **DySP (Deputy Superintendent) at CCB (City Crime Branch)**
- Age ~45, intelligence-focused, builds cases against organised crime
- Job-to-be-done: *"Map the criminal network behind repeat cases."*
- Pain: data scattered across DCRBs (District Crime Records Bureaus); no unique accused identifier across stations
- AI win: criminal network graph visualization + "find all linked accused" queries that traverse the graph

### Bureau user — **SCRB Analyst (Karnataka State Crime Records Bureau)**
- Bureau-level role aggregating DCRB feeds into PoliceIT for state-wide reports
- Job-to-be-done: *"Surface state-wide trends for DGP-level decisions."*
- Pain: writes custom SQL for every cross-district query
- AI win: natural-language state-level queries with explainable methodology

**Out of scope as primary users:** SHO morning briefings (already covered by PI persona), Constables (no investigation authority).

---

## Section 4 — Goals & Success Metrics

| Type | Metric | Target |
|---|---|---|
| **Demo** | Time-to-first-audio (voice query → first audio out) | < 1.5 s |
| **Demo** | Full response time | < 3.5 s |
| **Demo** | Kannada query understanding accuracy (eval set) | ≥ 90% |
| **Demo** | Synthesis answer relevance (judge eval) | ≥ 4/5 |
| **Demo** | All 9 listed features functional in live demo | 9/9 |
| **Product** | Sample investigator query coverage | ≥ 80% of top 50 |
| **Product** | Audit-trail completeness (every step logged) | 100% |
| **Reliability** | Demo-day uptime | 100% (no cold starts) |
| **Compliance** | India-only data flow | 100% |

---

## Section 5 — The 9 Features (Sub-Specs)

### 5.1 Natural language chatbot (English + Kannada)
- Streaming chat UI (Vercel AI SDK on Next.js)
- Detects input language; responds in detected language by default
- User can toggle to switch language explicitly
- Code-mixed input ("kannada-english mix") handled gracefully

### 5.2 Voice-enabled interaction
- Browser captures audio (Web Audio API + MediaRecorder)
- Voice Activity Detection (VAD) detects silence → triggers transcription
- **Language-aware routing:**
  - **Kannada audio →** Gemini Live API STT (primary; Catalyst Zia gap) → Gemini Live API TTS
  - **English/Hindi audio →** Catalyst Zia STT → Catalyst Zia TTS
  - Fallback ladder: Google Cloud STT/TTS for any language at any layer
- Audio barge-in: user can interrupt mid-answer
- Full duplex (talk while AI talks) supported in v1.1 if time

### 5.3 Context-aware conversations
- Session-level memory in Catalyst NoSQL
- Last N turns + extracted entities passed to LLM
- "What about last month?" resolves to previously discussed filter
- 30-minute session timeout; long-term memory v2

### 5.4 PDF export of conversation history
- Catalyst SmartBrowz generates branded PDF
- Includes: chat transcript, embedded map screenshot, embedded graph, audit trail
- "Save to case file" button → Catalyst Stratus + email to officer via Catalyst Mail

### 5.5 Criminal network visualization
- Neo4j AuraDB Free (graph DB — Catalyst has no equivalent)
- Schema: `(Person)-[KNOWS|CALLS|CO_ACCUSED_IN|LIVES_NEAR]-(Person)`, `(Person)-[ACCUSED_IN]->(FIR)`
- React-Flow graph in UI; animates as agent traverses
- Supports 1–3 hop traversal queries
- "Centrality" mode highlights gang hubs

### 5.6 Crime trend & hotspot detection
- Google Maps JS API for map UI (Catalyst has no maps)
- PostGIS-style spatial queries on Catalyst Data Store *(verify at workshop)*; fallback: H3 indexing in app code
- DBSCAN clustering for hotspot generation
- Date range slider with animated heatmap
- District/station drill-downs

### 5.7 Predictive analytics & early warnings
- **Reframed as "resource allocation hints", not Minority Report**
- Catalyst Zia AutoML (primary) — train on synthetic + public NCRB data
- Vertex AI Forecasting (augmentation) — if Zia AutoML quality insufficient
- Features used: location, time-of-day, day-of-week, weather, holidays, recent counts
- **Explicitly excluded features**: caste, religion, community — for ethics + bias safety
- Output: confidence interval, top contributing features, "review board" audit link

### 5.8 Explainable AI with audit trails
- **First-class UI feature**, not a checkbox
- Every chat turn writes to Catalyst NoSQL audit log:
  - `{ ts, userId, role, raw_query, lang, intent, route_decision, sql_or_cypher, sources, response, confidence }`
- "Why?" drawer in UI shows the chain visually
- Officer can flag wrong answers → goes to bias-review queue
- Audit log immutable + exportable (IT Act 2008 compliance)

### 5.9 Role-based secure access
- Catalyst Authentication with custom claims
- Roles: `constable`, `sub_inspector`, `inspector`, `sho`, `dcp`, `scrb_analyst`, `admin`
- Each role sees different data surface area:
  - Constable: own station only
  - Inspector: own jurisdiction
  - SHO: full station data
  - DCP/SCRB: district / state
- Sensitive fields (PII, accused minor data) masked per role

---

## Section 6 — Architecture

### 6.1 High-level diagram

```
┌──────────────────────────────────────────────────────────┐
│  FRONTEND  — Next.js 15 + shadcn/ui + Vercel AI SDK      │
│  ▸ Catalyst Web Client Hosting (or Slate)                │
│  ▸ Catalyst Domain Mappings (custom domain + SSL)        │
│  ▸ Chat pane (voice + text) | Map | Graph | Audit drawer │
└───────────────────────────┬──────────────────────────────┘
                            │  WebSocket + REST
┌───────────────────────────▼──────────────────────────────┐
│  EDGE — Catalyst API Gateway                             │
│  ▸ Catalyst Authentication (JWT + role claims)           │
│  ▸ Audit logger → Catalyst NoSQL                         │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│  ORCHESTRATOR — Catalyst Circuits + Functions            │
│                                                          │
│  STEP 1: Intent Router (Catalyst QuickML LLM — fast)     │
│    → classifies: tabular / graph / RAG / predict / mixed │
│                                                          │
│  STEP 2: Parallel specialist execution                   │
│    ├── SQL Gen → Catalyst Data Store                     │
│    ├── Cypher Gen → 🟡 Neo4j AuraDB (GCP)                │
│    ├── RAG Retrieval → Catalyst QuickML RAG              │
│    └── Forecast → Catalyst Zia AutoML (or Vertex AI)     │
│                                                          │
│  STEP 3: Synthesizer (Catalyst QuickML LLM or Gemini Pro)│
│    → streams answer + viz spec to frontend               │
│    → writes complete audit trail                         │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│  VOICE — Language-routed                                 │
│  ▸ Kannada → 🟡 Gemini Live API (Catalyst Zia has no Kannada)  │
│  ▸ English/Hindi → ★ Catalyst Zia STT/TTS                │
│  ▸ Google Cloud STT/TTS = universal fallback             │
└──────────────────────────────────────────────────────────┘

★ = Catalyst (mandatory)        🟡 = Justified third-party
                  All in India 🇮🇳
```

### 6.2 Data flow (voice query — Kannada path)

```
0.0s   User speaks Kannada
0.2s   VAD silence detected, transcript ready (Gemini Live API)
0.3s   Catalyst API Gateway: auth + audit log entry created
0.5s   Intent router (Qwen 2.5 7B on QuickML): classified as "tabular_geo"
1.0s   Parallel: SQL on Data Store + Hotspot via H3 + RAG retrieval
1.5s   Synthesizer (Qwen 2.5 14B, or Gemini Pro for premium) begins streaming
1.7s   First TTS audio chunk plays (Gemini Live API)
2.5s   Map animates to hotspot (Google Maps), network graph populates (Neo4j)
3.5s   Full answer delivered + audit trail visible in UI
```

For English/Hindi queries, Catalyst Zia replaces Gemini Live API in steps 0.2 and 1.7.

### 6.3 Service map — Catalyst vs Google

**Catalyst (mandatory, primary):** Web Client Hosting · Domain Mappings · API Gateway · Authentication · Functions · Circuits · Data Store · NoSQL · Stratus · Cache · QuickML LLM Serving + RAG · Zia AutoML · Zia Services (voice) · SmartBrowz · Cron · Mail · Push · Signals + Event Functions · Pipelines

**Google (justified augmentation only):**
- **Neo4j AuraDB** (on GCP) — Catalyst has no graph DB
- **Google Maps Platform** — Catalyst has no Maps service
- **Gemini 2.5 Pro** — for premium Kannada synthesis if QuickML quality insufficient (A/B tested, documented)
- **gemini-embedding-001** — for RAG embeddings if QuickML embedder weak (A/B tested)
- **Vertex AI Forecasting** — fallback if Zia AutoML insufficient

**Justification log:** every Google service usage will be documented in `decisions.md` with the Catalyst alternative tested and the measured gap.

---

## Section 7 — Data Strategy

### 7.1 Three-tier data approach

| Tier | Source | Use | Volume |
|---|---|---|---|
| **Tier 1 — Real public** | NCRB Crime in India + data.gov.in + Karnataka open data + OpenStreetMap + Census | Aggregate trends, geography, demographics | ~10–20K records |
| **Tier 2 — News scrape** | Deccan Herald, ToI Bengaluru, Vijaya Karnataka, Prajavani, Indian Kanoon judgments | Real case narratives (Kannada + English), MO patterns | ~5–10K narratives |
| **Tier 3 — Synthetic FIRs** | Custom generator (`data/generate_synthetic_firs.py`) | Case-level demos with realistic schema | 50K records |

### 7.2 Storage map

| Store | Catalyst service | Contents |
|---|---|---|
| Structured FIRs + aggregates | Catalyst Data Store | All FIR records, station refs, accused refs |
| Embeddings (case narratives) | Catalyst QuickML RAG | English + Kannada narrative chunks |
| Audit logs | Catalyst NoSQL | One doc per user turn |
| Session state | Catalyst NoSQL | Last N turns + extracted entities |
| Files (PDF exports, uploaded docs) | Catalyst Stratus | Object storage |
| Query cache | Catalyst Cache | Hot query results (5-min TTL) |
| Criminal network graph | Neo4j AuraDB | Person/FIR nodes + relationships |

### 7.3 Schema (FIR record)
See `data/README.md` for full schema. Summary: `fir_no, station_name, station_lat/lng, district, date_registered, crime_type, ipc_sections, location_lat/lng, location_text, complainant, accused[], victims[], modus_operandi, modus_operandi_kannada, investigating_officer, status, linked_fir_nos, narrative, narrative_kannada`.

### 7.4 Honest disclosure (for pitch)
Slide line: *"Real Karnataka trends from NCRB + 50K representative case records. When KSP supplies SCRB data, we plug it in unchanged."*

---

## Section 8 — Tech Stack (Decisive)

| Layer | Tool | Catalyst service? |
|---|---|---|
| Frontend framework | Next.js 15 (App Router) | hosted on Catalyst Web Client Hosting |
| UI library | shadcn/ui + Tailwind 3 | — |
| Streaming chat | Vercel AI SDK (`useChat`) | — |
| Maps | Google Maps JS API + Places | 🟡 GCP |
| Network graph viz | React-Flow / Cytoscape | — |
| Charts | Recharts | — |
| Backend | FastAPI on Catalyst AppSail (managed) OR Catalyst Functions (Python) | ★ Catalyst |
| Orchestration | Catalyst Circuits | ★ Catalyst |
| Auth | Catalyst Authentication | ★ Catalyst |
| Relational DB | Catalyst Data Store | ★ Catalyst |
| NoSQL (audit/sessions) | Catalyst NoSQL | ★ Catalyst |
| Object storage | Catalyst Stratus | ★ Catalyst |
| Cache | Catalyst Cache | ★ Catalyst |
| Graph DB | Neo4j AuraDB Free | 🟡 GCP |
| LLM (routing + synth) | Catalyst QuickML LLM Serving (primary) | ★ Catalyst |
| LLM (premium synth) | Gemini 2.5 Pro (augmentation if QuickML weak) | 🟡 GCP |
| Embeddings | Catalyst QuickML RAG embedder; fallback `gemini-embedding-001` | ★ + 🟡 |
| Forecasting | Catalyst Zia AutoML; fallback Vertex AI Forecasting | ★ + 🟡 |
| Voice STT/TTS (Kannada) | Gemini Live API (native multimodal) *(Catalyst gap)* | 🟡 |
| Voice STT/TTS (English/Hindi) | Catalyst Zia Services | ★ Catalyst |
| PDF generation | Catalyst SmartBrowz | ★ Catalyst |
| Cron / scheduled | Catalyst Cron | ★ Catalyst |
| Email | Catalyst Mail | ★ Catalyst |
| Push notifications | Catalyst Push | ★ Catalyst |
| Event-driven hooks | Catalyst Signals + Event Functions | ★ Catalyst |
| CI/CD | Catalyst Pipelines | ★ Catalyst |
| Observability | Catalyst built-in logs + GCP Cloud Logging for GCP-side | ★ + 🟡 |

**Approx 90/10 Catalyst/Google split** — by intent.

---

## Section 9 — Voice Strategy

### 9.1 Latency budget

| Step | Target | Tech |
|---|---|---|
| Speech-end → VAD silence | 200 ms | `@ricky0123/vad-web` |
| STT streaming → final transcript | +100 ms | Gemini Live API (Kannada) / Catalyst Zia (English/Hindi) |
| Intent route + tool start | +300 ms | QuickML Flash + Circuits |
| Specialist tools (parallel) | +400 ms | SQL/Cypher/RAG/Forecast |
| Synthesis first token | +200 ms | Streaming LLM |
| TTS first audio | +200 ms | Gemini Live API (Kannada) / Catalyst Zia (English/Hindi) |
| **Total to first audio** | **~1.4 s** | |
| Total to full audio | ~3.5 s | |

### 9.2 Tactics to hit the budget
1. Streaming everywhere (STT, LLM, TTS)
2. VAD instead of fixed-timeout silence detection
3. Parallel tool execution in Circuits
4. Region pinning (everything in Catalyst India DC / `asia-south1`)
5. Demo-day: warm pre-flight + min-instances=1
6. Sentence-boundary TTS chunking (don't wait for full synth)

### 9.3 Quality fallback ladder

**Updated after research: Catalyst Zia does NOT support Kannada (English + Hindi only).** Gemini Live API becomes PRIMARY for Kannada with documented exception.

| Language | Primary STT | Fallback STT | Primary TTS | Fallback TTS |
|---|---|---|---|---|
| **Kannada** | 🟡 Gemini Live API (native multimodal) *(Catalyst gap — justified)* | Google Cloud STT (kn-IN) | 🟡 Gemini Live API (native audio out) | Google TTS Neural2 (kn-IN-Wavenet-A) |
| **English** | ★ Catalyst Zia STT | Google Cloud STT (en-IN) | ★ Catalyst Zia TTS | Google TTS Neural2 (en-IN) |
| **Hindi (bonus)** | ★ Catalyst Zia STT | Google Cloud STT (hi-IN) | ★ Catalyst Zia TTS | Google TTS Neural2 (hi-IN) |

**Detection flow:** language detector on transcript → route to appropriate STT/TTS. If Kannada → Gemini Live API. If English/Hindi → Catalyst Zia.

**Architecture upside of Gemini Live:** native multimodal audio in/out collapses STT→LLM→TTS into a single bidirectional API call — potentially sub-second first audio. Vendor count drops from 3 → 2 (Catalyst + Google only).

**Exception justification (to organizers):** *"Catalyst Zia Services do not support Kannada language (kn-IN) as of June 2026 — verified in official Catalyst documentation. Karnataka State Police is the project sponsor and Kannada is the operational language. We use Google Cloud Gemini Live API for Kannada voice only; all English/Hindi voice processing remains on Catalyst Zia. All Google services run in asia-south1 (Mumbai) — India data residency preserved."*

---

## Section 10 — AI / LLM Strategy

### 10.1 Routing
Two-tier routing for cost + speed:
- **Tier 1 (Flash router):** small fast LLM classifies query intent (~300 ms)
- **Tier 2 (Synthesizer):** larger LLM streams the response

### 10.2 Tool taxonomy
Router emits one of:
- `tabular_query` — Data Store SQL
- `graph_query` — Neo4j Cypher
- `semantic_query` — RAG over narratives
- `predictive_query` — Zia AutoML
- `geo_query` — PostGIS / H3 cluster
- `meta_query` — "explain previous answer" → audit-log lookup
- `mixed` — multiple of the above in parallel

### 10.3 Safety rails
- Output guard: synthesized answer must cite source(s) — if no source attached, AI refuses
- Hallucination guard: predictive answers always include confidence interval + caveat
- Bias guard: predictions exclude caste/religion/community features; all flagged outputs land in bias-review queue
- Refusal rules: PII queries blocked at API gateway based on role claims

### 10.4 Evaluation harness
- 100-query Kannada eval set (50 tabular, 25 graph, 25 predictive)
- 100-query English eval set
- Weekly LLM eval runs on dev environment
- Pass/fail criteria: ≥ 90% correct intent route, ≥ 4/5 answer relevance

---

## Section 11 — Security & Compliance

### 11.1 Compliance posture
- **IT Act 2008** — data hosted in India (Catalyst India DC) ✅
- **DPDP Act 2023** — role-based access + audit + deletion API ✅
- **No PII in LLM logs** — masked before any LLM call

### 11.2 RBAC matrix (preview)

| Role | Read | Write | Special |
|---|---|---|---|
| Constable | Own station, last 30 days | — | — |
| Sub-Inspector | Own station, all time | Witness statements | Mobile-only |
| Inspector | Own jurisdiction (sub-division) | Case notes | — |
| SHO | Full station | All | Briefing access |
| DCP | District | Read-only | Cross-station |
| SCRB Analyst | State-wide aggregates | Reports | No case-level PII |
| Admin | All | All | Audit access |

### 11.3 Audit trail (required for every query)
- `request_id, user_id, role, ip, language, raw_query`
- `intent_router_decision, confidence, model_version`
- `tool_calls[] (sql/cypher/embedding/forecast)`
- `data_accessed[] (record_ids, fields)`
- `final_answer, response_lang, latency_ms`
- `user_flagged_as_wrong (bool)`

---

## Section 12 — Team & Ownership

| Person | Role | Modules | Critical-path |
|---|---|---|---|
| A | Data Engineer | Synthetic generator · Catalyst Data Store schema · NCRB ingest · pgvector seeding (or QuickML RAG) | ✅ Day 1 |
| B | AI / Orchestrator | Catalyst Circuits flows · LLM router · SQL/Cypher generators · synthesizer · audit logging | Blocks D |
| C | Graph + Predictive | Neo4j schema · Cypher generator prompts · Zia AutoML training · Vertex AI fallback | Parallel |
| D | Frontend + Maps | Next.js shell · streaming chat · Google Maps panel · React-Flow graph · audit drawer · PDF export | Blocks demo |
| E | Voice + Design + Demo | Gemini Live API (Kannada) + Catalyst Zia (English) · Google Cloud STT/TTS fallback · UI polish · demo script · 3-min video | Final 2 weeks |

**Daily standup 10 AM IST · Friday demos · End-of-week retro.**

---

## Section 13 — Timeline (mapped to hackathon dates)

| Phase | Dates | What happens |
|---|---|---|
| **Setup** | Week 0 (this week) | Register · Catalyst credits claimed · 5-person team confirmed · GCP credits applied · Gemini Live API access · Repo + Catalyst project init · Validation tasks (4 unknowns) |
| **Foundation** | 4 Jun → 18 Jun | Synthetic data generated · Catalyst services wired · Voice loop working in English · Hello-world chat |
| **Workshops** | 4 / 11 / 18 Jun | Problem Statement Explainer · Catalyst workshop · AMA — attend live |
| **Core build** | 19 Jun → 19 Jul | All 9 features integrated · Kannada working end-to-end · Network graph live · First demo video draft |
| **Polish + submit** | 20 Jul → 26 Jul | Demo video v2 · GitHub README · Live URL stable · Submission deck · **Submit by 26 Jul** |
| **Wait + refine** | 27 Jul → 19 Aug | Continue building toward shortlist features · Internal evaluation |
| **Shortlist refinement** | 20 Aug → 30 Aug | Mentor feedback applied · 1 killer feature added · Final polish |
| **Induction + mentor** | 20 → 28 Aug | Mentor-mentee connects · Final architecture review |
| **Final shortlist** | 9 Sep | Make top 6 |
| **Finale prep** | 10 → 25 Sep | Demo rehearsals · backup video · stage choreography · Kannada speaker confirmed |
| **GRAND FINALE** | **26 Sep** | In-person demo day · Win ₹2.5 L |

---

## Section 14 — Demo Strategy (the 3-min video AND the live finale)

### 14.1 The 30-second hook (open with this)
Kannada voice query → live Map/Graph animation → Kannada voice answer → mic drop.

### 14.2 The middle (90 seconds)
- Switch to text mode mid-conversation
- Show network graph traversal animating live
- Hit a follow-up: "Why did you say that?" → audit drawer opens
- Brief mention of stack: *"Built on Zoho Catalyst. India residency. IT Act compliant."*

### 14.3 The close (60 seconds)
- Show role switching (Inspector → SHO) — UI surface changes
- Show predictive forecast with confidence interval
- Pitch line: *"1,650 officer-hours saved daily across Karnataka. Deployable to all 1,100 stations day one."*

### 14.4 Safety nets
- Backup video on USB (in case live demo fails)
- 8–10 golden-path queries pre-tested
- Local fallback running on laptop with cached data
- One teammate's hotspot ready in case venue WiFi fails

---

## Section 15 — Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Catalyst QuickML LLM has poor Kannada quality | Med | High | A/B test at 11 Jun workshop · Gemini 2.5 Pro fallback documented · synthesis-only Gemini call for complex Kannada queries |
| Gemini Live API Kannada quality below bar | Med | High | Validate with 20-query eval in Week 0 · fallback to Google Cloud STT/TTS (kn-IN proven) · last resort: Sarvam.ai (still allowed under exception) |
| Catalyst Data Store no geospatial | Med | Med | H3 indexing in app code · or supplement with read-only Postgres+PostGIS for spatial queries (justify as gap) |
| Live demo internet failure | Low | High | Hotspot · pre-recorded backup video |
| Team member drops out | Low | High | Pair-program critical paths · cross-train on Catalyst |
| Cold-start during demo | Med | High | min-instances=1 + warm-up pings before demo |
| Predictive feature accused of bias | Med | High | Excluded sensitive features · framed as "resource hints" · prepared answer for judges |
| Overscope — half-built features | High | High | Weekly demos · ruthless cuts in week 6 · "all 9 features minimal" > "5 features deep" |
| Sponsor-track violation (third-party misuse) | Med | High | Document every Google usage in `decisions.md` · email organizers for explicit OK on Neo4j + Maps |

---

## Section 16 — NOT in Scope (Explicit Cuts)

We will not build (saved for v2):
- A separate "morning briefing" app product (was Mitra PM critique — out of scope vs problem statement)
- Mobile native iOS/Android apps (mobile-responsive PWA only)
- Full multi-language support beyond Kannada + English
- Investigator productivity workflows beyond querying (no FIR registration UI, no case management)
- Real-time CCTV/IoT integration
- Court-ready statement translation tool
- Witness voice-recording field tool
- Push-based daily briefings to SHOs (Catalyst Cron capability used internally only)
- Multi-tenant deployment for multiple states

**Why these cuts:** they deviate from the literal problem statement, even if individually valuable.

---

## Section 17 — Open Questions (status after research)

### ✅ RESOLVED (from `research-catalyst.md`)

1. ✅ **Catalyst QuickML LLM Serving — resolved.** Only **Qwen 2.5** family hosted (14B Instruct, 7B Coder, 7B Vision). Custom LLM deployment NOT supported. → Strategy: use Qwen 2.5 14B Instruct as primary; augment with Gemini 2.5 Pro for premium Kannada synthesis. Document Qwen Kannada benchmark quality early.

2. ✅ **Catalyst Zia Services voice — resolved.** ASR supports **English + Hindi only as of 2025. NO Kannada.** → Strategy: **Gemini Live API is now PRIMARY** for Kannada voice with formal exception note to organizers (Catalyst has no equivalent for our target language). Google STT as secondary fallback.

3. ✅ **Catalyst Data Store geospatial — resolved.** No PostGIS / spatial indexing. → Strategy: app-level **H3 hexagonal indexing** for hotspot detection; Google Maps for visualization. Document gap.

4. ✅ **Catalyst QuickML RAG embedder — resolved (partial).** Embedder model is opaque / non-configurable. → Strategy: if Kannada retrieval quality is poor, supplement with `gemini-embedding-001` for Kannada chunks. A/B test on 100-query eval set.

### 🟡 STILL OPEN (validate at 11 Jun workshop)

5. **Catalyst Zia AutoML** — time-series forecasting capabilities? Confidence intervals? Custom features?
6. **Catalyst SmartBrowz** — Kannada PDF font rendering quality?
7. **Catalyst Authentication** — custom role claims in JWT? Multi-claim support?
8. **Catalyst Circuits** — parallel branches in a single run? Step retry semantics? Streaming output across steps?
9. **Catalyst free tier exact quotas** — NoSQL free tier `[UNCERTAIN]`, Stratus free tier `[UNCERTAIN]`. Demo-day traffic burst handling?
10. **Third-party allowance** — written confirmation Neo4j AuraDB + Google Maps + Gemini Live API (for Kannada voice gap) + Gemini 2.5 Pro (for premium synth) don't affect validity? **Email organizers this week.**

---

## Section 18 — Decision Log (append-only)

| Date | Decision | Rationale | Reversal cost |
|---|---|---|---|
| 2026-06-13 | Lock Challenge 01 over 02 | Higher demo magic, Kannada moat, fewer competitors | High (full pivot) |
| 2026-06-13 | All 9 features in scope (no morning-briefing pivot) | Stay true to problem statement | Medium |
| 2026-06-13 | Catalyst end-to-end primary | Mandatory per rules · free credits · India residency | None (decided) |
| 2026-06-13 | Google as intentional augmentation, not fallback | Graph + Maps + premium Kannada LLM justified | Low |
| 2026-06-13 | Drop "morning briefing" Mitra product | Deviated from official problem statement | Low |
| 2026-06-13 | Predictive framed as "resource hints", not Minority Report | Bias risk too high; ethical defensibility wins judges | Low |
| 2026-06-13 | Architecture Approach C (Routed multi-modal RAG) | Predictable, parallelizable, explainable | Medium |
| 2026-06-14 | **Gemini Live API = PRIMARY for Kannada voice** (was fallback) | Catalyst Zia confirmed English+Hindi only — no Kannada. Documented gap. | Low |
| 2026-06-14 | **Qwen 2.5 14B Instruct = primary LLM** on QuickML | Only model family on QuickML LLM Serving. Custom deployment NOT supported. | Low |
| 2026-06-14 | **Gemini 2.5 Pro = augmentation** for premium Kannada synthesis | A/B test vs Qwen 2.5 on Kannada eval set | Low |
| 2026-06-14 | **App-level H3 indexing** for hotspots (no PostGIS) | Catalyst Data Store has no spatial support. H3 + Google Maps. | Low |
| 2026-06-14 | Investigating ranks targeted = PSI, PI, DySP | Confirmed by Karnataka HC 2022 + research brief | Low |
| 2026-06-16 | **Product renamed: KSP Saathi → Yaksha** (codename `ksp-saathi` retained for code paths) | "Yaksha" = Sanskrit/Kannada guardian spirit — culturally resonant for police AI; better demo brand | None |
| 2026-06-16 | **Kannada CONFIRMED on Gemini Live API** (per docs harvest) | BCP-47 `kn-IN` supported on `gemini-3.1-flash-live-preview`. Also `gemini-3.5-live-translate-preview` for witness-statement translation. Removes our biggest open risk. | None |
| 2026-06-16 | **⚠ Catalyst Circuits is NOT available in India DC** (per docs harvest) | Orchestration moves from YAML Circuits → Python "orchestrator" Function that chains specialist functions sequentially/parallel via httpx | Medium — `circuits/main-query-flow.yaml` replaced by `functions/orchestrator/index.py` |
| 2026-06-16 | **Catalyst Zia has NO native STT/TTS** (per docs harvest) | Voice path always external (Gemini Live primary, Google STT/TTS fallback). Strengthens our justified-gap argument. | None |
| 2026-06-16 | **Gemini Live API replaces Sarvam.ai for Kannada voice** | Single vendor (Catalyst + Google only) · native multimodal collapses STT→LLM→TTS into one call · potentially <1s first audio · simpler exception story for organizers | Low — must verify Kannada quality in validation week |

---

## Section 19 — Companion Artifacts

| File | Purpose | Status |
|---|---|---|
| `research-investigators.md` | PSI/PI/DySP personas · 15 bilingual queries · pain points | ✅ Written |
| `research-catalyst.md` | Per-service capability + limits + 3 critical gaps | ✅ Written |
| `data/generate_synthetic_firs.py` | 50K-record FIR generator | ✅ Written |
| `data/README.md` | Data schema + how to load to Catalyst | ✅ Written |
| `data/firs.jsonl` | 50,000 synthetic FIRs (91 MB) | ✅ Generated |
| `data/firs_sample.jsonl` | First 100 FIRs for testing | ✅ Generated |
| `README.md` | Project overview | ✅ Exists |
| `challenges.md` · `timeline.md` · `rewards.md` · `faqs.md` · `terms-and-conditions.md` | Hackathon docs | ✅ Exists |
| `decisions.md` | Justification log for every Google service usage | 📋 Next-up |
| `validation-checklist.md` | The 6 still-open questions, owned by teammates | 📋 Next-up |
| `demo-script.md` | 3-min video script + finale stage script | 📋 Week 8 |
| `email-organizers.md` | Draft of email asking for written OK on Neo4j/Google Maps/Gemini augmentations | 📋 This week |

---

## Section 20 — Implementation Plan (next 7 days)

| Day | Owner | Task |
|---|---|---|
| Today | Everyone | Register on hack2skill · claim Catalyst credits · sign up Gemini Live API |
| +1 | A | Run `generate_synthetic_firs.py` → 50K records · upload to Catalyst Data Store |
| +1 | B | Catalyst project init · Functions hello-world · Circuits hello-world |
| +1 | C | Neo4j AuraDB Free account · schema design · ingest people/cases from synthetic |
| +1 | D | Next.js scaffold · deploy to Catalyst Web Client Hosting · Auth integration |
| +1 | E | **Gemini Live API Kannada quality test** (20-query bilingual eval set) · Catalyst Zia test for English/Hindi · Google Cloud STT/TTS fallback verified |
| +2 | All | Validation checklist execution (10 open questions) |
| +3 | B | First end-to-end query: voice in (English) → SQL → answer → voice out |
| +4 | All | Friday demo: end-to-end English voice query working |
| +7 | All | Friday demo: Kannada query working end-to-end |

---

**This design doc is the single source of truth. All implementation decisions reference back to this doc. Updates go in Section 18 (Decision Log) — append-only, never edit.**

*Locked: 2026-06-13. Owner: Team. Next review: 11 Jun Catalyst workshop.*
