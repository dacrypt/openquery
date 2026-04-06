"""Unit tests for uy.msp source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.uy.msp import UyMspResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.uy.msp import UyMspSource


class TestUyMspResult:
    """Test UyMspResult model."""

    def test_default_values(self):
        data = UyMspResult()
        assert data.search_term == ""
        assert data.facility_name == ""
        assert data.permit_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = UyMspResult(
            search_term="Clínica Ejemplo",
            facility_name="CLÍNICA EJEMPLO SA",
            permit_status="Habilitado",
            details={"Código": "MSP-001"},
        )
        json_str = data.model_dump_json()
        restored = UyMspResult.model_validate_json(json_str)
        assert restored.facility_name == "CLÍNICA EJEMPLO SA"
        assert restored.permit_status == "Habilitado"

    def test_audit_excluded_from_json(self):
        data = UyMspResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestUyMspSourceMeta:
    """Test UyMspSource metadata."""

    def test_meta_name(self):
        source = UyMspSource()
        meta = source.meta()
        assert meta.name == "uy.msp"

    def test_meta_country(self):
        source = UyMspSource()
        meta = source.meta()
        assert meta.country == "UY"

    def test_meta_rate_limit(self):
        source = UyMspSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = UyMspSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = UyMspSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = UyMspSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = UyMspSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_facility_name_raises(self):
        src = UyMspSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_facility_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Clínica Ejemplo")
        assert inp.document_number == "Clínica Ejemplo"

    def test_facility_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"facility_name": "Clínica Ejemplo"},
        )
        assert inp.extra.get("facility_name") == "Clínica Ejemplo"


class TestUyMspParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Clínica Ejemplo"):
        source = UyMspSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_facility_name(self):
        result = self._parse(
            "Nombre del Establecimiento: CLÍNICA EJEMPLO SA\nEstado: Habilitado\n"
        )
        assert result.facility_name == "CLÍNICA EJEMPLO SA"

    def test_parse_permit_status(self):
        result = self._parse("Estado del Permiso: Habilitado\nNombre: CLÍNICA\n")
        assert result.permit_status == "Habilitado"

    def test_parse_habilitacion(self):
        result = self._parse("Estado de Habilitación: Vigente\n")
        assert result.permit_status == "Vigente"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Clínica Ejemplo"
        assert result.facility_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Código: MSP-001\nFecha: 2020-01-15\n")
        assert "Código" in result.details

    def test_search_term_preserved(self):
        result = self._parse("", search_term="HOSPITAL MACIEL")
        assert result.search_term == "HOSPITAL MACIEL"

    def test_model_roundtrip(self):
        r = UyMspResult(
            search_term="Clínica Ejemplo",
            facility_name="CLÍNICA EJEMPLO SA",
            permit_status="Habilitado",
        )
        data = r.model_dump_json()
        r2 = UyMspResult.model_validate_json(data)
        assert r2.facility_name == "CLÍNICA EJEMPLO SA"
        assert r2.permit_status == "Habilitado"
