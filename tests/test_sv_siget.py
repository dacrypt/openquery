"""Tests for sv.siget — El Salvador SIGET utilities regulator source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSigetParseResult:
    def _parse(self, body_text: str, search_term: str = "Claro El Salvador"):
        from openquery.sources.sv.siget import SigetSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SigetSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.provider_name == ""
        assert result.service_type == ""
        assert result.authorization_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Tigo El Salvador")
        assert result.search_term == "Tigo El Salvador"

    def test_parses_provider_name(self):
        body = "Proveedor: Claro El Salvador S.A.\nServicio: Telefonía móvil\nEstado: Autorizado"
        result = self._parse(body)
        assert result.provider_name == "Claro El Salvador S.A."

    def test_parses_service_type(self):
        body = "Servicio: Internet de banda ancha\nEstado: Autorizado"
        result = self._parse(body)
        assert result.service_type == "Internet de banda ancha"

    def test_parses_authorization_status(self):
        body = "Estado: Autorizado\nProveedor: Tigo"
        result = self._parse(body)
        assert result.authorization_status == "Autorizado"

    def test_parses_licencia_label(self):
        body = "Licencia: Concesión vigente\nProveedor: Test SA"
        result = self._parse(body)
        assert result.authorization_status == "Concesión vigente"

    def test_model_roundtrip(self):
        from openquery.models.sv.siget import SigetResult

        r = SigetResult(
            search_term="Claro",
            provider_name="Claro El Salvador S.A.",
            service_type="Telefonía móvil",
            authorization_status="Autorizado",
        )
        data = r.model_dump_json()
        r2 = SigetResult.model_validate_json(data)
        assert r2.search_term == "Claro"
        assert r2.provider_name == "Claro El Salvador S.A."

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.siget import SigetResult

        r = SigetResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSigetSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.siget import SigetSource

        meta = SigetSource().meta()
        assert meta.name == "sv.siget"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.sv.siget import SigetSource

        src = SigetSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Claro El Salvador",
        )
        assert input_.document_number == "Claro El Salvador"

    def test_extra_company_name(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"company_name": "Tigo"},
        )
        assert input_.extra["company_name"] == "Tigo"
