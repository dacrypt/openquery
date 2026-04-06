"""Tests for pa.aup — Panama ASEP public utilities authority."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestPaAupResult — model tests
# ===========================================================================


class TestPaAupResult:
    def test_defaults(self):
        from openquery.models.pa.aup import PaAupResult

        r = PaAupResult()
        assert r.search_term == ""
        assert r.provider_name == ""
        assert r.service_type == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pa.aup import PaAupResult

        r = PaAupResult(
            search_term="Electrica SA",
            provider_name="Electrica SA",
            service_type="electricity",
            status="active",
        )
        restored = PaAupResult.model_validate_json(r.model_dump_json())
        assert restored.provider_name == "Electrica SA"
        assert restored.service_type == "electricity"

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.aup import PaAupResult

        r = PaAupResult(audit="evidence")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestPaAupSourceMeta
# ===========================================================================


class TestPaAupSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.aup import PaAupSource

        assert PaAupSource().meta().name == "pa.aup"

    def test_meta_country(self):
        from openquery.sources.pa.aup import PaAupSource

        assert PaAupSource().meta().country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.aup import PaAupSource

        assert PaAupSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.pa.aup import PaAupSource

        assert PaAupSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.pa.aup import PaAupSource

        assert PaAupSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestPaAupParseResult — parsing logic
# ===========================================================================


class TestPaAupParseResult:
    def test_missing_search_raises(self):
        from openquery.sources.pa.aup import PaAupSource

        src = PaAupSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_parse_page_found(self):
        from openquery.sources.pa.aup import PaAupSource

        src = PaAupSource()
        page = MagicMock()
        page.inner_text.return_value = "Cable Onda SA proveedor de servicios"

        result = src._parse_page(page, "Cable Onda SA")
        assert result.search_term == "Cable Onda SA"
        assert result.status == "found"

    def test_parse_page_not_found(self):
        from openquery.sources.pa.aup import PaAupSource

        src = PaAupSource()
        page = MagicMock()
        page.inner_text.return_value = "Bienvenido al portal ASEP"

        result = src._parse_page(page, "Empresa Inexistente XYZ")
        assert result.status == "not_found"

    def test_extra_name_used(self):
        from openquery.sources.pa.aup import PaAupSource

        src = PaAupSource()
        called_with: list[str] = []

        from openquery.models.pa.aup import PaAupResult

        def fake_query(search: str) -> PaAupResult:
            called_with.append(search)
            return PaAupResult(search_term=search)

        src._query = fake_query
        src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"name": "ENSA"},
        ))
        assert called_with[0] == "ENSA"


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestPaAupIntegration:
    def test_query_provider(self):
        from openquery.sources.pa.aup import PaAupSource

        src = PaAupSource(headless=True)
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            extra={"name": "ENSA"},
        ))
        assert isinstance(result.search_term, str)
