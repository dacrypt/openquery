"""Unit tests for Argentina SISA health professionals registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.sisa_profesionales import SisaProfesionalesResult
from openquery.sources.ar.sisa_profesionales import SisaProfesionalesSource


class TestSisaProfesionalesResult:
    """Test SisaProfesionalesResult model."""

    def test_default_values(self):
        data = SisaProfesionalesResult()
        assert data.documento == ""
        assert data.nombre == ""
        assert data.profession == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SisaProfesionalesResult(
            documento="12345678",
            nombre="Juan Perez",
            profession="Medico",
            registration_status="Registrado",
        )
        json_str = data.model_dump_json()
        restored = SisaProfesionalesResult.model_validate_json(json_str)
        assert restored.documento == "12345678"
        assert restored.nombre == "Juan Perez"
        assert restored.profession == "Medico"

    def test_audit_excluded_from_json(self):
        data = SisaProfesionalesResult(documento="12345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSisaProfesionalesSourceMeta:
    """Test SisaProfesionalesSource metadata."""

    def test_meta_name(self):
        source = SisaProfesionalesSource()
        assert source.meta().name == "ar.sisa_profesionales"

    def test_meta_country(self):
        source = SisaProfesionalesSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = SisaProfesionalesSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = SisaProfesionalesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SisaProfesionalesSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SisaProfesionalesSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


class TestParseResult:
    """Test SisaProfesionalesSource._parse_result parsing logic."""

    def test_parse_registered(self):
        source = SisaProfesionalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Juan Perez\n"
            "Profesion: Medico\n"
            "Estado: Activo\n"
            "Profesional registrado habilitado\n"
        )
        result = source._parse_result(mock_page, "12345678")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = SisaProfesionalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "00000000")
        assert result.details["found"] is False
        assert result.registration_status == "No encontrado"

    def test_query_requires_cedula(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = SisaProfesionalesSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="12345678")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "ar.sisa_profesionales" in str(e)
