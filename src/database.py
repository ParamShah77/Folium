"""
GAP 1 – Database Manager
=========================
SQLite-backed persistence layer for the financial decision intelligence system.

Tables
------
  user_profiles       — registered investor profiles
  bias_profiles_live  — running-average bias scores per user
  decisions_live      — individual decision analysis records
  audit_logs          — append-only tamper-evident audit trail (SHA-256)
  market_data_cache   — persisted market context snapshots

All SQL queries use parameterized placeholders — no SQL injection risk.

Database file location: <project_root>/data/financial_intelligence.db

Usage
-----
    from database import DatabaseManager
    db  = DatabaseManager()
    uid = db.register_user({"age": 35, "monthly_income": 80000, ...})
    db.log_decision({...})
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "financial_intelligence.db")


# ═══════════════════════════════════════════════════════════
# DATABASE MANAGER
# ═══════════════════════════════════════════════════════════

class DatabaseManager:
    """
    SQLite-backed manager for users, decisions, bias profiles, and audit logs.

    Thread-safety: Uses `check_same_thread=False` with WAL mode — safe for
    FastAPI's async/sync hybrid (each request serialised at the DB level).
    """

    # ──────────────────────────────────────────
    # INIT & SCHEMA
    # ──────────────────────────────────────────

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:   # guard against empty string (e.g. ":memory:")
            os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,   # allow multi-thread access
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row   # dict-like row access
        self._conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        logger.info("DatabaseManager initialised — %s", db_path)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def _create_tables(self) -> None:
        """Create all tables if they don't already exist (idempotent)."""
        ddl = """
        -- ── User profiles ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id            TEXT PRIMARY KEY,
            age                INTEGER,
            monthly_income     REAL,
            risk_tolerance     REAL,
            investment_horizon INTEGER,
            has_emergency_fund INTEGER DEFAULT 0,
            name               TEXT,
            created_at         TEXT NOT NULL,
            updated_at         TEXT NOT NULL
        );

        -- ── Live bias profiles (running average) ─────────────────────
        CREATE TABLE IF NOT EXISTS bias_profiles_live (
            user_id            TEXT PRIMARY KEY,
            disposition_score  REAL DEFAULT 0.0,
            herd_score         REAL DEFAULT 0.0,
            loss_aversion_score REAL DEFAULT 0.0,
            rational_score     REAL DEFAULT 0.0,
            total_decisions    INTEGER DEFAULT 0,
            last_updated       TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
        );

        -- ── Individual decision records ───────────────────────────────
        CREATE TABLE IF NOT EXISTS decisions_live (
            decision_id        TEXT PRIMARY KEY,
            user_id            TEXT,
            bias_detected      TEXT,
            confidence         REAL,
            recommendation     TEXT,
            risk_score         REAL,
            timestamp          TEXT NOT NULL,
            input_hash         TEXT,
            output_hash        TEXT,
            raw_input          TEXT,   -- JSON blob
            raw_output         TEXT    -- JSON blob
        );

        -- ── Audit logs — APPEND-ONLY, never UPDATE ───────────────────
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id             TEXT PRIMARY KEY,
            decision_id        TEXT,
            input_hash         TEXT NOT NULL,
            output_hash        TEXT NOT NULL,
            explanation_hash   TEXT NOT NULL,
            full_hash          TEXT NOT NULL,
            timestamp          TEXT NOT NULL
        );

        -- ── Market snapshot cache ─────────────────────────────────────
        CREATE TABLE IF NOT EXISTS market_data_cache (
            cache_key          TEXT PRIMARY KEY,
            market_return      REAL,
            market_volatility  REAL,
            crowd_ratio        REAL,
            fetched_at         TEXT NOT NULL
        );
        """
        self._conn.executescript(ddl)
        self._conn.commit()

    # ──────────────────────────────────────────
    # USER MANAGEMENT
    # ──────────────────────────────────────────

    def register_user(self, user_data: dict) -> str:
        """
        Insert a new user profile.

        Parameters
        ----------
        user_data : dict — must contain at minimum: age, monthly_income,
                           risk_tolerance, investment_horizon, has_emergency_fund

        Returns
        -------
        user_id : str   — UUID-based identifier
        """
        user_id = str(uuid.uuid4())
        now     = _now_iso()

        self._conn.execute(
            """
            INSERT INTO user_profiles
                (user_id, age, monthly_income, risk_tolerance,
                 investment_horizon, has_emergency_fund, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                int(user_data.get("age", 30)),
                float(user_data.get("monthly_income", 50_000)),
                float(user_data.get("risk_tolerance", 0.5)),
                int(user_data.get("investment_horizon", 10)),
                int(bool(user_data.get("has_emergency_fund", 0))),
                str(user_data.get("name", "")),
                now,
                now,
            ),
        )

        # Initialise empty bias profile
        self._conn.execute(
            """
            INSERT INTO bias_profiles_live
                (user_id, disposition_score, herd_score,
                 loss_aversion_score, rational_score, total_decisions, last_updated)
            VALUES (?, 0.0, 0.0, 0.0, 0.0, 0, ?)
            """,
            (user_id, now),
        )
        self._conn.commit()
        logger.info("Registered new user: %s", user_id)
        return user_id

    def get_user(self, user_id: str) -> dict | None:
        """
        Fetch a user profile.

        Returns
        -------
        dict with profile columns, or None if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_bias_profile(self, user_id: str) -> dict | None:
        """Return the live bias profile for a user."""
        row = self._conn.execute(
            "SELECT * FROM bias_profiles_live WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_bias_profile(self, user_id: str, new_bias_type: str) -> None:
        """
        Update the running-average bias profile after a new decision.

        Uses an incremental average formula:
            new_avg = ((old_avg * n) + new_val) / (n + 1)
        where new_val = 1.0 for the detected class, 0.0 for others.
        """
        row = self._conn.execute(
            "SELECT * FROM bias_profiles_live WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row is None:
            # Create a blank entry first (defensive)
            now = _now_iso()
            self._conn.execute(
                """
                INSERT INTO bias_profiles_live
                    (user_id, disposition_score, herd_score,
                     loss_aversion_score, rational_score, total_decisions, last_updated)
                VALUES (?, 0.0, 0.0, 0.0, 0.0, 0, ?)
                """,
                (user_id, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM bias_profiles_live WHERE user_id = ?", (user_id,)
            ).fetchone()

        n = int(row["total_decisions"])
        score_map = {
            "disposition"   : "disposition_score",
            "herd"          : "herd_score",
            "loss_aversion" : "loss_aversion_score",
            "rational"      : "rational_score",
        }

        # Compute new running averages
        updates: dict[str, float] = {}
        for bias, col in score_map.items():
            old_avg = float(row[col])
            new_val = 1.0 if new_bias_type == bias else 0.0
            updates[col] = _running_avg(old_avg, new_val, n)

        self._conn.execute(
            """
            UPDATE bias_profiles_live
               SET disposition_score    = ?,
                   herd_score           = ?,
                   loss_aversion_score  = ?,
                   rational_score       = ?,
                   total_decisions      = ?,
                   last_updated         = ?
             WHERE user_id = ?
            """,
            (
                updates["disposition_score"],
                updates["herd_score"],
                updates["loss_aversion_score"],
                updates["rational_score"],
                n + 1,
                _now_iso(),
                user_id,
            ),
        )
        self._conn.commit()

    # ──────────────────────────────────────────
    # DECISION LOGGING
    # ──────────────────────────────────────────

    def log_decision(self, decision_data: dict) -> str:
        """
        Persist a single-decision analysis result.

        Parameters
        ----------
        decision_data : dict — keys: user_id (opt), bias_detected, confidence,
                                recommendation, risk_score, raw_input, raw_output

        Returns
        -------
        decision_id : str — UUID
        """
        decision_id = str(uuid.uuid4())
        now         = _now_iso()

        raw_input  = json.dumps(decision_data.get("raw_input",  {}), default=str)
        raw_output = json.dumps(decision_data.get("raw_output", {}), default=str)

        input_hash  = _sha256(raw_input)
        output_hash = _sha256(raw_output)

        self._conn.execute(
            """
            INSERT INTO decisions_live
                (decision_id, user_id, bias_detected, confidence,
                 recommendation, risk_score, timestamp,
                 input_hash, output_hash, raw_input, raw_output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                decision_data.get("user_id"),
                str(decision_data.get("bias_detected", "")),
                float(decision_data.get("confidence", 0.0)),
                str(decision_data.get("recommendation", "")),
                float(decision_data.get("risk_score", 0.0)),
                now,
                input_hash,
                output_hash,
                raw_input,
                raw_output,
            ),
        )
        self._conn.commit()
        logger.debug("Logged decision %s", decision_id)
        return decision_id

    # ──────────────────────────────────────────
    # AUDIT TRAIL (append-only)
    # ──────────────────────────────────────────

    def append_audit_log(self, audit_data: dict) -> str:
        """
        Append an immutable audit log entry.  This method NEVER updates
        existing rows — only INSERT is used.

        Parameters
        ----------
        audit_data : dict — keys: decision_id, input_hash, output_hash,
                            explanation_hash (all strings)

        Returns
        -------
        log_id : str — UUID of the new audit entry
        """
        log_id      = str(uuid.uuid4())
        now         = _now_iso()
        input_h     = str(audit_data.get("input_hash",       ""))
        output_h    = str(audit_data.get("output_hash",      ""))
        expl_h      = str(audit_data.get("explanation_hash", ""))
        full_h      = _sha256(input_h + output_h + expl_h + now)

        self._conn.execute(
            """
            INSERT INTO audit_logs
                (log_id, decision_id, input_hash, output_hash,
                 explanation_hash, full_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, audit_data.get("decision_id"), input_h, output_h, expl_h, full_h, now),
        )
        self._conn.commit()
        return log_id

    # ──────────────────────────────────────────
    # RETRIEVAL
    # ──────────────────────────────────────────

    def get_user_decision_history(self, user_id: str) -> list[dict]:
        """Return all decisions for a user, newest first."""
        rows = self._conn.execute(
            """
            SELECT decision_id, bias_detected, confidence, recommendation,
                   risk_score, timestamp, input_hash, output_hash
              FROM decisions_live
             WHERE user_id = ?
             ORDER BY timestamp DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_audit_trail(self, decision_id: str) -> dict | None:
        """
        Fetch the audit log for a decision and verify hash integrity.

        Returns
        -------
        dict with all audit fields plus `tamper_detected` bool.
        """
        row = self._conn.execute(
            "SELECT * FROM audit_logs WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if row is None:
            return None

        r = dict(row)
        # Recompute full_hash and compare
        expected = _sha256(
            r["input_hash"] + r["output_hash"] + r["explanation_hash"] + r["timestamp"]
        )
        r["tamper_detected"] = expected != r["full_hash"]
        r["hash_verified"]   = not r["tamper_detected"]
        return r

    # ──────────────────────────────────────────
    # MARKET CACHE
    # ──────────────────────────────────────────

    def cache_market_data(self, cache_key: str, market_data: dict) -> None:
        """Upsert a market snapshot into the cache table."""
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO market_data_cache
                (cache_key, market_return, market_volatility, crowd_ratio, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                market_return      = excluded.market_return,
                market_volatility  = excluded.market_volatility,
                crowd_ratio        = excluded.crowd_ratio,
                fetched_at         = excluded.fetched_at
            """,
            (
                cache_key,
                float(market_data.get("market_return", 0.0)),
                float(market_data.get("market_volatility", 0.0)),
                float(market_data.get("crowd_ratio", 0.5)),
                now,
            ),
        )
        self._conn.commit()

    def get_cached_market_data(self, cache_key: str) -> dict | None:
        """Retrieve a cached market snapshot."""
        row = self._conn.execute(
            "SELECT * FROM market_data_cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _now_iso() -> str:
    """Current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    """Hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _running_avg(old_avg: float, new_val: float, n: int) -> float:
    """Incremental running average: ((old_avg * n) + new_val) / (n + 1)."""
    return round((old_avg * n + new_val) / (n + 1), 6)


# ─────────────────────────────────────────────────────────────
# Module-level singleton (used by api.py)
# ─────────────────────────────────────────────────────────────
_db_instance: DatabaseManager | None = None


def get_db() -> DatabaseManager:
    """Return (or create) the module-level singleton DatabaseManager."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


# ─────────────────────────────────────────────
# Quick smoke test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    db = DatabaseManager(":memory:")    # in-memory DB for testing

    # Register a user
    uid = db.register_user({
        "age": 35, "monthly_income": 80000,
        "risk_tolerance": 0.6, "investment_horizon": 15,
        "has_emergency_fund": 1, "name": "Test User",
    })
    print(f"Registered user: {uid}")
    print(f"Profile: {db.get_user(uid)}")

    # Log a decision
    did = db.log_decision({
        "user_id"       : uid,
        "bias_detected" : "loss_aversion",
        "confidence"    : 0.87,
        "recommendation": "Reduce exposure gradually",
        "risk_score"    : 0.72,
        "raw_input"     : {"market_return": -0.10},
        "raw_output"    : {"bias_type": "loss_aversion"},
    })
    print(f"Logged decision: {did}")

    # Update bias profile
    db.update_bias_profile(uid, "loss_aversion")
    print(f"Bias profile: {db.get_bias_profile(uid)}")

    # Audit log
    dec = db.get_user(uid)  # just for hashes
    log_id = db.append_audit_log({
        "decision_id"     : did,
        "input_hash"      : "abc123",
        "output_hash"     : "def456",
        "explanation_hash": "ghi789",
    })
    trail = db.get_audit_trail(did)
    print(f"Audit trail: {trail}")
    db.close()
