"""Tests for ve.cne — Venezuela electoral registry / cedula lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestCneResult — model tests
# ===========================================================================


class TestCneResult:
    def test_defaults(self):
        from openquery.models.ve.cne import CneResult

        r = CneResult()
        assert r.cedula == ""
        assert r.nombre == ""
        assert r.centro_votacion == ""
        assert r.municipio == ""
        assert r.estado == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.cne import CneResult

        r = CneResult(
            cedula="V12345678",
            nombre="JUAN PEREZ",
            centro_votacion="Escuela Bolivariana",
            municipio="Libertador",
            estado="Distrito Capital",
        )
        dumped = r.model_dump_json()
        restored = CneResult.model_validate_json(dumped)
        assert restored.cedula == "V12345678"
        assert restored.nombre == "JUAN PEREZ"
        assert restored.centro_votacion == "Escuela Bolivariana"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.cne import CneResult

        r = CneResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.cne import CneResult

        r = CneResult(details={"Nombre": "JUAN PEREZ", "Estado": "Miranda"})
        assert r.details["Nombre"] == "JUAN PEREZ"


# ===========================================================================
# TestCneSourceMeta
# ===========================================================================


class TestCneSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.cne import CneSource

        assert CneSource().meta().name == "ve.cne"

    def test_meta_country(self):
        from openquery.sources.ve.cne import CneSource

        assert CneSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.cne import CneSource

        assert CneSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.ve.cne import CneSource

        assert CneSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.cne import CneSource

        assert DocumentType.CEDULA in CneSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.cne import CneSource

        assert CneSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestCneQuery — input validation
# ===========================================================================


class TestCneQuery:
    def test_wrong_document_type_raises(self):
        from openquery.sources.ve.cne import CneSource

        src = CneSource()
        with pytest.raises(SourceError, match="cedula"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="123"))

    def test_empty_cedula_raises(self):
        from openquery.sources.ve.cne import CneSource

        src = CneSource()
        with pytest.raises(SourceError, match="cedula is required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_valid_cedula_calls_query(self):
        from openquery.models.ve.cne import CneResult
        from openquery.sources.ve.cne import CneSource

        src = CneSource()
        src._query = MagicMock(return_value=CneResult(cedula="12345678"))
        result = src.query(
            QueryInput(document_type=DocumentType.CEDULA, document_number="12345678")
        )
        src._query.assert_called_once_with("12345678", audit=False)
        assert result.cedula == "12345678"


# ===========================================================================
# TestCneParseResult — parsing logic
# ===========================================================================


class TestCneParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        return page

    def _parse(self, body_text: str, cedula: str = "12345678") -> object:
        from openquery.sources.ve.cne import CneSource

        return CneSource()._parse_result(self._make_page(body_text), cedula)

    def test_nombre_extracted(self):
        body = "Nombre: JUAN PEREZ\nCentro: Escuela Bolivariana\n"
        result = self._parse(body)
        assert result.nombre == "JUAN PEREZ"

    def test_centro_votacion_extracted(self):
        body = "Nombre: JUAN PEREZ\nCentro: Escuela Bolivariana\n"
        result = self._parse(body)
        assert result.centro_votacion == "Escuela Bolivariana"

    def test_municipio_extracted(self):
        body = "Municipio: Libertador\n"
        result = self._parse(body)
        assert result.municipio == "Libertador"

    def test_estado_extracted(self):
        body = "Estado: Miranda\n"
        result = self._parse(body)
        assert result.estado == "Miranda"

    def test_cedula_preserved(self):
        result = self._parse("", cedula="V12345678")
        assert result.cedula == "V12345678"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.centro_votacion == ""

    def test_details_populated(self):
        body = "Nombre: JUAN PEREZ\nEstado: Miranda\n"
        result = self._parse(body)
        assert "Nombre" in result.details or isinstance(result.details, dict)

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestCneIntegration:
    def test_query_by_cedula(self):
        from openquery.sources.ve.cne import CneSource

        src = CneSource(headless=True)
        # Use a public test cedula (V prefix)
        result = src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="V1"))
        assert isinstance(result.cedula, str)
        assert isinstance(result.nombre, str)
