"""Tests for pe.essalud — EsSalud health insurance affiliation lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestEssaludResult:
    """Test EssaludResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pe.essalud import EssaludResult

        r = EssaludResult()
        assert r.dni == ""
        assert r.affiliation_status == ""
        assert r.employer == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.essalud import EssaludResult

        r = EssaludResult(dni="12345678", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "12345678" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pe.essalud import EssaludResult

        r = EssaludResult(
            dni="12345678",
            affiliation_status="Activo",
            employer="EMPRESA ABC SAC",
            details={"Estado": "Activo"},
        )
        r2 = EssaludResult.model_validate_json(r.model_dump_json())
        assert r2.dni == "12345678"
        assert r2.affiliation_status == "Activo"
        assert r2.employer == "EMPRESA ABC SAC"

    def test_queried_at_default(self):
        from openquery.models.pe.essalud import EssaludResult

        before = datetime.now()
        r = EssaludResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestEssaludSourceMeta:
    """Test pe.essalud source metadata."""

    def test_meta_name(self):
        from openquery.sources.pe.essalud import EssaludSource

        assert EssaludSource().meta().name == "pe.essalud"

    def test_meta_country(self):
        from openquery.sources.pe.essalud import EssaludSource

        assert EssaludSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        from openquery.sources.pe.essalud import EssaludSource

        assert EssaludSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.pe.essalud import EssaludSource

        assert DocumentType.CEDULA in EssaludSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pe.essalud import EssaludSource

        assert EssaludSource().meta().rate_limit_rpm == 10


class TestEssaludParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, dni: str = "12345678"):
        from openquery.sources.pe.essalud import EssaludSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return EssaludSource()._parse_result(page, dni)

    def test_dni_preserved(self):
        assert self._parse("Datos", dni="87654321").dni == "87654321"

    def test_affiliation_status_parsed(self):
        result = self._parse("Estado de afiliación: Activo\nOtros")
        assert result.affiliation_status == "Activo"

    def test_employer_parsed(self):
        result = self._parse("Empleador: EMPRESA XYZ SAC\nOtros")
        assert result.employer == "EMPRESA XYZ SAC"

    def test_empty_body(self):
        result = self._parse("")
        assert result.dni == "12345678"
        assert result.affiliation_status == ""

    def test_query_missing_dni_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pe.essalud import EssaludSource

        with pytest.raises(SourceError, match="DNI"):
            EssaludSource().query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))
