"""Tests for pa.registro_publico — Panama company registry."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestResult
# ===========================================================================

class TestResult:
    def test_default_values(self):
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        r = RegistroPublicoResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.folio == ""
        assert r.registration_status == ""
        assert r.directors == []
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        r = RegistroPublicoResult(search_term="ACME SA", company_name="ACME SA")
        r.audit = {"evidence": "data"}
        data = r.model_dump_json()
        assert "audit" not in data

    def test_model_roundtrip(self):
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        r = RegistroPublicoResult(
            search_term="ACME SA",
            company_name="ACME SOCIEDAD ANONIMA",
            folio="12345",
            registration_status="Vigente",
            directors=["Juan Perez", "Maria Lopez"],
        )
        r2 = RegistroPublicoResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "ACME SA"
        assert r2.company_name == "ACME SOCIEDAD ANONIMA"
        assert r2.folio == "12345"
        assert r2.registration_status == "Vigente"
        assert r2.directors == ["Juan Perez", "Maria Lopez"]


# ===========================================================================
# TestSourceMeta
# ===========================================================================

class TestSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        meta = RegistroPublicoSource().meta()
        assert meta.name == "pa.registro_publico"

    def test_meta_country(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        meta = RegistroPublicoSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        meta = RegistroPublicoSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supports_custom(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        meta = RegistroPublicoSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        meta = RegistroPublicoSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestParseResult
# ===========================================================================

class TestParseResult:
    def _make_source(self):
        from openquery.sources.pa.registro_publico import RegistroPublicoSource
        return RegistroPublicoSource()

    def _make_page(self, text: str):
        from unittest.mock import MagicMock
        page = MagicMock()
        page.inner_text.return_value = text
        page.query_selector_all.return_value = []
        return page

    def test_parse_not_found(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "EMPRESA XYZ")
        assert result.search_term == "EMPRESA XYZ"
        assert result.company_name == ""
        assert result.directors == []

    def test_parse_company_data(self):
        src = self._make_source()
        text = (
            "Nombre: ACME SOCIEDAD ANONIMA\n"
            "Folio: 12345\n"
            "Estado: Vigente\n"
            "Director: Juan Perez\n"
        )
        page = self._make_page(text)
        result = src._parse_result(page, "ACME")
        assert result.company_name == "ACME SOCIEDAD ANONIMA"
        assert result.folio == "12345"
        assert result.registration_status == "Vigente"
        assert "Juan Perez" in result.directors

    def test_query_missing_search_raises(self):
        src = self._make_source()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch
        src = self._make_source()
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        mock_result = RegistroPublicoResult(search_term="ACME SA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="ACME SA"))
            m.assert_called_once_with("ACME SA", audit=False)

    def test_query_uses_extra_company_name(self):
        from unittest.mock import patch
        src = self._make_source()
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        mock_result = RegistroPublicoResult(search_term="ACME SA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"company_name": "ACME SA"},
            ))
            m.assert_called_once_with("ACME SA", audit=False)

    def test_query_uses_extra_folio(self):
        from unittest.mock import patch
        src = self._make_source()
        from openquery.models.pa.registro_publico import RegistroPublicoResult
        mock_result = RegistroPublicoResult(search_term="12345")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"folio": "12345"},
            ))
            m.assert_called_once_with("12345", audit=False)
