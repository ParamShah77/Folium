"""Analysis pipeline core (§3F).

``pipeline.run_analysis_pipeline`` is the entry point; ``steps`` holds the
step protocol and registry that Phase 5 plugs its ML components into.

Importing this package registers the Milestone 3 placeholder steps as the
fallback implementations (``stub_steps``). They only take effect for steps that
Phase 5 has not registered yet, and only while ``PIPELINE_STUB_STEPS`` is on.

It then registers the real Phase 5 steps, which win over the placeholders. They
register *unconditionally* — not "if the ML extras import" — so a machine
missing those extras fails the step with an explicit ``MLUnavailableError``
instead of quietly falling back to the stub. Serving placeholder arithmetic
under the name of the classifier is the one failure mode worth crashing over.
The module-level import stays cheap: the heavy libraries load lazily on first
prediction, not here.
"""
from __future__ import annotations

from . import stub_steps  # noqa: F401 — import for its register_default_step calls
from . import bias_detector  # noqa: F401 — Phase 5A; import for its register_step call
from . import simulator  # noqa: F401 — Phase 5B: 20-year Monte Carlo
from . import explainer  # noqa: F401 — Phase 5C: causal explanation
from . import recommendation  # noqa: F401 — evidence-based verdict until Phase 5D
from . import audit  # noqa: F401 — Phase B1: tamper-evident audit chain
from .pipeline import run_analysis_pipeline
from .steps import PipelineContext, StepResult, is_stubbed, register_step, resolve_step

__all__ = [
    "PipelineContext",
    "StepResult",
    "is_stubbed",
    "register_step",
    "resolve_step",
    "run_analysis_pipeline",
]
