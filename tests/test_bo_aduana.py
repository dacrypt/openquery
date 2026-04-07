"""Tests for bo.aduana — Bolivia Aduana Nacional customs source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAduanaParseResult:
    def _parse(self, body_text: str, declaration_number: str = "DUI-2024-001"):
        from openquery.sources.bo.aduana import AduanaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = AduanaSource()
        return src._parse_result(page, declaration_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.declarant_name == ""
        assert result.customs_status == ""

    def test_declaration_number_preserved(self):
        result = self._parse("", declaration_number="DUI-2024-999")
        assert result.declaration_number == "DUI-2024-999"

    def test_parses_declarant(self):
        body = "Declarante: Importadora Bolivia SA\nEstado: Despachado"
        result = self._parse(body)
        assert result.declarant_name == "Importadora Bolivia SA"

    def test_parses_customs_status(self):
        body = "Estado: Levante autorizado\nFecha: 2024-01-15"
        result = self._parse(body)
        assert result.customs_status == "Levante autorizado"

    def test_parses_goods_description(self):
        body = "Mercancía: Maquinaria industrial\nEstado: Ingresado"
        result = self._parse(body)
        assert result.goods_description == "Maquinaria industrial"

    def test_model_roundtrip(self):
        from openquery.models.bo.aduana import AduanaResult

        r = AduanaResult(
            declaration_number="DUI-001",
            declarant_name="Importadora BO",
            customs_status="Despachado",
        )
        data = r.model_dump_json()
        r2 = AduanaResult.model_validate_json(data)
        assert r2.declaration_number == "DUI-001"
        assert r2.declarant_name == "Importadora BO"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.aduana import AduanaResult

        r = AduanaResult(declaration_number="DUI-001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestAduanaSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.aduana import AduanaSource

        meta = AduanaSource().meta()
        assert meta.name == "bo.aduana"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_declaration_raises(self):
        from openquery.sources.bo.aduana import AduanaSource

        src = AduanaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
