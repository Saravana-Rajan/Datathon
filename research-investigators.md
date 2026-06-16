# Indian Police Investigator Research Brief

*Datathon 2026 — Challenge 01: Conversational AI for Karnataka Police Investigators*

---

## 1. CCTNS — What Investigators Use Today

The **Crime and Criminal Tracking Network and Systems (CCTNS)** is the backbone IT platform for Indian policing, conceived after the 2008 Mumbai attacks and rolled out from 2013 onward by the National Crime Records Bureau (NCRB). It interconnects **over 15,000 police stations** across 28 states and 8 UTs through a Core Application Software (CAS) built by Wipro in Bengaluru. CCTNS digitises FIR registration, case diaries, charge sheets, arrest memos, and stolen-property records, and it feeds NATGRID and state portals (in Karnataka, **PoliceIT / Police Seva**). At the police-station level, an SI or Inspector enters the FIR into CCTNS, attaches witness statements, and updates the case as it moves toward charge sheet.

What's painful: an October 2018 NCRB Journal paper flagged that **inaccurate, low-quality data entry "sometimes hinders" report and query production**. Only ~80% of fields in core forms (IIF1–IIF6) and ~56% of supplementary fields (IIF8–IIF11) are actually filled in nationally. There is **no unique identifier** for arrestees or unidentified bodies, so the same accused appears under multiple spellings across districts. CBI and NIA FIRs are not in CCTNS, making the database incomplete for inter-agency cases. Rural stations struggle with **patchy connectivity**, forcing offline-first workarounds. Search itself is form-based, exact-match, and brittle — investigators cannot ask natural-language questions like "show me chain-snatching cases on two-wheelers in Mysuru this quarter."

What investigators wish it could do: free-text/voice queries in Kannada and English, fuzzy name and alias matching, MO-based pattern discovery across district boundaries, automatic linkage of FIRs with the same suspects/vehicles/phones, and predictive flagging of repeat offenders likely involved in a fresh case. The system today is a digital filing cabinet; investigators want a working partner.

## 2. Karnataka Police Ranks & Investigation Workflow

| # | Rank | Investigates? | Notes |
|---|------|---------------|-------|
| 1 | Director General of Police (DGP) | No | State head; policy and supervision |
| 2 | Additional DGP (ADGP) | No | Heads zones / wings (Law & Order, CID, Crime) |
| 3 | Inspector General of Police (IGP) | No | Heads 7 ranges in Karnataka |
| 4 | Deputy IGP (DIG) | Supervisory | Range deputy / specialised units |
| 5 | Superintendent of Police (SP) / Commissioner | Supervisory | District head; reviews major cases |
| 6 | Additional SP / DCP | Supervisory | Sub-division oversight |
| 7 | **Deputy Superintendent of Police (DySP) / ACP** | **Yes** | IO for serious cases (murder, dacoity, POCSO) |
| 8 | **Police Inspector (PI)** | **Yes** | Station House Officer (SHO) in urban stations; primary IO |
| 9 | **Police Sub-Inspector (PSI)** | **Yes** | SHO in rural stations; Karnataka HC (2022) confirmed PSIs can investigate and file charge sheets |
| 10 | Assistant Sub-Inspector (ASI) | Assists | Limited investigative duties |
| 11 | Head Constable (HC) | Assists | Beat work, witness handling |
| 12 | Police Constable (PC) | No | Patrol, summons service |

**Workflow:** A complaint is received at the police station → if cognisable, the SHO (PI or PSI) registers an **FIR** in CCTNS under the relevant BNS / IPC sections → the case is assigned to an **Investigating Officer (IO)**, typically a PSI, PI, or DySP depending on gravity → IO visits scene, collects evidence, records 161 CrPC / 180 BNSS statements, arrests suspects, sends items to FSL → IO files the **charge sheet (final report)** in the jurisdictional magistrate's court within 60/90 days. Supervisory officers (SP/DCP) review monthly crime statements and pendency.

## 3. State Crime Records Bureau (SCRB) Karnataka

The **SCRB Karnataka** is the state-level counterpart of NCRB, housed under Karnataka State Police. It is the central repository for crime data flowing up from **District Crime Record Bureaus (DCRBs)** — every DCRB sends monthly crime reviews, fortnightly crime statements, and criminal dossiers to SCRB.

**What it holds:** all FIRs registered in the state (uploaded to PoliceIT — citizens can download non-sensitive FIRs from the KSP portal; FIRs related to terrorism, rape, and POCSO are excluded from public view), criminal dossiers (history-sheeters, rowdy-sheeters), stolen-vehicle and stolen-property registers, missing-person and unidentified-body records, fingerprint records (linked to NAFIS), and crime statistics that feed NCRB's annual "Crime in India" publication.

**Who accesses:** Karnataka Police officers (investigators, intelligence, special units), authorised central agencies via NATGRID, courts via formal requisition, and the public via limited citizen services (police verification certificates, stolen-vehicle search, FIR download, lost-article reports). SCRB also runs analytics and publishes the state Crime Review. [UNCERTAIN: exact API access surface for officers — likely via Police Seva intranet and CCTNS CAS.]

## 4. Investigator Personas

### Persona A — PSI Ramesh Gowda, 32, Rural Station SHO
- **Posting:** SHO at a rural police station in Mandya district
- **Daily job:** Registers FIRs, leads investigation on 15–25 active cases (theft, assault, NDPS, MV accidents), supervises 2 HCs and 8 PCs, attends court for ongoing trials
- **Top 3 pains:** (1) drowning in CCTNS form-filling instead of fieldwork, (2) suspect names in Kannada spelled five different ways across districts so cross-referencing fails, (3) cannot easily pull "similar MO" cases from neighbouring stations
- **Would ask AI:** "Recent two-wheeler thefts in Mandya and Mysuru rural where accused fled on KA-11 plate" / "Show all cases linked to mobile 98xxxxxx21"

### Persona B — Inspector Anjali Hegde, 41, Urban Crime Branch
- **Posting:** PI, Crime Branch, Bengaluru City
- **Daily job:** Investigates chain-snatching, burglary, organised property crime; coordinates with technical cell (CDR/IPDR), runs informant network, briefs ACP weekly
- **Top 3 pains:** (1) connecting fresh case to a known gang requires manually flipping through dossiers in multiple stations, (2) CDR analysis is offline in Excel and disconnected from CCTNS, (3) language barrier — complainants give statements in Kannada but CCTNS search is English-biased
- **Would ask AI:** "Chain-snatching cases in last 90 days where two accused on Pulsar bike, snatched and fled south" / "Has this IMEI appeared in any FIR statewide?"

### Persona C — DySP Imran Pasha, 47, District CID/CCB
- **Posting:** DySP, City Crime Branch, Hubballi-Dharwad
- **Daily job:** IO for grave cases (murder, dacoity, POCSO), supervises 3 PIs, owns conviction strategy and inter-state coordination, briefs SP and prosecution
- **Top 3 pains:** (1) inter-state criminal movement (rowdy-sheeters operating across KA-MH-AP) hard to track, (2) repeat-offender prediction is gut-feel, not data, (3) charge-sheet quality varies wildly across IOs reporting to him
- **Would ask AI:** "Profile of suspect X across Karnataka, Maharashtra, Telangana" / "Cases where the IO missed Section 27 NDPS evidence step" / "Predict re-offence probability for accused released on bail last month"

## 5. Top 15 Queries Investigators Would Realistically Ask

**Pattern discovery (MO)**
1. EN: "Show me all chain-snatching cases in Bengaluru South in the last 60 days where the accused used a two-wheeler."
   KN: *"Kaḷedha 60 dinagaḷalli Bengaḷūru dakṣiṇadalli dwichakra vāhana baḷasi naḍeda sarapaḷi kaḷḷatana prakaraṇagaḷannu tōrisi."*
2. EN: "Burglaries where entry was through the bathroom ventilator, last 6 months, statewide."
   KN: *"Kaḷedha 6 tingaḷalli rājyāddyanta snānagṛhada gāḷi kiṇḍiyinda praveśisi naḍeda kannada prakaraṇagaḷu."*
3. EN: "House thefts where accused posed as electricity-board officials."
   KN: *"Vidyut maṇḍaḷi adhikāriyendu naṭisi naḍesida mane kaḷḷatana prakaraṇagaḷu."*

**Criminal network**
4. EN: "All FIRs linked to mobile number 98xxxxxx21 or its associated IMEI."
   KN: *"Mobile saṅkhye 98xxxxxx21 athavā adara IMEIge sambandhisida ella FIRgaḷu."*
5. EN: "Show co-accused network of rowdy-sheeter Suresh @ Pintu, KR Puram."
   KN: *"KR Puramda rowdy-sheeter Sureśa @ Pintu jote sambandhisida sahā-āropigaḷ jāla."*
6. EN: "Cases where accused A and accused B appear together in any FIR, last 3 years."
   KN: *"Kaḷedha 3 varṣagaḷalli āropi A mattu āropi B ibbarū ondē FIRnalli iruva prakaraṇagaḷu."*

**Hotspot / trend**
7. EN: "Heatmap of NDPS seizures in Mangaluru in 2026."
   KN: *"2026ralli Maṅgaḷūrina NDPS vasti vaśapaḍisikoḷḷuvike heatmap."*
8. EN: "Which beats in Yelahanka show rising vehicle-theft trend month-on-month?"
   KN: *"Yelahaṅkadalli yāva beats vāhana kaḷḷatana hēcciside?"*

**Prediction**
9. EN: "List history-sheeters released on bail in the last 30 days in my jurisdiction."
   KN: *"Nanna vyāptiyalli kaḷedha 30 dinagaḷalli jāmīnu mēle biḍugaḍeyāda itihāsa-sheeters."*
10. EN: "Predict likely accused profile for last night's ATM break-in at Indiranagar."
    KN: *"Ninne rātri Indirānagara ATM odeyuvike — sambhāvya āropi prōfailu."*

**Case lookup**
11. EN: "Status of FIR 142/2026 of Vidhana Soudha PS — has chargesheet been filed?"
    KN: *"Vidhāna Soudha ṭhāṇeya FIR 142/2026 sthiti — dōṣa paṭṭi sallisalāgide?"*
12. EN: "Pull all 60-day-pending cases assigned to PSI Ramesh."
    KN: *"PSI Rameśavarige niyojita 60 dinagaḷige hecciḍda bākiya prakaraṇagaḷu."*

**MO matching**
13. EN: "Find cases similar to this FIR's MO — show top 10 with similarity score."
    KN: *"Ī FIRna MOge horuva prakaraṇagaḷu — meḷe 10 hōliketa scōre joteege."*
14. EN: "Cases involving a white Bolero with partial plate KA-25-xxxx-9382."
    KN: *"Bili Bolero, bhāgaśaḥ namūne KA-25-xxxx-9382 olagonda prakaraṇagaḷu."*
15. EN: "Cyber-fraud cases where accused used UPI ID ending in @okicici and victim above 60."
    KN: *"@okicicide koneyāguva UPI baḷasi naḍeda cyber vañcane, sanruddha bali 60 mēlpaṭṭu."*

## 6. Pain Points Our AI Solves (Concrete)

- **Pain:** CCTNS exact-match search misses Kannada spelling variants (Suresh / Sureśa / Suresha). → **Fix:** transliteration-aware fuzzy entity resolution across English and Kannada.
- **Pain:** IO spends 2+ hours flipping FIRs across stations to find MO matches. → **Fix:** semantic MO search ranks similar cases statewide in seconds.
- **Pain:** No unique identifier for accused; same person looks like 5 people. → **Fix:** AI-side entity-resolution layer clusters aliases by phone, address, biometrics, co-accused graph.
- **Pain:** Phone/IMEI/vehicle cross-reference is manual and Excel-based. → **Fix:** structured-attribute lookup unified with FIR narrative in one query.
- **Pain:** Inter-district criminal movement invisible until SCRB monthly review. → **Fix:** real-time graph queries across districts and ranges.
- **Pain:** Supervisors can't quickly see which IOs have pendency or weak charge sheets. → **Fix:** natural-language pendency and quality dashboards.
- **Pain:** Predictive policing is gut-feel — repeat offenders re-offending on bail. → **Fix:** risk scoring on bail releases using historic patterns, surfaced to SHO.
- **Pain:** Rural connectivity is patchy. → **Fix:** offline-first PWA / WhatsApp-style bot caches recent queries.
- **Pain:** Junior IOs miss procedural steps (e.g., Section 27 NDPS, 65B certificate). → **Fix:** AI checklist nudges based on FIR sections invoked.
- **Pain:** Kannada-only complainants → English-biased search → lost evidence. → **Fix:** bilingual query layer, Kannada voice in, structured query out.

## 7. Sources

- https://en.wikipedia.org/wiki/Crime_and_Criminal_Tracking_Network_and_Systems
- https://en.wikipedia.org/wiki/National_Crime_Records_Bureau
- https://en.wikipedia.org/wiki/NATGRID
- https://en.wikipedia.org/wiki/Automated_Facial_Recognition_System_(India)
- https://en.wikipedia.org/wiki/Criminal_Investigation_Department_(India)
- https://www.justice.gov/eoir/page/file/1290786/dl
- https://testbook.com/ias-preparation/crime-and-criminal-tracking-network-system-cctns
- https://eservices.tnpolice.gov.in/CCTNSNICSDC/pdfs/aboutcctns/cctns_cas.pdf
- https://informatics.nic.in/uploads/pdfs/a506f896_CCTNS.pdf
- https://digitalpolice.gov.in/DigitalPolice/AboutUs
- https://ncrb.gov.in/
- https://ksp.karnataka.gov.in/page/About+Us/Organization/en
- https://www.nammakpsc.com/articles/karnataka-state-police/
- https://www.karnataka.com/govt/law-and-order/
- https://www.indiacode.nic.in/bitstream/123456789/8195/1/4_of_1964_(e).pdf
- https://mysurupolice.karnataka.gov.in/page/Specail+Branches/District+Crime+Record+Bureau/en
- https://policeseva.ksp.gov.in/
- https://www.deccanherald.com/content/573942/firs-filed-anywhere-state-available.html
- https://www.deccanherald.com/india/karnataka/with-rising-cases-of-cybercrimes-karnataka-to-get-dgp-to-oversee-investigations-3275602
- https://www.livelaw.in/news-updates/karnataka-high-court-police-sub-inspector-chargesheet-suicide-married-woman-200255
- https://primelegal.in/2022/05/31/police-sub-inspector-is-empowered-to-investigate-file-charge-sheet-in-karnataka-high-court/
- https://www.leadindia.law/blog/en/can-a-police-sub-inspector-investigate-and-file-a-charge-sheet-in-criminal-case/
- https://en.wikipedia.org/wiki/Modus_operandi
