"""Tests for ve.ivss — Venezuela social security / cedula lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIvssResult — model tests
# ===========================================================================


class TestIvssResult:
    def test_defaults(self):
        from openquery.models.ve.ivss import IvssResult

        r = IvssResult()
        assert r.cedula == ""
        assert r.enrollment_status == ""
        assert r.contribution_status == ""
        assert r.employer == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.ivss import IvssResult

        r = IvssResult(
            cedula="V12345678",
            enrollment_status="INSCRITO",
            contribution_status="AL DIA",
            employer="EMPRESA EJEMPLO C.A.",
        )
        dumped = r.model_dump_json()
        restored = IvssResult.model_validate_json(dumped)
        assert restored.cedula == "V12345678"
        assert restored.enrollment_status == "INSCRITO"
        assert restored.contribution_status == "AL DIA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.ivss import IvssResult

        r = IvssResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.ivss import IvssResult

        r = IvssResult(details={"Patrono": "EMPRESA EJEMPLO C.A.", "Estado": "ACTIVO"})
        assert r.details["Patrono"] == "EMPRESA EJEMPLO C.A."


# ===========================================================================
# TestIvssSourceMeta
# ===========================================================================


class TestIvssSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource().meta().name == "ve.ivss"

    def test_meta_country(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.ivss import IvssSource

        assert DocumentType.CEDULA in IvssSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource().meta().rate_limit_rpm == 5

    def test_default_timeout(self):
        from openquery.sources.ve.ivss import IvssSource

        assert IvssSource()._timeout == 45.0


# ===========================================================================
# TestIvssQuery — input validation
# ===========================================================================


class TestIvssQuery:
    def test_wrong_document_type_raises(self):
        from openquery.sources.ve.ivss import IvssSource

        src = IvssSource()
        with pytest.raises(SourceError, match="cedula"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="123"))

    def test_empty_cedula_raises(self):
        from openquery.sources.ve.ivss import IvssSource

        src = IvssSource()
        with pytest.raises(SourceError, match="cedula is required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_valid_cedula_calls_query(self):
        from openquery.models.ve.ivss import IvssResult
        from openquery.sources.ve.ivss import IvssSource

        src = IvssSource()
        src._query = MagicMock(return_value=IvssResult(cedula="12345678"))
        result = src.query(
            QueryInput(document_type=DocumentType.CEDULA, document_number="12345678")
        )
        src._query.assert_called_once_with("12345678", audit=False)
        assert result.cedula == "12345678"

    def test_cedula_whitespace_stripped(self):
        from openquery.models.ve.ivss import IvssResult
        from openquery.sources.ve.ivss import IvssSource

        src = IvssSource()
        src._query = MagicMock(return_value=IvssResult(cedula="12345678"))
        src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="  12345678  "))
        src._query.assert_called_once_with("12345678", audit=False)


# ===========================================================================
# TestIvssParseResult — parsing logic
# ===========================================================================


class TestIvssParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        return page

    def _parse(self, body_text: str, cedula: str = "12345678") -> object:
        from openquery.sources.ve.ivss import IvssSource

        return IvssSource()._parse_result(self._make_page(body_text), cedula)

    def test_enrollment_status_extracted(self):
        body = "Inscripcion: INSCRITO\n"
        result = self._parse(body)
        assert result.enrollment_status == "INSCRITO"

    def test_contribution_status_extracted(self):
        body = "Cotizacion: AL DIA\n"
        result = self._parse(body)
        assert result.contribution_status == "AL DIA"

    def test_employer_extracted(self):
        body = "Patrono: EMPRESA EJEMPLO C.A.\n"
        result = self._parse(body)
        assert result.employer == "EMPRESA EJEMPLO C.A."

    def test_cedula_preserved(self):
        result = self._parse("", cedula="V12345678")
        assert result.cedula == "V12345678"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.enrollment_status == ""
        assert result.contribution_status == ""
        assert result.employer == ""

    def test_details_populated(self):
        body = "Inscripcion: INSCRITO\nPatrono: EMPRESA C.A.\n"
        result = self._parse(body)
        assert isinstance(result.details, dict)
        assert len(result.details) > 0

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestIvssIntegration:
    def test_query_by_cedula(self):
        from openquery.sources.ve.ivss import IvssSource

        src = IvssSource(headless=True)
        result = src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="V1"))
        assert isinstance(result.cedula, str)
        assert isinstance(result.enrollment_status, str)
