"""Tests for py.seprelad — Paraguay SEPRELAD PEP/sanctions source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSepreladParseResult:
    def _parse(self, body_text: str, search_term: str = "funcionario test"):
        from openquery.sources.py.seprelad import SepreladSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SepreladSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.found is False
        assert result.entity_name == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Juan PY")
        assert result.search_term == "Juan PY"

    def test_found_on_pep_keyword(self):
        result = self._parse("PEP: encontrado\nRegistro activo")
        assert result.found is True

    def test_parses_list_type(self):
        body = "Lista: PEP Nacional\nEstado: Activo"
        result = self._parse(body)
        assert result.list_type == "PEP Nacional"

    def test_model_roundtrip(self):
        from openquery.models.py.seprelad import SepreladResult

        r = SepreladResult(search_term="test", found=True, list_type="PEP")
        data = r.model_dump_json()
        r2 = SepreladResult.model_validate_json(data)
        assert r2.found is True

    def test_audit_excluded_from_json(self):
        from openquery.models.py.seprelad import SepreladResult

        r = SepreladResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSepreladSourceMeta:
    def test_meta(self):
        from openquery.sources.py.seprelad import SepreladSource

        meta = SepreladSource().meta()
        assert meta.name == "py.seprelad"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.py.seprelad import SepreladSource

        src = SepreladSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
