"""Tests for ni.dgi — Nicaragua DGI tax/RUC registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiDgiResult:
    def test_defaults(self):
        from openquery.models.ni.dgi import NiDgiResult

        r = NiDgiResult()
        assert r.ruc == ""
        assert r.taxpayer_name == ""
        assert r.tax_status == ""
        assert r.address == ""
        assert r.economic_activity == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.dgi import NiDgiResult

        r = NiDgiResult(
            ruc="J0310000000001",
            taxpayer_name="EMPRESA EJEMPLO SA",
            tax_status="Activo",
            address="Managua, Nicaragua",
            economic_activity="Comercio al por mayor",
        )
        dumped = r.model_dump_json()
        restored = NiDgiResult.model_validate_json(dumped)
        assert restored.ruc == "J0310000000001"
        assert restored.taxpayer_name == "EMPRESA EJEMPLO SA"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.dgi import NiDgiResult

        r = NiDgiResult(ruc="J0310000000001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiDgiSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.dgi import NiDgiSource

        meta = NiDgiSource().meta()
        assert meta.name == "ni.dgi"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_ruc_raises(self):
        from openquery.sources.ni.dgi import NiDgiSource

        src = NiDgiSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_ruc_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="J0310000000001")
        assert inp.document_number == "J0310000000001"

    def test_ruc_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"ruc": "J0310000000001"},
        )
        assert inp.extra.get("ruc") == "J0310000000001"


class TestNiDgiParseResult:
    def _parse(self, body_text: str, ruc: str = "J0310000000001"):
        from openquery.sources.ni.dgi import NiDgiSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiDgiSource()
        return src._parse_result(page, ruc)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.taxpayer_name == ""
        assert result.tax_status == ""

    def test_ruc_preserved(self):
        result = self._parse("", ruc="J0310000000001")
        assert result.ruc == "J0310000000001"

    def test_taxpayer_name_parsed(self):
        result = self._parse("Nombre: EMPRESA EJEMPLO SOCIEDAD ANONIMA\nEstado: Activo")
        assert result.taxpayer_name == "EMPRESA EJEMPLO SOCIEDAD ANONIMA"

    def test_tax_status_parsed(self):
        result = self._parse("Estado: Activo\nNombre: EMPRESA SA")
        assert result.tax_status == "Activo"

    def test_address_parsed(self):
        result = self._parse("Dirección: Managua, Distrito I\nNombre: EMPRESA SA")
        assert result.address == "Managua, Distrito I"

    def test_economic_activity_parsed(self):
        result = self._parse("Actividad: Comercio al por mayor\nNombre: EMPRESA SA")
        assert result.economic_activity == "Comercio al por mayor"

    def test_details_populated(self):
        result = self._parse("Nombre: EMPRESA SA\nEstado: Activo")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.ni.dgi import NiDgiResult

        r = NiDgiResult(
            ruc="J0310000000001",
            taxpayer_name="EMPRESA EJEMPLO SA",
            tax_status="Activo",
        )
        data = r.model_dump_json()
        r2 = NiDgiResult.model_validate_json(data)
        assert r2.ruc == "J0310000000001"
        assert r2.taxpayer_name == "EMPRESA EJEMPLO SA"
