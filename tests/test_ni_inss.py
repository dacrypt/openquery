"""Unit tests for ni.inss source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.ni.inss import NiInssResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.ni.inss import NiInssSource


class TestNiInssResult:
    """Test NiInssResult model."""

    def test_default_values(self):
        data = NiInssResult()
        assert data.cedula == ""
        assert data.affiliation_status == ""
        assert data.employer == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NiInssResult(
            cedula="001-010190-0001A",
            affiliation_status="Activo",
            employer="EMPRESA EJEMPLO SA",
            details={"Número INSS": "123456"},
        )
        json_str = data.model_dump_json()
        restored = NiInssResult.model_validate_json(json_str)
        assert restored.cedula == "001-010190-0001A"
        assert restored.affiliation_status == "Activo"
        assert restored.employer == "EMPRESA EJEMPLO SA"

    def test_audit_excluded_from_json(self):
        data = NiInssResult(cedula="001-010190-0001A", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestNiInssSourceMeta:
    """Test NiInssSource metadata."""

    def test_meta_name(self):
        source = NiInssSource()
        meta = source.meta()
        assert meta.name == "ni.inss"

    def test_meta_country(self):
        source = NiInssSource()
        meta = source.meta()
        assert meta.country == "NI"

    def test_meta_rate_limit(self):
        source = NiInssSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NiInssSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = NiInssSource()
        meta = source.meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_default_timeout(self):
        source = NiInssSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NiInssSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_cedula_raises(self):
        src = NiInssSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_cedula_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CEDULA, document_number="001-010190-0001A")
        assert inp.document_number == "001-010190-0001A"

    def test_inss_number_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="",
            extra={"inss_number": "123456"},
        )
        assert inp.extra.get("inss_number") == "123456"


class TestNiInssParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, cedula: str = "001-010190-0001A"):
        source = NiInssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, cedula)

    def test_parse_affiliation_status(self):
        result = self._parse("Afiliación: Activo\nEmpleador: EMPRESA EJEMPLO SA\n")
        assert result.affiliation_status == "Activo"

    def test_parse_estado(self):
        result = self._parse("Estado: Activo\nEmpleador: EMPRESA EJEMPLO SA\n")
        assert result.affiliation_status == "Activo"

    def test_parse_employer(self):
        result = self._parse("Empleador: EMPRESA EJEMPLO SA\nEstado: Activo\n")
        assert result.employer == "EMPRESA EJEMPLO SA"

    def test_parse_empresa(self):
        result = self._parse("Empresa: EMPRESA NICARAGUA SRL\nEstado: Activo\n")
        assert result.employer == "EMPRESA NICARAGUA SRL"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.cedula == "001-010190-0001A"
        assert result.affiliation_status == ""
        assert result.employer == ""
        assert result.details == {}

    def test_cedula_preserved(self):
        result = self._parse("", cedula="001-010190-0001A")
        assert result.cedula == "001-010190-0001A"

    def test_parse_details_collected(self):
        result = self._parse("Número INSS: 123456\nEstado: Activo\n")
        assert isinstance(result.details, dict)
        assert "Número INSS" in result.details

    def test_model_roundtrip(self):
        r = NiInssResult(
            cedula="001-010190-0001A",
            affiliation_status="Activo",
            employer="EMPRESA EJEMPLO SA",
        )
        data = r.model_dump_json()
        r2 = NiInssResult.model_validate_json(data)
        assert r2.cedula == "001-010190-0001A"
        assert r2.affiliation_status == "Activo"
