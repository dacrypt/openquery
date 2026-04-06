"""Unit tests for Uruguay MSP health professionals source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.uy.msp_profesionales import MspProfesionalesResult
from openquery.sources.uy.msp_profesionales import MspProfesionalesSource


class TestMspProfesionalesResult:
    """Test MspProfesionalesResult model."""

    def test_default_values(self):
        data = MspProfesionalesResult()
        assert data.search_term == ""
        assert data.professional_name == ""
        assert data.profession == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = MspProfesionalesResult(
            search_term="Maria Lopez",
            professional_name="Maria Lopez Gomez",
            profession="Enfermera",
            registration_status="Registrado",
        )
        json_str = data.model_dump_json()
        restored = MspProfesionalesResult.model_validate_json(json_str)
        assert restored.search_term == "Maria Lopez"
        assert restored.profession == "Enfermera"

    def test_audit_excluded_from_json(self):
        data = MspProfesionalesResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestMspProfesionalesSourceMeta:
    """Test MspProfesionalesSource metadata."""

    def test_meta_name(self):
        source = MspProfesionalesSource()
        assert source.meta().name == "uy.msp_profesionales"

    def test_meta_country(self):
        source = MspProfesionalesSource()
        assert source.meta().country == "UY"

    def test_meta_requires_browser(self):
        source = MspProfesionalesSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = MspProfesionalesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = MspProfesionalesSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = MspProfesionalesSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test MspProfesionalesSource._parse_result parsing logic."""

    def test_parse_registered(self):
        source = MspProfesionalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Maria Lopez Gomez\n"
            "Profesion: Enfermera\n"
            "Estado: Activo\n"
            "Profesional registrado habilitado\n"
        )
        result = source._parse_result(mock_page, "Maria Lopez")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = MspProfesionalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False

    def test_query_requires_professional_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = MspProfesionalesSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "uy.msp_profesionales" in str(e)
