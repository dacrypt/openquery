"""Tests for pr.trabajo — Puerto Rico Department of Labor source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrTrabajoParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Test"):
        from openquery.sources.pr.trabajo import PrTrabajoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = PrTrabajoSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.employer_name == ""
        assert result.compliance_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Corp PR")
        assert result.search_term == "Corp PR"

    def test_parses_employer_name(self):
        body = "Patrono: Empresa PR Inc\nCumplimiento: Al día"
        result = self._parse(body)
        assert result.employer_name == "Empresa PR Inc"

    def test_parses_compliance_status(self):
        body = "Cumplimiento: En cumplimiento\nIndustria: Manufactura"
        result = self._parse(body)
        assert result.compliance_status == "En cumplimiento"

    def test_model_roundtrip(self):
        from openquery.models.pr.trabajo import PrTrabajoResult

        r = PrTrabajoResult(search_term="test", employer_name="Empresa PR", compliance_status="Cumple")  # noqa: E501
        data = r.model_dump_json()
        r2 = PrTrabajoResult.model_validate_json(data)
        assert r2.employer_name == "Empresa PR"

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.trabajo import PrTrabajoResult

        r = PrTrabajoResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestPrTrabajoSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.trabajo import PrTrabajoSource

        meta = PrTrabajoSource().meta()
        assert meta.name == "pr.trabajo"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.pr.trabajo import PrTrabajoSource

        src = PrTrabajoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
