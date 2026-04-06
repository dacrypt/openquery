"""Tests for intl.un_comtrade — UN Comtrade international trade statistics."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestIntlUnComtradeResult — model tests
# ===========================================================================


class TestIntlUnComtradeResult:
    def test_defaults(self):
        from openquery.models.intl.un_comtrade import IntlUnComtradeResult

        r = IntlUnComtradeResult()
        assert r.reporter == ""
        assert r.commodity_code == ""
        assert r.total_trade_value is None
        assert r.partners == []
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.un_comtrade import ComtradePartner, IntlUnComtradeResult

        r = IntlUnComtradeResult(
            reporter="76",
            commodity_code="TOTAL",
            total_trade_value=1000000.0,
            partners=[ComtradePartner(partner_code="484", partner_desc="Mexico", trade_value=500000.0)],
        )
        restored = IntlUnComtradeResult.model_validate_json(r.model_dump_json())
        assert restored.reporter == "76"
        assert len(restored.partners) == 1
        assert restored.partners[0].partner_code == "484"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.un_comtrade import IntlUnComtradeResult

        r = IntlUnComtradeResult(audit="evidence")
        assert "audit" not in r.model_dump()


class TestComtradePartner:
    def test_defaults(self):
        from openquery.models.intl.un_comtrade import ComtradePartner

        p = ComtradePartner()
        assert p.partner_code == ""
        assert p.partner_desc == ""
        assert p.trade_value is None
        assert p.flow == ""


# ===========================================================================
# TestIntlUnComtradeSourceMeta
# ===========================================================================


class TestIntlUnComtradeSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        assert IntlUnComtradeSource().meta().name == "intl.un_comtrade"

    def test_meta_country(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        assert IntlUnComtradeSource().meta().country == "INTL"

    def test_meta_no_browser(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        assert IntlUnComtradeSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        assert IntlUnComtradeSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        assert IntlUnComtradeSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestIntlUnComtradeParseResult — parsing logic
# ===========================================================================


class TestIntlUnComtradeParseResult:
    def test_missing_reporter_raises(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        src = IntlUnComtradeSource()
        with pytest.raises(SourceError, match="Reporter"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_reporter(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource
        from openquery.models.intl.un_comtrade import IntlUnComtradeResult

        src = IntlUnComtradeSource()
        called_with: list = []

        def fake_query(reporter: str, commodity_code: str) -> IntlUnComtradeResult:
            called_with.append((reporter, commodity_code))
            return IntlUnComtradeResult(reporter=reporter, commodity_code=commodity_code)

        src._query = fake_query
        src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="76"))
        assert called_with[0][0] == "76"
        assert called_with[0][1] == "TOTAL"

    def test_parse_response_with_data(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        src = IntlUnComtradeSource()
        data = {
            "data": [
                {
                    "partnerCode": "484",
                    "partnerDesc": "Mexico",
                    "primaryValue": 1500000.0,
                    "flowDesc": "Export",
                },
                {
                    "partnerCode": "840",
                    "partnerDesc": "USA",
                    "primaryValue": 2000000.0,
                    "flowDesc": "Import",
                },
            ]
        }
        result = src._parse_response(data, "76", "TOTAL")
        assert len(result.partners) == 2
        assert result.total_trade_value == pytest.approx(3500000.0)

    def test_parse_response_empty(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        src = IntlUnComtradeSource()
        result = src._parse_response({"data": []}, "76", "TOTAL")
        assert result.total_trade_value is None
        assert result.partners == []


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestIntlUnComtradeIntegration:
    def test_query_brazil(self):
        from openquery.sources.intl.un_comtrade import IntlUnComtradeSource

        src = IntlUnComtradeSource()
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="76",
            extra={"reporter": "76", "commodity_code": "TOTAL"},
        ))
        assert isinstance(result.reporter, str)
