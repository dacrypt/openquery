"""Tests for br.anfavea — ANFAVEA vehicle production/sales statistics."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestAnfaveaResult — model tests
# ===========================================================================


class TestAnfaveaResult:
    def test_defaults(self):
        from openquery.models.br.anfavea import AnfaveaResult

        r = AnfaveaResult()
        assert r.period == ""
        assert r.total_production == 0
        assert r.total_licensing == 0
        assert r.total_exports == 0
        assert r.segments == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.anfavea import AnfaveaResult, AnfaveaSegment

        r = AnfaveaResult(
            period="2024-01",
            total_production=250000,
            total_licensing=180000,
            total_exports=40000,
            segments=[
                AnfaveaSegment(
                    segment="automobiles",
                    production=180000,
                    licensing=130000,
                    exports=30000,
                ),
                AnfaveaSegment(
                    segment="trucks",
                    production=70000,
                    licensing=50000,
                    exports=10000,
                ),
            ],
        )
        dumped = r.model_dump_json()
        restored = AnfaveaResult.model_validate_json(dumped)
        assert restored.period == "2024-01"
        assert restored.total_production == 250000
        assert len(restored.segments) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.br.anfavea import AnfaveaResult

        r = AnfaveaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_segment_defaults(self):
        from openquery.models.br.anfavea import AnfaveaSegment

        seg = AnfaveaSegment()
        assert seg.segment == ""
        assert seg.production == 0
        assert seg.licensing == 0
        assert seg.exports == 0


# ===========================================================================
# TestAnfaveaSourceMeta
# ===========================================================================


class TestAnfaveaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        meta = AnfaveaSource().meta()
        assert meta.name == "br.anfavea"

    def test_meta_country(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        meta = AnfaveaSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        meta = AnfaveaSource().meta()
        assert meta.requires_browser is True

    def test_meta_rate_limit(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        meta = AnfaveaSource().meta()
        assert meta.rate_limit_rpm == 5

    def test_meta_supports_custom(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        meta = AnfaveaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestAnfaveaParseResult
# ===========================================================================


try:
    import openpyxl as _openpyxl_check  # noqa: F401

    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False


def _make_xlsx_bytes() -> bytes:
    """Create a minimal xlsx file with ANFAVEA-like data."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Producao"
    # Header row
    ws.append(["Segmento", "Producao", "Emplacamentos", "Exportacoes"])
    # Data rows
    ws.append(["Automóveis", 180000, 130000, 30000])
    ws.append(["Veículos Comerciais Leves", 45000, 32000, 8000])
    ws.append(["Caminhões", 25000, 18000, 4000])
    ws.append(["Ônibus", 5000, 3500, 500])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestAnfaveaParseResult:
    def _make_input(self, year: str = "2024", month: str = "01") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"year": year, "month": month},
        )

    @pytest.mark.skipif(not _OPENPYXL_AVAILABLE, reason="openpyxl not installed")
    def test_parse_excel_segments(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        xlsx_bytes = _make_xlsx_bytes()
        source = AnfaveaSource()
        result = source._parse_excel(xlsx_bytes, "https://anfavea.com.br/2024.xlsx", "2024", "01")

        assert result.period == "2024-01"
        assert result.total_production > 0
        assert result.total_licensing > 0
        # Should have found at least automobiles
        segment_names = [s.segment for s in result.segments]
        assert "automobiles" in segment_names

    def test_extract_period_year_month(self):
        from openquery.sources.br.anfavea import _extract_period

        assert _extract_period("https://example.com/file.xlsx", "2024", "03") == "2024-03"

    def test_extract_period_year_only(self):
        from openquery.sources.br.anfavea import _extract_period

        assert _extract_period("https://example.com/file.xlsx", "2024", "") == "2024"

    def test_extract_period_from_url(self):
        from openquery.sources.br.anfavea import _extract_period

        assert _extract_period("https://anfavea.com.br/2023_data.xlsx", "", "") == "2023"

    def test_safe_int_handles_various(self):
        from openquery.sources.br.anfavea import _safe_int

        assert _safe_int(12345) == 12345
        assert _safe_int("12,345") == 12345
        assert _safe_int(None) == 0
        assert _safe_int("") == 0
        assert _safe_int("abc") == 0

    def test_no_links_raises_source_error(self):
        from openquery.sources.br.anfavea import AnfaveaSource

        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []
        mock_page.goto = MagicMock()

        mock_ctx = MagicMock()
        mock_ctx.new_page.return_value = mock_page
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_browser = MagicMock()
        mock_browser.sync_context.return_value = mock_ctx

        with patch("openquery.core.browser.BrowserManager") as mock_bm_cls:
            mock_bm_cls.return_value = mock_browser
            source = AnfaveaSource()
            with pytest.raises(SourceError, match="No Excel links"):
                source.query(self._make_input())
