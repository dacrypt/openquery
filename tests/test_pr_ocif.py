"""Unit tests for pr.ocif source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pr.ocif import PrOcifResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pr.ocif import PrOcifSource


class TestPrOcifResult:
    """Test PrOcifResult model."""

    def test_default_values(self):
        data = PrOcifResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PrOcifResult(
            search_term="Banco Popular",
            entity_name="BANCO POPULAR DE PUERTO RICO",
            entity_type="Banco Comercial",
            status="Activo",
            details={"Licencia": "BC-001"},
        )
        json_str = data.model_dump_json()
        restored = PrOcifResult.model_validate_json(json_str)
        assert restored.entity_name == "BANCO POPULAR DE PUERTO RICO"
        assert restored.entity_type == "Banco Comercial"
        assert restored.status == "Activo"

    def test_audit_excluded_from_json(self):
        data = PrOcifResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestPrOcifSourceMeta:
    """Test PrOcifSource metadata."""

    def test_meta_name(self):
        source = PrOcifSource()
        meta = source.meta()
        assert meta.name == "pr.ocif"

    def test_meta_country(self):
        source = PrOcifSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = PrOcifSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = PrOcifSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = PrOcifSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = PrOcifSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = PrOcifSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_entity_name_raises(self):
        src = PrOcifSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_entity_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Banco Popular")
        assert inp.document_number == "Banco Popular"

    def test_entity_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"entity_name": "Banco Popular"},
        )
        assert inp.extra.get("entity_name") == "Banco Popular"


class TestPrOcifParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Banco Popular"):
        source = PrOcifSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_entity_name(self):
        result = self._parse(
            "Nombre de la Entidad: BANCO POPULAR DE PR\nEstado: Activo\n"
        )
        assert result.entity_name == "BANCO POPULAR DE PR"

    def test_parse_entity_type(self):
        result = self._parse("Tipo de Entidad: Banco Comercial\nNombre: BANCO\n")
        assert result.entity_type == "Banco Comercial"

    def test_parse_status(self):
        result = self._parse("Estado: Activo\nNombre: BANCO POPULAR\n")
        assert result.status == "Activo"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Banco Popular"
        assert result.entity_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Licencia: BC-001\nFecha: 2000-01-01\n")
        assert "Licencia" in result.details
        assert result.details["Licencia"] == "BC-001"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="FIRSTBANK")
        assert result.search_term == "FIRSTBANK"

    def test_model_roundtrip(self):
        r = PrOcifResult(
            search_term="Banco Popular",
            entity_name="BANCO POPULAR DE PR",
            entity_type="Banco Comercial",
            status="Activo",
        )
        data = r.model_dump_json()
        r2 = PrOcifResult.model_validate_json(data)
        assert r2.entity_name == "BANCO POPULAR DE PR"
        assert r2.status == "Activo"
