"""Tests for gt.registromercantil — Guatemala company registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtRegistroMercantilParseResult:
    def _parse(self, body_text: str, search_term: str = "EMPRESA EJEMPLO SA"):
        from openquery.sources.gt.registromercantil import GtRegistroMercantilSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = GtRegistroMercantilSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.registration_status == ""
        assert result.folio == ""
        assert result.company_type == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA EJEMPLO SA")
        assert result.search_term == "EMPRESA EJEMPLO SA"

    def test_razon_social_parsed(self):
        result = self._parse("Razón Social: EMPRESA EJEMPLO SOCIEDAD ANONIMA\nEstado: Activo")
        assert result.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_empresa_maps_to_company_name(self):
        result = self._parse("Empresa: COMERCIAL LOPEZ SA\nEstado: Activo")
        assert result.company_name == "COMERCIAL LOPEZ SA"

    def test_estado_parsed(self):
        result = self._parse("Razón Social: EMPRESA SA\nEstado: Activa")
        assert result.registration_status == "Activa"

    def test_folio_parsed(self):
        result = self._parse("Razón Social: EMPRESA SA\nFolio: 12345")
        assert result.folio == "12345"

    def test_tipo_maps_to_company_type(self):
        result = self._parse("Razón Social: EMPRESA SA\nTipo: Sociedad Anónima")
        assert result.company_type == "Sociedad Anónima"

    def test_sociedad_maps_to_company_type(self):
        result = self._parse("Razón Social: EMPRESA SA\nSociedad: Responsabilidad Limitada")
        assert result.company_type == "Responsabilidad Limitada"

    def test_details_populated(self):
        result = self._parse("Razón Social: EMPRESA SA\nFecha Inscripcion: 2020-05-10")
        assert isinstance(result.details, dict)
        assert result.details.get("Fecha Inscripcion") == "2020-05-10"

    def test_model_roundtrip(self):
        from openquery.models.gt.registromercantil import GtRegistroMercantilResult

        r = GtRegistroMercantilResult(
            search_term="EMPRESA EJEMPLO SA",
            company_name="EMPRESA EJEMPLO SOCIEDAD ANONIMA",
            registration_status="Activa",
            folio="12345",
            company_type="Sociedad Anónima",
        )
        data = r.model_dump_json()
        r2 = GtRegistroMercantilResult.model_validate_json(data)
        assert r2.search_term == "EMPRESA EJEMPLO SA"
        assert r2.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"
        assert r2.folio == "12345"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.registromercantil import GtRegistroMercantilResult

        r = GtRegistroMercantilResult(search_term="EMPRESA SA", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtRegistroMercantilSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.registromercantil import GtRegistroMercantilSource

        meta = GtRegistroMercantilSource().meta()
        assert meta.name == "gt.registromercantil"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.gt.registromercantil import GtRegistroMercantilSource

        src = GtRegistroMercantilSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_search_term(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="EMPRESA EJEMPLO SA")
        assert qi.document_number == "EMPRESA EJEMPLO SA"
