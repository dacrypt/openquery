"""Unit tests for Costa Rica CCSS social security source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cr.ccss import CcssResult
from openquery.sources.cr.ccss import CcssSource


class TestCcssResult:
    """Test CcssResult model."""

    def test_default_values(self):
        data = CcssResult()
        assert data.cedula == ""
        assert data.affiliation_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CcssResult(
            cedula="100000001",
            affiliation_status="ASEGURADO DIRECTO",
        )
        json_str = data.model_dump_json()
        restored = CcssResult.model_validate_json(json_str)
        assert restored.cedula == "100000001"
        assert restored.affiliation_status == "ASEGURADO DIRECTO"

    def test_audit_excluded_from_json(self):
        data = CcssResult(cedula="100000001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCcssSourceMeta:
    """Test CcssSource metadata."""

    def test_meta_name(self):
        source = CcssSource()
        assert source.meta().name == "cr.ccss"

    def test_meta_country(self):
        source = CcssSource()
        assert source.meta().country == "CR"

    def test_meta_requires_browser(self):
        source = CcssSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CcssSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CcssSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CcssSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CcssSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = CcssSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


class TestParseResult:
    """Test CcssSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = CcssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "ASEGURADO DIRECTO"
        mock_row1.query_selector_all.return_value = [cell0]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "100000001")
        assert result.cedula == "100000001"
        assert result.affiliation_status == "ASEGURADO DIRECTO"

    def test_parse_from_text_labels(self):
        source = CcssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Estado: ASEGURADO FAMILIAR\n"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "200000002")
        assert result.cedula == "200000002"

    def test_parse_empty_page(self):
        source = CcssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "999999999")
        assert result.cedula == "999999999"
        assert result.affiliation_status == ""
