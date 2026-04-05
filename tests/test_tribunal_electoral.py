"""Tests for pa.tribunal_electoral — Panama identity verification."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestResult
# ===========================================================================

class TestResult:
    def test_default_values(self):
        from openquery.models.pa.tribunal_electoral import TribunalElectoralResult
        r = TribunalElectoralResult()
        assert r.cedula == ""
        assert r.nombre == ""
        assert r.estado == ""
        assert r.circuito == ""
        assert r.corregimiento == ""
        assert r.centro_votacion == ""
        assert r.mesa == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.tribunal_electoral import TribunalElectoralResult
        r = TribunalElectoralResult(cedula="8-123-456")
        r.audit = {"evidence": "data"}
        data = r.model_dump_json()
        assert "audit" not in data

    def test_model_roundtrip(self):
        from openquery.models.pa.tribunal_electoral import TribunalElectoralResult
        r = TribunalElectoralResult(
            cedula="8-123-456",
            nombre="Juan Perez",
            estado="Vigente",
            circuito="8-1",
            corregimiento="Bella Vista",
            centro_votacion="Escuela Bella Vista",
            mesa="5",
        )
        r2 = TribunalElectoralResult.model_validate_json(r.model_dump_json())
        assert r2.cedula == "8-123-456"
        assert r2.nombre == "Juan Perez"
        assert r2.estado == "Vigente"
        assert r2.circuito == "8-1"
        assert r2.mesa == "5"


# ===========================================================================
# TestSourceMeta
# ===========================================================================

class TestSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        meta = TribunalElectoralSource().meta()
        assert meta.name == "pa.tribunal_electoral"

    def test_meta_country(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        meta = TribunalElectoralSource().meta()
        assert meta.country == "PA"

    def test_meta_requires_browser(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        meta = TribunalElectoralSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supports_cedula(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        meta = TribunalElectoralSource().meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        meta = TribunalElectoralSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestParseResult
# ===========================================================================

class TestParseResult:
    def _parse(self, body_text: str, cedula: str = "8-123-456"):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        page = MagicMock()
        page.inner_text.return_value = body_text
        src = TribunalElectoralSource()
        return src._parse_result(page, cedula)

    def test_parses_nombre(self):
        result = self._parse("Nombre: Juan Carlos Perez\nEstado: Vigente")
        assert result.nombre == "Juan Carlos Perez"

    def test_parses_estado_vigente(self):
        result = self._parse("Estado: Vigente\nNombre: Maria Lopez")
        assert result.estado == "Vigente"

    def test_parses_circuito(self):
        result = self._parse("Nombre: Ana\nCircuito: 8-1\nCorregimiento: Bella Vista")
        assert result.circuito == "8-1"
        assert result.corregimiento == "Bella Vista"

    def test_parses_centro_votacion(self):
        result = self._parse("Nombre: Ana\nCentro de Votación: Escuela Bella Vista\nMesa: 3")
        assert result.centro_votacion == "Escuela Bella Vista"
        assert result.mesa == "3"

    def test_not_found_returns_no_registrada(self):
        result = self._parse("No se encontró información para la cédula consultada")
        assert result.estado == "No registrada"
        assert result.nombre == ""

    def test_fallback_vigente_from_body(self):
        result = self._parse("El ciudadano se encuentra habilitado para votar")
        assert result.estado == "Vigente"

    def test_fallback_cancelada_from_body(self):
        result = self._parse("La cédula ha sido cancelada por fallecimiento")
        assert result.estado == "Cancelada"

    def test_cedula_preserved(self):
        result = self._parse("Estado: Vigente", cedula="9-999-999")
        assert result.cedula == "9-999-999"

    def test_details_populated(self):
        result = self._parse("Nombre: Juan\nCircuito: 8-1\nMesa: 2")
        assert "Nombre" in result.details
        assert result.details["Nombre"] == "Juan"

    def test_wrong_document_type_raises(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        src = TribunalElectoralSource()
        with pytest.raises(SourceError, match="cedula"):
            src.query(QueryInput(document_type=DocumentType.NIT, document_number="123"))

    def test_empty_cedula_raises(self):
        from openquery.sources.pa.tribunal_electoral import TribunalElectoralSource
        src = TribunalElectoralSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))
