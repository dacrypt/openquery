"""Tests for co.consejo_profesional — Professional council verification."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestConsejoProfesionalResult:
    def test_defaults(self):
        from openquery.models.co.consejo_profesional import ConsejoProfesionalResult

        r = ConsejoProfesionalResult()
        assert r.documento == ""
        assert r.nombre == ""
        assert r.profesion == ""
        assert r.estado_matricula == ""
        assert r.matricula == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.consejo_profesional import ConsejoProfesionalResult

        r = ConsejoProfesionalResult(
            documento="12345678",
            nombre="Juan Ingeniero",
            profesion="Ingeniería Civil",
            estado_matricula="Vigente",
        )
        dumped = r.model_dump_json()
        restored = ConsejoProfesionalResult.model_validate_json(dumped)
        assert restored.documento == "12345678"
        assert restored.estado_matricula == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.consejo_profesional import ConsejoProfesionalResult

        r = ConsejoProfesionalResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestConsejoProfesionalSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.consejo_profesional import ConsejoProfesionalSource

        assert ConsejoProfesionalSource().meta().name == "co.consejo_profesional"

    def test_meta_country(self):
        from openquery.sources.co.consejo_profesional import ConsejoProfesionalSource

        assert ConsejoProfesionalSource().meta().country == "CO"

    def test_meta_supports_cedula(self):
        from openquery.sources.co.consejo_profesional import ConsejoProfesionalSource

        assert DocumentType.CEDULA in ConsejoProfesionalSource().meta().supported_inputs


class TestConsejoProfesionalParseResult:
    def _make_input(self, documento: str = "12345678") -> QueryInput:
        return QueryInput(document_number=documento, document_type=DocumentType.CEDULA)

    def test_empty_document_raises(self):
        from openquery.sources.co.consejo_profesional import ConsejoProfesionalSource

        with pytest.raises(SourceError, match="co.consejo_profesional"):
            ConsejoProfesionalSource().query(
                QueryInput(document_number="", document_type=DocumentType.CEDULA)
            )

    def test_query_returns_result(self):
        from openquery.sources.co.consejo_profesional import ConsejoProfesionalSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Juan Ingeniero\nProfesión: Ingeniería Civil\nEstado: Vigente"
        )
        mock_page.query_selector.return_value = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = ConsejoProfesionalSource().query(self._make_input())

        assert result.documento == "12345678"
