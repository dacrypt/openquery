"""Tests for br.bacen_ptax — BACEN PTAX USD/BRL exchange rates."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestBrBacenPtaxResult — model tests
# ===========================================================================


class TestBrBacenPtaxResult:
    def test_defaults(self):
        from openquery.models.br.bacen_ptax import BrBacenPtaxResult

        r = BrBacenPtaxResult()
        assert r.date == ""
        assert r.buy_rate is None
        assert r.sell_rate is None
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.bacen_ptax import BrBacenPtaxResult

        r = BrBacenPtaxResult(date="01-15-2025", buy_rate=5.8942, sell_rate=5.8948)
        restored = BrBacenPtaxResult.model_validate_json(r.model_dump_json())
        assert restored.buy_rate == pytest.approx(5.8942)
        assert restored.date == "01-15-2025"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.bacen_ptax import BrBacenPtaxResult

        r = BrBacenPtaxResult(audit="test")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestBrBacenPtaxSourceMeta
# ===========================================================================


class TestBrBacenPtaxSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        assert BrBacenPtaxSource().meta().name == "br.bacen_ptax"

    def test_meta_country(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        assert BrBacenPtaxSource().meta().country == "BR"

    def test_meta_no_browser(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        assert BrBacenPtaxSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        assert BrBacenPtaxSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        assert BrBacenPtaxSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestBrBacenPtaxParseResult — parsing logic
# ===========================================================================


class TestBrBacenPtaxParseResult:
    def test_date_normalization_iso(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        src = BrBacenPtaxSource()
        assert src._normalize_date("2025-01-15") == "01-15-2025"

    def test_date_normalization_passthrough(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        src = BrBacenPtaxSource()
        assert src._normalize_date("01-15-2025") == "01-15-2025"

    def test_parse_api_response(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        src = BrBacenPtaxSource()
        api_data = {
            "value": [
                {
                    "cotacaoCompra": 5.8942,
                    "cotacaoVenda": 5.8948,
                    "dataHoraCotacao": "2025-01-15 13:08:35.38",
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query("01-15-2025")

        assert result.buy_rate == pytest.approx(5.8942)
        assert result.sell_rate == pytest.approx(5.8948)

    def test_empty_value_returns_no_rate(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        src = BrBacenPtaxSource()
        api_data = {"value": []}

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query("01-01-2025")

        assert result.buy_rate is None
        assert result.sell_rate is None


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestBrBacenPtaxIntegration:
    def test_query_known_date(self):
        from openquery.sources.br.bacen_ptax import BrBacenPtaxSource

        src = BrBacenPtaxSource()
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="01-15-2025",
                extra={"date": "01-15-2025"},
            )
        )
        assert isinstance(result.date, str)
