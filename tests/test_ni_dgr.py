"""Tests for ni.dgr — Nicaragua DGR tax registry source."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiDgrResult:
    def test_defaults(self):
        from openquery.models.ni.dgr import NiDgrResult

        r = NiDgrResult()
        assert r.search_term == ""
        assert r.taxpayer_name == ""
        assert r.tax_status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.dgr import NiDgrResult

        r = NiDgrResult(
            search_term="EMPRESA EJEMPLO",
            taxpayer_name="EMPRESA EJEMPLO SOCIEDAD ANONIMA",
            tax_status="Activo",
        )
        dumped = r.model_dump_json()
        restored = NiDgrResult.model_validate_json(dumped)
        assert restored.search_term == "EMPRESA EJEMPLO"
        assert restored.taxpayer_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"
        assert restored.tax_status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.dgr import NiDgrResult

        r = NiDgrResult(search_term="EMPRESA EJEMPLO", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiDgrSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.dgr import NiDgrSource

        meta = NiDgrSource().meta()
        assert meta.name == "ni.dgr"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.ni.dgr import NiDgrSource

        src = NiDgrSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_term_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="EMPRESA EJEMPLO")
        assert inp.document_number == "EMPRESA EJEMPLO"

    def test_search_term_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"taxpayer_name": "EMPRESA EJEMPLO"},
        )
        assert inp.extra.get("taxpayer_name") == "EMPRESA EJEMPLO"


class TestNiDgrParseResult:
    def _parse(self, body_text: str, search_term: str = "EMPRESA EJEMPLO"):
        from openquery.sources.ni.dgr import NiDgrSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiDgrSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.taxpayer_name == ""
        assert result.tax_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA EJEMPLO")
        assert result.search_term == "EMPRESA EJEMPLO"

    def test_taxpayer_name_parsed_nombre(self):
        result = self._parse("Nombre: EMPRESA EJEMPLO SOCIEDAD ANONIMA\nEstado: Activo")
        assert result.taxpayer_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_taxpayer_name_parsed_contribuyente(self):
        result = self._parse("Contribuyente: EMPRESA SA\nEstado: Activo")
        assert result.taxpayer_name == "EMPRESA SA"

    def test_tax_status_parsed(self):
        result = self._parse("Estado: Activo\nNombre: EMPRESA SA")
        assert result.tax_status == "Activo"

    def test_tax_status_parsed_situacion(self):
        result = self._parse("Situación: Suspendido\nNombre: EMPRESA SA")
        assert result.tax_status == "Suspendido"

    def test_details_populated(self):
        result = self._parse("Nombre: EMPRESA SA\nEstado: Activo")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.ni.dgr import NiDgrResult

        r = NiDgrResult(
            search_term="EMPRESA EJEMPLO",
            taxpayer_name="EMPRESA EJEMPLO SA",
            tax_status="Activo",
        )
        data = r.model_dump_json()
        r2 = NiDgrResult.model_validate_json(data)
        assert r2.search_term == "EMPRESA EJEMPLO"
        assert r2.taxpayer_name == "EMPRESA EJEMPLO SA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.dgr import NiDgrResult

        r = NiDgrResult(search_term="EMPRESA EJEMPLO", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()
