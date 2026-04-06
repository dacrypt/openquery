"""Unit tests for Ecuador DINARDAP identity and property lookup source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.dinardap import DinardapResult
from openquery.sources.ec.dinardap import DinardapSource


class TestDinardapResult:
    """Test DinardapResult model."""

    def test_default_values(self):
        data = DinardapResult()
        assert data.cedula == ""
        assert data.nombre == ""
        assert data.property_records == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = DinardapResult(
            cedula="1234567890",
            nombre="JUAN PEREZ LOPEZ",
            property_records=["Predio 001 - Quito"],
            details={"estado_civil": "SOLTERO"},
        )
        json_str = data.model_dump_json()
        restored = DinardapResult.model_validate_json(json_str)
        assert restored.cedula == "1234567890"
        assert restored.nombre == "JUAN PEREZ LOPEZ"
        assert restored.property_records == ["Predio 001 - Quito"]
        assert restored.details["estado_civil"] == "SOLTERO"

    def test_audit_excluded_from_json(self):
        data = DinardapResult(cedula="1234567890", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}


class TestDinardapSourceMeta:
    """Test DinardapSource metadata."""

    def test_meta_name(self):
        source = DinardapSource()
        meta = source.meta()
        assert meta.name == "ec.dinardap"

    def test_meta_country(self):
        source = DinardapSource()
        meta = source.meta()
        assert meta.country == "EC"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = DinardapSource()
        meta = source.meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = DinardapSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = DinardapSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = DinardapSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = DinardapSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = DinardapSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nombre(self):
        source = DinardapSource()
        page = self._make_page(
            "Consulta de Datos\n"
            "Nombre: JUAN PEREZ LOPEZ\n"
            "Estado Civil: SOLTERO\n"
        )
        result = source._parse_result(page, "1234567890")
        assert result.cedula == "1234567890"
        assert result.nombre == "JUAN PEREZ LOPEZ"

    def test_parse_property_records(self):
        source = DinardapSource()
        page = self._make_page(
            "Nombre: JUAN PEREZ LOPEZ\n"
            "Predio: Lote 5 Sector Norte\n"
            "Predio: Apartamento 3B Torre A\n"
        )
        result = source._parse_result(page, "1234567890")
        assert len(result.property_records) == 2
        assert "Lote 5 Sector Norte" in result.property_records

    def test_parse_details(self):
        source = DinardapSource()
        page = self._make_page(
            "Nombre: JUAN PEREZ LOPEZ\n"
            "Estado Civil: CASADO\n"
            "Fecha Nacimiento: 01/01/1980\n"
        )
        result = source._parse_result(page, "1234567890")
        assert "Estado Civil" in result.details
        assert result.details["Estado Civil"] == "CASADO"

    def test_parse_cedula_preserved(self):
        source = DinardapSource()
        page = self._make_page("No se encontraron resultados.")
        result = source._parse_result(page, "9999999999")
        assert result.cedula == "9999999999"

    def test_parse_empty_body(self):
        source = DinardapSource()
        page = self._make_page("")
        result = source._parse_result(page, "1234567890")
        assert result.nombre == ""
        assert result.property_records == []
