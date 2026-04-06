"""Tests for br.detran_pr — Paraná DETRAN vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test DetranPrResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.detran_pr import DetranPrResult

        r = DetranPrResult()
        assert r.placa == ""
        assert r.vehicle_description == ""
        assert r.situation == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.detran_pr import DetranPrResult

        r = DetranPrResult(placa="ABC1D23", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "ABC1D23" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.detran_pr import DetranPrResult

        r = DetranPrResult(
            placa="ABC1D23",
            vehicle_description="HONDA CIVIC",
            situation="Regular",
            details={"Marca": "HONDA"},
        )
        r2 = DetranPrResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC1D23"
        assert r2.vehicle_description == "HONDA CIVIC"
        assert r2.situation == "Regular"
        assert r2.details["Marca"] == "HONDA"

    def test_queried_at_default(self):
        from openquery.models.br.detran_pr import DetranPrResult

        before = datetime.now()
        r = DetranPrResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test br.detran_pr source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        meta = DetranPrSource().meta()
        assert meta.name == "br.detran_pr"

    def test_meta_country(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        meta = DetranPrSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        meta = DetranPrSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        meta = DetranPrSource().meta()
        assert DocumentType.PLATE in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        meta = DetranPrSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page.inner_text."""

    def _make_source(self):
        from openquery.sources.br.detran_pr import DetranPrSource

        return DetranPrSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_placa_preserved(self):
        src = self._make_source()
        page = self._make_page("Nenhum resultado")
        result = src._parse_result(page, "ABC1D23")
        assert result.placa == "ABC1D23"

    def test_vehicle_description_parsed(self):
        src = self._make_source()
        page = self._make_page("Modelo: CIVIC\nAno: 2020")
        result = src._parse_result(page, "ABC1D23")
        assert result.vehicle_description == "CIVIC"

    def test_situation_parsed(self):
        src = self._make_source()
        page = self._make_page("Situação: Regular\nOutros dados")
        result = src._parse_result(page, "ABC1D23")
        assert result.situation == "Regular"

    def test_details_populated(self):
        src = self._make_source()
        page = self._make_page("Marca: HONDA\nModelo: CIVIC")
        result = src._parse_result(page, "ABC1D23")
        assert "Marca" in result.details
        assert result.details["Marca"] == "HONDA"

    def test_empty_body(self):
        src = self._make_source()
        page = self._make_page("")
        result = src._parse_result(page, "ABC1D23")
        assert result.placa == "ABC1D23"
        assert result.situation == ""

    def test_query_missing_plate_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.detran_pr import DetranPrSource

        src = DetranPrSource()
        with pytest.raises(SourceError, match="placa"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_normalizes_plate(self):
        from unittest.mock import patch

        from openquery.models.br.detran_pr import DetranPrResult
        from openquery.sources.br.detran_pr import DetranPrSource

        src = DetranPrSource()
        mock_result = DetranPrResult(placa="ABC1D23")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="abc-1d23"))
            m.assert_called_once_with("ABC1D23", audit=False)
