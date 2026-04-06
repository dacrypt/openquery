"""Tests for cr.registro_nacional — Costa Rica Registro Nacional company lookup source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCrRegistroNacionalParseResult:
    def _parse(self, body_text: str, search_term: str = "3-101-123456"):
        from openquery.sources.cr.registro_nacional import CrRegistroNacionalSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrRegistroNacionalSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.cedula_juridica == ""
        assert result.status == ""
        assert result.legal_representative == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="3-101-999999")
        assert result.search_term == "3-101-999999"

    def test_parses_company_name(self):
        body = "Razón Social: Empresa Demo S.A.\nEstado: Activa"
        result = self._parse(body)
        assert result.company_name == "Empresa Demo S.A."

    def test_parses_cedula_juridica(self):
        body = "Cédula Jurídica: 3-101-123456\nRazón Social: Demo Corp"
        result = self._parse(body)
        assert result.cedula_juridica == "3-101-123456"

    def test_parses_status(self):
        body = "Estado: Activa\nRazón Social: Test Corp"
        result = self._parse(body)
        assert result.status == "Activa"

    def test_parses_legal_representative(self):
        body = "Representante Legal: Juan Pérez\nEstado: Activa"
        result = self._parse(body)
        assert result.legal_representative == "Juan Pérez"

    def test_model_roundtrip(self):
        from openquery.models.cr.registro_nacional import CrRegistroNacionalResult

        r = CrRegistroNacionalResult(
            search_term="3-101-123456",
            company_name="Empresa Demo S.A.",
            cedula_juridica="3-101-123456",
            status="Activa",
            legal_representative="Juan Pérez",
        )
        data = r.model_dump_json()
        r2 = CrRegistroNacionalResult.model_validate_json(data)
        assert r2.search_term == "3-101-123456"
        assert r2.company_name == "Empresa Demo S.A."

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.registro_nacional import CrRegistroNacionalResult

        r = CrRegistroNacionalResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestCrRegistroNacionalSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.registro_nacional import CrRegistroNacionalSource

        meta = CrRegistroNacionalSource().meta()
        assert meta.name == "cr.registro_nacional"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.cr.registro_nacional import CrRegistroNacionalSource

        src = CrRegistroNacionalSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="3-101-123456",
        )
        assert input_.document_number == "3-101-123456"

    def test_extra_cedula_juridica(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"cedula_juridica": "3-101-999999"},
        )
        assert input_.extra["cedula_juridica"] == "3-101-999999"
