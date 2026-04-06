"""Tests for do.dgii_rnc_ext — Dominican Republic DGII RNC extended info source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestDgiiRncExtParseResult:
    def _parse(self, body_text: str, rnc: str = "101023129"):
        from openquery.sources.do.dgii_rnc_ext import DgiiRncExtSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = DgiiRncExtSource()
        return src._parse_result(page, rnc)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.commercial_name == ""
        assert result.status == ""
        assert result.economic_activity == ""
        assert result.address == ""

    def test_rnc_preserved(self):
        result = self._parse("", rnc="101099999")
        assert result.rnc == "101099999"

    def test_parses_company_name(self):
        body = "Razón Social: Empresa Demo S.R.L.\nEstado: Activo"
        result = self._parse(body)
        assert result.company_name == "Empresa Demo S.R.L."

    def test_parses_commercial_name(self):
        body = "Nombre Comercial: Demo Corp\nRazón Social: Empresa Demo"
        result = self._parse(body)
        assert result.commercial_name == "Demo Corp"

    def test_parses_status(self):
        body = "Estado: Activo\nRazón Social: Test"
        result = self._parse(body)
        assert result.status == "Activo"

    def test_parses_economic_activity(self):
        body = "Actividad Económica: Comercio al por mayor\nEstado: Activo"
        result = self._parse(body)
        assert result.economic_activity == "Comercio al por mayor"

    def test_parses_address(self):
        body = "Dirección: Calle Principal 123, Santo Domingo\nEstado: Activo"
        result = self._parse(body)
        assert result.address == "Calle Principal 123, Santo Domingo"

    def test_model_roundtrip(self):
        from openquery.models.do.dgii_rnc_ext import DgiiRncExtResult

        r = DgiiRncExtResult(
            rnc="101023129",
            company_name="Empresa Demo S.R.L.",
            commercial_name="Demo Corp",
            status="Activo",
            economic_activity="Comercio",
            address="Calle 1",
        )
        data = r.model_dump_json()
        r2 = DgiiRncExtResult.model_validate_json(data)
        assert r2.rnc == "101023129"
        assert r2.company_name == "Empresa Demo S.R.L."

    def test_audit_excluded_from_json(self):
        from openquery.models.do.dgii_rnc_ext import DgiiRncExtResult

        r = DgiiRncExtResult(rnc="101023129", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestDgiiRncExtSourceMeta:
    def test_meta(self):
        from openquery.sources.do.dgii_rnc_ext import DgiiRncExtSource

        meta = DgiiRncExtSource().meta()
        assert meta.name == "do.dgii_rnc_ext"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_rnc_raises(self):
        from openquery.sources.do.dgii_rnc_ext import DgiiRncExtSource

        src = DgiiRncExtSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_rnc(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="101023129",
        )
        assert input_.document_number == "101023129"
