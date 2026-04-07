"""Tests for cr.cfia — Costa Rica CFIA professional registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCfiaParseResult:
    def _parse(self, body_text: str, search_term: str = "Juan Ingeniero"):
        from openquery.sources.cr.cfia import CfiaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CfiaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.professional_name == ""
        assert result.license_number == ""
        assert result.profession == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Maria Arquitecta")
        assert result.search_term == "Maria Arquitecta"

    def test_parses_professional_name(self):
        body = "Nombre: Juan Carlos Perez\nEstado: Activo al día"
        result = self._parse(body)
        assert result.professional_name == "Juan Carlos Perez"

    def test_parses_membership_status(self):
        body = "Estado: Activo al día\nCarnet: 12345"
        result = self._parse(body)
        assert result.membership_status == "Activo al día"

    def test_model_roundtrip(self):
        from openquery.models.cr.cfia import CfiaResult

        r = CfiaResult(search_term="test", professional_name="Juan Perez", profession="Ingeniería Civil")  # noqa: E501
        data = r.model_dump_json()
        r2 = CfiaResult.model_validate_json(data)
        assert r2.professional_name == "Juan Perez"

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.cfia import CfiaResult

        r = CfiaResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestCfiaSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.cfia import CfiaSource

        meta = CfiaSource().meta()
        assert meta.name == "cr.cfia"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.cr.cfia import CfiaSource

        src = CfiaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
