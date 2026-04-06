"""Tests for sv.empresa — El Salvador company registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvEmpresaParseResult:
    def _parse(self, body_text: str, search_term: str = "EMPRESA EJEMPLO SA DE CV"):
        from openquery.sources.sv.empresa import SvEmpresaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvEmpresaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.registration_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA EJEMPLO SA DE CV")
        assert result.search_term == "EMPRESA EJEMPLO SA DE CV"

    def test_company_name_parsed(self):
        result = self._parse(
            "Nombre: EMPRESA EJEMPLO SOCIEDAD ANONIMA DE CAPITAL VARIABLE\nEstado: Activa"
        )
        assert result.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA DE CAPITAL VARIABLE"

    def test_registration_type_parsed(self):
        result = self._parse("Tipo: Sociedad Anonima de Capital Variable\nNombre: ACME")
        assert result.registration_type == "Sociedad Anonima de Capital Variable"

    def test_status_parsed(self):
        result = self._parse("Estado: Activa\nNombre: ACME SA DE CV")
        assert result.status == "Activa"

    def test_details_populated(self):
        result = self._parse("Nombre: EMPRESA SA\nDepartamento: San Salvador")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.sv.empresa import SvEmpresaResult

        r = SvEmpresaResult(
            search_term="ACME SA DE CV",
            company_name="ACME SOCIEDAD ANONIMA DE CAPITAL VARIABLE",
            registration_type="Sociedad Anonima de Capital Variable",
            status="Activa",
        )
        data = r.model_dump_json()
        r2 = SvEmpresaResult.model_validate_json(data)
        assert r2.search_term == "ACME SA DE CV"
        assert r2.company_name == "ACME SOCIEDAD ANONIMA DE CAPITAL VARIABLE"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.empresa import SvEmpresaResult

        r = SvEmpresaResult(search_term="ACME SA", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvEmpresaSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.empresa import SvEmpresaSource

        meta = SvEmpresaSource().meta()
        assert meta.name == "sv.empresa"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.sv.empresa import SvEmpresaSource

        src = SvEmpresaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_company_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"company_name": "EMPRESA TEST SA DE CV"},
        )
        assert inp.extra.get("company_name") == "EMPRESA TEST SA DE CV"

    def test_nit_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"nit": "0614-010180-001-0"},
        )
        assert inp.extra.get("nit") == "0614-010180-001-0"
