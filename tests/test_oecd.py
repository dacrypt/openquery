"""Tests for intl.oecd — OECD economic indicators.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestOecdResult — model tests
# ===========================================================================


class TestOecdResult:
    def test_defaults(self):
        from openquery.models.intl.oecd import OecdResult

        r = OecdResult()
        assert r.country_code == ""
        assert r.indicator_code == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.oecd import OecdDataPoint, OecdResult

        r = OecdResult(
            country_code="USA",
            indicator_code="CPI01",
            data_points=[
                OecdDataPoint(period="2022-Q1", value="108.5"),
                OecdDataPoint(period="2022-Q2", value="110.2"),
            ],
        )
        dumped = r.model_dump_json()
        restored = OecdResult.model_validate_json(dumped)
        assert restored.country_code == "USA"
        assert restored.indicator_code == "CPI01"
        assert len(restored.data_points) == 2
        assert restored.data_points[0].period == "2022-Q1"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.oecd import OecdResult

        r = OecdResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.oecd import OecdDataPoint

        dp = OecdDataPoint()
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestOecdSourceMeta
# ===========================================================================


class TestOecdSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.oecd import OecdSource

        meta = OecdSource().meta()
        assert meta.name == "intl.oecd"

    def test_meta_country(self):
        from openquery.sources.intl.oecd import OecdSource

        meta = OecdSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.oecd import OecdSource

        meta = OecdSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.oecd import OecdSource

        meta = OecdSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.intl.oecd import OecdSource

        meta = OecdSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestOecdParseResult
# ===========================================================================

MOCK_OECD_RESPONSE = {
    "data": {
        "dataSets": [
            {
                "series": {
                    "0:0:0:0:0": {
                        "observations": {
                            "0": [108.5, None],
                            "1": [110.2, None],
                        }
                    }
                }
            }
        ],
        "structures": [
            {
                "dimensions": {
                    "observation": [
                        {
                            "id": "TIME_PERIOD",
                            "values": [
                                {"id": "2022-Q1"},
                                {"id": "2022-Q2"},
                            ],
                        }
                    ]
                },
                "attributes": {"series": []},
            }
        ],
    }
}


class TestOecdParseResult:
    def _make_input(self, country: str = "USA", indicator: str = "CPI01") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def test_successful_query(self):
        from openquery.sources.intl.oecd import OecdSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OECD_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = OecdSource()
            result = source.query(self._make_input())

        assert result.country_code == "USA"
        assert result.indicator_code == "CPI01"
        assert len(result.data_points) == 2
        assert result.data_points[0].period == "2022-Q1"
        assert result.data_points[0].value == "108.5"

    def test_missing_country_raises(self):
        from openquery.sources.intl.oecd import OecdSource

        source = OecdSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": "CPI01"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.oecd import OecdSource

        source = OecdSource()
        inp = QueryInput(
            document_number="USA",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_country_uppercased(self):
        from openquery.sources.intl.oecd import OecdSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OECD_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = OecdSource()
            inp = QueryInput(
                document_number="usa",
                document_type=DocumentType.CUSTOM,
                extra={"indicator": "CPI01"},
            )
            result = source.query(inp)

        assert result.country_code == "USA"

    def test_empty_datasets(self):
        from openquery.sources.intl.oecd import OecdSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"dataSets": [], "structures": []}}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = OecdSource()
            result = source.query(self._make_input())

        assert result.data_points == []

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.oecd import OecdSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = OecdSource()
            with pytest.raises(SourceError, match="intl.oecd"):
                source.query(self._make_input())
