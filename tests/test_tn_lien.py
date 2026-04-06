"""Unit tests for Tennessee MVTL lien search source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.tn_lien import TnLienRecord, TnLienResult
from openquery.sources.us.tn_lien import TnLienSource


class TestTnLienResult:
    """Test TnLienResult model."""

    def test_default_values(self):
        data = TnLienResult()
        assert data.search_value == ""
        assert data.search_type == ""
        assert data.total_liens == 0
        assert data.liens == []
        assert data.audit is None

    def test_round_trip_json(self):
        record = TnLienRecord(
            document_number="TN-2024-001",
            debtor_name="JOHN DOE",
            lienholder="FIRST BANK",
            filing_date="2024-01-15",
            status="ACTIVE",
        )
        data = TnLienResult(
            search_value="1HGCM82633A004352",
            search_type="vin",
            total_liens=1,
            liens=[record],
        )
        json_str = data.model_dump_json()
        restored = TnLienResult.model_validate_json(json_str)
        assert restored.search_value == "1HGCM82633A004352"
        assert restored.search_type == "vin"
        assert restored.total_liens == 1
        assert len(restored.liens) == 1
        assert restored.liens[0].debtor_name == "JOHN DOE"

    def test_audit_excluded_from_json(self):
        data = TnLienResult(search_value="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_lien_record_defaults(self):
        record = TnLienRecord()
        assert record.document_number == ""
        assert record.debtor_name == ""
        assert record.lienholder == ""
        assert record.filing_date == ""
        assert record.status == ""


class TestTnLienSourceMeta:
    """Test TnLienSource metadata."""

    def test_meta_name(self):
        source = TnLienSource()
        meta = source.meta()
        assert meta.name == "us.tn_lien"

    def test_meta_country(self):
        source = TnLienSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = TnLienSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = TnLienSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = TnLienSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = TnLienSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = TnLienSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = TnLienSource(timeout=60.0)
        assert source._timeout == 60.0


class TestTnLienQueryValidation:
    """Test query() input validation without a browser."""

    def test_unsupported_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = TnLienSource()
        inp = QueryInput(document_type=DocumentType.CEDULA, document_number="123")
        try:
            source.query(inp)
            assert False, "Expected SourceError"
        except SourceError as e:
            assert "us.tn_lien" in str(e)

    def test_empty_vin_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = TnLienSource()
        inp = QueryInput(document_type=DocumentType.VIN, document_number="   ")
        try:
            source.query(inp)
            assert False, "Expected SourceError"
        except SourceError as e:
            assert "us.tn_lien" in str(e)

    def test_invalid_custom_search_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = TnLienSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="TEST",
            extra={"search_type": "invalid"},
        )
        try:
            source.query(inp)
            assert False, "Expected SourceError"
        except SourceError as e:
            assert "us.tn_lien" in str(e)


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, rows: list[list[str]] | None = None) -> MagicMock:
        mock_page = MagicMock()
        if rows:
            mock_rows = []
            for row_data in rows:
                mock_row = MagicMock()
                mock_cells = []
                for cell_text in row_data:
                    mock_cell = MagicMock()
                    mock_cell.inner_text.return_value = cell_text
                    mock_cells.append(mock_cell)
                mock_row.query_selector_all.return_value = mock_cells
                mock_rows.append(mock_row)
            mock_page.query_selector_all.return_value = mock_rows
        else:
            mock_page.query_selector_all.return_value = []
        return mock_page

    def test_parse_no_results(self):
        source = TnLienSource()
        page = self._make_page(rows=[])
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.total_liens == 0
        assert result.liens == []
        assert result.search_value == "1HGCM82633A004352"
        assert result.search_type == "vin"

    def test_parse_single_lien(self):
        source = TnLienSource()
        page = self._make_page(
            rows=[
                ["TN-2024-001", "JOHN DOE", "FIRST BANK", "2024-01-15", "ACTIVE"],
            ]
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.total_liens == 1
        assert result.liens[0].document_number == "TN-2024-001"
        assert result.liens[0].debtor_name == "JOHN DOE"
        assert result.liens[0].lienholder == "FIRST BANK"
        assert result.liens[0].filing_date == "2024-01-15"
        assert result.liens[0].status == "ACTIVE"

    def test_parse_multiple_liens(self):
        source = TnLienSource()
        page = self._make_page(
            rows=[
                ["TN-2024-001", "JOHN DOE", "FIRST BANK", "2024-01-15", "ACTIVE"],
                ["TN-2024-002", "JANE SMITH", "CREDIT UNION", "2024-02-20", "ACTIVE"],
            ]
        )
        result = source._parse_results(page, "SMITH", "debtor")
        assert result.total_liens == 2
        assert result.search_type == "debtor"

    def test_parse_partial_row(self):
        source = TnLienSource()
        page = self._make_page(
            rows=[
                ["TN-2024-001", "JOHN DOE"],
            ]
        )
        result = source._parse_results(page, "TN-2024-001", "document")
        assert result.total_liens == 1
        assert result.liens[0].document_number == "TN-2024-001"
        assert result.liens[0].debtor_name == "JOHN DOE"
        assert result.liens[0].lienholder == ""
