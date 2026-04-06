"""Tests for intl.opencorporates — global company search."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestOpenCorporatesResult — model tests
# ===========================================================================


class TestOpenCorporatesResult:
    def test_defaults(self):
        from openquery.models.intl.opencorporates import IntlOpenCorporatesResult

        r = IntlOpenCorporatesResult()
        assert r.search_term == ""
        assert r.total == 0
        assert r.companies == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.opencorporates import IntlOpenCorporatesResult, OpenCorporatesCompany

        r = IntlOpenCorporatesResult(
            search_term="Apple",
            total=2,
            companies=[
                OpenCorporatesCompany(
                    name="Apple Inc.",
                    jurisdiction="us_ca",
                    status="Active",
                    company_number="C0806592",
                    incorporation_date="1977-01-03",
                    company_type="Domestic Stock",
                ),
                OpenCorporatesCompany(
                    name="Apple Ltd",
                    jurisdiction="gb",
                    status="Active",
                    company_number="00123456",
                ),
            ],
        )
        dumped = r.model_dump_json()
        restored = IntlOpenCorporatesResult.model_validate_json(dumped)
        assert restored.search_term == "Apple"
        assert restored.total == 2
        assert restored.companies[0].name == "Apple Inc."
        assert restored.companies[0].jurisdiction == "us_ca"
        assert restored.companies[1].company_number == "00123456"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.opencorporates import IntlOpenCorporatesResult

        r = IntlOpenCorporatesResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_company_defaults(self):
        from openquery.models.intl.opencorporates import OpenCorporatesCompany

        co = OpenCorporatesCompany()
        assert co.name == ""
        assert co.jurisdiction == ""
        assert co.status == ""
        assert co.company_number == ""
        assert co.incorporation_date == ""
        assert co.company_type == ""
        assert co.registered_address == ""


# ===========================================================================
# TestOpenCorporatesSourceMeta
# ===========================================================================


class TestOpenCorporatesSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        assert IntlOpenCorporatesSource().meta().name == "intl.opencorporates"

    def test_meta_country(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        assert IntlOpenCorporatesSource().meta().country == "INTL"

    def test_meta_no_captcha_no_browser(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        meta = IntlOpenCorporatesSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        assert IntlOpenCorporatesSource().meta().rate_limit_rpm == 5

    def test_meta_supports_custom(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        assert DocumentType.CUSTOM in IntlOpenCorporatesSource().meta().supported_inputs


# ===========================================================================
# TestOpenCorporatesParseResult
# ===========================================================================

MOCK_OC_RESPONSE = {
    "results": {
        "total_count": 2,
        "companies": [
            {
                "company": {
                    "name": "Apple Inc.",
                    "jurisdiction_code": "us_ca",
                    "current_status": "Active",
                    "company_number": "C0806592",
                    "incorporation_date": "1977-01-03",
                    "company_type": "Domestic Stock",
                    "registered_address": {
                        "street_address": "1 Apple Park Way",
                        "locality": "Cupertino",
                        "country": "United States",
                    },
                }
            },
            {
                "company": {
                    "name": "Apple Ltd",
                    "jurisdiction_code": "gb",
                    "current_status": "Dissolved",
                    "company_number": "00123456",
                    "incorporation_date": "1990-06-15",
                    "company_type": "Private Limited Company",
                    "registered_address": None,
                }
            },
        ],
    }
}


class TestOpenCorporatesParseResult:
    def _make_input(self, name: str = "Apple") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"name": name},
        )

    def test_successful_search_returns_companies(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = IntlOpenCorporatesSource().query(self._make_input("Apple"))

        assert result.search_term == "Apple"
        assert result.total == 2
        assert len(result.companies) == 2
        assert result.companies[0].name == "Apple Inc."
        assert result.companies[0].jurisdiction == "us_ca"
        assert result.companies[0].status == "Active"
        assert result.companies[0].company_number == "C0806592"
        assert "Cupertino" in result.companies[0].registered_address

    def test_second_company_parsed(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = IntlOpenCorporatesSource().query(self._make_input("Apple"))

        co = result.companies[1]
        assert co.name == "Apple Ltd"
        assert co.jurisdiction == "gb"
        assert co.status == "Dissolved"

    def test_missing_input_raises(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        source = IntlOpenCorporatesSource()
        inp = QueryInput(document_number="", document_type=DocumentType.CUSTOM, extra={})
        with pytest.raises(SourceError, match="intl.opencorporates"):
            source.query(inp)

    def test_document_number_used_as_search_term(self):
        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            inp = QueryInput(
                document_number="Google",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = IntlOpenCorporatesSource().query(inp)

        assert result.search_term == "Google"

    def test_rate_limit_error_raises_descriptive(self):
        import httpx

        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="Rate limit"):
                IntlOpenCorporatesSource().query(self._make_input())

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.opencorporates import IntlOpenCorporatesSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="intl.opencorporates"):
                IntlOpenCorporatesSource().query(self._make_input())
