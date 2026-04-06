"""Unit tests for ni.minsa source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.ni.minsa import NiMinsaResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.ni.minsa import NiMinsaSource


class TestNiMinsaResult:
    """Test NiMinsaResult model."""

    def test_default_values(self):
        data = NiMinsaResult()
        assert data.search_term == ""
        assert data.establishment_name == ""
        assert data.permit_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NiMinsaResult(
            search_term="Farmacia Ejemplo",
            establishment_name="FARMACIA EJEMPLO",
            permit_status="Habilitado",
            details={"Código": "MINSA-001"},
        )
        json_str = data.model_dump_json()
        restored = NiMinsaResult.model_validate_json(json_str)
        assert restored.establishment_name == "FARMACIA EJEMPLO"
        assert restored.permit_status == "Habilitado"

    def test_audit_excluded_from_json(self):
        data = NiMinsaResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestNiMinsaSourceMeta:
    """Test NiMinsaSource metadata."""

    def test_meta_name(self):
        source = NiMinsaSource()
        meta = source.meta()
        assert meta.name == "ni.minsa"

    def test_meta_country(self):
        source = NiMinsaSource()
        meta = source.meta()
        assert meta.country == "NI"

    def test_meta_rate_limit(self):
        source = NiMinsaSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NiMinsaSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = NiMinsaSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = NiMinsaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NiMinsaSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_establishment_name_raises(self):
        src = NiMinsaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_establishment_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Farmacia Ejemplo")
        assert inp.document_number == "Farmacia Ejemplo"

    def test_establishment_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"establishment_name": "Farmacia Ejemplo"},
        )
        assert inp.extra.get("establishment_name") == "Farmacia Ejemplo"


class TestNiMinsaParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Farmacia Ejemplo"):
        source = NiMinsaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_establishment_name(self):
        result = self._parse(
            "Nombre del Establecimiento: FARMACIA EJEMPLO\nEstado: Habilitado\n"
        )
        assert result.establishment_name == "FARMACIA EJEMPLO"

    def test_parse_permit_status(self):
        result = self._parse("Estado del Permiso: Habilitado\nNombre: FARMACIA\n")
        assert result.permit_status == "Habilitado"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Farmacia Ejemplo"
        assert result.establishment_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Código: MINSA-001\nFecha: 2020-01-15\n")
        assert "Código" in result.details
        assert result.details["Código"] == "MINSA-001"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="HOSPITAL REGIONAL")
        assert result.search_term == "HOSPITAL REGIONAL"

    def test_model_roundtrip(self):
        r = NiMinsaResult(
            search_term="Farmacia Ejemplo",
            establishment_name="FARMACIA EJEMPLO",
            permit_status="Habilitado",
        )
        data = r.model_dump_json()
        r2 = NiMinsaResult.model_validate_json(data)
        assert r2.establishment_name == "FARMACIA EJEMPLO"
        assert r2.permit_status == "Habilitado"
