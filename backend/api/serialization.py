"""JSON-safe coercion for asyncpg rows.

asyncpg hands back ``Decimal`` for NUMERIC, ``UUID`` for UUID and ``datetime``
for TIMESTAMPTZ — none of which the default JSON encoder accepts. Route modules
run rows through here before returning them.
"""
from __future__ import annotations

import datetime
import decimal
import json
import uuid
from typing import Any, Iterable, Mapping, Optional


def jsonable(value: Any) -> Any:
    """Decimal -> float, UUID/datetime -> str, everything else unchanged."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


#: ``decisions`` columns stored as JSONB. The pool registers no JSON codec
#: (the pipeline writes these as pre-serialised text with a ``::jsonb`` cast,
#: which a codec would double-encode), so asyncpg returns them as ``str``.
JSONB_COLUMNS = frozenset({"explainer_output", "debate_transcript", "simulation_curves", "portfolio_context",
                           "comment_facts"})


def decode_jsonb(value: Any) -> Any:
    """JSONB text -> Python object; anything else unchanged."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def jsonable_row(
    row: Mapping[str, Any], fields: Optional[Iterable[str]] = None
) -> dict[str, Any]:
    """Coerce a row to a JSON-safe dict, optionally restricted to ``fields``.

    JSONB columns are decoded, so clients receive objects rather than JSON
    nested inside a string.
    """
    keys = list(fields) if fields is not None else list(row.keys())
    return {
        key: decode_jsonb(row[key]) if key in JSONB_COLUMNS else jsonable(row[key])
        for key in keys
    }
