"""Tests for gt.sat_vehiculo — Guatemala SAT vehicle circulation tax source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtSatVehiculoParseResult:
    def _parse(self, body_text: str, placa: str = "P123ABC", nit: str = "12345678"):
        from openquery.sources.gt.sat_vehiculo import GtSatVehiculoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = GtSatVehiculoSource()
        return src._parse_result(page, placa, nit)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.tax_amount == ""
        assert result.payment_status == ""
        assert result.vehicle_description == ""

    def test_placa_preserved(self):
        result = self._parse("", placa="P123ABC")
        assert result.placa == "P123ABC"

    def test_nit_preserved(self):
        result = self._parse("", nit="12345678")
        assert result.nit == "12345678"

    def test_pagado_status_detected(self):
        result = self._parse("Estado: Pagado\nMonto: Q350.00")
        assert result.payment_status == "Pagado"

    def test_al_dia_status_detected(self):
        result = self._parse("El vehículo se encuentra al día en sus pagos")
        assert result.payment_status == "Pagado"

    def test_pendiente_status_detected(self):
        result = self._parse("Estado de pago: Pendiente de cancelación")
        assert result.payment_status == "Pendiente"

    def test_vencido_status_detected(self):
        result = self._parse("Su calcomania se encuentra vencida")
        assert result.payment_status == "Vencido"

    def test_tax_amount_parsed(self):
        result = self._parse("Monto: Q350.00\nEstado: Pagado")
        assert result.tax_amount == "Q350.00"

    def test_vehicle_description_parsed(self):
        result = self._parse("Descripcion: TOYOTA HILUX 2020\nMonto: Q350.00")
        assert result.vehicle_description == "TOYOTA HILUX 2020"

    def test_marca_maps_to_vehicle_description(self):
        result = self._parse("Marca: TOYOTA\nModelo: HILUX")
        assert result.vehicle_description == "TOYOTA"

    def test_details_populated(self):
        result = self._parse("Placa: P123ABC\nModelo: HILUX")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.gt.sat_vehiculo import GtSatVehiculoResult

        r = GtSatVehiculoResult(
            placa="P123ABC",
            nit="12345678",
            tax_amount="Q350.00",
            payment_status="Pagado",
            vehicle_description="TOYOTA HILUX 2020",
        )
        data = r.model_dump_json()
        r2 = GtSatVehiculoResult.model_validate_json(data)
        assert r2.placa == "P123ABC"
        assert r2.tax_amount == "Q350.00"
        assert r2.payment_status == "Pagado"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.sat_vehiculo import GtSatVehiculoResult

        r = GtSatVehiculoResult(placa="P123ABC", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtSatVehiculoSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.sat_vehiculo import GtSatVehiculoSource

        meta = GtSatVehiculoSource().meta()
        assert meta.name == "gt.sat_vehiculo"
        assert meta.country == "GT"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_plate_raises(self):
        from openquery.sources.gt.sat_vehiculo import GtSatVehiculoSource

        src = GtSatVehiculoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(
                QueryInput(
                    document_type=DocumentType.PLATE,
                    document_number="",
                    extra={"nit": "12345678"},
                )
            )

    def test_missing_nit_raises(self):
        from openquery.sources.gt.sat_vehiculo import GtSatVehiculoSource

        src = GtSatVehiculoSource()
        with pytest.raises(SourceError, match="NIT"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="P123ABC"))

    def test_wrong_document_type_raises(self):
        from openquery.sources.gt.sat_vehiculo import GtSatVehiculoSource

        src = GtSatVehiculoSource()
        with pytest.raises(SourceError):
            src.query(
                QueryInput(
                    document_type=DocumentType.CEDULA,
                    document_number="1234567890101",
                    extra={"nit": "12345678"},
                )
            )
