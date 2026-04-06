"""Unit tests for co.supernotariado — Supernotariado notary registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.supernotariado import SupernotariadoResult
from openquery.sources.co.supernotariado import SupernotariadoSource


class TestSupernotariadoResult:
    def test_default_values(self):
        data = SupernotariadoResult()
        assert data.search_term == ""
        assert data.notary_name == ""
        assert data.city == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SupernotariadoResult(
            search_term="Notaría 1 Bogotá",
            notary_name="Notaría Primera de Bogotá",
            city="Bogotá",
            status="Activa",
        )
        restored = SupernotariadoResult.model_validate_json(data.model_dump_json())
        assert restored.notary_name == "Notaría Primera de Bogotá"
        assert restored.city == "Bogotá"

    def test_audit_excluded_from_json(self):
        data = SupernotariadoResult(search_term="TEST", audit={"pdf": "bytes"})
        assert "audit" not in data.model_dump_json()
        assert data.audit == {"pdf": "bytes"}


class TestSupernotariadoSourceMeta:
    def test_meta_name(self):
        assert SupernotariadoSource().meta().name == "co.supernotariado"

    def test_meta_country(self):
        assert SupernotariadoSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert SupernotariadoSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert SupernotariadoSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SupernotariadoSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_notary_name(self):
        source = SupernotariadoSource()
        page = self._make_page("Notaría: Notaría Primera de Bogotá\nCiudad: Bogotá\nEstado: Activa\n")  # noqa: E501
        result = source._parse_result(page, "Notaría 1")
        assert result.notary_name == "Notaría Primera de Bogotá"

    def test_parse_city(self):
        source = SupernotariadoSource()
        page = self._make_page("Notaría: TEST\nCiudad: Medellín\nEstado: Activa\n")
        result = source._parse_result(page, "TEST")
        assert result.city == "Medellín"

    def test_parse_status(self):
        source = SupernotariadoSource()
        page = self._make_page("Notaría: TEST\nCiudad: Cali\nEstado: Inactiva\n")
        result = source._parse_result(page, "TEST")
        assert result.status == "Inactiva"

    def test_parse_empty_body(self):
        source = SupernotariadoSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "TEST")
        assert result.search_term == "TEST"
        assert result.notary_name == ""
