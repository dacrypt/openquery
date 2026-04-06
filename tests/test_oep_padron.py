"""Unit tests for Bolivia OEP electoral registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.bo.oep_padron import OepPadronResult
from openquery.sources.bo.oep_padron import OepPadronSource


class TestOepPadronResult:
    """Test OepPadronResult model."""

    def test_default_values(self):
        data = OepPadronResult()
        assert data.cedula == ""
        assert data.nombre == ""
        assert data.departamento == ""
        assert data.municipio == ""
        assert data.recinto == ""
        assert data.mesa == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OepPadronResult(
            cedula="12345678",
            nombre="JUAN PEREZ LOPEZ",
            departamento="LA PAZ",
            municipio="LA PAZ",
            recinto="UNIDAD EDUCATIVA TEST",
            mesa="001",
            details={"zona": "Norte"},
        )
        json_str = data.model_dump_json()
        restored = OepPadronResult.model_validate_json(json_str)
        assert restored.cedula == "12345678"
        assert restored.nombre == "JUAN PEREZ LOPEZ"
        assert restored.departamento == "LA PAZ"
        assert restored.municipio == "LA PAZ"
        assert restored.recinto == "UNIDAD EDUCATIVA TEST"
        assert restored.mesa == "001"
        assert restored.details["zona"] == "Norte"

    def test_audit_excluded_from_json(self):
        data = OepPadronResult(cedula="12345678", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}


class TestOepPadronSourceMeta:
    """Test OepPadronSource metadata."""

    def test_meta_name(self):
        source = OepPadronSource()
        meta = source.meta()
        assert meta.name == "bo.oep_padron"

    def test_meta_country(self):
        source = OepPadronSource()
        meta = source.meta()
        assert meta.country == "BO"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = OepPadronSource()
        meta = source.meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = OepPadronSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = OepPadronSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = OepPadronSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = OepPadronSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = OepPadronSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nombre(self):
        source = OepPadronSource()
        page = self._make_page("Padrón Electoral\nNombre: JUAN PEREZ LOPEZ\nDepartamento: LA PAZ\n")
        result = source._parse_result(page, "12345678")
        assert result.cedula == "12345678"
        assert result.nombre == "JUAN PEREZ LOPEZ"

    def test_parse_departamento(self):
        source = OepPadronSource()
        page = self._make_page(
            "Nombre: JUAN PEREZ LOPEZ\nDepartamento: COCHABAMBA\nMunicipio: COCHABAMBA\n"
        )
        result = source._parse_result(page, "12345678")
        assert result.departamento == "COCHABAMBA"

    def test_parse_municipio(self):
        source = OepPadronSource()
        page = self._make_page(
            "Departamento: SANTA CRUZ\n"
            "Municipio: SANTA CRUZ DE LA SIERRA\n"
            "Recinto: UNIDAD EDUCATIVA MODELO\n"
        )
        result = source._parse_result(page, "12345678")
        assert result.municipio == "SANTA CRUZ DE LA SIERRA"

    def test_parse_recinto(self):
        source = OepPadronSource()
        page = self._make_page("Municipio: LA PAZ\nRecinto: UNIDAD EDUCATIVA TEST\nMesa: 042\n")
        result = source._parse_result(page, "12345678")
        assert result.recinto == "UNIDAD EDUCATIVA TEST"

    def test_parse_mesa(self):
        source = OepPadronSource()
        page = self._make_page("Recinto: UNIDAD EDUCATIVA TEST\nMesa: 042\n")
        result = source._parse_result(page, "12345678")
        assert result.mesa == "042"

    def test_parse_cedula_preserved(self):
        source = OepPadronSource()
        page = self._make_page("No se encontró registro electoral.")
        result = source._parse_result(page, "99999999")
        assert result.cedula == "99999999"

    def test_parse_empty_body(self):
        source = OepPadronSource()
        page = self._make_page("")
        result = source._parse_result(page, "12345678")
        assert result.nombre == ""
        assert result.departamento == ""
