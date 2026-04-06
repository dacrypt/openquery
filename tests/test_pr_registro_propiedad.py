"""Unit tests for pr.registro_propiedad source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pr.registro_propiedad import RegistroPropiedadResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pr.registro_propiedad import RegistroPropiedadSource


class TestRegistroPropiedadResult:
    """Test RegistroPropiedadResult model."""

    def test_default_values(self):
        data = RegistroPropiedadResult()
        assert data.search_value == ""
        assert data.property_number == ""
        assert data.owner == ""
        assert data.liens == ""
        assert data.property_value == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroPropiedadResult(
            search_value="12345-678",
            property_number="12345-678",
            owner="JUAN PEREZ RODRIGUEZ",
            liens="Hipoteca First Bank",
            property_value="$250,000",
            details={"Municipio": "San Juan"},
        )
        json_str = data.model_dump_json()
        restored = RegistroPropiedadResult.model_validate_json(json_str)
        assert restored.property_number == "12345-678"
        assert restored.owner == "JUAN PEREZ RODRIGUEZ"
        assert restored.liens == "Hipoteca First Bank"
        assert restored.property_value == "$250,000"

    def test_audit_excluded_from_json(self):
        data = RegistroPropiedadResult(search_value="test", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestRegistroPropiedadSourceMeta:
    """Test RegistroPropiedadSource metadata."""

    def test_meta_name(self):
        source = RegistroPropiedadSource()
        meta = source.meta()
        assert meta.name == "pr.registro_propiedad"

    def test_meta_country(self):
        source = RegistroPropiedadSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = RegistroPropiedadSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = RegistroPropiedadSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = RegistroPropiedadSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = RegistroPropiedadSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RegistroPropiedadSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_empty_search_value_raises(self):
        src = RegistroPropiedadSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_value_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="12345-678")
        assert inp.document_number == "12345-678"

    def test_search_value_from_extra_property_number(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"property_number": "12345-678"},
        )
        assert inp.extra.get("property_number") == "12345-678"

    def test_search_value_from_extra_owner_name(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"owner_name": "JUAN PEREZ"},
        )
        assert inp.extra.get("owner_name") == "JUAN PEREZ"


class TestParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_value: str = "12345-678"):
        source = RegistroPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_value)

    def test_parse_property_number(self):
        result = self._parse("Property Number: 12345-678\nOwner: JUAN PEREZ\n")
        assert result.property_number == "12345-678"

    def test_parse_owner(self):
        result = self._parse("Owner: JUAN PEREZ RODRIGUEZ\nProperty Number: 12345\n")
        assert result.owner == "JUAN PEREZ RODRIGUEZ"

    def test_parse_liens(self):
        result = self._parse("Liens: Hipoteca First Bank\nOwner: JUAN PEREZ\n")
        assert result.liens == "Hipoteca First Bank"

    def test_parse_property_value(self):
        result = self._parse("Property Value: $250,000\nOwner: JUAN PEREZ\n")
        assert result.property_value == "$250,000"

    def test_parse_spanish_finca(self):
        result = self._parse("Finca: 12345-678\nTitular: JUAN PEREZ\n")
        assert result.property_number == "12345-678"
        assert result.owner == "JUAN PEREZ"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_value == "12345-678"
        assert result.property_number == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Municipio: San Juan\nBarrio: Santurce\n")
        assert "Municipio" in result.details
        assert result.details["Municipio"] == "San Juan"
