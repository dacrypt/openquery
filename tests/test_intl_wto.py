"""Tests for intl.wto — WTO trade profiles / tariff data."""

from __future__ import annotations

from datetime import datetime

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestWtoResult — model tests
# ===========================================================================


class TestWtoResult:
    def test_defaults(self):
        from openquery.models.intl.wto import WtoResult

        r = WtoResult()
        assert r.reporter == ""
        assert r.indicator_code == ""
        assert r.total == 0
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.wto import WtoDataPoint, WtoResult

        r = WtoResult(
            reporter="840",
            indicator_code="HS_M_0010",
            total=2,
            data_points=[
                WtoDataPoint(year="2023", value="3.5", indicator="HS_M_0010", partner="000"),
                WtoDataPoint(year="2022", value="4.1", indicator="HS_M_0010", partner="000"),
            ],
        )
        restored = WtoResult.model_validate_json(r.model_dump_json())
        assert restored.reporter == "840"
        assert restored.total == 2
        assert len(restored.data_points) == 2
        assert restored.data_points[0].year == "2023"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.wto import WtoResult

        r = WtoResult(audit="evidence")
        assert "audit" not in r.model_dump()


class TestWtoDataPoint:
    def test_defaults(self):
        from openquery.models.intl.wto import WtoDataPoint

        dp = WtoDataPoint()
        assert dp.year == ""
        assert dp.value == ""
        assert dp.indicator == ""
        assert dp.partner == ""


# ===========================================================================
# TestWtoSourceMeta
# ===========================================================================


class TestWtoSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.wto import WtoSource

        assert WtoSource().meta().name == "intl.wto"

    def test_meta_country(self):
        from openquery.sources.intl.wto import WtoSource

        assert WtoSource().meta().country == "INTL"

    def test_meta_no_browser(self):
        from openquery.sources.intl.wto import WtoSource

        assert WtoSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.intl.wto import WtoSource

        assert WtoSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.wto import WtoSource

        assert WtoSource().meta().rate_limit_rpm == 10

    def test_meta_custom_input(self):
        from openquery.sources.intl.wto import WtoSource

        assert DocumentType.CUSTOM in WtoSource().meta().supported_inputs


# ===========================================================================
# TestWtoParseResult — parsing logic
# ===========================================================================


class TestWtoParseResult:
    def test_missing_reporter_raises(self):
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        with pytest.raises(SourceError, match="Reporter"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_reporter(self):
        from openquery.models.intl.wto import WtoResult
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        called_with: list = []

        def fake_fetch(reporter: str, indicator: str) -> WtoResult:
            called_with.append((reporter, indicator))
            return WtoResult(reporter=reporter, indicator_code=indicator)

        src._fetch = fake_fetch
        src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="840"))
        assert called_with[0][0] == "840"
        assert called_with[0][1] == "HS_M_0010"  # default indicator

    def test_extra_reporter_takes_precedence(self):
        from openquery.models.intl.wto import WtoResult
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        called_with: list = []

        def fake_fetch(reporter: str, indicator: str) -> WtoResult:
            called_with.append((reporter, indicator))
            return WtoResult(reporter=reporter, indicator_code=indicator)

        src._fetch = fake_fetch
        src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="000",
            extra={"reporter": "76", "indicator": "HS_M_0020"},
        ))
        assert called_with[0][0] == "76"
        assert called_with[0][1] == "HS_M_0020"

    def test_parse_response_dataset_key(self):
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        data = {
            "Dataset": [
                {"Year": "2023", "Value": "3.5", "IndicatorCode": "HS_M_0010", "PartnerEconomy": "000"},
                {"Year": "2022", "Value": "4.0", "IndicatorCode": "HS_M_0010", "PartnerEconomy": "000"},
            ],
            "total": 2,
        }
        result = src._parse_response(data, "840", "HS_M_0010")
        assert len(result.data_points) == 2
        assert result.total == 2
        assert result.data_points[0].year == "2023"
        assert result.data_points[0].value == "3.5"

    def test_parse_response_data_key(self):
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        data = {
            "data": [
                {"period": "2023", "value": "5.1", "indicatorCode": "HS_M_0010", "partnerEconomy": "76"},
            ],
        }
        result = src._parse_response(data, "840", "HS_M_0010")
        assert len(result.data_points) == 1
        assert result.data_points[0].year == "2023"
        assert result.data_points[0].partner == "76"

    def test_parse_response_empty(self):
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        result = src._parse_response({"Dataset": [], "total": 0}, "840", "HS_M_0010")
        assert result.data_points == []
        assert result.total == 0
        assert result.reporter == "840"


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestWtoIntegration:
    def test_query_usa(self):
        from openquery.sources.intl.wto import WtoSource

        src = WtoSource()
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="840",
            extra={"reporter": "840", "indicator": "HS_M_0010"},
        ))
        assert result.reporter == "840"
        assert result.indicator_code == "HS_M_0010"
        assert isinstance(result.data_points, list)
