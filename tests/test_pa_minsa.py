"""Tests for pa.minsa — MINSA health registry lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test MinsaResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pa.minsa import MinsaResult

        r = MinsaResult()
        assert r.search_term == ""
        assert r.establishment_name == ""
        assert r.permit_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.minsa import MinsaResult

        r = MinsaResult(search_term="CLINICA PANAMA", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "CLINICA PANAMA" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pa.minsa import MinsaResult

        r = MinsaResult(
            search_term="CLINICA PANAMA",
            establishment_name="CLINICA PANAMA S.A.",
            permit_status="Habilitado",
            details={"Tipo": "Clínica"},
        )
        r2 = MinsaResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "CLINICA PANAMA"
        assert r2.establishment_name == "CLINICA PANAMA S.A."
        assert r2.permit_status == "Habilitado"

    def test_queried_at_default(self):
        from openquery.models.pa.minsa import MinsaResult

        before = datetime.now()
        r = MinsaResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test pa.minsa source metadata."""

    def test_meta_name(self):
        from openquery.sources.pa.minsa import MinsaSource

        meta = MinsaSource().meta()
        assert meta.name == "pa.minsa"

    def test_meta_country(self):
        from openquery.sources.pa.minsa import MinsaSource

        meta = MinsaSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.minsa import MinsaSource

        meta = MinsaSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.pa.minsa import MinsaSource

        meta = MinsaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.minsa import MinsaSource

        meta = MinsaSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.pa.minsa import MinsaSource

        return MinsaSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.establishment_name == ""
        assert result.permit_status == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultados de la consulta")
        result = src._parse_result(page, "CLINICA PANAMA")
        assert result.search_term == "CLINICA PANAMA"

    def test_establishment_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Establecimiento: CLINICA PANAMA S.A.\nPermiso: Habilitado")
        result = src._parse_result(page, "CLINICA PANAMA")
        assert result.establishment_name == "CLINICA PANAMA S.A."

    def test_permit_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Estado: Habilitado\nOtros datos")
        result = src._parse_result(page, "CLINICA PANAMA")
        assert result.permit_status == "Habilitado"

    def test_details_populated(self):
        src = self._make_source()
        page = self._make_page("Tipo: Clínica\nRegión: Panamá")
        result = src._parse_result(page, "CLINICA PANAMA")
        assert "Tipo" in result.details

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pa.minsa import MinsaSource

        src = MinsaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.pa.minsa import MinsaResult
        from openquery.sources.pa.minsa import MinsaSource

        src = MinsaSource()
        mock_result = MinsaResult(search_term="CLINICA PANAMA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="CLINICA PANAMA")
            )
            m.assert_called_once_with("CLINICA PANAMA", audit=False)
