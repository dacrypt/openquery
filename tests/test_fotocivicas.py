"""Unit tests for mx.fotocivicas — CDMX photo enforcement fines."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openquery.models.mx.fotocivicas import FotocivicasResult, FotocivicaViolation
from openquery.sources.mx.fotocivicas import FotocivicasSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestFotocivicasResult:
    def test_default_values(self):
        r = FotocivicasResult()
        assert r.placa == ""
        assert r.total_violations == 0
        assert r.total_amount == ""
        assert r.violations == []
        assert r.details == ""
        assert r.audit is None

    def test_round_trip(self):
        r = FotocivicasResult(
            placa="ABC1234",
            total_violations=1,
            total_amount="$2,000.00",
            violations=[
                FotocivicaViolation(
                    folio="FC001",
                    fecha="2024-02-20",
                    tipo="Exceso de velocidad",
                    ubicacion="Periferico Sur km 10",
                    monto="$2,000.00",
                    estatus="Pendiente",
                )
            ],
        )
        restored = FotocivicasResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC1234"
        assert restored.total_violations == 1
        assert len(restored.violations) == 1
        assert restored.violations[0].folio == "FC001"
        assert restored.violations[0].tipo == "Exceso de velocidad"

    def test_audit_excluded(self):
        r = FotocivicasResult(placa="ABC1234")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = FotocivicasResult(placa="XYZ9999")
        r.audit = b"pdf_bytes"
        data = json.loads(r.model_dump_json())
        assert "audit" not in data


class TestFotocivicaViolation:
    def test_default_values(self):
        v = FotocivicaViolation()
        assert v.folio == ""
        assert v.fecha == ""
        assert v.tipo == ""
        assert v.ubicacion == ""
        assert v.monto == ""
        assert v.estatus == ""

    def test_populated(self):
        v = FotocivicaViolation(
            folio="FC999",
            tipo="Semaforo en rojo",
            monto="$3,000.00",
            estatus="Pagado",
        )
        assert v.folio == "FC999"
        assert v.tipo == "Semaforo en rojo"
        assert v.estatus == "Pagado"


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------


class TestFotocivicasSourceMeta:
    def test_meta(self):
        src = FotocivicasSource()
        meta = src.meta()
        assert meta.name == "mx.fotocivicas"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_display_name(self):
        src = FotocivicasSource()
        meta = src.meta()
        assert "Fotocivicas" in meta.display_name or "CDMX" in meta.display_name

    def test_url(self):
        src = FotocivicasSource()
        meta = src.meta()
        assert "tramites.cdmx.gob.mx" in meta.url

    def test_supported_inputs(self):
        from openquery.sources.base import DocumentType

        src = FotocivicasSource()
        meta = src.meta()
        assert DocumentType.PLATE in meta.supported_inputs


# ---------------------------------------------------------------------------
# Parse result tests
# ---------------------------------------------------------------------------


class TestFotocivicasParseResult:
    def test_parse_no_violations(self):
        page = MagicMock()
        page.inner_text.return_value = "Sin multas registradas para esta placa."
        page.query_selector_all.return_value = []

        src = FotocivicasSource()
        result = src._parse_result(page, "ABC1234")

        assert result.placa == "ABC1234"
        assert result.total_violations == 0
        assert result.violations == []

    def test_parse_not_found(self):
        page = MagicMock()
        page.inner_text.return_value = "No se encontraron infracciones para la placa."
        page.query_selector_all.return_value = []

        src = FotocivicasSource()
        result = src._parse_result(page, "XYZ9999")

        assert result.total_violations == 0

    def test_parse_violation_count(self):
        page = MagicMock()
        page.inner_text.return_value = "Se encontraron 2 infracciones fotocivicas."
        page.query_selector_all.return_value = []

        src = FotocivicasSource()
        result = src._parse_result(page, "CNT1234")

        assert result.total_violations == 2

    def test_parse_total_amount(self):
        page = MagicMock()
        page.inner_text.return_value = "Total: $5,000.00\n2 multas pendientes."
        page.query_selector_all.return_value = []

        src = FotocivicasSource()
        result = src._parse_result(page, "AMT1234")

        assert result.total_amount == "$5,000.00"

    def test_parse_table_rows(self):
        page = MagicMock()
        page.inner_text.return_value = "Fotocivicas encontradas."

        # Mock table rows with cells
        cell_texts = ["FC001", "2024-04-01", "Exceso de velocidad", "Periferico km 5", "$2,000.00", "Pendiente"]  # noqa: E501
        cells = [MagicMock() for _ in cell_texts]
        for cell, text in zip(cells, cell_texts):
            cell.inner_text.return_value = text

        row = MagicMock()
        row.query_selector_all.return_value = cells

        page.query_selector_all.return_value = [row]

        src = FotocivicasSource()
        result = src._parse_result(page, "ROW1234")

        assert len(result.violations) == 1
        assert result.violations[0].folio == "FC001"
        assert result.violations[0].tipo == "Exceso de velocidad"
        assert result.violations[0].ubicacion == "Periferico km 5"

    def test_violations_count_from_list(self):
        """total_violations inferred from violations list when not in body text."""
        page = MagicMock()
        page.inner_text.return_value = "Resultado de consulta."

        cell_texts = ["FC002", "2024-05-15", "Semaforo en rojo", "Eje Central", "$3,000.00", "Pendiente"]  # noqa: E501
        cells = [MagicMock() for _ in cell_texts]
        for cell, text in zip(cells, cell_texts):
            cell.inner_text.return_value = text

        row = MagicMock()
        row.query_selector_all.return_value = cells
        page.query_selector_all.return_value = [row]

        src = FotocivicasSource()
        result = src._parse_result(page, "INF9999")

        assert result.total_violations == 1
