"""Tests for ve.tsj — Venezuela TSJ Supreme Court case lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestTsjResult — model tests
# ===========================================================================


class TestTsjResult:
    def test_defaults(self):
        from openquery.models.ve.tsj import TsjResult

        r = TsjResult()
        assert r.search_term == ""
        assert r.case_number == ""
        assert r.chamber == ""
        assert r.status == ""
        assert r.ruling == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.tsj import TsjResult

        r = TsjResult(
            search_term="AA20-C-2021-000001",
            case_number="AA20-C-2021-000001",
            chamber="Sala Civil",
            status="SENTENCIADO",
            ruling="Con Lugar",
        )
        dumped = r.model_dump_json()
        restored = TsjResult.model_validate_json(dumped)
        assert restored.case_number == "AA20-C-2021-000001"
        assert restored.chamber == "Sala Civil"
        assert restored.status == "SENTENCIADO"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.tsj import TsjResult

        r = TsjResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.tsj import TsjResult

        r = TsjResult(details={"Sala": "Sala Civil", "Estado": "ACTIVO"})
        assert r.details["Sala"] == "Sala Civil"


# ===========================================================================
# TestTsjSourceMeta
# ===========================================================================


class TestTsjSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.tsj import TsjSource

        assert TsjSource().meta().name == "ve.tsj"

    def test_meta_country(self):
        from openquery.sources.ve.tsj import TsjSource

        assert TsjSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.tsj import TsjSource

        assert TsjSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.ve.tsj import TsjSource

        assert TsjSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.tsj import TsjSource

        assert DocumentType.CUSTOM in TsjSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.tsj import TsjSource

        assert TsjSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestTsjQuery — input validation
# ===========================================================================


class TestTsjQuery:
    def test_empty_search_raises(self):
        from openquery.sources.ve.tsj import TsjSource

        src = TsjSource()
        with pytest.raises(SourceError, match="Search term"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_from_document_number(self):
        from openquery.models.ve.tsj import TsjResult
        from openquery.sources.ve.tsj import TsjSource

        src = TsjSource()
        src._query = MagicMock(return_value=TsjResult(search_term="AA20-C-2021-000001"))
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="AA20-C-2021-000001",
            )
        )
        src._query.assert_called_once_with(
            search_term="AA20-C-2021-000001", audit=False
        )
        assert result.search_term == "AA20-C-2021-000001"

    def test_search_from_extra_case_number(self):
        from openquery.models.ve.tsj import TsjResult
        from openquery.sources.ve.tsj import TsjSource

        src = TsjSource()
        src._query = MagicMock(return_value=TsjResult(search_term="AA20-C-2021-000001"))
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"case_number": "AA20-C-2021-000001"},
            )
        )
        src._query.assert_called_once_with(
            search_term="AA20-C-2021-000001", audit=False
        )
        assert result.search_term == "AA20-C-2021-000001"

    def test_search_from_extra_party_name(self):
        from openquery.models.ve.tsj import TsjResult
        from openquery.sources.ve.tsj import TsjSource

        src = TsjSource()
        src._query = MagicMock(return_value=TsjResult(search_term="EMPRESA EJEMPLO"))
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"party_name": "EMPRESA EJEMPLO"},
            )
        )
        src._query.assert_called_once_with(search_term="EMPRESA EJEMPLO", audit=False)
        assert result.search_term == "EMPRESA EJEMPLO"


# ===========================================================================
# TestTsjParseResult — parsing logic
# ===========================================================================


class TestTsjParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        return page

    def _parse(
        self, body_text: str, search_term: str = "AA20-C-2021-000001"
    ) -> object:
        from openquery.sources.ve.tsj import TsjSource

        return TsjSource()._parse_result(self._make_page(body_text), search_term)

    def test_case_number_extracted(self):
        body = "Expediente: AA20-C-2021-000001\nSala: Sala Civil\n"
        result = self._parse(body)
        assert result.case_number == "AA20-C-2021-000001"

    def test_chamber_extracted(self):
        body = "Expediente: AA20-C-2021-000001\nSala: Sala Civil\n"
        result = self._parse(body)
        assert result.chamber == "Sala Civil"

    def test_status_extracted(self):
        body = "Estado: SENTENCIADO\n"
        result = self._parse(body)
        assert result.status == "SENTENCIADO"

    def test_ruling_extracted(self):
        body = "Decisión: Con Lugar\n"
        result = self._parse(body)
        assert result.ruling == "Con Lugar"

    def test_search_term_preserved(self):
        result = self._parse("", search_term="AA20-C-2021-000001")
        assert result.search_term == "AA20-C-2021-000001"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.case_number == ""
        assert result.chamber == ""
        assert result.status == ""
        assert result.ruling == ""

    def test_details_populated(self):
        body = "Sala: Sala Civil\nEstado: ACTIVO\n"
        result = self._parse(body)
        assert isinstance(result.details, dict)
        assert len(result.details) > 0

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)

    def test_regex_fallback_tribunal(self):
        body = "Tribunal: Sala Constitucional\n"
        result = self._parse(body)
        assert result.chamber == "Sala Constitucional"

    def test_regex_fallback_sentencia(self):
        body = "Sentencia: Sin Lugar\n"
        result = self._parse(body)
        assert result.ruling == "Sin Lugar"


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestTsjIntegration:
    def test_query_by_case_number(self):
        from openquery.sources.ve.tsj import TsjSource

        src = TsjSource(headless=True)
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                extra={"case_number": "AA20-C-2021-000001"},
                document_number="",
            )
        )
        assert isinstance(result.search_term, str)
        assert isinstance(result.case_number, str)
