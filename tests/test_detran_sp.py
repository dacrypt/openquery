"""Tests for br.detran_sp — São Paulo DETRAN vehicle debt lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestDetranSpResult:
    """Test DetranSpResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.detran_sp import DetranSpResult

        r = DetranSpResult()
        assert r.placa == ""
        assert r.renavam == ""
        assert r.vehicle_description == ""
        assert r.ipva_status == ""
        assert r.licensing_status == ""
        assert r.fines_count == 0
        assert r.total_debt == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.detran_sp import DetranSpResult

        r = DetranSpResult(placa="ABC1234", audit={"screenshot": "base64data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "ABC1234" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.detran_sp import DetranSpResult

        r = DetranSpResult(
            placa="ABC1234",
            renavam="12345678901",
            vehicle_description="HONDA CIVIC",
            ipva_status="Pago",
            licensing_status="Licenciado",
            fines_count=2,
            total_debt="R$ 500,00",
            details={"Marca": "HONDA", "Modelo": "CIVIC"},
        )
        r2 = DetranSpResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC1234"
        assert r2.fines_count == 2
        assert r2.details["Marca"] == "HONDA"

    def test_queried_at_default(self):
        from openquery.models.br.detran_sp import DetranSpResult

        before = datetime.now()
        r = DetranSpResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestDetranSpSourceMeta:
    """Test br.detran_sp source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.detran_sp import DetranSpSource

        meta = DetranSpSource().meta()
        assert meta.name == "br.detran_sp"

    def test_meta_country(self):
        from openquery.sources.br.detran_sp import DetranSpSource

        meta = DetranSpSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.detran_sp import DetranSpSource

        meta = DetranSpSource().meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.br.detran_sp import DetranSpSource

        meta = DetranSpSource().meta()
        assert DocumentType.PLATE in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.detran_sp import DetranSpSource

        meta = DetranSpSource().meta()
        assert meta.rate_limit_rpm == 10


class TestDetranSpParseResult:
    """Test _parse_result with mocked page.inner_text."""

    def _parse(self, body_text: str, placa: str = "ABC1234", renavam: str = ""):
        from openquery.sources.br.detran_sp import DetranSpSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = DetranSpSource()
        return src._parse_result(page, placa, renavam)

    def test_placa_preserved(self):
        result = self._parse("Nenhum débito encontrado", placa="ABC1234")
        assert result.placa == "ABC1234"

    def test_renavam_preserved(self):
        result = self._parse("Nenhum débito encontrado", renavam="12345678901")
        assert result.renavam == "12345678901"

    def test_ipva_status_parsed(self):
        result = self._parse("IPVA: Pago\nOutros dados")
        assert result.ipva_status == "Pago"

    def test_licensing_status_parsed(self):
        result = self._parse("Licenciamento: Em dia\nOutros dados")
        assert result.licensing_status == "Em dia"

    def test_total_debt_parsed(self):
        result = self._parse("Total: R$ 1.200,00\nDetalhes")
        assert result.total_debt == "R$ 1.200,00"

    def test_empty_body(self):
        result = self._parse("")
        assert result.placa == "ABC1234"
        assert result.ipva_status == ""
        assert result.fines_count == 0

    def test_vehicle_description_from_modelo(self):
        result = self._parse("Modelo: CIVIC\nAno: 2020")
        assert result.vehicle_description == "CIVIC"

    def test_query_missing_plate_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.detran_sp import DetranSpSource

        src = DetranSpSource()
        with pytest.raises(SourceError, match="placa"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))
