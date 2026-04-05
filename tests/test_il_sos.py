"""Unit tests for Illinois SOS title/registration status source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.il_sos import IlSosResult
from openquery.sources.us.il_sos import IlSosSource


class TestIlSosResult:
    """Test IlSosResult model."""

    def test_default_values(self):
        data = IlSosResult()
        assert data.vin == ""
        assert data.title_status == ""
        assert data.registration_status == ""
        assert data.lien_info == ""
        assert data.outstanding_fees == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IlSosResult(
            vin="1HGCM82633A004352",
            title_status="Active",
            registration_status="Active",
            lien_info="No lien on file",
            outstanding_fees="$0.00",
            vehicle_description="2003 HONDA ACCORD",
            details={"title status": "Active", "registration status": "Active"},
        )
        json_str = data.model_dump_json()
        restored = IlSosResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.title_status == "Active"
        assert restored.registration_status == "Active"
        assert restored.lien_info == "No lien on file"
        assert restored.outstanding_fees == "$0.00"
        assert restored.vehicle_description == "2003 HONDA ACCORD"
        assert restored.details["title status"] == "Active"

    def test_audit_excluded_from_json(self):
        data = IlSosResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_inactive_status(self):
        data = IlSosResult(
            vin="1HGCM82633A004352",
            title_status="Inactive",
            registration_status="Inactive",
        )
        assert data.title_status == "Inactive"
        assert data.registration_status == "Inactive"


class TestIlSosSourceMeta:
    """Test IlSosSource metadata."""

    def test_meta_name(self):
        source = IlSosSource()
        meta = source.meta()
        assert meta.name == "us.il_sos"

    def test_meta_country(self):
        source = IlSosSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = IlSosSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = IlSosSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = IlSosSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = IlSosSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = IlSosSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = IlSosSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, rows: list[tuple[str, str]] | None = None) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        mock_page.query_selector.return_value = None

        if rows:
            mock_rows = []
            for label, value in rows:
                mock_label_cell = MagicMock()
                mock_label_cell.inner_text.return_value = label
                mock_value_cell = MagicMock()
                mock_value_cell.inner_text.return_value = value
                mock_row = MagicMock()
                mock_row.query_selector_all.return_value = [mock_label_cell, mock_value_cell]
                mock_rows.append(mock_row)
            mock_page.query_selector_all.return_value = mock_rows
        else:
            mock_page.query_selector_all.return_value = []

        return mock_page

    def test_parse_table_active_title(self):
        source = IlSosSource()
        page = self._make_page(
            "Title Status: Active\nRegistration Status: Active\n",
            rows=[("Title Status", "Active"), ("Registration Status", "Active")],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vin == "1HGCM82633A004352"
        assert result.title_status == "Active"
        assert result.registration_status == "Active"

    def test_parse_table_with_lien(self):
        source = IlSosSource()
        page = self._make_page(
            "Title Status: Active\nLien Holder: First National Bank\n",
            rows=[("Title Status", "Active"), ("Lien Holder", "First National Bank")],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.title_status == "Active"
        assert result.lien_info == "First National Bank"

    def test_parse_table_with_fees(self):
        source = IlSosSource()
        page = self._make_page(
            "Outstanding Fees: $150.00\n",
            rows=[("Outstanding Fees", "$150.00")],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.outstanding_fees == "$150.00"

    def test_parse_not_found(self):
        source = IlSosSource()
        page = self._make_page("No record found for the provided VIN.")
        result = source._parse_results(page, "INVALIDVIN00000")
        assert result.vin == "INVALIDVIN00000"
        assert result.title_status == "Not found"

    def test_parse_vin_preserved(self):
        source = IlSosSource()
        page = self._make_page("No results.")
        result = source._parse_results(page, "TESTVIN123")
        assert result.vin == "TESTVIN123"

    def test_parse_details_populated(self):
        source = IlSosSource()
        page = self._make_page(
            "Title Status: Active",
            rows=[("Title Status", "Active"), ("Registration Status", "Inactive")],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert "title status" in result.details
        assert result.details["title status"] == "Active"

    def test_parse_vehicle_description_from_text(self):
        source = IlSosSource()
        page = self._make_page(
            "Vehicle: 2003 HONDA ACCORD\nTitle Status Active",
            rows=[("Vehicle", "2003 HONDA ACCORD"), ("Title Status", "Active")],
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert "2003 HONDA ACCORD" in result.vehicle_description
