"""Tests for pa.attt_placa — Panama traffic/plate lookup."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestResult
# ===========================================================================


class TestResult:
    def test_default_values(self):
        from openquery.models.pa.attt_placa import AtttPlacaResult

        r = AtttPlacaResult()
        assert r.search_value == ""
        assert r.plate == ""
        assert r.fines_count == 0
        assert r.total_fines == ""
        assert r.plate_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.attt_placa import AtttPlacaResult

        r = AtttPlacaResult(search_value="ABC-123", plate="ABC-123")
        r.audit = {"evidence": "data"}
        data = r.model_dump_json()
        assert "audit" not in data

    def test_model_roundtrip(self):
        from openquery.models.pa.attt_placa import AtttPlacaResult

        r = AtttPlacaResult(
            search_value="ABC-123",
            plate="ABC-123",
            fines_count=2,
            total_fines="150.00",
            plate_status="Al Dia",
        )
        r2 = AtttPlacaResult.model_validate_json(r.model_dump_json())
        assert r2.search_value == "ABC-123"
        assert r2.plate == "ABC-123"
        assert r2.fines_count == 2
        assert r2.total_fines == "150.00"
        assert r2.plate_status == "Al Dia"


# ===========================================================================
# TestSourceMeta
# ===========================================================================


class TestSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert meta.name == "pa.attt_placa"

    def test_meta_country(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supports_plate(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert DocumentType.PLATE in meta.supported_inputs

    def test_meta_supports_cedula(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        meta = AtttPlacaSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestParseResult
# ===========================================================================


class TestParseResult:
    def _make_source(self):
        from openquery.sources.pa.attt_placa import AtttPlacaSource

        return AtttPlacaSource()

    def _make_page(self, text: str):
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = text
        page.query_selector_all.return_value = []
        return page

    def test_parse_not_found(self):
        src = self._make_source()
        page = self._make_page("No se encontraron resultados")
        result = src._parse_result(page, "ZZZ-999")
        assert result.search_value == "ZZZ-999"
        assert result.fines_count == 0
        assert result.plate_status == ""

    def test_parse_plate_data(self):
        src = self._make_source()
        text = "Placa: ABC-123\nEstado: Al Dia\nTotal: 150.00\nCantidad: 2\n"
        page = self._make_page(text)
        result = src._parse_result(page, "ABC-123")
        assert result.plate == "ABC-123"
        assert result.plate_status == "Al Dia"
        assert result.total_fines == "150.00"
        assert result.fines_count == 2

    def test_parse_uses_search_value_as_plate_fallback(self):
        src = self._make_source()
        page = self._make_page("Estado: Vigente\n")
        result = src._parse_result(page, "XYZ-456")
        assert result.plate == "XYZ-456"

    def test_query_missing_value_raises(self):
        src = self._make_source()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        src = self._make_source()
        from openquery.models.pa.attt_placa import AtttPlacaResult

        mock_result = AtttPlacaResult(search_value="ABC-123", plate="ABC-123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC-123"))
            m.assert_called_once_with("ABC-123", audit=False)

    def test_query_uses_extra_plate(self):
        from unittest.mock import patch

        src = self._make_source()
        from openquery.models.pa.attt_placa import AtttPlacaResult

        mock_result = AtttPlacaResult(search_value="ABC-123", plate="ABC-123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"plate": "ABC-123"},
                )
            )
            m.assert_called_once_with("ABC-123", audit=False)
