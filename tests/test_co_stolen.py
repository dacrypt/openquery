"""Unit tests for Colorado stolen vehicle check source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.co_stolen import CoStolenResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.us.co_stolen import CoStolenSource


class TestCoStolenResult:
    """Test CoStolenResult model."""

    def test_default_values(self):
        data = CoStolenResult()
        assert data.vin == ""
        assert data.model_year == ""
        assert data.is_stolen is False
        assert data.status_message == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CoStolenResult(
            vin="1HGCM82633A004352",
            model_year="2003",
            is_stolen=False,
            status_message="Not reported stolen",
            details={"stolen_status": "not stolen"},
        )
        json_str = data.model_dump_json()
        restored = CoStolenResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.model_year == "2003"
        assert restored.is_stolen is False
        assert restored.status_message == "Not reported stolen"
        assert restored.details == {"stolen_status": "not stolen"}

    def test_audit_excluded_from_json(self):
        data = CoStolenResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_stolen_flag(self):
        data = CoStolenResult(
            vin="1HGCM82633A004352",
            is_stolen=True,
            details={"stolen_status": "reported stolen"},
        )
        assert data.is_stolen is True


class TestCoStolenSourceMeta:
    """Test CoStolenSource metadata."""

    def test_meta_name(self):
        source = CoStolenSource()
        meta = source.meta()
        assert meta.name == "us.co_stolen"

    def test_meta_country(self):
        source = CoStolenSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        source = CoStolenSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = CoStolenSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = CoStolenSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = CoStolenSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = CoStolenSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CoStolenSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_query_rejects_wrong_type(self):
        import pytest

        from openquery.exceptions import SourceError

        source = CoStolenSource()
        inp = QueryInput(document_type=DocumentType.CEDULA, document_number="123")
        with pytest.raises(SourceError):
            source.query(inp)

    def test_query_requires_year(self):
        import pytest

        from openquery.exceptions import SourceError

        source = CoStolenSource()
        inp = QueryInput(document_type=DocumentType.VIN, document_number="1HGCM82633A004352")
        with pytest.raises(SourceError, match="year"):
            source.query(inp)


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, heading: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if heading:
            mock_el = MagicMock()
            mock_el.inner_text.return_value = heading
            mock_page.query_selector.return_value = mock_el
        else:
            mock_page.query_selector.return_value = None
        return mock_page

    def test_parse_not_stolen(self):
        source = CoStolenSource()
        page = self._make_page(
            "Colorado Motor Vehicle Verification System\n"
            "VIN: 1HGCM82633A004352\n"
            "This vehicle is not reported stolen.\n",
            heading="Vehicle is clear",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "2003")
        assert result.vin == "1HGCM82633A004352"
        assert result.model_year == "2003"
        assert result.is_stolen is False
        assert result.details.get("stolen_status") == "not stolen"

    def test_parse_stolen(self):
        source = CoStolenSource()
        page = self._make_page(
            "Colorado Motor Vehicle Verification System\n"
            "VIN: 1HGCM82633A004352\n"
            "This vehicle has been reported stolen.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "2003")
        assert result.is_stolen is True
        assert result.details.get("stolen_status") == "reported stolen"

    def test_parse_clear_keyword(self):
        source = CoStolenSource()
        page = self._make_page(
            "Result: clear\nNo theft record found.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "2020")
        assert result.is_stolen is False

    def test_parse_vin_and_year_preserved(self):
        source = CoStolenSource()
        page = self._make_page("No record found.")
        result = source._parse_results(page, "TESTVIN123", "1999")
        assert result.vin == "TESTVIN123"
        assert result.model_year == "1999"

    def test_parse_no_match_defaults_not_stolen(self):
        source = CoStolenSource()
        page = self._make_page("Colorado Motor Vehicle Verification System")
        result = source._parse_results(page, "1HGCM82633A004352", "2010")
        assert result.is_stolen is False
