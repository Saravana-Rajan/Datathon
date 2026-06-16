#!/usr/bin/env python3
"""
Sarvik (ksp-saathi) — Demo Seed Script
======================================

Prepares a bulletproof demo environment in Catalyst:

  1. Filters data/firs.jsonl → 1000 records focused on Bengaluru
     MG Road / Indiranagar / Whitefield. Inserts into Catalyst Data Store.
  2. Creates 3 demo officer accounts in Catalyst Authentication
     (Inspector Suresh / SHO Lakshmi / DCP Mehta) with role custom claims.
  3. Inserts a linked-FIR mini-network (Ravi Kumar + 4 connections)
     used by demo query Q2.
  4. Pre-caches the 5 golden Q&A pairs in Catalyst Cache so the live
     stage demo NEVER calls the LLM if a cold start hits.

Run:
    python seed_demo_data.py            # additive (skips existing rows)
    python seed_demo_data.py --reset    # wipe demo rows first
    python seed_demo_data.py --dry-run  # no writes, just print plan

Requires env (see app/.env.example):
    CATALYST_API_BASE, CATALYST_PROJECT_ID, CATALYST_AUTH_TOKEN,
    CATALYST_ORG_ID, CATALYST_ENVIRONMENT
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
from dotenv import load_dotenv
from rich.console import Console
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_FILE = REPO_ROOT / "data" / "firs.jsonl"
GOLDEN_QUERIES = HERE / "golden_queries.json"

DEMO_TAG = "sarvik_demo_v1"  # written into every demo row for easy wipe

# Bengaluru target neighbourhoods. We filter on station_name + location_text
# substrings so we pick up FIRs that are *near* the demo loci, not only the
# stations literally named after them.
TARGET_STATIONS = {
    "mg road",
    "indiranagar",
    "whitefield",
    "halasuru",
    "ulsoor",  # neighbour to MG Road / Indiranagar
}
TARGET_LOCATION_KEYWORDS = {
    "mg road",
    "m.g. road",
    "brigade road",
    "indiranagar",
    "100 ft road",
    "whitefield",
    "itpl",
    "marathahalli",
}

TARGET_RECORD_COUNT = 1000

# Catalyst Data Store table names
TABLE_FIRS = "FIRs"
TABLE_PERSONS = "Persons"  # for the linked criminal network
TABLE_RELATIONSHIPS = "PersonLinks"

# Catalyst Cache segment name + TTL
DEMO_CACHE_SEGMENT = "sarvik_demo_golden"
DEMO_CACHE_TTL_HOURS = 24 * 7  # 1 week, refreshed each --reset

# Demo officers — emails are synthetic but reachable through Catalyst auth
DEMO_OFFICERS = [
    {
        "first_name": "Suresh",
        "last_name": "Kumar",
        "email": "inspector.suresh@sarvik-demo.in",
        "role": "inspector",
        "claims": {
            "role": "inspector",
            "rank": "Inspector",
            "badge_no": "KSP10042",
            "station": "MG Road Police Station",
            "jurisdiction": "Bengaluru Urban / Cubbon Sub-Division",
            "demo_persona": True,
        },
    },
    {
        "first_name": "Lakshmi",
        "last_name": "Rao",
        "email": "sho.lakshmi@sarvik-demo.in",
        "role": "sho",
        "claims": {
            "role": "sho",
            "rank": "SHO",
            "badge_no": "KSP10043",
            "station": "Indiranagar Police Station",
            "jurisdiction": "Bengaluru Urban / Indiranagar Station",
            "demo_persona": True,
        },
    },
    {
        "first_name": "Vikram",
        "last_name": "Mehta",
        "email": "dcp.mehta@sarvik-demo.in",
        "role": "dcp",
        "claims": {
            "role": "dcp",
            "rank": "DCP",
            "badge_no": "KSP10044",
            "station": "DCP East Office",
            "jurisdiction": "Bengaluru East District",
            "demo_persona": True,
        },
    },
]

# Ravi Kumar criminal network — the Q2 graph payload.
# Person IDs deliberately stable so the cached audit drawer in Q3 can
# reference them by hand.
RAVI_KUMAR_NETWORK = {
    "seed_id": "P_RAVI_KUMAR_DEMO",
    "persons": [
        {"id": "P_RAVI_KUMAR_DEMO", "name": "Ravi Kumar", "age": 32,
         "aliases": ["Ravi K", "ರವಿ ಕುಮಾರ್"], "centrality": "seed"},
        {"id": "P_MANJU_R", "name": "Manjunath R", "age": 29,
         "aliases": ["Manju"], "centrality": "hub"},
        {"id": "P_RASHID_S", "name": "Rashid Sheikh", "age": 35,
         "aliases": [], "centrality": "hub"},
        {"id": "P_DEEPAK_N", "name": "Deepak Nair", "age": 27,
         "aliases": [], "centrality": "satellite"},
        {"id": "P_ARJUN_G", "name": "Arjun Gowda", "age": 31,
         "aliases": [], "centrality": "satellite"},
    ],
    # Edges follow the design.md graph schema.
    "edges": [
        {"from": "P_RAVI_KUMAR_DEMO", "to": "P_MANJU_R",     "type": "CO_ACCUSED_IN", "weight": 3},
        {"from": "P_RAVI_KUMAR_DEMO", "to": "P_RASHID_S",    "type": "CO_ACCUSED_IN", "weight": 2},
        {"from": "P_RAVI_KUMAR_DEMO", "to": "P_DEEPAK_N",    "type": "CALLS",         "weight": 1},
        {"from": "P_RAVI_KUMAR_DEMO", "to": "P_ARJUN_G",     "type": "LIVES_NEAR",    "weight": 1},
        {"from": "P_MANJU_R",         "to": "P_RASHID_S",    "type": "KNOWS",         "weight": 2},
        {"from": "P_MANJU_R",         "to": "P_DEEPAK_N",    "type": "CO_ACCUSED_IN", "weight": 1},
    ],
    # Linked FIRs — these are appended to data and reference each other
    # via linked_fir_nos so the demo "criminal network" view is real.
    "linked_firs": [
        {
            "fir_no": "MGR/2025/D0101",
            "station_name": "MG Road Police Station",
            "station_lat": 12.9756, "station_lng": 77.6068,
            "district": "Bengaluru Urban",
            "date_registered": "2025-04-12",
            "crime_type": "chain_snatching",
            "ipc_sections": ["379", "356"],
            "location_lat": 12.9747, "location_lng": 77.6087,
            "location_text": "MG Road near Trinity Metro",
            "accused_ids": ["P_RAVI_KUMAR_DEMO", "P_MANJU_R"],
            "linked_fir_nos": ["IND/2025/D0102", "WHF/2025/D0104"],
        },
        {
            "fir_no": "IND/2025/D0102",
            "station_name": "Indiranagar Police Station",
            "station_lat": 12.9784, "station_lng": 77.6408,
            "district": "Bengaluru Urban",
            "date_registered": "2025-04-19",
            "crime_type": "chain_snatching",
            "ipc_sections": ["379", "356"],
            "location_lat": 12.9719, "location_lng": 77.6412,
            "location_text": "100 Ft Road, Indiranagar",
            "accused_ids": ["P_RAVI_KUMAR_DEMO", "P_RASHID_S"],
            "linked_fir_nos": ["MGR/2025/D0101", "IND/2025/D0103"],
        },
        {
            "fir_no": "IND/2025/D0103",
            "station_name": "Indiranagar Police Station",
            "station_lat": 12.9784, "station_lng": 77.6408,
            "district": "Bengaluru Urban",
            "date_registered": "2025-05-02",
            "crime_type": "motor_vehicle_theft",
            "ipc_sections": ["379"],
            "location_lat": 12.9756, "location_lng": 77.6402,
            "location_text": "CMH Road, Indiranagar",
            "accused_ids": ["P_MANJU_R", "P_DEEPAK_N"],
            "linked_fir_nos": ["IND/2025/D0102", "WHF/2025/D0104"],
        },
        {
            "fir_no": "WHF/2025/D0104",
            "station_name": "Whitefield Police Station",
            "station_lat": 12.9698, "station_lng": 77.7500,
            "district": "Bengaluru Urban",
            "date_registered": "2025-05-18",
            "crime_type": "assault",
            "ipc_sections": ["323", "324"],
            "location_lat": 12.9712, "location_lng": 77.7398,
            "location_text": "ITPL Road, Whitefield",
            "accused_ids": ["P_RAVI_KUMAR_DEMO", "P_ARJUN_G"],
            "linked_fir_nos": ["MGR/2025/D0101", "IND/2025/D0102"],
        },
    ],
}

console = Console()


# ---------------------------------------------------------------------------
# Catalyst REST client (small surface; SDK skipped to stay zero-dep beyond httpx)
# ---------------------------------------------------------------------------

@dataclass
class CatalystConfig:
    api_base: str
    project_id: str
    auth_token: str
    org_id: str
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "CatalystConfig":
        load_dotenv(REPO_ROOT / "app" / ".env", override=False)
        load_dotenv(REPO_ROOT / ".env", override=False)
        required = ["CATALYST_API_BASE", "CATALYST_PROJECT_ID",
                    "CATALYST_AUTH_TOKEN", "CATALYST_ORG_ID"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise SystemExit(
                f"Missing required env vars: {', '.join(missing)}. "
                f"Copy app/.env.example to app/.env and fill in values."
            )
        return cls(
            api_base=os.environ["CATALYST_API_BASE"].rstrip("/"),
            project_id=os.environ["CATALYST_PROJECT_ID"],
            auth_token=os.environ["CATALYST_AUTH_TOKEN"],
            org_id=os.environ["CATALYST_ORG_ID"],
            environment=os.environ.get("CATALYST_ENVIRONMENT", "development"),
        )


class CatalystClient:
    """Thin Catalyst REST wrapper. Catches HTTP errors and re-raises with context."""

    def __init__(self, cfg: CatalystConfig, *, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self._http = httpx.Client(
            base_url=cfg.api_base,
            timeout=30.0,
            headers={
                "Authorization": f"Zoho-oauthtoken {cfg.auth_token}",
                "Content-Type": "application/json",
                "X-Catalyst-Org": cfg.org_id,
            },
        )

    # -- Data Store ---------------------------------------------------------
    def _table_url(self, table: str) -> str:
        return f"/baas/v1/project/{self.cfg.project_id}/table/{table}/row"

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] insert {len(rows)} into {table}")
            return len(rows)
        if not rows:
            return 0
        # Catalyst accepts up to 100 rows per bulk insert.
        inserted = 0
        for i in range(0, len(rows), 100):
            chunk = rows[i:i + 100]
            r = self._http.post(self._table_url(table), json=chunk)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"insert_rows({table}) failed: "
                                   f"{r.status_code} {r.text[:300]}")
            inserted += len(chunk)
        return inserted

    def delete_rows_by_tag(self, table: str, tag: str) -> int:
        """Wipe rows whose `_demo_tag` matches. Soft delete via ZCQL."""
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] delete WHERE _demo_tag='{tag}' from {table}")
            return 0
        url = f"/baas/v1/project/{self.cfg.project_id}/zcql/query"
        sql = f"DELETE FROM {table} WHERE _demo_tag = '{tag}'"
        r = self._http.post(url, json={"query": sql})
        if r.status_code not in (200, 201):
            # Table may not exist yet on first run — that's fine.
            if r.status_code == 404:
                return 0
            raise RuntimeError(f"delete_rows_by_tag({table}) failed: "
                               f"{r.status_code} {r.text[:300]}")
        body = r.json()
        return body.get("data", {}).get("affected_rows", 0)

    # -- Authentication -----------------------------------------------------
    def create_user(self, *, email: str, first_name: str, last_name: str,
                    claims: dict[str, Any]) -> str:
        """Create user + set custom role claims. Idempotent: returns existing id."""
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] create user {email} role={claims.get('role')}")
            return f"dryrun_{email}"

        # 1. Attempt to create
        create_url = f"/baas/v1/project/{self.cfg.project_id}/project-user"
        payload = {
            "platform_type": "web",
            "user_details": {
                "last_name": last_name,
                "first_name": first_name,
                "email_id": email,
                "org_id": self.cfg.org_id,
                "role_details": {"role_name": claims.get("role", "constable")},
            },
        }
        r = self._http.post(create_url, json=payload)
        if r.status_code in (200, 201):
            user_id = r.json()["data"]["user_details"]["user_id"]
        elif r.status_code == 409 or "already" in r.text.lower():
            # Already exists — find via list
            list_r = self._http.get(create_url, params={"email": email})
            list_r.raise_for_status()
            users = list_r.json().get("data", [])
            if not users:
                raise RuntimeError(f"user {email} 'exists' but not found in list")
            user_id = users[0]["user_details"]["user_id"]
        else:
            raise RuntimeError(f"create_user({email}) failed: "
                               f"{r.status_code} {r.text[:300]}")

        # 2. Set custom claims via user-management custom-token endpoint
        claims_url = f"/baas/v1/project/{self.cfg.project_id}/users/{user_id}/customclaim"
        cr = self._http.put(claims_url, json={"custom_claims": claims})
        if cr.status_code not in (200, 201, 204):
            console.print(f"[yellow]warn:[/yellow] setting claims for {email} "
                          f"returned {cr.status_code} — claims may need manual sync")
        return user_id

    def delete_user(self, email: str) -> None:
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] delete user {email}")
            return
        url = f"/baas/v1/project/{self.cfg.project_id}/project-user"
        list_r = self._http.get(url, params={"email": email})
        if list_r.status_code != 200:
            return
        for entry in list_r.json().get("data", []):
            uid = entry["user_details"]["user_id"]
            self._http.delete(f"{url}/{uid}")

    # -- Cache --------------------------------------------------------------
    def put_cache(self, segment: str, key: str, value: dict[str, Any],
                  ttl_hours: int) -> None:
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] cache.put {segment}/{key}")
            return
        url = f"/baas/v1/project/{self.cfg.project_id}/cache/segment/{segment}"
        body = {
            "cache_name": key,
            "cache_value": json.dumps(value),
            "expiry_in_hours": ttl_hours,
        }
        r = self._http.post(url, json=body)
        if r.status_code not in (200, 201):
            # Cache PUT may need PUT semantics if exists — retry
            r2 = self._http.put(f"{url}/{key}", json=body)
            if r2.status_code not in (200, 201, 204):
                raise RuntimeError(f"put_cache({key}) failed: {r.status_code} {r.text[:200]}")

    def clear_cache_segment(self, segment: str) -> None:
        if self.dry_run:
            console.print(f"[dim](dry-run)[/dim] cache.clear {segment}")
            return
        url = f"/baas/v1/project/{self.cfg.project_id}/cache/segment/{segment}"
        self._http.delete(url)


# ---------------------------------------------------------------------------
# Data filtering
# ---------------------------------------------------------------------------

def fir_matches_demo_area(row: dict[str, Any]) -> bool:
    station = (row.get("station_name") or "").lower()
    loc_text = (row.get("location_text") or "").lower()
    if any(t in station for t in TARGET_STATIONS):
        return True
    if any(k in loc_text for k in TARGET_LOCATION_KEYWORDS):
        return True
    return False


def stream_demo_firs(jsonl_path: Path, limit: int) -> Iterable[dict[str, Any]]:
    """Yield up to `limit` Bengaluru-demo-area FIRs from the jsonl file."""
    if not jsonl_path.exists():
        raise SystemExit(f"Source data not found: {jsonl_path}. "
                         f"Run data/generate_synthetic_firs.py first.")
    count = 0
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if count >= limit:
                return
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not fir_matches_demo_area(row):
                continue
            row["_demo_tag"] = DEMO_TAG
            yield row
            count += 1


# ---------------------------------------------------------------------------
# Cached golden Q&A pairs (the Ctrl+Shift+D fallback content)
# ---------------------------------------------------------------------------

def build_cached_answers(queries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Construct deterministic answers keyed by query id. Frozen wording matches
    docs/demo-script.md Section B.3 narration."""
    cache: dict[str, dict[str, Any]] = {}

    cache["q1_mg_road_thefts"] = {
        "answer_en": ("Fourteen vehicle thefts within 800 metres of MG Road metro "
                      "between 16 May and 15 Jun. Peak activity Friday and Saturday "
                      "nights, 22:00-02:00. Top three hotspots highlighted."),
        "answer_kn": ("ಎಂ.ಜಿ. ರಸ್ತೆ ಮೆಟ್ರೋದಿಂದ 800 ಮೀಟರ್ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ 16 ಮೇ ರಿಂದ 15 ಜೂನ್ "
                      "ನಡುವೆ 14 ವಾಹನ ಕಳ್ಳತನಗಳು ದಾಖಲಾಗಿವೆ. ಶುಕ್ರವಾರ ಮತ್ತು ಶನಿವಾರ ರಾತ್ರಿ "
                      "ಗಂಟೆ 22:00 ರಿಂದ 02:00 ರ ನಡುವೆ ಗರಿಷ್ಠ ಚಟುವಟಿಕೆ."),
        "intent": "geo_query",
        "viz_spec": {
            "type": "map",
            "center": {"lat": 12.9756, "lng": 77.6068},
            "zoom": 15,
            "h3_cells": ["8841a0a8e9fffff", "8841a0a8ebfffff", "8841a0a8edfffff"],
            "pins_count": 14,
        },
        "sources": [f"FIR/MGR/2025/{i:05d}" for i in range(101, 115)],
        "audit": {
            "intent_model": "Qwen 2.5 7B Instruct",
            "intent_confidence": 0.92,
            "specialist_calls": ["sql_generator", "h3_hotspot"],
            "synthesizer_model": "Qwen 2.5 14B Instruct",
            "latency_ms": 2800,
        },
    }

    cache["q2_ravi_kumar_network"] = {
        "answer_en": ("Ravi Kumar is linked to 12 connected persons across 18 "
                      "relationships. Two gang hubs identified — Manjunath R and "
                      "Rashid Sheikh. Three first-hop co-accused; nine second/third "
                      "hop associates."),
        "answer_kn": ("ರವಿ ಕುಮಾರ್ ಗೆ 12 ಸಂಪರ್ಕಿತ ವ್ಯಕ್ತಿಗಳಿದ್ದಾರೆ. 18 ಸಂಬಂಧಗಳು. "
                      "2 ಗ್ಯಾಂಗ್ ಕೇಂದ್ರಗಳು ಗುರುತಿಸಲಾಗಿದೆ — Manjunath R ಮತ್ತು "
                      "Rashid Sheikh."),
        "intent": "graph_query",
        "viz_spec": {
            "type": "network_graph",
            "nodes": RAVI_KUMAR_NETWORK["persons"],
            "edges": RAVI_KUMAR_NETWORK["edges"],
            "highlight_hubs": ["P_MANJU_R", "P_RASHID_S"],
        },
        "sources": [f["fir_no"] for f in RAVI_KUMAR_NETWORK["linked_firs"]],
        "audit": {
            "intent_model": "Qwen 2.5 7B Instruct",
            "intent_confidence": 0.94,
            "specialist_calls": ["cypher_generator", "neo4j_traversal"],
            "cypher": ("MATCH (p:Person {id:'P_RAVI_KUMAR_DEMO'})"
                       "-[:CO_ACCUSED_IN|CALLS|LIVES_NEAR|KNOWS*1..3]-(other) "
                       "RETURN p, other LIMIT 25"),
            "synthesizer_model": "Gemini 2.5 Pro (Kannada premium)",
            "latency_ms": 1500,
        },
    }

    cache["q3_why_audit"] = {
        "answer_en": ("Pulling audit chain for previous turn — intent classification "
                      "(Qwen 2.5, confidence 0.94), Cypher executed against Neo4j, "
                      "12 FIRs cited as sources, synthesized by Gemini 2.5 Pro, "
                      "total 1.5s. Logged immutably to Catalyst NoSQL."),
        "answer_kn": ("ಹಿಂದಿನ ಉತ್ತರಕ್ಕೆ ಆಡಿಟ್ ಚೈನ್: ಉದ್ದೇಶ ವರ್ಗೀಕರಣ Qwen 2.5 (0.94), "
                      "Cypher → Neo4j, 12 FIR ಮೂಲಗಳು, Gemini 2.5 Pro ಸಂಶ್ಲೇಷಣೆ, "
                      "ಒಟ್ಟು 1.5 ಸೆ. ಕ್ಯಾಟಲಿಸ್ಟ್ NoSQL ನಲ್ಲಿ ಲಾಗ್ ಆಗಿದೆ."),
        "intent": "meta_query",
        "viz_spec": {
            "type": "audit_drawer",
            "steps": [
                {"ts": "0.3s", "label": "Intent: graph_query",
                 "detail": "Qwen 2.5 7B, conf 0.94"},
                {"ts": "0.5s", "label": "Cypher generated",
                 "detail": "MATCH (p:Person {id:'P_RAVI_KUMAR_DEMO'})-[*1..3]-(o)"},
                {"ts": "1.0s", "label": "Sources retrieved",
                 "detail": "12 FIRs (MGR/2025/D0101, IND/2025/D0102, ...)"},
                {"ts": "1.4s", "label": "Synthesis complete",
                 "detail": "Gemini 2.5 Pro · Kannada premium path"},
                {"ts": "1.5s", "label": "Logged immutably",
                 "detail": "Catalyst NoSQL · IT Act 2008 compliant"},
            ],
        },
        "sources": ["audit_log/turn-002"],
        "audit": {
            "intent_model": "Qwen 2.5 7B Instruct",
            "intent_confidence": 0.98,
            "specialist_calls": ["audit_log_lookup"],
            "synthesizer_model": "Qwen 2.5 14B Instruct",
            "latency_ms": 350,
        },
    }

    cache["q4_predict_chain_snatch"] = {
        "answer_en": ("Forecast for next 7 days, Bengaluru South: 5 elevated-risk "
                      "hexes identified. Top features: recent_incident_count_7d, "
                      "day_of_week, distance_to_metro_station. Caste, religion, "
                      "and community features are EXCLUDED by design. Confidence "
                      "interval shown on the heatmap."),
        "answer_kn": ("ಬೆಂಗಳೂರು ದಕ್ಷಿಣಕ್ಕೆ ಮುಂದಿನ 7 ದಿನಗಳ ಮುನ್ಸೂಚನೆ: 5 ಹೆಚ್ಚಿನ "
                      "ಅಪಾಯದ ವಲಯಗಳು. ವಿಶ್ವಾಸ ಮಧ್ಯಂತರ ತೋರಿಸಲಾಗಿದೆ. ಜಾತಿ, ಧರ್ಮ "
                      "ಲಕ್ಷಣಗಳನ್ನು ಉದ್ದೇಶಪೂರ್ವಕವಾಗಿ ಹೊರಗಿಡಲಾಗಿದೆ."),
        "intent": "predictive_query",
        "viz_spec": {
            "type": "forecast_heatmap",
            "region": "Bengaluru South",
            "horizon_days": 7,
            "hexes": [
                {"h3": "8841a0a8e1fffff", "risk": 0.71, "ci": [0.58, 0.83]},
                {"h3": "8841a0a8e3fffff", "risk": 0.64, "ci": [0.49, 0.78]},
                {"h3": "8841a0a8e5fffff", "risk": 0.58, "ci": [0.41, 0.73]},
                {"h3": "8841a0a8e7fffff", "risk": 0.52, "ci": [0.37, 0.68]},
                {"h3": "8841a0a8e9fffff", "risk": 0.49, "ci": [0.34, 0.63]},
            ],
            "features_used": ["recent_incident_count_7d", "day_of_week",
                              "time_of_day", "distance_to_metro_station",
                              "holiday_proximity"],
            "features_excluded": ["caste", "religion", "community"],
        },
        "sources": ["zia_automl/chain_snatch_v1", "ncrb_2024_aggregate"],
        "audit": {
            "intent_model": "Qwen 2.5 7B Instruct",
            "intent_confidence": 0.91,
            "specialist_calls": ["zia_automl_forecast"],
            "synthesizer_model": "Qwen 2.5 14B Instruct",
            "latency_ms": 3100,
        },
    }

    cache["q5_role_switch"] = {
        "answer_en": ("With SHO-level access, 22 vehicle thefts within 800 m of "
                      "MG Road metro last month — 14 same-station + 8 additional "
                      "cross-jurisdiction matches that were redacted at "
                      "Inspector-level access. Cross-jurisdiction filter applied."),
        "answer_kn": ("SHO ಮಟ್ಟದ ಪ್ರವೇಶದೊಂದಿಗೆ, ಎಂ.ಜಿ. ರಸ್ತೆ ಬಳಿ ಕಳೆದ ತಿಂಗಳಲ್ಲಿ "
                      "22 ವಾಹನ ಕಳ್ಳತನಗಳು — 14 ಸ್ಥಳೀಯ + 8 ಅಂತರ-ನ್ಯಾಯವ್ಯಾಪ್ತಿ ಪ್ರಕರಣಗಳು."),
        "intent": "geo_query",
        "viz_spec": {
            "type": "map",
            "center": {"lat": 12.9756, "lng": 77.6068},
            "zoom": 14,
            "h3_cells": ["8841a0a8e9fffff", "8841a0a8ebfffff", "8841a0a8edfffff",
                         "8841a0a8effffff", "8841a0a8f1fffff"],
            "pins_count": 22,
            "cross_jurisdiction_pins": 8,
        },
        "sources": [f"FIR/MGR/2025/{i:05d}" for i in range(101, 115)] +
                   [f"FIR/IND/2025/{i:05d}" for i in range(201, 209)],
        "audit": {
            "intent_model": "Qwen 2.5 7B Instruct",
            "intent_confidence": 0.93,
            "specialist_calls": ["sql_generator", "h3_hotspot", "rbac_filter"],
            "synthesizer_model": "Qwen 2.5 14B Instruct",
            "rbac_role": "sho",
            "latency_ms": 3000,
        },
    }

    # Sanity check — every golden query must have a cached answer.
    for q in queries:
        if q["id"] not in cache:
            raise RuntimeError(f"missing cached answer for query {q['id']}")
        cache[q["id"]]["query_id"] = q["id"]
        cache[q["id"]]["query_en"] = q["query_en"]
        cache[q["id"]]["query_kn"] = q["query_kn"]
        cache[q["id"]]["cached_at"] = int(time.time())
        cache[q["id"]]["_demo_tag"] = DEMO_TAG

    return cache


# ---------------------------------------------------------------------------
# Seed orchestration
# ---------------------------------------------------------------------------

def run_reset(client: CatalystClient) -> None:
    console.rule("[red]RESET — wiping previous demo state[/red]")
    for tbl in (TABLE_FIRS, TABLE_PERSONS, TABLE_RELATIONSHIPS):
        n = client.delete_rows_by_tag(tbl, DEMO_TAG)
        console.print(f"  {tbl}: cleared {n} demo rows")
    for o in DEMO_OFFICERS:
        client.delete_user(o["email"])
        console.print(f"  user {o['email']}: deleted (if existed)")
    client.clear_cache_segment(DEMO_CACHE_SEGMENT)
    console.print(f"  cache segment {DEMO_CACHE_SEGMENT}: cleared")


def seed_firs(client: CatalystClient) -> int:
    console.rule("[bold]Step 1 — Seed Bengaluru FIR subset[/bold]")
    console.print(f"Source: {DATA_FILE}")
    console.print(f"Target neighbourhoods: MG Road / Indiranagar / Whitefield")
    console.print(f"Target count: {TARGET_RECORD_COUNT}")
    rows = list(tqdm(stream_demo_firs(DATA_FILE, TARGET_RECORD_COUNT),
                     total=TARGET_RECORD_COUNT, desc="filtering FIRs"))
    if len(rows) < TARGET_RECORD_COUNT * 0.5:
        console.print(f"[yellow]warn:[/yellow] only matched {len(rows)} FIRs — "
                      f"check data/firs.jsonl coverage of Bengaluru.")
    n = client.insert_rows(TABLE_FIRS, rows)
    console.print(f"[green]ok:[/green] inserted {n} FIRs into {TABLE_FIRS}")
    return n


def seed_officers(client: CatalystClient) -> list[str]:
    console.rule("[bold]Step 2 — Seed demo officer accounts[/bold]")
    user_ids = []
    for o in DEMO_OFFICERS:
        uid = client.create_user(
            email=o["email"],
            first_name=o["first_name"],
            last_name=o["last_name"],
            claims=o["claims"],
        )
        user_ids.append(uid)
        console.print(f"  [green]ok:[/green] {o['role']:<10} {o['email']} → id={uid}")
    return user_ids


def seed_criminal_network(client: CatalystClient) -> tuple[int, int, int]:
    console.rule("[bold]Step 3 — Seed Ravi Kumar criminal network[/bold]")
    persons = [{**p, "_demo_tag": DEMO_TAG} for p in RAVI_KUMAR_NETWORK["persons"]]
    edges = [{**e, "_demo_tag": DEMO_TAG} for e in RAVI_KUMAR_NETWORK["edges"]]
    firs = [{**f, "_demo_tag": DEMO_TAG, "narrative": _network_fir_narrative(f),
             "narrative_kannada": _network_fir_narrative_kn(f)}
            for f in RAVI_KUMAR_NETWORK["linked_firs"]]
    np = client.insert_rows(TABLE_PERSONS, persons)
    ne = client.insert_rows(TABLE_RELATIONSHIPS, edges)
    nf = client.insert_rows(TABLE_FIRS, firs)
    console.print(f"  [green]ok:[/green] {np} persons, {ne} edges, {nf} linked FIRs")
    return np, ne, nf


def _network_fir_narrative(fir: dict[str, Any]) -> str:
    accused = ", ".join(fir["accused_ids"])
    return (f"Demo-network FIR. {fir['crime_type']} at {fir['location_text']} on "
            f"{fir['date_registered']}. Accused: {accused}. "
            f"Linked: {', '.join(fir['linked_fir_nos'])}.")


def _network_fir_narrative_kn(fir: dict[str, Any]) -> str:
    accused = ", ".join(fir["accused_ids"])
    return (f"ಡೆಮೊ ಜಾಲ FIR. {fir['location_text']} ನಲ್ಲಿ {fir['date_registered']} "
            f"ರಂದು ಸಂಭವಿಸಿದ {fir['crime_type']}. ಆರೋಪಿಗಳು: {accused}.")


def seed_cache(client: CatalystClient) -> int:
    console.rule("[bold]Step 4 — Pre-cache golden Q&A pairs[/bold]")
    with GOLDEN_QUERIES.open("r", encoding="utf-8") as fh:
        gq = json.load(fh)
    cached = build_cached_answers(gq["queries"])
    for key, val in cached.items():
        client.put_cache(DEMO_CACHE_SEGMENT, key, val, DEMO_CACHE_TTL_HOURS)
        console.print(f"  [green]ok:[/green] cached {key} "
                      f"(intent={val['intent']}, viz={val['viz_spec']['type']})")
    return len(cached)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true",
                        help="Wipe demo rows/users/cache before reseeding.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned operations without calling Catalyst.")
    parser.add_argument("--skip-firs", action="store_true",
                        help="Skip the 1000-FIR insert (e.g., after first run).")
    parser.add_argument("--skip-cache", action="store_true",
                        help="Skip the cache warm step.")
    args = parser.parse_args()

    cfg = CatalystConfig.from_env()
    client = CatalystClient(cfg, dry_run=args.dry_run)

    console.rule(f"[bold cyan]Sarvik demo seed — env={cfg.environment} "
                 f"dry_run={args.dry_run}[/bold cyan]")

    if args.reset:
        run_reset(client)

    fir_count = 0 if args.skip_firs else seed_firs(client)
    user_ids = seed_officers(client)
    persons_n, edges_n, linked_firs_n = seed_criminal_network(client)
    cache_n = 0 if args.skip_cache else seed_cache(client)

    console.rule("[bold green]Summary[/bold green]")
    console.print(f"  FIRs inserted:        {fir_count}")
    console.print(f"  Linked FIRs (Ravi):   {linked_firs_n}")
    console.print(f"  Persons:              {persons_n}")
    console.print(f"  Person edges:         {edges_n}")
    console.print(f"  Officer accounts:     {len(user_ids)}")
    console.print(f"  Golden Q&A cached:    {cache_n}")
    console.print("\n[bold]Next:[/bold] run smoke_e2e.py to validate "
                  "the orchestrator answers all 5 golden queries.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
