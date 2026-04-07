"""Tests for hn.ihtt — Honduras IHT tourism establishment registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIhttParseResult:
    def _parse(self, body_text: str, search_term: str = "Hotel Test"):
        from openquery.sources.hn.ihtt import IhttSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = IhttSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.establishment_name == ""
        assert result.license_number == ""
        assert result.license_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Hostal HN")
        assert result.search_term == "Hostal HN"

    def test_parses_establishment_name(self):
        body = "Nombre: Hotel Honduras Central\nEstado: Autorizado"
        result = self._parse(body)
        assert result.establishment_name == "Hotel Honduras Central"

    def test_parses_license_status(self):
        body = "Tipo: Hotel\nEstado: Autorizado"
        result = self._parse(body)
        assert result.license_status == "Autorizado"

    def test_model_roundtrip(self):
        from openquery.models.hn.ihtt import IhttResult

        r = IhttResult(search_term="test", establishment_name="Hotel HN", license_status="Activo")
        data = r.model_dump_json()
        r2 = IhttResult.model_validate_json(data)
        assert r2.establishment_name == "Hotel HN"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.ihtt import IhttResult

        r = IhttResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestIhttSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.ihtt import IhttSource

        meta = IhttSource().meta()
        assert meta.name == "hn.ihtt"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.hn.ihtt import IhttSource

        src = IhttSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
