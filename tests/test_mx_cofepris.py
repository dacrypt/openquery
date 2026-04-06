"""Tests for mx.cofepris — COFEPRIS health product sanitary registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestCofeprisResult:
    """Test CofeprisResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.mx.cofepris import CofeprisResult

        r = CofeprisResult()
        assert r.search_term == ""
        assert r.product_name == ""
        assert r.registration_number == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.mx.cofepris import CofeprisResult

        r = CofeprisResult(search_term="aspirina", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "aspirina" in dumped

    def test_json_roundtrip(self):
        from openquery.models.mx.cofepris import CofeprisResult

        r = CofeprisResult(
            search_term="aspirina",
            product_name="ASPIRINA 500MG",
            registration_number="COFEPRIS-123456",
            status="Vigente",
            details={"Tipo": "Medicamento"},
        )
        r2 = CofeprisResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "aspirina"
        assert r2.product_name == "ASPIRINA 500MG"
        assert r2.registration_number == "COFEPRIS-123456"

    def test_queried_at_default(self):
        from openquery.models.mx.cofepris import CofeprisResult

        before = datetime.now()
        r = CofeprisResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestCofeprisSourceMeta:
    """Test mx.cofepris source metadata."""

    def test_meta_name(self):
        from openquery.sources.mx.cofepris import CofeprisSource

        assert CofeprisSource().meta().name == "mx.cofepris"

    def test_meta_country(self):
        from openquery.sources.mx.cofepris import CofeprisSource

        assert CofeprisSource().meta().country == "MX"

    def test_meta_requires_browser(self):
        from openquery.sources.mx.cofepris import CofeprisSource

        assert CofeprisSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.mx.cofepris import CofeprisSource

        assert DocumentType.CUSTOM in CofeprisSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.mx.cofepris import CofeprisSource

        assert CofeprisSource().meta().rate_limit_rpm == 10


class TestCofeprisParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, search_term: str = "aspirina"):
        from openquery.sources.mx.cofepris import CofeprisSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return CofeprisSource()._parse_result(page, search_term)

    def test_search_term_preserved(self):
        assert self._parse("Datos").search_term == "aspirina"

    def test_product_name_parsed(self):
        result = self._parse("Denominación: ASPIRINA 500MG\nOtros")
        assert result.product_name == "ASPIRINA 500MG"

    def test_registration_number_parsed(self):
        result = self._parse("Registro: COFEPRIS-123456\nOtros")
        assert result.registration_number == "COFEPRIS-123456"

    def test_status_parsed(self):
        result = self._parse("Estado: Vigente\nOtros")
        assert result.status == "Vigente"

    def test_empty_body(self):
        result = self._parse("")
        assert result.search_term == "aspirina"
        assert result.product_name == ""

    def test_query_missing_search_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.mx.cofepris import CofeprisSource

        with pytest.raises(SourceError, match="[Pp]roduct"):
            CofeprisSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
