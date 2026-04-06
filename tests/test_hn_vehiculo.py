"""Tests for hn.vehiculo — Honduras vehicle registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnVehiculoParseResult:
    def _parse(self, body_text: str, placa: str = "ABC1234"):
        from openquery.sources.hn.vehiculo import HnVehiculoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnVehiculoSource()
        return src._parse_result(page, placa)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.matricula_fee == ""
        assert result.registration_status == ""
        assert result.vehicle_description == ""

    def test_placa_preserved(self):
        result = self._parse("", placa="ABC1234")
        assert result.placa == "ABC1234"

    def test_al_dia_status_detected(self):
        result = self._parse("Estado: Al día\nMatricula: L. 500.00")
        assert result.registration_status == "Al día"

    def test_moroso_status_detected(self):
        result = self._parse("El vehiculo tiene deuda pendiente")
        assert result.registration_status == "Moroso"

    def test_matricula_fee_parsed(self):
        result = self._parse("Matricula: L. 750.00\nModelo: Toyota Corolla 2018")
        assert result.matricula_fee == "L. 750.00"

    def test_vehicle_description_parsed(self):
        result = self._parse("Descripcion: Toyota Corolla 2018 Gris")
        assert result.vehicle_description == "Toyota Corolla 2018 Gris"

    def test_details_populated(self):
        result = self._parse("Matricula: L. 500.00\nEstado: Al dia")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.hn.vehiculo import HnVehiculoResult

        r = HnVehiculoResult(
            placa="ABC1234",
            matricula_fee="L. 500.00",
            registration_status="Al día",
            vehicle_description="Toyota Corolla 2018",
        )
        data = r.model_dump_json()
        r2 = HnVehiculoResult.model_validate_json(data)
        assert r2.placa == "ABC1234"
        assert r2.matricula_fee == "L. 500.00"
        assert r2.registration_status == "Al día"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.vehiculo import HnVehiculoResult

        r = HnVehiculoResult(placa="ABC1234", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnVehiculoSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.vehiculo import HnVehiculoSource

        meta = HnVehiculoSource().meta()
        assert meta.name == "hn.vehiculo"
        assert meta.country == "HN"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_placa_raises(self):
        from openquery.sources.hn.vehiculo import HnVehiculoSource

        src = HnVehiculoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.hn.vehiculo import HnVehiculoSource

        src = HnVehiculoSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="12345"))
