"""Tests for intl.idb — IDB Inter-American Development Bank data.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIdbResult — model tests
# ===========================================================================


class TestIdbResult:
    def test_defaults(self):
        from openquery.models.intl.idb import IdbResult

        r = IdbResult()
        assert r.country_code == ""
        assert r.indicator == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.idb import IdbDataPoint, IdbResult

        r = IdbResult(
            country_code="CO",
            indicator="BI.POV.DDAY",
            data_points=[
                IdbDataPoint(year="2022", value="4.5"),
                IdbDataPoint(year="2021", value="5.2"),
            ],
        )
        dumped = r.model_dump_json()
        restored = IdbResult.model_validate_json(dumped)
        assert restored.country_code == "CO"
        assert restored.indicator == "BI.POV.DDAY"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.idb import IdbResult

        r = IdbResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.idb import IdbDataPoint

        dp = IdbDataPoint()
        assert dp.year == ""
        assert dp.value == ""


# ===========================================================================
# TestIdbSourceMeta
# ===========================================================================


class TestIdbSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.idb import IdbSource

        meta = IdbSource().meta()
        assert meta.name == "intl.idb"

    def test_meta_country(self):
        from openquery.sources.intl.idb import IdbSource

        meta = IdbSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.idb import IdbSource

        meta = IdbSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.idb import IdbSource

        meta = IdbSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.idb import IdbSource

        meta = IdbSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestIdbParseResult
# ===========================================================================

MOCK_IDB_RESPONSE = [
    {"year": 2021, "value": 5.2, "indicatorName": "Poverty headcount ratio"},
    {"year": 2022, "value": 4.5, "indicatorName": "Poverty headcount ratio"},
]


class TestIdbParseResult:
    def _make_input(self, country: str = "CO", indicator: str = "BI.POV.DDAY") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def test_successful_query(self):
        from openquery.sources.intl.idb import IdbSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_IDB_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IdbSource()
            result = source.query(self._make_input())

        assert result.country_code == "CO"
        assert result.indicator == "BI.POV.DDAY"
        assert len(result.data_points) == 2
        assert result.data_points[0].year == "2021"
        assert result.data_points[0].value == "5.2"
        assert result.details == "Poverty headcount ratio"

    def test_missing_country_raises(self):
        from openquery.sources.intl.idb import IdbSource

        source = IdbSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": "BI.POV.DDAY"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.idb import IdbSource

        source = IdbSource()
        inp = QueryInput(
            document_number="CO",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_dict_response_with_data_key(self):
        from openquery.sources.intl.idb import IdbSource

        dict_response = {"data": MOCK_IDB_RESPONSE}
        mock_resp = MagicMock()
        mock_resp.json.return_value = dict_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IdbSource()
            result = source.query(self._make_input())

        assert len(result.data_points) == 2

    def test_null_value_records(self):
        from openquery.sources.intl.idb import IdbSource

        response_with_null = [{"year": 2022, "value": None, "indicatorName": "Test"}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_with_null
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IdbSource()
            result = source.query(self._make_input())

        assert result.data_points[0].value == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.idb import IdbSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = IdbSource()
            with pytest.raises(SourceError, match="intl.idb"):
                source.query(self._make_input())
