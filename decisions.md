# Third-Party Service Decisions Log — Datathon 2026

**Project**: Karnataka State Police Intelligence Platform
**Submission Track**: Datathon 2026
**Last Updated**: 2026-06-13
**Status**: Audit-ready evidence file

> This document formally justifies every third-party (non-Catalyst) service used in our Datathon 2026 submission. It exists to demonstrate good-faith compliance with the Catalyst-first rule:
>
> > *"Using a third-party alternative when a Catalyst service is available may affect the validity of your submission."*
>
> Every third-party dependency listed below has been evaluated against an equivalent Catalyst service. Where Catalyst offers an equivalent, we use Catalyst. Where Catalyst has a documented gap, we record the gap, the source of confirmation, and the mitigation.

---

## Design Principles for Third-Party Use

1. **Catalyst is the default.** We do NOT use a third-party service when Catalyst has equivalent capability. Catalyst Data Store, Catalyst Functions, Catalyst Web Client Hosting, Catalyst Zia Services, and Catalyst QuickML form the core of our stack.
2. **Third-party use requires three things**: (a) a documented Catalyst gap referenced against Catalyst's public capability documentation, (b) an A/B test recorded in our evaluation log if the gap is quality-based rather than absolute, and (c) India region hosting (asia-south1 / Mumbai) to preserve IT Act 2008 data residency posture.
3. **Every third-party service is auditable, swappable, and documented in this file.** If Catalyst ships a missing capability before submission day, we will swap to Catalyst and update this document accordingly.
4. **Three categories of third-party use:**
   - **Hard gap** — Catalyst has no equivalent service at all. Justification is structural.
   - **Documented gap** — Catalyst offers the service category, but a specific feature we need is confirmed missing or unsupported.
   - **Conditional** — Used only when measured A/B testing shows the Catalyst equivalent is materially weaker for our use case. Default remains Catalyst until evidence dictates otherwise.

---

## Justifications

### Neo4j AuraDB Free — Criminal Network Graph Database
- **Catalyst alternative considered:** Catalyst Data Store (NoSQL document tables), Catalyst Cache, Catalyst File Store.
- **Catalyst gap found:** Catalyst exposes no native graph database primitive. Graph traversal queries (multi-hop relationship walks, shortest-path between suspects, centrality scoring) cannot be expressed efficiently against Catalyst Data Store's document/table model. Simulating graph traversal in application code over Data Store would require N+1 round trips per hop and would not scale to the relationship depths required by Feature 5.
- **Source of confirmation:** Catalyst capability matrix lists only Data Store (NoSQL), Cache, File Store, and Object Store under the data persistence category. No graph database service is published. Verified against the Catalyst service catalogue on 2026-06-10.
- **Why we chose this third-party:** Neo4j is the industry-standard property graph database; Cypher query language directly maps to the criminal-network use case (suspect-to-suspect, suspect-to-incident, suspect-to-location traversals). AuraDB Free tier provides a managed, zero-ops deployment suitable for hackathon scale.
- **Risk if rejected:** Loss of Feature 5 (Criminal network visualization) from the problem statement. The feature is non-substitutable without a graph engine.
- **Mitigation:** AuraDB instance is hosted on Google Cloud Platform in the asia-south1 (Mumbai) region. Connection strings, queries, and responses are logged via a Catalyst Function proxy so every graph access is auditable from inside the Catalyst environment.

### Google Maps Platform — Map UI and Geocoding
- **Catalyst alternative considered:** Catalyst Web Client Hosting (for tile serving), Catalyst Data Store (for geospatial queries), Catalyst Search.
- **Catalyst gap found:** Catalyst publishes no Maps, geocoding, reverse-geocoding, or geospatial visualization service. Catalyst Data Store does not support PostGIS or any spatial index type; range queries on lat/lng pairs cannot be performed efficiently and bounding-box / radius queries are not supported.
- **Source of confirmation:** Catalyst Data Store documentation lists supported column types (string, number, boolean, datetime, JSON) with no `geography`, `geometry`, or `point` type. No Maps service appears in the Catalyst service catalogue.
- **Why we chose this third-party:** Google Maps Platform is the de-facto standard for Indian map data, includes high-quality Karnataka-level granularity, supports clustering and heat-map overlays required by Feature 6 (Crime trend & hotspot detection), and offers a free monthly credit sufficient for hackathon evaluation.
- **Risk if rejected:** Loss of Feature 6 (Crime trend & hotspot detection). Hotspot detection without a map renderer would degrade to tabular output, which fails the user-experience bar for a police-facing tool.
- **Mitigation:** All Google Maps API calls are issued from the Catalyst-hosted frontend with the API key restricted by HTTP referrer to our Catalyst Web Client domain and by IP allowlist to Indian region egress. Tile and geocoding requests are logged for audit.

### Google Cloud Gemini Live API — Kannada Voice STT/TTS (Primary for Kannada)
- **Catalyst alternative considered:** Catalyst Zia Services Automatic Speech Recognition (ASR) and Text-to-Speech (TTS).
- **Catalyst gap found:** As of June 2026, Catalyst Zia ASR supports English and Hindi only. Catalyst Zia TTS does not ship a Kannada voice. Karnataka State Police is the project sponsor and Kannada is the operational language of field officers; the absence of Kannada coverage is a blocking gap for the voice-first interface.
- **Source of confirmation:** Catalyst Zia Services documentation under Speech Recognition lists supported languages as English (en-IN, en-US) and Hindi (hi-IN). Catalyst Zia TTS voice catalogue lists no kn-IN voice as of the 2026-06 documentation snapshot.
- **Why we chose this third-party:** Gemini Live API provides real-time bidirectional Kannada speech-to-speech with low latency, native kn-IN support, and adequate accent coverage for Karnataka regional dialects.
- **Risk if rejected:** Loss of the Kannada voice interface, which removes accessibility for the primary user persona (Karnataka police field officers). The product loses its sponsor-language alignment.
- **Mitigation:** Gemini Live API is invoked from the asia-south1 (Mumbai) endpoint, preserving IT Act 2008 data residency. Catalyst Zia ASR/TTS is still used for English and Hindi voice paths — we do not replace Catalyst where Catalyst is sufficient. All Gemini Live API calls are proxied through a Catalyst Function for centralized logging.

### Gemini 2.5 Pro — Premium LLM Augmentation for Complex Kannada Queries
- **Catalyst alternative considered:** Catalyst QuickML LLM Serving (Qwen 2.5 14B Instruct, Qwen 2.5 7B Coder, Qwen 2.5 7B Vision).
- **Catalyst gap found:** Catalyst QuickML LLM Serving is restricted to the Qwen 2.5 model family. Custom model deployment is not supported. Qwen 2.5 Kannada generation quality on nuanced synthesis tasks (multi-document reasoning over Kannada FIRs) is uncertain and may be insufficient for the analyst-facing summarization workload.
- **Source of confirmation:** Catalyst QuickML documentation lists the served model catalogue and explicitly excludes user-uploaded LLM weights. Custom model upload is restricted to traditional ML artifacts.
- **Why we chose this third-party:** Gemini 2.5 Pro is a top-tier multilingual frontier model with strong Kannada coverage. We will only route to Gemini 2.5 Pro on queries where the Qwen 2.5 14B Instruct response is measurably weaker, as scored by our offline Kannada evaluation harness.
- **Risk if rejected:** Degraded synthesis quality on the most demanding analyst queries. Core features continue to function on Qwen 2.5.
- **Mitigation:** Qwen 2.5 on Catalyst QuickML remains the default. Gemini 2.5 Pro is invoked only on the conditional branch with A/B evidence recorded. All Gemini API calls originate from the asia-south1 region.

### gemini-embedding-001 — Multilingual Embeddings (Conditional Fallback)
- **Catalyst alternative considered:** Catalyst QuickML RAG embedder (model identity not publicly documented).
- **Catalyst gap found:** Catalyst QuickML RAG uses an opaque embedder whose multilingual retrieval quality on Kannada is not published. Until our retrieval evaluation completes, we cannot certify Kannada recall@k quality.
- **Source of confirmation:** Catalyst QuickML RAG documentation does not name the embedding model or publish multilingual benchmark results.
- **Why we chose this third-party:** gemini-embedding-001 has published multilingual MTEB results including strong Indic-language performance. We will swap to it only if Catalyst QuickML RAG underperforms on our Kannada retrieval evaluation set.
- **Risk if rejected:** Degraded retrieval recall on Kannada documents. English and Hindi paths are unaffected.
- **Mitigation:** Catalyst QuickML RAG is the default embedder. Swap is gated on a recorded A/B test using a held-out Kannada query set with measured recall@10. The A/B record is committed to the evaluation log.

### Google Cloud STT/TTS (kn-IN) — Universal Voice Fallback
- **Catalyst alternative considered:** Catalyst Zia ASR/TTS (English/Hindi) and Gemini Live API (Kannada).
- **Catalyst gap found:** No gap against Catalyst; this is a reliability fallback against Gemini Live API runtime issues during the hackathon demo window.
- **Source of confirmation:** Operational risk decision, not a Catalyst capability gap.
- **Why we chose this third-party:** Google Cloud STT/TTS provides kn-IN coverage independent of the Gemini Live API endpoint, isolating the demo from a single-provider outage.
- **Risk if rejected:** No primary functionality lost; only the redundancy layer is removed.
- **Mitigation:** Hosted in asia-south1. Invoked only when Gemini Live API health checks fail. Disabled by default; enabled by feature flag.

### Vertex AI Forecasting — Backup Forecasting (Conditional)
- **Catalyst alternative considered:** Catalyst Zia AutoML (forecasting models).
- **Catalyst gap found:** No structural gap. Catalyst Zia AutoML is the primary forecasting engine. Vertex AI Forecasting is a contingency in case Zia AutoML accuracy is insufficient on our crime-trend dataset.
- **Source of confirmation:** Catalyst Zia AutoML documents forecasting as a supported task. We have not yet measured accuracy on our specific dataset.
- **Why we chose this third-party:** Vertex AI Forecasting is a managed alternative we can swap in with minimal integration effort if Zia AutoML underperforms.
- **Risk if rejected:** None to the primary path. Forecasting continues on Catalyst Zia AutoML.
- **Mitigation:** Catalyst Zia AutoML remains the default and ships in our submission unless an A/B test recorded in the evaluation log demonstrates a material accuracy gap.

### Open-Source Frontend Libraries — Next.js, shadcn/ui, Vercel AI SDK, React-Flow, Recharts
- **Catalyst alternative considered:** N/A — these are open-source client libraries, not cloud services.
- **Catalyst gap found:** Not applicable. All libraries are bundled into the frontend and served from Catalyst Web Client Hosting.
- **Source of confirmation:** These libraries are MIT/Apache-licensed npm packages compiled into our static bundle.
- **Why we chose them:** Industry-standard frontend stack; no managed third-party endpoint is called.
- **Risk if rejected:** N/A — these are not third-party cloud services under the rule.
- **Mitigation:** Hosted entirely on Catalyst Web Client Hosting. No external runtime dependency introduced.

---

## Summary Table

| Service | Category | Catalyst alt? | Decision |
|---|---|---|---|
| Neo4j AuraDB | Hard gap | None | LOCKED |
| Google Maps | Hard gap | None | LOCKED |
| Gemini Live API (Kannada) | Documented gap | Zia (no Kannada) | LOCKED for Kannada path |
| Gemini 2.5 Pro | Conditional | Qwen 2.5 | A/B test pending |
| gemini-embedding-001 | Conditional | QuickML RAG | A/B test pending |
| Google STT/TTS fallback | Conditional | Zia / Gemini Live | Standby |
| Vertex AI Forecasting | Conditional | Zia AutoML | Standby |
| OSS frontend libs | N/A | N/A | Hosted on Catalyst |

---

*End of decisions log. This file is the canonical evidence record for Catalyst-first compliance in the Datathon 2026 submission. Any future change to the third-party surface must update this file before deployment.*
