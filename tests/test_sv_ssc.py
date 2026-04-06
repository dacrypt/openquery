"""Unit tests for El Salvador SSC social security source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.sv.ssc import SscResult
from openquery.sources.sv.ssc import SscSource


class TestSscResult:
    """Test SscResult model."""

    def test_default_values(self):
        data = SscResult()
        assert data.dui == ""
        assert data.affiliation_status == ""
        assert data.afp == ""
        assert data.isss == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SscResult(
            dui="00000001-1",
            affiliation_status="ACTIVO",
            afp="AFP CRECER",
            isss="AFILIADO",
        )
        json_str = data.model_dump_json()
        restored = SscResult.model_validate_json(json_str)
        assert restored.dui == "00000001-1"
        assert restored.affiliation_status == "ACTIVO"
        assert restored.afp == "AFP CRECER"
        assert restored.isss == "AFILIADO"

    def test_audit_excluded_from_json(self):
        data = SscResult(dui="00000001-1", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSscSourceMeta:
    """Test SscSource metadata."""

    def test_meta_name(self):
        source = SscSource()
        assert source.meta().name == "sv.ssc"

    def test_meta_country(self):
        source = SscSource()
        assert source.meta().country == "SV"

    def test_meta_requires_browser(self):
        source = SscSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SscSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SscSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SscSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SscSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = SscSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


class TestParseResult:
    """Test SscSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = SscSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "ACTIVO"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "AFP CRECER"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "AFILIADO ISSS"
        mock_row1.query_selector_all.return_value = [cell0, cell1, cell2]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "00000001-1")
        assert result.dui == "00000001-1"
        assert result.affiliation_status == "ACTIVO"
        assert result.afp == "AFP CRECER"
        assert result.isss == "AFILIADO ISSS"

    def test_parse_empty_page(self):
        source = SscSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "99999999-9")
        assert result.dui == "99999999-9"
        assert result.affiliation_status == ""
