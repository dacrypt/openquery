"""Tests for cl.dicom — DICOM/Equifax credit report public summary."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestDicomResult:
    """Test DicomResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.cl.dicom import DicomResult

        r = DicomResult()
        assert r.rut == ""
        assert r.dicom_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.cl.dicom import DicomResult

        r = DicomResult(rut="12345678-9", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "12345678-9" in dumped

    def test_json_roundtrip(self):
        from openquery.models.cl.dicom import DicomResult

        r = DicomResult(
            rut="12345678-9",
            dicom_status="Sin DICOM",
            details={"Estado": "Limpio"},
        )
        r2 = DicomResult.model_validate_json(r.model_dump_json())
        assert r2.rut == "12345678-9"
        assert r2.dicom_status == "Sin DICOM"

    def test_queried_at_default(self):
        from openquery.models.cl.dicom import DicomResult

        before = datetime.now()
        r = DicomResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestDicomSourceMeta:
    """Test cl.dicom source metadata."""

    def test_meta_name(self):
        from openquery.sources.cl.dicom import DicomSource

        assert DicomSource().meta().name == "cl.dicom"

    def test_meta_country(self):
        from openquery.sources.cl.dicom import DicomSource

        assert DicomSource().meta().country == "CL"

    def test_meta_requires_browser(self):
        from openquery.sources.cl.dicom import DicomSource

        assert DicomSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.cl.dicom import DicomSource

        assert DocumentType.CUSTOM in DicomSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.cl.dicom import DicomSource

        assert DicomSource().meta().rate_limit_rpm == 10


class TestDicomParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, rut: str = "12345678-9"):
        from openquery.sources.cl.dicom import DicomSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return DicomSource()._parse_result(page, rut)

    def test_rut_preserved(self):
        assert self._parse("Datos").rut == "12345678-9"

    def test_dicom_status_clean(self):
        result = self._parse("Sin DICOM - No registra deudas")
        assert result.dicom_status == "Sin DICOM"

    def test_dicom_status_delinquent(self):
        result = self._parse("Con DICOM - Registra deudas morosas")
        assert result.dicom_status == "Con DICOM"

    def test_empty_body(self):
        result = self._parse("")
        assert result.rut == "12345678-9"
        assert result.dicom_status == ""

    def test_query_missing_rut_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.cl.dicom import DicomSource

        with pytest.raises(SourceError, match="RUT"):
            DicomSource().query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
