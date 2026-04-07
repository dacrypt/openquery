"""Tests for gt.igss — Guatemala IGSS social security source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIgssParseResult:
    def _parse(self, body_text: str, affiliation_number: str = "12345678"):
        from openquery.sources.gt.igss import IgssSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = IgssSource()
        return src._parse_result(page, affiliation_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.affiliate_name == ""
        assert result.affiliation_status == ""

    def test_affiliation_number_preserved(self):
        result = self._parse("", affiliation_number="99999999")
        assert result.affiliation_number == "99999999"

    def test_parses_affiliate_name(self):
        body = "Nombre: Carlos Mendez\nEstado: Afiliado activo"
        result = self._parse(body)
        assert result.affiliate_name == "Carlos Mendez"

    def test_parses_employer(self):
        body = "Patrono: Empresa ABC\nEstado: Activo"
        result = self._parse(body)
        assert result.employer == "Empresa ABC"

    def test_model_roundtrip(self):
        from openquery.models.gt.igss import IgssResult

        r = IgssResult(affiliation_number="12345678", affiliate_name="Carlos GT", affiliation_status="Activo")  # noqa: E501
        data = r.model_dump_json()
        r2 = IgssResult.model_validate_json(data)
        assert r2.affiliation_number == "12345678"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.igss import IgssResult

        r = IgssResult(affiliation_number="12345678", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestIgssSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.igss import IgssSource

        meta = IgssSource().meta()
        assert meta.name == "gt.igss"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_affiliation_raises(self):
        from openquery.sources.gt.igss import IgssSource

        src = IgssSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
