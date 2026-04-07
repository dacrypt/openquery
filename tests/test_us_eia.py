"""Tests for us.eia — EIA US electricity retail prices.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestUsEiaResult — model tests
# ===========================================================================


class TestUsEiaResult:
    def test_defaults(self):
        from openquery.models.us.eia import UsEiaResult

        r = UsEiaResult()
        assert r.state == ""
        assert r.sector == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.eia import EiaDataPoint, UsEiaResult

        r = UsEiaResult(
            state="CA",
            sector="residential",
            data_points=[EiaDataPoint(period="2023-01", price="22.5")],
        )
        dumped = r.model_dump_json()
        restored = UsEiaResult.model_validate_json(dumped)
        assert restored.state == "CA"
        assert len(restored.data_points) == 1
        assert restored.data_points[0].period == "2023-01"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.eia import UsEiaResult

        r = UsEiaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.us.eia import EiaDataPoint

        dp = EiaDataPoint()
        assert dp.period == ""
        assert dp.price == ""


# ===========================================================================
# TestUsEiaSourceMeta
# ===========================================================================


class TestUsEiaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.eia import EiaSource

        meta = EiaSource().meta()
        assert meta.name == "us.eia"

    def test_meta_country(self):
        from openquery.sources.us.eia import EiaSource

        meta = EiaSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.eia import EiaSource

        meta = EiaSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.eia import EiaSource

        meta = EiaSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.eia import EiaSource

        meta = EiaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestUsEiaParseResult
# ===========================================================================

MOCK_EIA_RESPONSE = {
    "response": {
        "total": 2,
        "dateFormat": "YYYY-MM",
        "data": [
            {"period": "2023-12", "stateid": "CA", "sectorid": "RES", "price": "22.51"},
            {"period": "2023-11", "stateid": "CA", "sectorid": "RES", "price": "21.89"},
        ],
    }
}


class TestUsEiaParseResult:
    def _make_input(self, state: str = "CA", sector: str = "residential") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"state": state, "sector": sector},
        )

    def test_no_api_key_raises(self):
        from openquery.sources.us.eia import EiaSource

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key = ""
            source = EiaSource()
            with pytest.raises(SourceError, match="EIA_API_KEY"):
                source.query(self._make_input())

    def test_missing_state_raises(self):
        from openquery.sources.us.eia import EiaSource

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key = "testkey"
            source = EiaSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"sector": "residential"},
            )
            with pytest.raises(SourceError, match="state"):
                source.query(inp)

    def test_successful_query(self):
        from openquery.sources.us.eia import EiaSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EIA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key = "testkey"
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__.return_value = mock_client
                mock_client.get.return_value = mock_resp

                source = EiaSource()
                result = source.query(self._make_input())

        assert result.state == "CA"
        assert result.sector == "residential"
        assert len(result.data_points) == 2
        assert result.data_points[0].period == "2023-12"
        assert result.data_points[0].price == "22.51"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.eia import EiaSource

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=mock_resp
        )

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key = "testkey"
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__.return_value = mock_client
                mock_client.get.return_value = mock_resp

                source = EiaSource()
                with pytest.raises(SourceError, match="us.eia"):
                    source.query(self._make_input())
