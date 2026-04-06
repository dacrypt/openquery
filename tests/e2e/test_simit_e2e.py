"""End-to-end tests for SIMIT source.

Run: uv run pytest tests/e2e/test_simit_e2e.py -v -s
"""

from __future__ import annotations

import pytest

from openquery.models.co.simit import SimitResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.co.simit import SimitSource


@pytest.fixture
def simit():
    return SimitSource(timeout=30.0, headless=True)


@pytest.mark.integration
class TestSimitE2E:
    """End-to-end SIMIT queries against the real website."""

    def test_query_cedula(self, simit):
        """Query SIMIT with a cedula number."""
        result = simit.query(
            QueryInput(
                document_type=DocumentType.CEDULA,
                document_number="1017268287",
            )
        )
        assert isinstance(result, SimitResult)
        assert result.cedula == "1017268287"
        # Should have parsed the summary
        assert result.comparendos >= 0
        assert result.multas >= 0
        assert result.total_deuda >= 0.0

        print("\nSIMIT result for 1017268287:")
        print(f"  Comparendos: {result.comparendos}")
        print(f"  Multas: {result.multas}")
        print(f"  Total deuda: ${result.total_deuda:,.0f}")
        print(f"  Paz y salvo: {result.paz_y_salvo}")
        if result.historial:
            print(f"  Historial: {len(result.historial)} records")
