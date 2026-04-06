"""Unit tests for Paraguay SENAVE phytosanitary registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.py.senave import SenaveResult
from openquery.sources.py.senave import SenaveSource


class TestSenaveResult:
    """Test SenaveResult model."""

    def test_default_values(self):
        data = SenaveResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SenaveResult(
            search_term="AGRO SA",
            company_name="AGROQUIMICA SA",
            registration_status="HABILITADO",
        )
        json_str = data.model_dump_json()
        restored = SenaveResult.model_validate_json(json_str)
        assert restored.search_term == "AGRO SA"
        assert restored.company_name == "AGROQUIMICA SA"
        assert restored.registration_status == "HABILITADO"

    def test_audit_excluded_from_json(self):
        data = SenaveResult(search_term="AGRO SA", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSenaveSourceMeta:
    """Test SenaveSource metadata."""

    def test_meta_name(self):
        source = SenaveSource()
        assert source.meta().name == "py.senave"

    def test_meta_country(self):
        source = SenaveSource()
        assert source.meta().country == "PY"

    def test_meta_requires_browser(self):
        source = SenaveSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SenaveSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SenaveSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SenaveSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SenaveSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SenaveSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test SenaveSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = SenaveSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "AGROQUIMICA PARAGUAYA SA"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "HABILITADO"
        mock_row1.query_selector_all.return_value = [cell0, cell1]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "AGRO SA")
        assert result.search_term == "AGRO SA"
        assert result.company_name == "AGROQUIMICA PARAGUAYA SA"
        assert result.registration_status == "HABILITADO"

    def test_parse_empty_page(self):
        source = SenaveSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "NO EXISTE SA")
        assert result.search_term == "NO EXISTE SA"
        assert result.company_name == ""
