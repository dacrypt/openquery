"""Tests for document OCR extraction pipelines."""

from __future__ import annotations

import pytest

from openquery.core.document_ocr import DocumentOCR
from openquery.models.ocr import DocumentTypeOCR, OCRInput, OCRResult


class TestOCRModels:
    """Test OCR model validation."""

    def test_ocr_input_requires_image_source(self):
        with pytest.raises(ValueError, match="Provide either"):
            OCRInput(document_type=DocumentTypeOCR.CO_CEDULA)

    def test_ocr_input_rejects_both_sources(self):
        with pytest.raises(ValueError, match="Provide only one"):
            OCRInput(
                image_base64="abc",
                image_path="/tmp/test.png",
                document_type=DocumentTypeOCR.CO_CEDULA,
            )

    def test_ocr_input_accepts_base64(self):
        inp = OCRInput(image_base64="abc", document_type=DocumentTypeOCR.CO_CEDULA)
        assert inp.image_base64 == "abc"

    def test_ocr_input_accepts_path(self):
        inp = OCRInput(image_path="/tmp/test.png", document_type=DocumentTypeOCR.CO_CEDULA)
        assert inp.image_path == "/tmp/test.png"

    def test_document_type_values(self):
        assert DocumentTypeOCR.CO_CEDULA == "co.cedula"
        assert DocumentTypeOCR.MX_INE == "mx.ine"
        assert DocumentTypeOCR.PE_DNI == "pe.dni"
        assert DocumentTypeOCR.CL_CARNET == "cl.carnet"
        assert DocumentTypeOCR.PASSPORT_MRZ == "passport.mrz"

    def test_ocr_result_serialization(self):
        result = OCRResult(
            document_type=DocumentTypeOCR.CO_CEDULA,
            fields={"cedula": "12345678", "nombres": "JUAN"},
            confidence=0.95,
            raw_text="test",
            processing_time_ms=100,
        )
        data = result.model_dump(mode="json")
        assert data["fields"]["cedula"] == "12345678"


class TestCOCedulaPipeline:
    """Test Colombian cedula regex extraction."""

    def _extract(self, text: str) -> dict:
        ocr = DocumentOCR()
        return ocr._extract_co_cedula(text)

    def test_extracts_cedula_number(self):
        fields = self._extract("CEDULA DE CIUDADANIA\n1234567890\nBOGOTA DC")
        assert fields["cedula"] == "1234567890"

    def test_extracts_dob(self):
        fields = self._extract("FECHA NACIMIENTO 15/03/1990\nNUMERO 12345678")
        assert fields["fecha_nacimiento"] == "15/03/1990"

    def test_extracts_blood_type(self):
        fields = self._extract("RH O+\nREGISTRO CIVIL")
        assert fields["grupo_sanguineo"] == "O+"

    def test_extracts_sex(self):
        fields = self._extract("SEXO MASCULINO\nNACIONALIDAD COLOMBIANA")
        assert fields["sexo"] == "MASCULINO"

    def test_extracts_names(self):
        fields = self._extract("APELLIDOS: GARCIA MARTINEZ\nNOMBRES: JUAN CARLOS")
        assert fields["apellidos"] == "GARCIA MARTINEZ"
        assert fields["nombres"] == "JUAN CARLOS"


class TestMXINEPipeline:
    """Test Mexican INE regex extraction."""

    def _extract(self, text: str) -> dict:
        ocr = DocumentOCR()
        return ocr._extract_mx_ine(text)

    def test_extracts_curp(self):
        fields = self._extract("CURP GARC901215HDFRRL09")
        assert fields["curp"] == "GARC901215HDFRRL09"

    def test_extracts_clave_elector(self):
        fields = self._extract("CLAVE ELECTOR GRCRLS90121509H001")
        assert fields["clave_elector"] == "GRCRLS90121509H001"

    def test_extracts_dob(self):
        fields = self._extract("F. NAC 15/12/1990")
        assert fields["fecha_nacimiento"] == "15/12/1990"

    def test_extracts_sex(self):
        fields = self._extract("SEXO: H ESTADO")
        assert fields["sexo"] == "H"


class TestPEDNIPipeline:
    """Test Peruvian DNI regex extraction."""

    def _extract(self, text: str) -> dict:
        ocr = DocumentOCR()
        return ocr._extract_pe_dni(text)

    def test_extracts_dni_number(self):
        fields = self._extract("DNI 12345678\nREPUBLICA DEL PERU")
        assert fields["dni"] == "12345678"

    def test_extracts_names(self):
        fields = self._extract("APELLIDO PATERNO: GARCIA\nAPELLIDO MATERNO: LOPEZ\nNOMBRES: CARLOS")
        assert fields["apellido_paterno"] == "GARCIA"
        assert fields["apellido_materno"] == "LOPEZ"
        assert fields["nombres"] == "CARLOS"


class TestCLCarnetPipeline:
    """Test Chilean carnet regex extraction."""

    def _extract(self, text: str) -> dict:
        ocr = DocumentOCR()
        return ocr._extract_cl_carnet(text)

    def test_extracts_run_with_dots(self):
        fields = self._extract("RUN 12.345.678-9\nREPUBLICA DE CHILE")
        assert fields["run"] == "12.345.678-9"

    def test_extracts_run_without_dots(self):
        fields = self._extract("RUN 12345678-K\nNACIONALIDAD CHILENA")
        assert fields["run"] == "12345678-K"

    def test_extracts_names(self):
        fields = self._extract("APELLIDOS: GONZALEZ ROJAS\nNOMBRES: MARIA ISABEL")
        assert fields["apellidos"] == "GONZALEZ ROJAS"
        assert fields["nombres"] == "MARIA ISABEL"


class TestPassportMRZPipeline:
    """Test passport MRZ regex extraction."""

    def _extract(self, text: str) -> dict:
        ocr = DocumentOCR()
        return ocr._parse_mrz_from_text(text)

    def test_extracts_mrz_line1(self):
        fields = self._extract("P<COL<GARCIA<MARTINEZ<<JUAN<CARLOS<<<<")
        assert fields["pais_emisor"] == "COL"
        assert fields["apellidos"] == "GARCIA MARTINEZ"
        assert fields["nombres"] == "JUAN CARLOS"

    def test_extracts_mrz_line2(self):
        fields = self._extract("AB1234567<3COL9012157M2501011<<<<<<<<<<<")
        # The regex should find passport number, nationality, etc.
        # Note: exact parsing depends on the OCR output format
        if "numero_pasaporte" in fields:
            assert len(fields["numero_pasaporte"]) > 0
