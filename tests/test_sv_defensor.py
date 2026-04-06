"""Tests for sv.defensor — El Salvador Defensoría del Consumidor source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvDefensorParseResult:
    def _parse(self, body_text: str, search_term: str = "Claro"):
        from openquery.sources.sv.defensor import SvDefensorSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = SvDefensorSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.total_complaints == 0

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Tigo")
        assert result.search_term == "Tigo"

    def test_company_name_parsed(self):
        result = self._parse("Empresa: Claro El Salvador\nDenuncias: 25")
        assert result.company_name == "Claro El Salvador"

    def test_total_complaints_parsed(self):
        result = self._parse("Empresa: Claro\nDenuncias: 42")
        assert result.total_complaints == 42

    def test_details_populated(self):
        result = self._parse("Empresa: Tigo\nQuejas: 10")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.sv.defensor import SvDefensorResult

        r = SvDefensorResult(
            search_term="Claro",
            company_name="Claro El Salvador",
            total_complaints=25,
        )
        data = r.model_dump_json()
        r2 = SvDefensorResult.model_validate_json(data)
        assert r2.search_term == "Claro"
        assert r2.company_name == "Claro El Salvador"
        assert r2.total_complaints == 25

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.defensor import SvDefensorResult

        r = SvDefensorResult(search_term="Claro", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvDefensorSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.defensor import SvDefensorSource

        meta = SvDefensorSource().meta()
        assert meta.name == "sv.defensor"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_company_name_raises(self):
        from openquery.sources.sv.defensor import SvDefensorSource

        src = SvDefensorSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
