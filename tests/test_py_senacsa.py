"""Tests for py.senacsa — Paraguay SENACSA animal health registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSenácsaParseResult:
    def _parse(self, body_text: str, search_term: str = "Estancia Test"):
        from openquery.sources.py.senacsa import SenácsaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SenácsaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.farm_name == ""
        assert result.sanitary_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Estancia Sur")
        assert result.search_term == "Estancia Sur"

    def test_parses_farm_name(self):
        body = "Establecimiento: Estancia La Esperanza\nEstado sanitario: Habilitado"
        result = self._parse(body)
        assert result.farm_name == "Estancia La Esperanza"

    def test_parses_owner(self):
        body = "Propietario: Carlos Py\nEstado sanitario: Habilitado"
        result = self._parse(body)
        assert result.owner_name == "Carlos Py"

    def test_model_roundtrip(self):
        from openquery.models.py.senacsa import SenácsaResult

        r = SenácsaResult(search_term="test", farm_name="Estancia PY", sanitary_status="Habilitado")
        data = r.model_dump_json()
        r2 = SenácsaResult.model_validate_json(data)
        assert r2.farm_name == "Estancia PY"

    def test_audit_excluded_from_json(self):
        from openquery.models.py.senacsa import SenácsaResult

        r = SenácsaResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSenácsaSourceMeta:
    def test_meta(self):
        from openquery.sources.py.senacsa import SenácsaSource

        meta = SenácsaSource().meta()
        assert meta.name == "py.senacsa"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.py.senacsa import SenácsaSource

        src = SenácsaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
