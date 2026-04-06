"""Tests for pa.tribunal_cuentas — Tribunal de Cuentas audit findings lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test TribunalCuentasResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult

        r = TribunalCuentasResult()
        assert r.search_term == ""
        assert r.entity_name == ""
        assert r.findings == []
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult

        r = TribunalCuentasResult(search_term="MINISTERIO", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "MINISTERIO" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult

        r = TribunalCuentasResult(
            search_term="MINISTERIO",
            entity_name="MINISTERIO DE SALUD",
            findings=[{"col_0": "Proceso 001", "col_1": "En curso"}],
            details={"Fecha": "2024"},
        )
        r2 = TribunalCuentasResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "MINISTERIO"
        assert r2.entity_name == "MINISTERIO DE SALUD"
        assert len(r2.findings) == 1
        assert r2.findings[0]["col_0"] == "Proceso 001"

    def test_queried_at_default(self):
        from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult

        before = datetime.now()
        r = TribunalCuentasResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test pa.tribunal_cuentas source metadata."""

    def test_meta_name(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        meta = TribunalCuentasSource().meta()
        assert meta.name == "pa.tribunal_cuentas"

    def test_meta_country(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        meta = TribunalCuentasSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        meta = TribunalCuentasSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        meta = TribunalCuentasSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        meta = TribunalCuentasSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        return TribunalCuentasSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        page.query_selector_all.return_value = []
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.entity_name == ""
        assert result.findings == []

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultados de la consulta")
        result = src._parse_result(page, "MINISTERIO")
        assert result.search_term == "MINISTERIO"

    def test_entity_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Entidad: MINISTERIO DE SALUD\nFecha: 2024")
        result = src._parse_result(page, "MINISTERIO")
        assert result.entity_name == "MINISTERIO DE SALUD"

    def test_details_populated(self):
        src = self._make_source()
        page = self._make_page("Fecha: 2024\nExpediente: 001-2024")
        result = src._parse_result(page, "MINISTERIO")
        assert "Fecha" in result.details

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        src = TribunalCuentasSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult
        from openquery.sources.pa.tribunal_cuentas import TribunalCuentasSource

        src = TribunalCuentasSource()
        mock_result = TribunalCuentasResult(search_term="MINISTERIO")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="MINISTERIO")
            )
            m.assert_called_once_with("MINISTERIO", audit=False)
