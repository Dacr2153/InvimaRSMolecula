from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.fixture
def reloj_fijo():
    """Reloj determinista: dos corridas producen exactamente los mismos timestamps."""
    momento = datetime(2026, 8, 26, 14, 0, 0, tzinfo=UTC)
    contador = {"n": 0}

    def reloj() -> datetime:
        contador["n"] += 1
        return momento

    return reloj
