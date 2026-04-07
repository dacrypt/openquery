"""Tests for ni.inss_estadisticas — Nicaragua INSS statistics source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestInssEstadisticasParseResult:
    def _parse(self, body_text: str, indicator: str = "asegurados"):
        from openquery.sources.ni.inss_estadisticas import InssEstadisticasSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = InssEstadisticasSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.indicator_name == ""
        assert result.value == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="pensionados")
        assert result.indicator == "pensionados"

    def test_parses_value(self):
        body = "Valor: 850,000\nPeríodo: 2024"
        result = self._parse(body)
        assert result.value == "850,000"

    def test_model_roundtrip(self):
        from openquery.models.ni.inss_estadisticas import InssEstadisticasResult

        r = InssEstadisticasResult(indicator="asegurados", value="850000", period="2024")
        data = r.model_dump_json()
        r2 = InssEstadisticasResult.model_validate_json(data)
        assert r2.indicator == "asegurados"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.inss_estadisticas import InssEstadisticasResult

        r = InssEstadisticasResult(indicator="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestInssEstadisticasSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.inss_estadisticas import InssEstadisticasSource

        meta = InssEstadisticasSource().meta()
        assert meta.name == "ni.inss_estadisticas"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.ni.inss_estadisticas import InssEstadisticasSource

        src = InssEstadisticasSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
