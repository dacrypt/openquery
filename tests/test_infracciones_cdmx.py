"""Unit tests for mx.infracciones_cdmx — CDMX traffic infractions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openquery.models.mx.infracciones_cdmx import InfraccionesCdmxResult, InfraccionRecord
from openquery.sources.mx.infracciones_cdmx import InfraccionesCdmxSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestInfraccionesCdmxResult:
    def test_default_values(self):
        r = InfraccionesCdmxResult()
        assert r.placa == ""
        assert r.total_infractions == 0
        assert r.total_amount == ""
        assert r.infractions == []
        assert r.details == ""
        assert r.audit is None

    def test_round_trip(self):
        r = InfraccionesCdmxResult(
            placa="ABC1234",
            total_infractions=2,
            total_amount="$3,000.00",
            infractions=[
                InfraccionRecord(
                    folio="INF001",
                    fecha="2024-01-15",
                    descripcion="Exceso de velocidad",
                    monto="$1,500.00",
                    estatus="Pendiente",
                )
            ],
        )
        restored = InfraccionesCdmxResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC1234"
        assert restored.total_infractions == 2
        assert restored.total_amount == "$3,000.00"
        assert len(restored.infractions) == 1
        assert restored.infractions[0].folio == "INF001"

    def test_audit_excluded(self):
        r = InfraccionesCdmxResult(placa="ABC1234")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = InfraccionesCdmxResult(placa="XYZ9999")
        r.audit = b"pdf_bytes"
        data = json.loads(r.model_dump_json())
        assert "audit" not in data


class TestInfraccionRecord:
    def test_default_values(self):
        rec = InfraccionRecord()
        assert rec.folio == ""
        assert rec.fecha == ""
        assert rec.descripcion == ""
        assert rec.monto == ""
        assert rec.estatus == ""

    def test_populated(self):
        rec = InfraccionRecord(
            folio="INF999",
            fecha="2024-06-01",
            descripcion="Semaforo en rojo",
            monto="$2,000.00",
            estatus="Pagado",
        )
        assert rec.folio == "INF999"
        assert rec.estatus == "Pagado"


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------


class TestInfraccionesCdmxSourceMeta:
    def test_meta(self):
        src = InfraccionesCdmxSource()
        meta = src.meta()
        assert meta.name == "mx.infracciones_cdmx"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_display_name(self):
        src = InfraccionesCdmxSource()
        meta = src.meta()
        assert "Infracciones" in meta.display_name or "CDMX" in meta.display_name

    def test_url(self):
        src = InfraccionesCdmxSource()
        meta = src.meta()
        assert "infracciones.cdmx.gob.mx" in meta.url

    def test_supported_inputs(self):
        from openquery.sources.base import DocumentType

        src = InfraccionesCdmxSource()
        meta = src.meta()
        assert DocumentType.PLATE in meta.supported_inputs


# ---------------------------------------------------------------------------
# Parse result tests
# ---------------------------------------------------------------------------


class TestInfraccionesCdmxParseResult:
    def test_parse_no_infractions(self):
        page = MagicMock()
        page.inner_text.return_value = "Sin infracciones registradas para esta placa."
        page.query_selector_all.return_value = []

        src = InfraccionesCdmxSource()
        result = src._parse_result(page, "ABC1234")

        assert result.placa == "ABC1234"
        assert result.total_infractions == 0
        assert result.infractions == []

    def test_parse_not_found(self):
        page = MagicMock()
        page.inner_text.return_value = "No se encontraron resultados para la placa XYZ9999."
        page.query_selector_all.return_value = []

        src = InfraccionesCdmxSource()
        result = src._parse_result(page, "XYZ9999")

        assert result.total_infractions == 0

    def test_parse_infraction_count(self):
        page = MagicMock()
        page.inner_text.return_value = "Se encontraron 3 infracciones para su vehículo."
        page.query_selector_all.return_value = []

        src = InfraccionesCdmxSource()
        result = src._parse_result(page, "TEST123")

        assert result.total_infractions == 3

    def test_parse_total_amount(self):
        page = MagicMock()
        page.inner_text.return_value = "Total: $4,500.00\n2 infracciones pendientes."
        page.query_selector_all.return_value = []

        src = InfraccionesCdmxSource()
        result = src._parse_result(page, "AMT1234")

        assert result.total_amount == "$4,500.00"

    def test_parse_table_rows(self):
        page = MagicMock()
        page.inner_text.return_value = "Infracciones encontradas."

        # Mock table rows with cells
        cell_texts = ["INF001", "2024-03-10", "Exceso de velocidad", "$1,500.00", "Pendiente"]
        cells = [MagicMock() for _ in cell_texts]
        for cell, text in zip(cells, cell_texts):
            cell.inner_text.return_value = text

        row = MagicMock()
        row.query_selector_all.return_value = cells

        page.query_selector_all.return_value = [row]

        src = InfraccionesCdmxSource()
        result = src._parse_result(page, "ROW1234")

        assert len(result.infractions) == 1
        assert result.infractions[0].folio == "INF001"
        assert result.infractions[0].descripcion == "Exceso de velocidad"
