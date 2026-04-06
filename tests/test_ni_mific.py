"""Unit tests for ni.mific source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.ni.mific import NiMificResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.ni.mific import NiMificSource


class TestNiMificResult:
    """Test NiMificResult model."""

    def test_default_values(self):
        data = NiMificResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NiMificResult(
            search_term="Empresa Ejemplo",
            company_name="EMPRESA EJEMPLO SA",
            registration_status="Registrado",
            details={"Número": "MIFIC-001"},
        )
        json_str = data.model_dump_json()
        restored = NiMificResult.model_validate_json(json_str)
        assert restored.company_name == "EMPRESA EJEMPLO SA"
        assert restored.registration_status == "Registrado"

    def test_audit_excluded_from_json(self):
        data = NiMificResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestNiMificSourceMeta:
    """Test NiMificSource metadata."""

    def test_meta_name(self):
        source = NiMificSource()
        meta = source.meta()
        assert meta.name == "ni.mific"

    def test_meta_country(self):
        source = NiMificSource()
        meta = source.meta()
        assert meta.country == "NI"

    def test_meta_rate_limit(self):
        source = NiMificSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NiMificSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = NiMificSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = NiMificSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NiMificSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_company_name_raises(self):
        src = NiMificSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_company_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Empresa Ejemplo")
        assert inp.document_number == "Empresa Ejemplo"

    def test_company_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"company_name": "Empresa Ejemplo"},
        )
        assert inp.extra.get("company_name") == "Empresa Ejemplo"


class TestNiMificParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Empresa Ejemplo"):
        source = NiMificSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_company_name(self):
        result = self._parse("Nombre de la Empresa: EMPRESA EJEMPLO SA\nEstado: Registrado\n")
        assert result.company_name == "EMPRESA EJEMPLO SA"

    def test_parse_registration_status(self):
        result = self._parse("Estado de Registro: Registrado\nNombre: EMPRESA EJEMPLO\n")
        assert result.registration_status == "Registrado"

    def test_parse_nombre_comercial(self):
        result = self._parse("Nombre Comercial: EMPRESA ABC\n")
        assert result.company_name == "EMPRESA ABC"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Empresa Ejemplo"
        assert result.company_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Número: MIFIC-001\nFecha: 2020-01-15\n")
        assert "Número" in result.details
        assert result.details["Número"] == "MIFIC-001"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA ESPECIAL")
        assert result.search_term == "EMPRESA ESPECIAL"

    def test_model_roundtrip(self):
        r = NiMificResult(
            search_term="Empresa Ejemplo",
            company_name="EMPRESA EJEMPLO SA",
            registration_status="Registrado",
        )
        data = r.model_dump_json()
        r2 = NiMificResult.model_validate_json(data)
        assert r2.company_name == "EMPRESA EJEMPLO SA"
        assert r2.registration_status == "Registrado"
