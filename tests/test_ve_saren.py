"""Tests for ve.saren — Venezuela company registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestSarenResult — model tests
# ===========================================================================


class TestSarenResult:
    def test_defaults(self):
        from openquery.models.ve.saren import SarenResult

        r = SarenResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.rif == ""
        assert r.registration_status == ""
        assert r.company_type == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.saren import SarenResult

        r = SarenResult(
            search_term="PDVSA",
            company_name="PDVSA S.A.",
            rif="J-00123456-7",
            registration_status="INSCRITA",
            company_type="Compañía Anónima",
        )
        dumped = r.model_dump_json()
        restored = SarenResult.model_validate_json(dumped)
        assert restored.company_name == "PDVSA S.A."
        assert restored.rif == "J-00123456-7"
        assert restored.registration_status == "INSCRITA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.saren import SarenResult

        r = SarenResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.saren import SarenResult

        r = SarenResult(details={"RIF": "J-00123456-7", "Tipo": "CA"})
        assert r.details["RIF"] == "J-00123456-7"


# ===========================================================================
# TestSarenSourceMeta
# ===========================================================================


class TestSarenSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.saren import SarenSource

        assert SarenSource().meta().name == "ve.saren"

    def test_meta_country(self):
        from openquery.sources.ve.saren import SarenSource

        assert SarenSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.saren import SarenSource

        assert SarenSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.ve.saren import SarenSource

        assert SarenSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.saren import SarenSource

        assert DocumentType.CUSTOM in SarenSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.saren import SarenSource

        assert SarenSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestSarenQuery — input validation
# ===========================================================================


class TestSarenQuery:
    def test_empty_search_term_raises(self):
        from openquery.sources.ve.saren import SarenSource

        src = SarenSource()
        with pytest.raises(SourceError, match="company name or RIF"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_empty_with_no_extra_name_raises(self):
        from openquery.sources.ve.saren import SarenSource

        src = SarenSource()
        with pytest.raises(SourceError):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={},
                )
            )

    def test_document_number_used_as_search_term(self):
        from openquery.models.ve.saren import SarenResult
        from openquery.sources.ve.saren import SarenSource

        src = SarenSource()
        src._query = MagicMock(return_value=SarenResult(search_term="PDVSA"))
        result = src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="PDVSA"))
        src._query.assert_called_once_with("PDVSA", audit=False)
        assert result.search_term == "PDVSA"

    def test_extra_name_used_when_no_document_number(self):
        from openquery.models.ve.saren import SarenResult
        from openquery.sources.ve.saren import SarenSource

        src = SarenSource()
        called_with: dict = {}

        def fake_query(search_term: str, audit: bool = False):
            called_with["term"] = search_term
            return SarenResult(search_term=search_term)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"name": "Banco de Venezuela"},
            )
        )
        assert called_with["term"] == "Banco de Venezuela"


# ===========================================================================
# TestSarenParseResult — parsing logic
# ===========================================================================


class TestSarenParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        return page

    def _parse(self, body_text: str, search_term: str = "PDVSA") -> object:
        from openquery.sources.ve.saren import SarenSource

        return SarenSource()._parse_result(self._make_page(body_text), search_term)

    def test_company_name_extracted(self):
        body = "Denominacion: PDVSA S.A.\nRIF: J-00123456-7\n"
        result = self._parse(body)
        assert result.company_name == "PDVSA S.A."

    def test_rif_extracted(self):
        body = "RIF: J-00123456-7\n"
        result = self._parse(body)
        assert result.rif == "J-00123456-7"

    def test_status_extracted(self):
        body = "Estado: INSCRITA\n"
        result = self._parse(body)
        assert result.registration_status == "INSCRITA"

    def test_company_type_extracted(self):
        body = "Tipo: Compañía Anónima\n"
        result = self._parse(body)
        assert result.company_type == "Compañía Anónima"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="PDVSA")
        assert result.search_term == "PDVSA"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.rif == ""

    def test_details_populated(self):
        body = "RIF: J-00123456-7\nEstado: INSCRITA\n"
        result = self._parse(body)
        assert isinstance(result.details, dict)

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestSarenIntegration:
    def test_query_by_company_name(self):
        from openquery.sources.ve.saren import SarenSource

        src = SarenSource(headless=True)
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="PDVSA",
            )
        )
        assert isinstance(result.search_term, str)
        assert isinstance(result.company_name, str)
