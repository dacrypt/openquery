"""Tests for gt.renap — Guatemala RENAP DPI identity status source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtRenapParseResult:
    def _parse(self, body_text: str, dpi: str = "1234567890101"):
        from openquery.sources.gt.renap import GtRenapSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = GtRenapSource()
        return src._parse_result(page, dpi)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.status == ""

    def test_dpi_preserved(self):
        result = self._parse("", dpi="1234567890101")
        assert result.dpi == "1234567890101"

    def test_entregado_status_detected(self):
        result = self._parse("Su DPI ha sido entregado en la sede")
        assert result.status == "Entregado"

    def test_listo_status_detected(self):
        result = self._parse("Su documento está listo para retirar")
        assert result.status == "Entregado"

    def test_en_proceso_status_detected(self):
        result = self._parse("Su trámite se encuentra en proceso de fabricación")
        assert result.status == "En Proceso"

    def test_pendiente_status_detected(self):
        result = self._parse("Estado: Pendiente de validación")
        assert result.status == "Pendiente"

    def test_rechazado_status_detected(self):
        result = self._parse("Su trámite fue rechazado por documentación incompleta")
        assert result.status == "Rechazado"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: JUAN CARLOS LOPEZ GARCIA\nEstado: Entregado")
        assert result.nombre == "JUAN CARLOS LOPEZ GARCIA"

    def test_estado_parsed(self):
        result = self._parse("Nombre: ANA PEREZ\nEstado: Activo")
        assert result.status == "Activo"

    def test_details_populated(self):
        result = self._parse("Nombre: ANA PEREZ\nFecha: 2024-01-15")
        assert isinstance(result.details, dict)
        assert result.details.get("Fecha") == "2024-01-15"

    def test_model_roundtrip(self):
        from openquery.models.gt.renap import GtRenapResult

        r = GtRenapResult(
            dpi="1234567890101",
            nombre="JUAN CARLOS LOPEZ",
            status="Entregado",
        )
        data = r.model_dump_json()
        r2 = GtRenapResult.model_validate_json(data)
        assert r2.dpi == "1234567890101"
        assert r2.nombre == "JUAN CARLOS LOPEZ"
        assert r2.status == "Entregado"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.renap import GtRenapResult

        r = GtRenapResult(dpi="1234567890101", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtRenapSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.renap import GtRenapSource

        meta = GtRenapSource().meta()
        assert meta.name == "gt.renap"
        assert meta.country == "GT"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dpi_raises(self):
        from openquery.sources.gt.renap import GtRenapSource

        src = GtRenapSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.gt.renap import GtRenapSource

        src = GtRenapSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
