"""Unit tests for ar.csjn — Argentine Supreme Court cases source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.csjn import CsjnResult
from openquery.sources.ar.csjn import CsjnSource


class TestCsjnResult:
    """Test CsjnResult model."""

    def test_default_values(self):
        data = CsjnResult()
        assert data.search_term == ""
        assert data.case_number == ""
        assert data.court == ""
        assert data.status == ""
        assert data.ruling == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CsjnResult(
            search_term="12345/2023",
            case_number="12345/2023",
            court="Corte Suprema",
            status="En trámite",
            ruling="Se admite el recurso",
            details={"raw_text": "Texto del expediente"},
        )
        json_str = data.model_dump_json()
        restored = CsjnResult.model_validate_json(json_str)
        assert restored.search_term == "12345/2023"
        assert restored.case_number == "12345/2023"
        assert restored.court == "Corte Suprema"
        assert restored.status == "En trámite"

    def test_audit_excluded_from_json(self):
        data = CsjnResult(search_term="12345/2023", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCsjnSourceMeta:
    """Test CsjnSource metadata."""

    def test_meta_name(self):
        source = CsjnSource()
        assert source.meta().name == "ar.csjn"

    def test_meta_country(self):
        source = CsjnSource()
        assert source.meta().country == "AR"

    def test_meta_rate_limit(self):
        source = CsjnSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = CsjnSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CsjnSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = CsjnSource()
        assert source._timeout == 30.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_case_number(self):
        source = CsjnSource()
        page = self._make_page(
            "Expediente 12345/2023\n"
            "Tribunal: Corte Suprema de Justicia\n"
            "Estado: En trámite\n"
            "Sentencia: Se admite el recurso extraordinario\n"
        )
        result = source._parse_result(page, "12345/2023")
        assert result.search_term == "12345/2023"
        assert result.case_number == "12345/2023"
        assert result.court == "Corte Suprema de Justicia"
        assert result.status == "En trámite"

    def test_parse_ruling(self):
        source = CsjnSource()
        page = self._make_page("Causa 99/2022\nFallo: Confirmar la sentencia apelada\n")
        result = source._parse_result(page, "99/2022")
        assert result.ruling == "Confirmar la sentencia apelada"

    def test_parse_no_results(self):
        source = CsjnSource()
        page = self._make_page("No se encontraron resultados.")
        result = source._parse_result(page, "99999/2099")
        assert result.search_term == "99999/2099"

    def test_parse_details_present(self):
        source = CsjnSource()
        page = self._make_page("Expediente 1/2024\nTribunal: CSJN")
        result = source._parse_result(page, "1/2024")
        assert "raw_text" in result.details
