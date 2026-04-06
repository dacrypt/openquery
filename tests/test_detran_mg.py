"""Tests for br.detran_mg — Minas Gerais DETRAN vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestDetranMgResult:
    """Test DetranMgResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.detran_mg import DetranMgResult

        r = DetranMgResult()
        assert r.placa == ""
        assert r.renavam == ""
        assert r.vehicle_description == ""
        assert r.situation == ""
        assert r.ipva_status == ""
        assert r.total_debt == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.detran_mg import DetranMgResult

        r = DetranMgResult(placa="XYZ5678", audit={"screenshot": "base64data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "XYZ5678" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.detran_mg import DetranMgResult

        r = DetranMgResult(
            placa="XYZ5678",
            renavam="98765432100",
            vehicle_description="FIAT UNO",
            situation="Regular",
            ipva_status="Quitado",
            total_debt="R$ 0,00",
            details={"Marca": "FIAT", "Modelo": "UNO"},
        )
        r2 = DetranMgResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "XYZ5678"
        assert r2.situation == "Regular"
        assert r2.details["Modelo"] == "UNO"

    def test_queried_at_default(self):
        from openquery.models.br.detran_mg import DetranMgResult

        before = datetime.now()
        r = DetranMgResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestDetranMgSourceMeta:
    """Test br.detran_mg source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.detran_mg import DetranMgSource

        meta = DetranMgSource().meta()
        assert meta.name == "br.detran_mg"

    def test_meta_country(self):
        from openquery.sources.br.detran_mg import DetranMgSource

        meta = DetranMgSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.detran_mg import DetranMgSource

        meta = DetranMgSource().meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.br.detran_mg import DetranMgSource

        meta = DetranMgSource().meta()
        assert DocumentType.PLATE in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.detran_mg import DetranMgSource

        meta = DetranMgSource().meta()
        assert meta.rate_limit_rpm == 10


class TestDetranMgParseResult:
    """Test _parse_result with mocked page.inner_text."""

    def _parse(self, body_text: str, placa: str = "XYZ5678", renavam: str = ""):
        from openquery.sources.br.detran_mg import DetranMgSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = DetranMgSource()
        return src._parse_result(page, placa, renavam)

    def test_placa_preserved(self):
        result = self._parse("Veículo regular", placa="XYZ5678")
        assert result.placa == "XYZ5678"

    def test_renavam_preserved(self):
        result = self._parse("Veículo regular", renavam="98765432100")
        assert result.renavam == "98765432100"

    def test_situation_parsed(self):
        result = self._parse("Situação: Regular\nOutros dados")
        assert result.situation == "Regular"

    def test_ipva_status_parsed(self):
        result = self._parse("IPVA: Quitado\nOutros dados")
        assert result.ipva_status == "Quitado"

    def test_total_debt_parsed(self):
        result = self._parse("Total: R$ 0,00\nDetalhes")
        assert result.total_debt == "R$ 0,00"

    def test_empty_body(self):
        result = self._parse("")
        assert result.placa == "XYZ5678"
        assert result.situation == ""
        assert result.ipva_status == ""

    def test_vehicle_description_from_modelo(self):
        result = self._parse("Modelo: UNO\nAno: 2018")
        assert result.vehicle_description == "UNO"

    def test_query_missing_plate_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.detran_mg import DetranMgSource

        src = DetranMgSource()
        with pytest.raises(SourceError, match="placa"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))
