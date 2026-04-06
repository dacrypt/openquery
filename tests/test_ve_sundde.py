"""Unit tests for ve.sundde — SUNDDE price regulation."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ve.sundde import SunddeResult
from openquery.sources.ve.sundde import SunddeSource


class TestSunddeResult:
    def test_default_values(self):
        data = SunddeResult()
        assert data.search_term == ""
        assert data.product_name == ""
        assert data.regulated_price == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SunddeResult(
            search_term="arroz",
            product_name="Arroz Blanco 1kg",
            regulated_price="Bs. 45.00",
        )
        restored = SunddeResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "arroz"
        assert restored.product_name == "Arroz Blanco 1kg"
        assert restored.regulated_price == "Bs. 45.00"

    def test_audit_excluded_from_json(self):
        data = SunddeResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestSunddeSourceMeta:
    def test_meta_name(self):
        assert SunddeSource().meta().name == "ve.sundde"

    def test_meta_country(self):
        assert SunddeSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        assert SunddeSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SunddeSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert SunddeSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SunddeSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_product_name(self):
        source = SunddeSource()
        page = self._make_page("Producto: Arroz Blanco 1kg\nPrecio: Bs. 45.00\n")
        result = source._parse_result(page, "arroz")
        assert result.product_name == "Arroz Blanco 1kg"

    def test_parse_regulated_price(self):
        source = SunddeSource()
        page = self._make_page("Producto: Harina\nPrecio: Bs. 30.00\n")
        result = source._parse_result(page, "harina")
        assert result.regulated_price == "Bs. 30.00"

    def test_parse_empty_body(self):
        source = SunddeSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "desconocido")
        assert result.search_term == "desconocido"
        assert result.product_name == ""

    def test_parse_preserves_search_term(self):
        source = SunddeSource()
        page = self._make_page("Producto: Leche\nPrecio: Bs. 20.00\n")
        result = source._parse_result(page, "leche")
        assert result.search_term == "leche"
