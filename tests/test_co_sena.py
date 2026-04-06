"""Tests for co.sena — SENA certification/training verification."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test SenaResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.co.sena import SenaResult

        r = SenaResult()
        assert r.documento == ""
        assert r.nombre == ""
        assert r.certification_status == ""
        assert r.program == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.co.sena import SenaResult

        r = SenaResult(documento="12345678", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "12345678" in dumped

    def test_json_roundtrip(self):
        from openquery.models.co.sena import SenaResult

        r = SenaResult(
            documento="12345678",
            nombre="JUAN PEREZ",
            certification_status="Certificado",
            program="Sistemas",
            details={"Ficha": "1234"},
        )
        r2 = SenaResult.model_validate_json(r.model_dump_json())
        assert r2.documento == "12345678"
        assert r2.nombre == "JUAN PEREZ"
        assert r2.certification_status == "Certificado"
        assert r2.program == "Sistemas"

    def test_queried_at_default(self):
        from openquery.models.co.sena import SenaResult

        before = datetime.now()
        r = SenaResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test co.sena source metadata."""

    def test_meta_name(self):
        from openquery.sources.co.sena import SenaSource

        meta = SenaSource().meta()
        assert meta.name == "co.sena"

    def test_meta_country(self):
        from openquery.sources.co.sena import SenaSource

        meta = SenaSource().meta()
        assert meta.country == "CO"

    def test_meta_requires_browser(self):
        from openquery.sources.co.sena import SenaSource

        meta = SenaSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.co.sena import SenaSource

        meta = SenaSource().meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.co.sena import SenaSource

        meta = SenaSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.co.sena import SenaSource

        return SenaSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("No se encontró información para el documento")
        result = src._parse_result(page, "99999999")
        assert result.documento == "99999999"
        assert result.nombre == ""
        assert result.certification_status == ""

    def test_documento_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultado encontrado")
        result = src._parse_result(page, "12345678")
        assert result.documento == "12345678"

    def test_nombre_parsed(self):
        src = self._make_source()
        page = self._make_page("Nombre: JUAN PEREZ\nEstado: Certificado")
        result = src._parse_result(page, "12345678")
        assert result.nombre == "JUAN PEREZ"

    def test_program_parsed(self):
        src = self._make_source()
        page = self._make_page("Programa: Sistemas\nEstado: Certificado")
        result = src._parse_result(page, "12345678")
        assert result.program == "Sistemas"

    def test_certification_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Estado: Certificado\nOtros datos")
        result = src._parse_result(page, "12345678")
        assert result.certification_status == "Certificado"

    def test_query_missing_documento_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.co.sena import SenaSource

        src = SenaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.co.sena import SenaResult
        from openquery.sources.co.sena import SenaSource

        src = SenaSource()
        mock_result = SenaResult(documento="12345678")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(document_type=DocumentType.CEDULA, document_number="12345678")
            )
            m.assert_called_once_with("12345678", audit=False)
