"""Tests for pr.salud — Puerto Rico Department of Health facility source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrSaludParseResult:
    def _parse(self, body_text: str, search_term: str = "Hospital Test"):
        from openquery.sources.pr.salud import PrSaludSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = PrSaludSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.facility_name == ""
        assert result.license_number == ""
        assert result.license_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Clinica PR")
        assert result.search_term == "Clinica PR"

    def test_parses_facility_name(self):
        body = "Nombre: Hospital San Juan\nEstado: Activo"
        result = self._parse(body)
        assert result.facility_name == "Hospital San Juan"

    def test_parses_license_status(self):
        body = "Licencia: 12345\nEstado: Activo"
        result = self._parse(body)
        assert result.license_status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.pr.salud import PrSaludResult

        r = PrSaludResult(search_term="Hospital Test", facility_name="Hospital PR", license_status="Active")  # noqa: E501
        data = r.model_dump_json()
        r2 = PrSaludResult.model_validate_json(data)
        assert r2.facility_name == "Hospital PR"

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.salud import PrSaludResult

        r = PrSaludResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestPrSaludSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.salud import PrSaludSource

        meta = PrSaludSource().meta()
        assert meta.name == "pr.salud"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.pr.salud import PrSaludSource

        src = PrSaludSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
