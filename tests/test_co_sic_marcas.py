"""Unit tests for co.sic_marcas — SIC trademark registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.sic_marcas import SicMarcasResult
from openquery.sources.co.sic_marcas import SicMarcasSource


class TestSicMarcasResult:
    def test_default_values(self):
        data = SicMarcasResult()
        assert data.search_term == ""
        assert data.trademark_name == ""
        assert data.owner == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SicMarcasResult(
            search_term="CAFÉ EXPRESS",
            trademark_name="CAFÉ EXPRESS",
            owner="Empresa XYZ S.A.S.",
            status="Registrada",
        )
        restored = SicMarcasResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "CAFÉ EXPRESS"
        assert restored.trademark_name == "CAFÉ EXPRESS"
        assert restored.owner == "Empresa XYZ S.A.S."
        assert restored.status == "Registrada"

    def test_audit_excluded_from_json(self):
        data = SicMarcasResult(search_term="TEST", audit={"evidence": "bytes"})
        assert "audit" not in data.model_dump_json()
        assert data.audit == {"evidence": "bytes"}


class TestSicMarcasSourceMeta:
    def test_meta_name(self):
        assert SicMarcasSource().meta().name == "co.sic_marcas"

    def test_meta_country(self):
        assert SicMarcasSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert SicMarcasSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SicMarcasSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert SicMarcasSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SicMarcasSource()._timeout == 30.0

    def test_custom_timeout(self):
        assert SicMarcasSource(timeout=60.0)._timeout == 60.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_trademark_name(self):
        source = SicMarcasSource()
        page = self._make_page("Marca: CAFÉ EXPRESS\nTitular: XYZ S.A.S.\nEstado: Registrada\n")
        result = source._parse_result(page, "CAFÉ EXPRESS")
        assert result.search_term == "CAFÉ EXPRESS"
        assert result.trademark_name == "CAFÉ EXPRESS"

    def test_parse_owner(self):
        source = SicMarcasSource()
        page = self._make_page("Marca: TEST\nTitular: Empresa ABC\nEstado: Activa\n")
        result = source._parse_result(page, "TEST")
        assert result.owner == "Empresa ABC"

    def test_parse_status(self):
        source = SicMarcasSource()
        page = self._make_page("Marca: TEST\nTitular: ABC\nEstado: Registrada\n")
        result = source._parse_result(page, "TEST")
        assert result.status == "Registrada"

    def test_parse_empty_body(self):
        source = SicMarcasSource()
        page = self._make_page("No results found.")
        result = source._parse_result(page, "UNKNOWN")
        assert result.search_term == "UNKNOWN"
        assert result.trademark_name == ""
