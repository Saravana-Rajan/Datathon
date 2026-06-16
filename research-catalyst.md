# Zoho Catalyst Services — Capability & Limits Brief

**Scope:** Factual reference for Datathon 2026 team committed to Catalyst as primary platform. Items marked [UNCERTAIN] could not be confirmed from official docs in the research budget.

---

## 1. Catalyst Functions (serverless)
- **What it does:** Event-driven serverless code execution. Supported runtimes include Node.js, Java, Python. Function types: Basic I/O, Advanced I/O, Cron, Event, Integration.
- **Free tier:** 25,000 GB-seconds/month across the whole account (split across all memory sizes).
- **Indian language support:** N/A — language-agnostic execution.
- **Limitations for conversational AI:** Function execution timeouts (Basic I/O ~10s, Advanced I/O longer [UNCERTAIN exact ceiling]) — long-running LLM streaming responses must use AppSail or chunked streaming. Cold-starts apply.
- **Docs:** https://docs.catalyst.zoho.com/en/serverless/help/functions/introduction/

## 2. Catalyst AppSail (managed runtime)
- **What it does:** Managed container/runtime for long-running stacks (Node.js, Java, Python, Go, PHP, .NET, Ruby) — like a PaaS for full apps without rewriting to functions.
- **Free tier:** 15 GB-hours/month.
- **Indian language:** N/A.
- **Limitations for conversational AI:** Good fit for WebSocket / SSE streaming chat backends. Resource ceiling tied to GB-hour budget — sustained workloads exceed free tier quickly.
- **Docs:** https://docs.catalyst.zoho.com/en/

## 3. Catalyst Web Client Hosting & Slate (frontend)
- **What it does:** Web Client Hosting serves static SPAs/PWAs over Catalyst CDN. **Slate** is a newer hosting service for web apps (Early Access at time of writing).
- **Free tier:** Web Client Hosting — 300,000 requests/month.
- **Indian language:** N/A (content-driven).
- **Limitations for conversational AI:** Static hosting only — dynamic SSR needs AppSail. Slate's Early Access status means feature surface may shift mid-hackathon.
- **Docs:** https://catalyst.zoho.com/features.html

## 4. Catalyst Data Store (relational)
- **What it does:** Cloud-managed relational DB with ZCQL (Zoho Catalyst Query Language — SQL dialect), bulk operations, OLAP analytics, indexed search.
- **Free tier:** 2 GB storage + 5,000 insertions/month.
- **Indian language:** Stores Unicode text; no language-specific features.
- **GEOSPATIAL / PostGIS support:** **NO** — Catalyst Data Store does **not** advertise PostGIS, geometry/geography types, or spatial indexing. The underlying engine is not disclosed as PostgreSQL. [UNCERTAIN — official docs do not state engine; for spatial queries plan to supplement with Google Maps / Places APIs or maintain lat/lng as numeric columns with bounding-box filters in ZCQL.]
- **Limitations for conversational AI:** No native vector type [UNCERTAIN]. No spatial joins. Suitable for transactional/structured chat history; not for embeddings.
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/data-store/introduction/

## 5. Catalyst NoSQL
- **What it does:** Schema-less document/key-value store. Composite primary keys (partition + sort key — DynamoDB-style). Custom JSON, nested fields, indexes, TTL for short-lived data, auto-scaling.
- **Free tier:** [UNCERTAIN — not published on free-tier landing page].
- **Indian language:** Stores Unicode JSON natively.
- **Limitations for conversational AI:** Good for chat session state, transient context, user-pref blobs. No full-text or vector search. Query model is partition+sort-key driven (not arbitrary attribute filters at scale).
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/nosql/introduction

## 6. Catalyst Stratus (object storage)
- **What it does:** S3-compatible object storage. Buckets, objects, pre-signed URLs, ACLs, metadata, REST API + SDKs. For media, audio uploads, RAG source PDFs, logs.
- **Free tier:** [UNCERTAIN — not on the public free-tier list].
- **Indian language:** N/A.
- **Limitations for conversational AI:** Suitable for storing raw audio (STT input), TTS output, document corpus. Pre-signed URLs handle direct browser upload.
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/stratus/introduction/

## 7. Catalyst Cache
- **What it does:** Key-value cache for session data, rate-limit counters, hot reads.
- **Free tier:** 1,000 GET + 5,000 PUT + 5,000 UPDATE / month.
- **Limitations:** Very low free-tier read budget — cannot back a high-traffic chat without exceeding free quota fast. Plan to use sparingly (only for hot config / auth tokens).
- **Docs:** https://catalyst.zoho.com/free-tier.html

## 8. Catalyst QuickML — LLM Serving + RAG
- **What it does:** No-code ML pipeline builder + hosted LLM serving + RAG knowledge base.
- **LLMs available:** **Qwen 2.5 14B Instruct**, **Qwen 2.5 7B Coder**, **Qwen 2.5 7B Vision Language**. Context: 128K tokens (Qwen 14B & Coder); ~9K for Vision model.
- **RAG:** Powered by Qwen 2.5-14B-Instruct. Embedding model used for semantic search is **not specified** in public docs [UNCERTAIN — likely Zoho-managed; cannot swap].
- **Custom model deployment (Llama, Sarvam-1):** **Not supported** in public surface — only the three Qwen models are exposed. Confirm via support@zohocatalyst.com for any custom serving option.
- **Kannada quality:** [UNCERTAIN] — Qwen 2.5 is multilingual and Kannada-capable in principle, but Catalyst docs do not benchmark or claim Indian-language quality. Expect inferior fluency vs. Sarvam-1 or Gemini for Kannada.
- **Free tier:** 500 prediction calls + 1 GB storage + 1,800 vCPU-seconds training/month (QuickML overall). LLM Serving-specific quotas [UNCERTAIN].
- **Availability:** US, IN, EU data centers.
- **Docs:** https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/llm-serving/ • https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/rag/

## 9. Catalyst Zia AutoML
- **What it does:** No-code training — provide dataset + target column; Zia auto-selects algorithm. Tasks: classification, regression. **Time series forecasting** is supported via QuickML's time-series algorithms (separate path from AutoML proper).
- **Free tier:** Bundled under Zia Services — 100 API calls/month free across Zia.
- **Limitations for conversational AI:** Useful for intent classification, escalation scoring, churn prediction; not a generative tool. Forecasting via QuickML time-series module.
- **Docs:** https://docs.catalyst.zoho.com/en/zia-services/help/automl/introduction • https://docs.catalyst.zoho.com/en/quickml/help/ml-algorithms/time-series/

## 10. Catalyst Zia Services
- **What it offers:** OCR, NER, object/keyword detection, sentiment, barcode, face analysis, ID extraction, Zia LLM (Zoho's own model, recently launched), ASR (speech-to-text).
- **STT/TTS for Kannada (kn-IN):** **NOT YET SUPPORTED.** Zoho's proprietary ASR launched with **English + Hindi only** (announced 2025). Zoho stated "We will support other Indian languages over time" — Kannada is on the roadmap but not live. **For Datathon 2026, supplement with Sarvam.ai or Google Cloud STT/TTS for Kannada.**
- **Streaming:** [UNCERTAIN — Catalyst Zia ASR streaming endpoint not documented publicly; Zoho's recent ASR is batch-oriented in published material.]
- **Quality vs Sarvam.ai / Google:** Zoho claims ASR benchmarks "up to 75% better than comparable models" on internal eval — unverified externally. For Kannada specifically, Sarvam.ai is the leader; Google Cloud STT has solid kn-IN support. **Recommend Sarvam.ai or Google for any Kannada voice flow.**
- **Free tier:** 100 API calls/month across Zia Services.
- **Docs:** https://docs.catalyst.zoho.com/en/zia-services/

## 11. Catalyst SmartBrowz
- **What it does:** Headless browser service (cloud Chrome). Components: Headless automation, Browser Logic, PDF & Screenshot generation, Templates.
- **Free tier:** 5 headless-hours + 50 PDF conversions/month.
- **Use cases:** Web scraping for RAG corpus, on-the-fly PDF reports, screenshot capture.
- **Docs:** https://docs.catalyst.zoho.com/en/smartbrowz/

## 12. Catalyst Authentication
- **What it does:** Hosted + embedded auth. Supports Catalyst-native credentials, Zoho accounts, Google, Facebook, LinkedIn, Microsoft, Apple, GitHub social logins [list per docs].
- **RBAC:** Yes — user roles assignable per project; custom roles supported.
- **Custom claims:** Custom User Validation hook lets you run a Basic I/O function during login to inject/validate custom logic. Native "custom JWT claims" surface [UNCERTAIN — handled via the validation function rather than a JWT-claim editor].
- **Free tier:** Free tier specifics not on landing page [UNCERTAIN — but auth itself is widely available without explicit per-call billing in normal use].
- **Limitations:** No SAML SSO mentioned for end-user auth [UNCERTAIN]; primarily OAuth-based.
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/authentication/

## 13. Catalyst API Gateway
- **What it does:** Custom endpoints over Functions/AppSail with auth, throttling, rate limits. Three auth methods configurable.
- **Free tier:** 100,000 API calls/month.
- **Use:** Front-door for conversational backend; built-in throttling protects LLM quota.
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/api-gateway/key-concepts/

## 14. Catalyst Circuits (workflow)
- **What it does:** Serverless step-function-style orchestration. Define JSON schema, chain Functions/Webhooks/AppSail, trigger via cron or events.
- **Free tier:** 2,000 state transitions/month.
- **Use:** Multi-step agent workflows, ingestion pipelines, RAG indexing.
- **Docs:** https://docs.catalyst.zoho.com/en/serverless/help/circuits/

## 15. Catalyst Cron / Job Scheduling
- **What it does:** Scheduled job triggers — Functions, Circuits, Webhooks, AppSail services. New **Job Scheduling** service is enhanced replacement for legacy Cron.
- **Free tier:** [UNCERTAIN — bundled with Functions GB-seconds].
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/cron/introduction/

## 16. Catalyst Mail / Push Notifications
- **Mail free tier:** 100 emails/month — **insufficient for production**, fine for hackathon demo.
- **Push Notifications free tier:** 500 notifications/month. SDKs for iOS, Android, Flutter, Web.
- **Limitations:** Mail quota is very low; supplement with SendGrid/SES for any real volume.
- **Docs:** https://docs.catalyst.zoho.com/en/cloud-scale/help/push-notifications/introduction/

## 17. Catalyst Signals + Event Functions
- **What it does:** Event Bus — publishers emit events, targets (Functions, Circuits, Webhooks) consume them. Custom publishers/events configurable no-code; ETL on event payload supported.
- **Free tier:** [UNCERTAIN].
- **Use:** Decouple chat ingestion from downstream LLM/RAG/analytics jobs.
- **Docs:** https://docs.catalyst.zoho.com/en/signals/

## 18. Catalyst Pipelines (CI/CD)
- **What it does:** Native CI/CD for Catalyst projects — build, test, deploy Functions/AppSail/Web Hosting.
- **Free tier:** [UNCERTAIN].
- **Limitations:** Catalyst-centric; existing GitHub Actions workflows would need porting.
- **Docs:** https://docs.catalyst.zoho.com/en/

---

## CRITICAL GAPS — what Catalyst CANNOT do
1. **Geospatial / PostGIS queries** — no spatial types, no `ST_*` functions, no geo-indexing. Use Google Maps Platform or store lat/lng + bounding-box filter manually.
2. **Graph database** — no Neo4j/Cypher equivalent. For knowledge-graph features, use Neo4j Aura or build adjacency tables in Data Store.
3. **Native vector database / pgvector** — RAG is encapsulated inside QuickML's managed offering; no raw vector index you control. For custom embeddings (e.g. Sarvam, Cohere), use Pinecone / Qdrant / Weaviate externally.
4. **Kannada STT / TTS** — Zia ASR is English+Hindi only as of 2025-2026. Use **Sarvam.ai** (best Kannada quality) or **Google Cloud Speech** for any Kannada voice features.
5. **Custom LLM deployment (Llama, Sarvam-1, Mistral)** — QuickML LLM Serving only exposes Qwen 2.5 variants. Self-hosted LLMs require AppSail container with your own inference runtime (and GB-hour budget will be tight).
6. **Maps / routing / geocoding** — no native maps service. Use Google Maps / Mapbox.
7. **Real-time WebSocket Pub/Sub** at app level — Signals handles async events, not interactive realtime sockets; build over AppSail.
8. **Streaming STT** [UNCERTAIN] — not documented; assume batch-only for now.

---

## RECOMMENDATIONS — Catalyst vs. Supplement

| Service | Use Catalyst? | Reason |
|---|---|---|
| Functions | **Yes** | Generous 25K GB-s free tier; fits webhook/handlers |
| AppSail | **Yes** | Required for long-running chat/LLM streaming backend |
| Web Hosting / Slate | **Yes** | 300K req/mo covers any demo |
| Data Store | **Yes for transactional**, **supplement Google** for geospatial | No PostGIS — pair with Google Maps for geo |
| NoSQL | **Yes** | Best fit for chat session + context blobs |
| Stratus | **Yes** | S3-class storage for audio/PDF corpus |
| Cache | **Use sparingly** | 1K GET/mo free tier is tight; supplement with in-process LRU |
| QuickML LLM | **Use for English/coding**, **supplement** for Kannada | Qwen has weaker Kannada vs Sarvam; no custom-model upload |
| QuickML RAG | **Use for MVP**, evaluate **external vector DB** if quality lags | Opaque embedding model; can't tune |
| Zia AutoML | **Yes** | No-code classification/regression for intent + scoring |
| Zia STT/TTS | **NO for Kannada — supplement with Sarvam.ai or Google** | Kannada not yet supported in Zia ASR |
| SmartBrowz | **Yes** | Scrape + PDF gen in 5 hrs/mo free |
| Authentication | **Yes** | Social login + RBAC built-in; custom validation hook |
| API Gateway | **Yes** | 100K calls/mo free, native throttling |
| Circuits | **Yes** | Orchestration for ingestion/RAG indexing pipelines |
| Cron / Jobs | **Yes** | Native scheduled triggers |
| Mail | **Supplement with SendGrid** | 100/mo too low for anything beyond demo |
| Push | **Yes for demo** | 500/mo workable for hackathon |
| Signals | **Yes** | Event decoupling between agent stages |
| Pipelines | **Yes** | Native CI/CD; less friction than wiring GH Actions |

**Headline rule for Datathon 2026 Kannada conversational AI:** Catalyst for compute, storage, auth, orchestration. **Sarvam.ai or Google Cloud for Kannada STT/TTS.** Google Maps for any geospatial. Optional external vector DB if QuickML RAG quality lags on Kannada.

---

## Sources
- https://docs.catalyst.zoho.com/en/deployment-and-billing/billing/free-tier/
- https://catalyst.zoho.com/free-tier.html
- https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/llm-serving/
- https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/rag/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/data-store/introduction/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/nosql/introduction
- https://docs.catalyst.zoho.com/en/cloud-scale/help/stratus/introduction/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/authentication/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/api-gateway/key-concepts/
- https://docs.catalyst.zoho.com/en/serverless/help/functions/introduction/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/cron/introduction/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/push-notifications/introduction/
- https://docs.catalyst.zoho.com/en/signals/
- https://docs.catalyst.zoho.com/en/smartbrowz/
- https://docs.catalyst.zoho.com/en/zia-services/help/automl/introduction
- https://docs.catalyst.zoho.com/en/quickml/help/ml-algorithms/time-series/
- https://catalyst.zoho.com/features.html
- https://www.deccanherald.com/technology/ai-race-zoho-launches-its-own-llm-proprietary-models-for-speech-to-text-conversion-3634773
