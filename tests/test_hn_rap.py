"""Tests for hn.rap — Honduras property registry source."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnRapResult:
    def test_defaults(self):
        from openquery.models.hn.rap import HnRapResult

        r = HnRapResult()
        assert r.search_value == ""
        assert r.owner == ""
        assert r.property_type == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.hn.rap import HnRapResult

        r = HnRapResult(
            search_value="0101-2023-00001",
            owner="JUAN CARLOS FLORES MARTINEZ",
            property_type="Urbano",
        )
        dumped = r.model_dump_json()
        restored = HnRapResult.model_validate_json(dumped)
        assert restored.search_value == "0101-2023-00001"
        assert restored.owner == "JUAN CARLOS FLORES MARTINEZ"
        assert restored.property_type == "Urbano"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.rap import HnRapResult

        r = HnRapResult(search_value="0101-2023-00001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnRapSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.rap import HnRapSource

        meta = HnRapSource().meta()
        assert meta.name == "hn.rap"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_property_number_raises(self):
        from openquery.sources.hn.rap import HnRapSource

        src = HnRapSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_property_number_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="0101-2023-00001")
        assert inp.document_number == "0101-2023-00001"

    def test_property_number_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"property_number": "0101-2023-00001"},
        )
        assert inp.extra.get("property_number") == "0101-2023-00001"


class TestHnRapParseResult:
    def _parse(self, body_text: str, property_number: str = "0101-2023-00001"):
        from openquery.sources.hn.rap import HnRapSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnRapSource()
        return src._parse_result(page, property_number)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.owner == ""
        assert result.property_type == ""

    def test_search_value_preserved(self):
        result = self._parse("", property_number="0101-2023-00001")
        assert result.search_value == "0101-2023-00001"

    def test_owner_parsed_propietario(self):
        result = self._parse("Propietario: JUAN CARLOS FLORES MARTINEZ\nTipo: Urbano")
        assert result.owner == "JUAN CARLOS FLORES MARTINEZ"

    def test_owner_parsed_titular(self):
        result = self._parse("Titular: ANA LOPEZ GARCIA\nTipo: Rural")
        assert result.owner == "ANA LOPEZ GARCIA"

    def test_property_type_parsed(self):
        result = self._parse("Tipo: Urbano\nPropietario: JUAN FLORES")
        assert result.property_type == "Urbano"

    def test_details_populated(self):
        result = self._parse("Propietario: JUAN FLORES\nMunicipio: Tegucigalpa")
        assert isinstance(result.details, dict)
        assert result.details.get("Municipio") == "Tegucigalpa"

    def test_model_roundtrip(self):
        from openquery.models.hn.rap import HnRapResult

        r = HnRapResult(
            search_value="0101-2023-00001",
            owner="JUAN CARLOS FLORES MARTINEZ",
            property_type="Urbano",
        )
        data = r.model_dump_json()
        r2 = HnRapResult.model_validate_json(data)
        assert r2.search_value == "0101-2023-00001"
        assert r2.owner == "JUAN CARLOS FLORES MARTINEZ"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.rap import HnRapResult

        r = HnRapResult(search_value="0101-2023-00001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()
