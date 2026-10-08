"""Analysis pipeline orchestrator (§3F).

Runs as a FastAPI ``BackgroundTask`` scheduled by ``POST /v1/decisions/analyze``.
For each of the five steps in ``STEP_ORDER`` it:

    1. sets ``pipeline_step`` and publishes ``{step, status: "running"}``,
    2. runs the step implementation (Phase 5's, or the placeholder — see
       ``steps.resolve_step``),
    3. writes the returned columns and publishes ``{step, status: "done", ...}``.

then marks the decision ``complete`` and publishes a final ``complete`` event.
Any exception fails the decision: ``status='failed'`` + ``error_message``, a
``failed`` event so connected streams stop waiting, and a Sentry capture.

Everything touching ``decisions`` goes through ``db.rls_transaction(user_id)``
— the table is RLS-protected (§2E) and there is no request context out here, so
the GUC must be set explicitly on every transaction.

Why the terminal event always fires: an SSE client has no other way to learn the
run ended. Both the success and failure paths publish before returning, and the
failure path is itself wrapped so a broken publish still leaves the row failed
rather than stuck in ``processing``.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

import sentry_sdk
import structlog

from ..db import Database, RedisService
from ..state import get_database, get_redis
from .events import STEP_ORDER, publish_event
from .steps import PipelineContext, resolve_step

logger = structlog.get_logger(__name__)

# Columns the orchestrator itself owns; a step may not overwrite them.
_RESERVED_COLUMNS = frozenset(
    {"decision_id", "user_id", "status", "pipeline_step", "error_message", "completed_at"}
)

# ``decisions`` columns declared JSONB in migration 0003 — these are sent as a
# JSON string with an explicit ``::jsonb`` cast rather than relying on asyncpg
# to infer a type for a Python dict.
_JSONB_COLUMNS = frozenset({"explainer_output", "debate_transcript", "simulation_curves", "portfolio_context",
                            "comment_facts"})


def _bind(value: Any) -> Any:
    """Adapt a Python value to something asyncpg will bind for a NUMERIC/JSONB column."""
    if isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, default=str)
    if isinstance(value, float):
        # NUMERIC columns want exact values; go through str to avoid binary float noise.
        return Decimal(str(value))
    return value


async def _apply_updates(
    db: Database, decision_id: str, user_id: str, updates: dict[str, Any]
) -> None:
    """UPDATE ``decisions`` with a step's columns inside one RLS transaction."""
    if not updates:
        return
    illegal = _RESERVED_COLUMNS & updates.keys()
    if illegal:
        raise ValueError(f"step tried to write orchestrator-owned columns: {sorted(illegal)}")

    assignments: list[str] = []
    args: list[Any] = []
    for column, value in updates.items():
        args.append(_bind(value))
        cast = "::jsonb" if column in _JSONB_COLUMNS else ""
        assignments.append(f"{column} = ${len(args)}{cast}")

    args.append(decision_id)
    query = (
        f"UPDATE decisions SET {', '.join(assignments)} WHERE decision_id = ${len(args)}"
    )
    async with db.rls_transaction(user_id) as conn:
        await conn.execute(query, *args)


async def _set_status(
    db: Database,
    decision_id: str,
    user_id: str,
    status: str,
    pipeline_step: Optional[str],
    *,
    error_message: Optional[str] = None,
    completed: bool = False,
) -> None:
    async with db.rls_transaction(user_id) as conn:
        await conn.execute(
            """
            UPDATE decisions
               SET status = $1,
                   pipeline_step = $2,
                   error_message = $3,
                   completed_at = CASE WHEN $4 THEN NOW() ELSE completed_at END
             WHERE decision_id = $5
            """,
            status,
            pipeline_step,
            error_message,
            completed,
            decision_id,
        )


async def _load_decision(db: Database, decision_id: str, user_id: str) -> Optional[dict[str, Any]]:
    async with db.rls_transaction(user_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM decisions WHERE decision_id = $1", decision_id
        )
    if row is None:
        return None
    decision = dict(row)
    # asyncpg returns JSONB as text (no codec is registered); decode so a later
    # step can read what an earlier one wrote, e.g. 5C merging 5A's SHAP block.
    for column in _JSONB_COLUMNS:
        value = decision.get(column)
        if isinstance(value, str):
            try:
                decision[column] = json.loads(value)
            except ValueError:
                pass
    return decision


async def run_analysis_pipeline(
    decision_id: str,
    user_id: str,
    db: Optional[Database] = None,
    redis: Optional[RedisService] = None,
) -> None:
    """Run every step for one decision, publishing SSE events as it goes.

    ``db``/``redis`` default to the process singletons set up by the lifespan —
    they are parameters only so tests can drive the pipeline directly.
    """
    db = db or get_database()
    redis = redis or get_redis()
    decision_id = str(decision_id)
    user_id = str(user_id)
    log = logger.bind(decision_id=decision_id, user_id=user_id)

    try:
        for step_name in STEP_ORDER:
            await _set_status(db, decision_id, user_id, "processing", step_name)
            await publish_event(redis, decision_id, {"step": step_name, "status": "running"})

            # Reload before each step so it sees the previous steps' writes
            # (the explanation step reads bias_detected, the debate step reads
            # the explanation's opportunity cost, ...).
            decision = await _load_decision(db, decision_id, user_id)
            if decision is None:
                raise LookupError(f"decision {decision_id} not found for user {user_id}")

            ctx = PipelineContext(
                decision_id=decision_id,
                user_id=user_id,
                decision=decision,
                db=db,
                redis=redis,
            )
            result = await resolve_step(step_name)(ctx)
            await _apply_updates(db, decision_id, user_id, result.updates)
            await publish_event(
                redis,
                decision_id,
                {"step": step_name, "status": "done", **result.event},
            )

        await _set_status(db, decision_id, user_id, "complete", None, completed=True)
        await publish_event(redis, decision_id, {"step": "complete", "status": "done"})
        log.info("pipeline_complete")

    except Exception as exc:  # noqa: BLE001 — any step failure fails the decision
        sentry_sdk.capture_exception(exc)
        log.error("pipeline_failed", error=str(exc), exc_info=exc)
        # Best-effort: the row must not be left in 'processing', and any
        # connected stream must be told to stop waiting.
        try:
            await _set_status(
                db, decision_id, user_id, "failed", None, error_message=str(exc)[:500]
            )
        finally:
            await publish_event(
                redis, decision_id, {"step": "failed", "status": "error", "error": str(exc)[:500]}
            )
