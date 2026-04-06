"""Unit tests for mx.impi — Mexico trademark search source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.impi import ImpiResult
from openquery.sources.mx.impi import ImpiSource


class TestImpiResult:
    """Test ImpiResult model."""

    def test_default_values(self):
        data = ImpiResult()
        assert data.search_term == ""
        assert data.trademark_name == ""
        assert data.owner == ""
        assert data.status == ""
        assert data.registration_date == ""
        assert data.trademark_class == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ImpiResult(
            search_term="ACME",
            trademark_name="ACME TOOLS",
            owner="Acme Corporation SA de CV",
            status="Registrada",
            registration_date="2020-05-10",
            trademark_class="8",
            details={"raw_text": "Registrada"},
        )
        json_str = data.model_dump_json()
        restored = ImpiResult.model_validate_json(json_str)
        assert restored.search_term == "ACME"
        assert restored.trademark_name == "ACME TOOLS"
        assert restored.owner == "Acme Corporation SA de CV"
        assert restored.status == "Registrada"

    def test_audit_excluded_from_json(self):
        data = ImpiResult(search_term="ACME", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestImpiSourceMeta:
    """Test ImpiSource metadata."""

    def test_meta_name(self):
        source = ImpiSource()
        assert source.meta().name == "mx.impi"

    def test_meta_country(self):
        source = ImpiSource()
        assert source.meta().country == "MX"

    def test_meta_rate_limit(self):
        source = ImpiSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = ImpiSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ImpiSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = ImpiSource()
        assert source._timeout == 30.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_trademark_name(self):
        source = ImpiSource()
        page = self._make_page(
            "Resultados IMPI\n"
            "Denominación: ACME TOOLS\n"
            "Titular: Acme Corporation SA de CV\n"
            "Estado: Registrada\n"
            "Clase: 8\n"
        )
        result = source._parse_result(page, "ACME")
        assert result.search_term == "ACME"
        assert result.trademark_name == "ACME TOOLS"
        assert result.owner == "Acme Corporation SA de CV"
        assert result.status == "Registrada"
        assert result.trademark_class == "8"

    def test_parse_no_results(self):
        source = ImpiSource()
        page = self._make_page("Sin resultados encontrados.")
        result = source._parse_result(page, "UNKNOWNBRAND")
        assert result.search_term == "UNKNOWNBRAND"
        assert result.trademark_name == ""

    def test_parse_details_present(self):
        source = ImpiSource()
        page = self._make_page("Marca: TEST\nTitular: Owner Corp")
        result = source._parse_result(page, "TEST")
        assert "raw_text" in result.details
