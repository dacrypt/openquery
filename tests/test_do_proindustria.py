"""Tests for do.proindustria — Dominican Republic PROINDUSTRIA industrial registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestProindustriaParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Test"):
        from openquery.sources.do.proindustria import ProindustriaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = ProindustriaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.registration_number == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Industria DO")
        assert result.search_term == "Industria DO"

    def test_parses_company_name(self):
        body = "Empresa: Industrias del Norte SRL\nEstado: Registrado"
        result = self._parse(body)
        assert result.company_name == "Industrias del Norte SRL"

    def test_parses_industry_type(self):
        body = "Sector: Textil\nRegistro: IND-2024-001"
        result = self._parse(body)
        assert result.industry_type == "Textil"

    def test_model_roundtrip(self):
        from openquery.models.do.proindustria import ProindustriaResult

        r = ProindustriaResult(search_term="test", company_name="Industrias DO", registration_number="IND-001")  # noqa: E501
        data = r.model_dump_json()
        r2 = ProindustriaResult.model_validate_json(data)
        assert r2.company_name == "Industrias DO"

    def test_audit_excluded_from_json(self):
        from openquery.models.do.proindustria import ProindustriaResult

        r = ProindustriaResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestProindustriaSourceMeta:
    def test_meta(self):
        from openquery.sources.do.proindustria import ProindustriaSource

        meta = ProindustriaSource().meta()
        assert meta.name == "do.proindustria"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.do.proindustria import ProindustriaSource

        src = ProindustriaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
