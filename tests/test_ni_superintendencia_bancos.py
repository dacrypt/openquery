"""Tests for ni.superintendencia_bancos — Nicaragua SIBOIF banking statistics source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiSuperintendenciaBancosParseResult:
    def _parse(self, body_text: str, indicator: str = "cartera"):
        from openquery.sources.ni.superintendencia_bancos import NiSuperintendenciaBancosSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiSuperintendenciaBancosSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.indicator_name == ""
        assert result.value == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="depositos")
        assert result.indicator == "depositos"

    def test_parses_institution(self):
        body = "Institución: BAC Nicaragua\nValor: 15,000M"
        result = self._parse(body)
        assert result.institution == "BAC Nicaragua"

    def test_model_roundtrip(self):
        from openquery.models.ni.superintendencia_bancos import NiSuperintendenciaBancosResult

        r = NiSuperintendenciaBancosResult(indicator="cartera", value="15B", institution="BAC")
        data = r.model_dump_json()
        r2 = NiSuperintendenciaBancosResult.model_validate_json(data)
        assert r2.indicator == "cartera"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.superintendencia_bancos import NiSuperintendenciaBancosResult

        r = NiSuperintendenciaBancosResult(indicator="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiSuperintendenciaBancosSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.superintendencia_bancos import NiSuperintendenciaBancosSource

        meta = NiSuperintendenciaBancosSource().meta()
        assert meta.name == "ni.superintendencia_bancos"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.ni.superintendencia_bancos import NiSuperintendenciaBancosSource

        src = NiSuperintendenciaBancosSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
