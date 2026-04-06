"""Unit tests for ve.sudeban — SUDEBAN banking supervisor."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ve.sudeban import SudebanResult
from openquery.sources.ve.sudeban import SudebanSource


class TestSudebanResult:
    def test_default_values(self):
        data = SudebanResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SudebanResult(
            search_term="Banco de Venezuela",
            entity_name="Banco de Venezuela S.A.",
            entity_type="Banco Universal",
            status="Autorizado",
        )
        restored = SudebanResult.model_validate_json(data.model_dump_json())
        assert restored.entity_name == "Banco de Venezuela S.A."
        assert restored.entity_type == "Banco Universal"

    def test_audit_excluded_from_json(self):
        data = SudebanResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestSudebanSourceMeta:
    def test_meta_name(self):
        assert SudebanSource().meta().name == "ve.sudeban"

    def test_meta_country(self):
        assert SudebanSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        assert SudebanSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SudebanSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert SudebanSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SudebanSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_entity_name(self):
        source = SudebanSource()
        page = self._make_page("Institución: Banco de Venezuela S.A.\nTipo: Banco Universal\nEstado: Autorizado\n")  # noqa: E501
        result = source._parse_result(page, "Banco de Venezuela")
        assert result.entity_name == "Banco de Venezuela S.A."

    def test_parse_entity_type(self):
        source = SudebanSource()
        page = self._make_page("Institución: Test\nTipo: Banco Comercial\nEstado: Activo\n")
        result = source._parse_result(page, "Test")
        assert result.entity_type == "Banco Comercial"

    def test_parse_status(self):
        source = SudebanSource()
        page = self._make_page("Institución: Test\nTipo: X\nEstado: Intervenido\n")
        result = source._parse_result(page, "Test")
        assert result.status == "Intervenido"

    def test_parse_preserves_search_term(self):
        source = SudebanSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "Desconocido")
        assert result.search_term == "Desconocido"
