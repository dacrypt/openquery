"""Unit tests for co.sena_egresados — SENA graduate verification."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.sena_egresados import SenaEgresadosResult
from openquery.sources.co.sena_egresados import SenaEgresadosSource


class TestSenaEgresadosResult:
    def test_default_values(self):
        data = SenaEgresadosResult()
        assert data.documento == ""
        assert data.nombre == ""
        assert data.program == ""
        assert data.completion_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SenaEgresadosResult(
            documento="12345678",
            nombre="Juan Pérez",
            program="Técnico en Sistemas",
            completion_status="Certificado",
        )
        restored = SenaEgresadosResult.model_validate_json(data.model_dump_json())
        assert restored.documento == "12345678"
        assert restored.nombre == "Juan Pérez"
        assert restored.completion_status == "Certificado"

    def test_audit_excluded_from_json(self):
        data = SenaEgresadosResult(documento="123", audit={"pdf": "bytes"})
        assert "audit" not in data.model_dump_json()


class TestSenaEgresadosSourceMeta:
    def test_meta_name(self):
        assert SenaEgresadosSource().meta().name == "co.sena_egresados"

    def test_meta_country(self):
        assert SenaEgresadosSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert SenaEgresadosSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert SenaEgresadosSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SenaEgresadosSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nombre(self):
        source = SenaEgresadosSource()
        page = self._make_page("Nombre: Juan Pérez\nPrograma: Técnico en Sistemas\nEstado: Certificado\n")  # noqa: E501
        result = source._parse_result(page, "12345678")
        assert result.nombre == "Juan Pérez"

    def test_parse_program(self):
        source = SenaEgresadosSource()
        page = self._make_page("Nombre: Test\nPrograma: Electrónica\nEstado: Aprobado\n")
        result = source._parse_result(page, "123")
        assert result.program == "Electrónica"

    def test_parse_completion_status(self):
        source = SenaEgresadosSource()
        page = self._make_page("Nombre: Test\nPrograma: X\nEstado: Certificado\n")
        result = source._parse_result(page, "123")
        assert result.completion_status == "Certificado"

    def test_parse_preserves_documento(self):
        source = SenaEgresadosSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "99999999")
        assert result.documento == "99999999"
