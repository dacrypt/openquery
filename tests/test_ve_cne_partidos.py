"""Tests for ve.cne_partidos — Venezuela CNE political party registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestVeCnePartidosParseResult:
    def _parse(self, body_text: str, search_term: str = "PSUV"):
        from openquery.sources.ve.cne_partidos import VeCnePartidosSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = VeCnePartidosSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.party_name == ""
        assert result.registration_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="PSUV")
        assert result.search_term == "PSUV"

    def test_party_name_parsed(self):
        result = self._parse("Partido: Partido Socialista Unido de Venezuela\nEstado: Activo")
        assert result.party_name == "Partido Socialista Unido de Venezuela"

    def test_registration_status_parsed(self):
        result = self._parse("Partido: MUD\nEstado: Activo")
        assert result.registration_status == "Activo"

    def test_details_populated(self):
        result = self._parse("Partido: AD\nRegistro: Vigente")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.ve.cne_partidos import VeCnePartidosResult

        r = VeCnePartidosResult(
            search_term="PSUV",
            party_name="Partido Socialista Unido de Venezuela",
            registration_status="Activo",
        )
        data = r.model_dump_json()
        r2 = VeCnePartidosResult.model_validate_json(data)
        assert r2.search_term == "PSUV"
        assert r2.party_name == "Partido Socialista Unido de Venezuela"
        assert r2.registration_status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.cne_partidos import VeCnePartidosResult

        r = VeCnePartidosResult(search_term="PSUV", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestVeCnePartidosSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.cne_partidos import VeCnePartidosSource

        meta = VeCnePartidosSource().meta()
        assert meta.name == "ve.cne_partidos"
        assert meta.country == "VE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_party_name_raises(self):
        from openquery.sources.ve.cne_partidos import VeCnePartidosSource

        src = VeCnePartidosSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
