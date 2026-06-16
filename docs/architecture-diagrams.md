# KSP Saathi — Architecture Diagrams

> Visual reference for the KSP Saathi system architecture. All diagrams render natively in GitHub, GitLab, and most Markdown viewers via Mermaid. ASCII fallback included where rendering may fail.
>
> **Source of truth:** [`design.md`](../design.md) Section 6. If anything here conflicts with `design.md`, `design.md` wins — update this file to match.

---

## 1. High-Level System Architecture (C4 Context)

External actors interact with KSP Saathi, which in turn delegates to Catalyst-native services and a small set of justified Google Cloud + Neo4j augmentations. Everything runs in India (Catalyst India DC + `asia-south1`).

```mermaid
flowchart LR
    subgraph Actors["External Actors"]
        INV["Investigator<br/>(Browser / Desktop)"]
        OFF["Officer<br/>(Mobile PWA)"]
        ADM["KSP IT Admin<br/>(Console)"]
    end

    subgraph KSPS["KSP Saathi Platform"]
        APP["Conversational AI<br/>Web + Voice<br/>9 features"]
    end

    subgraph Catalyst["Zoho Catalyst (India DC)"]
        CAT["Hosting · Auth · Functions<br/>Circuits · Data Store · NoSQL<br/>Stratus · QuickML · Zia"]
    end

    subgraph GCP["Google Cloud (asia-south1)"]
        GLIVE["Gemini Live API<br/>(Kannada STT/TTS)"]
        GPRO["Gemini 2.5 Pro<br/>(Premium synth)"]
        GMAPS["Google Maps<br/>Platform"]
        GEMB["gemini-embedding-001"]
    end

    subgraph Graph["Neo4j AuraDB Free (GCP)"]
        NEO["Criminal Network Graph"]
    end

    INV -->|HTTPS + WSS| APP
    OFF -->|HTTPS + WSS| APP
    ADM -->|Admin Console| APP

    APP --> CAT
    APP --> GLIVE
    APP --> GPRO
    APP --> GMAPS
    APP --> GEMB
    APP --> NEO

    classDef catalyst fill:#FF6B35,stroke:#333,color:#fff
    classDef gcp fill:#4285F4,stroke:#333,color:#fff
    classDef graph fill:#018BFF,stroke:#333,color:#fff
    class CAT catalyst
    class GLIVE,GPRO,GMAPS,GEMB gcp
    class NEO graph
```

**What this shows:** Three user personas (PSI/PI/DySP in browser, field officers on mobile PWA, IT admins) reach a single Next.js app. The app routes ~90% of work to Catalyst-native services and only crosses into GCP for documented gaps: Kannada voice (Gemini Live), graph DB (Neo4j), maps, and premium Kannada synthesis. All data flows stay inside Indian DCs for IT Act 2008 compliance.

### ASCII Fallback for Diagram 1

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Investigator   │     │     Officer     │     │   KSP IT Admin  │
│    (Browser)    │     │  (Mobile PWA)   │     │    (Console)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │ HTTPS / WSS
                    ┌────────────▼────────────┐
                    │     KSP SAATHI APP      │
                    │  (Next.js · 9 features) │
                    └────┬───────────┬────────┘
                         │           │
            ┌────────────┘           └─────────────┐
            │                                      │
   ┌────────▼────────┐                  ┌─────────▼─────────┐
   │   CATALYST      │                  │   GOOGLE CLOUD    │
   │   (India DC)    │                  │   (asia-south1)   │
   │ ─────────────── │                  │ ───────────────── │
   │ Hosting · Auth  │                  │  Gemini Live API  │
   │ Functions       │                  │  Gemini 2.5 Pro   │
   │ Circuits        │                  │  Maps Platform    │
   │ Data Store      │                  │  Embeddings       │
   │ NoSQL · Stratus │                  └─────────┬─────────┘
   │ QuickML · Zia   │                            │
   └─────────────────┘                  ┌─────────▼─────────┐
                                        │   Neo4j AuraDB    │
                                        │ (Criminal Graph)  │
                                        └───────────────────┘

                       ALL DATA IN INDIA
```

---

## 2. Component Architecture (C4 Container)

Each container is a deployable, ownable unit. Frontend ships to Catalyst Hosting; backend logic is split between Functions (per-task compute) and Circuits (orchestration). Stateful tier separates structured (Data Store) from semi-structured (NoSQL), graph (Neo4j), and blobs (Stratus).

```mermaid
flowchart TB
    subgraph Client["FRONTEND — Next.js 15"]
        UI["Chat UI · Map · Graph · Audit Drawer<br/>(Vercel AI SDK + shadcn/ui)"]
    end

    subgraph Edge["EDGE — Catalyst API Gateway"]
        AUTH["Catalyst Authentication<br/>JWT + role claims"]
        GW["API Gateway<br/>(Rate limit · CORS · TLS)"]
    end

    subgraph Orch["ORCHESTRATOR — Circuits + Functions"]
        IR["Intent Router (Qwen 7B)"]
        SQL["SQL Generator"]
        CYP["Cypher Generator"]
        RAG["RAG Retriever"]
        FCT["Forecast Caller"]
        SYN["Synthesizer (Qwen 14B / Gemini Pro)"]
        AUD["Audit Logger"]
        PDF["PDF Exporter"]
    end

    subgraph Data["DATA LAYER"]
        DS["Catalyst Data Store<br/>(FIRs · stations · accused)"]
        NSQL["Catalyst NoSQL<br/>(audit · sessions · embeddings)"]
        STR["Catalyst Stratus<br/>(PDFs · uploads)"]
        NEO["Neo4j AuraDB<br/>(criminal network)"]
    end

    subgraph AI["AI LAYER"]
        QML["Catalyst QuickML<br/>(Qwen 2.5 LLM + RAG)"]
        GP["Gemini 2.5 Pro<br/>(premium Kannada)"]
        ZAI["Catalyst Zia AutoML<br/>(forecasting)"]
    end

    subgraph Voice["VOICE LAYER"]
        ZIA["Catalyst Zia<br/>(English/Hindi STT+TTS)"]
        GL["Gemini Live API<br/>(Kannada STT+TTS)"]
    end

    UI -->|WSS + REST| GW
    GW --> AUTH
    AUTH --> IR
    IR --> SQL & CYP & RAG & FCT
    SQL --> DS
    CYP --> NEO
    RAG --> NSQL
    RAG --> QML
    FCT --> ZAI
    SQL & CYP & RAG & FCT --> SYN
    SYN --> QML
    SYN --> GP
    SYN --> AUD
    AUD --> NSQL
    PDF --> STR
    UI <-->|audio stream| GL
    UI <-->|audio stream| ZIA
```

**What this shows:** The orchestrator is the brain — eight specialized Functions wired together by Circuits. The Intent Router classifies; specialists run in parallel; the Synthesizer merges results and streams the answer. The Audit Logger writes on every turn so explainability is non-optional.

---

## 3. Single Voice Query Sequence (Kannada Path)

This is the **happy path** for a Kannada voice query. Latency annotations match the budget in [`design.md`](../design.md) Section 9.1. Anything past 3.5s breaks the demo promise.

```mermaid
sequenceDiagram
    autonumber
    participant U as User (Kannada voice)
    participant B as Browser (VAD)
    participant GL as Gemini Live STT
    participant GW as Catalyst API Gateway
    participant IR as Intent Router (Qwen 7B)
    participant SQL as SQL Gen + Data Store
    participant CYP as Cypher Gen + Neo4j
    participant RAG as RAG + Embeddings
    participant SYN as Synthesizer (Qwen / Gemini Pro)
    participant TTS as Gemini Live TTS
    participant AL as Audit Logger + NoSQL

    Note over U,B: 0.0s — user speaks
    U->>B: Kannada audio stream
    Note over B,GL: 0.2s — VAD silence detected
    B->>GL: Stream audio chunks
    GL-->>B: Transcript (streaming)
    B->>GW: POST /query {transcript, role, lang=kn}
    Note over GW: 0.3s — auth + initial audit row
    GW->>AL: Open audit record
    GW->>IR: Route intent
    Note over IR: 0.5s — intent = "tabular_geo + graph"
    par Parallel specialist execution
        IR->>SQL: Generate + execute SQL
        and
        IR->>CYP: Generate + execute Cypher
        and
        IR->>RAG: Embed + retrieve narratives
    end
    Note over SQL,RAG: 1.0s — specialists return
    SQL-->>SYN: Tabular results
    CYP-->>SYN: Graph subgraph
    RAG-->>SYN: Top-K narratives
    Note over SYN: 1.5s — first token streaming
    SYN-->>B: Streamed answer chunks
    SYN->>TTS: Sentence chunks
    TTS-->>B: First audio chunk
    Note over B,U: 1.7s — first audio plays
    B->>U: Kannada audio out
    SYN->>AL: Write tool calls + sources
    AL->>AL: Write final audit row
    Note over U,AL: 3.0s — full answer delivered + audit complete
```

**What this shows:** Parallelism is the trick. Once intent is classified at 0.5s, three specialists fan out simultaneously; the Synthesizer joins them at 1.5s and starts streaming audio at 1.7s — that's the metric the judges hear. Audit logging happens on the critical path so no answer ever ships without traceability.

---

## 4. Data Flow Diagram (Ingestion Pipeline)

Cold-load pipeline that takes 50K synthetic FIRs from local JSONL into all three storage backends. Each script is independently runnable; they fan out from the same source file.

```mermaid
flowchart LR
    SRC["data/firs.jsonl<br/>(50K synthetic FIRs · 91 MB)"]

    subgraph Pipelines["app/data-pipeline/"]
        P1["jsonl_to_catalyst.py"]
        P2["neo4j_ingest.py"]
        P3["embed_narratives.py"]
        P4["h3_hotspot_index.py"]
    end

    subgraph Stores["Storage Targets"]
        DS["Catalyst Data Store<br/>firs table + stations + accused"]
        NEO["Neo4j AuraDB<br/>Person · FIR · KNOWS · CO_ACCUSED_IN"]
        EMB["Catalyst NoSQL<br/>narrative_embeddings collection"]
        H3["Catalyst Data Store<br/>h3_index column (resolution 8)"]
    end

    SRC --> P1 --> DS
    SRC --> P2 --> NEO
    SRC --> P3
    P3 -->|"gemini-embedding-001<br/>(or QuickML RAG)"| EMB
    SRC --> P4 --> H3

    classDef store fill:#E8F4F8,stroke:#0066CC
    class DS,NEO,EMB,H3 store
```

**What this shows:** One canonical source, four parallel ingestion paths. The embedder is the only step that calls out to GCP (multilingual Kannada quality), and only if Catalyst's built-in QuickML RAG embedder fails the A/B eval. H3 indexing happens in app code because Catalyst Data Store has no spatial type.

---

## 5. Catalyst Deployment Topology

Where every artifact physically lives in the Catalyst project. This is the answer to "what gets deployed where" — useful for `catalyst deploy` debugging.

```mermaid
flowchart TB
    subgraph Project["Catalyst Project: ksp-saathi"]
        direction TB

        subgraph Hosting["Web Client Hosting"]
            FE["frontend/out/<br/>(Next.js static export)"]
        end

        subgraph Functions["Functions (8)"]
            F1["intent-router/"]
            F2["sql-generator/"]
            F3["cypher-generator/"]
            F4["rag-retriever/"]
            F5["synthesizer/"]
            F6["audit-logger/"]
            F7["pdf-exporter/"]
            F8["hello/"]
        end

        subgraph Circuits["Circuits (3)"]
            C1["main-query-flow.yaml"]
            C2["embedding-batch-flow.yaml"]
            C3["audit-export-flow.yaml"]
        end

        subgraph DataStore["Data Store"]
            T1["firs (main table)"]
            T2["stations"]
            T3["accused_persons"]
            T4["ipc_section_lookup"]
        end

        subgraph NoSQL["NoSQL"]
            N1["audit_logs"]
            N2["narrative_embeddings"]
            N3["sessions"]
        end

        subgraph Stratus["Stratus (object storage)"]
            S1["exports/*.pdf"]
            S2["uploads/*"]
        end

        subgraph External["External (justified)"]
            X1["Neo4j AuraDB Free"]
            X2["Gemini Live + Pro + Embeddings"]
            X3["Google Maps JS API"]
        end
    end

    FE --> C1
    C1 --> F1 --> F2 & F3 & F4
    F2 --> F5
    F3 --> F5
    F4 --> F5
    F5 --> F6
    F5 --> X2
    F7 --> S1
    F2 --> T1
    F3 --> X1
    F4 --> N2
    F6 --> N1
```

**What this shows:** The whole system fits in one Catalyst project. Eight Functions, three Circuits, four Data Store tables, three NoSQL collections, two Stratus buckets — plus three external services with documented justification. Nothing is hand-rolled outside Catalyst's deploy pipeline.

---

## 6. Frontend Component Tree

React component hierarchy for the Next.js 15 app. Lazy-loaded panels are mounted on tab activation to keep initial JS payload under 200KB gzipped.

```mermaid
flowchart TB
    App["App<br/>(layout.tsx)"]
    App --> AG["AuthGate<br/>(Catalyst Auth check)"]
    AG --> DL["DashboardLayout"]
    DL --> CP["ChatPanel"]
    DL --> SP["SidePanel (Tabs)"]
    DL --> AD["AuditDrawer<br/>(slide-over)"]

    CP --> CM["ChatMessage[]<br/>(streaming)"]
    CP --> MI["MessageInput"]
    MI --> VR["VoiceRecorder<br/>(VAD + Web Audio)"]
    MI --> LT["LanguageToggle<br/>(EN / KN / HI)"]

    SP --> MP["MapPanel"]
    SP --> NG["NetworkGraph"]

    MP --> HL["HotspotLayer<br/>(H3 hexes)"]
    MP --> HM["HeatmapLayer<br/>(DBSCAN clusters)"]

    NG --> PN["PersonNode<br/>(React-Flow)"]
    NG --> FN["FIRNode<br/>(React-Flow)"]
    NG --> EE["EdgeRenderer<br/>(KNOWS / CO_ACCUSED_IN)"]

    AD --> AT["AuditTimeline"]
    AD --> SC["SourceCitations"]
    AD --> FL["FlagWrongAnswer"]
```

**What this shows:** The chat is always-on (top of the page); map and graph share a tabbed side panel; the audit drawer slides over from the right when "Why?" is clicked. Voice and language controls live inside the input bar so they feel like part of typing, not a separate mode.

---

## 7. RBAC Matrix Visualization

The Catalyst Authentication JWT carries a `role` custom claim; every Function reads it and applies row-level filters before any data leaves the boundary. The matrix below is enforced both in SQL (Data Store row policies) and in app code (defense in depth).

```
┌──────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Role             │ Read Scope   │ Write Scope  │ PII Access   │ Special      │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ constable        │ Own station, │      —       │ Masked       │      —       │
│                  │ last 30d     │              │              │              │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ sub_inspector    │ Own station, │ Witness      │ Partial      │ Mobile-only  │
│                  │ all time     │ statements   │              │              │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ inspector        │ Sub-division │ Case notes   │ Full (own)   │      —       │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ sho              │ Full station │ All          │ Full         │ Briefings    │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ dcp              │ District     │ Read-only    │ Full         │ Cross-stn    │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ scrb_analyst     │ State-wide   │ Reports      │ Aggregates   │ No case PII  │
│                  │ aggregates   │              │ only         │              │
├──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ admin            │ All          │ All          │ Full         │ Audit access │
└──────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**What this shows:** Seven roles, four enforcement dimensions. A constable querying for an out-of-station case will get a polite "not authorized" — and the attempt is logged. SCRB analysts see aggregates without ever touching case-level PII, satisfying DPDP Act 2023 minimization.

---

## 8. Audit Chain Visualization

Every query becomes an immutable audit record. The chain below is what the "Why?" drawer renders visually and what the IT Act 2008 export job ships to KSP's compliance team.

```mermaid
flowchart LR
    Q["User Query<br/>(text or voice)"] --> R1["Audit Row Opened<br/>{request_id, user, role, raw_query, lang, ts}"]
    R1 --> IR["Intent Router Decision<br/>+ model_version + confidence"]
    IR --> R2["Append: route_decision"]
    R2 --> TC["Tool Calls<br/>SQL · Cypher · RAG · Forecast"]
    TC --> R3["Append: tool_calls[] + data_accessed[]"]
    R3 --> SY["Synthesizer Output<br/>(answer + sources)"]
    SY --> R4["Append: final_answer + sources + latency"]
    R4 --> SEAL["Seal Record<br/>(write-once to NoSQL)"]
    SEAL --> UI["UI: Audit Drawer<br/>(shows full chain)"]
    SEAL --> EXP["Compliance Export<br/>(monthly PDF + JSONL)"]

    classDef sealed fill:#1F8B4C,stroke:#333,color:#fff
    class SEAL,EXP sealed
```

**What this shows:** The audit record grows incrementally as the query moves through the pipeline, then gets sealed on completion. Nothing can be amended after seal — corrections create a new linked record. This is the spine of Feature 8 (Explainable AI) and the legal evidence for Feature 9 (RBAC enforcement).

---

## Maintenance Notes

- **When to update this file:** any change to the locked architecture in `design.md` Section 6, any new Function, any new external service.
- **How to verify Mermaid renders:** push to GitHub and open the file — GitHub renders Mermaid natively. For local preview use VS Code's "Markdown Preview Mermaid Support" extension.
- **ASCII fallback policy:** required for Diagram 1 (the one most likely to be screenshotted into the pitch deck). Optional for the rest.

*Last updated: 2026-06-16 · Owner: Person B (Orchestrator) · Cross-ref: `design.md` Section 6, `decisions.md`*
