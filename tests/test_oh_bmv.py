"""Unit tests for Ohio BMV title search source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.oh_bmv import OhBmvResult
from openquery.sources.us.oh_bmv import OhBmvSource


class TestOhBmvResult:
    """Test OhBmvResult model."""

    def test_default_values(self):
        data = OhBmvResult()
        assert data.vin == ""
        assert data.title_number == ""
        assert data.title_status == ""
        assert data.lien_status == ""
        assert data.vehicle_description == ""
        assert data.owner_verification == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OhBmvResult(
            vin="1HGCM82633A004352",
            title_number="OH12345678",
            title_status="Clean Title",
            lien_status="No Lien",
            vehicle_description="2003 Honda Accord",
            owner_verification="Verified",
            details={"Title Status": "Clean Title", "Lien Status": "No Lien"},
        )
        json_str = data.model_dump_json()
        restored = OhBmvResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.title_number == "OH12345678"
        assert restored.title_status == "Clean Title"
        assert restored.lien_status == "No Lien"
        assert restored.vehicle_description == "2003 Honda Accord"

    def test_audit_excluded_from_json(self):
        data = OhBmvResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_details_dict(self):
        data = OhBmvResult(details={"Title Status": "Salvage", "Lien": "Recorded"})
        assert data.details["Title Status"] == "Salvage"
        assert data.details["Lien"] == "Recorded"


class TestOhBmvSourceMeta:
    """Test OhBmvSource metadata."""

    def test_meta_name(self):
        source = OhBmvSource()
        meta = source.meta()
        assert meta.name == "us.oh_bmv"

    def test_meta_country(self):
        source = OhBmvSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = OhBmvSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = OhBmvSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = OhBmvSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = OhBmvSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = OhBmvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = OhBmvSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, rows: list[str] | None = None) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if rows is not None:
            mock_els = []
            for text in rows:
                el = MagicMock()
                el.inner_text.return_value = text
                mock_els.append(el)
            mock_page.query_selector_all.return_value = mock_els
        else:
            mock_page.query_selector_all.return_value = []
        return mock_page

    def test_parse_no_lien(self):
        source = OhBmvSource()
        page = self._make_page(
            "Title Search Results\n"
            "Title Status: Clean Title\n"
            "No lien recorded for this vehicle.\n"
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vin == "1HGCM82633A004352"
        assert result.lien_status == "No Lien"

    def test_parse_lien_recorded(self):
        source = OhBmvSource()
        page = self._make_page(
            "Title Search Results\n"
            "Lien holder: First National Bank\n"
            "Lien recorded on this vehicle.\n"
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.lien_status == "Lien Recorded"

    def test_parse_salvage_title(self):
        source = OhBmvSource()
        page = self._make_page(
            "Title Search Results\n"
            "Title type: Salvage\n"
            "This vehicle has a salvage title.\n"
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.title_status == "Salvage"

    def test_parse_table_rows(self):
        source = OhBmvSource()
        page = self._make_page(
            "Title Search Results",
            rows=[
                "Title Status:",
                "Clean Title",
                "Lien Status:",
                "No Lien",
                "Vehicle Description:",
                "2003 Honda Accord",
                "Title Number:",
                "OH99887766",
            ],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.title_status == "Clean Title"
        assert result.lien_status == "No Lien"
        assert result.title_number == "OH99887766"

    def test_parse_vin_preserved(self):
        source = OhBmvSource()
        page = self._make_page("No records found.")
        result = source._parse_results(page, "TESTVIN12345678AB")
        assert result.vin == "TESTVIN12345678AB"

    def test_parse_empty_page(self):
        source = OhBmvSource()
        page = self._make_page("")
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vin == "1HGCM82633A004352"
        assert result.title_status == ""
        assert result.lien_status == ""
