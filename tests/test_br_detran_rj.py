"""Tests for br.detran_rj — Rio de Janeiro DETRAN vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestDetranRjResult:
    """Test DetranRjResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.detran_rj import DetranRjResult

        r = DetranRjResult()
        assert r.placa == ""
        assert r.renavam == ""
        assert r.vehicle_description == ""
        assert r.situation == ""
        assert r.total_debt == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.detran_rj import DetranRjResult

        r = DetranRjResult(placa="ABC1234", audit={"screenshot": "base64data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "ABC1234" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.detran_rj import DetranRjResult

        r = DetranRjResult(
            placa="XYZ5678",
            renavam="12345678901",
            vehicle_description="FIAT PALIO",
            situation="Regular",
            total_debt="R$ 0,00",
            details={"Marca": "FIAT"},
        )
        r2 = DetranRjResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "XYZ5678"
        assert r2.situation == "Regular"
        assert r2.details["Marca"] == "FIAT"

    def test_queried_at_default(self):
        from openquery.models.br.detran_rj import DetranRjResult

        before = datetime.now()
        r = DetranRjResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestDetranRjSourceMeta:
    """Test br.detran_rj source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.detran_rj import DetranRjSource

        assert DetranRjSource().meta().name == "br.detran_rj"

    def test_meta_country(self):
        from openquery.sources.br.detran_rj import DetranRjSource

        assert DetranRjSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.detran_rj import DetranRjSource

        assert DetranRjSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.br.detran_rj import DetranRjSource

        assert DocumentType.PLATE in DetranRjSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.detran_rj import DetranRjSource

        assert DetranRjSource().meta().rate_limit_rpm == 10


class TestDetranRjParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, placa: str = "ABC1234", renavam: str = ""):
        from openquery.sources.br.detran_rj import DetranRjSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return DetranRjSource()._parse_result(page, placa, renavam)

    def test_placa_preserved(self):
        assert self._parse("Veículo regular", placa="ABC1234").placa == "ABC1234"

    def test_renavam_preserved(self):
        assert self._parse("Dados", renavam="12345678901").renavam == "12345678901"

    def test_situation_parsed(self):
        result = self._parse("Situação: Regular\nOutros dados")
        assert result.situation == "Regular"

    def test_vehicle_description_from_modelo(self):
        result = self._parse("Modelo: PALIO\nAno: 2019")
        assert result.vehicle_description == "PALIO"

    def test_total_debt_parsed(self):
        result = self._parse("Total débito: R$ 500,00")
        assert result.total_debt == "R$ 500,00"

    def test_empty_body(self):
        result = self._parse("")
        assert result.placa == "ABC1234"
        assert result.situation == ""

    def test_query_missing_plate_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.detran_rj import DetranRjSource

        with pytest.raises(SourceError, match="placa"):
            DetranRjSource().query(QueryInput(document_type=DocumentType.PLATE, document_number=""))
