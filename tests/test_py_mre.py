"""Unit tests for py.mre source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.py.mre import PyMreResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.py.mre import PyMreSource


class TestPyMreResult:
    """Test PyMreResult model."""

    def test_default_values(self):
        data = PyMreResult()
        assert data.passport_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PyMreResult(
            passport_number="PY123456",
            status="Vigente",
            details={"Emisión": "2020-01-01"},
        )
        json_str = data.model_dump_json()
        restored = PyMreResult.model_validate_json(json_str)
        assert restored.passport_number == "PY123456"
        assert restored.status == "Vigente"

    def test_audit_excluded_from_json(self):
        data = PyMreResult(passport_number="PY123456", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestPyMreSourceMeta:
    """Test PyMreSource metadata."""

    def test_meta_name(self):
        source = PyMreSource()
        meta = source.meta()
        assert meta.name == "py.mre"

    def test_meta_country(self):
        source = PyMreSource()
        meta = source.meta()
        assert meta.country == "PY"

    def test_meta_rate_limit(self):
        source = PyMreSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = PyMreSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = PyMreSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = PyMreSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = PyMreSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_passport_number_raises(self):
        src = PyMreSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_passport_number_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="PY123456")
        assert inp.document_number == "PY123456"

    def test_passport_number_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"passport_number": "PY123456"},
        )
        assert inp.extra.get("passport_number") == "PY123456"


class TestPyMreParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, passport_number: str = "PY123456"):
        source = PyMreSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, passport_number)

    def test_parse_status(self):
        result = self._parse("Estado: Vigente\nPasaporte: PY123456\n")
        assert result.status == "Vigente"

    def test_parse_passport_status(self):
        result = self._parse("Estado del Pasaporte: Vencido\n")
        assert result.status == "Vencido"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.passport_number == "PY123456"
        assert result.status == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Emisión: 2020-01-01\nVencimiento: 2030-01-01\n")
        assert "Emisión" in result.details
        assert result.details["Emisión"] == "2020-01-01"

    def test_passport_number_preserved(self):
        result = self._parse("", passport_number="PY999999")
        assert result.passport_number == "PY999999"

    def test_model_roundtrip(self):
        r = PyMreResult(passport_number="PY123456", status="Vigente")
        data = r.model_dump_json()
        r2 = PyMreResult.model_validate_json(data)
        assert r2.passport_number == "PY123456"
        assert r2.status == "Vigente"
