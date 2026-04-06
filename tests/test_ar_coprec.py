"""Tests for ar.coprec — COPREC consumer mediation records."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestCoprecResult:
    """Test CoprecResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.ar.coprec import CoprecResult

        r = CoprecResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.total_records == 0
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.ar.coprec import CoprecResult

        r = CoprecResult(search_term="Telecom", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "Telecom" in dumped

    def test_json_roundtrip(self):
        from openquery.models.ar.coprec import CoprecResult

        r = CoprecResult(
            search_term="Telecom",
            company_name="TELECOM ARGENTINA SA",
            total_records=42,
            details={"Empresa": "TELECOM"},
        )
        r2 = CoprecResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "Telecom"
        assert r2.total_records == 42
        assert r2.company_name == "TELECOM ARGENTINA SA"

    def test_queried_at_default(self):
        from openquery.models.ar.coprec import CoprecResult

        before = datetime.now()
        r = CoprecResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestCoprecSourceMeta:
    """Test ar.coprec source metadata."""

    def test_meta_name(self):
        from openquery.sources.ar.coprec import CoprecSource

        assert CoprecSource().meta().name == "ar.coprec"

    def test_meta_country(self):
        from openquery.sources.ar.coprec import CoprecSource

        assert CoprecSource().meta().country == "AR"

    def test_meta_requires_browser(self):
        from openquery.sources.ar.coprec import CoprecSource

        assert CoprecSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.ar.coprec import CoprecSource

        assert DocumentType.CUSTOM in CoprecSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ar.coprec import CoprecSource

        assert CoprecSource().meta().rate_limit_rpm == 10


class TestCoprecParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, search_term: str = "Telecom"):
        from openquery.sources.ar.coprec import CoprecSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return CoprecSource()._parse_result(page, search_term)

    def test_search_term_preserved(self):
        assert self._parse("Datos").search_term == "Telecom"

    def test_total_records_parsed(self):
        result = self._parse("Se encontraron 15 mediaciones para la empresa")
        assert result.total_records == 15

    def test_company_name_parsed(self):
        result = self._parse("Empresa: TELECOM ARGENTINA SA\nOtros")
        assert result.company_name == "TELECOM ARGENTINA SA"

    def test_company_name_defaults_to_search_term(self):
        result = self._parse("Sin resultados")
        assert result.company_name == "Telecom"

    def test_empty_body(self):
        result = self._parse("")
        assert result.search_term == "Telecom"
        assert result.total_records == 0

    def test_query_missing_search_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.ar.coprec import CoprecSource

        with pytest.raises(SourceError, match="[Cc]ompany"):
            CoprecSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
