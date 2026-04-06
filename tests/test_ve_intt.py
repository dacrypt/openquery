"""Tests for ve.intt — Venezuela vehicle registration / plate lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestInttResult — model tests
# ===========================================================================


class TestInttResult:
    def test_defaults(self):
        from openquery.models.ve.intt import InttResult

        r = InttResult()
        assert r.placa == ""
        assert r.vehicle_description == ""
        assert r.registration_status == ""
        assert r.owner == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.intt import InttResult

        r = InttResult(
            placa="ABC123",
            vehicle_description="Toyota Corolla 2020",
            registration_status="ACTIVO",
            owner="JUAN PEREZ",
        )
        dumped = r.model_dump_json()
        restored = InttResult.model_validate_json(dumped)
        assert restored.placa == "ABC123"
        assert restored.vehicle_description == "Toyota Corolla 2020"
        assert restored.registration_status == "ACTIVO"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.intt import InttResult

        r = InttResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.intt import InttResult

        r = InttResult(details={"Marca": "Toyota", "Modelo": "Corolla"})
        assert r.details["Marca"] == "Toyota"


# ===========================================================================
# TestInttSourceMeta
# ===========================================================================


class TestInttSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.intt import InttSource

        assert InttSource().meta().name == "ve.intt"

    def test_meta_country(self):
        from openquery.sources.ve.intt import InttSource

        assert InttSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.intt import InttSource

        assert InttSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.ve.intt import InttSource

        assert InttSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.intt import InttSource

        assert DocumentType.PLATE in InttSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.intt import InttSource

        assert InttSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestInttQuery — input validation
# ===========================================================================


class TestInttQuery:
    def test_wrong_document_type_raises(self):
        from openquery.sources.ve.intt import InttSource

        src = InttSource()
        with pytest.raises(SourceError, match="plate"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))

    def test_empty_plate_raises(self):
        from openquery.sources.ve.intt import InttSource

        src = InttSource()
        with pytest.raises(SourceError, match="placa is required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_valid_plate_calls_query(self):
        from openquery.models.ve.intt import InttResult
        from openquery.sources.ve.intt import InttSource

        src = InttSource()
        src._query = MagicMock(return_value=InttResult(placa="ABC123"))
        result = src.query(QueryInput(document_type=DocumentType.PLATE, document_number="abc123"))
        src._query.assert_called_once_with("ABC123", audit=False)
        assert result.placa == "ABC123"

    def test_plate_uppercased(self):
        from openquery.models.ve.intt import InttResult
        from openquery.sources.ve.intt import InttSource

        src = InttSource()
        src._query = MagicMock(return_value=InttResult(placa="XYZ456"))
        src.query(QueryInput(document_type=DocumentType.PLATE, document_number="xyz456"))
        src._query.assert_called_once_with("XYZ456", audit=False)


# ===========================================================================
# TestInttParseResult — parsing logic
# ===========================================================================


class TestInttParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        return page

    def _parse(self, body_text: str, placa: str = "ABC123") -> object:
        from openquery.sources.ve.intt import InttSource

        return InttSource()._parse_result(self._make_page(body_text), placa)

    def test_vehicle_description_extracted(self):
        body = "Marca: Toyota\nModelo: Corolla\n"
        result = self._parse(body)
        assert result.vehicle_description == "Toyota"

    def test_registration_status_extracted(self):
        body = "Estado: ACTIVO\n"
        result = self._parse(body)
        assert result.registration_status == "ACTIVO"

    def test_owner_extracted(self):
        body = "Propietario: JUAN PEREZ\n"
        result = self._parse(body)
        assert result.owner == "JUAN PEREZ"

    def test_placa_preserved(self):
        result = self._parse("", placa="XYZ789")
        assert result.placa == "XYZ789"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.vehicle_description == ""
        assert result.registration_status == ""
        assert result.owner == ""

    def test_details_populated(self):
        body = "Marca: Toyota\nEstado: ACTIVO\n"
        result = self._parse(body)
        assert isinstance(result.details, dict)
        assert len(result.details) > 0

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestInttIntegration:
    def test_query_by_plate(self):
        from openquery.sources.ve.intt import InttSource

        src = InttSource(headless=True)
        result = src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
        assert isinstance(result.placa, str)
        assert isinstance(result.vehicle_description, str)
