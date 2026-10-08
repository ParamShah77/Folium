"""/v1/decisions/* — async analysis submission + SSE progress stream (§3F).

Endpoints:
    POST /v1/decisions/analyze        202 + decision_id, schedules the pipeline
    GET  /v1/decisions/my             paginated history
    GET  /v1/decisions/stats          per-user aggregates for the dashboard
    GET  /v1/decisions/{id}/result    full row (status included; poll or stream)
    GET  /v1/decisions/{id}/stream    text/event-stream of pipeline progress

Ownership (§3C): the id comes from the path, so every read re-checks it inside
``db.rls_transaction(user.user_id)``. RLS makes another user's row invisible
rather than forbidden, so a miss is a 404 — which is also the right answer for
enumeration resistance. ``POST /batch`` is deliberately not here: it belongs
with the real ML steps in Phase 5.

NOTE: no ``from __future__ import annotations`` in route modules (see
auth/routes.py for the slowapi/PEP 563 body-inference reason).
"""
import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from ...auth.dependencies import get_current_user
from ...config import get_settings
from ...core.events import (
    HEARTBEAT_FRAME,
    STEP_ORDER,
    TERMINAL_STEPS,
    channel,
    event_frame,
    parse_seq,
    parse_step,
    read_backlog,
    sse_frame,
)
from ...core import audit
from ...core.ml_bridge import ensure_src_importable
from ...core.pipeline import run_analysis_pipeline
from ...core.steps import is_stubbed
from ...db import Database, RedisService
from ...errors import AppError
from ...middleware.rate_limiter import DECISIONS_ANALYZE_LIMIT, limiter
from ...models import User
from ...schemas.decisions import DecisionInput, DecisionSubmitResponse
from ...services.market_data import capture_market_context
from ...services.portfolio import decision_context, load_portfolio
from ...services.prices import stock_risk
from ...state import get_db, get_redis_service
from ..serialization import jsonable_row

logger = structlog.get_logger(__name__)
router = APIRouter()

# Columns returned by GET /my — enough for a history list, no heavy JSONB.
_SUMMARY_FIELDS = (
    "decision_id", "symbol", "exchange", "status", "pipeline_step",
    "decision_intent", "holding_quantity", "avg_buy_price", "current_price",
    "unrealized_pnl_pct", "bias_detected", "bias_confidence", "recommendation", "holding_id",
    "portfolio_context",
    "opportunity_cost_inr", "hold_median_20y", "sell_median_20y",
    "error_message", "submitted_at", "completed_at",
)

_MAX_PAGE_SIZE = 100


async def _load_owned_decision(db: Database, decision_id: str, user_id):
    """Fetch a decision through RLS; ``None`` when it is absent or not theirs."""
    async with db.rls_transaction(str(user_id)) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM decisions WHERE decision_id = $1", decision_id
        )
    return row


def _not_found() -> AppError:
    return AppError(
        status_code=404, error="DECISION_NOT_FOUND", message="Decision not found"
    )


def _parse_uuid(decision_id: str) -> str:
    """A malformed id is a 404, not a 500 from Postgres' uuid cast."""
    try:
        return str(uuid.UUID(decision_id))
    except (ValueError, AttributeError, TypeError):
        raise _not_found() from None


# --------------------------------------------------------------------------- #
# POST /v1/decisions/analyze — §3F step 1
# --------------------------------------------------------------------------- #
@router.post("/analyze", status_code=202, response_model=DecisionSubmitResponse)
@limiter.limit(DECISIONS_ANALYZE_LIMIT)
async def analyze_decision(
    request: Request,
    response: Response,  # REQUIRED by @limiter.limit — see the note on the limiter
    payload: DecisionInput,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Insert a ``pending`` decision and hand the work to a background task.

    Returns immediately (202) with the id the client needs to open the stream;
    the pipeline itself takes tens of seconds once Phase 5's debate engine is in
    place, which is the whole reason for the async flow.

    Market context (migration 0008) is captured *here*, at submission, and
    stored on the row, so the pipeline — and any later re-run — sees exactly
    the market the investor was deciding in. A market trend the user stated
    explicitly wins over the one derived from NIFTY's 1-month return.
    """
    market = await capture_market_context()
    market_trend = payload.market_trend or market["market_trend"]

    # Portfolio-aware path: the decision is about one holding, judged against
    # everything else the investor owns.
    symbol, exchange = payload.symbol, payload.exchange
    quantity, avg_price, current_price = (
        payload.holding_quantity, payload.avg_buy_price, payload.current_price,
    )
    unrealized = payload.unrealized_pnl_pct
    holding_id, context = None, None
    if payload.holding_id:
        holding_uuid = _parse_uuid(payload.holding_id)
        async with db.rls_transaction(str(user.user_id)) as conn:
            portfolio = await load_portfolio(conn, str(user.user_id))
        holding = next((h for h in portfolio["holdings"] if h["holding_id"] == holding_uuid), None)
        if holding is None:
            raise AppError(status_code=404, error="HOLDING_NOT_FOUND", message="Holding not found")
        holding_id = holding_uuid
        symbol, exchange = holding["symbol"], holding["exchange"]
        quantity, avg_price = holding["quantity"], holding["avg_buy_price"]
        # Live price when available; otherwise the price the user confirmed.
        current_price = holding["current_price"] or payload.current_price
        unrealized = round(current_price / avg_price - 1, 4)
        context = decision_context(portfolio, {**holding, "value": quantity * current_price})
        # How this one stock moves (simulation v2), measured now and stored so
        # a re-run reproduces it. Unavailable -> the simulation uses the median
        # NIFTY 50 stock and says so.
        if holding["asset_type"] == "equity":
            risk = await stock_risk(symbol, exchange)
            if risk:
                context["stock_risk"] = risk

    async with db.rls_transaction(str(user.user_id)) as conn:
        decision_id = await conn.fetchval(
            """
            INSERT INTO decisions (
                user_id, status, symbol, exchange, holding_quantity,
                avg_buy_price, current_price, unrealized_pnl_pct,
                decision_intent, user_reasoning, holding_period_days,
                market_trend, sector, tax_category,
                nifty_1m_return, nifty_volatility_30d, nifty_1d_change,
                vix_value, market_data_source, holding_id, portfolio_context
            )
            VALUES ($1, 'pending', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20::jsonb)
            RETURNING decision_id
            """,
            user.user_id,
            symbol,
            exchange,
            quantity,
            avg_price,
            current_price,
            unrealized,
            payload.decision_intent,
            payload.user_reasoning,
            payload.holding_period_days,
            market_trend,
            payload.sector,
            _tax_category(payload.holding_period_days),
            market["nifty_1m_return"],
            market["nifty_volatility_30d"],
            market["nifty_1d_change"],
            market["vix_value"],
            market["market_data_source"],
            holding_id,
            json.dumps(context) if context else None,
        )

    decision_id = str(decision_id)
    background.add_task(run_analysis_pipeline, decision_id, str(user.user_id))
    logger.info("decision_submitted", decision_id=decision_id, user_id=str(user.user_id))

    return DecisionSubmitResponse(
        decision_id=decision_id,
        status="pending",
        stream_url=f"/v1/decisions/{decision_id}/stream",
    )


def _tax_category(holding_period_days):
    """STCG under a year, LTCG at or beyond it (§6A owns the real rules)."""
    if holding_period_days is None:
        return None
    return "LTCG" if holding_period_days >= 365 else "STCG"


# --------------------------------------------------------------------------- #
# GET /v1/decisions/my
# --------------------------------------------------------------------------- #
@router.get("/my")
async def my_decisions(
    limit: int = Query(20, ge=1, le=_MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    async with db.rls_transaction(str(user.user_id)) as conn:
        rows = await conn.fetch(
            f"""
            SELECT {', '.join(_SUMMARY_FIELDS)}
              FROM decisions
             ORDER BY submitted_at DESC, decision_id DESC
             LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM decisions")

    return {
        "items": [jsonable_row(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# --------------------------------------------------------------------------- #
# GET /v1/decisions/stats
# --------------------------------------------------------------------------- #
_BIAS_LABELS = ("loss_aversion", "herd_behavior", "disposition_effect", "rational")


@router.get("/stats")
async def decision_stats(
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Per-user aggregates for the dashboard, computed from ``decisions``.

    ``bias_profiles`` is not maintained by the pipeline yet (it reads as zeros
    for everyone), so the bias mix is derived from the user's own completed
    decisions — RLS scopes every query here to the caller.

    ``wealth_at_stake_inr`` sums the simulated 20-year cost of the user's
    *sell* intents where holding came out ahead: the money the analysis says
    acting on those sells would have given up.
    """
    async with db.rls_transaction(str(user.user_id)) as conn:
        totals = await conn.fetchrow(
            """
            SELECT COUNT(*)                                        AS total,
                   COUNT(*) FILTER (WHERE status = 'complete')     AS completed,
                   AVG(bias_confidence) FILTER (WHERE status = 'complete')
                                                                   AS avg_confidence,
                   COALESCE(SUM(GREATEST(opportunity_cost_inr, 0)) FILTER (
                       WHERE status = 'complete' AND decision_intent = 'sell'
                   ), 0)                                           AS wealth_at_stake_inr
              FROM decisions
            """
        )
        counts = await conn.fetch(
            """
            SELECT bias_detected, COUNT(*) AS n
              FROM decisions
             WHERE status = 'complete' AND bias_detected IS NOT NULL
             GROUP BY bias_detected
            """
        )
    by_bias = {label: 0 for label in _BIAS_LABELS}
    for row in counts:
        by_bias[row["bias_detected"]] = row["n"]
    biased = {k: v for k, v in by_bias.items() if k != "rational" and v > 0}
    dominant = max(biased, key=biased.get) if biased else None
    completed = totals["completed"] or 0
    return {
        "total": totals["total"],
        "completed": completed,
        "by_bias": by_bias,
        "dominant_bias": dominant,
        "rational_share": round(by_bias["rational"] / completed, 4) if completed else None,
        "avg_confidence": (
            round(float(totals["avg_confidence"]), 4)
            if totals["avg_confidence"] is not None else None
        ),
        "wealth_at_stake_inr": float(totals["wealth_at_stake_inr"]),
    }


# --------------------------------------------------------------------------- #
# GET /v1/decisions/{id}/result
# --------------------------------------------------------------------------- #
@router.get("/{decision_id}/result")
async def decision_result(
    decision_id: str,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """The full decision row, whatever its status.

    Returned for ``pending``/``processing`` too (with the ML fields still null)
    so a client that missed the stream can poll instead of guessing.
    """
    row = await _load_owned_decision(db, _parse_uuid(decision_id), user.user_id)
    if row is None:
        raise _not_found()

    return {
        "decision": jsonable_row(row),
        # Which steps ran a Milestone 3 placeholder rather than a real Phase 5
        # implementation. Empty once all five are registered.
        "stubbed_steps": [name for name in STEP_ORDER if is_stubbed(name)],
    }


# --------------------------------------------------------------------------- #
# GET /v1/decisions/{id}/verify — the tamper-evident record (Phase B1)
# --------------------------------------------------------------------------- #
@router.get("/{decision_id}/verify")
async def verify_decision(
    decision_id: str,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Check that the investor's record chain is intact and that this analysis
    still matches what was recorded when it ran (``backend/core/audit.py``)."""
    row = await _load_owned_decision(db, _parse_uuid(decision_id), user.user_id)
    if row is None:
        raise _not_found()
    async with db.rls_transaction(str(user.user_id)) as conn:
        entries, genesis = await audit.load_chain(conn, str(user.user_id))
    chain = audit.verify_chain(entries, genesis)
    record = audit.verify_decision(row, entries, chain)
    return {
        "record": record,
        "chain": {k: chain[k] for k in ("valid", "entries", "linked", "anchor", "problems")},
        "verified": chain["valid"] and record["status"] in ("verified", "matches_earlier_format"),
    }


# --------------------------------------------------------------------------- #
# GET /v1/decisions/{id}/report — downloadable explanation (GAP 3)
# --------------------------------------------------------------------------- #
@router.get("/{decision_id}/report")
async def decision_report(
    decision_id: str,
    format: str = Query("html", pattern="^(html|pdf)$"),
    lang: str = Query("en", pattern="^(en|hi)$"),
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """The explanation the user read, as a file they can keep or share.

    Built by ``src/explanation_report.py`` from the explanation stored with the
    decision, so the report always matches the screen. PDF is English-only:
    ReportLab cannot shape Devanagari, so Hindi is offered as print-ready HTML
    (the browser's "Save as PDF" then produces a correct Hindi PDF).
    """
    row = await _load_owned_decision(db, _parse_uuid(decision_id), user.user_id)
    if row is None:
        raise _not_found()
    explainer = jsonable_row(row, ["explainer_output"])["explainer_output"] or {}
    explanation = (explainer.get("explanation") or {}).get(lang)
    if not explanation:
        raise AppError(
            status_code=404, error="REPORT_UNAVAILABLE",
            message="A report isn't available for this analysis. Run a new analysis to get one.",
        )
    if format == "pdf" and lang != "en":
        raise AppError(
            status_code=400, error="PDF_ENGLISH_ONLY",
            message="PDF is available in English. Download the HTML report for Hindi.",
        )

    ensure_src_importable()
    from src.explanation_report import to_html, to_pdf

    stem = f"folium-{row['symbol'].lower()}-{str(row['submitted_at'].date())}-{lang}"
    if format == "pdf":
        content = await asyncio.to_thread(to_pdf, explanation)
        media, filename = "application/pdf", f"{stem}.pdf"
    else:
        content = to_html(explanation).encode("utf-8")
        media, filename = "text/html; charset=utf-8", f"{stem}.html"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# GET /v1/decisions/{id}/stream — §3F step 4
# --------------------------------------------------------------------------- #
@router.get("/{decision_id}/stream")
async def stream_decision(
    request: Request,
    decision_id: str,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    decision_id = _parse_uuid(decision_id)
    row = await _load_owned_decision(db, decision_id, user.user_id)
    if row is None:
        raise _not_found()

    return StreamingResponse(
        _event_stream(request, redis, decision_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tell nginx/Render's proxy not to buffer — buffering defeats SSE.
            "X-Accel-Buffering": "no",
        },
    )


async def _event_stream(request: Request, redis: RedisService, decision_id: str):
    """Replay the backlog, then forward live events until a terminal one.

    Order matters: SUBSCRIBE happens before the backlog read so an event
    published *between* the two is caught by the subscription rather than lost.
    The overlap that creates is removed by skipping any ``seq`` already emitted
    (see core/events.py).
    """
    settings = get_settings()
    loop = asyncio.get_running_loop()
    pubsub = redis.client.pubsub()
    await pubsub.subscribe(channel(decision_id))

    try:
        last_seq = 0
        for raw in await read_backlog(redis, decision_id):
            seq = parse_seq(raw)
            if seq is not None:
                last_seq = max(last_seq, seq)
            yield sse_frame(raw)
            if parse_step(raw) in TERMINAL_STEPS:
                return

        deadline = loop.time() + settings.SSE_STREAM_TIMEOUT_SECONDS
        last_beat = loop.time()

        while True:
            if await request.is_disconnected():
                logger.info("sse_client_disconnected", decision_id=decision_id)
                return

            now = loop.time()
            if now >= deadline:
                yield event_frame({"step": "timeout", "decision_id": decision_id})
                return

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message is None:
                if loop.time() - last_beat >= settings.SSE_HEARTBEAT_SECONDS:
                    last_beat = loop.time()
                    yield HEARTBEAT_FRAME
                continue

            raw = message["data"]
            if isinstance(raw, bytes):  # only if decode_responses were ever off
                raw = raw.decode("utf-8")
            seq = parse_seq(raw)
            if seq is not None:
                if seq <= last_seq:
                    continue  # already replayed from the backlog
                last_seq = seq

            yield sse_frame(raw)
            if parse_step(raw) in TERMINAL_STEPS:
                return
    finally:
        # The client may have vanished; unsubscribing must not raise out of the
        # generator's cleanup.
        try:
            await pubsub.unsubscribe(channel(decision_id))
        except Exception:  # noqa: BLE001
            pass
        await pubsub.aclose()
