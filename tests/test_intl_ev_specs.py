"""Tests for intl.ev_specs — Open EV Data battery/range specs.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlEvSpecsResult — model tests
# ===========================================================================


class TestIntlEvSpecsResult:
    def test_defaults(self):
        from openquery.models.intl.ev_specs import IntlEvSpecsResult

        r = IntlEvSpecsResult()
        assert r.brand == ""
        assert r.model == ""
        assert r.battery_capacity_kwh == ""
        assert r.range_km == ""
        assert r.fast_charge_kw == ""
        assert r.connector_type == ""
        assert r.details == ""
        assert r.matches == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.ev_specs import IntlEvSpecsResult

        r = IntlEvSpecsResult(
            brand="Tesla",
            model="Model 3",
            battery_capacity_kwh="75",
            range_km="550",
        )
        dumped = r.model_dump_json()
        restored = IntlEvSpecsResult.model_validate_json(dumped)
        assert restored.brand == "Tesla"
        assert restored.model == "Model 3"
        assert restored.battery_capacity_kwh == "75"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.ev_specs import IntlEvSpecsResult

        r = IntlEvSpecsResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestIntlEvSpecsSourceMeta
# ===========================================================================


class TestIntlEvSpecsSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        meta = EvSpecsSource().meta()
        assert meta.name == "intl.ev_specs"

    def test_meta_country(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        meta = EvSpecsSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        meta = EvSpecsSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        meta = EvSpecsSource().meta()
        assert meta.rate_limit_rpm == 30

    def test_meta_supports_custom(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        meta = EvSpecsSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestIntlEvSpecsParseResult
# ===========================================================================

MOCK_EV_DATA = [
    {
        "brand": "Tesla",
        "model": "Model 3",
        "usable_battery_size": 75,
        "range": 550,
        "fast_charge_speed": 170,
        "connector": "CCS",
    },
    {
        "brand": "Tesla",
        "model": "Model S",
        "usable_battery_size": 95,
        "range": 600,
        "fast_charge_speed": 200,
        "connector": "CCS",
    },
]


class TestIntlEvSpecsParseResult:
    def _make_input(self, brand: str = "tesla", model: str = "model 3") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"brand": brand, "model": model},
        )

    def test_missing_brand_and_model_raises(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        source = EvSpecsSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="brand"):
            source.query(inp)

    def test_successful_query(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EV_DATA
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EvSpecsSource()
            result = source.query(self._make_input())

        assert result.brand == "Tesla"
        assert result.model == "Model 3"
        assert result.battery_capacity_kwh == "75"
        assert result.range_km == "550"
        assert result.connector_type == "CCS"
        assert len(result.matches) == 1

    def test_no_match_returns_empty(self):
        from openquery.sources.intl.ev_specs import EvSpecsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EV_DATA
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EvSpecsSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"brand": "BYD", "model": "Atto"},
            )
            result = source.query(inp)

        assert "No EV found" in result.details
        assert result.matches == []

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.ev_specs import EvSpecsSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EvSpecsSource()
            with pytest.raises(SourceError, match="intl.ev_specs"):
                source.query(self._make_input())
