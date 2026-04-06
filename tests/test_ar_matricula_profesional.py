"""Tests for ar.matricula_profesional — Argentina professional registration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMatriculaProfesionalResult:
    def test_defaults(self):
        from openquery.models.ar.matricula_profesional import MatriculaProfesionalResult

        r = MatriculaProfesionalResult()
        assert r.search_term == ""
        assert r.nombre == ""
        assert r.profession == ""
        assert r.license_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ar.matricula_profesional import MatriculaProfesionalResult

        r = MatriculaProfesionalResult(
            search_term="54321",
            nombre="Maria Abogada",
            profession="Derecho",
            license_status="Vigente",
        )
        dumped = r.model_dump_json()
        restored = MatriculaProfesionalResult.model_validate_json(dumped)
        assert restored.search_term == "54321"
        assert restored.license_status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.ar.matricula_profesional import MatriculaProfesionalResult

        r = MatriculaProfesionalResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestMatriculaProfesionalSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ar.matricula_profesional import MatriculaProfesionalSource

        assert MatriculaProfesionalSource().meta().name == "ar.matricula_profesional"

    def test_meta_country(self):
        from openquery.sources.ar.matricula_profesional import MatriculaProfesionalSource

        assert MatriculaProfesionalSource().meta().country == "AR"

    def test_meta_supports_custom(self):
        from openquery.sources.ar.matricula_profesional import MatriculaProfesionalSource

        assert DocumentType.CUSTOM in MatriculaProfesionalSource().meta().supported_inputs


class TestMatriculaProfesionalParseResult:
    def _make_input(self, reg: str = "54321") -> QueryInput:
        return QueryInput(
            document_number=reg,
            document_type=DocumentType.CUSTOM,
            extra={"registration_number": reg},
        )

    def test_empty_term_raises(self):
        from openquery.sources.ar.matricula_profesional import MatriculaProfesionalSource

        with pytest.raises(SourceError, match="ar.matricula_profesional"):
            MatriculaProfesionalSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.ar.matricula_profesional import MatriculaProfesionalSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Maria Abogada\nProfesión: Derecho\nEstado: Vigente"
        )
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = MatriculaProfesionalSource().query(self._make_input())

        assert result.search_term == "54321"
