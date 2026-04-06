"""Tests for co.supersalud — Supersalud health entities lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test SupersaludResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.co.supersalud import SupersaludResult

        r = SupersaludResult()
        assert r.search_term == ""
        assert r.entity_name == ""
        assert r.entity_type == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.co.supersalud import SupersaludResult

        r = SupersaludResult(search_term="SURA EPS", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "SURA EPS" in dumped

    def test_json_roundtrip(self):
        from openquery.models.co.supersalud import SupersaludResult

        r = SupersaludResult(
            search_term="SURA EPS",
            entity_name="EPS SURA",
            entity_type="EPS",
            status="Habilitado",
            details={"NIT": "800.088.702-2"},
        )
        r2 = SupersaludResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "SURA EPS"
        assert r2.entity_name == "EPS SURA"
        assert r2.entity_type == "EPS"
        assert r2.status == "Habilitado"

    def test_queried_at_default(self):
        from openquery.models.co.supersalud import SupersaludResult

        before = datetime.now()
        r = SupersaludResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test co.supersalud source metadata."""

    def test_meta_name(self):
        from openquery.sources.co.supersalud import SupersaludSource

        meta = SupersaludSource().meta()
        assert meta.name == "co.supersalud"

    def test_meta_country(self):
        from openquery.sources.co.supersalud import SupersaludSource

        meta = SupersaludSource().meta()
        assert meta.country == "CO"

    def test_meta_requires_browser(self):
        from openquery.sources.co.supersalud import SupersaludSource

        meta = SupersaludSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.co.supersalud import SupersaludSource

        meta = SupersaludSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.co.supersalud import SupersaludSource

        meta = SupersaludSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.co.supersalud import SupersaludSource

        return SupersaludSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.entity_name == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultados de la consulta")
        result = src._parse_result(page, "SURA EPS")
        assert result.search_term == "SURA EPS"

    def test_entity_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Entidad: EPS SURA\nTipo: EPS")
        result = src._parse_result(page, "SURA EPS")
        assert result.entity_name == "EPS SURA"

    def test_entity_type_parsed(self):
        src = self._make_source()
        page = self._make_page("Clase: EPS\nEstado: Habilitado")
        result = src._parse_result(page, "SURA EPS")
        assert result.entity_type == "EPS"

    def test_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Estado: Habilitado\nOtros datos")
        result = src._parse_result(page, "SURA EPS")
        assert result.status == "Habilitado"

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.co.supersalud import SupersaludSource

        src = SupersaludSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.co.supersalud import SupersaludResult
        from openquery.sources.co.supersalud import SupersaludSource

        src = SupersaludSource()
        mock_result = SupersaludResult(search_term="SURA EPS")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="SURA EPS"))
            m.assert_called_once_with("SURA EPS", audit=False)
