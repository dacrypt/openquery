"""Unit tests for co.sisben_consulta — SISBEN social targeting system."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.sisben_consulta import SisbenConsultaResult
from openquery.sources.co.sisben_consulta import SisbenConsultaSource


class TestSisbenConsultaResult:
    def test_default_values(self):
        data = SisbenConsultaResult()
        assert data.documento == ""
        assert data.nombre == ""
        assert data.grupo == ""
        assert data.subgrupo == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SisbenConsultaResult(
            documento="12345678",
            nombre="María López",
            grupo="C",
            subgrupo="C2",
        )
        restored = SisbenConsultaResult.model_validate_json(data.model_dump_json())
        assert restored.documento == "12345678"
        assert restored.grupo == "C"
        assert restored.subgrupo == "C2"

    def test_audit_excluded_from_json(self):
        data = SisbenConsultaResult(documento="123", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestSisbenConsultaSourceMeta:
    def test_meta_name(self):
        assert SisbenConsultaSource().meta().name == "co.sisben_consulta"

    def test_meta_country(self):
        assert SisbenConsultaSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert SisbenConsultaSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert SisbenConsultaSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SisbenConsultaSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nombre(self):
        source = SisbenConsultaSource()
        page = self._make_page("Nombre: María López\nGrupo: C\nSubgrupo: C2\n")
        result = source._parse_result(page, "12345678")
        assert result.nombre == "María López"

    def test_parse_grupo(self):
        source = SisbenConsultaSource()
        page = self._make_page("Nombre: Test\nGrupo: B\nSubgrupo: B5\n")
        result = source._parse_result(page, "123")
        assert result.grupo == "B"

    def test_parse_subgrupo(self):
        source = SisbenConsultaSource()
        page = self._make_page("Nombre: Test\nGrupo: A\nSubgrupo: A1\n")
        result = source._parse_result(page, "123")
        assert result.subgrupo == "A1"

    def test_parse_preserves_documento(self):
        source = SisbenConsultaSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "99887766")
        assert result.documento == "99887766"
