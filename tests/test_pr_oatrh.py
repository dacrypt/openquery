"""Unit tests for pr.oatrh source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pr.oatrh import PrOatrhResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pr.oatrh import PrOatrhSource


class TestPrOatrhResult:
    """Test PrOatrhResult model."""

    def test_default_values(self):
        data = PrOatrhResult()
        assert data.search_term == ""
        assert data.employee_name == ""
        assert data.agency == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PrOatrhResult(
            search_term="Juan García",
            employee_name="JUAN GARCÍA",
            agency="Departamento de Hacienda",
            status="Activo",
            details={"Cargo": "Analista"},
        )
        json_str = data.model_dump_json()
        restored = PrOatrhResult.model_validate_json(json_str)
        assert restored.employee_name == "JUAN GARCÍA"
        assert restored.agency == "Departamento de Hacienda"
        assert restored.status == "Activo"

    def test_audit_excluded_from_json(self):
        data = PrOatrhResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestPrOatrhSourceMeta:
    """Test PrOatrhSource metadata."""

    def test_meta_name(self):
        source = PrOatrhSource()
        meta = source.meta()
        assert meta.name == "pr.oatrh"

    def test_meta_country(self):
        source = PrOatrhSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = PrOatrhSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = PrOatrhSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = PrOatrhSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = PrOatrhSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = PrOatrhSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_employee_name_raises(self):
        src = PrOatrhSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_employee_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Juan García")
        assert inp.document_number == "Juan García"

    def test_employee_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"employee_name": "Juan García"},
        )
        assert inp.extra.get("employee_name") == "Juan García"


class TestPrOatrhParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Juan García"):
        source = PrOatrhSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_employee_name(self):
        result = self._parse("Nombre del Empleado: JUAN GARCÍA\nEstado: Activo\n")
        assert result.employee_name == "JUAN GARCÍA"

    def test_parse_agency(self):
        result = self._parse("Agencia: Departamento de Hacienda\nEstado: Activo\n")
        assert result.agency == "Departamento de Hacienda"

    def test_parse_status(self):
        result = self._parse("Estado: Activo\nNombre: JUAN\n")
        assert result.status == "Activo"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Juan García"
        assert result.employee_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Cargo: Analista\nFecha Ingreso: 2015-06-01\n")
        assert "Cargo" in result.details
        assert result.details["Cargo"] == "Analista"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="MARÍA RODRÍGUEZ")
        assert result.search_term == "MARÍA RODRÍGUEZ"

    def test_model_roundtrip(self):
        r = PrOatrhResult(
            search_term="Juan García",
            employee_name="JUAN GARCÍA",
            agency="Hacienda",
            status="Activo",
        )
        data = r.model_dump_json()
        r2 = PrOatrhResult.model_validate_json(data)
        assert r2.employee_name == "JUAN GARCÍA"
        assert r2.status == "Activo"
