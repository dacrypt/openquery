"""Tests for do.dgii_ncf — Dominican Republic DGII NCF invoice verification source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestDoDgiiNcfParseResult:
    def _parse(self, body_text: str, rnc: str = "130862346", ncf: str = "B0100000001"):
        from openquery.sources.do.dgii_ncf import DoDgiiNcfSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = DoDgiiNcfSource()
        return src._parse_result(page, rnc, ncf)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.ncf_valid is False

    def test_rnc_and_ncf_preserved(self):
        result = self._parse("", rnc="130862346", ncf="B0100000001")
        assert result.rnc == "130862346"
        assert result.ncf == "B0100000001"

    def test_valid_ncf_detected(self):
        result = self._parse("Comprobante Válido\nEstado: Activo")
        assert result.ncf_valid is True

    def test_invalid_ncf_detected(self):
        result = self._parse("Comprobante Inválido\nEstado: Anulado")
        assert result.ncf_valid is False

    def test_autorizado_detected_as_valid(self):
        result = self._parse("NCF Autorizado y Vigente")
        assert result.ncf_valid is True

    def test_details_populated(self):
        result = self._parse("Válido\nFecha: 2024-01-01")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.do.dgii_ncf import DoDgiiNcfResult

        r = DoDgiiNcfResult(
            rnc="130862346",
            ncf="B0100000001",
            ncf_valid=True,
        )
        data = r.model_dump_json()
        r2 = DoDgiiNcfResult.model_validate_json(data)
        assert r2.rnc == "130862346"
        assert r2.ncf == "B0100000001"
        assert r2.ncf_valid is True

    def test_audit_excluded_from_json(self):
        from openquery.models.do.dgii_ncf import DoDgiiNcfResult

        r = DoDgiiNcfResult(rnc="130862346", ncf="B0100000001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestDoDgiiNcfSourceMeta:
    def test_meta(self):
        from openquery.sources.do.dgii_ncf import DoDgiiNcfSource

        meta = DoDgiiNcfSource().meta()
        assert meta.name == "do.dgii_ncf"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_missing_rnc_raises(self):
        from openquery.sources.do.dgii_ncf import DoDgiiNcfSource

        src = DoDgiiNcfSource()
        with pytest.raises(SourceError, match="RNC"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_missing_ncf_raises(self):
        from openquery.sources.do.dgii_ncf import DoDgiiNcfSource

        src = DoDgiiNcfSource()
        with pytest.raises(SourceError, match="NCF"):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="130862346",
                    extra={"rnc": "130862346"},
                )
            )
