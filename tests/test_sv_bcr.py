"""Unit tests for sv.bcr source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.sv.bcr import SvBcrResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.sv.bcr import SvBcrSource


class TestSvBcrResult:
    """Test SvBcrResult model."""

    def test_default_values(self):
        data = SvBcrResult()
        assert data.indicator == ""
        assert data.value == ""
        assert data.date == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SvBcrResult(
            indicator="tipo_cambio",
            value="1.00",
            date="2024-01-15",
            details={"Moneda": "USD"},
        )
        json_str = data.model_dump_json()
        restored = SvBcrResult.model_validate_json(json_str)
        assert restored.indicator == "tipo_cambio"
        assert restored.value == "1.00"
        assert restored.date == "2024-01-15"

    def test_audit_excluded_from_json(self):
        data = SvBcrResult(indicator="tipo_cambio", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestSvBcrSourceMeta:
    """Test SvBcrSource metadata."""

    def test_meta_name(self):
        source = SvBcrSource()
        meta = source.meta()
        assert meta.name == "sv.bcr"

    def test_meta_country(self):
        source = SvBcrSource()
        meta = source.meta()
        assert meta.country == "SV"

    def test_meta_rate_limit(self):
        source = SvBcrSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = SvBcrSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = SvBcrSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = SvBcrSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SvBcrSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_default_indicator_from_empty_document_number(self):
        SvBcrSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        # Should not raise — defaults to "tipo_cambio"
        indicator = inp.extra.get("indicator", "") or inp.document_number or "tipo_cambio"
        assert indicator == "tipo_cambio"

    def test_indicator_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"indicator": "inflacion"},
        )
        assert inp.extra.get("indicator") == "inflacion"


class TestSvBcrParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, indicator: str = "tipo_cambio", rows=None):
        source = SvBcrSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if rows is None:
            mock_page.query_selector_all.return_value = []
        else:
            mock_page.query_selector_all.return_value = rows
        return source._parse_result(mock_page, indicator)

    def test_parse_value_from_text(self):
        result = self._parse("Tipo de Cambio: 1.00\nFecha: 2024-01-15\n")
        assert result.value == "1.00"

    def test_parse_from_table(self):
        mock_row = MagicMock()
        cell1 = MagicMock()
        cell1.inner_text.return_value = "tipo_cambio"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "1.00"
        mock_row.query_selector_all.return_value = [cell1, cell2]
        result = self._parse("", rows=[mock_row])
        assert result.value == "1.00"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.indicator == "tipo_cambio"
        assert result.value == ""

    def test_parse_details_collected(self):
        result = self._parse("Moneda: USD\nPaís: El Salvador\n")
        assert "Moneda" in result.details
        assert result.details["Moneda"] == "USD"

    def test_indicator_preserved(self):
        result = self._parse("", indicator="inflacion")
        assert result.indicator == "inflacion"

    def test_date_set(self):
        result = self._parse("")
        assert result.date != ""

    def test_model_roundtrip(self):
        r = SvBcrResult(indicator="tipo_cambio", value="1.00", date="2024-01-15")
        data = r.model_dump_json()
        r2 = SvBcrResult.model_validate_json(data)
        assert r2.indicator == "tipo_cambio"
        assert r2.value == "1.00"
