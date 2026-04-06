"""Tests for hn.sar — Honduras SAR tax registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnSarParseResult:
    def _parse(self, body_text: str, rtn: str = "08011234567890"):
        from openquery.sources.hn.sar import HnSarSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnSarSource()
        return src._parse_result(page, rtn)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.taxpayer_name == ""
        assert result.address == ""
        assert result.registration_date == ""
        assert result.tax_status == ""

    def test_rtn_preserved(self):
        result = self._parse("", rtn="08011234567890")
        assert result.rtn == "08011234567890"

    def test_taxpayer_name_parsed(self):
        result = self._parse("Nombre: JUAN GARCIA PEREZ\nEstado: Activo")
        assert result.taxpayer_name == "JUAN GARCIA PEREZ"

    def test_address_parsed(self):
        result = self._parse("Dirección: Col. Kennedy, Tegucigalpa\nNombre: GARCIA")
        assert result.address == "Col. Kennedy, Tegucigalpa"

    def test_tax_status_parsed(self):
        result = self._parse("Estado: Activo\nNombre: GARCIA")
        assert result.tax_status == "Activo"

    def test_registration_date_parsed(self):
        result = self._parse("Fecha: 2010-05-12\nNombre: GARCIA")
        assert result.registration_date == "2010-05-12"

    def test_details_populated(self):
        result = self._parse("Nombre: GARCIA\nMunicipio: Tegucigalpa")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.hn.sar import HnSarResult

        r = HnSarResult(
            rtn="08011234567890",
            taxpayer_name="JUAN GARCIA PEREZ",
            tax_status="Activo",
            address="Col. Kennedy",
        )
        data = r.model_dump_json()
        r2 = HnSarResult.model_validate_json(data)
        assert r2.rtn == "08011234567890"
        assert r2.taxpayer_name == "JUAN GARCIA PEREZ"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.sar import HnSarResult

        r = HnSarResult(rtn="08011234567890", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnSarSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.sar import HnSarSource

        meta = HnSarSource().meta()
        assert meta.name == "hn.sar"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is True
        assert meta.rate_limit_rpm == 10

    def test_empty_rtn_raises(self):
        from openquery.sources.hn.sar import HnSarSource

        src = HnSarSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_rtn_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"rtn": "08011234567890"},
        )
        assert inp.extra.get("rtn") == "08011234567890"

    def test_rtn_from_document_number(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="08011234567890",
        )
        assert inp.document_number == "08011234567890"
