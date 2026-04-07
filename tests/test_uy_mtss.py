"""Tests for uy.mtss — Uruguay MTSS labor ministry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMtssParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Test"):
        from openquery.sources.uy.mtss import MtssSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = MtssSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.employer_name == ""
        assert result.compliance_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="UY Empresa")
        assert result.search_term == "UY Empresa"

    def test_parses_employer_name(self):
        body = "Empleador: Empresa Uruguay SA\nCumplimiento: En regla"
        result = self._parse(body)
        assert result.employer_name == "Empresa Uruguay SA"

    def test_parses_industry(self):
        body = "Sector: Construcción\nEstado: Activo"
        result = self._parse(body)
        assert result.industry == "Construcción"

    def test_model_roundtrip(self):
        from openquery.models.uy.mtss import MtssResult

        r = MtssResult(search_term="test", employer_name="Empresa UY", compliance_status="Cumple")
        data = r.model_dump_json()
        r2 = MtssResult.model_validate_json(data)
        assert r2.employer_name == "Empresa UY"

    def test_audit_excluded_from_json(self):
        from openquery.models.uy.mtss import MtssResult

        r = MtssResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestMtssSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.mtss import MtssSource

        meta = MtssSource().meta()
        assert meta.name == "uy.mtss"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.uy.mtss import MtssSource

        src = MtssSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
