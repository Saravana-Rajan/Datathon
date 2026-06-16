# Synthetic FIR Data Generator — Karnataka Police

`generate_synthetic_firs.py` produces realistic, fully synthetic First
Information Report (FIR) records for use in the Karnataka Police
conversational AI hackathon. Records are bilingual (English + Kannada),
geographically anchored to real Karnataka police stations, and follow
plausible crime patterns.

> No real complainant, accused, officer, or phone-number data is
> contained in this dataset. Names are sampled from curated first-name
> and surname lists; phone numbers are masked. Coordinates are jittered
> around real station locations.

---

## What this generates

Each record is a single JSON object written one-per-line (JSONL). Key
realism features:

- **Bengaluru-heavy distribution** — ~70% of FIRs are filed at one of 30
  real Bengaluru Urban stations; the remainder are spread across Mysuru,
  Dharwad, Mangaluru, Belagavi, Kalaburagi, and 12+ other districts.
- **Crime mix that matches reality** — vehicle theft, cybercrime, fraud,
  and burglary dominate; murder and attempt-to-murder are rare.
- **Time-of-day patterns** — theft skews to night, fraud and cybercrime
  to working hours, accidents to peak commute windows.
- **IPC sections** that align with crime type
  (e.g., `379/411` for vehicle theft, `498A/323` for domestic violence,
  `IT Act 66C/66D + 420` for cybercrime).
- **Linked FIRs** — 5–10% of records share an accused with an earlier
  FIR, seeding patterns for graph / serial-offender analytics.
- **Bilingual narratives** — every record carries an English `narrative`
  and `modus_operandi` plus Kannada (`narrative_kannada`,
  `modus_operandi_kannada`) using real Kannada script (ಕನ್ನಡ).
- **Multicultural names** — Hindu/Kannadiga, Muslim, Christian, Sikh,
  Tamil, Telugu, and Malayali names mixed proportionally for Bengaluru.

---

## How to run it

```bash
pip install faker          # required
# pip install faker-india  # optional, gracefully ignored if missing

# Default: 50,000 records to firs.jsonl + firs_sample.jsonl (first 100)
python generate_synthetic_firs.py --count 50000 --output firs.jsonl

# Smaller demo set
python generate_synthetic_firs.py --count 1000 --output demo.jsonl

# Custom sample path and reproducible seed
python generate_synthetic_firs.py \
    --count 50000 \
    --output firs.jsonl \
    --sample-output firs_sample.jsonl \
    --seed 42
```

CLI flags:

| Flag              | Default              | Description                                      |
|-------------------|----------------------|--------------------------------------------------|
| `--count`         | `50000`              | Number of FIRs to generate                       |
| `--output`        | `firs.jsonl`         | Output JSONL path                                |
| `--sample-output` | `<output>_sample.jsonl` | First 100 records, for quick inspection        |
| `--seed`          | `42`                 | Random seed for reproducibility                  |

Performance: ~50K records in well under 5 minutes on a typical laptop;
the script is single-file pure Python, streaming writes line-by-line so
memory stays flat. On any error it saves partial work and exits.

---

## Schema reference

| Field                       | Type                                | Notes                                                                 |
|-----------------------------|-------------------------------------|-----------------------------------------------------------------------|
| `fir_no`                    | string                              | `<STATION_CODE>/<YEAR>/<COUNTER>` e.g. `MGR/2024/00012`               |
| `station_name`              | string                              | Real Karnataka police station                                         |
| `station_lat`, `station_lng`| float                               | Real station coordinates                                              |
| `district`                  | string                              | Real Karnataka district                                               |
| `date_registered`           | string `YYYY-MM-DD`                 | Between 2022-01-01 and 2025-12-31                                     |
| `time_registered`           | string `HH:MM:SS`                   | Crime-type aware time-of-day distribution                             |
| `crime_type`                | enum                                | See list below                                                        |
| `ipc_sections`              | list[string]                        | Crime-type-aware IPC / NDPS / IT Act mapping                          |
| `location_lat`, `location_lng` | float                            | Within ~10 km of station                                              |
| `location_text`             | string                              | Real Bengaluru / Karnataka locality name                              |
| `complainant`               | object                              | `{ name, age, gender (M/F), phone (masked), address }`                |
| `accused`                   | list[object]                        | `{ name, age, gender, status: arrested/absconding/on_bail/unknown }`  |
| `victims`                   | list[object]                        | May overlap with complainant (`relation_to_complainant: "self"`)      |
| `modus_operandi`            | string                              | English MO narrative                                                  |
| `modus_operandi_kannada`    | string                              | Kannada MO narrative (Unicode Kannada script)                         |
| `investigating_officer`     | object                              | `{ name, rank (PSI/SI/Inspector), badge_no }`                         |
| `status`                    | enum                                | `under_investigation / chargesheet_filed / closed / transferred`      |
| `linked_fir_nos`            | list[string]                        | Empty for most; populated for ~5–10% to simulate criminal patterns    |
| `narrative`                 | string                              | 1–3 sentence English summary                                          |
| `narrative_kannada`         | string                              | Kannada summary                                                       |

### Crime types

`vehicle_theft, chain_snatching, burglary, robbery, fraud, assault,
kidnapping, narcotics, cybercrime, missing_person, accident,
public_nuisance, domestic_violence, murder, attempt_to_murder`

### Sample record

```json
{
  "fir_no": "INDR/2024/00128",
  "station_name": "Indiranagar Police Station",
  "station_lat": 12.9784,
  "station_lng": 77.6408,
  "district": "Bengaluru Urban",
  "date_registered": "2024-08-19",
  "time_registered": "23:47:11",
  "crime_type": "vehicle_theft",
  "ipc_sections": ["379", "411"],
  "location_lat": 12.9711,
  "location_lng": 77.6492,
  "location_text": "CMH Road",
  "complainant": {
    "name": "Manjunath Gowda",
    "age": 41,
    "gender": "M",
    "phone": "98XXXXXX21",
    "address": "#214, 7th Cross, 12th Main, CMH Road, Bengaluru Urban - 560038"
  },
  "accused": [
    { "name": "Unknown", "age": null, "gender": "U", "status": "unknown" }
  ],
  "victims": [
    { "name": "Manjunath Gowda", "age": 41, "gender": "M",
      "relation_to_complainant": "self" }
  ],
  "modus_operandi": "Two-wheeler parked outside residence was stolen during night hours; lock was found broken.",
  "modus_operandi_kannada": "ರಾತ್ರಿ ವೇಳೆ ದೂರುದಾರರ ದ್ವಿಚಕ್ರ ವಾಹನವನ್ನು ಅಪರಿಚಿತ ಕಳ್ಳರು ಕದ್ದೊಯ್ದಿದ್ದಾರೆ.",
  "investigating_officer": {
    "name": "Ravi Shetty", "rank": "SI", "badge_no": "KSP47213"
  },
  "status": "under_investigation",
  "linked_fir_nos": [],
  "narrative": "Complainant Manjunath Gowda (age 41) reported the incident at CMH Road. Two-wheeler parked outside residence was stolen during night hours; lock was found broken.",
  "narrative_kannada": "ದೂರುದಾರ Manjunath Gowda ಅವರು CMH Road ಬಳಿ ನಡೆದ ಘಟನೆಯ ಬಗ್ಗೆ ದೂರು ನೀಡಿದ್ದಾರೆ. ರಾತ್ರಿ ವೇಳೆ ದೂರುದಾರರ ದ್ವಿಚಕ್ರ ವಾಹನವನ್ನು ಅಪರಿಚಿತ ಕಳ್ಳರು ಕದ್ದೊಯ್ದಿದ್ದಾರೆ. ಆರೋಪಿಗಳನ್ನು ಗುರುತಿಸಿಲ್ಲ."
}
```

---

## Loading into Catalyst Data Store

The output is plain JSONL (one JSON object per line), so it loads into
Zoho Catalyst's Data Store with minimal preprocessing.

### Option 1 — CLI bulk import

1. Create a Data Store table called `firs` whose columns mirror the
   schema above. For nested fields (`complainant`, `accused`, `victims`,
   `investigating_officer`, `ipc_sections`, `linked_fir_nos`) use the
   `TEXT` / `JSON` column type and store the serialized JSON.
2. Convert JSONL to CSV (or use Catalyst's JSON import) — example:

   ```python
   import json, csv
   FIELDS = ["fir_no","station_name","station_lat","station_lng",
             "district","date_registered","time_registered","crime_type",
             "ipc_sections","location_lat","location_lng","location_text",
             "complainant","accused","victims","modus_operandi",
             "modus_operandi_kannada","investigating_officer","status",
             "linked_fir_nos","narrative","narrative_kannada"]
   with open("firs.jsonl", encoding="utf-8") as src, \
        open("firs.csv", "w", encoding="utf-8", newline="") as dst:
       w = csv.DictWriter(dst, fieldnames=FIELDS)
       w.writeheader()
       for line in src:
           rec = json.loads(line)
           for k in ("ipc_sections","complainant","accused","victims",
                     "investigating_officer","linked_fir_nos"):
               rec[k] = json.dumps(rec[k], ensure_ascii=False)
           w.writerow(rec)
   ```

3. Use `catalyst datastore:import --table firs --file firs.csv` (or the
   Catalyst Console's Import option) to bulk-load.

### Option 2 — SDK insert

Within a Catalyst Function:

```python
import json, catalyst
app = catalyst.initialize()
table = app.datastore().table("firs")
with open("firs.jsonl", encoding="utf-8") as f:
    batch = []
    for line in f:
        batch.append(json.loads(line))
        if len(batch) >= 200:
            table.insert_rows(batch)
            batch = []
    if batch:
        table.insert_rows(batch)
```

Recommended indexes for the hackathon conversational AI use-case:
`fir_no` (unique), `station_name`, `district`, `crime_type`,
`date_registered`, and a composite on `(district, crime_type, date_registered)`
for time-series filters.

---

## License & ethical use

This dataset is fully synthetic and intended only for hackathon /
research / model evaluation purposes. Do not present generated records
as real cases, real victims, or real officers.
