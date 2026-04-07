"""Tests for gt.inacif — Guatemala INACIF forensic registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestInacifParseResult:
    def _parse(self, body_text: str, case_number: str = "GT-2024-001"):
        from openquery.sources.gt.inacif import InacifSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = InacifSource()
        return src._parse_result(page, case_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.case_type == ""
        assert result.status == ""

    def test_case_number_preserved(self):
        result = self._parse("", case_number="GT-2024-999")
        assert result.case_number == "GT-2024-999"

    def test_parses_case_type(self):
        body = "Tipo: Necropsia\nEstado: Cerrado"
        result = self._parse(body)
        assert result.case_type == "Necropsia"

    def test_parses_status(self):
        body = "Estado: En proceso\nFecha: 2024-01-15"
        result = self._parse(body)
        assert result.status == "En proceso"

    def test_model_roundtrip(self):
        from openquery.models.gt.inacif import InacifResult

        r = InacifResult(case_number="GT-001", case_type="Necropsia", status="Cerrado")
        data = r.model_dump_json()
        r2 = InacifResult.model_validate_json(data)
        assert r2.case_number == "GT-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.inacif import InacifResult

        r = InacifResult(case_number="GT-001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestInacifSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.inacif import InacifSource

        meta = InacifSource().meta()
        assert meta.name == "gt.inacif"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_case_raises(self):
        from openquery.sources.gt.inacif import InacifSource

        src = InacifSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
