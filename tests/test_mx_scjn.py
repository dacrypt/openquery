"""Unit tests for mx.scjn — SCJN/PJF federal judicial cases."""

from __future__ import annotations

import json

from openquery.models.mx.scjn import MxCaseRecord, ScjnResult
from openquery.sources.mx.scjn import ScjnSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestScjnResult:
    def test_default_values(self):
        r = ScjnResult()
        assert r.search_term == ""
        assert r.total == 0
        assert r.cases == []

    def test_round_trip(self):
        r = ScjnResult(
            search_term="123/2023",
            total=2,
            cases=[
                MxCaseRecord(
                    case_number="123/2023",
                    court="Primer Juzgado de Distrito",
                    case_type="Amparo",
                    status="En trámite",
                    parties="JUAN PEREZ vs GOBIERNO",
                    date="2023-05-10",
                )
            ],
        )
        restored = ScjnResult.model_validate_json(r.model_dump_json())
        assert restored.search_term == "123/2023"
        assert restored.total == 2
        assert len(restored.cases) == 1
        assert restored.cases[0].case_number == "123/2023"
        assert restored.cases[0].court == "Primer Juzgado de Distrito"

    def test_audit_excluded(self):
        r = ScjnResult(search_term="123/2023")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = ScjnResult(search_term="456/2022")
        r.audit = b"pdf_bytes"
        data = json.loads(r.model_dump_json())
        assert "audit" not in data


class TestMxCaseRecord:
    def test_default_values(self):
        rec = MxCaseRecord()
        assert rec.case_number == ""
        assert rec.court == ""
        assert rec.case_type == ""
        assert rec.status == ""
        assert rec.parties == ""
        assert rec.date == ""

    def test_populated(self):
        rec = MxCaseRecord(
            case_number="789/2021",
            court="Tribunal Colegiado",
            status="Concluido",
        )
        assert rec.case_number == "789/2021"
        assert rec.status == "Concluido"


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------

class TestScjnSourceMeta:
    def test_meta(self):
        src = ScjnSource()
        meta = src.meta()
        assert meta.name == "mx.scjn"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_display_name(self):
        src = ScjnSource()
        meta = src.meta()
        assert "SCJN" in meta.display_name or "PJF" in meta.display_name

    def test_url(self):
        src = ScjnSource()
        meta = src.meta()
        assert "pjf.gob.mx" in meta.url


# ---------------------------------------------------------------------------
# Parse result tests
# ---------------------------------------------------------------------------

class TestScjnParseResult:
    def test_parse_no_results(self):
        """Returns empty cases list when no case numbers found in body."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = "No se encontraron resultados para su búsqueda."
        page.query_selector_all.return_value = []

        src = ScjnSource()
        result = src._parse_result(page, "999/9999")

        assert result.search_term == "999/9999"
        assert result.cases == []
        assert result.total == 0

    def test_parse_single_case(self):
        """Source should extract a case number from body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "Expediente: 123/2023\n"
            "Juzgado: Primer Juzgado de Distrito en Materia Civil\n"
            "Estado: En trámite\n"
            "Fecha: 2023-05-10\n"
        )
        page.query_selector_all.return_value = []

        src = ScjnSource()
        result = src._parse_result(page, "123/2023")

        assert result.search_term == "123/2023"
        assert len(result.cases) == 1
        assert result.cases[0].case_number == "123/2023"

    def test_parse_case_row_fields(self):
        """_parse_case_row extracts court and status from structured text."""
        src = ScjnSource()
        row_text = (
            "456/2022 | Tribunal Colegiado del Primer Circuito | Amparo Directo | "
            "Estado: Concluido | Fecha: 15/03/2022"
        )
        record = src._parse_case_row(row_text)

        assert record.case_number == "456/2022"
        assert record.status == "Concluido"

    def test_parse_total_count(self):
        """Source should extract explicit result count from body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "5 expedientes encontrados\n"
            "123/2023 | Juzgado Primero | Amparo | En trámite\n"
        )
        page.query_selector_all.return_value = []

        src = ScjnSource()
        result = src._parse_result(page, "test")

        assert result.total == 5

    def test_parse_multiple_cases(self):
        """Source should find multiple case numbers in body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "Resultados:\n"
            "Expediente: 100/2023 | Juzgado Segundo | En trámite\n"
            "Expediente: 200/2022 | Tribunal Tercero | Concluido\n"
        )
        page.query_selector_all.return_value = []

        src = ScjnSource()
        result = src._parse_result(page, "JUAN PEREZ")

        assert len(result.cases) == 2
        case_numbers = {c.case_number for c in result.cases}
        assert "100/2023" in case_numbers
        assert "200/2022" in case_numbers
