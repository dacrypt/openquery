"""Tests for pa.organo_judicial — Panama court case search."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestResult
# ===========================================================================

class TestResult:
    def test_default_values(self):
        from openquery.models.pa.organo_judicial import OrganoJudicialResult
        r = OrganoJudicialResult()
        assert r.search_value == ""
        assert r.total == 0
        assert r.processes == []
        assert r.audit is None

    def test_proceso_record_defaults(self):
        from openquery.models.pa.organo_judicial import PaProcesoRecord
        p = PaProcesoRecord()
        assert p.case_number == ""
        assert p.court == ""
        assert p.case_type == ""
        assert p.status == ""
        assert p.filing_date == ""
        assert p.parties == ""

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.organo_judicial import OrganoJudicialResult
        r = OrganoJudicialResult(search_value="1-234-5678", total=0)
        r.audit = {"evidence": "data"}
        data = r.model_dump_json()
        assert "audit" not in data

    def test_model_roundtrip(self):
        from openquery.models.pa.organo_judicial import OrganoJudicialResult, PaProcesoRecord
        r = OrganoJudicialResult(
            search_value="1-234-5678",
            total=1,
            processes=[PaProcesoRecord(
                case_number="2024-00123",
                court="Juzgado Civil",
                case_type="Civil",
                status="Activo",
                filing_date="2024-01-15",
                parties="Juan vs Pedro",
            )],
        )
        r2 = OrganoJudicialResult.model_validate_json(r.model_dump_json())
        assert r2.search_value == "1-234-5678"
        assert r2.total == 1
        assert r2.processes[0].case_number == "2024-00123"
        assert r2.processes[0].court == "Juzgado Civil"


# ===========================================================================
# TestSourceMeta
# ===========================================================================

class TestSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        meta = OrganoJudicialSource().meta()
        assert meta.name == "pa.organo_judicial"

    def test_meta_country(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        meta = OrganoJudicialSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        meta = OrganoJudicialSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supports_cedula(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        meta = OrganoJudicialSource().meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        meta = OrganoJudicialSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestParseResult
# ===========================================================================

class TestParseResult:
    def _make_source(self):
        from openquery.sources.pa.organo_judicial import OrganoJudicialSource
        return OrganoJudicialSource()

    def _make_page(self, text: str):
        from unittest.mock import MagicMock
        page = MagicMock()
        page.inner_text.return_value = text
        page.query_selector_all.return_value = []
        return page

    def test_parse_not_found(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados para su búsqueda")
        result = src._parse_result(page, "9-999-9999")
        assert result.search_value == "9-999-9999"
        assert result.total == 0
        assert result.processes == []

    def test_parse_empty_page(self):
        src = self._make_source()
        page = self._make_page("")
        result = src._parse_result(page, "1-234-5678")
        assert result.search_value == "1-234-5678"
        assert result.total == 0

    def test_query_missing_value_raises(self):
        src = self._make_source()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch
        src = self._make_source()
        from openquery.models.pa.organo_judicial import OrganoJudicialResult
        mock_result = OrganoJudicialResult(search_value="1-234-5678")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="1-234-5678"))
            m.assert_called_once_with("1-234-5678", audit=False)

    def test_query_uses_extra_case_number(self):
        from unittest.mock import patch
        src = self._make_source()
        from openquery.models.pa.organo_judicial import OrganoJudicialResult
        mock_result = OrganoJudicialResult(search_value="2024-00123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"case_number": "2024-00123"},
            ))
            m.assert_called_once_with("2024-00123", audit=False)
