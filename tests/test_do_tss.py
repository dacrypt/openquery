"""Unit tests for Dominican Republic TSS social security source."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openquery.models.do.tss import TssResult
from openquery.sources.do.tss import TssSource


class TestTssResult:
    """Test TssResult model."""

    def test_default_values(self):
        data = TssResult()
        assert data.cedula == ""
        assert data.affiliation_status == ""
        assert data.employer == ""
        assert data.ars == ""
        assert data.afp == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = TssResult(
            cedula="00100000001",
            affiliation_status="ACTIVO",
            employer="EMPRESA SA",
            ars="ARS UNIVERSAL",
            afp="AFP CRECER",
        )
        json_str = data.model_dump_json()
        restored = TssResult.model_validate_json(json_str)
        assert restored.cedula == "00100000001"
        assert restored.affiliation_status == "ACTIVO"
        assert restored.employer == "EMPRESA SA"
        assert restored.ars == "ARS UNIVERSAL"
        assert restored.afp == "AFP CRECER"

    def test_audit_excluded_from_json(self):
        data = TssResult(cedula="00100000001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestTssSourceMeta:
    """Test TssSource metadata."""

    def test_meta_name(self):
        source = TssSource()
        assert source.meta().name == "do.tss"

    def test_meta_country(self):
        source = TssSource()
        assert source.meta().country == "DO"

    def test_meta_requires_browser(self):
        source = TssSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = TssSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = TssSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = TssSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = TssSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = TssSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


class TestParseResult:
    """Test TssSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = TssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "ACTIVO"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "EMPRESA DOMINICANA SA"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "ARS UNIVERSAL"
        cell3 = MagicMock()
        cell3.inner_text.return_value = "AFP SIEMBRA"
        mock_row1.query_selector_all.return_value = [cell0, cell1, cell2, cell3]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "00100000001")
        assert result.cedula == "00100000001"
        assert result.affiliation_status == "ACTIVO"
        assert result.employer == "EMPRESA DOMINICANA SA"
        assert result.ars == "ARS UNIVERSAL"
        assert result.afp == "AFP SIEMBRA"

    def test_parse_from_text_labels(self):
        source = TssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Estado: ACTIVO\nEmpleador: EMPRESA TEST\nARS: ARS PRIMERA\nAFP: AFP RESERVAS\n"
        )
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "00200000002")
        assert result.cedula == "00200000002"

    def test_parse_empty_page(self):
        source = TssSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "00300000003")
        assert result.cedula == "00300000003"
        assert result.affiliation_status == ""
