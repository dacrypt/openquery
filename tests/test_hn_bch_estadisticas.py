"""Tests for hn.bch_estadisticas — Honduras BCH economic statistics source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBchEstadisticasParseResult:
    def _parse(self, body_text: str, indicator: str = "inflacion"):
        from openquery.sources.hn.bch_estadisticas import BchEstadisticasSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = BchEstadisticasSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.indicator_name == ""
        assert result.value == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="pib")
        assert result.indicator == "pib"

    def test_parses_value(self):
        body = "Valor: 3.5%\nPeríodo: 2024-Q1"
        result = self._parse(body)
        assert result.value == "3.5%"

    def test_model_roundtrip(self):
        from openquery.models.hn.bch_estadisticas import BchEstadisticasResult

        r = BchEstadisticasResult(indicator="inflacion", value="3.5%", period="2024")
        data = r.model_dump_json()
        r2 = BchEstadisticasResult.model_validate_json(data)
        assert r2.indicator == "inflacion"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.bch_estadisticas import BchEstadisticasResult

        r = BchEstadisticasResult(indicator="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestBchEstadisticasSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.bch_estadisticas import BchEstadisticasSource

        meta = BchEstadisticasSource().meta()
        assert meta.name == "hn.bch_estadisticas"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.hn.bch_estadisticas import BchEstadisticasSource

        src = BchEstadisticasSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
