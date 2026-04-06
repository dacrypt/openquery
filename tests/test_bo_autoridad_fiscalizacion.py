"""Tests for bo.autoridad_fiscalizacion — Bolivia AEMP business supervision source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBoAutoridadFiscalizacionParseResult:
    def _parse(self, body_text: str, search_term: str = "ENTEL"):
        from openquery.sources.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = BoAutoridadFiscalizacionSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.registration_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="ENTEL SA")
        assert result.search_term == "ENTEL SA"

    def test_company_name_parsed(self):
        result = self._parse("Empresa: ENTEL SA\nEstado: Activo")
        assert result.company_name == "ENTEL SA"

    def test_registration_status_parsed(self):
        result = self._parse("Empresa: ENTEL\nEstado: Registrado")
        assert result.registration_status == "Registrado"

    def test_details_populated(self):
        result = self._parse("Empresa: YPFB\nSituación: Activo")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionResult

        r = BoAutoridadFiscalizacionResult(
            search_term="ENTEL",
            company_name="ENTEL SA",
            registration_status="Activo",
        )
        data = r.model_dump_json()
        r2 = BoAutoridadFiscalizacionResult.model_validate_json(data)
        assert r2.search_term == "ENTEL"
        assert r2.company_name == "ENTEL SA"
        assert r2.registration_status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionResult

        r = BoAutoridadFiscalizacionResult(search_term="ENTEL", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestBoAutoridadFiscalizacionSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionSource

        meta = BoAutoridadFiscalizacionSource().meta()
        assert meta.name == "bo.autoridad_fiscalizacion"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_company_raises(self):
        from openquery.sources.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionSource

        src = BoAutoridadFiscalizacionSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
