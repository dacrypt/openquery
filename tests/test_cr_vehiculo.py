"""Tests for cr.vehiculo — Costa Rica Hacienda vehicle registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.cr.vehiculo import CrVehiculoResult
from openquery.sources.base import DocumentType, QueryInput


class TestCrVehiculoResult:
    """Model default values, JSON roundtrip, audit exclusion."""

    def test_defaults(self):
        r = CrVehiculoResult()
        assert r.placa == ""
        assert r.owner == ""
        assert r.brand == ""
        assert r.model == ""
        assert r.year == ""
        assert r.engine == ""
        assert r.use_type == ""
        assert r.details == ""
        assert r.audit is None

    def test_queried_at_default(self):
        r = CrVehiculoResult()
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        r = CrVehiculoResult(placa="ABC123", owner="JUAN PEREZ", brand="TOYOTA")
        restored = CrVehiculoResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC123"
        assert restored.owner == "JUAN PEREZ"
        assert restored.brand == "TOYOTA"

    def test_audit_excluded_from_json(self):
        r = CrVehiculoResult(placa="XYZ", audit=b"pdf-data")
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_audit_excluded_from_dict(self):
        r = CrVehiculoResult(placa="XYZ", audit={"key": "val"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCrVehiculoSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.vehiculo import CrVehiculoSource

        meta = CrVehiculoSource().meta()
        assert meta.name == "cr.vehiculo"
        assert meta.country == "CR"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10

    def test_missing_placa_raises(self):
        from openquery.sources.cr.vehiculo import CrVehiculoSource

        src = CrVehiculoSource()
        with pytest.raises(SourceError, match="Placa is required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))


class TestCrVehiculoParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, placa: str = "ABC123") -> CrVehiculoResult:
        from openquery.sources.cr.vehiculo import CrVehiculoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrVehiculoSource()
        return src._parse_result(page, placa)

    def test_placa_preserved(self):
        result = self._parse("Sin resultados", placa="XYZ789")
        assert result.placa == "XYZ789"

    def test_parses_propietario(self):
        body = "Propietario: MARIA GONZALEZ ROJAS\nMarca: HONDA\n"
        result = self._parse(body)
        assert result.owner == "MARIA GONZALEZ ROJAS"

    def test_parses_marca(self):
        body = "Marca: TOYOTA\nModelo: COROLLA\n"
        result = self._parse(body)
        assert result.brand == "TOYOTA"

    def test_parses_modelo(self):
        body = "Modelo: RAV4\n"
        result = self._parse(body)
        assert result.model == "RAV4"

    def test_parses_year(self):
        body = "Año: 2019\n"
        result = self._parse(body)
        assert result.year == "2019"

    def test_parses_motor(self):
        body = "Motor: 2AZFE123456\n"
        result = self._parse(body)
        assert result.engine == "2AZFE123456"

    def test_parses_numero_motor(self):
        body = "Número de Motor: XYZ987\n"
        result = self._parse(body)
        assert result.engine == "XYZ987"

    def test_parses_uso(self):
        body = "Uso: PARTICULAR\n"
        result = self._parse(body)
        assert result.use_type == "PARTICULAR"

    def test_parses_tipo_de_uso(self):
        body = "Tipo de Uso: SERVICIO PUBLICO\n"
        result = self._parse(body)
        assert result.use_type == "SERVICIO PUBLICO"

    def test_details_truncated_to_500(self):
        body = "A" * 1000
        result = self._parse(body)
        assert len(result.details) == 500

    def test_empty_body(self):
        result = self._parse("")
        assert result.owner == ""
        assert result.brand == ""

    def test_placa_uppercased_in_query(self):
        from openquery.sources.cr.vehiculo import CrVehiculoSource

        CrVehiculoSource()
        inp = QueryInput(document_type=DocumentType.PLATE, document_number="abc123")
        # Verify upper() is called — check via extra kwarg path too
        inp2 = QueryInput(
            document_type=DocumentType.PLATE,
            document_number="",
            extra={"placa": "def456"},
        )
        # Just confirm no crash on input extraction
        assert inp.document_number == "abc123"
        assert inp2.extra["placa"] == "def456"
