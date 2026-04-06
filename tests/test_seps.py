"""Unit tests for Ecuador SEPS Superintendencia de Economía Popular y Solidaria source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.seps import SepsResult
from openquery.sources.ec.seps import SepsSource


class TestSepsResult:
    """Test SepsResult model."""

    def test_default_values(self):
        data = SepsResult()
        assert data.search_term == ""
        assert data.organization_name == ""
        assert data.ruc == ""
        assert data.status == ""
        assert data.organization_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SepsResult(
            search_term="COOPERATIVA TEST",
            organization_name="COOPERATIVA DE AHORRO TEST LTDA",
            ruc="0912345678001",
            status="ACTIVA",
            organization_type="COOPERATIVA DE AHORRO Y CREDITO",
            details={"supervisor": "SEPS"},
        )
        json_str = data.model_dump_json()
        restored = SepsResult.model_validate_json(json_str)
        assert restored.search_term == "COOPERATIVA TEST"
        assert restored.organization_name == "COOPERATIVA DE AHORRO TEST LTDA"
        assert restored.ruc == "0912345678001"
        assert restored.status == "ACTIVA"
        assert restored.organization_type == "COOPERATIVA DE AHORRO Y CREDITO"
        assert restored.details["supervisor"] == "SEPS"

    def test_audit_excluded_from_json(self):
        data = SepsResult(search_term="TEST", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}


class TestSepsSourceMeta:
    """Test SepsSource metadata."""

    def test_meta_name(self):
        source = SepsSource()
        meta = source.meta()
        assert meta.name == "ec.seps"

    def test_meta_country(self):
        source = SepsSource()
        meta = source.meta()
        assert meta.country == "EC"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SepsSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = SepsSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = SepsSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = SepsSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = SepsSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SepsSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_organization_name(self):
        source = SepsSource()
        page = self._make_page(
            "Resultados de búsqueda\n"
            "Razón Social: COOPERATIVA DE AHORRO TEST LTDA\n"
            "Estado: ACTIVA\n"
        )
        result = source._parse_result(page, "COOPERATIVA TEST")
        assert result.search_term == "COOPERATIVA TEST"
        assert result.organization_name == "COOPERATIVA DE AHORRO TEST LTDA"

    def test_parse_ruc(self):
        source = SepsSource()
        page = self._make_page(
            "Razón Social: COOPERATIVA TEST LTDA\nRUC: 0912345678001\nEstado: ACTIVA\n"
        )
        result = source._parse_result(page, "0912345678001")
        assert result.ruc == "0912345678001"

    def test_parse_status(self):
        source = SepsSource()
        page = self._make_page(
            "Razón Social: COOPERATIVA TEST LTDA\n"
            "Estado: ACTIVA\n"
            "Tipo: COOPERATIVA DE AHORRO Y CREDITO\n"
        )
        result = source._parse_result(page, "COOPERATIVA TEST")
        assert result.status == "ACTIVA"

    def test_parse_organization_type(self):
        source = SepsSource()
        page = self._make_page(
            "Razón Social: COOPERATIVA TEST LTDA\nTipo: COOPERATIVA DE AHORRO Y CREDITO\n"
        )
        result = source._parse_result(page, "COOPERATIVA TEST")
        assert result.organization_type == "COOPERATIVA DE AHORRO Y CREDITO"

    def test_parse_search_term_preserved(self):
        source = SepsSource()
        page = self._make_page("No se encontraron resultados.")
        result = source._parse_result(page, "BUSQUEDA TEST")
        assert result.search_term == "BUSQUEDA TEST"

    def test_parse_empty_body(self):
        source = SepsSource()
        page = self._make_page("")
        result = source._parse_result(page, "TEST")
        assert result.organization_name == ""
        assert result.status == ""
