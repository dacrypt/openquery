"""Tests for cr.bccr — Costa Rica BCCR economic indicators source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBccrParseResult:
    def _parse(self, body_text: str, indicator: str = "317"):
        from openquery.sources.cr.bccr import BccrSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = BccrSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.indicator_name == ""
        assert result.value == ""
        assert result.period == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="317")
        assert result.indicator == "317"

    def test_parses_value(self):
        body = "Valor: 540.25\nPeríodo: 2024-01\nIndicador: Tipo de cambio venta"
        result = self._parse(body)
        assert result.value == "540.25"

    def test_parses_period(self):
        body = "Período: 2024-01-15\nValor: 540.25"
        result = self._parse(body)
        assert result.period == "2024-01-15"

    def test_model_roundtrip(self):
        from openquery.models.cr.bccr import BccrResult

        r = BccrResult(indicator="317", indicator_name="Tipo de cambio venta", value="540.25")
        data = r.model_dump_json()
        r2 = BccrResult.model_validate_json(data)
        assert r2.indicator == "317"
        assert r2.value == "540.25"

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.bccr import BccrResult

        r = BccrResult(indicator="317", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestBccrSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.bccr import BccrSource

        meta = BccrSource().meta()
        assert meta.name == "cr.bccr"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.cr.bccr import BccrSource

        src = BccrSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
