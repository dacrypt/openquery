"""Tests for cl.sii_boleta — SII boleta/invoice verification."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestSiiBoletaResult:
    """Test SiiBoletaResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.cl.sii_boleta import SiiBoletaResult

        r = SiiBoletaResult()
        assert r.rut == ""
        assert r.folio == ""
        assert r.boleta_valid is False
        assert r.amount == ""
        assert r.date == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.cl.sii_boleta import SiiBoletaResult

        r = SiiBoletaResult(rut="12345678-9", folio="1234", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "12345678-9" in dumped

    def test_json_roundtrip(self):
        from openquery.models.cl.sii_boleta import SiiBoletaResult

        r = SiiBoletaResult(
            rut="12345678-9",
            folio="9876",
            boleta_valid=True,
            amount="$15.000",
            date="2024-01-15",
            details={"Tipo": "Boleta"},
        )
        r2 = SiiBoletaResult.model_validate_json(r.model_dump_json())
        assert r2.rut == "12345678-9"
        assert r2.boleta_valid is True
        assert r2.amount == "$15.000"

    def test_queried_at_default(self):
        from openquery.models.cl.sii_boleta import SiiBoletaResult

        before = datetime.now()
        r = SiiBoletaResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSiiBoletaSourceMeta:
    """Test cl.sii_boleta source metadata."""

    def test_meta_name(self):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        assert SiiBoletaSource().meta().name == "cl.sii_boleta"

    def test_meta_country(self):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        assert SiiBoletaSource().meta().country == "CL"

    def test_meta_requires_browser(self):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        assert SiiBoletaSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        assert DocumentType.CUSTOM in SiiBoletaSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        assert SiiBoletaSource().meta().rate_limit_rpm == 10


class TestSiiBoletaParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, rut: str = "12345678-9", folio: str = "1234"):
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return SiiBoletaSource()._parse_result(page, rut, folio)

    def test_rut_preserved(self):
        assert self._parse("Datos").rut == "12345678-9"

    def test_folio_preserved(self):
        assert self._parse("Datos").folio == "1234"

    def test_boleta_valid_true(self):
        result = self._parse("Boleta válida y vigente")
        assert result.boleta_valid is True

    def test_boleta_valid_false(self):
        result = self._parse("Boleta no válida para este folio")
        assert result.boleta_valid is False

    def test_amount_parsed(self):
        result = self._parse("Monto: $15.000\nFecha: 2024-01-15")
        assert result.amount == "$15.000"

    def test_date_parsed(self):
        result = self._parse("Fecha: 2024-01-15\nOtros")
        assert result.date == "2024-01-15"

    def test_empty_body(self):
        result = self._parse("")
        assert result.rut == "12345678-9"
        assert result.boleta_valid is False

    def test_query_missing_rut_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        with pytest.raises(SourceError, match="RUT"):
            SiiBoletaSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )

    def test_query_missing_folio_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.cl.sii_boleta import SiiBoletaSource

        with pytest.raises(SourceError, match="[Ff]olio"):
            SiiBoletaSource().query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"rut": "12345678-9"},
                )
            )
