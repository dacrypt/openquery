"""Tests for co.superfinanciera — Superfinanciera supervised entities lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test SuperfinancieraResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.co.superfinanciera import SuperfinancieraResult

        r = SuperfinancieraResult()
        assert r.search_term == ""
        assert r.entity_name == ""
        assert r.entity_type == ""
        assert r.supervision_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.co.superfinanciera import SuperfinancieraResult

        r = SuperfinancieraResult(search_term="BANCOLOMBIA", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "BANCOLOMBIA" in dumped

    def test_json_roundtrip(self):
        from openquery.models.co.superfinanciera import SuperfinancieraResult

        r = SuperfinancieraResult(
            search_term="BANCOLOMBIA",
            entity_name="BANCOLOMBIA S.A.",
            entity_type="Banco",
            supervision_status="Autorizado",
            details={"NIT": "890.903.938-8"},
        )
        r2 = SuperfinancieraResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "BANCOLOMBIA"
        assert r2.entity_name == "BANCOLOMBIA S.A."
        assert r2.entity_type == "Banco"
        assert r2.supervision_status == "Autorizado"

    def test_queried_at_default(self):
        from openquery.models.co.superfinanciera import SuperfinancieraResult

        before = datetime.now()
        r = SuperfinancieraResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test co.superfinanciera source metadata."""

    def test_meta_name(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        meta = SuperfinancieraSource().meta()
        assert meta.name == "co.superfinanciera"

    def test_meta_country(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        meta = SuperfinancieraSource().meta()
        assert meta.country == "CO"

    def test_meta_requires_browser(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        meta = SuperfinancieraSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        meta = SuperfinancieraSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        meta = SuperfinancieraSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        return SuperfinancieraSource()

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
        assert result.supervision_status == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultados de la consulta")
        result = src._parse_result(page, "BANCOLOMBIA")
        assert result.search_term == "BANCOLOMBIA"

    def test_entity_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Entidad: BANCOLOMBIA S.A.\nTipo: Banco")
        result = src._parse_result(page, "BANCOLOMBIA")
        assert result.entity_name == "BANCOLOMBIA S.A."

    def test_entity_type_parsed(self):
        src = self._make_source()
        page = self._make_page("Tipo: Banco\nEstado: Autorizado")
        result = src._parse_result(page, "BANCOLOMBIA")
        assert result.entity_type == "Banco"

    def test_supervision_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Estado: Autorizado\nOtros datos")
        result = src._parse_result(page, "BANCOLOMBIA")
        assert result.supervision_status == "Autorizado"

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        src = SuperfinancieraSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.co.superfinanciera import SuperfinancieraResult
        from openquery.sources.co.superfinanciera import SuperfinancieraSource

        src = SuperfinancieraSource()
        mock_result = SuperfinancieraResult(search_term="BANCOLOMBIA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="BANCOLOMBIA")
            )
            m.assert_called_once_with("BANCOLOMBIA", audit=False)
