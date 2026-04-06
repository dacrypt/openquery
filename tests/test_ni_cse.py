"""Tests for ni.cse — Nicaragua CSE electoral/cedula lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiCseResult:
    def test_defaults(self):
        from openquery.models.ni.cse import NiCseResult

        r = NiCseResult()
        assert r.cedula == ""
        assert r.nombre == ""
        assert r.voting_center == ""
        assert r.municipality == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.cse import NiCseResult

        r = NiCseResult(
            cedula="001-010190-0001A",
            nombre="JUAN CARLOS GARCIA LOPEZ",
            voting_center="Escuela Primaria Nacional",
            municipality="Managua",
        )
        dumped = r.model_dump_json()
        restored = NiCseResult.model_validate_json(dumped)
        assert restored.cedula == "001-010190-0001A"
        assert restored.nombre == "JUAN CARLOS GARCIA LOPEZ"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.cse import NiCseResult

        r = NiCseResult(cedula="001-010190-0001A", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiCseSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.cse import NiCseSource

        meta = NiCseSource().meta()
        assert meta.name == "ni.cse"
        assert meta.country == "NI"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cedula_raises(self):
        from openquery.sources.ni.cse import NiCseSource

        src = NiCseSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_cedula_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CEDULA, document_number="001-010190-0001A")
        assert inp.document_number == "001-010190-0001A"

    def test_cedula_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="",
            extra={"cedula": "001-010190-0001A"},
        )
        assert inp.extra.get("cedula") == "001-010190-0001A"


class TestNiCseParseResult:
    def _parse(self, body_text: str, cedula: str = "001-010190-0001A"):
        from openquery.sources.ni.cse import NiCseSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiCseSource()
        return src._parse_result(page, cedula)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.voting_center == ""
        assert result.municipality == ""

    def test_cedula_preserved(self):
        result = self._parse("", cedula="001-010190-0001A")
        assert result.cedula == "001-010190-0001A"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: JUAN CARLOS GARCIA LOPEZ\nMunicipio: Managua")
        assert result.nombre == "JUAN CARLOS GARCIA LOPEZ"

    def test_voting_center_parsed(self):
        result = self._parse("Centro: Escuela Primaria Nacional\nNombre: JUAN GARCIA")
        assert result.voting_center == "Escuela Primaria Nacional"

    def test_municipality_parsed(self):
        result = self._parse("Municipio: Managua\nNombre: JUAN GARCIA")
        assert result.municipality == "Managua"

    def test_details_populated(self):
        result = self._parse("Nombre: JUAN GARCIA\nMunicipio: Managua")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.ni.cse import NiCseResult

        r = NiCseResult(
            cedula="001-010190-0001A",
            nombre="JUAN CARLOS GARCIA LOPEZ",
            voting_center="Escuela Primaria Nacional",
            municipality="Managua",
        )
        data = r.model_dump_json()
        r2 = NiCseResult.model_validate_json(data)
        assert r2.cedula == "001-010190-0001A"
        assert r2.nombre == "JUAN CARLOS GARCIA LOPEZ"
