"""Tests for pa.mici — MICI company/industrial registry lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test MiciResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pa.mici import MiciResult

        r = MiciResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.registration_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.mici import MiciResult

        r = MiciResult(search_term="EMPRESA ABC", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "EMPRESA ABC" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pa.mici import MiciResult

        r = MiciResult(
            search_term="EMPRESA ABC",
            company_name="EMPRESA ABC S.A.",
            registration_status="Vigente",
            details={"RUC": "123456789"},
        )
        r2 = MiciResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "EMPRESA ABC"
        assert r2.company_name == "EMPRESA ABC S.A."
        assert r2.registration_status == "Vigente"

    def test_queried_at_default(self):
        from openquery.models.pa.mici import MiciResult

        before = datetime.now()
        r = MiciResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test pa.mici source metadata."""

    def test_meta_name(self):
        from openquery.sources.pa.mici import MiciSource

        meta = MiciSource().meta()
        assert meta.name == "pa.mici"

    def test_meta_country(self):
        from openquery.sources.pa.mici import MiciSource

        meta = MiciSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.mici import MiciSource

        meta = MiciSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.pa.mici import MiciSource

        meta = MiciSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.mici import MiciSource

        meta = MiciSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.pa.mici import MiciSource

        return MiciSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.company_name == ""
        assert result.registration_status == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultados de la consulta")
        result = src._parse_result(page, "EMPRESA ABC")
        assert result.search_term == "EMPRESA ABC"

    def test_company_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Empresa: EMPRESA ABC S.A.\nEstado: Vigente")
        result = src._parse_result(page, "EMPRESA ABC")
        assert result.company_name == "EMPRESA ABC S.A."

    def test_registration_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Estado: Vigente\nOtros datos")
        result = src._parse_result(page, "EMPRESA ABC")
        assert result.registration_status == "Vigente"

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pa.mici import MiciSource

        src = MiciSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.pa.mici import MiciResult
        from openquery.sources.pa.mici import MiciSource

        src = MiciSource()
        mock_result = MiciResult(search_term="EMPRESA ABC")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="EMPRESA ABC")
            )
            m.assert_called_once_with("EMPRESA ABC", audit=False)
