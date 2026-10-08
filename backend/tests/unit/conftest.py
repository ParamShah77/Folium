"""Neutralise the compose-stack fixtures for tests that touch no datastore.

``backend/tests/conftest.py`` provisions ``finai_test`` and flushes Redis via
two ``autouse`` fixtures, so every test under it needs the compose stack up.
Most of the Phase 5 bridge, though, is pure translation — feature assembly,
label mapping, profile defaulting — and its bugs are exactly the kind that
should be caught in a second on a laptop with Docker stopped, not only in CI.

Overriding the two fixtures by name here (nearest conftest wins) buys that
without weakening the real suite: tests in this directory get no database, and
anything that reaches for one fails loudly rather than silently sharing state.
"""
from __future__ import annotations

import pytest
import pytest_asyncio


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    """No-op: these tests never open a connection."""
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """No-op: nothing to truncate."""
    yield
