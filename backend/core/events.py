"""SSE event bus over Redis pub/sub with a replayable backlog (§3F).

Redis keys (extends the §2B schema):
    sse:{decision_id}       PUBLISH channel  — live fan-out to connected streams
    sse_log:{decision_id}   LIST             — every event, for replay
    sse_seq:{decision_id}   INCR counter     — monotonic per-event ``seq``

WHY A BACKLOG (deviation from the §3F sketch, which subscribes only).
§3F has the browser open ``GET /v1/decisions/{id}/stream`` *after* it receives
the 202 from ``POST /v1/decisions/analyze`` — but the pipeline starts the moment
that 202 is sent. Redis pub/sub is fire-and-forget: anything published before
the subscriber attaches is lost, so a fast first step (bias detection) would
routinely never reach the UI, and a page reload mid-pipeline would show a blank
progress list. Every event is therefore ALSO appended to ``sse_log:{id}``, and a
connecting stream:

    1. SUBSCRIBEs first,
    2. replays ``sse_log:{id}``, tracking the highest ``seq`` it emitted,
    3. forwards live messages, skipping any ``seq`` already replayed.

Subscribing *before* replaying closes the reverse race — an event published
between the replay and the subscribe would otherwise fall through both paths.
The ``seq`` field makes the overlap between the two sources safe to de-duplicate.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ..config import get_settings
from ..db import RedisService

# Steps published by the pipeline, in order (§3F).
STEP_ORDER = ("bias_detection", "simulation", "explanation", "debate", "audit")

# Events after which a stream stops reading.
TERMINAL_STEPS = frozenset({"complete", "failed", "timeout"})


def channel(decision_id: str) -> str:
    return f"sse:{decision_id}"


def backlog_key(decision_id: str) -> str:
    return f"sse_log:{decision_id}"


def seq_key(decision_id: str) -> str:
    return f"sse_seq:{decision_id}"


async def publish_event(
    redis: RedisService, decision_id: str, event: dict[str, Any]
) -> dict[str, Any]:
    """Stamp an event with ``seq``/``decision_id``, append it, and publish it.

    Returns the full event dict that was written (useful for logging/tests).
    """
    ttl = get_settings().SSE_BACKLOG_TTL_SECONDS
    client = redis.client

    seq = await client.incr(seq_key(decision_id))
    payload = {**event, "decision_id": str(decision_id), "seq": seq}
    raw = json.dumps(payload, default=str)

    pipe = client.pipeline()
    pipe.rpush(backlog_key(decision_id), raw)
    pipe.expire(backlog_key(decision_id), ttl)
    pipe.expire(seq_key(decision_id), ttl)
    pipe.publish(channel(decision_id), raw)
    await pipe.execute()

    return payload


async def read_backlog(redis: RedisService, decision_id: str) -> list[str]:
    """Every event published for this decision so far, oldest first (raw JSON)."""
    return await redis.client.lrange(backlog_key(decision_id), 0, -1)


async def clear_events(redis: RedisService, decision_id: str) -> None:
    """Drop the backlog + sequence for a decision (re-run / cleanup)."""
    await redis.delete(backlog_key(decision_id), seq_key(decision_id))


# --------------------------------------------------------------------------- #
# Wire format
# --------------------------------------------------------------------------- #
# A bare comment frame. Carries no data (EventSource ignores it) but keeps
# intermediaries from closing an idle connection.
HEARTBEAT_FRAME = ": ping\n\n"


def sse_frame(raw_json: str) -> str:
    """Wrap a JSON payload in an SSE ``data:`` frame."""
    return f"data: {raw_json}\n\n"


def event_frame(event: dict[str, Any]) -> str:
    return sse_frame(json.dumps(event, default=str))


def parse_seq(raw_json: str) -> Optional[int]:
    """Best-effort ``seq`` extraction; ``None`` if the payload is unreadable."""
    try:
        value = json.loads(raw_json).get("seq")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, int) else None


def parse_step(raw_json: str) -> Optional[str]:
    try:
        value = json.loads(raw_json).get("step")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None
