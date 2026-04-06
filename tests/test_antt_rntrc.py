"""Tests for br.antt_rntrc — ANTT carrier registry (RNTRC).

Uses mocked Playwright via patching BrowserManager.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError  # noqa: F401
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestAnttRntrcResult — model tests
# ===========================================================================


class TestAnttRntrcResult:
    def test_defaults(self):
        from openquery.models.br.antt_rntrc import AnttRntrcResult

        r = AnttRntrcResult()
        assert r.search_type == ""
        assert r.search_value == ""
        assert r.rntrc_number == ""
        assert r.carrier_name == ""
        assert r.status == ""
        assert r.transport_type == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.antt_rntrc import AnttRntrcResult

        r = AnttRntrcResult(
            search_type="rntrc",
            search_value="12345",
            rntrc_number="12345",
            carrier_name="Transportes Exemplo Ltda",
            status="HABILITADO",
            transport_type="ETC",
            details={"RNTRC": "12345"},
        )
        dumped = r.model_dump_json()
        restored = AnttRntrcResult.model_validate_json(dumped)
        assert restored.rntrc_number == "12345"
        assert restored.carrier_name == "Transportes Exemplo Ltda"
        assert restored.status == "HABILITADO"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.antt_rntrc import AnttRntrcResult

        r = AnttRntrcResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.br.antt_rntrc import AnttRntrcResult

        r = AnttRntrcResult(details={"Tipo": "ETC", "Situação": "HABILITADO"})
        assert r.details["Tipo"] == "ETC"


# ===========================================================================
# TestAnttRntrcSourceMeta
# ===========================================================================


class TestAnttRntrcSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert meta.name == "br.antt_rntrc"

    def test_meta_country(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert meta.requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        meta = AnttRntrcSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestAnttRntrcQuery — input validation
# ===========================================================================


class TestAnttRntrcQuery:
    def test_wrong_document_type_raises(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        with pytest.raises(SourceError, match="CUSTOM"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))

    def test_missing_search_value_raises(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        with pytest.raises(SourceError, match="search_value is required"):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"search_type": "rntrc", "search_value": ""},
                )
            )

    def test_invalid_search_type_raises(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        with pytest.raises(SourceError, match="Invalid search_type"):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="12345",
                    extra={"search_type": "nit"},
                )
            )

    def test_document_number_used_as_search_value(self):
        """document_number falls back to search_value when extra is absent."""
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        # Patch _query to avoid real browser call
        called_with: dict = {}

        def fake_query(search_type: str, search_value: str, audit: bool = False):
            called_with["type"] = search_type
            called_with["value"] = search_value
            from openquery.models.br.antt_rntrc import AnttRntrcResult

            return AnttRntrcResult(search_type=search_type, search_value=search_value)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="12345",
                extra={},
            )
        )
        assert called_with["value"] == "12345"
        assert called_with["type"] == "rntrc"  # 5-digit numeric → rntrc

    def test_cnpj_auto_detected(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        called_with: dict = {}

        def fake_query(search_type: str, search_value: str, audit: bool = False):
            called_with["type"] = search_type
            from openquery.models.br.antt_rntrc import AnttRntrcResult

            return AnttRntrcResult(search_type=search_type, search_value=search_value)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="12345678000195",
                extra={},
            )
        )
        assert called_with["type"] == "cnpj"

    def test_cpf_auto_detected(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        called_with: dict = {}

        def fake_query(search_type: str, search_value: str, audit: bool = False):
            called_with["type"] = search_type
            from openquery.models.br.antt_rntrc import AnttRntrcResult

            return AnttRntrcResult(search_type=search_type, search_value=search_value)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="12345678901",
                extra={},
            )
        )
        assert called_with["type"] == "cpf"

    def test_plate_auto_detected(self):
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        called_with: dict = {}

        def fake_query(search_type: str, search_value: str, audit: bool = False):
            called_with["type"] = search_type
            from openquery.models.br.antt_rntrc import AnttRntrcResult

            return AnttRntrcResult(search_type=search_type, search_value=search_value)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="ABC1234",
                extra={},
            )
        )
        assert called_with["type"] == "plate"


# ===========================================================================
# TestAnttRntrcParseResult — parsing logic
# ===========================================================================


class TestAnttRntrcParseResult:
    def _make_page(self, body_text: str, table_rows: list[list[str]] | None = None) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text

        if table_rows is not None:
            mock_rows = []
            for row_values in table_rows:
                row = MagicMock()
                cells = []
                for val in row_values:
                    cell = MagicMock()
                    cell.inner_text.return_value = val
                    cells.append(cell)
                row.query_selector_all.return_value = cells
                mock_rows.append(row)
            page.query_selector_all.return_value = mock_rows
        else:
            page.query_selector_all.return_value = []

        return page

    def _parse(
        self,
        body_text: str,
        table_rows: list[list[str]] | None = None,
        search_type: str = "rntrc",
        search_value: str = "12345",
    ) -> object:
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource()
        page = self._make_page(body_text, table_rows)
        return src._parse_result(page, search_type, search_value)

    def test_table_parsing_rntrc(self):
        headers = ["RNTRC", "Nome / Razão Social", "Situação", "Tipo"]
        data = ["00012345", "Transportes ABC Ltda", "HABILITADO", "ETC"]
        result = self._parse("", table_rows=[headers, data])
        assert result.rntrc_number == "00012345"
        assert result.carrier_name == "Transportes ABC Ltda"
        assert result.status == "HABILITADO"
        assert result.transport_type == "ETC"

    def test_table_parsing_situacao_variant(self):
        headers = ["RNTRC", "Transportador", "Situação", "Modal"]
        data = ["99999", "Logistica XYZ", "CANCELADO", "Rodoviário"]
        result = self._parse("", table_rows=[headers, data])
        assert result.status == "CANCELADO"
        assert result.transport_type == "Rodoviário"

    def test_fallback_text_parsing(self):
        body = (
            "RNTRC: 00099999\nRazão Social: Empresa Teste Ltda\nSituação: HABILITADO\nTipo: ETC\n"
        )
        result = self._parse(body)
        assert result.rntrc_number == "00099999"
        assert result.carrier_name == "Empresa Teste Ltda"
        assert result.status == "HABILITADO"
        assert result.transport_type == "ETC"

    def test_empty_response(self):
        result = self._parse("Nenhum resultado encontrado")
        assert result.rntrc_number == ""
        assert result.carrier_name == ""
        assert result.status == ""

    def test_search_type_and_value_preserved(self):
        result = self._parse("", search_type="cnpj", search_value="12345678000195")
        assert result.search_type == "cnpj"
        assert result.search_value == "12345678000195"

    def test_details_populated_from_table(self):
        headers = ["RNTRC", "Nome / Razão Social", "Situação"]
        data = ["11111", "Empresa Y", "HABILITADO"]
        result = self._parse("", table_rows=[headers, data])
        assert "RNTRC" in result.details or "Nome / Razão Social" in result.details


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestAnttRntrcIntegration:
    def test_query_by_rntrc(self):
        """Query a known public RNTRC number. Requires real browser."""
        from openquery.sources.br.antt_rntrc import AnttRntrcSource

        src = AnttRntrcSource(headless=True)
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="1",
                extra={"search_type": "rntrc", "search_value": "1"},
            )
        )
        assert result.search_type == "rntrc"
        assert isinstance(result.rntrc_number, str)
