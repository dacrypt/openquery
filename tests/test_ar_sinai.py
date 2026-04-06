"""Unit tests for Argentina SINAI traffic infractions source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.sinai import SinaiInfraction, SinaiResult
from openquery.sources.ar.sinai import SinaiSource


class TestSinaiResult:
    """Test SinaiResult model."""

    def test_default_values(self):
        data = SinaiResult()
        assert data.placa == ""
        assert data.total_infractions == 0
        assert data.infractions == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SinaiResult(
            placa="ABC123",
            total_infractions=2,
            infractions=[
                SinaiInfraction(
                    date="01/01/2024",
                    description="Exceso de velocidad",
                    amount="$5000",
                    status="PENDIENTE",
                ),
                SinaiInfraction(
                    date="15/03/2024",
                    description="Semáforo en rojo",
                    amount="$8000",
                    status="PAGADA",
                ),
            ],
        )
        json_str = data.model_dump_json()
        restored = SinaiResult.model_validate_json(json_str)
        assert restored.placa == "ABC123"
        assert restored.total_infractions == 2
        assert len(restored.infractions) == 2
        assert restored.infractions[0].description == "Exceso de velocidad"
        assert restored.infractions[1].status == "PAGADA"

    def test_audit_excluded_from_json(self):
        data = SinaiResult(placa="ABC123", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_sinai_infraction_default_values(self):
        infraction = SinaiInfraction()
        assert infraction.date == ""
        assert infraction.description == ""
        assert infraction.amount == ""
        assert infraction.status == ""


class TestSinaiSourceMeta:
    """Test SinaiSource metadata."""

    def test_meta_name(self):
        source = SinaiSource()
        assert source.meta().name == "ar.sinai"

    def test_meta_country(self):
        source = SinaiSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = SinaiSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SinaiSource()
        assert source.meta().requires_captcha is True

    def test_meta_rate_limit(self):
        source = SinaiSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SinaiSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SinaiSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SinaiSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_query_wrong_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = SinaiSource()
        with __import__("pytest").raises(SourceError, match="Unsupported document type"):
            source.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))


class TestParseResult:
    """Test _parse_result parsing logic."""

    def test_parse_no_infractions(self):
        source = SinaiSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron infracciones para el dominio ABC123"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.placa == "ABC123"
        assert result.total_infractions == 0
        assert result.infractions == []

    def test_parse_with_infractions(self):
        source = SinaiSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Infracciones encontradas"

        # Mock table rows with cells
        mock_cell_date = MagicMock()
        mock_cell_date.inner_text.return_value = "01/01/2024"
        mock_cell_desc = MagicMock()
        mock_cell_desc.inner_text.return_value = "Exceso de velocidad"
        mock_cell_amount = MagicMock()
        mock_cell_amount.inner_text.return_value = "$5000"
        mock_cell_status = MagicMock()
        mock_cell_status.inner_text.return_value = "PENDIENTE"

        mock_row = MagicMock()
        mock_row.query_selector_all.return_value = [
            mock_cell_date,
            mock_cell_desc,
            mock_cell_amount,
            mock_cell_status,
        ]

        mock_page.query_selector_all.return_value = [mock_row]

        result = source._parse_result(mock_page, "ABC123")
        assert result.placa == "ABC123"
        assert result.total_infractions == 1
        assert len(result.infractions) == 1
        assert result.infractions[0].date == "01/01/2024"
        assert result.infractions[0].description == "Exceso de velocidad"
        assert result.infractions[0].amount == "$5000"
        assert result.infractions[0].status == "PENDIENTE"

    def test_parse_plate_uppercased(self):
        source = SinaiSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "abc123")
        assert result.placa == "ABC123"
