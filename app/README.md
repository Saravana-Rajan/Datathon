# KSP Saathi

> **Bilingual voice AI for Karnataka Police, end-to-end on Catalyst.** Investigators query 1,100+ stations of crime data by voice (Kannada or English), see networks and hotspots on a live map, get predictive resource hints, and export audit-ready PDFs — with full IT Act 2008 compliance and India-only data residency.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built on Zoho Catalyst](https://img.shields.io/badge/Built%20on-Zoho%20Catalyst-blue.svg)](https://catalyst.zoho.com)
[![Datathon 2026](https://img.shields.io/badge/Datathon-2026-orange.svg)](#hackathon-context)
[![Region: asia-south1](https://img.shields.io/badge/Region-asia--south1-green.svg)](#)

---

## The 30-Second Pitch

A Karnataka PSI at a remote rural station opens KSP Saathi on her phone and asks in Kannada:

> *"ಈ ಸಂಶಯಿತನ ಮೇಲೆ ಮೊದಲು ಎಷ್ಟು ಪ್ರಕರಣಗಳಿವೆ?"*
> ("How many prior cases does this suspect have?")

Within **1.4 seconds** the first audio chunk plays back. The map zooms to the suspect's hotspot. A criminal network graph fans out behind it. An "Explain" drawer shows the SQL, Cypher, and RAG sources that produced the answer. Every byte stayed in India.

KSP Saathi delivers **all 9 features** from Datathon 2026 Challenge 01 — natural language chat, voice interaction, context memory, PDF export, network visualization, hotspot detection, predictive analytics, explainable AI, and role-based access — running ~90% on Zoho Catalyst with intentionally justified Google augmentations for the gaps.

---

## Live Demo

| Resource | URL |
|---|---|
| Production app | `https://saathi.ksp-datathon.dev` *(deploys live during Datathon)* |
| 3-minute demo video | `https://youtu.be/ksp-saathi-demo` *(linked at submission)* |
| Pitch deck | `https://saathi.ksp-datathon.dev/deck.pdf` |
| API health check | `https://saathi.ksp-datathon.dev/api/health` |

> Demo credentials are issued per judge — request via the submission portal.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND  — Next.js 15 + shadcn/ui + Vercel AI SDK              │
│  Catalyst Web Client Hosting · Catalyst Domain Mappings          │
│  Chat (voice + text) | Map | Network Graph | Audit Drawer        │
└─────────────────────────────┬────────────────────────────────────┘
                              │  WSS + REST (JWT auth)
┌─────────────────────────────▼────────────────────────────────────┐
│  EDGE  — Catalyst API Gateway                                    │
│  Catalyst Authentication (role claims) · Audit logger → NoSQL    │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│  ORCHESTRATOR  — Catalyst Circuits + Functions                   │
│                                                                  │
│  STEP 1 — Intent Router  (Qwen 2.5 7B on QuickML, ~300ms)        │
│            classifies: tabular / graph / RAG / predict / mixed   │
│                                                                  │
│  STEP 2 — Parallel specialists                                   │
│    ├── SQL Gen        → Catalyst Data Store (FIR records)        │
│    ├── Cypher Gen     → Neo4j AuraDB (criminal network)          │
│    ├── RAG Retrieval  → Catalyst QuickML RAG (narratives)        │
│    └── Forecast       → Catalyst Zia AutoML (resource hints)     │
│                                                                  │
│  STEP 3 — Synthesizer  (Qwen 2.5 14B / Gemini 2.5 Pro premium)   │
│            streams answer + viz spec · writes full audit trail   │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│  VOICE  — Language-routed                                        │
│  Kannada     → Gemini Live API (Catalyst Zia has no Kannada)     │
│  English/Hi  → Catalyst Zia STT/TTS                              │
│  Fallback    → Google Cloud STT/TTS (kn-IN-Wavenet-A)            │
└──────────────────────────────────────────────────────────────────┘

★ Catalyst (mandatory, primary)     Augmented in India 🇮🇳
```

For a full data-flow walkthrough (Kannada voice path, 0.0 s → 3.5 s), see [`../design.md`](../design.md) Section 6.2.

---

## Tech Stack Summary

| Layer | Choice | Hosted on |
|---|---|---|
| Frontend framework | Next.js 15 (App Router) | Catalyst Web Client Hosting |
| UI / styling | shadcn/ui + Tailwind 3 | — |
| Streaming chat | Vercel AI SDK (`useChat`) | — |
| Maps | Google Maps JS API | GCP (`asia-south1`) |
| Network graph | React-Flow | — |
| Backend functions | Python 3.11 on Catalyst Functions | Catalyst (India DC) |
| Orchestration | Catalyst Circuits | Catalyst |
| Auth | Catalyst Authentication (JWT + role claims) | Catalyst |
| Relational store | Catalyst Data Store | Catalyst |
| Audit + sessions | Catalyst NoSQL | Catalyst |
| Object storage | Catalyst Stratus | Catalyst |
| Cache | Catalyst Cache | Catalyst |
| Graph DB | Neo4j AuraDB Free | GCP (`asia-south1`) |
| LLM (router + synth) | Qwen 2.5 14B Instruct via Catalyst QuickML | Catalyst |
| LLM (premium Kannada) | Gemini 2.5 Pro | GCP (`asia-south1`) |
| Embeddings | `gemini-embedding-001` | GCP (`asia-south1`) |
| Forecasting | Catalyst Zia AutoML | Catalyst |
| Voice (Kannada) | Gemini Live API (multimodal STT+TTS) | GCP (`asia-south1`) |
| Voice (English/Hindi) | Catalyst Zia Services | Catalyst |
| PDF generation | Catalyst SmartBrowz | Catalyst |
| CI/CD | GitHub Actions + Catalyst Pipelines | — |

Approximate Catalyst/Google split: **90 / 10 by service count**. Every Google service is justified in [`../decisions.md`](../decisions.md) against a measured Catalyst gap.

---

## Quick Start (5 Steps to Local Dev)

You need: Python 3.11+, Node.js 20+, Catalyst CLI, a Google Cloud project with Gemini API access, and a free Neo4j AuraDB instance.

```bash
# 1. Clone and enter the app directory
git clone https://github.com/ksp-saathi/datathon-2026.git
cd datathon-2026/app

# 2. Copy and fill in the unified env template
cp .env.example .env
# Edit .env with your Catalyst, Google, and Neo4j credentials

# 3. Install backend dependencies and seed the FIR store
cd backend
pip install -r requirements.txt
python ../data-pipeline/jsonl_to_catalyst.py ../../data/firs_sample.jsonl

# 4. Install frontend dependencies
cd ../frontend
npm install

# 5. Run both layers
catalyst serve            # backend on http://localhost:3030
npm run dev               # frontend on http://localhost:3000 (separate terminal)
```

Open `http://localhost:3000`, sign in with the seeded `inspector@ksp.local` account (password printed to console on first boot), and ask in English or Kannada.

For deployment to Catalyst, see [`docs/DEPLOY.md`](docs/DEPLOY.md).

---

## Project Structure

```
app/
├── README.md                       ← you are here
├── LICENSE                         ← MIT
├── CONTRIBUTING.md                 ← how to add functions, components, commits
├── .env.example                    ← unified env template (backend + frontend)
├── .gitignore                      ← Python + Node + OS + IDE
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml                  ← Ruff + Pytest + Next.js build/typecheck
│   └── PULL_REQUEST_TEMPLATE.md
│
├── docs/
│   └── DEPLOY.md                   ← Catalyst deployment runbook
│
├── backend/                        ← Catalyst project (Functions + Circuits)
│   ├── catalyst.json
│   ├── requirements.txt
│   ├── functions/
│   │   ├── hello/                  ← health check
│   │   ├── intent-router/          ← Qwen 7B classifier
│   │   ├── sql-generator/          ← NL → Data Store SQL
│   │   ├── cypher-generator/       ← NL → Neo4j Cypher
│   │   ├── rag-retriever/          ← QuickML RAG over narratives
│   │   ├── synthesizer/            ← streams final answer
│   │   ├── audit-logger/           ← writes immutable audit row
│   │   └── pdf-exporter/           ← SmartBrowz PDF generation
│   ├── circuits/
│   │   └── main-query-flow.yaml    ← parallel-branch orchestration
│   └── shared/                     ← Gemini client, role guard, masking utils
│
├── frontend/                       ← Next.js 15
│   ├── package.json
│   ├── next.config.js
│   ├── catalyst.json
│   ├── src/
│   │   ├── app/                    ← App Router pages
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── VoiceRecorder.tsx
│   │   │   ├── MapPanel.tsx
│   │   │   ├── NetworkGraph.tsx
│   │   │   ├── AuditDrawer.tsx
│   │   │   ├── LanguageToggle.tsx
│   │   │   └── AuthGate.tsx
│   │   └── lib/                    ← API client, hooks, formatters
│   └── public/
│
├── data-pipeline/                  ← one-off ingestion scripts
│   ├── jsonl_to_catalyst.py        ← upload FIRs to Data Store
│   ├── neo4j_ingest.py             ← build the criminal network graph
│   ├── embed_narratives.py         ← Gemini embeddings batch job
│   └── h3_hotspot_index.py         ← H3 hex spatial index
│
└── validation/                     ← Week-0 unknown-resolution scripts
    ├── test_catalyst_zia_voice.py
    ├── test_gemini_live_kannada.py
    ├── test_qwen_kannada_quality.py
    ├── test_data_store_geospatial.py
    ├── test_zia_automl_forecast.py
    ├── test_circuits_parallel.py
    └── test_results.md
```

---

## Deployment to Catalyst

Full step-by-step is in [`docs/DEPLOY.md`](docs/DEPLOY.md). The short version:

```bash
# Backend: functions + orchestration
cd backend
catalyst deploy --only functions,circuits

# Frontend: static export to Catalyst Web Client Hosting
cd ../frontend
npm run build
catalyst deploy --only web-client-hosting
```

Then map your custom domain in the Catalyst console (`Settings → Domain Mappings`) and set environment variables under `Settings → Environment Variables` using the keys in [`.env.example`](.env.example).

---

## Team Credits

KSP Saathi is built by a 5-person team for **Datathon 2026 Challenge 01**.

| Owner | Role | Modules |
|---|---|---|
| **Person A** | Data Engineer | Synthetic FIR generator · Catalyst Data Store schema · NCRB ingest |
| **Person B** | AI Orchestrator | Catalyst Circuits flows · LLM router · SQL/Cypher generators · synthesizer |
| **Person C** | Graph + Predictive | Neo4j schema · Cypher prompts · Zia AutoML training |
| **Person D** | Frontend + Maps | Next.js shell · streaming chat · Maps panel · React-Flow graph · audit drawer |
| **Person E** | Voice + Demo | Gemini Live API integration · Catalyst Zia · demo video · finale rehearsal |

Project lead: Saravana Rajan (`saravanarajan.b@techjays.com`).

---

## License

[MIT](LICENSE) — Copyright (c) 2026 KSP Saathi Team. You may use, copy, modify, and distribute this code freely with attribution.

---

## Acknowledgements

- **Zoho Catalyst** — for the platform, the free credits, and the India-resident infrastructure that makes IT Act 2008 compliance effortless.
- **Google Cloud** — for Gemini Live API, Gemini 2.5 Pro, `gemini-embedding-001`, and Google Maps Platform — the bridges that fill Catalyst's documented gaps.
- **hack2skill** — for organizing Datathon 2026 and providing a serious stage for serious problems.
- **Karnataka State Police** — for fielding the problem statement and being the kind of institution that asks "how do we serve investigators better?" in 2026.
- **Neo4j AuraDB Free** — for graph infrastructure at hackathon-friendly cost.
- **NCRB, data.gov.in, Karnataka Open Data Portal** — for the public datasets that ground our synthetic FIRs in reality.

---

## Hackathon Context

KSP Saathi is the official entry of our team for:

- **Event**: Datathon 2026
- **Organizers**: hack2skill, in partnership with Zoho Catalyst, Google, and Karnataka State Police
- **Challenge**: 01 — Intelligent Conversational AI for the KSP Crime Database
- **Prototype submission**: 26 July 2026
- **Initial shortlist**: 19 August 2026
- **Final shortlist**: 9 September 2026
- **Grand Finale (in-person demo)**: 26 September 2026
- **Top prize**: ₹2.5 Lakh

Scope discipline: we build **all 9 listed features** from the official problem statement. No additions outside scope, no subtractions. The win comes from depth of execution, not redefinition. See [`../design.md`](../design.md) for the locked design doc and decision log.

> *"1,650 officer-hours saved daily across Karnataka. Deployable to all 1,100 stations day one."*
