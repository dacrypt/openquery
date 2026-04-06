"""Tests for ni.marena — Nicaragua MARENA environmental permits source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiMarenaParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Minera SA"):
        from openquery.sources.ni.marena import NiMarenaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = NiMarenaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.permit_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Empresa Minera SA")
        assert result.search_term == "Empresa Minera SA"

    def test_company_name_parsed(self):
        result = self._parse("Empresa: Minera Norte SA\nEstado: Vigente")
        assert result.company_name == "Minera Norte SA"

    def test_permit_type_parsed(self):
        result = self._parse("Tipo: Permiso Ambiental\nEstado: Vigente")
        assert result.permit_type == "Permiso Ambiental"

    def test_status_parsed(self):
        result = self._parse("Estado: Vigente")
        assert result.status == "Vigente"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.ni.marena import NiMarenaSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Empresa XYZ", "Ambiental", "Activo"])]  # noqa: E501
        src = NiMarenaSource()
        result = src._parse_result(page, "Empresa XYZ")
        assert result.company_name == "Empresa XYZ"
        assert result.permit_type == "Ambiental"
        assert result.status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.ni.marena import NiMarenaResult

        r = NiMarenaResult(
            search_term="Empresa Minera SA",
            company_name="Minera Norte SA",
            permit_type="Permiso Ambiental",
            status="Vigente",
        )
        data = r.model_dump_json()
        r2 = NiMarenaResult.model_validate_json(data)
        assert r2.company_name == "Minera Norte SA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.marena import NiMarenaResult

        r = NiMarenaResult(search_term="Empresa X", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestNiMarenaSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.marena import NiMarenaSource

        meta = NiMarenaSource().meta()
        assert meta.name == "ni.marena"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.ni.marena import NiMarenaSource

        src = NiMarenaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
