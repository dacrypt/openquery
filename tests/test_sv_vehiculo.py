"""Tests for sv.vehiculo — El Salvador SERTRACEN vehicle registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvVehiculoParseResult:
    def _parse(self, body_text: str, search_value: str = "P123456"):
        from openquery.sources.sv.vehiculo import SvVehiculoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvVehiculoSource()
        return src._parse_result(page, search_value)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.vehicle_status == ""
        assert result.registration_status == ""
        assert result.owner == ""
        assert result.liens == []

    def test_search_value_preserved(self):
        result = self._parse("", search_value="P123456")
        assert result.search_value == "P123456"

    def test_activo_status_detected(self):
        result = self._parse("Estado: Activo\nPropietario: JUAN RAMIREZ")
        assert result.vehicle_status == "Activo"

    def test_inactivo_status_detected(self):
        result = self._parse("El vehiculo se encuentra inactivo en el registro")
        assert result.vehicle_status == "Inactivo"

    def test_robado_status_detected(self):
        result = self._parse("Alerta: Vehículo reportado como robado")
        assert result.vehicle_status == "Robado"

    def test_owner_parsed(self):
        result = self._parse("Propietario: JUAN CARLOS RAMIREZ LOPEZ\nEstado: Activo")
        assert result.owner == "JUAN CARLOS RAMIREZ LOPEZ"

    def test_liens_captured(self):
        result = self._parse(
            "Estado: Activo\nGravamen: Prenda por Banco Agricola\nEmbargo judicial 2023"
        )
        assert len(result.liens) >= 1
        assert any("Gravamen" in lien or "Embargo" in lien for lien in result.liens)

    def test_no_liens_when_clean(self):
        result = self._parse("Propietario: ANA GARCIA\nEstado: Activo")
        assert result.liens == []

    def test_details_populated(self):
        result = self._parse("Propietario: PEDRO SILVA\nMatricula: 2024-P123456")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.sv.vehiculo import SvVehiculoResult

        r = SvVehiculoResult(
            search_value="P123456",
            vehicle_status="Activo",
            registration_status="Vigente",
            liens=["Prenda Banco Agricola"],
            owner="JUAN RAMIREZ",
        )
        data = r.model_dump_json()
        r2 = SvVehiculoResult.model_validate_json(data)
        assert r2.search_value == "P123456"
        assert r2.vehicle_status == "Activo"
        assert r2.liens == ["Prenda Banco Agricola"]
        assert r2.owner == "JUAN RAMIREZ"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.vehiculo import SvVehiculoResult

        r = SvVehiculoResult(search_value="P123456", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvVehiculoSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.vehiculo import SvVehiculoSource

        meta = SvVehiculoSource().meta()
        assert meta.name == "sv.vehiculo"
        assert meta.country == "SV"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_plate_raises(self):
        from openquery.sources.sv.vehiculo import SvVehiculoSource

        src = SvVehiculoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.sv.vehiculo import SvVehiculoSource

        src = SvVehiculoSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="00000000-0"))
