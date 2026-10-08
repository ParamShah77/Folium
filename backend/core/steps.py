"""Pipeline step protocol + registry (§3F).

§3F's orchestrator calls five things in order — bias detection, simulation,
explanation, debate, audit — but every one of them is built in Phase 5
(5A–5E). This module is the seam between the two milestones: Milestone 3 owns
the *orchestration* (status transitions, SSE events, failure handling) and
Phase 5 fills in the *work* by calling ``register_step``.

A step is an async callable ``(PipelineContext) -> StepResult``. It returns the
``decisions`` columns to write plus the fields to attach to that step's SSE
event; ``pipeline.py`` persists the columns and publishes the event, so no step
has to know the status/event protocol. A step that must write *other* tables
(the audit step and ``audit_logs``) does so itself via ``ctx.db`` — inside
``rls_transaction``, since every user-owned table is RLS-protected (§2E).

Registration (Phase 5, e.g. in ``core/bias_detector.py``)::

    from .steps import register_step

    async def detect_bias(ctx):
        features = build_features(ctx.decision)
        bias, confidence = model.predict(features)
        return StepResult(
            updates={"bias_detected": bias, "bias_confidence": confidence},
            event={"bias": bias, "confidence": confidence},
        )

    register_step("bias_detection", detect_bias)

Until then ``resolve_step`` falls back to the placeholder in ``stub_steps.py``
(see ``PIPELINE_STUB_STEPS``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from ..config import get_settings
from ..db import Database, RedisService
from .events import STEP_ORDER


@dataclass(frozen=True)
class PipelineContext:
    """Everything a step needs to do its work.

    ``decision`` is the full ``decisions`` row as a plain dict, refreshed before
    each step so later steps see earlier steps' writes.
    """

    decision_id: str
    user_id: str
    decision: Mapping[str, Any]
    db: Database
    redis: RedisService


@dataclass
class StepResult:
    """What a step produced.

    ``updates``  — ``decisions`` columns to UPDATE (column name -> value).
    ``event``    — extra fields merged into this step's ``status: done`` event.
    """

    updates: dict[str, Any] = field(default_factory=dict)
    event: dict[str, Any] = field(default_factory=dict)


StepFn = Callable[[PipelineContext], Awaitable[StepResult]]


class UnregisteredStepError(RuntimeError):
    """A step has no implementation and stub fallback is disabled."""


_REGISTRY: dict[str, StepFn] = {}
_DEFAULTS: dict[str, StepFn] = {}


def register_step(name: str, fn: StepFn) -> None:
    """Install the real (Phase 5) implementation for ``name``."""
    if name not in STEP_ORDER:
        raise ValueError(f"unknown pipeline step {name!r}; expected one of {STEP_ORDER}")
    _REGISTRY[name] = fn


def register_default_step(name: str, fn: StepFn) -> None:
    """Install the placeholder used until a real implementation registers."""
    if name not in STEP_ORDER:
        raise ValueError(f"unknown pipeline step {name!r}; expected one of {STEP_ORDER}")
    _DEFAULTS[name] = fn


def resolve_step(name: str) -> StepFn:
    """The implementation to run for ``name`` — real one first, else the stub."""
    fn = _REGISTRY.get(name)
    if fn is not None:
        return fn
    if get_settings().PIPELINE_STUB_STEPS and name in _DEFAULTS:
        return _DEFAULTS[name]
    raise UnregisteredStepError(
        f"pipeline step {name!r} has no implementation "
        "(Phase 5 registers it; set PIPELINE_STUB_STEPS=true to use the placeholder)"
    )


def is_stubbed(name: str) -> bool:
    """True when ``name`` would run the placeholder rather than a real step."""
    return name not in _REGISTRY
