"""Tests for ve.oncdoft — Venezuela ONCDOFT/SUNDDE price regulation source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestVeOncdoftParseResult:
    def _parse(self, body_text: str, search_term: str = "harina"):
        from openquery.sources.ve.oncdoft import VeOncdoftSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = VeOncdoftSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.product_name == ""
        assert result.regulated_price == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="harina de maiz")
        assert result.search_term == "harina de maiz"

    def test_product_name_parsed(self):
        result = self._parse("Producto: Harina de Maíz Precocida\nPrecio: 5.00 Bs")
        assert result.product_name == "Harina de Maíz Precocida"

    def test_regulated_price_parsed(self):
        result = self._parse("Producto: Aceite\nPrecio: 12.50 Bs")
        assert result.regulated_price == "12.50 Bs"

    def test_details_populated(self):
        result = self._parse("Producto: Azúcar\nPrecio: 3.00")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.ve.oncdoft import VeOncdoftResult

        r = VeOncdoftResult(
            search_term="harina",
            product_name="Harina de Maíz",
            regulated_price="5.00 Bs",
        )
        data = r.model_dump_json()
        r2 = VeOncdoftResult.model_validate_json(data)
        assert r2.search_term == "harina"
        assert r2.product_name == "Harina de Maíz"
        assert r2.regulated_price == "5.00 Bs"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.oncdoft import VeOncdoftResult

        r = VeOncdoftResult(search_term="harina", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestVeOncdoftSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.oncdoft import VeOncdoftSource

        meta = VeOncdoftSource().meta()
        assert meta.name == "ve.oncdoft"
        assert meta.country == "VE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_product_raises(self):
        from openquery.sources.ve.oncdoft import VeOncdoftSource

        src = VeOncdoftSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
