"""Tests for sv.rnpn — El Salvador RNPN civil registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestRnpnParseResult:
    def _parse(self, body_text: str, dui: str = "00000001-0"):
        from openquery.sources.sv.rnpn import RnpnSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = RnpnSource()
        return src._parse_result(page, dui)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.civil_status == ""

    def test_dui_preserved(self):
        result = self._parse("", dui="00000002-1")
        assert result.dui == "00000002-1"

    def test_parses_nombre(self):
        body = "Nombre: Carlos Antonio López\nEstado Civil: Soltero"
        result = self._parse(body)
        assert result.nombre == "Carlos Antonio López"

    def test_parses_civil_status(self):
        body = "Estado Civil: Casado\nNombre: Ana García"
        result = self._parse(body)
        assert result.civil_status == "Casado"

    def test_parses_estado_label(self):
        body = "Estado: Activo\nNombre: Pedro Ramírez"
        result = self._parse(body)
        assert result.civil_status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.sv.rnpn import RnpnResult

        r = RnpnResult(
            dui="00000001-0",
            nombre="Carlos López",
            civil_status="Soltero",
        )
        data = r.model_dump_json()
        r2 = RnpnResult.model_validate_json(data)
        assert r2.dui == "00000001-0"
        assert r2.nombre == "Carlos López"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.rnpn import RnpnResult

        r = RnpnResult(dui="00000001-0", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestRnpnSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.rnpn import RnpnSource

        meta = RnpnSource().meta()
        assert meta.name == "sv.rnpn"
        assert meta.country == "SV"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dui_raises(self):
        from openquery.sources.sv.rnpn import RnpnSource

        src = RnpnSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_document_number_used_as_dui(self):
        input_ = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="00000001-0",
        )
        assert input_.document_number == "00000001-0"
