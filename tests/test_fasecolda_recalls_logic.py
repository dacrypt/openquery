"""Tests for fasecolda and recalls source logic (mocked browser)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestFasecoldaValidation:
    def test_missing_marca_raises(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        with pytest.raises(SourceError, match="marca"):
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={},
            ))

    def test_empty_marca_raises(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        with pytest.raises(SourceError, match="marca"):
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"marca": ""},
            ))


class TestFasecoldaBuildResult:
    def test_build_result_empty(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        result = src._build_result("TESLA", 2026, [])
        assert result.marca == "TESLA"
        assert result.modelo == 2026
        assert result.valor == 0
        assert result.resultados == []

    def test_build_result_with_data(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        data = [{
            "referencia": "MODEL 3",
            "valor": 150000000,
            "cilindraje": 0,
            "combustible": "ELECTRICO",
            "transmision": "AUTOMATICA",
            "puertas": 4,
            "pasajeros": 5,
            "codigoFasecolda": "XYZ",
        }]
        result = src._build_result("TESLA", 2026, data)
        assert result.marca == "TESLA"
        assert result.linea == "MODEL 3"
        assert result.valor == 150000000
        assert result.combustible == "ELECTRICO"
        assert result.codigo_fasecolda == "XYZ"

    def test_build_result_no_modelo(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        result = src._build_result("CHEVROLET", None, [{"valor": 50000000}])
        assert result.modelo == 0
        assert result.valor == 50000000


class TestFasecoldaApiFetch:
    def test_api_fetch_success(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        page = MagicMock()
        page.evaluate.return_value = [{"id": 1, "marca": "TESLA"}]
        result = src._api_fetch(page, "Bearer xyz", "https://example.com/api")
        assert result == [{"id": 1, "marca": "TESLA"}]

    def test_api_fetch_error(self):
        from openquery.sources.co.fasecolda import FasecoldaSource

        src = FasecoldaSource()
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True, "status": 403, "text": "Forbidden",
        }
        with pytest.raises(SourceError, match="403"):
            src._api_fetch(page, "Bearer xyz", "https://example.com/api")


class TestRecallsValidation:
    def test_missing_marca_raises(self):
        from openquery.sources.co.recalls import RecallsSource

        src = RecallsSource()
        with pytest.raises(SourceError, match="marca"):
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={},
            ))

    def test_empty_marca_raises(self):
        from openquery.sources.co.recalls import RecallsSource

        src = RecallsSource()
        with pytest.raises(SourceError, match="marca"):
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"marca": "  "},
            ))


class TestRecallsExtract:
    def test_extract_no_matches(self):
        from openquery.sources.co.recalls import RecallsSource

        src = RecallsSource()
        page = MagicMock()
        page.query_selector_all.return_value = []
        result = src._extract_recalls(page, "NONEXISTENT_BRAND")
        assert result == []

    def test_extract_from_links(self):
        from openquery.sources.co.recalls import RecallsSource

        src = RecallsSource()
        page = MagicMock()

        # First call: a:has-text returns matches
        link1 = MagicMock()
        link1.inner_text.return_value = "TESLA Model 3 Recall"
        link1.get_attribute.return_value = "https://sic.gov.co/recall/1"
        page.query_selector_all.return_value = [link1]

        result = src._extract_recalls(page, "TESLA")
        assert len(result) == 1
        assert "TESLA" in result[0]["descripcion"]
        assert result[0]["url"] == "https://sic.gov.co/recall/1"

    def test_extract_from_table_rows(self):
        from openquery.sources.co.recalls import RecallsSource

        src = RecallsSource()
        page = MagicMock()

        # First call (links): no matches
        # Second call (table rows): has matches
        row = MagicMock()
        row.inner_text.return_value = "CHEVROLET Spark recall campaign 2024"

        def side_effect(selector):
            if "has-text" in selector:
                return []
            if selector == "a":
                return []  # No matching links
            return [row]

        page.query_selector_all.side_effect = side_effect

        result = src._extract_recalls(page, "CHEVROLET")
        assert len(result) == 1
        assert "CHEVROLET" in result[0]["descripcion"]
