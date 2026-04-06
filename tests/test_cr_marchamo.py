"""Tests for cr.marchamo — Costa Rica INS marchamo insurance/tax lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.cr.marchamo import CrMarchamoResult
from openquery.sources.base import DocumentType, QueryInput


class TestCrMarchamoResult:
    """Model default values, JSON roundtrip, audit exclusion."""

    def test_defaults(self):
        r = CrMarchamoResult()
        assert r.placa == ""
        assert r.marchamo_amount == ""
        assert r.marchamo_expiry == ""
        assert r.insurance_status == ""
        assert r.vehicle_description == ""
        assert r.details == ""
        assert r.audit is None

    def test_queried_at_default(self):
        r = CrMarchamoResult()
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        r = CrMarchamoResult(
            placa="ABC123",
            marchamo_amount="45000",
            insurance_status="AL DIA",
        )
        restored = CrMarchamoResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC123"
        assert restored.marchamo_amount == "45000"
        assert restored.insurance_status == "AL DIA"

    def test_audit_excluded_from_json(self):
        r = CrMarchamoResult(placa="XYZ", audit=b"pdf-data")
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_audit_excluded_from_dict(self):
        r = CrMarchamoResult(placa="XYZ", audit={"key": "val"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCrMarchamoSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.marchamo import CrMarchamoSource

        meta = CrMarchamoSource().meta()
        assert meta.name == "cr.marchamo"
        assert meta.country == "CR"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10

    def test_missing_placa_raises(self):
        from openquery.sources.cr.marchamo import CrMarchamoSource

        src = CrMarchamoSource()
        with pytest.raises(SourceError, match="Placa is required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))


class TestCrMarchamoParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, placa: str = "ABC123") -> CrMarchamoResult:
        from openquery.sources.cr.marchamo import CrMarchamoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrMarchamoSource()
        return src._parse_result(page, placa)

    def test_placa_preserved(self):
        result = self._parse("Sin resultados", placa="XYZ789")
        assert result.placa == "XYZ789"

    def test_parses_monto(self):
        body = "Monto: 45,000\nVencimiento: 31/12/2025\n"
        result = self._parse(body)
        assert result.marchamo_amount == "45,000"

    def test_parses_total_a_pagar(self):
        body = "Total a Pagar: 67,500\n"
        result = self._parse(body)
        assert result.marchamo_amount == "67,500"

    def test_parses_vencimiento(self):
        body = "Vencimiento: 31/12/2025\n"
        result = self._parse(body)
        assert result.marchamo_expiry == "31/12/2025"

    def test_parses_fecha_vencimiento(self):
        body = "Fecha de Vencimiento: 2025-12-31\n"
        result = self._parse(body)
        assert result.marchamo_expiry == "2025-12-31"

    def test_parses_seguro(self):
        body = "Seguro: AL DIA\n"
        result = self._parse(body)
        assert result.insurance_status == "AL DIA"

    def test_parses_soa(self):
        body = "SOA: VIGENTE\n"
        result = self._parse(body)
        assert result.insurance_status == "VIGENTE"

    def test_parses_estado_del_seguro(self):
        body = "Estado del Seguro: VENCIDO\n"
        result = self._parse(body)
        assert result.insurance_status == "VENCIDO"

    def test_parses_descripcion(self):
        body = "Descripción: TOYOTA COROLLA 2019\n"
        result = self._parse(body)
        assert result.vehicle_description == "TOYOTA COROLLA 2019"

    def test_parses_vehiculo(self):
        body = "Vehículo: HONDA CIVIC 2020\n"
        result = self._parse(body)
        assert result.vehicle_description == "HONDA CIVIC 2020"

    def test_details_truncated_to_500(self):
        body = "B" * 1000
        result = self._parse(body)
        assert len(result.details) == 500

    def test_empty_body(self):
        result = self._parse("")
        assert result.marchamo_amount == ""
        assert result.insurance_status == ""

    def test_multiple_fields_parsed(self):
        body = (
            "Monto: 52,000\n"
            "Vencimiento: 31/12/2025\n"
            "Seguro: AL DIA\n"
            "Descripción: SUZUKI SWIFT 2018\n"
        )
        result = self._parse(body)
        assert result.marchamo_amount == "52,000"
        assert result.marchamo_expiry == "31/12/2025"
        assert result.insurance_status == "AL DIA"
        assert result.vehicle_description == "SUZUKI SWIFT 2018"
