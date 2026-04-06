"""Tests for bo.sicoes — Bolivia SICOES government contracts source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSicoesParseResult:
    def _parse(self, body_text: str, rows=None, search_term: str = "YPFB"):
        from openquery.sources.bo.sicoes import SicoesSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = SicoesSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_contracts(self):
        result = self._parse("")
        assert result.contracts == []
        assert result.total == 0

    def test_search_term_preserved(self):
        result = self._parse("", search_term="YPFB Corporación")
        assert result.search_term == "YPFB Corporación"

    def test_text_parse_code_and_entity(self):
        body = "Código: CONT-2024-001\nEntidad: Ministerio de Salud\nEstado: Vigente"
        result = self._parse(body)
        assert len(result.contracts) == 1
        assert result.contracts[0].code == "CONT-2024-001"
        assert result.contracts[0].entity == "Ministerio de Salud"
        assert result.contracts[0].status == "Vigente"

    def test_text_parse_multiple_contracts(self):
        body = (
            "Código: CONT-001\nEntidad: Entidad A\n"
            "Código: CONT-002\nEntidad: Entidad B\n"
        )
        result = self._parse(body)
        assert len(result.contracts) == 2
        assert result.total == 2

    def test_table_rows_parsed(self):
        def make_cell(text):
            cell = MagicMock()
            cell.inner_text.return_value = text
            return cell

        def make_row(texts):
            row = MagicMock()
            row.query_selector_all.return_value = [make_cell(t) for t in texts]
            return row

        header = make_row(["Código", "Entidad", "Descripción", "Monto", "Estado", "Fecha"])
        data_row = make_row(["CONT-001", "Min. Educación", "Construcción", "100000", "Adjudicado", "2024-01-15"])

        result = self._parse("", rows=[header, data_row])
        assert len(result.contracts) == 1
        assert result.contracts[0].code == "CONT-001"
        assert result.contracts[0].entity == "Min. Educación"
        assert result.contracts[0].amount == "100000"
        assert result.contracts[0].date == "2024-01-15"

    def test_model_roundtrip(self):
        from openquery.models.bo.sicoes import SicoesResult, SicoesContract

        r = SicoesResult(
            search_term="YPFB",
            total=1,
            contracts=[SicoesContract(code="C-001", entity="YPFB", status="Vigente")],
        )
        data = r.model_dump_json()
        r2 = SicoesResult.model_validate_json(data)
        assert r2.search_term == "YPFB"
        assert r2.total == 1
        assert r2.contracts[0].code == "C-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.sicoes import SicoesResult

        r = SicoesResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSicoesSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.sicoes import SicoesSource

        meta = SicoesSource().meta()
        assert meta.name == "bo.sicoes"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True

    def test_empty_search_raises(self):
        from openquery.sources.bo.sicoes import SicoesSource

        src = SicoesSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_entity_name_extra(self):
        from openquery.sources.bo.sicoes import SicoesSource

        src = SicoesSource()
        # Verify extra key is accepted (query would proceed, not raise)
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"entity_name": "Ministerio"},
        )
        # Should not raise on validation — only raises if empty after extraction
        assert input_.extra["entity_name"] == "Ministerio"
