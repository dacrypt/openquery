"""Tests for ni.registro_publico — Nicaragua SINARE company registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiRegistroPublicoResult:
    def test_defaults(self):
        from openquery.models.ni.registro_publico import NiRegistroPublicoResult

        r = NiRegistroPublicoResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.department == ""
        assert r.nam == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.registro_publico import NiRegistroPublicoResult

        r = NiRegistroPublicoResult(
            search_term="EMPRESA EJEMPLO SA",
            company_name="EMPRESA EJEMPLO SOCIEDAD ANONIMA",
            department="Managua",
            nam="M-00001",
            status="Activa",
        )
        dumped = r.model_dump_json()
        restored = NiRegistroPublicoResult.model_validate_json(dumped)
        assert restored.search_term == "EMPRESA EJEMPLO SA"
        assert restored.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.registro_publico import NiRegistroPublicoResult

        r = NiRegistroPublicoResult(search_term="EMPRESA SA", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiRegistroPublicoSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.registro_publico import NiRegistroPublicoSource

        meta = NiRegistroPublicoSource().meta()
        assert meta.name == "ni.registro_publico"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.ni.registro_publico import NiRegistroPublicoSource

        src = NiRegistroPublicoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_company_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"company_name": "EMPRESA EJEMPLO SA"},
        )
        assert inp.extra.get("company_name") == "EMPRESA EJEMPLO SA"


class TestNiRegistroPublicoParseResult:
    def _parse(self, body_text: str, search_term: str = "EMPRESA EJEMPLO SA"):
        from openquery.sources.ni.registro_publico import NiRegistroPublicoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiRegistroPublicoSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.department == ""
        assert result.nam == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA EJEMPLO SA")
        assert result.search_term == "EMPRESA EJEMPLO SA"

    def test_company_name_parsed(self):
        result = self._parse("Nombre: EMPRESA EJEMPLO SOCIEDAD ANONIMA\nEstado: Activa")
        assert result.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_department_parsed(self):
        result = self._parse("Departamento: Managua\nNombre: EMPRESA SA")
        assert result.department == "Managua"

    def test_nam_parsed(self):
        result = self._parse("NAM: M-00001\nNombre: EMPRESA SA")
        assert result.nam == "M-00001"

    def test_status_parsed(self):
        result = self._parse("Estado: Activa\nNombre: EMPRESA SA")
        assert result.status == "Activa"

    def test_details_populated(self):
        result = self._parse("Nombre: EMPRESA SA\nEstado: Activa")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.ni.registro_publico import NiRegistroPublicoResult

        r = NiRegistroPublicoResult(
            search_term="EMPRESA SA",
            company_name="EMPRESA EJEMPLO SOCIEDAD ANONIMA",
            department="Managua",
            nam="M-00001",
            status="Activa",
        )
        data = r.model_dump_json()
        r2 = NiRegistroPublicoResult.model_validate_json(data)
        assert r2.search_term == "EMPRESA SA"
        assert r2.nam == "M-00001"
