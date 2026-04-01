"""Tests for browser-based sources — policia, adres, fasecolda, recalls.

Uses mocked Playwright via patching BrowserManager.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# co.policia — parse_result logic
# ===========================================================================

class TestPoliciaParseResult:
    """Test _parse_result with mocked page.inner_text."""

    def _parse(self, body_text: str, cedula: str = "12345678"):
        from openquery.sources.co.policia import PoliciaSource
        page = MagicMock()
        page.inner_text.return_value = body_text
        src = PoliciaSource()
        return src._parse_result(page, cedula)

    def test_no_records(self):
        result = self._parse("Su cédula de ciudadanía no registra antecedentes")
        assert result.tiene_antecedentes is False
        assert "no tiene asuntos pendientes" in result.mensaje.lower()

    def test_has_records(self):
        result = self._parse("Registra antecedentes judiciales vigentes")
        assert result.tiene_antecedentes is True
        assert "antecedentes" in result.mensaje.lower()

    def test_no_records_alt_phrase(self):
        result = self._parse("La persona no aparece en la base de datos")
        assert result.tiene_antecedentes is False

    def test_ambiguous_text(self):
        result = self._parse("Resultado de la consulta realizada")
        assert result.tiene_antecedentes is False
        assert result.mensaje == ""

    def test_cedula_preserved(self):
        result = self._parse("No registra", cedula="9876543")
        assert result.cedula == "9876543"


class TestPoliciaSource:
    def test_meta(self):
        from openquery.sources.co.policia import PoliciaSource
        meta = PoliciaSource().meta()
        assert meta.name == "co.policia"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True

    def test_unsupported_doc_type(self):
        from openquery.sources.co.policia import PoliciaSource
        src = PoliciaSource()
        with pytest.raises(SourceError, match="Only cedula"):
            src.query(QueryInput(
                document_type=DocumentType.PLATE,
                document_number="ABC123",
            ))


# ===========================================================================
# co.adres — parse_result logic
# ===========================================================================

class TestAdresParseResult:
    def _parse(self, body_text: str, rows_data=None, doc_number="12345"):
        from openquery.sources.co.adres import AdresSource
        page = MagicMock()
        page.inner_text.return_value = body_text

        if rows_data:
            mock_rows = []
            for row_values in rows_data:
                row = MagicMock()
                cells = []
                for val in row_values:
                    cell = MagicMock()
                    cell.inner_text.return_value = val
                    cells.append(cell)
                row.query_selector_all.return_value = cells
                mock_rows.append(row)
            page.query_selector_all.return_value = mock_rows
        else:
            page.query_selector_all.return_value = []

        src = AdresSource()
        return src._parse_result(page, DocumentType.CEDULA, doc_number)

    def test_table_parsing(self):
        header = ["TipoDoc", "Numero", "Juan Perez", "ACTIVO", "SANITAS", "CONTRIBUTIVO",
                   "COTIZANTE", "BOGOTA", "CUNDINAMARCA", "2020-01-15"]
        data = ["CC", "12345", "Juan Perez", "ACTIVO", "SANITAS", "CONTRIBUTIVO",
                "COTIZANTE", "BOGOTA", "CUNDINAMARCA", "2020-01-15"]
        result = self._parse("", rows_data=[header, data])
        assert result.eps == "SANITAS"
        assert result.regimen == "CONTRIBUTIVO"
        assert result.estado_afiliacion == "ACTIVO"
        assert result.municipio == "BOGOTA"

    def test_fallback_regex_parsing(self):
        text = "EPS: NUEVA EPS\nEstado: ACTIVO\nRégimen: SUBSIDIADO"
        result = self._parse(text)
        assert result.eps == "NUEVA EPS"
        assert result.regimen == "SUBSIDIADO"
        assert result.estado_afiliacion == "ACTIVO"

    def test_no_data(self):
        result = self._parse("No se encontraron resultados")
        assert result.eps == ""


class TestAdresSource:
    def test_meta(self):
        from openquery.sources.co.adres import AdresSource
        meta = AdresSource().meta()
        assert meta.name == "co.adres"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert DocumentType.PASSPORT in meta.supported_inputs
        assert meta.requires_browser is True

    def test_unsupported_doc_type(self):
        from openquery.sources.co.adres import AdresSource
        src = AdresSource()
        with pytest.raises(SourceError, match="Unsupported document type"):
            src.query(QueryInput(
                document_type=DocumentType.PLATE,
                document_number="ABC123",
            ))


# ===========================================================================
# co.fasecolda
# ===========================================================================

class TestFasecoldaSource:
    def test_meta(self):
        from openquery.sources.co.fasecolda import FasecoldaSource
        meta = FasecoldaSource().meta()
        assert meta.name == "co.fasecolda"
        assert meta.requires_browser is True
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_unsupported_doc_type(self):
        from openquery.sources.co.fasecolda import FasecoldaSource
        src = FasecoldaSource()
        with pytest.raises(SourceError, match="CUSTOM"):
            src.query(QueryInput(
                document_type=DocumentType.CEDULA,
                document_number="123",
            ))


# ===========================================================================
# co.recalls
# ===========================================================================

class TestRecallsSource:
    def test_meta(self):
        from openquery.sources.co.recalls import RecallsSource
        meta = RecallsSource().meta()
        assert meta.name == "co.recalls"
        assert meta.requires_browser is True
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_unsupported_doc_type(self):
        from openquery.sources.co.recalls import RecallsSource
        src = RecallsSource()
        with pytest.raises(SourceError, match="CUSTOM"):
            src.query(QueryInput(
                document_type=DocumentType.CEDULA,
                document_number="123",
            ))
