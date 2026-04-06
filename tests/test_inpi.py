"""Unit tests for ar.inpi — Argentine trademark search source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.inpi import InpiResult
from openquery.sources.ar.inpi import InpiSource


class TestInpiResult:
    """Test InpiResult model."""

    def test_default_values(self):
        data = InpiResult()
        assert data.search_term == ""
        assert data.trademark_name == ""
        assert data.owner == ""
        assert data.status == ""
        assert data.trademark_class == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = InpiResult(
            search_term="QUILMES",
            trademark_name="QUILMES",
            owner="Cerveceria Argentina SA",
            status="Registrada",
            trademark_class="32",
            details={"raw_text": "Registrada"},
        )
        json_str = data.model_dump_json()
        restored = InpiResult.model_validate_json(json_str)
        assert restored.search_term == "QUILMES"
        assert restored.trademark_name == "QUILMES"
        assert restored.owner == "Cerveceria Argentina SA"
        assert restored.status == "Registrada"
        assert restored.trademark_class == "32"

    def test_audit_excluded_from_json(self):
        data = InpiResult(search_term="QUILMES", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestInpiSourceMeta:
    """Test InpiSource metadata."""

    def test_meta_name(self):
        source = InpiSource()
        assert source.meta().name == "ar.inpi"

    def test_meta_country(self):
        source = InpiSource()
        assert source.meta().country == "AR"

    def test_meta_rate_limit(self):
        source = InpiSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = InpiSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = InpiSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = InpiSource()
        assert source._timeout == 30.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_trademark(self):
        source = InpiSource()
        page = self._make_page(
            "Resultados INPI\n"
            "Denominación: QUILMES\n"
            "Titular: Cerveceria Argentina SA\n"
            "Estado: Registrada\n"
            "Clase: 32\n"
        )
        result = source._parse_result(page, "QUILMES")
        assert result.search_term == "QUILMES"
        assert result.trademark_name == "QUILMES"
        assert result.owner == "Cerveceria Argentina SA"
        assert result.status == "Registrada"
        assert result.trademark_class == "32"

    def test_parse_no_results(self):
        source = InpiSource()
        page = self._make_page("Sin resultados encontrados.")
        result = source._parse_result(page, "UNKNOWNMARK")
        assert result.search_term == "UNKNOWNMARK"
        assert result.trademark_name == ""

    def test_parse_details_present(self):
        source = InpiSource()
        page = self._make_page("Marca: TEST")
        result = source._parse_result(page, "TEST")
        assert "raw_text" in result.details
