"""Tests for bo.tsj_procesos — Bolivia TSJ court case search source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestTsjProcesosParseResult:
    def _parse(self, body_text: str, rows=None, search_value: str = "2024-001"):
        from openquery.sources.bo.tsj_procesos import TsjProcesosSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = TsjProcesosSource()
        return src._parse_result(page, search_value)

    def test_empty_body_returns_empty_processes(self):
        result = self._parse("")
        assert result.processes == []
        assert result.total == 0

    def test_search_value_preserved(self):
        result = self._parse("", search_value="CASO-9999")
        assert result.search_value == "CASO-9999"

    def test_text_parse_case_number(self):
        body = "Número: 2024-001\nJuzgado: Juzgado 1ro Civil\nEstado: En trámite"
        result = self._parse(body)
        assert len(result.processes) == 1
        assert result.processes[0].case_number == "2024-001"
        assert result.processes[0].court == "Juzgado 1ro Civil"
        assert result.processes[0].status == "En trámite"

    def test_text_parse_multiple_cases(self):
        body = "Número: CASO-001\nJuzgado: Juzgado A\nNúmero: CASO-002\nJuzgado: Juzgado B\n"
        result = self._parse(body)
        assert len(result.processes) == 2
        assert result.total == 2

    def test_expediente_keyword(self):
        body = "Expediente: EXP-2024-555\nEstado: Concluido"
        result = self._parse(body)
        assert len(result.processes) == 1
        assert result.processes[0].case_number == "EXP-2024-555"

    def test_tribunal_keyword(self):
        body = "Número: EXP-001\nTribunal: Tribunal Supremo\nEstado: Activo"
        result = self._parse(body)
        assert result.processes[0].court == "Tribunal Supremo"

    def test_table_rows_parsed(self):
        def make_cell(text):
            cell = MagicMock()
            cell.inner_text.return_value = text
            return cell

        def make_row(texts):
            row = MagicMock()
            row.query_selector_all.return_value = [make_cell(t) for t in texts]
            return row

        header = make_row(["Expediente", "Juzgado", "Estado", "Partes", "Fecha"])
        data_row = make_row(["EXP-001", "Juzgado 2do", "Activo", "García vs. López", "2024-03-01"])

        result = self._parse("", rows=[header, data_row])
        assert len(result.processes) == 1
        assert result.processes[0].case_number == "EXP-001"
        assert result.processes[0].court == "Juzgado 2do"
        assert result.processes[0].parties == "García vs. López"

    def test_model_roundtrip(self):
        from openquery.models.bo.tsj_procesos import TsjProcesosResult, TsjProcess

        r = TsjProcesosResult(
            search_value="CASO-001",
            total=1,
            processes=[TsjProcess(case_number="CASO-001", court="Juzgado 1ro", status="Activo")],
        )
        data = r.model_dump_json()
        r2 = TsjProcesosResult.model_validate_json(data)
        assert r2.search_value == "CASO-001"
        assert r2.total == 1
        assert r2.processes[0].case_number == "CASO-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.tsj_procesos import TsjProcesosResult

        r = TsjProcesosResult(search_value="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestTsjProcesosSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.tsj_procesos import TsjProcesosSource

        meta = TsjProcesosSource().meta()
        assert meta.name == "bo.tsj_procesos"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True

    def test_empty_input_raises(self):
        from openquery.sources.bo.tsj_procesos import TsjProcesosSource

        src = TsjProcesosSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_case_number_extra_accepted(self):

        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"case_number": "EXP-2024-001"},
        )
        assert input_.extra["case_number"] == "EXP-2024-001"
