# Email to Datathon 2026 Organizers — Third-Party Service Clarification

---

**To:** datathon2026support@hack2skill.com
**CC:** [team-lead@example.com]
**From:** [team-lead@example.com]
**Subject:** [Datathon 2026 — Challenge 01] Clarification on Third-Party Service Use Where Catalyst Has Gaps

---

Dear Datathon 2026 Organizing Committee,

Greetings from **Team [TEAM_NAME]**, participating in **Challenge 01 — Intelligent Conversational AI for KSP Crime Database** (Registration ID: **[REG_ID_PLACEHOLDER]**).

We have carefully reviewed the Resources page and fully understand the two foundational requirements: that **deployment via Zoho Catalyst is mandatory for all submissions, without exception**, and that **using a third-party alternative where a Catalyst service is available may affect submission validity**. We are committed to honoring both, and Catalyst is our primary platform — approximately **90% of our architecture** (Functions, AppSic, Data Store, File Store, Authentication, API Gateway, Cache, Job Scheduler, Zia AutoML, and QuickML LLM Serving) runs natively on Catalyst.

We are writing to seek **written confirmation** that the following narrowly scoped third-party augmentations — used **only where Catalyst has no equivalent service or a documented capability gap** — do not affect the validity of our submission:

1. **Graph Database — Neo4j AuraDB (GCP, asia-south1).** Catalyst does not offer a native graph database. Neo4j is required for **Feature 5: Criminal Network Analysis** as specified in the problem statement (relationship traversal across suspects, cases, and locations).

2. **Maps and Geocoding — Google Maps Platform.** Catalyst does not offer a Maps or geocoding service. Required for **Feature 6: Crime Hotspot Detection and Visualization**.

3. **Kannada Voice STT/TTS — Google Cloud Gemini Live API.** Catalyst Zia Services currently support English and Hindi only (verified in Catalyst documentation as of June 2026). Karnataka State Police is the project sponsor, and **Kannada is the operational language** for end users; native Kannada voice support is essential to the user experience.

4. **Premium LLM augmentation — Gemini 2.5 Pro.** Catalyst QuickML LLM Serving currently offers the Qwen 2.5 family. We use Gemini 2.5 Pro **only for complex Kannada synthesis queries** where Qwen output quality is measurably insufficient. We will publish full **A/B benchmark results** comparing Qwen 2.5 vs Gemini 2.5 Pro on Kannada query accuracy, fluency, and latency as supporting evidence.

5. **Backup forecasting — Vertex AI Forecasting.** Used **only as a contingency** if Catalyst Zia AutoML model quality on time-series crime forecasting falls below our acceptance threshold. **Primary remains Zia AutoML.**

**Data residency and compliance:** All third-party services listed above are hosted in **India regions (asia-south1 / Mumbai)**. We maintain full compliance with the **Information Technology Act, 2008**, and all sensitive data remains within Indian jurisdiction.

We respectfully request:

- **Written confirmation** that the specific augmentations above do not affect submission validity, given that each addresses a documented Catalyst gap.
- **Guidance on the preferred process** for documenting our Catalyst-vs-third-party A/B test results as evidence of our good-faith Catalyst-first effort.
- Information on any **sponsor-track or special-category prizes** (KSP, Zoho, or hack2skill) we should be aware of and eligible to compete for.

We are glad to provide additional architectural diagrams, the full Catalyst service inventory we are using, or a brief call at your convenience.

Thank you for organizing this opportunity to contribute to public safety in Karnataka. We look forward to your guidance.

Warm regards,

**[TEAM_LEAD_NAME]**
Team Lead, **Team [TEAM_NAME]**
Email: [team-lead@example.com] | Phone: [+91-XXXXX-XXXXX]

**Team members:**
- [Member 1 Name] — [Role] — [College / Organization]
- [Member 2 Name] — [Role] — [College / Organization]
- [Member 3 Name] — [Role] — [College / Organization]
- [Member 4 Name] — [Role] — [College / Organization]

**Affiliation:** [College / Organization Name]
**Registration ID:** [REG_ID_PLACEHOLDER]
**Challenge:** Challenge 01 — Intelligent Conversational AI for KSP Crime Database

---

## How to Send This Email

1. **Recipient (To):** `datathon2026support@hack2skill.com`
2. **CC:** Your team lead's email address (so a second team member retains the thread for audit purposes)
3. **Subject line (copy exactly):**
   `[Datathon 2026 — Challenge 01] Clarification on Third-Party Service Use Where Catalyst Has Gaps`
4. **Before sending — replace all placeholders:**
   - `[TEAM_NAME]` (appears in subject line context, body, and signature)
   - `[REG_ID_PLACEHOLDER]` (your hack2skill registration ID)
   - `[TEAM_LEAD_NAME]`, `[team-lead@example.com]`, `[+91-XXXXX-XXXXX]`
   - All four `[Member X Name]` / `[Role]` / `[College / Organization]` entries
   - `[College / Organization Name]` in the affiliation line
5. **Expected response time:** 3-5 business days. If no reply by day 5, send a polite follow-up referencing the original thread.
6. **Save the reply.** Archive the organizer's response in your project repository (e.g., `docs/compliance/organizer-confirmation.pdf`) as evidence of good-faith Catalyst-first compliance — this protects your submission during judging and any post-submission review.
7. **Optional but recommended:** Request read receipt / delivery confirmation if your email client supports it, so you have proof of delivery in case the response is delayed.
