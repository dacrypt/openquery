"""Tests for sv.superintendencia_financiera — El Salvador SSF financial statistics source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvSuperintendenciaFinancieraParseResult:
    def _parse(self, body_text: str, indicator: str = "cartera"):
        from openquery.sources.sv.superintendencia_financiera import (
            SvSuperintendenciaFinancieraSource,
        )

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvSuperintendenciaFinancieraSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.indicator_name == ""
        assert result.value == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="depositos")
        assert result.indicator == "depositos"

    def test_parses_institution(self):
        body = "Institución: Banco Agrícola\nValor: $5,000M"
        result = self._parse(body)
        assert result.institution == "Banco Agrícola"

    def test_parses_value(self):
        body = "Valor: $5,000M\nPeríodo: 2024-Q1"
        result = self._parse(body)
        assert result.value == "$5,000M"

    def test_model_roundtrip(self):
        from openquery.models.sv.superintendencia_financiera import (
            SvSuperintendenciaFinancieraResult,
        )

        r = SvSuperintendenciaFinancieraResult(indicator="cartera", value="$5B", institution="Banco SV")  # noqa: E501
        data = r.model_dump_json()
        r2 = SvSuperintendenciaFinancieraResult.model_validate_json(data)
        assert r2.indicator == "cartera"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.superintendencia_financiera import (
            SvSuperintendenciaFinancieraResult,
        )

        r = SvSuperintendenciaFinancieraResult(indicator="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvSuperintendenciaFinancieraSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.superintendencia_financiera import (
            SvSuperintendenciaFinancieraSource,
        )

        meta = SvSuperintendenciaFinancieraSource().meta()
        assert meta.name == "sv.superintendencia_financiera"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.sv.superintendencia_financiera import (
            SvSuperintendenciaFinancieraSource,
        )

        src = SvSuperintendenciaFinancieraSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
