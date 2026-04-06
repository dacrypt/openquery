"""Tests for pa.css_patrono — Panama CSS employer/patrono registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestPaCssPatronoResult — model tests
# ===========================================================================


class TestPaCssPatronoResult:
    def test_defaults(self):
        from openquery.models.pa.css_patrono import PaCssPatronoResult

        r = PaCssPatronoResult()
        assert r.search_term == ""
        assert r.employer_name == ""
        assert r.registration_status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pa.css_patrono import PaCssPatronoResult

        r = PaCssPatronoResult(
            search_term="Empresa SA",
            employer_name="Empresa SA",
            registration_status="active",
        )
        restored = PaCssPatronoResult.model_validate_json(r.model_dump_json())
        assert restored.employer_name == "Empresa SA"
        assert restored.registration_status == "active"

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.css_patrono import PaCssPatronoResult

        r = PaCssPatronoResult(audit="evidence")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestPaCssPatronoSourceMeta
# ===========================================================================


class TestPaCssPatronoSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert PaCssPatronoSource().meta().name == "pa.css_patrono"

    def test_meta_country(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert PaCssPatronoSource().meta().country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert PaCssPatronoSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert PaCssPatronoSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert DocumentType.CUSTOM in PaCssPatronoSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        assert PaCssPatronoSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestPaCssPatronoParseResult — parsing logic
# ===========================================================================


class TestPaCssPatronoParseResult:
    def test_missing_search_raises(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        src = PaCssPatronoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_parse_page_found(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        src = PaCssPatronoSource()
        page = MagicMock()
        page.inner_text.return_value = "Empresa Patrono SA ... registro activo"

        result = src._parse_page(page, "Empresa Patrono SA")
        assert result.search_term == "Empresa Patrono SA"
        assert result.employer_name == "Empresa Patrono SA"
        assert result.registration_status == "found"

    def test_parse_page_not_found(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        src = PaCssPatronoSource()
        page = MagicMock()
        page.inner_text.return_value = "No existen resultados para esta búsqueda."

        result = src._parse_page(page, "Empresa Inexistente")
        assert result.registration_status == "not_found"


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestPaCssPatronoIntegration:
    def test_query_employer(self):
        from openquery.sources.pa.css_patrono import PaCssPatronoSource

        src = PaCssPatronoSource(headless=True)
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Copa Airlines",
        ))
        assert isinstance(result.search_term, str)
