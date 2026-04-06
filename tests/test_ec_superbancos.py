"""Tests for ec.superbancos — Superintendencia de Bancos supervised entities."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestSuperbancosResult:
    """Test SuperbancosResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.ec.superbancos import SuperbancosResult

        r = SuperbancosResult()
        assert r.search_term == ""
        assert r.entity_name == ""
        assert r.entity_type == ""
        assert r.supervision_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.ec.superbancos import SuperbancosResult

        r = SuperbancosResult(search_term="Banco Pichincha", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "Banco Pichincha" in dumped

    def test_json_roundtrip(self):
        from openquery.models.ec.superbancos import SuperbancosResult

        r = SuperbancosResult(
            search_term="Banco Pichincha",
            entity_name="BANCO PICHINCHA CA",
            entity_type="Banco Privado",
            supervision_status="Activo",
            details={"Tipo": "Banco Privado"},
        )
        r2 = SuperbancosResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "Banco Pichincha"
        assert r2.entity_name == "BANCO PICHINCHA CA"
        assert r2.entity_type == "Banco Privado"

    def test_queried_at_default(self):
        from openquery.models.ec.superbancos import SuperbancosResult

        before = datetime.now()
        r = SuperbancosResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSuperbancosSourceMeta:
    """Test ec.superbancos source metadata."""

    def test_meta_name(self):
        from openquery.sources.ec.superbancos import SuperbancosSource

        assert SuperbancosSource().meta().name == "ec.superbancos"

    def test_meta_country(self):
        from openquery.sources.ec.superbancos import SuperbancosSource

        assert SuperbancosSource().meta().country == "EC"

    def test_meta_requires_browser(self):
        from openquery.sources.ec.superbancos import SuperbancosSource

        assert SuperbancosSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.ec.superbancos import SuperbancosSource

        assert DocumentType.CUSTOM in SuperbancosSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ec.superbancos import SuperbancosSource

        assert SuperbancosSource().meta().rate_limit_rpm == 10


class TestSuperbancosParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, search_term: str = "Banco Pichincha"):
        from openquery.sources.ec.superbancos import SuperbancosSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return SuperbancosSource()._parse_result(page, search_term)

    def test_search_term_preserved(self):
        assert self._parse("Datos").search_term == "Banco Pichincha"

    def test_entity_name_parsed(self):
        result = self._parse("Entidad: BANCO PICHINCHA CA\nOtros")
        assert result.entity_name == "BANCO PICHINCHA CA"

    def test_entity_name_defaults_to_search_term(self):
        result = self._parse("Sin resultados")
        assert result.entity_name == "Banco Pichincha"

    def test_entity_type_parsed(self):
        result = self._parse("Tipo: Banco Privado\nOtros")
        assert result.entity_type == "Banco Privado"

    def test_supervision_status_parsed(self):
        result = self._parse("Estado: Activo\nOtros")
        assert result.supervision_status == "Activo"

    def test_empty_body(self):
        result = self._parse("")
        assert result.search_term == "Banco Pichincha"
        assert result.supervision_status == ""

    def test_query_missing_search_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.ec.superbancos import SuperbancosSource

        with pytest.raises(SourceError, match="[Ee]ntity"):
            SuperbancosSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
