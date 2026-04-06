"""Unit tests for ni.siboif source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.ni.siboif import NiSiboifResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.ni.siboif import NiSiboifSource


class TestNiSiboifResult:
    """Test NiSiboifResult model."""

    def test_default_values(self):
        data = NiSiboifResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.license_status == ""
        assert data.entity_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NiSiboifResult(
            search_term="Banco de Finanzas",
            entity_name="BANCO DE FINANZAS SA",
            license_status="Autorizado",
            entity_type="Banco Comercial",
            details={"Resolución": "CD-SIBOIF-123"},
        )
        json_str = data.model_dump_json()
        restored = NiSiboifResult.model_validate_json(json_str)
        assert restored.entity_name == "BANCO DE FINANZAS SA"
        assert restored.license_status == "Autorizado"
        assert restored.entity_type == "Banco Comercial"

    def test_audit_excluded_from_json(self):
        data = NiSiboifResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestNiSiboifSourceMeta:
    """Test NiSiboifSource metadata."""

    def test_meta_name(self):
        source = NiSiboifSource()
        meta = source.meta()
        assert meta.name == "ni.siboif"

    def test_meta_country(self):
        source = NiSiboifSource()
        meta = source.meta()
        assert meta.country == "NI"

    def test_meta_rate_limit(self):
        source = NiSiboifSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NiSiboifSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = NiSiboifSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = NiSiboifSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NiSiboifSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_entity_name_raises(self):
        src = NiSiboifSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_entity_name_from_document_number(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM, document_number="Banco de Finanzas"
        )
        assert inp.document_number == "Banco de Finanzas"

    def test_entity_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"entity_name": "Banco de Finanzas"},
        )
        assert inp.extra.get("entity_name") == "Banco de Finanzas"


class TestNiSiboifParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Banco de Finanzas"):
        source = NiSiboifSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_entity_name(self):
        result = self._parse("Nombre de la Entidad: BANCO DE FINANZAS SA\nEstado: Autorizado\n")
        assert result.entity_name == "BANCO DE FINANZAS SA"

    def test_parse_license_status(self):
        result = self._parse("Estado de Licencia: Autorizado\nNombre: BANCO DE FINANZAS\n")
        assert result.license_status == "Autorizado"

    def test_parse_estado(self):
        result = self._parse("Estado: Activo\nNombre: EMPRESA FINANCIERA\n")
        assert result.license_status == "Activo"

    def test_parse_entity_type(self):
        result = self._parse("Tipo de Entidad: Banco Comercial\nNombre: BANCO\n")
        assert result.entity_type == "Banco Comercial"

    def test_parse_english_fields(self):
        result = self._parse(
            "Entity Name: BANCO DE FINANZAS SA\n"
            "License Status: Authorized\n"
            "Entity Type: Commercial Bank\n"
        )
        assert result.entity_name == "BANCO DE FINANZAS SA"
        assert result.license_status == "Authorized"
        assert result.entity_type == "Commercial Bank"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Banco de Finanzas"
        assert result.entity_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Resolución: CD-SIBOIF-123\nFecha: 2020-01-15\n")
        assert "Resolución" in result.details
        assert result.details["Resolución"] == "CD-SIBOIF-123"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="MICROFINANCIERA EJEMPLO")
        assert result.search_term == "MICROFINANCIERA EJEMPLO"

    def test_model_roundtrip(self):
        r = NiSiboifResult(
            search_term="Banco de Finanzas",
            entity_name="BANCO DE FINANZAS SA",
            license_status="Autorizado",
            entity_type="Banco Comercial",
        )
        data = r.model_dump_json()
        r2 = NiSiboifResult.model_validate_json(data)
        assert r2.entity_name == "BANCO DE FINANZAS SA"
        assert r2.license_status == "Autorizado"
