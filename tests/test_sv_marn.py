"""Tests for sv.marn — El Salvador MARN environmental permits source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMarnParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Minera Test"):
        from openquery.sources.sv.marn import MarnSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = MarnSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.permit_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Industria SV")
        assert result.search_term == "Industria SV"

    def test_parses_company_name(self):
        body = "Empresa: Industrias Verdes SV\nEstado: Vigente"
        result = self._parse(body)
        assert result.company_name == "Industrias Verdes SV"

    def test_parses_permit_status(self):
        body = "Permiso: AMB-2024-001\nEstado: Vigente"
        result = self._parse(body)
        assert result.permit_status == "Vigente"

    def test_model_roundtrip(self):
        from openquery.models.sv.marn import MarnResult

        r = MarnResult(search_term="test", company_name="Industria SV", permit_status="Vigente")
        data = r.model_dump_json()
        r2 = MarnResult.model_validate_json(data)
        assert r2.company_name == "Industria SV"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.marn import MarnResult

        r = MarnResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestMarnSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.marn import MarnSource

        meta = MarnSource().meta()
        assert meta.name == "sv.marn"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.sv.marn import MarnSource

        src = MarnSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
