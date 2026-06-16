# Vertex AI Forecasting — When You're Ready

**Status:** ON HOLD. Only spin up if Catalyst Zia AutoML can't meet our forecasting needs.

---

## When to use this

Pick this up **only if** Zia AutoML fails one or more of our Week 0 validation checks: (a) no usable confidence intervals on per-station forecasts, (b) training fails on our sparse station+crime-type slices, (c) MAPE > 25% on the holdout week, or (d) the API surface won't let us batch-predict across all 50+ stations in a single call. If Zia passes, skip this entirely — Vertex is heavier ops for marginal gain.

## What we'll forecast

**Per-station, per-crime-type daily counts** over a **7-day horizon** with 80% and 95% confidence bands. Series ID is `{station}__{crime_type}` (e.g., `indiranagar__vehicle_theft`). The downstream use case is the "where to patrol tonight" beat-officer assistant — we surface predicted counts + uncertainty so commanders allocate patrol density rationally rather than reactively.

## Prerequisites (5 min)

- [x] GCP project active in `asia-south1` (already done — `ksp-saathi-2026`)
- [ ] Enable Vertex AI API: `gcloud services enable aiplatform.googleapis.com`
- [ ] Service account with `roles/aiplatform.user` + `roles/storage.objectAdmin`
- [ ] gcloud CLI installed and authed: `gcloud auth application-default login`
- [ ] Python deps: `pip install google-cloud-aiplatform google-cloud-bigquery pandas`

## Step 1 — Prepare the training data (15 min)

Vertex Forecasting expects a **long-format** table with one row per (series, timestamp). Reuse `data/prep_forecast_data.py` — it already emits the right shape from our raw FIR exports.

**Schema:**

| column | type | role |
|--------|------|------|
| `date` | DATE | time_column |
| `series_id` | STRING | time_series_identifier_column |
| `count` | INTEGER | target_column |
| `station` | STRING | covariate (categorical) |
| `crime_type` | STRING | covariate (categorical) |
| `is_weekend` | BOOL | covariate (known at forecast time) |
| `is_festival` | BOOL | covariate (known at forecast time) |

**Example row:**
```csv
date,series_id,count,station,crime_type,is_weekend,is_festival
2025-11-04,indiranagar__vehicle_theft,3,indiranagar,vehicle_theft,false,false
```

Minimum 1000 rows per series is recommended; pad sparse crime types with zero-fill rather than dropping them.

## Step 2 — Upload to GCS or BigQuery (10 min)

**Option A — BigQuery (preferred, faster for retraining):**
```bash
bq mk --dataset --location=asia-south1 ksp-saathi-2026:crime
bq load --source_format=CSV --autodetect \
  ksp-saathi-2026:crime.daily_counts ./forecast_input.csv
```

**Option B — GCS (simpler one-shot):**
```bash
gsutil mb -l asia-south1 gs://ksp-saathi-forecast-data
gsutil cp ./forecast_input.csv gs://ksp-saathi-forecast-data/
```

## Step 3 — Train via the Console UI (easiest, ~2 hours)

1. Open `https://console.cloud.google.com/vertex-ai/datasets` (confirm region = `asia-south1` in the header).
2. **Create Dataset** → **Tabular** → **Forecasting** → name `ksp-crime-forecasting` → point at your BQ table or GCS file.
3. **Train New Model** → AutoML.
4. Set: **target_column** = `count`, **time_column** = `date`, **series_identifier** = `series_id`, **forecast_horizon** = `7`, **data_granularity** = `daily`, **context_window** = `30`.
5. Mark `is_weekend`, `is_festival` as **available at forecast** (we know future weekends/festivals). Mark `count` as **unavailable at forecast**.
6. Optimization objective: **minimize RMSE**. Training budget: **1 node-hour** (~₹500, fits free credit).
7. Click train. Walk away for 2 hours.

## Step 4 — Train via the Python SDK (alternative — version-controlled, reproducible)

```python
from google.cloud import aiplatform
aiplatform.init(project="ksp-saathi-2026", location="asia-south1")

dataset = aiplatform.TimeSeriesDataset.create(
    display_name="ksp-crime-forecasting",
    bq_source="bq://ksp-saathi-2026.crime.daily_counts",
)

job = aiplatform.AutoMLForecastingTrainingJob(
    display_name="ksp-forecast-7day",
    optimization_objective="minimize-rmse",
)

model = job.run(
    dataset=dataset,
    target_column="count",
    time_column="date",
    time_series_identifier_column="series_id",
    forecast_horizon=7,
    context_window=30,
    data_granularity_unit="day",
    data_granularity_count=1,
    available_at_forecast_columns=["date", "is_weekend", "is_festival"],
    unavailable_at_forecast_columns=["count"],
    budget_milli_node_hours=1000,  # ~1 node-hour
)
print("Model resource name:", model.resource_name)
```

## Step 5 — Deploy and call the prediction endpoint

```python
endpoint = model.deploy(machine_type="n1-standard-2", min_replica_count=1)

instances = [{
    "date": "2026-06-17",
    "series_id": "indiranagar__vehicle_theft",
    "station": "indiranagar",
    "crime_type": "vehicle_theft",
    "is_weekend": False,
    "is_festival": False,
}]
prediction = endpoint.predict(instances=instances)
# prediction.predictions[0] → {"value": 2.7, "lower_bound": 1.1, "upper_bound": 4.8}
```

**Remember to undeploy when idle** — endpoints bill hourly:
`endpoint.undeploy_all()`.

## Step 6 — Integrate into our Catalyst Function

```python
# catalyst/functions/forecast/handler.py
from google.cloud import aiplatform
import os

ENDPOINT_ID = os.environ["VERTEX_ENDPOINT_ID"]
endpoint = aiplatform.Endpoint(ENDPOINT_ID)

def handler(event, context):
    station = event["station"]
    crime_type = event["crime_type"]
    instances = build_7day_window(station, crime_type)  # helper in utils.py
    preds = endpoint.predict(instances=instances).predictions
    return {"forecast": preds, "series_id": f"{station}__{crime_type}"}
```

Store the endpoint ID + service account JSON as Catalyst environment secrets.

## Cost estimate

- **Training:** ~₹500 one-time (covered by free trial)
- **Endpoint hosting:** ~₹40/hour while deployed — **undeploy between demos**
- **Prediction:** ~₹0.01 per call (negligible at hackathon volume)
- **BigQuery + GCS storage:** <₹50/month

## When NOT to bother

- Catalyst Zia AutoML passes Week 0 validation
- A simpler baseline (7-day moving average + day-of-week seasonality) lands within 10% of Vertex on our holdout
- We're <72 hours from demo — operational risk of debugging Vertex auth at 2am isn't worth it

## Validation smoke test

After deploy, predict 7 days for `indiranagar__vehicle_theft`. Confirm: (1) all 7 values returned, (2) values are non-negative integers or near-integers, (3) lower_bound ≤ point estimate ≤ upper_bound, (4) values are within historical min/max range. If any check fails, your `series_id` or covariate schema is misaligned with training.

## References

- https://cloud.google.com/vertex-ai/docs/tabular-data/forecasting/overview
- https://cloud.google.com/python/docs/reference/aiplatform/latest
- Internal: `data/prep_forecast_data.py`, `docs/zia-automl-validation.md`
