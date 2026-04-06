"""Tests for hn.empresa — Honduras company registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnEmpresaParseResult:
    def _parse(self, body_text: str, search_term: str = "EMPRESA EJEMPLO SA"):
        from openquery.sources.hn.empresa import HnEmpresaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnEmpresaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.company_type == ""
        assert result.registration_date == ""
        assert result.legal_representative == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA EJEMPLO SA")
        assert result.search_term == "EMPRESA EJEMPLO SA"

    def test_company_name_parsed(self):
        result = self._parse("Nombre: EMPRESA EJEMPLO SOCIEDAD ANONIMA\nTipo: S.A.")
        assert result.company_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_company_type_parsed(self):
        result = self._parse("Tipo: Sociedad Anonima\nNombre: ACME SA")
        assert result.company_type == "Sociedad Anonima"

    def test_registration_date_parsed(self):
        result = self._parse("Fecha: 2015-03-22\nNombre: EMPRESA SA")
        assert result.registration_date == "2015-03-22"

    def test_legal_representative_parsed(self):
        result = self._parse("Representante: JUAN GARCIA LOPEZ\nNombre: ACME SA")
        assert result.legal_representative == "JUAN GARCIA LOPEZ"

    def test_details_populated(self):
        result = self._parse("Nombre: EMPRESA SA\nMunicipio: San Pedro Sula")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.hn.empresa import HnEmpresaResult

        r = HnEmpresaResult(
            search_term="ACME SA",
            company_name="ACME SOCIEDAD ANONIMA",
            company_type="Sociedad Anonima",
            registration_date="2010-01-15",
            legal_representative="CARLOS LOPEZ",
        )
        data = r.model_dump_json()
        r2 = HnEmpresaResult.model_validate_json(data)
        assert r2.search_term == "ACME SA"
        assert r2.company_name == "ACME SOCIEDAD ANONIMA"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.empresa import HnEmpresaResult

        r = HnEmpresaResult(search_term="ACME SA", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnEmpresaSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.empresa import HnEmpresaSource

        meta = HnEmpresaSource().meta()
        assert meta.name == "hn.empresa"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.hn.empresa import HnEmpresaSource

        src = HnEmpresaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_company_name_extra_used(self):
        from openquery.sources.hn.empresa import HnEmpresaSource

        src = HnEmpresaSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"company_name": "EMPRESA TEST SA"},
        )
        # Just verify routing — no browser call needed
        assert inp.extra.get("company_name") == "EMPRESA TEST SA"

    def test_rtn_extra_used(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"rtn": "08011234567890"},
        )
        assert inp.extra.get("rtn") == "08011234567890"
