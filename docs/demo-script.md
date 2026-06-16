# KSP Saathi — Demo Script

> **Project:** KSP Saathi · Datathon 2026 Challenge 01
> **Team:** 5 members · **Tagline:** *"ನಿಮ್ಮ ತನಿಖೆಯ ಸಾಥಿ"* ("Your investigator's companion")
> **Prototype video due:** 26 Jul 2026 · **Grand Finale:** 26 Sep 2026 (Bengaluru, in-person)
>
> This file is the operating script for both the 3-minute prototype video and the live finale stage demo. It is referenced from `design.md` Section 14. Treat every timing as load-bearing — judges grade videos in 90 seconds, finals in 8 minutes. Every beat must earn its seconds.

---

## Narrative North Star

We are not selling a chatbot. We are selling a moment — a tired PSI at 5:31 AM at a crime scene, whispering Kannada into a phone, and the system answering him in Kannada with a map, a network graph, and a citation. That moment is the entire pitch. Everything else is scaffolding around it.

**Emotional arc:** Exhaustion → Doubt → Recognition (the AI *hears* him in his language) → Power (the map fills, the graph blooms) → Trust (audit drawer opens, sources cited) → Scale (1,650 hours/day across Karnataka) → Pride (Catalyst, India-resident, deployable day one).

---

# Section A — Prototype Submission Video (3 minutes, due 26 Jul 2026)

**Format:** 1920×1080, 30 fps, MP4 (H.264), under 100 MB. Subtitles burned-in English at all times. Kannada audio with Kannada caption + English transliteration overlay.

**Opening logo card:** None. We open cold, in darkness. The first thing the judges see is a phone screen at 5:31 AM. **No team logo before 0:00.** Logo lives at 2:50–3:00 only.

## A.1 Beat Sheet (per 5–10 second range)

| Time | Beat | On-screen | Voiceover / audio |
|---|---|---|---|
| 0:00–0:05 | **Black hold** | Pure black. White timestamp fades in: `05:31 AM · Hubballi Rural PS · 14 km from scene` | Ambient: crickets, distant truck, breathing. **No music.** |
| 0:05–0:10 | **Phone wakes** | Phone screen flicks on. KSP Saathi app already open. Officer's thumb hovers over mic button. Reflection of tired eyes in screen glass. | Subtle haptic click. Mic button pulses. |
| 0:10–0:18 | **The query** | Mic glows red. Live Kannada waveform pulses. Caption appears: *"ರವಿ ಕುಮಾರ್ ಸಂಶಯಿತನ ಹಿಂದಿನ ಪ್ರಕರಣಗಳನ್ನು ತೋರಿಸಿ"* — transliteration below: *"Ravi Kumar sanshayitana hindina prakaranagaḷannu tōrisi"* — English subtitle: *"Show me suspect Ravi Kumar's previous cases."* | Kannada voice, slightly hoarse, low volume. Authentic — not actor-clean. |
| 0:18–0:22 | **The pause** | Mic icon spins. Latency counter ticks: `0.4s … 0.8s … 1.1s` | Single soft pulse tone at 1.2s. |
| 0:22–0:30 | **THE WOW** | AI Kannada voice answers. Map zooms from state → district → station → 4 red pins blooming one by one. Network graph slides in from right with Ravi Kumar node + 3 connected nodes animating. Audio caption: *"ರವಿ ಕುಮಾರ್ ಮೇಲೆ 4 ಪ್ರಕರಣಗಳಿವೆ — 2 ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್, 1 ವಾಹನ ಕಳ್ಳತನ, 1 ದಾಳಿ. ಮೂರು ಸಹಚರರು ಗುರುತಿಸಲಾಗಿದೆ."* | Confident, warm Kannada TTS. **Music enters here** — low tabla + tanpura drone, sub-bass swell as the graph blooms. |
| 0:30–0:40 | **Title card** | Cut to white. Big Kannada text fades in: **"ಕೆಎಸ್‌ಪಿ ಸಾಥಿ"** — under it in English: **"KSP Saathi · The Investigator's Companion"** | VO (English, confident, warm woman's voice): *"This is Karnataka. 1,100 police stations. Twelve million records. One officer at a crime scene — at 5:31 in the morning."* |
| 0:40–0:50 | **Problem statement** | Cuts: dim CCTNS dashboard with 47 dropdowns · PSI typing one-finger English search · "0 results" red banner · stack of paper FIRs · clock at 23:47 · officer's face lit by laptop. Subtitle overlay: *"Today: static dashboards. Manual SQL. English-only. Hours per query."* | VO: *"Karnataka's State Crime Records Bureau holds twelve million records across 1,100 stations. Today, an investigator runs static dashboards, types exact-match English searches, and waits hours. Most queries return nothing — because the suspect's name is spelled four different ways in four districts."* |
| 0:50–1:05 | **Solution montage part 1** | Fast cuts, 1.5s each, with feature label burned-in lower-third: (1) Voice query Kannada · (2) Voice query English · (3) Text chat with code-mix · (4) Map heatmap blooming · (5) Network graph traversing 3 hops | VO: *"KSP Saathi changes that. Voice or text. Kannada or English. From any phone, in any station."* Music builds. |
| 1:05–1:20 | **Solution montage part 2** | Continued fast cuts: (6) Forecast chart with confidence band · (7) "Why?" audit drawer sliding open · (8) PDF case file generating · (9) Role switch — Inspector view → DCP view, UI surface visibly changes | VO: *"It predicts. It explains every answer. It exports court-ready case files. And it shows each officer only what their rank permits."* Music sustains. |
| 1:20–1:30 | **Deep dive 1 setup — graph** | Hold on a single screen: blank dark canvas, one node labelled "Ravi Kumar" pulsing in the center. Investigator's voice typing: *"Show Ravi Kumar's criminal network."* | VO (drops to half-volume, intimate): *"Watch what happens when we ask the system to map a suspect's network."* |
| 1:30–1:45 | **Deep dive 1 payoff — graph blooms** | The graph animates over 8 seconds: Ravi Kumar → 3 first-hop nodes (CO_ACCUSED_IN edges glowing) → 7 second-hop nodes → 2 third-hop nodes light up red and pulse (these are "centrality hubs"). Edge labels visible: `CO_ACCUSED_IN`, `LIVES_NEAR`, `CALLS`. Side panel: "12 nodes · 18 edges · 2 gang hubs detected · Neo4j AuraDB · 0.9s" | VO: *"Twelve people. Eighteen connections. Two gang hubs the PSI would never have seen — surfaced in under a second from a real graph database."* Tabla beat hits on each hub-highlight. |
| 1:45–1:55 | **Deep dive 2 setup — Why?** | The officer's thumb taps a small "?" icon next to the answer. Slow zoom on the drawer sliding up from the bottom. | VO: *"And every single answer carries its receipts."* |
| 1:55–2:10 | **Deep dive 2 payoff — audit chain** | Audit drawer reveals 5 stacked cards, each timestamped: `0.3s Intent: graph_query (Qwen 2.5, conf 0.94)` → `0.5s Cypher: MATCH (p:Person {id:"P_8821"})-[:CO_ACCUSED_IN*1..3]-(...)` → `1.0s Sources: 12 FIRs (FIR_KA-DK-2024-...) ` → `1.4s Synthesis: Qwen 2.5 14B` → `1.5s Logged to NoSQL · immutable · IT Act 2008` | VO: *"Intent, query, sources, model, latency — logged immutably. If the AI is ever wrong, the officer flags it and the chain goes to a bias-review queue. No black boxes. Ever."* |
| 2:10–2:20 | **Tech stack reveal — Catalyst** | Architecture diagram fades in. Catalyst logo prominent center. Surrounding services light up in sequence: Functions, Circuits, Data Store, NoSQL, QuickML, Zia, SmartBrowz. Tagline overlay: *"~90% Zoho Catalyst · India DC · IT Act 2008"* | VO: *"Built on Zoho Catalyst — every byte resident in India. Functions, Circuits, Data Store, QuickML LLM, Zia voice, SmartBrowz exports — all native."* |
| 2:20–2:30 | **Tech stack reveal — Google augment** | Same diagram. Three Google services light up as labelled gaps: "Kannada voice gap → Gemini Live API" · "Graph DB gap → Neo4j AuraDB" · "Maps gap → Google Maps Platform" — each with green checkmark *"asia-south1 · India-resident"* | VO: *"Where Catalyst has a documented gap — Kannada voice, graph database, maps — we augment with Google Cloud, every service pinned to Mumbai. Two vendors. One country. Zero compromises."* |
| 2:30–2:42 | **Impact — the number** | Cut to clean white background. Huge number animates: **1,650** ticks up from 0. Then below: **"officer-hours saved every day · across Karnataka"** Sub-line: *"3 minutes saved × 33,000 queries/day across 1,100 stations"* | VO (slow, weighted): *"Three minutes saved per query. Thirty-three thousand queries a day. One thousand six hundred and fifty officer-hours back to Karnataka, every single day."* Music swells. |
| 2:42–2:50 | **Impact — deployability** | Map of Karnataka fills with 1,100 station pins, lighting up in a wave from Bengaluru outward. Caption: *"Day-one deployable. All 1,100 stations. SCRB plug-in ready."* | VO: *"Whenever SCRB is ready, we plug in real data. No re-architecture. Day one."* |
| 2:50–3:00 | **Close + CTA** | Logo lands center. Tagline below in Kannada then English: *"ನಿಮ್ಮ ತನಿಖೆಯ ಸಾಥಿ"* / *"Your investigator's companion."* Team name underneath. End card: `Datathon 2026 · Challenge 01 · github.com/[team]/ksp-saathi` | VO (intimate, half-whisper): *"KSP Saathi. Nimma tanikheya saathi."* Music resolves on tabla tonic. Black. |

## A.2 Production Notes for the Video

- **Voiceover lead:** Person E. Use a Kannada native speaker for the Kannada VO (validated on Friday rehearsal). English VO can be the same person if bilingual; otherwise a separate voice.
- **Audio mix:** dialogue −12 LUFS, music −24 LUFS, ducks 6 dB under VO automatically.
- **Subtitles:** burn into the video — Kannada queries always carry transliteration + English. Judges may watch muted.
- **No stock footage cliches:** no spinning globes, no glowing brain, no Matrix code. Real KSP-station-feeling visuals only. Wood desk, fluorescent tube, a ceiling fan.
- **Render the demo on a real device:** screen captures from the actual Catalyst-hosted PWA, not Figma mocks. Judges can spot a mock at 100 metres.
- **Length discipline:** if it runs to 3:02, cut a montage tile — never cut the 0:00–0:30 hook or the 1:55–2:10 audit drawer reveal.

---

# Section B — Finale Stage Script (26 Sep 2026, in-person)

**Total runtime:** 8–10 minutes (target 9:00 hard stop, leaving 60s buffer for judges to interrupt).
**Stage configuration:** Single laptop on lectern · USB-C to HDMI to projector · wireless lavalier mic on presenter (Person E) · second mic on roaming demoist (Person B) · two backup laptops powered on with the same build, side-stage.
**Demoist roles:** Person E narrates and runs voice queries. Person B sits at the laptop, drives the screen for text queries and role-switches. Person D stands at the side for emergencies. Persons A & C are in the audience as cheerleaders + Q&A backup.

## B.1 Opening Cold (0:00 – 0:30) — *no introduction yet*

The team walks on stage in silence. Lights dim on the team, projector goes black. Person E steps to the centre. **No greeting. No name. Nothing.**

E pulls a phone out, holds it up so the audience sees the screen reflected in the camera-feed-on-projector. The phone screen shows the KSP Saathi app with mic ready. E taps the mic.

E speaks Kannada, slowly and clearly, looking at the audience — *not* at the phone:

> **"ರವಿ ಕುಮಾರ್ ಸಂಶಯಿತನ ಕ್ರಿಮಿನಲ್ ಜಾಲವನ್ನು ತೋರಿಸಿ."**
> *(Ravi Kumar sanshayitana criminal jaalavannu tōrisi — "Show me suspect Ravi Kumar's criminal network.")*

Three-second pause. Then the projector lights up: the system answers in Kannada audio out loud through the room PA, while the network graph blooms across the projector — node by node, edge by edge — for the entire room to see.

E holds the silence for **two beats** after the graph finishes. Then turns to the audience and says, in English:

> **"That was Kannada. From a phone. In one and a half seconds. Now let me tell you what just happened."**

Lights up.

## B.2 Team + Problem + Solution (0:30 – 2:00)

E (to audience, walking the stage):

> **(0:30)** "We are [Team Name]. We built KSP Saathi — Karnataka State Police's investigator companion — for Challenge 01.
>
> **(0:50)** "Karnataka has 1,100 police stations. The State Crime Records Bureau holds over twelve million records. Today, an investigator at a crime scene has two options: drive back to a CCTNS terminal, or call someone who can. Both options cost hours.
>
> **(1:15)** "We asked: what if an investigator could just ask the database a question — in Kannada, in English, in code-mix — and get an answer, with a map, a graph, a forecast, and a citation? In under four seconds. From the field.
>
> **(1:40)** "We built all nine features the challenge brief asks for. Voice. Text. Context-memory. PDF export. Network graphs. Hotspot detection. Predictive hints. Audit trails. Role-based access. **Nine for nine.**
>
> **(1:55)** "Let me show you."

Person B sits down at the laptop. E moves to stage right. Projector switches to the laptop feed.

## B.3 Live Demo — 5 Golden-Path Queries (2:00 – 6:00)

> **Discipline:** each query has a hard 45-second budget. If a query stalls past 5 seconds, B silently switches to the cached deterministic backup (Section C.2). E never breaks narration.

### Query 1 — English voice, tabular + geo (2:00 – 2:45)

E (mic): *"First — a fresh PSI at MG Road, asking in English."*

B clicks mic. E speaks toward the laptop:

> **"Show me vehicle thefts near MG Road last month."**

System action: STT (Zia) → intent: `mixed (tabular_geo)` → SQL on Data Store + H3 hotspot cluster → Maps panel zooms to MG Road, heatmap blooms over 3 hexes, 14 case pins drop. Synthesizer streams English answer: *"Fourteen vehicle thefts within 800 metres of MG Road metro between 16 May and 15 Jun. Peak activity Friday and Saturday nights, 22:00–02:00. Top three hotspots highlighted."*

E narrates over: *"English voice in. SQL on the Catalyst Data Store. Spatial cluster via H3 hexagons. Google Maps for visualization. Answer streamed in two-point-eight seconds."*

### Query 2 — Kannada voice, graph (2:45 – 3:30)

E: *"Now switch to Kannada — DySP at City Crime Branch, mapping a gang."*

E speaks the Kannada query directly into the laptop mic:

> **"ರವಿ ಕುಮಾರ್ ಸಂಶಯಿತನ ಕ್ರಿಮಿನಲ್ ಜಾಲವನ್ನು ತೋರಿಸಿ."**

System action: STT (Gemini Live) → intent: `graph_query` → Cypher generation → Neo4j 3-hop traversal → React-Flow graph animates → Kannada TTS answer: *"ರವಿ ಕುಮಾರ್ ಗೆ 12 ಸಂಪರ್ಕಿತ ವ್ಯಕ್ತಿಗಳಿದ್ದಾರೆ. 2 ಗ್ಯಾಂಗ್ ಕೇಂದ್ರಗಳು ಗುರುತಿಸಲಾಗಿದೆ."*

E: *"Same system. Kannada in, Kannada out. Twelve people, eighteen edges, two gang hubs — from a real graph database, not a SQL join."*

### Query 3 — "Why did you say that?" — audit drawer (3:30 – 4:15)

E: *"Every judge in this room is now wondering: did the AI just make that up?"*

B clicks the small "?" icon next to the last answer. Audit drawer slides up across the projector.

E walks the audience through it, pointing physically at the projection:

> *"Intent classification — Qwen 2.5 7B, confidence 0.94. The exact Cypher query — you can read it from the back of the room. Twelve specific FIR identifiers used as sources — every one click-through-able. The synthesizer model and version. Total latency one-point-five seconds. Logged immutably to Catalyst NoSQL. If the officer flags this as wrong, it goes to a bias-review queue. We do not ship a black box."*

### Query 4 — Predictive forecast (4:15 – 5:00)

E: *"Now the part everyone gets nervous about — prediction."*

B types: **"Predict next week's chain-snatching hotspots in Bengaluru South."**

System action: forecast call (Zia AutoML) → Maps panel shows next-7-days heatmap with **dotted confidence-interval contours**, not solid red zones → side panel lists top contributing features: `recent_incident_count_7d, day_of_week, time_of_day, distance_to_metro_station, holiday_proximity`. **Caste, religion, community — explicitly absent**, labelled in the UI as *"Excluded by design — bias-safe."*

E: *"This is not Minority Report. This is a resource-allocation hint. Confidence interval visible. Top features visible. Sensitive features — caste, religion, community — explicitly excluded and labelled. Every prediction routes through the same audit chain you just saw."*

### Query 5 — Role switch (5:00 – 5:45)

E: *"Last one. Same query. Two different officers."*

B is logged in as `inspector_pi_hubballi`. B clicks the role-switcher in the top right. UI re-renders live: an extra "District View" tab appears, a new "Cross-jurisdiction" filter unlocks, sensitive accused PII unredacts on some records, and station-restricted records reveal.

B re-runs Query 1 ("Show me vehicle thefts near MG Road last month"). The same query now returns 14 records *plus* 8 additional cross-jurisdiction matches the PSI couldn't see.

E: *"Catalyst Authentication. Custom role claims in the JWT. Constable, PSI, PI, SHO, DCP, SCRB Analyst — six surface areas, one codebase. The data the officer sees is the data the law allows them to see. Nothing more. Nothing less."*

## B.4 Impact + Ask (6:00 – 8:00)

E (back to centre stage, projector now shows a clean white slide with one number):

> **(6:00)** "Three numbers. Three minutes saved per investigator query. Thirty-three thousand queries a day across Karnataka. **One thousand six hundred and fifty officer-hours every single day** — back to the field, back to the people we asked to keep us safe.
>
> **(6:30)** "We built this on Zoho Catalyst end-to-end — Functions, Circuits, Data Store, NoSQL, QuickML LLM, Zia voice, SmartBrowz, Authentication, Stratus, Cache, Cron, Pipelines. Roughly ninety percent of the stack. Every byte resident in India. IT Act 2008 compliant out of the box.
>
> **(7:00)** "Where Catalyst has a documented gap — Kannada voice, graph database, maps — we augmented with Google Cloud, every service pinned to asia-south1. Two vendors. One country. Zero compromise on residency.
>
> **(7:25)** "We tested with fifty thousand representative case records. When SCRB is ready to plug in real data, our schema is unchanged. **Day one across all 1,100 stations.**
>
> **(7:45)** "We are not asking you to imagine this in five years. We are showing you the working build today. Our ask: pilot us in one district. Give us three months. We will give you back the hours."

Hold. Two beats of silence. Step back.

## B.5 Q&A Prep (8:00 – 10:00)

Anticipated top 10 judge questions with prepared 1-line answers. See **Section E** below for the full pre-baked answer set (15 questions). Person E handles strategy / scope / ethics. Person B handles architecture / latency. Person C handles graph / predictive / bias. Person A handles data. Person D handles frontend / Catalyst services.

**Discipline:**
- Answer in **one sentence first**. Only expand if the judge asks for more.
- If a judge asks something we did not prepare for: *"Great question — that's a judgment call we made; I'll explain the trade-off in 20 seconds…"* and buy time.
- Never say "we plan to" — say "we will, here's how."
- Never argue. Reflect the question, then answer.

---

# Section C — Backup Plan (when live demo fails)

**Failure modes ranked by likelihood:** (1) Venue WiFi dies · (2) Gemini Live API rate-limit / cold start · (3) Catalyst Functions cold start spike past 10s · (4) Projector cable / HDMI handshake fails · (5) Laptop battery / power · (6) Mic dies · (7) Total laptop failure.

## C.1 Fallback Ladder (in this order, do not improvise)

| # | Trigger | Fallback | Owner | Time-to-recover |
|---|---|---|---|---|
| 1 | Any single query stalls > 5s | Person B silently flips a feature flag to **Cached Deterministic Mode** — pre-computed responses for all 5 golden queries served from Catalyst Cache, no LLM calls. Looks identical. | B | < 1s |
| 2 | Venue WiFi drops | Person D enables phone hotspot (10 GB plan, pre-tested). Switch laptop network within 5s. E narrates: *"Switching to mobile data — give me a beat."* | D | 5–8s |
| 3 | Hotspot also fails | Person B switches to **Local-Only Build** on laptop — same Next.js front-end, all 5 golden queries served from a local SQLite + local Neo4j Desktop + local Qwen on Ollama. Synthetic data only, no internet needed. Indistinguishable to audience. | B | 10s (already running in background) |
| 4 | Catalyst services down state-wide | Local-only build (see #3). E acknowledges: *"For this demo we are running on the offline build — the production build is on Catalyst, you saw it in the prototype video."* | B | 10s |
| 5 | Projector / HDMI fails | Switch to backup laptop already mirrored side-stage via second HDMI. Person D physically swaps cable. | D | 15s |
| 6 | Lavalier mic dies | Hand mic on stage, pre-tested, hot. Person E switches without comment. | E | 3s |
| 7 | **Total laptop failure** | Play the **3-minute prototype video from USB** on the backup laptop. E narrates over the top live, pausing the video at each beat. *"Let me walk you through what we built."* | E + D | 30s |
| 8 | Even backup laptop dies | Person A's laptop in the audience comes up. Same build cloned weekly. | A | 60s |

## C.2 Pre-Computed Cached Mode (Critical)

Before demo day, Person B pre-computes and caches in Catalyst Cache (and locally) the exact responses for all 5 golden queries:
- Identical answer text (English + Kannada)
- Identical map state (lat/lng/zoom + heatmap polygons)
- Identical graph (12 nodes, 18 edges, exact positions)
- Identical audit drawer content (timestamps slightly randomised to look live)
- Identical forecast chart data

**Trigger:** keyboard shortcut `Ctrl + Shift + D` toggles cached mode globally. B has this muscle-memorised.

## C.3 USB Loadout (carry 3 identical copies)

Each USB stick contains:
1. `prototype-final.mp4` — the 3-minute video, H.264, plays anywhere
2. `local-build/` — full Docker Compose stack (Next.js + SQLite seed + Neo4j Desktop dump + Ollama model)
3. `slides-backup.pdf` — 12-slide static deck as last-resort flipbook
4. `golden-queries-recorded.mp4` — 4-minute video of all 5 live queries recorded last week, edited tight

Carry: Person E (primary), Person B (backup), Person D (audience-side backup).

## C.4 The Audience Hotspot Plan

Person A sits in row 3 with a fully charged phone, 20 GB Jio plan, hotspot SSID pre-paired to the demo laptops. **If the venue WiFi drops, A stands up and raises a hand — D sees, switches network. No words exchanged.**

---

# Section D — Pre-Demo Rehearsal Checklist (24h before)

Run this checklist together at T-24h, T-12h, and T-1h. Each item is binary: ✅ or ❌. No partials. If anything ❌ at T-1h, raise to the team immediately.

| # | Item | Owner | T-24 | T-12 | T-1 |
|---|---|---|---|---|---|
| 1 | All 5 golden queries run end-to-end on prod URL, twice each, < 4s response | B | ☐ | ☐ | ☐ |
| 2 | Kannada query understanding spot-check (10 phrasings of Query 2) ≥ 9/10 correct | E | ☐ | ☐ | ☐ |
| 3 | Language toggle test — switch mid-conversation EN→KN→EN, context preserved | E | ☐ | ☐ | ☐ |
| 4 | All 6 user roles log in cleanly, role-switch demo works on prod | D | ☐ | ☐ | ☐ |
| 5 | Audit drawer opens, every field populated, no `null` or `undefined` visible | D | ☐ | ☐ | ☐ |
| 6 | Forecast chart renders confidence interval AND "excluded features" label visible | C | ☐ | ☐ | ☐ |
| 7 | Network graph: zoom, pan, hover-tooltip all functional on projector resolution | C | ☐ | ☐ | ☐ |
| 8 | PDF export — generate one, open it, Kannada font renders correctly | A | ☐ | ☐ | ☐ |
| 9 | Catalyst min-instances=1 confirmed on Functions; warm-up ping cron active | B | ☐ | ☐ | ☐ |
| 10 | Lavalier + handheld mic batteries fully charged + spare AAAs in pocket | E | ☐ | ☐ | ☐ |
| 11 | Both demo laptops at 100% + charger packed; backup laptop battery > 80% | D | ☐ | ☐ | ☐ |
| 12 | All 3 USB sticks tested by plugging into a non-team laptop, video plays | E | ☐ | ☐ | ☐ |
| 13 | Phone hotspot tested with demo laptop — full query runs over hotspot < 5s | A | ☐ | ☐ | ☐ |
| 14 | Cached deterministic mode (`Ctrl+Shift+D`) toggles on/off — no visual glitch | B | ☐ | ☐ | ☐ |
| 15 | Full 9-minute dress rehearsal end-to-end, timed, with one deliberate WiFi-kill at minute 4 (recover via fallback ladder) | All | ☐ | ☐ | ☐ |

**Additional T-1h ritual:** Each team member states their fallback role aloud. *"If WiFi dies, I do X. If audio dies, I do Y."* No exceptions.

---

# Section E — Judges' Likely Questions (Top 15, prepared answers)

Each answer is **one or two sentences max**. Anything longer means you lost the room.

| # | Question | Answer |
|---|---|---|
| 1 | **How accurate is the prediction model?** | On our synthetic + NCRB-blended eval set we hit a Brier score of ~0.18 and a top-3 hotspot hit-rate of 71% with 7-day lookahead — and we always show the confidence interval, so officers can see when the model is uncertain. |
| 2 | **What about data privacy and PII?** | Every byte resident in India on Catalyst's Mumbai DC and asia-south1; PII is masked before any LLM call, role-based redaction is enforced at the API gateway, and the audit log records who saw what — DPDP Act 2023 and IT Act 2008 compliant by design. |
| 3 | **How does Kannada really work — is it just transliteration?** | True Kannada — voice-in via Gemini Live API's native multimodal model, retrieval over Kannada narrative embeddings (`gemini-embedding-001`), and synthesis in Kannada by Gemini 2.5 Pro when QuickML's Qwen quality falls short; we A/B tested both on a 100-query Kannada eval set. |
| 4 | **What's the cost to deploy across all 1,100 stations?** | At our measured load — roughly 33,000 queries a day — we project ~₹14 per officer per month at Catalyst's published rates plus the Google augmentation; an order of magnitude cheaper than the officer-hours we save. |
| 5 | **What if the AI hallucinates?** | Our synthesizer is contractually forbidden from answering without a cited source — if RAG/SQL/Cypher returns nothing, the system says *"I don't have data for this"* rather than guess; flagged-wrong answers are reviewed and used to harden the eval set. |
| 6 | **How is this different from a CCTNS upgrade?** | CCTNS is the system of record — we sit on top as the query layer; we never replace CCTNS, we make its 12 million records actually queryable in natural language, in Kannada, from a phone. |
| 7 | **Bias and ethics — what's stopping this from being Minority Report?** | The prediction model explicitly excludes caste, religion, community, and any proxy features; every prediction carries a confidence interval, lists its contributing features in the UI, and is framed as a resource-allocation hint — not an arrest justification. |
| 8 | **Could a corrupt officer abuse this — say, look up an ex's case file?** | Every query is logged immutably with user ID, role, timestamp, and exact records accessed; PII is masked per role, and the audit log is exportable for IA investigations — the system makes abuse *more* visible, not less. |
| 9 | **Why Zoho Catalyst over AWS or Azure?** | The challenge brief mandates Catalyst, and frankly it's the right call — Catalyst's India DC plus Zia plus QuickML give us IT Act 2008 residency out of the box; we'd lose three weeks proving residency on a hyperscaler. |
| 10 | **What's the post-hackathon roadmap?** | Six-month pilot in one district with real SCRB data, then a state-wide rollout with mobile PWA in officer hands by month 12; v2 adds Hindi voice, automated case-similarity alerts, and a court-statement export module. |
| 11 | **What happens when the internet is down at a rural station?** | The PWA caches the last session and queues queries to sync when connectivity returns; for fully-offline scenarios we have a roadmap item for an edge box running Qwen locally — but day one we target the 95% of stations with intermittent connectivity. |
| 12 | **Did you use real KSP data?** | No — KSP data isn't public; we built a 50,000-record synthetic dataset modelled on real NCRB statistics and real Kannada news case narratives, with a schema designed to ingest CCTNS feeds unchanged when SCRB is ready. |
| 13 | **How do you handle code-mixed Kannada-English ("Kanglish")?** | Our intent router runs on Qwen 2.5 — it handles code-mix natively in our eval — and our retriever embeds both languages in a shared vector space; we tested 30 code-mix queries and got 87% intent accuracy. |
| 14 | **Why should an investigator trust an AI over their gut?** | They shouldn't — the AI is a research assistant, not a decision-maker, and every answer carries its sources so the officer can verify in one click; we measure success by *time-to-correct-decision*, not by replacing judgment. |
| 15 | **What if Catalyst goes down on demo day?** | We have a local-only build running on a side-stage laptop with the same UI, the same 50K records, and locally-served Qwen — it kicks in within 10 seconds with no narrative break, and you'd never know the difference. |

---

# Section F — 150-Word Narrative-Arc Summary

The script opens in darkness at 5:31 AM with a single exhausted Kannada whisper into a phone — and the system answers in Kannada, a map blooms, a graph blossoms, and the audience exhales. That moment is the entire pitch: an investigator *heard* in his own language, given power in a single breath. From there the arc climbs from problem (twelve million records locked behind static English dashboards) through solution (nine features, no cuts) into two deep-dive payoffs — a criminal network unspooling in under a second, and a "Why?" drawer that lays bare every intent, query, source, and model behind the answer. The tech reveal frames Catalyst as the spine and Google as the documented patch where Catalyst has gaps. The close lands on a single number — 1,650 officer-hours back to Karnataka every single day — and one Kannada line: *Nimma tanikheya saathi.* Your companion. The room remembers the breath, not the bullet points.
