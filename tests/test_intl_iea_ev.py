"""Tests for intl.iea_ev — IEA Global EV Outlook data.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlIeaEvResult — model tests
# ===========================================================================


class TestIntlIeaEvResult:
    def test_defaults(self):
        from openquery.models.intl.iea_ev import IntlIeaEvResult

        r = IntlIeaEvResult()
        assert r.country == ""
        assert r.parameter == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.iea_ev import IeaEvDataPoint, IntlIeaEvResult

        r = IntlIeaEvResult(
            country="China",
            parameter="EV sales",
            data_points=[IeaEvDataPoint(year="2022", value="5900000")],
        )
        dumped = r.model_dump_json()
        restored = IntlIeaEvResult.model_validate_json(dumped)
        assert restored.country == "China"
        assert len(restored.data_points) == 1
        assert restored.data_points[0].year == "2022"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.iea_ev import IntlIeaEvResult

        r = IntlIeaEvResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.iea_ev import IeaEvDataPoint

        dp = IeaEvDataPoint()
        assert dp.year == ""
        assert dp.value == ""


# ===========================================================================
# TestIntlIeaEvSourceMeta
# ===========================================================================


class TestIntlIeaEvSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        meta = IeaEvSource().meta()
        assert meta.name == "intl.iea_ev"

    def test_meta_country(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        meta = IeaEvSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        meta = IeaEvSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        meta = IeaEvSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        meta = IeaEvSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestIntlIeaEvParseResult
# ===========================================================================

MOCK_CSV_CONTENT = """region,year,value,unit
China,2022,5900000,Vehicles
China,2021,3300000,Vehicles
Germany,2022,830000,Vehicles
"""


class TestIntlIeaEvParseResult:
    def _make_input(self, country: str = "China", parameter: str = "EV sales") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "parameter": parameter},
        )

    def test_missing_country_raises(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        source = IeaEvSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"parameter": "EV sales"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_successful_query(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_CSV_CONTENT
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IeaEvSource()
            result = source.query(self._make_input())

        assert "china" in result.country.lower()
        assert len(result.data_points) == 2
        assert result.data_points[0].year == "2022"
        assert "5900000" in result.data_points[0].value

    def test_country_from_document_number(self):
        from openquery.sources.intl.iea_ev import IeaEvSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_CSV_CONTENT
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IeaEvSource()
            inp = QueryInput(
                document_number="China",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert "china" in result.country.lower()

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.iea_ev import IeaEvSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IeaEvSource()
            with pytest.raises(SourceError, match="intl.iea_ev"):
                source.query(self._make_input())
