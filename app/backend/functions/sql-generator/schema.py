"""FIR table schema constant injected into the SQL generation prompt.

Kept as a plain Python string (not loaded from disk) so the function bundle
stays small and the schema travels with the generator. When the real CCTNS
schema lands we update this constant in one place — every prompt picks the
change up automatically.

Why a single TABLE? In v1 the FIR record is denormalised intentionally:
  - station + location coordinates are duplicated on the row so geo filters
    stay single-table (no joins required for the common case);
  - complainant / accused / IPC sections are JSON strings — Catalyst Data
    Store has no native JSONB / array type, and synthetic data is generated
    that way (see data/generate_synthetic_firs.py).

Geospatial caveat: Catalyst Data Store has no PostGIS. The "common patterns"
block at the bottom of FIR_SCHEMA explicitly nudges the LLM to emit
bounding-box predicates instead of ST_DWithin/ST_Distance. The safety layer
catches any PostGIS leakage; safety.py rewrites it to a bounding box and
index.py finishes the haversine filter in Python.
"""

from __future__ import annotations

# Canonical list of crime_type values. Generator should constrain the LLM
# output to this set (we surface it in the schema string AND in the prompt).
CRIME_TYPES: tuple[str, ...] = (
    "vehicle_theft",
    "chain_snatching",
    "burglary",
    "robbery",
    "fraud",
    "assault",
    "kidnapping",
    "narcotics",
    "cybercrime",
    "missing_person",
    "accident",
    "public_nuisance",
    "domestic_violence",
    "murder",
    "attempt_to_murder",
)

# Status values the FIR generator emits — kept here so prompt can hint the LLM.
STATUS_VALUES: tuple[str, ...] = (
    "open",
    "under_investigation",
    "chargesheeted",
    "closed",
    "transferred",
)


FIR_SCHEMA: str = """
TABLE firs(
  fir_no TEXT PRIMARY KEY,
  station_name TEXT,
  station_lat DECIMAL, station_lng DECIMAL,
  district TEXT,
  date_registered DATE, time_registered TIME,
  crime_type TEXT,        -- one of: vehicle_theft, chain_snatching, burglary, robbery, fraud, assault, kidnapping, narcotics, cybercrime, missing_person, accident, public_nuisance, domestic_violence, murder, attempt_to_murder
  ipc_sections TEXT,      -- JSON array as string
  location_lat DECIMAL, location_lng DECIMAL,
  location_text TEXT,
  complainant TEXT,       -- JSON object
  accused TEXT,           -- JSON array
  status TEXT,
  narrative TEXT,
  narrative_kannada TEXT
)
Common patterns:
  -- Count by crime type
  SELECT crime_type, COUNT(*) FROM firs WHERE date_registered >= ? GROUP BY crime_type
  -- Geographic bounding box (no PostGIS available)
  SELECT * FROM firs WHERE location_lat BETWEEN ? AND ? AND location_lng BETWEEN ? AND ?
""".strip()


# ---------------------------------------------------------------------------
# Allow-lists used by safety.py — exported here so the schema is the single
# source of truth for "what's a real column / table".
# ---------------------------------------------------------------------------

ALLOWED_TABLES: frozenset[str] = frozenset({"firs"})

ALLOWED_COLUMNS: frozenset[str] = frozenset({
    "fir_no",
    "station_name",
    "station_lat",
    "station_lng",
    "district",
    "date_registered",
    "time_registered",
    "crime_type",
    "ipc_sections",
    "location_lat",
    "location_lng",
    "location_text",
    "complainant",
    "accused",
    "status",
    "narrative",
    "narrative_kannada",
})
