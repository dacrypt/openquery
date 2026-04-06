"""Unit tests for Arizona MVD title/lien status source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.az_mvd import AzMvdResult
from openquery.sources.us.az_mvd import AzMvdSource


class TestAzMvdResult:
    """Test AzMvdResult model."""

    def test_default_values(self):
        data = AzMvdResult()
        assert data.vin == ""
        assert data.title_status == ""
        assert data.lien_status == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = AzMvdResult(
            vin="1HGCM82633A004352",
            title_status="Clear",
            lien_status="No Lien",
            vehicle_description="2003 HONDA ACCORD",
            details={"title_status": "Clear", "lien_status": "No Lien"},
        )
        json_str = data.model_dump_json()
        restored = AzMvdResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.title_status == "Clear"
        assert restored.lien_status == "No Lien"
        assert restored.vehicle_description == "2003 HONDA ACCORD"
        assert restored.details["title_status"] == "Clear"

    def test_audit_excluded_from_json(self):
        data = AzMvdResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_lien_reported(self):
        data = AzMvdResult(
            vin="1HGCM82633A004352",
            title_status="Clear",
            lien_status="Lien Reported",
        )
        assert data.lien_status == "Lien Reported"
        assert data.title_status == "Clear"


class TestAzMvdSourceMeta:
    """Test AzMvdSource metadata."""

    def test_meta_name(self):
        source = AzMvdSource()
        meta = source.meta()
        assert meta.name == "us.az_mvd"

    def test_meta_country(self):
        source = AzMvdSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = AzMvdSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = AzMvdSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = AzMvdSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = AzMvdSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = AzMvdSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = AzMvdSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, selector_text: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if selector_text:
            mock_el = MagicMock()
            mock_el.inner_text.return_value = selector_text
            mock_page.query_selector.return_value = mock_el
        else:
            mock_page.query_selector.return_value = None
        return mock_page

    def test_parse_clear_no_lien(self):
        source = AzMvdSource()
        page = self._make_page(
            "Title Check Results\nTitle Status: Clear\nNo lien reported for this vehicle.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vin == "1HGCM82633A004352"
        assert result.title_status == "Clear"
        assert result.lien_status == "No Lien"

    def test_parse_lien_reported(self):
        source = AzMvdSource()
        page = self._make_page(
            "Title Check Results\nTitle Status: Clear\nLien: First National Bank\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.lien_status == "Lien Reported"

    def test_parse_salvage_title(self):
        source = AzMvdSource()
        page = self._make_page(
            "Title Check Results\nTitle Status: Salvage\nNo liens on record.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.title_status == "Salvage"

    def test_parse_rebuilt_title(self):
        source = AzMvdSource()
        page = self._make_page(
            "Title Check Results\nThis vehicle has a rebuilt title.\nNo lien found.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.title_status == "Rebuilt"

    def test_parse_vin_preserved(self):
        source = AzMvdSource()
        page = self._make_page("No title records found.")
        result = source._parse_results(page, "TESTVIN123")
        assert result.vin == "TESTVIN123"

    def test_parse_vehicle_description(self):
        source = AzMvdSource()
        page = self._make_page(
            "Title Check Results\nClear title.\nNo lien.\n",
            selector_text="2003 HONDA ACCORD EX",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vehicle_description == "2003 HONDA ACCORD EX"
