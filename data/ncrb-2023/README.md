# NCRB "Crime in India 2023" — Normalized Aggregates

Real, citable, aggregate crime statistics for the Sarvik Datathon 2026 project.
Used to **ground** the 50K synthetic FIR corpus against published reality.

---

## Source & Provenance

- **Publisher:** National Crime Records Bureau (NCRB), Ministry of Home Affairs,
  Government of India.
- **Distribution mirror:** OpenCity India — <https://data.opencity.in/dataset/crime-in-india-2023>
- **Dataset UUID:** `40449a25-7fb3-4e38-91b9-f834af6078e2`
- **Year covered:** 2023 (reporting year). Some PDFs include 2021–2023 trend data.
- **License:** "Other (Public Domain)" per OpenCity. Underlying NCRB publications
  are GoI public-sector reports issued for free public use. Attribution
  recommended; redistribution permitted.
- **Citation:**
  > National Crime Records Bureau, Ministry of Home Affairs, Government of
  > India. *Crime in India 2023.* New Delhi: NCRB, 2024. Retrieved from
  > data.opencity.in.

---

## Files in this directory

### Normalized outputs (machine-readable)

| File | Records | Size | Description |
|------|---------|------|-------------|
| `all_states.jsonl` | 24,300 | ~9.9 MB | All metro cities, long-format, one metric per row |
| `karnataka_aggregates.jsonl` | 450 | ~184 KB | Karnataka rows (Bengaluru only — sole KA metro in NCRB's 53-city list) |

### Raw downloads (`raw/`)

| File | Type | Size | Notes |
|------|------|------|-------|
| `ipc_156_3_2023.xlsx` | XLSX | 13 KB | City-wise IPC cases (incl. CrPC 156_3 registrations) |
| `persons_disposal_ipc_2023.xlsx` | XLSX | 48 KB | Arrest / chargesheet / trial outcomes — IPC crimes |
| `persons_disposal_women_2023.xlsx` | XLSX | 45 KB | Same schema, scoped to crimes against women |
| `persons_disposal_children_2023.xlsx` | XLSX | 42 KB | Same schema, scoped to crimes against children |
| `property_stolen_recovered_2023.xlsx` | XLSX | 29 KB | Theft / burglary / robbery / dacoity — value (Crores) + counts |
| `ndps_seizures_2023.xlsx` | XLSX | 33 KB | NDPS Act drug seizures — kg / litre / numbers per substance |
| `crime_in_india_vol1_2023.pdf` | PDF | 22 MB | Master narrative report Volume 1 (state-wise, not parsed) |
| `crime_in_india_vol2_2023.pdf` | PDF | 17 MB | Master narrative report Volume 2 (specialized chapters, not parsed) |

**Total downloaded:** 8 files, ~39.6 MB on disk.

### Tooling

| File | Purpose |
|------|---------|
| `normalize.py` | Reproducible XLSX → JSONL flattener. Run with `python normalize.py`. |

---

## Normalized JSONL schema

One record = one numeric data point.

```json
{
  "state": "Karnataka",
  "city": "Bengaluru",
  "district": null,
  "crime_type": "cases_reported_under_156_3_during_the_year",
  "metric_path": "2023 | Cases Reported Under 156_3 during the year",
  "year": 2023,
  "count": 1218,
  "unit": "cases",
  "source_file": "ipc_156_3_2023.xlsx",
  "ncrb_table_id": "NCRB-2023-CITY-IPC-156_3",
  "is_total_row": false
}
```

Field notes:
- `state` — derived via deterministic city → state map. Set to
  `ALL_INDIA_METRO_TOTAL` for the 53-cities total row, `[UNCERTAIN]` if a city
  is unmappable (should never trigger on the current NCRB metro list).
- `district` — always `null`. NCRB's metro tables are **city-level only**; no
  sub-district breakdown exists in these files. State/district detail lives in
  the unparsed PDF Volumes 1 & 2.
- `crime_type` — leaf header in lower-snake. Use `metric_path` for the full
  pipe-joined header lineage when crime_type alone is ambiguous.
- `unit` — `cases` | `persons` | `crores_inr` | `kg` | `litre` | `numbers` |
  `null`. Auto-detected from header text.
- `is_total_row` — `true` for "TOTAL CITIES" rows so downstream sums don't
  double-count.

---

## Karnataka snapshot (Bengaluru, 2023)

Headline figures pulled straight from the normalized data:

| Metric | Count |
|--------|------:|
| Total IPC cases reported | **41,637** |
| Cases registered in police stations | 40,419 |
| CrPC 156(3) registrations | 1,218 |
| Theft — cases with property stolen | 10,438 |
| Burglary — cases with property stolen | 1,142 |
| Robbery — cases with property stolen | 790 |
| Theft — cases with property recovered (total) | 2,999 |

**Coverage limit:** Karnataka only appears via **Bengaluru** in NCRB's 53-metro
universe. State-wide and district-level (Mysuru, Hubli-Dharwad, Mangaluru,
etc.) figures require parsing the PDF reports (`raw/crime_in_india_vol*.pdf`)
or sourcing the state-wise XLSX tables direct from `ncrb.gov.in` if/when they
are republished there.

---

## Known gaps & blockers

- **Datastore Errors on OpenCity:** Five 156_3 city-wise XLSX files for
  Women/Children/SC/ST crimes had `Datastore Error` flags on the upstream
  resource page. They were **not downloaded**; falling back to the disposal
  files (which contain the same case populations via a wider schema).
- **PDF-only categories:** Murder, kidnapping, cybercrime, economic offences,
  SC/ST atrocities — only released as PDF on OpenCity 2023 vintage. They are
  retrievable from the URLs in the harvest log but were skipped from
  normalization to stay within budget. The two volume PDFs cover them
  narratively.
- **No 2024 data:** "Crime in India 2024" had not been published by NCRB as of
  the harvest date.

---

## Loading into Catalyst Data Store

```python
import json
from pathlib import Path

NCRB = Path("data/ncrb-2023")

def load_ncrb_karnataka():
    """Yield Catalyst-ready records for the Karnataka knowledge slice."""
    with (NCRB / "karnataka_aggregates.jsonl").open(encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

# Or load everything for cross-state comparisons:
def load_ncrb_all():
    with (NCRB / "all_states.jsonl").open(encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)
```

For the Catalyst Data Store, recommended ingest:
- **Collection:** `ncrb_aggregates_2023`
- **Primary key:** `(source_file, city, metric_path)` — stable across reruns of
  `normalize.py`.
- **Embed for RAG:** concatenate `f"{state} {city} {metric_path} {count} {unit} (NCRB 2023)"`
  so retrieval matches both metric and place.

---

## Integration plan with Sarvik's synthetic FIRs

1. **Trend grounding (SQL).** Add a `ncrb_aggregates` table; let the SQL agent
   compute `(synthetic_fir_count / ncrb_real_count) * 100` per crime type so
   demos cite a real anchor (e.g., "synthetic dataset represents ~12% of
   Bengaluru's real 10,438 thefts in 2023").
2. **RAG citation enrichment.** When the RAG agent answers a Bengaluru-specific
   crime question, retrieve the matching `karnataka_aggregates.jsonl` row and
   append `ncrb_table_id` + `metric_path` as a verifiable citation block.
3. **Validation guardrail.** During synthetic-FIR generation, reject any
   distribution that produces a `crime_type` mix more than ±2σ away from the
   NCRB Bengaluru baseline — keeps synthetic data plausibly real and prevents
   the LLM from hallucinating implausible crime rates.

---

## Reproducing the harvest

```bash
mkdir -p raw
# Re-download (URLs in this README)
curl -sSL <url> -o raw/<filename>
# Re-normalize
python normalize.py
```

`normalize.py` is **idempotent**: rerunning over unchanged raw XLSX produces
byte-identical JSONL.
