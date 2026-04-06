"""Unit tests for hn.sefin source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.hn.sefin import HnSefinResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.hn.sefin import HnSefinSource


class TestHnSefinResult:
    """Test HnSefinResult model."""

    def test_default_values(self):
        data = HnSefinResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.budget_amount == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = HnSefinResult(
            search_term="Secretaría de Educación",
            entity_name="SECRETARÍA DE EDUCACIÓN",
            budget_amount="L 5,000,000,000",
            details={"Ejercicio": "2024"},
        )
        json_str = data.model_dump_json()
        restored = HnSefinResult.model_validate_json(json_str)
        assert restored.entity_name == "SECRETARÍA DE EDUCACIÓN"
        assert restored.budget_amount == "L 5,000,000,000"

    def test_audit_excluded_from_json(self):
        data = HnSefinResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestHnSefinSourceMeta:
    """Test HnSefinSource metadata."""

    def test_meta_name(self):
        source = HnSefinSource()
        meta = source.meta()
        assert meta.name == "hn.sefin"

    def test_meta_country(self):
        source = HnSefinSource()
        meta = source.meta()
        assert meta.country == "HN"

    def test_meta_rate_limit(self):
        source = HnSefinSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = HnSefinSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = HnSefinSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = HnSefinSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = HnSefinSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_entity_name_raises(self):
        src = HnSefinSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_entity_name_from_document_number(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Secretaría de Educación",
        )
        assert inp.document_number == "Secretaría de Educación"

    def test_entity_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"entity_name": "Secretaría de Educación"},
        )
        assert inp.extra.get("entity_name") == "Secretaría de Educación"


class TestHnSefinParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Secretaría de Educación"):
        source = HnSefinSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_term)

    def test_parse_entity_name(self):
        result = self._parse(
            "Nombre de la Entidad: SECRETARÍA DE EDUCACIÓN\nPresupuesto: L 5,000,000,000\n"
        )
        assert result.entity_name == "SECRETARÍA DE EDUCACIÓN"

    def test_parse_budget_amount(self):
        result = self._parse(
            "Monto del Presupuesto: L 5,000,000,000\nNombre: SECRETARÍA\n"
        )
        assert result.budget_amount == "L 5,000,000,000"

    def test_parse_presupuesto(self):
        result = self._parse("Presupuesto: L 3,000,000,000\n")
        assert result.budget_amount == "L 3,000,000,000"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Secretaría de Educación"
        assert result.entity_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Ejercicio: 2024\nFuente: Tesoro Nacional\n")
        assert "Ejercicio" in result.details
        assert result.details["Ejercicio"] == "2024"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="SECRETARÍA DE SALUD")
        assert result.search_term == "SECRETARÍA DE SALUD"

    def test_model_roundtrip(self):
        r = HnSefinResult(
            search_term="Secretaría de Educación",
            entity_name="SECRETARÍA DE EDUCACIÓN",
            budget_amount="L 5,000,000,000",
        )
        data = r.model_dump_json()
        r2 = HnSefinResult.model_validate_json(data)
        assert r2.entity_name == "SECRETARÍA DE EDUCACIÓN"
        assert r2.budget_amount == "L 5,000,000,000"
