"""Neo4j AuraDB driver singleton for the KSP Saathi criminal-network graph.

Catalyst has no graph database, so Neo4j AuraDB Free hosts the
(Person)-[KNOWS|CO_ACCUSED_IN|CALLS|LIVES_NEAR]-(Person) and
(Person)-[ACCUSED_IN]->(FIR) schema. See design.md §5.5.

Env vars:
    NEO4J_URI       e.g. "neo4j+s://xxxxxxxx.databases.neo4j.io"
    NEO4J_USERNAME  e.g. "neo4j"
    NEO4J_PASSWORD  the AuraDB instance password
    NEO4J_DATABASE  optional — defaults to "neo4j"

One driver per process — the Bolt driver pools its own connections.
Always close via `close_driver()` in a function lifecycle hook if the
runtime supports it; Catalyst Functions will GC it on cold-stop.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, Driver, Session
    _NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore[assignment]
    Driver = Any  # type: ignore[assignment,misc]
    Session = Any  # type: ignore[assignment,misc]
    _NEO4J_AVAILABLE = False


class Neo4jClientError(RuntimeError):
    """Raised when the Neo4j driver is unavailable or misconfigured."""


_driver: "Driver | None" = None


def _require_sdk() -> None:
    if not _NEO4J_AVAILABLE:
        raise Neo4jClientError(
            "neo4j driver is not installed. Add `neo4j>=5.18.0` to requirements.txt."
        )


def _config() -> tuple[str, str, str, str]:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not password:
        raise Neo4jClientError(
            "NEO4J_URI and NEO4J_PASSWORD must be set. See .env.example."
        )
    return uri, user, password, database


def get_driver() -> "Driver":
    """Return the singleton Bolt driver, creating it on first call."""
    global _driver
    if _driver is None:
        _require_sdk()
        uri, user, password, _ = _config()
        _driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=int(os.getenv("NEO4J_MAX_POOL", "20")),
            connection_acquisition_timeout=float(
                os.getenv("NEO4J_ACQUIRE_TIMEOUT_S", "30")
            ),
        )
        logger.info("Neo4j driver initialised (uri=%s)", uri)
    return _driver


def get_session(database: str | None = None) -> "Session":
    """Open a Neo4j session against the configured database.

    Callers should use as a context manager:

        with get_session() as s:
            res = s.run("MATCH (p:Person) RETURN count(p) AS n")
    """
    _, _, _, default_db = _config()
    return get_driver().session(database=database or default_db)


def run_query(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    """Run a read query and return rows as a list of plain dicts."""
    with get_session(database=database) as session:
        result = session.run(cypher, parameters or {})
        return [record.data() for record in result]


def run_write(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    """Run a write query inside a managed transaction."""
    with get_session(database=database) as session:
        def _tx(tx, cy: str, p: dict[str, Any]) -> list[dict[str, Any]]:
            return [r.data() for r in tx.run(cy, p)]
        return session.execute_write(_tx, cypher, parameters or {})


def batch_write(
    statements: Iterable[tuple[str, dict[str, Any]]],
    *,
    database: str | None = None,
) -> None:
    """Run several writes in a single transaction (ingest helper)."""
    with get_session(database=database) as session:
        def _tx(tx):
            for cy, params in statements:
                tx.run(cy, params)
        session.execute_write(_tx)


def close_driver() -> None:
    """Close the driver — call on function shutdown."""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j driver close failed: %s", exc)
        _driver = None


def healthcheck() -> bool:
    """Lightweight ping for ops dashboards."""
    try:
        rows = run_query("RETURN 1 AS ok")
        return bool(rows and rows[0].get("ok") == 1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j healthcheck failed: %s", exc)
        return False
